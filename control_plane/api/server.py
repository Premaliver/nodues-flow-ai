"""
Control Plane REST API Server.
Handles university onboarding, subscription management, and license issuance.
Operates independently from the university data plane.
"""

import os
import uuid
from flask import Flask, request, jsonify
from control_plane.models.tenant import AVAILABLE_PLANS, TenantRegistration
from control_plane.licensing.issuer import ControlPlaneLicenseIssuer

# Global in-memory registry (can be backed by Control Plane PostgreSQL)
_TENANTS_DB = {}
_KEYPAIR = ControlPlaneLicenseIssuer.generate_platform_keypair()
_ISSUER = ControlPlaneLicenseIssuer(private_key_pem=_KEYPAIR["private_key_pem"])


def create_control_plane_app() -> Flask:
    app = Flask(__name__)

    @app.route("/api/v1/plans", methods=["GET"])
    def list_plans():
        """Returns available commercial SaaS subscription plans."""
        plans = [
            {
                "plan_id": p.plan_id,
                "name": p.name,
                "price_monthly_usd": p.price_monthly_usd,
                "price_annual_usd": p.price_annual_usd,
                "max_active_students": p.max_active_students,
                "max_departments": p.max_departments,
                "storage_limit_gb": p.storage_limit_gb,
                "features": p.features,
            }
            for p in AVAILABLE_PLANS.values()
        ]
        return jsonify({"success": True, "data": plans})

    @app.route("/api/v1/public-key", methods=["GET"])
    def get_public_key():
        """Returns the active Ed25519 public key used for license signature verification."""
        return jsonify({"success": True, "public_key_pem": _KEYPAIR["public_key_pem"]})

    @app.route("/api/v1/tenants/onboard", methods=["POST"])
    def onboard_tenant():
        """
        Onboards a new university tenant, provisions subscription, and mints signed license.
        """
        data = request.get_json(silent=True) or {}
        university_name = data.get("university_name", "").strip()
        tenant_slug = data.get("tenant_slug", "").strip().lower()
        admin_email = data.get("admin_email", "").strip().lower()
        plan_id = data.get("plan_id", "professional")
        deployment_type = data.get("deployment_type", "managed_saas")

        if not university_name or not tenant_slug or not admin_email:
            return jsonify({"success": False, "message": "university_name, tenant_slug, and admin_email are required"}), 400

        if plan_id not in AVAILABLE_PLANS:
            return jsonify({"success": False, "message": f"Invalid plan. Available: {list(AVAILABLE_PLANS.keys())}"}), 400

        tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
        plan = AVAILABLE_PLANS[plan_id]

        # Mint cryptographic license
        license_token = _ISSUER.issue_license(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            university_name=university_name,
            plan_name=plan_id,
            valid_days=365,
            grace_period_days=15,
            max_active_students=plan.max_active_students,
            max_departments=plan.max_departments,
            storage_limit_gb=plan.storage_limit_gb,
            features=plan.features,
        )

        tenant = TenantRegistration(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            university_name=university_name,
            admin_email=admin_email,
            plan_id=plan_id,
            subscription_status="active",
            deployment_type=deployment_type,
            latest_license_token=license_token,
        )
        _TENANTS_DB[tenant_id] = tenant

        return jsonify({
            "success": True,
            "message": f"University '{university_name}' successfully onboarded!",
            "data": {
                "tenant_id": tenant.tenant_id,
                "tenant_slug": tenant.tenant_slug,
                "university_name": tenant.university_name,
                "plan_id": tenant.plan_id,
                "subscription_status": tenant.subscription_status,
                "deployment_type": tenant.deployment_type,
                "license_token": license_token,
                "public_key_pem": _KEYPAIR["public_key_pem"],
            }
        }), 201

    @app.route("/api/v1/heartbeat", methods=["POST"])
    def record_heartbeat():
        """Receives non-sensitive health telemetry from university instances."""
        data = request.get_json(silent=True) or {}
        tenant_id = data.get("tenant_id")
        if not tenant_id or tenant_id not in _TENANTS_DB:
            return jsonify({"success": False, "message": "Unknown tenant"}), 404

        return jsonify({"success": True, "message": "Heartbeat received"})

    return app


if __name__ == "__main__":
    app = create_control_plane_app()
    app.run(port=8000, debug=True)
