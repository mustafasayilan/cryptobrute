from contextlib import redirect_stderr, redirect_stdout
from importlib.util import find_spec
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptobrute_lab.cli import main

REPOSITORY = Path(__file__).resolve().parents[1]
EXAMPLE_ADDRESSES = REPOSITORY / "examples" / "regtest-addresses.txt"


@unittest.skipUnless(find_spec("cryptography"), "Install requirements-key-demo.txt to test regtest matching.")
class RegtestTests(unittest.TestCase):
    def test_address_matches_the_public_fixture_and_signature(self):
        from cryptobrute_lab.key_demo import verify_proof
        from cryptobrute_lab.regtest import match_regtest_address

        expected = "bcrt1qw508d6qejxtdg4y5r3zarvary0c5xw7kygt080"
        result = match_regtest_address(EXAMPLE_ADDRESSES)
        self.assertEqual(result["regtest_address"], expected)
        self.assertEqual(result["key_source"], "public_test_vector")
        self.assertEqual(result["public_keys_checked"], 1)
        self.assertEqual(result["distinct_addresses_checked"], 2)
        self.assertTrue(result["matched"])
        self.assertEqual(result["matched_line"], 2)
        verify_proof(result["proof"])

    def test_fresh_key_can_be_matched_against_a_user_written_file(self):
        proof_output, match_output = StringIO(), StringIO()
        with redirect_stdout(proof_output):
            self.assertEqual(main(["key-demo", "--message", "Fresh key match"]), 0)
        proof = json.loads(proof_output.getvalue())
        with TemporaryDirectory() as directory:
            root = Path(directory)
            proof_path, address_path = root / "proof.json", root / "addresses.txt"
            proof_path.write_text(proof_output.getvalue(), encoding="utf-8")
            address_path.write_text(proof["regtest_address"] + "\n", encoding="utf-8")
            with redirect_stdout(match_output):
                self.assertEqual(main(["regtest-match", "-i", str(address_path), "--proof", str(proof_path)]), 0)
        result = json.loads(match_output.getvalue())
        self.assertEqual(result["key_source"], "signed_proof")
        self.assertEqual(result["public_keys_checked"], 1)
        self.assertEqual(result["matched_line"], 1)

    def test_cli_miss_reports_no_line_and_keeps_the_signed_proof(self):
        from cryptobrute_lab.key_demo import verify_proof

        first = EXAMPLE_ADDRESSES.read_text(encoding="utf-8").splitlines()[0]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "addresses.txt"
            path.write_text(first + "\n", encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["regtest-match", "-i", str(path)]), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result["matched"])
        self.assertIsNone(result["matched_line"])
        self.assertEqual(result["distinct_addresses_checked"], 1)
        self.assertGreater(result["elapsed_ns"], 0)
        verify_proof(result["proof"])

    def test_rejects_wrong_network_or_bad_checksum(self):
        from cryptobrute_lab.regtest import validate_regtest_addresses

        with self.assertRaisesRegex(ValueError, "Line 3.*regtest"):
            validate_regtest_addresses({"bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4": 3})
        with self.assertRaisesRegex(ValueError, "Line 5.*checksum"):
            validate_regtest_addresses({"bcrt1qw508d6qejxtdg4y5r3zarvary0c5xw7kygt08q": 5})

    def test_verifier_rejects_a_changed_regtest_address(self):
        from cryptobrute_lab.regtest import match_regtest_address

        report = match_regtest_address(EXAMPLE_ADDRESSES)
        report["regtest_address"] = EXAMPLE_ADDRESSES.read_text(encoding="utf-8").splitlines()[0]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "changed.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            error = StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(["verify-key-demo", str(path)]), 1)
        self.assertIn("claimed regtest address", error.getvalue())
