from base64 import b64encode
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cryptobrute_lab.audit import AuditError, BitcoinRpc, audit_addresses, read_addresses, to_satoshis


class AuditTests(unittest.TestCase):
    def test_file_accepts_bom_whitespace_and_duplicates(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "addresses.txt"
            path.write_text(" AddressOne \n\nAddressTwo\nAddressOne\n", encoding="utf-8-sig")
            self.assertEqual(read_addresses(path), {"AddressOne": 1, "AddressTwo": 3})

    def test_file_rejects_descriptor_syntax(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "addresses.txt"
            path.write_text("addr(AddressOne)\n", encoding="utf-8")
            with self.assertRaisesRegex(AuditError, "Line 1"):
                read_addresses(path)

    def test_file_rejects_empty_input(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "addresses.txt"
            path.write_text("\n   \n", encoding="utf-8")
            with self.assertRaisesRegex(AuditError, "empty"):
                read_addresses(path)

    def test_converts_decimal_btc_to_exact_satoshis(self):
        self.assertEqual(to_satoshis(Decimal("0.00000001")), 1)
        self.assertEqual(to_satoshis(Decimal("12.12345678")), 1_212_345_678)
        for amount in (Decimal("0.000000001"), Decimal("NaN"), Decimal("-0.01"), None):
            with self.subTest(amount=amount):
                with self.assertRaises(AuditError):
                    to_satoshis(amount)

    def test_audit_uses_one_scan_and_preserves_zero_balances(self):
        with patch("cryptobrute_lab.audit.HTTPConnection") as connection:
            http = connection.return_value
            response = http.getresponse.return_value.__enter__.return_value
            response.status = 200
            response.read.side_effect = [
                b'{"jsonrpc":"2.0","id":"getblockchaininfo","result":{"chain":"regtest","initialblockdownload":false}}',
                b'{"jsonrpc":"2.0","id":"validateaddress","result":{"isvalid":true,"address":"AddressOne","scriptPubKey":"0014"}}',
                b'{"jsonrpc":"2.0","id":"validateaddress","result":{"isvalid":true,"address":"AddressTwo","scriptPubKey":"0020"}}',
                b'{"jsonrpc":"2.0","id":"validateaddress","result":{"isvalid":true,"address":"AddressOne","scriptPubKey":"0014"}}',
                b'{"jsonrpc":"2.0","id":"scantxoutset","result":{"success":true,"height":101,"bestblock":"ab","unspents":[{"scriptPubKey":"0014","amount":0.00000001},{"scriptPubKey":"0014","amount":0.1}]}}',
            ]
            with TemporaryDirectory() as directory:
                cookie = Path(directory) / ".cookie"
                cookie.write_bytes(b"__cookie__:fixture")
                with BitcoinRpc(cookie, 18443, 3) as rpc:
                    result = audit_addresses(rpc, {"AddressOne": 1, "AddressTwo": 2, "ADDRESSONE": 3})

        connection.assert_called_once_with("127.0.0.1", 18443, timeout=3)
        http.close.assert_called_once_with()
        requests = [call.args for call in http.request.call_args_list]
        payloads = [json.loads(body) for _, _, body, _ in requests]
        self.assertTrue(all(method == "POST" and path == "/" for method, path, _, _ in requests))
        self.assertTrue(all(payload["jsonrpc"] == "2.0" for payload in payloads))
        self.assertEqual(
            [payload["method"] for payload in payloads],
            ["getblockchaininfo", "validateaddress", "validateaddress", "validateaddress", "scantxoutset"],
        )
        self.assertEqual(payloads[-1]["params"], ["start", ["addr(AddressOne)", "addr(AddressTwo)"]])
        self.assertEqual(requests[0][3]["Authorization"], "Basic " + b64encode(b"__cookie__:fixture").decode())
        self.assertEqual(
            result,
            {
                "network": "regtest",
                "height": 101,
                "best_block_hash": "ab",
                "addresses": [
                    {"address": "AddressOne", "confirmed_satoshis": 10_000_001, "utxos": 2},
                    {"address": "AddressTwo", "confirmed_satoshis": 0, "utxos": 0},
                ],
            },
        )

    def test_rejects_unsynced_node_before_a_scan(self):
        with patch("cryptobrute_lab.audit.BitcoinRpc") as rpc_class:
            rpc = rpc_class.return_value
            rpc.call.return_value = {"chain": "main", "initialblockdownload": True}
            with self.assertRaisesRegex(AuditError, "initial block download"):
                audit_addresses(rpc, {"AddressOne": 1})
            rpc.call.assert_called_once_with("getblockchaininfo", [])

    def test_rejects_invalid_address_before_a_scan(self):
        with patch("cryptobrute_lab.audit.BitcoinRpc") as rpc_class:
            rpc = rpc_class.return_value
            rpc.call.side_effect = [{"chain": "regtest", "initialblockdownload": False}, {"isvalid": False}]
            with self.assertRaisesRegex(AuditError, "line 4"):
                audit_addresses(rpc, {"WrongNetwork": 4})
            self.assertEqual(rpc.call.call_count, 2)

    def test_rejects_incomplete_scan(self):
        with patch("cryptobrute_lab.audit.BitcoinRpc") as rpc_class:
            rpc = rpc_class.return_value
            rpc.call.side_effect = [
                {"chain": "regtest", "initialblockdownload": False},
                {"isvalid": True, "address": "AddressOne", "scriptPubKey": "0014"},
                {"success": False},
            ]
            with self.assertRaisesRegex(AuditError, "did not finish"):
                audit_addresses(rpc, {"AddressOne": 1})
