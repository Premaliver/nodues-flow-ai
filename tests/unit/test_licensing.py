"""
Unit tests for Cryptographic Licensing & Entitlement Engine.
"""

import pytest
from datetime import datetime, timezone, timedelta
from control_plane.licensing.issuer import ControlPlaneLicenseIssuer
from backend.licensing.crypto import LicenseCrypto
from backend.licensing.license_manager import LicenseManager, LicenseStatus, LicenseEntitlements


def test_ed25519_keypair_generation():
    """Verify that Ed25519 keypairs are generated in valid PEM format."""
    keys = ControlPlaneLicenseIssuer.generate_platform_keypair()
    assert "BEGIN PRIVATE KEY" in keys["private_key_pem"]
    assert "BEGIN PUBLIC KEY" in keys["public_key_pem"]


def test_license_signing_and_verification():
    """Verify end-to-end signing by Control Plane and validation by Data Plane."""
    keys = ControlPlaneLicenseIssuer.generate_platform_keypair()
    issuer = ControlPlaneLicenseIssuer(private_key_pem=keys["private_key_pem"])

    token = issuer.issue_license(
        tenant_id="tenant_stanford_01",
        tenant_slug="stanford",
        university_name="Stanford University",
        plan_name="enterprise",
        valid_days=30,
        max_active_students=15000,
        max_departments=30,
        storage_limit_gb=200,
        features=["ai_receipt_ocr", "admit_card_generation"],
    )

    is_valid, payload, err = LicenseCrypto.verify_and_unpack(token, keys["public_key_pem"])
    assert is_valid is True
    assert payload is not None
    assert payload["tenant_id"] == "tenant_stanford_01"
    assert payload["plan_name"] == "enterprise"
    assert payload["entitlements"]["max_active_students"] == 15000
    assert "ai_receipt_ocr" in payload["entitlements"]["features"]


def test_tampered_license_rejection():
    """Verify that any modification to the license payload fails cryptographic verification."""
    import base64
    import json

    keys = ControlPlaneLicenseIssuer.generate_platform_keypair()
    issuer = ControlPlaneLicenseIssuer(private_key_pem=keys["private_key_pem"])

    token = issuer.issue_license(
        tenant_id="tenant_mit_01",
        tenant_slug="mit",
        university_name="MIT",
        plan_name="starter",
        valid_days=30,
    )

    # Tamper with payload (e.g. modify plan from starter to enterprise)
    raw_json = base64.b64decode(token.encode("utf-8")).decode("utf-8")
    package = json.loads(raw_json)
    package["payload"]["plan_name"] = "enterprise"
    package["payload"]["entitlements"]["max_active_students"] = 999999
    tampered_token = base64.b64encode(json.dumps(package).encode("utf-8")).decode("utf-8")

    is_valid, payload, err = LicenseCrypto.verify_and_unpack(tampered_token, keys["public_key_pem"])
    assert is_valid is False
    assert payload is None
    assert "tampered" in err.lower() or "failed" in err.lower()
