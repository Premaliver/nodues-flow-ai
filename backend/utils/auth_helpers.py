"""Authentication and multi-role session management helpers.

Provides session scoping per role so that users can have multiple dashboard roles
open in separate tabs (e.g., SuperAdmin in Tab 1, Student in Tab 2, Staff in Tab 3)
without session collisions or page refresh redirects.
"""

import uuid
from typing import Optional
from flask import session, request


def get_target_role_for_path(path: str) -> Optional[str]:
    """Determine the intended user role based on the requested endpoint path."""
    if not path:
        return None
    p = path.lower()
    if p.startswith("/superadmin"):
        return "super_admin"
    if p.startswith("/student"):
        return "student"
    if p.startswith("/accounts"):
        return "accounts"
    if p.startswith("/hostel"):
        return "hostel"
    if p.startswith("/mess"):
        return "mess"
    if p.startswith("/transport"):
        return "transport"
    if p.startswith("/scholarship"):
        return "scholarship"
    if p.startswith("/hod"):
        return "hod"
    if p.startswith("/examination"):
        return "examination"
    if p.startswith("/platform"):
        return "super_admin"
    if p.startswith("/university/dashboard") or p.startswith("/university/api/branding"):
        return "super_admin"
    if p.startswith("/api/student"):
        return "student"
    if p.startswith("/api/superadmin") or p.startswith("/api/university"):
        return "super_admin"
    return None



def save_role_session(user, tenant=None, session_obj=None) -> None:
    """Store role-isolated session state when a user logs in.
    
    Prevents cross-role overwrites when switching or operating multiple portals.
    """
    if not user:
        return

    if session_obj is None:
        session_obj = session

    role = getattr(user, "role", None)
    if not role:
        return

    # Auto-heal missing university_id for super_admin matching official_email or primary university
    if not user.university_id and role == "super_admin":
        try:
            from models.university import UniversityTenant
            from models import db
            matched_tenant = None
            if getattr(user, "email", None):
                matched_tenant = UniversityTenant.query.filter_by(official_email=user.email.strip().lower()).first()
            if not matched_tenant and tenant:
                matched_tenant = tenant
            if not matched_tenant:
                from utils.tenant_helpers import get_primary_or_default_university
                matched_tenant = get_primary_or_default_university()
            if matched_tenant:
                user.university_id = matched_tenant.id
                db.session.commit()
                if not tenant:
                    tenant = matched_tenant
        except Exception:
            pass

    # If tenant is explicitly provided and user has no university_id, bind permanently to DB
    if tenant and not user.university_id:
        try:
            from models import db
            user.university_id = tenant.id
            db.session.commit()
        except Exception:
            pass

    # Fetch tenant if not provided
    if not tenant and user.university_id:
        try:
            from models.university import UniversityTenant
            from models import db
            u_id = uuid.UUID(str(user.university_id)) if isinstance(user.university_id, str) else user.university_id
            tenant = db.session.get(UniversityTenant, u_id)
        except Exception:
            tenant = None


    # 1. Update role_sessions map
    role_sessions = dict(session_obj.get("role_sessions", {}))
    role_sessions[role] = str(user.id)
    session_obj["role_sessions"] = role_sessions

    # 2. Update role-specific tenant data
    role_univs = dict(session_obj.get("role_universities", {}))
    role_slugs = dict(session_obj.get("role_tenant_slugs", {}))
    role_logos = dict(session_obj.get("role_tenant_logos", {}))
    role_names = dict(session_obj.get("role_tenant_names", {}))

    if tenant:
        role_univs[role] = str(tenant.id)
        role_slugs[role] = tenant.slug
        role_names[role] = tenant.name
        if tenant.logo_url:
            role_logos[role] = tenant.logo_url
            session_obj["university_logo"] = tenant.logo_url

        session_obj["university_id"] = str(tenant.id)
        session_obj["university_slug"] = tenant.slug
        session_obj["university_name"] = tenant.name
        session_obj["portal_slug"] = tenant.slug
    elif user.university_id:
        role_univs[role] = str(user.university_id)
        session_obj["university_id"] = str(user.university_id)

    session_obj["role_universities"] = role_univs
    session_obj["role_tenant_slugs"] = role_slugs
    session_obj["role_tenant_logos"] = role_logos
    session_obj["role_tenant_names"] = role_names

    # 3. Active session state for this role
    session_obj["_user_id"] = str(user.id)
    session_obj["user_role"] = role
    session_obj.modified = True


def activate_role_for_request(target_role: str) -> bool:
    """Activate role-specific session variables for the current request context."""
    if not target_role:
        return False

    role_sessions = session.get("role_sessions", {})
    if target_role not in role_sessions:
        return False

    target_uid = role_sessions[target_role]
    session["_user_id"] = str(target_uid)
    session["user_role"] = target_role
    session["_fresh"] = True

    role_univs = session.get("role_universities", {})
    if target_role in role_univs:
        session["university_id"] = role_univs[target_role]

    role_slugs = session.get("role_tenant_slugs", {})
    if target_role in role_slugs:
        session["university_slug"] = role_slugs[target_role]
        session["portal_slug"] = role_slugs[target_role]

    role_logos = session.get("role_tenant_logos", {})
    if target_role in role_logos:
        session["university_logo"] = role_logos[target_role]

    role_names = session.get("role_tenant_names", {})
    if target_role in role_names:
        session["university_name"] = role_names[target_role]

    # Explicitly populate Flask-Login user on request global (g) to avoid stale user caching
    from flask import g
    from models import db
    from models.user import User
    try:
        uid_obj = uuid.UUID(str(target_uid)) if not isinstance(target_uid, uuid.UUID) else target_uid
        target_user = db.session.get(User, uid_obj)
        if target_user:
            if not target_user.university_id and target_role == "super_admin" and getattr(target_user, "email", None):
                from models.university import UniversityTenant
                matched_tenant = UniversityTenant.query.filter_by(official_email=target_user.email.strip().lower()).first()
                if matched_tenant:
                    target_user.university_id = matched_tenant.id
                    try:
                        db.session.commit()
                    except Exception:
                        pass
            g._login_user = target_user
            g.current_user = target_user
    except Exception:
        pass

    session.modified = True
    return True



def remove_role_session(role: Optional[str] = None) -> None:
    """Safely log out of a specific role without terminating other active roles in other tabs."""
    role_sessions = dict(session.get("role_sessions", {}))
    role_univs = dict(session.get("role_universities", {}))
    role_slugs = dict(session.get("role_tenant_slugs", {}))
    role_logos = dict(session.get("role_tenant_logos", {}))
    role_names = dict(session.get("role_tenant_names", {}))

    if not role:
        role = session.get("user_role")

    if role and role in role_sessions:
        role_sessions.pop(role, None)
        role_univs.pop(role, None)
        role_slugs.pop(role, None)
        role_logos.pop(role, None)
        role_names.pop(role, None)

    session["role_sessions"] = role_sessions
    session["role_universities"] = role_univs
    session["role_tenant_slugs"] = role_slugs
    session["role_tenant_logos"] = role_logos
    session["role_tenant_names"] = role_names

    # If other roles remain active, switch active session to one of them
    if role_sessions:
        remaining_role, remaining_uid = next(iter(role_sessions.items()))
        activate_role_for_request(remaining_role)
    else:
        # Full clear
        from flask_login import logout_user
        try:
            logout_user()
        except Exception:
            pass
        session.pop("_user_id", None)
        session.pop("user_role", None)
        session.pop("university_id", None)
        session.pop("university_slug", None)
        session.pop("portal_slug", None)
        session.pop("university_name", None)
        session.pop("university_logo", None)

    session.modified = True
