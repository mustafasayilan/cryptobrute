from base64 import b64encode
from decimal import Decimal, InvalidOperation
from http.client import HTTPConnection, HTTPException
import json
import re

ADDRESS_PATTERN = re.compile(r"[A-Za-z0-9]{1,90}")
SCRIPT_PATTERN = re.compile(r"(?:[0-9a-fA-F]{2})+")
SATOSHIS_PER_BTC = 100_000_000


class AuditError(RuntimeError):
    pass


class BitcoinRpc:
    """Connect to Bitcoin Core over loopback with cookie authentication."""

    def __init__(self, cookie_path, port, timeout):
        if not 1 <= port <= 65535 or not 1 <= timeout <= 86400:
            raise ValueError("Use a port from 1 to 65535 and a timeout from 1 to 86400 seconds.")
        try:
            credentials = cookie_path.read_bytes().strip()
        except OSError as exc:
            raise AuditError(f"Could not read Bitcoin Core's cookie at {cookie_path}.") from exc
        user, separator, password = credentials.partition(b":")
        if not (user and separator and password):
            raise AuditError("The Bitcoin Core RPC cookie is malformed.")
        self._headers = {
            "Authorization": "Basic " + b64encode(credentials).decode("ascii"),
            "Content-Type": "application/json",
        }
        self._connection = HTTPConnection("127.0.0.1", port, timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._connection.close()

    def call(self, method, params):
        body = json.dumps({"jsonrpc": "2.0", "id": method, "method": method, "params": params})
        try:
            self._connection.request("POST", "/", body, self._headers)
            with self._connection.getresponse() as response:
                status = response.status
                raw = response.read()
        except (OSError, HTTPException) as exc:
            raise AuditError(f"Bitcoin Core RPC {method} failed: {exc}") from exc

        if status == 401:
            raise AuditError("Bitcoin Core rejected the RPC cookie.")
        try:
            payload = json.loads(raw, parse_float=Decimal)
        except (ValueError, UnicodeError) as exc:
            raise AuditError(f"Bitcoin Core returned an invalid RPC response (HTTP {status}).") from exc
        if not isinstance(payload, dict) or payload.get("id") != method:
            raise AuditError(f"Bitcoin Core returned an unexpected response to {method}.")
        if isinstance(error := payload.get("error"), dict):
            raise AuditError(f"Bitcoin Core {method} failed ({error.get('code')}): {error.get('message')}")
        if status != 200 or "result" not in payload:
            raise AuditError(f"Bitcoin Core RPC {method} failed (HTTP {status}).")
        return payload["result"]


def read_addresses(path):
    addresses = {}
    with path.open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, 1):
            address = line.strip()
            if not address:
                continue
            if not ADDRESS_PATTERN.fullmatch(address):
                raise AuditError(f"Line {line_number} must contain one Bitcoin address.")
            addresses.setdefault(address, line_number)
    if not addresses:
        raise AuditError("The address list is empty.")
    return addresses


def to_satoshis(amount):
    try:
        satoshis = Decimal(amount) * SATOSHIS_PER_BTC
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AuditError("Bitcoin Core returned an invalid BTC amount.") from exc
    if not satoshis.is_finite() or satoshis < 0 or satoshis != satoshis.to_integral_value():
        raise AuditError("Bitcoin Core returned an invalid BTC amount.")
    return int(satoshis)


def audit_addresses(rpc, addresses):
    chain = rpc.call("getblockchaininfo", [])
    if not isinstance(chain, dict) or not isinstance(chain.get("chain"), str):
        raise AuditError("Bitcoin Core returned invalid chain information.")
    if chain.get("initialblockdownload") is not False:
        raise AuditError("Bitcoin Core must finish initial block download before the audit.")

    by_script = {}
    for address, line_number in addresses.items():
        validation = rpc.call("validateaddress", [address])
        if not isinstance(validation, dict) or validation.get("isvalid") is not True:
            raise AuditError(f"Bitcoin Core rejected the address on line {line_number}.")
        canonical, script = validation.get("address"), validation.get("scriptPubKey")
        if not isinstance(canonical, str) or not ADDRESS_PATTERN.fullmatch(canonical):
            raise AuditError("Bitcoin Core returned an invalid canonical address.")
        if not isinstance(script, str) or not SCRIPT_PATTERN.fullmatch(script):
            raise AuditError("Bitcoin Core returned an invalid output script.")
        by_script.setdefault(script.lower(), {"address": canonical, "confirmed_satoshis": 0, "utxos": 0})

    descriptors = [f"addr({entry['address']})" for entry in by_script.values()]
    scan = rpc.call("scantxoutset", ["start", descriptors])
    if not isinstance(scan, dict) or scan.get("success") is not True:
        raise AuditError("Bitcoin Core did not finish the UTXO scan.")
    outputs = scan.get("unspents")
    if not isinstance(outputs, list) or not isinstance(scan.get("height"), int):
        raise AuditError("Bitcoin Core returned invalid UTXO scan data.")
    if not isinstance(scan.get("bestblock"), str):
        raise AuditError("Bitcoin Core did not return the scan's block hash.")

    for output in outputs:
        if not isinstance(output, dict) or not isinstance(output.get("scriptPubKey"), str):
            raise AuditError("Bitcoin Core returned an invalid UTXO.")
        entry = by_script.get(output["scriptPubKey"].lower())
        if entry is None:
            raise AuditError("Bitcoin Core returned a UTXO for an unexpected output script.")
        entry["confirmed_satoshis"] += to_satoshis(output.get("amount"))
        entry["utxos"] += 1

    return {
        "network": chain["chain"],
        "height": scan["height"],
        "best_block_hash": scan["bestblock"],
        "addresses": list(by_script.values()),
    }
