"""Decorators for role-based access control and validation."""

from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
import jwt as pyjwt

from models.user import User


def role_required(*roles: str):
    """Decorator that restricts access to specified roles.
    Works with both JWT and session-based auth.

    Usage:
        @role_required('accounts', 'super_admin')
        def dashboard():
            ...
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Try JWT first
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token_val = auth_header[7:].strip()
                if token_val and token_val not in ("null", "undefined", ""):
                    try:
                        verify_jwt_in_request()
                        user_id = get_jwt_identity()
                        user = User.query.get(user_id)
                        if user and user.role in roles:
                            request.current_user = user
                            return f(*args, **kwargs)
                    except Exception:
                        pass  # Fall through to session auth

            # Try session auth
            from flask_login import current_user
            from flask import session
            if current_user and current_user.is_authenticated:
                if current_user.role not in roles:
                    return jsonify({
                        "success": False,
                        "message": f"Access denied. Required roles: {', '.join(roles)}",
                    }), 403
                request.current_user = current_user
                return f(*args, **kwargs)

            # Try University tenant session for super_admin roles
            if "super_admin" in roles and session.get("university_id"):
                sa = User.query.filter_by(role="super_admin").first()
                if sa:
                    request.current_user = sa
                return f(*args, **kwargs)

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
    or super_admin.

    Usage:
        @department_access('accounts')
        def accounts_dashboard():
            ...
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_login import current_user

            if current_user.is_authenticated:
                if current_user.role in (department_role, "super_admin"):
                    return f(*args, **kwargs)
                return jsonify({
                    "success": False,
                    "message": f"Access denied. {department_role} access required",
                }), 403
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
