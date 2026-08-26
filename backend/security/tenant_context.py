"""
Tenant Context & Security Isolation Module.
Ensures every request is strictly bound to the verified university tenant.
"""

import os
from typing import Optional
from flask import g, request, current_app


class TenantContext:
    """Manages the tenant context per request."""

    @staticmethod
    def get_tenant_id() -> str:
        """
        Get current tenant identifier.
        Prioritizes environment configuration / instance binding,
        never trusting arbitrary frontend client parameters.
        """
        if hasattr(g, "tenant_id") and g.tenant_id:
            return g.tenant_id

        # In dedicated Data Plane deployment, tenant_id is configured via environment
        tenant_id = os.environ.get("TENANT_ID") or current_app.config.get("TENANT_ID", "default_university")
        g.tenant_id = tenant_id
        return tenant_id

    @staticmethod
    def get_tenant_slug() -> str:
        """Get the slug/subdomain of the current university."""
        if hasattr(g, "tenant_slug") and g.tenant_slug:
            return g.tenant_slug

        slug = os.environ.get("TENANT_SLUG") or current_app.config.get("TENANT_SLUG", "default")
        g.tenant_slug = slug
        return slug

    @staticmethod
    def verify_request_tenant(user_tenant_id: Optional[str] = None) -> bool:
        """
        Verifies that a user's associated tenant matches the active Data Plane instance.
        Prevents cross-tenant token replay attacks.
        """
        current_tenant = TenantContext.get_tenant_id()
        if user_tenant_id and user_tenant_id != current_tenant:
            return False
        return True
