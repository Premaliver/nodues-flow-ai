"""Tenant Resolution and Multi-Tenant Scoping Engine.

Resolves the active university tenant per request via:
1. Subdomain (e.g. abc.smartnodues.com)
2. Custom Domain (e.g. nodues.abcuniversity.edu)
3. Session state (e.g. session['university_id'] / session['university_slug'])
4. Request headers (X-Tenant-Slug / X-Tenant-Id)
5. Query parameter (?tenant=slug)
6. Authenticated User's associated university_id
"""

import uuid
from typing import Optional
from functools import wraps
from flask import Flask, request, g, session, jsonify, redirect, url_for
from models.university import UniversityTenant


RESERVED_SUBDOMAINS = {"admin", "www", "app", "api", "platform", "localhost", "127", "0"}


def get_current_tenant() -> Optional[UniversityTenant]:
    """Retrieve the resolved UniversityTenant for the current request context."""
    return _resolve_tenant_from_request()


def get_current_tenant_id() -> Optional[uuid.UUID]:
    """Retrieve the active tenant UUID."""
    univ_id = session.get("university_id")
    if univ_id:
        try:
            return uuid.UUID(str(univ_id))
        except Exception:
            pass
    tenant = get_current_tenant()
    return tenant.id if tenant else None


def _resolve_tenant_from_request() -> Optional[UniversityTenant]:
    """Internal resolver inspecting host, headers, session, and query params."""
    from models import db

    try:
        # 1. Session state (Explicitly active University session takes priority for logged-in sessions)
        univ_id = session.get("university_id")
        if univ_id:
            try:
                t = db.session.get(UniversityTenant, uuid.UUID(str(univ_id)))
                if t:
                    return t
            except Exception:
                db.session.rollback()

        univ_slug = session.get("university_slug")
        if univ_slug:
            try:
                t = UniversityTenant.query.filter_by(slug=univ_slug).first()
                if t:
                    return t
            except Exception:
                db.session.rollback()

        # 2. Request Header (X-Tenant-Slug or X-Tenant-Id)
        header_slug = request.headers.get("X-Tenant-Slug", "").strip().lower()
        if header_slug:
            try:
                hdr_tenant = UniversityTenant.query.filter_by(slug=header_slug).first()
                if hdr_tenant:
                    return hdr_tenant
            except Exception:
                db.session.rollback()

        header_id = request.headers.get("X-Tenant-Id", "").strip()
        if header_id:
            try:
                t = db.session.get(UniversityTenant, uuid.UUID(header_id))
                if t:
                    return t
            except Exception:
                db.session.rollback()

        # 3. Custom Domain / Subdomain check from Host header
        host = request.host.split(":")[0].lower().strip()
        
        # Check custom domain match (e.g., nodues.abcuniversity.edu)
        try:
            custom_tenant = UniversityTenant.query.filter_by(custom_domain=host).first()
            if custom_tenant:
                return custom_tenant
        except Exception:
            db.session.rollback()

        # Check subdomain match (e.g., abc.smartnodues.com)
        host_parts = host.split(".")
        if len(host_parts) >= 3 and host_parts[0] not in RESERVED_SUBDOMAINS:
            subdomain_slug = host_parts[0]
            try:
                subdomain_tenant = UniversityTenant.query.filter_by(slug=subdomain_slug).first()
                if subdomain_tenant:
                    return subdomain_tenant
            except Exception:
                db.session.rollback()

        # 4. Query param (?tenant=slug)
        tenant_param = request.args.get("tenant", "").strip().lower()
        if tenant_param:
            try:
                param_tenant = UniversityTenant.query.filter(
                    (UniversityTenant.slug == tenant_param) |
                    (UniversityTenant.official_email.ilike(f"%{tenant_param}%"))
                ).first()
                if param_tenant:
                    return param_tenant
            except Exception:
                db.session.rollback()

        # 5. Authenticated User's university link
        from flask_login import current_user
        if current_user and current_user.is_authenticated and hasattr(current_user, "university_id") and current_user.university_id:
            try:
                user_tenant = db.session.get(UniversityTenant, current_user.university_id)
                if user_tenant:
                    return user_tenant
            except Exception:
                db.session.rollback()

        # No default fallback — unassigned/unscoped requests remain tenant-neutral
        return None
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


def tenant_required(f):
    """Decorator ensuring that a request is scoped to an active valid university tenant."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        tenant = get_current_tenant()
        if not tenant:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "message": "University Tenant context required."}), 400
            return redirect(url_for("university.login"))
        return f(*args, **kwargs)
    return decorated_function


def init_tenant_resolver(app: Flask) -> None:
    """Initialize tenant resolver hooks and template context processors."""

    @app.before_request
    def resolve_tenant_hook():
        # Populate g.current_tenant and g.university_id on every request
        tenant = get_current_tenant()
        g.current_tenant = tenant
        g.university_id = tenant.id if tenant else None

    @app.context_processor
    def inject_tenant_context():
        tenant = getattr(g, "current_tenant", None)
        return {
            "current_tenant": tenant,
            "tenant_name": tenant.name if tenant else "Smart NoDues AI",
            "tenant_slug": tenant.slug if tenant else "",
            "tenant_logo": tenant.logo_url if (tenant and tenant.logo_url) else "/static/images/logo.png",
            "tenant_primary_color": tenant.primary_color if (tenant and tenant.primary_color) else "#4f46e5",
            "tenant_accent_color": tenant.accent_color if (tenant and tenant.accent_color) else "#6366f1",
            "tenant_banner_text": tenant.banner_text if (tenant and tenant.banner_text) else None,
        }
