from contextlib import redirect_stderr, redirect_stdout
from importlib.util import find_spec
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptobrute_lab.cli import main


@unittest.skipUnless(find_spec("cryptography"), "Install requirements-key-demo.txt to test the key demo.")
class KeyDemoTests(unittest.TestCase):
    def test_fresh_keys_and_independently_verifiable_signatures(self):
        from base64 import b64decode

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        from cryptobrute_lab.key_demo import generate_proof

        message = "Yerel doğrulama"
        first = generate_proof(message)
        second = generate_proof(message)
        self.assertNotEqual(first["public_key_pem"], second["public_key_pem"])
        self.assertEqual(set(first), {"format", "message", "public_key_pem", "signature_der_base64"})
        public_key = serialization.load_pem_public_key(first["public_key_pem"].encode("ascii"))
        self.assertIsInstance(public_key.curve, ec.SECP256K1)
        public_key.verify(
            b64decode(first["signature_der_base64"]),
            message.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )

    def test_tampered_message_and_mismatched_public_key_fail(self):
        from cryptobrute_lab.key_demo import generate_proof, verify_proof

        proof = generate_proof("Original")
        other = generate_proof("Original")
        for modified in (
            {**proof, "message": "Modified"},
            {**proof, "public_key_pem": other["public_key_pem"]},
            {**proof, "signature_der_base64": other["signature_der_base64"]},
        ):
            with self.subTest(modified=modified):
                with self.assertRaisesRegex(ValueError, "Signature verification failed"):
                    verify_proof(modified)

    def test_cli_round_trip_and_tamper_exit(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["key-demo", "--message", "CLI check"]), 0)
        proof = json.loads(output.getvalue())

        with TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text(json.dumps(proof), encoding="utf-8-sig")
            verification = StringIO()
            with redirect_stdout(verification):
                self.assertEqual(main(["verify-key-demo", str(path)]), 0)
            self.assertTrue(json.loads(verification.getvalue())["verified"])

            path.write_text(json.dumps({**proof, "message": "Different"}), encoding="utf-8")
            error = StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(["verify-key-demo", str(path)]), 1)
            self.assertIn("Signature verification failed", error.getvalue())
