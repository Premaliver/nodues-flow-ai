"""
License verification decorators for Flask routes.
"""

from functools import wraps
from flask import jsonify
from .license_manager import LicenseManager, LicenseStatus


def require_active_license(allow_grace: bool = True):
    """
    Decorator that verifies the application has an active license or is in grace period.
    Suspended or expired licenses cannot perform state-modifying actions.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            status, _, message = LicenseManager.load_license()
            allowed_statuses = [LicenseStatus.ACTIVE, LicenseStatus.TRIAL]
            if allow_grace:
                allowed_statuses.append(LicenseStatus.GRACE_PERIOD)

            if status not in allowed_statuses:
                return jsonify({
                    "success": False,
                    "error_code": "LICENSE_SUSPENDED",
                    "message": f"Operation blocked: {message}. University portal is currently in read-only mode. Please contact administrator to renew subscription.",
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_feature(feature_key: str):
    """
    Decorator that gates premium enterprise features based on plan entitlements.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not LicenseManager.has_feature(feature_key):
                return jsonify({
                    "success": False,
                    "error_code": "FEATURE_NOT_ENTITLED",
                    "message": f"Feature '{feature_key}' is not enabled in your current university subscription plan.",
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
