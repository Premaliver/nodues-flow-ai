"""
Control Plane Data Models.
Tracks tenant registration, subscription plans, billing status, and license issuance.
NOTE: Contains ZERO sensitive student PII or institutional document records.
"""

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class SubscriptionPlan:
    plan_id: str
    name: str
    price_monthly_usd: float
    price_annual_usd: float
    max_active_students: int
    max_departments: int
    storage_limit_gb: int
    features: List[str]


# Predefined Commercial SaaS Subscription Tiers
AVAILABLE_PLANS: Dict[str, SubscriptionPlan] = {
    "starter": SubscriptionPlan(
        plan_id="starter",
        name="Starter College Plan",
        price_monthly_usd=199.0,
        price_annual_usd=1990.0,
        max_active_students=2000,
        max_departments=8,
        storage_limit_gb=20,
        features=["basic_workflows", "admit_card_generation", "email_notifications", "audit_export"],
    ),
    "professional": SubscriptionPlan(
        plan_id="professional",
        name="Professional University Plan",
        price_monthly_usd=499.0,
        price_annual_usd=4990.0,
        max_active_students=10000,
        max_departments=25,
        storage_limit_gb=100,
        features=[
            "basic_workflows",
            "admit_card_generation",
            "email_notifications",
            "ai_receipt_ocr",
            "digital_signatures",
            "audit_export",
        ],
    ),
    "enterprise": SubscriptionPlan(
        plan_id="enterprise",
        name="Enterprise Multi-Campus Plan",
        price_monthly_usd=999.0,
        price_annual_usd=9990.0,
        max_active_students=50000,
        max_departments=100,
        storage_limit_gb=500,
        features=[
            "basic_workflows",
            "admit_card_generation",
            "email_notifications",
            "ai_receipt_ocr",
            "digital_signatures",
            "custom_workflows",
            "audit_export",
            "sso_saml",
            "priority_sla",
        ],
    ),
}


@dataclass
class TenantRegistration:
    tenant_id: str
    tenant_slug: str
    university_name: str
    admin_email: str
    plan_id: str
    subscription_status: str  # active, past_due, canceled, trial
    deployment_type: str      # managed_saas, private_cloud, on_premise
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_heartbeat_at: Optional[str] = None
    latest_license_token: Optional[str] = None
