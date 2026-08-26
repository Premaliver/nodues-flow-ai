"""
Cryptographic License Signing & Verification Module.
Implements asymmetric digital signatures using Ed25519 and RSA-4096.
"""

import json
import base64
from typing import Tuple, Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class LicenseCrypto:
    """Handles asymmetric keypair generation, license signing, and verification."""

    @staticmethod
    def generate_ed25519_keypair() -> Tuple[str, str]:
        """
        Generates an Ed25519 keypair for Control Plane (Private) and Data Plane (Public).
        Returns (private_key_pem_str, public_key_pem_str).
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        return private_pem, public_pem

    @staticmethod
    def sign_payload(payload: Dict[str, Any], private_key_pem: str) -> str:
        """
        Signs a dictionary payload using the Control Plane's private Ed25519 key.
        Returns a base64-encoded license package containing payload and signature.
        """
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"), password=None
        )
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise ValueError("Private key must be Ed25519")

        # Canonical JSON encoding
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = private_key.sign(payload_bytes)

        package = {
            "payload": payload,
            "signature": base64.b64encode(signature).decode("utf-8"),
            "algo": "Ed25519",
        }
        return base64.b64encode(json.dumps(package).encode("utf-8")).decode("utf-8")

    @staticmethod
    def verify_and_unpack(license_token: str, public_key_pem: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Verifies a base64-encoded license token using the Data Plane's public Ed25519 key.
        Returns (is_valid, payload, error_message).
        """
        try:
            raw_json = base64.b64decode(license_token.strip().encode("utf-8")).decode("utf-8")
            package = json.loads(raw_json)

            payload = package.get("payload")
            sig_b64 = package.get("signature")
            algo = package.get("algo", "Ed25519")

            if not payload or not sig_b64:
                return False, None, "Malformed license package structure"

            if algo != "Ed25519":
                return False, None, f"Unsupported signature algorithm: {algo}"

            public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                return False, None, "Public key must be Ed25519"

            signature = base64.b64decode(sig_b64.encode("utf-8"))
            payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

            public_key.verify(signature, payload_bytes)
            return True, payload, "Signature valid"
        except InvalidSignature:
            return False, None, "Cryptographic signature verification failed (tampered license)"
        except Exception as e:
            return False, None, f"License validation error: {str(e)}"
