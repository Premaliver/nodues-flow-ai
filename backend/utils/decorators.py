"""Decorators for role-based access control and validation."""

from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
import jwt as pyjwt

from models.user import User


def role_required(*roles: str):
    """Decorator that restricts access to specified roles.
    Works with both JWT and session-based auth.
    Safely redirects browser navigation when unauthorized to prevent URL tampering.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            is_browser_request = (
                not request.is_json
                and not request.path.startswith("/api/")
                and "/api/" not in request.path
            )

            # Try JWT first (for API calls)
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token_val = auth_header[7:].strip()
                if token_val and token_val not in ("null", "undefined", ""):
                    try:
                        from models import db
                        verify_jwt_in_request()
                        user_id = get_jwt_identity()
                        user = None
                        if user_id:
                            try:
                                import uuid as _uuid
                                uid_obj = _uuid.UUID(str(user_id)) if not isinstance(user_id, _uuid.UUID) else user_id
                                user = db.session.get(User, uid_obj) or User.query.filter_by(id=uid_obj).first()
                            except Exception:
                                user = User.query.get(user_id)
                        if user and user.role in roles:
                            request.current_user = user
                            return f(*args, **kwargs)
                        elif user:
                            return jsonify({
                                "success": False,
                                "message": f"Access denied. Required roles: {', '.join(roles)}",
                            }), 403
                    except Exception as e:
                        current_app.logger.warning(f"JWT verify error in role_required: {e}")

            # Try session auth (Flask-Login)
            from flask_login import current_user
            from flask import session, redirect
            if current_user and current_user.is_authenticated:
                active_user = current_user
                try:
                    role_val = active_user.role
                except Exception:
                    uid = session.get("_user_id") or active_user.__dict__.get("id")
                    if uid:
                        import uuid
                        uid_obj = uuid.UUID(str(uid)) if not isinstance(uid, uuid.UUID) else uid
                        from models import db
                        active_user = db.session.get(User, uid_obj)
                    role_val = active_user.role if active_user else None

                if not active_user or role_val not in roles:
                    if is_browser_request:
                        # Redirect user safely to their authorized dashboard
                        role_dashboards = {
                            "student": "/student/dashboard",
                            "accounts": "/accounts/dashboard",
                            "hostel": "/hostel/dashboard",
                            "mess": "/mess/dashboard",
                            "transport": "/transport/dashboard",
                            "scholarship": "/scholarship/dashboard",
                            "hod": "/hod/dashboard",
                            "examination": "/examination/dashboard",
                            "super_admin": "/superadmin/dashboard",
                        }
                        target = role_dashboards.get(role_val, "/auth/login")
                        return redirect(target)
                    return jsonify({
                        "success": False,
                        "message": f"Access denied. Required roles: {', '.join(roles)}",
                    }), 403
                request.current_user = active_user
                return f(*args, **kwargs)

            # Unauthenticated access attempt
            if is_browser_request:
                portal_slug = session.get("portal_slug") or session.get("university_slug")
                if portal_slug:
                    return redirect(f"/u/{portal_slug}")
                return redirect("/auth/login")

            return jsonify({"success": False, "message": "Authentication required"}), 401

        return decorated_function

    return decorator


def student_only(f):
    """Decorator for student-only endpoints."""
    return role_required("student")(f)


def staff_only(f):
    """Decorator for staff-only endpoints (all departments + admin)."""
    return role_required(
        "accounts", "hostel", "mess", "transport",
        "scholarship", "hod", "examination", "super_admin",
    )(f)


def admin_only(f):
    """Decorator for super admin only."""
    return role_required("super_admin")(f)


def department_access(department_role: str):
    """Decorator that restricts access to a specific department role
    or super_admin. Prevents browser URL tampering and cross-role access.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_login import current_user
            from flask import session, redirect

            is_browser_request = (
                not request.is_json
                and not request.path.startswith("/api/")
                and "/api/" not in request.path
            )

            # Try JWT first (for API calls)
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token_val = auth_header[7:].strip()
                if token_val and token_val not in ("null", "undefined", ""):
                    try:
                        verify_jwt_in_request()
                        user_id = get_jwt_identity()
                        user = None
                        if user_id:
                            try:
                                import uuid as _uuid
                                user = User.query.get(_uuid.UUID(str(user_id)))
                            except Exception:
                                user = User.query.get(user_id)
                        if user and user.role in (department_role, "super_admin"):
                            request.current_user = user
                            return f(*args, **kwargs)
                        elif user:
                            return jsonify({
                                "success": False,
                                "message": f"Access denied. {department_role} access required",
                            }), 403
                    except Exception as e:
                        current_app.logger.debug(f"JWT verify in department_access: {e}")

            if current_user and current_user.is_authenticated:
                if current_user.role in (department_role, "super_admin"):
                    return f(*args, **kwargs)
                if is_browser_request:
                    role_dashboards = {
                        "student": "/student/dashboard",
                        "accounts": "/accounts/dashboard",
                        "hostel": "/hostel/dashboard",
                        "mess": "/mess/dashboard",
                        "transport": "/transport/dashboard",
                        "scholarship": "/scholarship/dashboard",
                        "hod": "/hod/dashboard",
                        "examination": "/examination/dashboard",
                        "super_admin": "/superadmin/dashboard",
                    }
                    return redirect(role_dashboards.get(current_user.role, "/auth/login"))
                return jsonify({
                    "success": False,
                    "message": f"Access denied. {department_role} access required",
                }), 403

            if is_browser_request:
                portal_slug = session.get("portal_slug") or session.get("university_slug")
                if portal_slug:
                    return redirect(f"/u/{portal_slug}")
                return redirect("/auth/login")

            return jsonify({"success": False, "message": "Authentication required"}), 401

        return decorated_function

    return decorator


def validate_json(*required_fields: str):
    """Decorator that validates required JSON fields in request body.

    Usage:
        @validate_json('email', 'password')
        def login():
            ...
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json(silent=True)
            if not data:
                return jsonify({"success": False, "message": "Request body must be JSON"}), 400

            missing = [field for field in required_fields if field not in data]
            if missing:
                return jsonify({
                    "success": False,
                    "message": f"Missing required fields: {', '.join(missing)}",
                }), 400

            request.validated_data = data
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def rate_limit_for_role(role: str, limit: str = "100/hour"):
    """Get appropriate rate limit string based on role.

    Usage:
        @rate_limit_for_role('student', '30/hour')
    """
    # Higher limits for staff, lower for students
    limits = {
        "student": "30/hour",
        "super_admin": "200/hour",
        "accounts": "100/hour",
        "hostel": "100/hour",
        "mess": "100/hour",
        "transport": "100/hour",
        "scholarship": "100/hour",
        "hod": "100/hour",
        "examination": "100/hour",
    }
    return limits.get(role, limit)
