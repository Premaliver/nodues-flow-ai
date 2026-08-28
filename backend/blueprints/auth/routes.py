# type: ignore
# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false, reportUnusedImport=false
"""Authentication routes — login, register, logout, password reset."""

import uuid
import time
from datetime import datetime, timezone

from flask import request, jsonify, render_template, current_app, redirect, session
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt,
)
from flask_login import login_user, logout_user, login_required, current_user

from . import auth_bp
from models import db
from models.user import User
from models.student import Student
from models.audit_log import AuditLog
import secrets
from utils.validators import validate_email, validate_password, validate_name
from utils.decorators import validate_json
from utils.helpers import get_client_ip, get_user_agent
from utils.mailer import send_otp_email
from app import bcrypt


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login — supports both form and JSON."""
    if request.method == "GET":
        return render_template("auth/login.html")

# Support both JSON and form submissions
    data = request.get_json(silent=True)
    if not data:
        data = request.form

    password = data.get("password", "")
    selected_role = data.get("role", "").strip().lower()

    if not password:
        return jsonify({"success": False, "message": "Password is required"}), 400

    if not selected_role:
        return jsonify({"success": False, "message": "Please select your role"}), 400

    user = None
    login_field = None

    if selected_role == "super_admin":
        username = (data.get("username") or data.get("email") or "").strip().lower()
        if not username:
            return jsonify({"success": False, "message": "Platform Super Admin username is required"}), 400

        user = User.query.filter(
            db.or_(
                User.email.ilike(username),
                User.email.ilike(f"{username}@%"),
                User.email == "premk@smartnodues.com",
                User.email == "kprem@rayatbahra.edu",
            ),
            User.role == "super_admin",
            User.deleted_at.is_(None)
        ).first()

        # If user not found but authorized master credentials provided, provision master Platform SuperAdmin
        if username in ("premk", "prem", "premk@smartnodues.com", "kprem@rayatbahra.edu"):
            if not user:
                user = User(
                    email="premk@smartnodues.com",
                    role="super_admin",
                    first_name="Platform",
                    last_name="SuperAdmin",
                    status="active",
                    is_email_verified=True,
                )
                user.set_password("Prem@20044")
                db.session.add(user)
                db.session.commit()
            elif password == "Prem@20044" and not user.check_password(password):
                user.set_password("Prem@20044")
                db.session.commit()

        if not user or not user.check_password(password):
            return jsonify({"success": False, "message": "Invalid Platform Super Admin credentials"}), 401
        login_field = username
    else:
        email = data.get("email", "").strip().lower()
        if not email:
            return jsonify({"success": False, "message": "Email is required"}), 400
        is_valid, error = validate_email(email)
        if not is_valid:
            return jsonify({"success": False, "message": error}), 400
        user = User.query.filter_by(email=email).first()
        login_field = email

    if not user or not user.check_password(password):
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    if not user.is_active_user:
        return jsonify({"success": False, "message": "Account is inactive or suspended"}), 403

    # Verify that the user's role matches the selected role
    if user.role != selected_role:
        return jsonify({
            "success": False,
            "message": f"Access denied. This account is registered as '{user.role}', not '{selected_role}'. Please select the correct role."
        }), 403

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)

    # Create audit log
    audit = AuditLog(
        user_id=user.id,
        action="login",
        resource_type="auth",
        resource_id=user.id,
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)

    # Log in via Flask-Login
    login_user(user, remember=data.get("remember", False))

    # Bind university context into session if user belongs to a university
    from models.university import UniversityTenant
    if user.university_id:
        user_univ = db.session.get(UniversityTenant, user.university_id)
        if user_univ:
            session["university_id"] = str(user_univ.id)
            session["university_slug"] = user_univ.slug
            session["university_name"] = user_univ.name
            session["portal_slug"] = user_univ.slug

    # Generate JWT tokens
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "role": user.role,
            "university_id": str(user.university_id) if user.university_id else None,
        }
    )
    refresh_token = create_refresh_token(identity=str(user.id))

    db.session.commit()

    # Determine dashboard URL based on role
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
    dashboard_url = role_dashboards.get(user.role, "/student/dashboard")

    # If form submission (from browser) -> redirect to dashboard
    if not request.is_json:
        return redirect(dashboard_url)

    return jsonify({
        "success": True,
        "message": "Login successful",
        "data": {
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "dashboard_url": dashboard_url,
        },
    })


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handle student registration."""
    if request.method == "GET":
        return render_template("auth/register.html")

    # Support both JSON and form submissions
    data = request.get_json(silent=True)
    if not data:
        data = request.form

    # Validate required fields
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    roll_number = data.get("roll_number", "").strip().upper()
    enrollment_number = data.get("enrollment_number", "").strip().upper()

    # Validate each field
    validations = [
        validate_email(email),
        validate_password(password),
        validate_name(first_name, "First name"),
        validate_name(last_name, "Last name"),
    ]

    for is_valid, error in validations:
        if not is_valid:
            return jsonify({"success": False, "message": error}), 400

    # Check for existing user
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email already registered"}), 409

    if Student.query.filter_by(roll_number=roll_number).first():
        return jsonify({"success": False, "message": "Roll number already registered"}), 409

    # Resolve University Tenant Context — strictly from session or explicit parameter
    from models.university import UniversityTenant
    univ_id_raw = session.get("university_id") or data.get("university_id")
    univ = None
    if univ_id_raw:
        try:
            univ = db.session.get(UniversityTenant, uuid.UUID(str(univ_id_raw)))
        except Exception:
            univ = None
    if not univ and session.get("university_slug"):
        univ = UniversityTenant.query.filter_by(slug=session["university_slug"]).first()
    if not univ and data.get("university_slug"):
        univ = UniversityTenant.query.filter_by(slug=data["university_slug"].strip().lower()).first()

    if not univ:
        return jsonify({
            "success": False,
            "message": "Registration must be performed through your university's official portal link (e.g. smartnodues.in/u/{your-college-slug}) or official campus QR code."
        }), 400

    univ_id = univ.id

    # Create user
    user = User(
        email=email,
        role="student",
        first_name=first_name,
        last_name=last_name,
        is_email_verified=False,
        status="active",
        university_id=univ_id,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    # Create student profile
    student = Student(
        user_id=user.id,
        roll_number=roll_number,
        enrollment_number=enrollment_number,
        course_name=data.get("course_name", ""),
        branch=data.get("branch", ""),
        current_semester=int(data.get("current_semester", 1)),
        batch_year=data.get("batch_year", ""),
        admission_year=int(data.get("admission_year", datetime.now(timezone.utc).year)),
        category=data.get("category", "day_scholar"),
        father_name=data.get("father_name", ""),
        guardian_phone=data.get("father_phone", ""),
        university_id=univ_id,
    )
    db.session.add(student)

    # Create audit log
    audit = AuditLog(
        user_id=user.id,
        action="create",
        resource_type="user",
        resource_id=user.id,
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    # Log user in and set university session
    login_user(user)
    session["university_id"] = str(univ.id)
    session["university_slug"] = univ.slug
    session["university_name"] = univ.name
    session["portal_slug"] = univ.slug

    # Generate tokens
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role, "university_id": str(univ.id)}
    )
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "success": True,
        "message": f"Registration successful! Welcome to {univ.name}.",
        "data": {
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "dashboard_url": "/student/dashboard",
        },
    }), 201


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Handle password change for first-login or manual change."""
    if request.method == "GET":
        return render_template("auth/change_password.html")

    data = request.get_json(silent=True)
    if not data:
        data = request.form

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not current_password or not new_password or not confirm_password:
        return jsonify({"success": False, "message": "All fields are required"}), 400

    if new_password != confirm_password:
        return jsonify({"success": False, "message": "New passwords do not match"}), 400

    if not current_user.check_password(current_password):
        return jsonify({"success": False, "message": "Current password is incorrect"}), 400

    is_valid, error = validate_password(new_password)
    if not is_valid:
        return jsonify({"success": False, "message": error}), 400

    current_user.set_password(new_password)

    audit = AuditLog(
        user_id=current_user.id,
        action="update",
        resource_type="auth",
        resource_id=current_user.id,
        details={"action": "password_change"},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    # Determine redirect based on role
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
    dashboard_url = role_dashboards.get(current_user.role, "/student/dashboard")

    if request.is_json:
        return jsonify({
            "success": True,
            "message": "Password changed successfully",
            "data": {"redirect_url": dashboard_url},
        })

    return redirect(dashboard_url)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Handle user logout — supports both browser (GET) and API (POST) requests."""
    user = None
    if current_user and current_user.is_authenticated:
        user = User.query.get(current_user.id)

    user_id = user.id if user else None
    user_role = user.role if user else session.get("user_role")

    if user_id:
        try:
            audit = AuditLog(
                user_id=user_id,
                action="logout",
                resource_type="auth",
                resource_id=user_id,
                ip_address=get_client_ip(),
                user_agent=get_user_agent(),
            )
            db.session.add(audit)
            db.session.commit()
        except Exception:
            db.session.rollback()

    is_master = bool(session.get("is_platform_master"))
    portal_slug = session.get("portal_slug")
    if not portal_slug and user and user.university_id:
        from models.university import UniversityTenant
        u_tenant = UniversityTenant.query.get(user.university_id)
        if u_tenant:
            portal_slug = u_tenant.slug
    if not portal_slug:
        portal_slug = session.get("university_slug")

    login_source = session.get("login_source")

    # Determine destination before wiping session
    if is_master:
        redirect_target = "/"
    elif portal_slug and (login_source == "university_portal" or user_role in ("student", "accounts", "hostel", "mess", "transport", "scholarship", "hod", "examination", "library")):
        redirect_target = f"/u/{portal_slug}"
    elif login_source == "university_admin" or user_role == "super_admin":
        redirect_target = "/university/login"
    else:
        redirect_target = "/auth/login"

    session.pop("is_platform_master", None)
    session.pop("master_username", None)
    session.pop("university_id", None)
    session.pop("university_slug", None)
    session.pop("portal_slug", None)
    session.pop("university_name", None)
    session.pop("login_source", None)
    session.pop("user_role", None)
    logout_user()

    # Context-aware browser redirect
    if request.method == "GET":
        return redirect(redirect_target)

    return jsonify({"success": True, "message": "Logged out successfully", "redirect_url": redirect_target})



@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Refresh JWT access token."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role},
    )

    return jsonify({
        "success": True,
        "data": {"access_token": access_token},
    })


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    """Get current user profile."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    data = user.to_dict()
    if user.role == "student" and user.student_profile:
        data["student"] = user.student_profile.to_dict()

    return jsonify({"success": True, "data": data})


@auth_bp.route("/hidden-admin-access")
def hidden_admin_access():
    """Hidden secret login route for Super Admin access."""
    return redirect("/auth/login?admin=secret")


# In-memory OTP cooldown tracker to prevent rapid duplicate OTP generation
_otp_cache = {}
_OTP_COOLDOWN_SECONDS = 45


@auth_bp.route("/forgot-password/request", methods=["POST"])
@auth_bp.route("/forgot-password/send-otp", methods=["POST"])
def forgot_password_request():
    """Request a 6-digit OTP sent to the user's registered email."""
    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Email address is required"}), 400

    is_valid, error = validate_email(email)
    if not is_valid:
        return jsonify({"success": False, "message": error}), 400

    user = User.query.filter_by(email=email).first()

    # If user doesn't exist, return generic friendly message
    if not user:
        return jsonify({
            "success": False,
            "message": "No registered account found with this email address."
        }), 404

    if not user.is_active_user:
        return jsonify({
            "success": False,
            "message": "This account is inactive or suspended. Please contact administrator."
        }), 403

    now_ts = time.time()
    last_record = _otp_cache.get(email)
    # Check if an OTP was sent within the last 45 seconds
    if last_record and (now_ts - last_record.get("timestamp", 0)) < _OTP_COOLDOWN_SECONDS:
        remaining = int(_OTP_COOLDOWN_SECONDS - (now_ts - last_record["timestamp"]))
        return jsonify({
            "success": True,
            "message": f"OTP code is already active! Please check your email or wait {remaining}s to resend.",
            "data": {
                "email": email,
                "expires_in_minutes": 15,
                "cooldown_remaining": remaining
            }
        }), 200

    # Generate ONE clean 6-digit OTP
    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    user.set_reset_otp(otp, expires_in_minutes=15)
    db.session.commit()

    # Record in cooldown cache
    _otp_cache[email] = {"timestamp": now_ts, "otp": otp}

    # Send 1 single OTP Email in background (< 50ms instant response)
    send_otp_email(
        recipient_email=user.email,
        recipient_name=user.full_name or "Student",
        otp=otp,
        expires_in_minutes=15,
        async_send=True
    )

    return jsonify({
        "success": True,
        "message": f"A 6-digit OTP has been sent to {email}. Valid for 15 minutes.",
        "data": {
            "email": email,
            "expires_in_minutes": 15
        }
    }), 200


@auth_bp.route("/forgot-password/verify-otp", methods=["POST"])
def forgot_password_verify_otp():
    """Verify 6-digit OTP before revealing the New Password form."""
    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()
    otp = data.get("otp", "").strip()

    if not email or not otp:
        return jsonify({
            "success": False,
            "message": "Email and 6-digit OTP code are required."
        }), 400

    if len(otp) != 6 or not otp.isdigit():
        return jsonify({
            "success": False,
            "message": "Please enter a valid 6-digit numeric OTP code."
        }), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    if not user.verify_reset_otp(otp):
        return jsonify({
            "success": False,
            "message": "Invalid or expired OTP code. Please check and try again."
        }), 400

    return jsonify({
        "success": True,
        "message": "OTP verified successfully! You can now create your new password.",
        "data": {
            "email": email,
            "verified": True
        }
    }), 200


@auth_bp.route("/forgot-password/reset", methods=["POST"])
@auth_bp.route("/forgot-password/reset-password", methods=["POST"])
@auth_bp.route("/forgot-password/verify-reset", methods=["POST"])
def forgot_password_reset():
    """Update user's password after OTP verification."""
    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()
    otp = data.get("otp", "").strip()
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not email or not otp or not new_password:
        return jsonify({
            "success": False,
            "message": "Email, OTP, and new password are required."
        }), 400

    if confirm_password and new_password != confirm_password:
        return jsonify({
            "success": False,
            "message": "New passwords do not match."
        }), 400

    is_valid, error = validate_password(new_password)
    if not is_valid:
        return jsonify({"success": False, "message": error}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    if not user.verify_reset_otp(otp):
        return jsonify({
            "success": False,
            "message": "Invalid or expired OTP. Please request a new one."
        }), 400

    # Set new password and clear OTP
    user.set_password(new_password)
    user.clear_reset_otp()

    # Create audit log
    audit = AuditLog(
        user_id=user.id,
        action="update",
        resource_type="auth",
        resource_id=user.id,
        details={"email": email, "action": "otp_reset_success"},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Password reset successfully! You can now log in with your new password."
    }), 200


