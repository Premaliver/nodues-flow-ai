"""
Control Plane License Issuer Module.
Issues cryptographically signed Ed25519 licenses for university instances.
"""

import os
import json
import base64
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


class ControlPlaneLicenseIssuer:
    """Platform-side licensing authority for generating signed university subscriptions."""

    def __init__(self, private_key_pem: Optional[str] = None):
        if private_key_pem:
            self.private_key_pem = private_key_pem
        else:
            self.private_key_pem = os.environ.get("CONTROL_PLANE_PRIVATE_KEY", "")

    @staticmethod
    def generate_platform_keypair() -> Dict[str, str]:
        """Generates a new master keypair for the platform control plane."""
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

        return {
            "private_key_pem": private_pem,
            "public_key_pem": public_pem,
        }

    def issue_license(
        self,
        tenant_id: str,
        tenant_slug: str,
        university_name: str,
        plan_name: str = "enterprise",
        valid_days: int = 365,
        grace_period_days: int = 15,
        max_active_students: int = 10000,
        max_departments: int = 25,
        storage_limit_gb: int = 100,
        features: Optional[List[str]] = None,
    ) -> str:
        """
        Mints and signs an enterprise license token.
        """
        if not self.private_key_pem:
            raise ValueError("Control Plane Private Key is required to sign licenses")

        if features is None:
            features = [
                "basic_workflows",
                "admit_card_generation",
                "email_notifications",
                "ai_receipt_ocr",
                "digital_signatures",
                "custom_workflows",
                "audit_export",
                "sso_saml",
            ]

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=valid_days)

        payload: Dict[str, Any] = {
            "license_id": f"lic_{uuid.uuid4().hex[:12]}",
            "tenant_id": tenant_id,
            "tenant_slug": tenant_slug,
            "university_name": university_name,
            "plan_name": plan_name,
            "issued_at": now.isoformat(),
            "valid_from": (now - timedelta(minutes=5)).isoformat(),
            "expires_at": expires_at.isoformat(),
            "grace_period_days": grace_period_days,
            "entitlements": {
                "max_active_students": max_active_students,
                "max_departments": max_departments,
                "storage_limit_gb": storage_limit_gb,
                "features": features,
            },
        }

        private_key = serialization.load_pem_private_key(
            self.private_key_pem.encode("utf-8"), password=None
        )
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise ValueError("Private key must be Ed25519")

        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = private_key.sign(payload_bytes)

        package = {
            "payload": payload,
            "signature": base64.b64encode(signature).decode("utf-8"),
            "algo": "Ed25519",
        }

        return base64.b64encode(json.dumps(package).encode("utf-8")).decode("utf-8")
