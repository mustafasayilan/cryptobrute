from base64 import b64decode, b64encode

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

PROOF_FORMAT = "cryptobrute-ecdsa-secp256k1-sha256-v1"
DEFAULT_MESSAGE = "Cryptobrute local key verification"


def generate_proof(message):
    """Generate an ephemeral key pair and return its public verification data."""
    try:
        private_key = ec.generate_private_key(ec.SECP256K1())
    except UnsupportedAlgorithm as exc:
        raise RuntimeError("The cryptography backend does not support secp256k1.") from exc
    return sign_proof(private_key, message)


def sign_proof(private_key, message):
    try:
        signature = private_key.sign(message.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    except UnsupportedAlgorithm as exc:
        raise RuntimeError("The cryptography backend does not support secp256k1.") from exc

    return {
        "format": PROOF_FORMAT,
        "message": message,
        "public_key_pem": public_key.decode("ascii"),
        "signature_der_base64": b64encode(signature).decode("ascii"),
    }


def verify_proof(proof):
    if not isinstance(proof, dict) or proof.get("format") != PROOF_FORMAT:
        raise ValueError("Unrecognized key proof format.")
    message = proof.get("message")
    public_key_pem = proof.get("public_key_pem")
    signature_base64 = proof.get("signature_der_base64")
    if not all(isinstance(value, str) for value in (message, public_key_pem, signature_base64)):
        raise ValueError("The key proof must contain a message, public key and signature.")

    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("ascii"))
        signature = b64decode(signature_base64, validate=True)
    except (ValueError, UnsupportedAlgorithm) as exc:
        raise ValueError("The key proof contains an invalid public key or signature encoding.") from exc
    if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP256K1):
        raise ValueError("The proof must contain a secp256k1 public key.")
    try:
        public_key.verify(signature, message.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise ValueError("Signature verification failed.") from exc
    except UnsupportedAlgorithm as exc:
        raise RuntimeError("The cryptography backend does not support secp256k1 verification.") from exc
    return public_key
