"""
License Manager & Entitlements Engine.
Evaluates plan limits, non-destructive expiry lifecycles, and offline caching.
"""

import os
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict, Any, Optional, List
from flask import current_app

from .crypto import LicenseCrypto


class LicenseStatus(str, Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    GRACE_PERIOD = "grace_period"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    INVALID = "invalid"


@dataclass
class LicenseEntitlements:
    max_active_students: int = 500
    max_departments: int = 10
    storage_limit_gb: int = 20
    features: List[str] = field(default_factory=lambda: [
        "basic_workflows",
        "admit_card_generation",
        "email_notifications",
    ])


@dataclass
class LicenseData:
    license_id: str
    tenant_id: str
    tenant_slug: str
    university_name: str
    plan_name: str
    issued_at: datetime
    valid_from: datetime
    expires_at: datetime
    grace_period_days: int = 15
    entitlements: LicenseEntitlements = field(default_factory=LicenseEntitlements)


class LicenseManager:
    """Manages local license validation, entitlements, and state transitions."""

    _cached_license: Optional[LicenseData] = None
    _cached_status: Optional[LicenseStatus] = None
    _last_checked_at: Optional[datetime] = None

    @classmethod
    def load_license(cls) -> Tuple[LicenseStatus, Optional[LicenseData], str]:
        """
        Loads and verifies the university license.
        Checks in-memory cache, filesystem, and environment variables.
        """
        public_key_pem = os.environ.get("LICENSE_PUBLIC_KEY") or current_app.config.get("LICENSE_PUBLIC_KEY", "")
        license_token = os.environ.get("LICENSE_TOKEN")

        license_file_path = os.environ.get("LICENSE_FILE_PATH") or current_app.config.get("LICENSE_FILE_PATH")
        if not license_token and license_file_path and os.path.exists(license_file_path):
            try:
                with open(license_file_path, "r", encoding="utf-8") as f:
                    license_token = f.read().strip()
            except Exception as e:
                return LicenseStatus.INVALID, None, f"Failed to read license file: {e}"

        # If no license token is configured, evaluate default Trial mode
        if not license_token or not public_key_pem:
            # Default fallback Trial (active for evaluation)
            trial_data = LicenseData(
                license_id="trial_demo_license",
                tenant_id=current_app.config.get("TENANT_ID", "default_tenant"),
                tenant_slug=current_app.config.get("TENANT_SLUG", "default"),
                university_name=current_app.config.get("UNIVERSITY_NAME", "Smart NoDues University"),
                plan_name="community_trial",
                issued_at=datetime.now(timezone.utc),
                valid_from=datetime.now(timezone.utc) - timedelta(days=1),
                expires_at=datetime.now(timezone.utc) + timedelta(days=90),
                grace_period_days=15,
                entitlements=LicenseEntitlements(
                    max_active_students=1000,
                    max_departments=15,
                    storage_limit_gb=25,
                    features=[
                        "basic_workflows",
                        "admit_card_generation",
                        "email_notifications",
                        "ai_receipt_ocr",
                        "audit_export",
                    ],
                ),
            )
            return LicenseStatus.TRIAL, trial_data, "Running in trial mode"

        # Verify cryptographic signature
        is_valid, payload, err = LicenseCrypto.verify_and_unpack(license_token, public_key_pem)
        if not is_valid or not payload:
            return LicenseStatus.INVALID, None, err

        try:
            entitlements_raw = payload.get("entitlements", {})
            entitlements = LicenseEntitlements(
                max_active_students=int(entitlements_raw.get("max_active_students", 500)),
                max_departments=int(entitlements_raw.get("max_departments", 10)),
                storage_limit_gb=int(entitlements_raw.get("storage_limit_gb", 20)),
                features=entitlements_raw.get("features", []),
            )

            lic_data = LicenseData(
                license_id=payload.get("license_id", "unknown"),
                tenant_id=payload.get("tenant_id", "default_tenant"),
                tenant_slug=payload.get("tenant_slug", "default"),
                university_name=payload.get("university_name", "Smart NoDues University"),
                plan_name=payload.get("plan_name", "standard"),
                issued_at=datetime.fromisoformat(payload.get("issued_at")),
                valid_from=datetime.fromisoformat(payload.get("valid_from")),
                expires_at=datetime.fromisoformat(payload.get("expires_at")),
                grace_period_days=int(payload.get("grace_period_days", 15)),
                entitlements=entitlements,
            )

            # Determine lifecycle state based on UTC time
            now = datetime.now(timezone.utc)
            if now < lic_data.valid_from:
                return LicenseStatus.INVALID, lic_data, "License not yet valid"

            if now <= lic_data.expires_at:
                return LicenseStatus.ACTIVE, lic_data, "License active"

            grace_expiry = lic_data.expires_at + timedelta(days=lic_data.grace_period_days)
            if now <= grace_expiry:
                return LicenseStatus.GRACE_PERIOD, lic_data, f"License expired. Grace period active until {grace_expiry.strftime('%Y-%m-%d')}"

            return LicenseStatus.SUSPENDED, lic_data, "Subscription suspended (read-only/export-only mode)"
        except Exception as e:
            return LicenseStatus.INVALID, None, f"Error parsing license payload: {str(e)}"

    @classmethod
    def get_license_info(cls) -> Dict[str, Any]:
        """Returns structured dictionary of the active license for dashboard display."""
        status, lic_data, message = cls.load_license()
        if not lic_data:
            return {
                "status": status.value,
                "is_active": False,
                "message": message,
            }

        return {
            "status": status.value,
            "is_active": status in (LicenseStatus.ACTIVE, LicenseStatus.TRIAL, LicenseStatus.GRACE_PERIOD),
            "is_read_only": status in (LicenseStatus.SUSPENDED, LicenseStatus.EXPIRED),
            "license_id": lic_data.license_id,
            "tenant_id": lic_data.tenant_id,
            "university_name": lic_data.university_name,
            "plan_name": lic_data.plan_name,
            "expires_at": lic_data.expires_at.isoformat(),
            "grace_period_days": lic_data.grace_period_days,
            "message": message,
            "entitlements": {
                "max_active_students": lic_data.entitlements.max_active_students,
                "max_departments": lic_data.entitlements.max_departments,
                "storage_limit_gb": lic_data.entitlements.storage_limit_gb,
                "features": lic_data.entitlements.features,
            },
        }

    @classmethod
    def has_feature(cls, feature_name: str) -> bool:
        """Verifies if the specified feature is allowed under the current plan."""
        status, lic_data, _ = cls.load_license()
        if status in (LicenseStatus.SUSPENDED, LicenseStatus.EXPIRED, LicenseStatus.INVALID):
            return False
        if not lic_data:
            return False
        return feature_name in lic_data.entitlements.features

    @classmethod
    def check_student_quota(cls, current_student_count: int) -> bool:
        """Checks if active student count is within plan limit."""
        status, lic_data, _ = cls.load_license()
        if not lic_data:
            return False
        return current_student_count < lic_data.entitlements.max_active_students
