from hashlib import new, sha256
from time import perf_counter_ns

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .audit import read_addresses
from .key_demo import sign_proof, verify_proof

REGTEST_HRP = "bcrt"
BECH32_ALPHABET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BECH32_GENERATORS = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
FIXTURE_MESSAGE = "Cryptobrute regtest address match v1"
FIXTURE_SCALAR = 1


def regtest_checksum(values):
    prefix = [ord(character) >> 5 for character in REGTEST_HRP]
    suffix = [ord(character) & 31 for character in REGTEST_HRP]
    checksum = 1
    for value in (*prefix, 0, *suffix, *values):
        top = checksum >> 25
        checksum = ((checksum & 0x1FFFFFF) << 5) ^ value
        for position, generator in enumerate(BECH32_GENERATORS):
            if (top >> position) & 1:
                checksum ^= generator
    return checksum


def regtest_address(public_key):
    compressed = public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint
    )
    try:
        key_hash = new("ripemd160", sha256(compressed).digest()).digest()
    except ValueError as exc:
        raise RuntimeError("The regtest demo requires RIPEMD-160 support in Python's OpenSSL.") from exc

    # P2WPKH uses witness version zero and exactly 160 bits, so no padding is needed.
    bits = int.from_bytes(key_hash, "big")
    values = [0] + [(bits >> offset) & 31 for offset in range(155, -1, -5)]
    checksum = regtest_checksum([*values, 0, 0, 0, 0, 0, 0]) ^ 1
    values.extend((checksum >> offset) & 31 for offset in range(25, -1, -5))
    return REGTEST_HRP + "1" + "".join(BECH32_ALPHABET[value] for value in values)


def validate_regtest_addresses(addresses):
    for address, line_number in addresses.items():
        if not (len(address) == 44 and address.startswith("bcrt1q")):
            raise ValueError(f"Line {line_number} must contain a lowercase regtest P2WPKH address.")
        try:
            values = [BECH32_ALPHABET.index(character) for character in address[5:]]
        except ValueError as exc:
            raise ValueError(f"Line {line_number} has invalid Bech32 characters.") from exc
        if regtest_checksum(values) != 1:
            raise ValueError(f"Line {line_number} has an invalid Bech32 checksum.")


def verified_regtest_address(proof):
    address = regtest_address(verify_proof(proof))
    if proof.get("regtest_address", address) != address:
        raise ValueError("The claimed regtest address does not match the verified public key.")
    return address


def match_regtest_address(path, proof=None):
    """Check one proved public key against a regtest address file."""
    start = perf_counter_ns()
    addresses = read_addresses(path)
    validate_regtest_addresses(addresses)
    key_source = "signed_proof"
    if proof is None:
        private_key = ec.derive_private_key(FIXTURE_SCALAR, ec.SECP256K1())
        proof = sign_proof(private_key, FIXTURE_MESSAGE)
        key_source = "public_test_vector"
    address = verified_regtest_address(proof)
    matched_line = addresses.get(address)
    return {
        "network": "regtest",
        "regtest_address": address,
        "key_source": key_source,
        "public_keys_checked": 1,
        "distinct_addresses_checked": len(addresses),
        "matched": matched_line is not None,
        "matched_line": matched_line,
        "elapsed_ns": perf_counter_ns() - start,
        "proof": proof,
    }
