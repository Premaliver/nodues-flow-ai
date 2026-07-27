"""Authentication routes — login, register, logout, password reset."""

import uuid
from datetime import datetime, timezone

from flask import request, jsonify, render_template, current_app, redirect
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
from utils.validators import validate_email, validate_password, validate_name
from utils.decorators import validate_json
from utils.helpers import get_client_ip, get_user_agent
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

    # Super Admin logs in via username (stored in email field), others via email
    user = None
    login_field = ""
    if selected_role == "super_admin":
        username = data.get("username", "").strip()
        if not username:
            return jsonify({"success": False, "message": "Username is required for Super Admin"}), 400

        # DEBUG: dump all super admins in DB
        all_sa = User.query.filter_by(role="super_admin").all()
        print(f"[DEBUG] Super admin login: username='{username}', total_sa_in_db={len(all_sa)}")
        for sa in all_sa:
            prefix = sa.email.split('@')[0].lower() if '@' in sa.email else sa.email.lower()
            print(f"[DEBUG]   SA in DB: email='{sa.email}', prefix='{prefix}'")

        # Try full email match
        user = User.query.filter_by(email=username, role="super_admin").first()
        # Try prefix match in Python (more reliable than SQL ILIKE)
        if not user:
            for sa in all_sa:
                if '@' in sa.email:
                    sa_prefix = sa.email.split('@')[0].lower()
                    if sa_prefix == username.lower():
                        user = sa
                        break
                elif sa.email.lower() == username.lower():
                    user = sa
                    break
        print(f"[DEBUG]   found_user={'YES' if user else 'NO'}")
        if user:
            print(f"[DEBUG]   matched: email='{user.email}', pw_check={user.check_password(data.get('password', ''))}")
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

    # Generate JWT tokens
    access_token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
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

    # Create user
    user = User(
        email=email,
        role="student",
        first_name=first_name,
        last_name=last_name,
        is_email_verified=False,
        status="active",
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

    # Generate tokens
    access_token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "success": True,
        "message": "Registration successful",
        "data": {
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
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
@login_required
def logout():
    """Handle user logout — supports both browser (GET) and API (POST) requests."""
    user_id = current_user.id

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

    logout_user()

    # For browser GET requests, redirect to login page
    if request.method == "GET":
        return redirect("/auth/login")

    return jsonify({"success": True, "message": "Logged out successfully"})


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

