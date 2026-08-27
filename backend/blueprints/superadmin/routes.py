# type: ignore
# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false, reportUnusedImport=false
"""Super Admin routes — system management and analytics."""

import string as str_mod
import random
from datetime import datetime, timezone, timedelta

from flask import request, jsonify, render_template, current_app, session, redirect, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required, current_user

from . import superadmin_bp
from models import db
from models.user import User
from models.student import Student
from models.department import Department, DepartmentStaff
from models.semester import Semester
from models.application import NoDuesApplication, ApplicationDepartment
from models.document import Document
from models.notification import Notification
from models.audit_log import AuditLog
from models.admit_card import AdmitCard
from models.system_setting import SystemSetting
from models.feedback import Feedback
from utils.decorators import admin_only, validate_json
from utils.helpers import paginate_query, get_client_ip, get_user_agent
from app import bcrypt


# ──────────────────────────────────────
# Helper: Generate random temp password
# ──────────────────────────────────────
def _generate_temp_password(length: int = 10) -> str:
    chars = str_mod.ascii_letters + str_mod.digits + "!@#$%&"
    return "".join(random.choice(chars) for _ in range(length))


def _get_active_tenant_id():
    import uuid
    if session.get("university_id"):
        try:
            return uuid.UUID(str(session["university_id"]))
        except Exception:
            pass
    if current_user and current_user.is_authenticated and current_user.university_id:
        return current_user.university_id
    if hasattr(request, "current_user") and request.current_user and request.current_user.university_id:
        return request.current_user.university_id
    return None


def _get_admin_audit_user_id(user_obj=None):
    if hasattr(request, "current_user") and request.current_user:
        return request.current_user.id
    if current_user and current_user.is_authenticated:
        return current_user.id
    jwt_uid = get_jwt_identity()
    if jwt_uid:
        try:
            return uuid.UUID(str(jwt_uid))
        except Exception:
            pass
    sa = User.query.filter_by(role="super_admin").first()
    return sa.id if sa else (user_obj.id if user_obj else None)


# ──────────────────────────────────────
# PAGE: Dashboard
# ──────────────────────────────────────
@superadmin_bp.route("/dashboard")
def dashboard():
    from flask_jwt_extended import create_access_token
    from flask_login import login_user

    try:
        db.session.rollback()
    except Exception:
        pass

    # Must be logged in via University Portal or active super_admin session
    if not session.get("university_id") and not (current_user and current_user.is_authenticated and current_user.role == "super_admin"):
        return redirect("/university/login")

    try:
        sa_user = current_user if (current_user and current_user.is_authenticated and current_user.role == "super_admin") else User.query.filter_by(role="super_admin").first()
        if sa_user and not (current_user and current_user.is_authenticated):
            login_user(sa_user)

        token = create_access_token(identity=str(sa_user.id), additional_claims={"role": "super_admin"}) if sa_user else ""
    except Exception as e:
        db.session.rollback()
        sa_user = None
        token = ""

    from models.university import UniversityTenant
    import uuid

    univ = None
    univ_id = session.get("university_id")
    if univ_id:
        try:
            univ = UniversityTenant.query.get(uuid.UUID(str(univ_id)))
        except Exception:
            univ = None

    if not univ:
        # Fallback to university slug in session or first tenant
        univ_slug = session.get("university_slug")
        if univ_slug:
            univ = UniversityTenant.query.filter_by(slug=univ_slug).first()
        if not univ:
            univ = UniversityTenant.query.first()

    univ_name = univ.name if univ else session.get("university_name", "University Command Center")
    univ_slug = univ.slug if univ else session.get("university_slug", "campus")

    return render_template(
        "superadmin/dashboard.html",
        access_token=token,
        university_name=univ_name,
        university_slug=univ_slug,
        university=univ,
    )


# ──────────────────────────────────────
# API: Dashboard Data (overview stats)
# ──────────────────────────────────────
@superadmin_bp.route("/api/dashboard")
@admin_only
def dashboard_data():
    """Get comprehensive system analytics for the dashboard overview."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tenant_id = _get_active_tenant_id()

    if tenant_id:
        total_users = User.query.filter(User.university_id == tenant_id, User.deleted_at.is_(None)).count()
        active_users = User.query.filter_by(university_id=tenant_id, status="active").filter(User.deleted_at.is_(None)).count()
        total_students = Student.query.filter_by(university_id=tenant_id).count()
        total_staff = User.query.filter(
            User.university_id == tenant_id,
            User.role != "student", User.role != "super_admin",
            User.deleted_at.is_(None),
        ).count()

        total_applications = NoDuesApplication.query.filter(NoDuesApplication.university_id == tenant_id, NoDuesApplication.deleted_at.is_(None)).count()
        pending_apps = NoDuesApplication.query.filter(
            NoDuesApplication.university_id == tenant_id,
            NoDuesApplication.status.in_(["draft", "submitted", "in_review"]),
            NoDuesApplication.deleted_at.is_(None),
        ).count()
        approved_apps = NoDuesApplication.query.filter_by(university_id=tenant_id, status="approved").filter(
            NoDuesApplication.deleted_at.is_(None),
        ).count()
        rejected_apps = NoDuesApplication.query.filter_by(university_id=tenant_id, status="rejected").filter(
            NoDuesApplication.deleted_at.is_(None),
        ).count()

        today_apps = NoDuesApplication.query.filter(
            NoDuesApplication.university_id == tenant_id,
            NoDuesApplication.created_at >= today_start,
            NoDuesApplication.deleted_at.is_(None),
        ).count()
        today_admit_cards = AdmitCard.query.join(NoDuesApplication).filter(
            NoDuesApplication.university_id == tenant_id,
            AdmitCard.created_at >= today_start,
        ).count()

        departments = Department.query.filter_by(university_id=tenant_id, is_active=True).order_by(Department.display_order).all()
        if not departments:
            departments = Department.query.filter_by(is_active=True).order_by(Department.display_order).all()
    else:
        total_users = User.query.filter(User.deleted_at.is_(None)).count()
        active_users = User.query.filter_by(status="active").filter(User.deleted_at.is_(None)).count()
        total_students = Student.query.count()
        total_staff = User.query.filter(
            User.role != "student", User.role != "super_admin",
            User.deleted_at.is_(None),
        ).count()

        total_applications = NoDuesApplication.query.filter(NoDuesApplication.deleted_at.is_(None)).count()
        pending_apps = NoDuesApplication.query.filter(
            NoDuesApplication.status.in_(["draft", "submitted", "in_review"]),
            NoDuesApplication.deleted_at.is_(None),
        ).count()
        approved_apps = NoDuesApplication.query.filter_by(status="approved").filter(
            NoDuesApplication.deleted_at.is_(None),
        ).count()
        rejected_apps = NoDuesApplication.query.filter_by(status="rejected").filter(
            NoDuesApplication.deleted_at.is_(None),
        ).count()

        today_apps = NoDuesApplication.query.filter(
            NoDuesApplication.created_at >= today_start,
            NoDuesApplication.deleted_at.is_(None),
        ).count()
        today_admit_cards = AdmitCard.query.filter(
            AdmitCard.created_at >= today_start,
        ).count()

        departments = Department.query.filter_by(is_active=True).order_by(Department.display_order).all()
    dept_stats = []
    for dept in departments:
        pending = ApplicationDepartment.query.filter_by(
            department_id=dept.id, status="pending",
        ).count()
        dept_stats.append({
            "id": str(dept.id),
            "name": dept.name,
            "code": dept.code,
            "pending": pending,
        })

    recent_audits = (
        AuditLog.query
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )

    return jsonify({
        "success": True,
        "data": {
            "users": {
                "total": total_users,
                "active": active_users,
                "students": total_students,
                "staff": total_staff,
            },
            "applications": {
                "total": total_applications,
                "pending": pending_apps,
                "approved": approved_apps,
                "rejected": rejected_apps,
            },
            "today": {
                "new_applications": today_apps,
                "admit_cards_issued": today_admit_cards,
            },
            "department_queues": dept_stats,
            "recent_activity": [
                {
                    "id": str(log.id),
                    "user_id": str(log.user_id) if log.user_id else None,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "details": log.details,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in recent_audits
            ],
        },
    })


# ──────────────────────────────────────
# API: Manage Staff Users (CRUD)
# ──────────────────────────────────────
SUPERVISOR_ROLES = [
    "accounts", "hostel", "mess", "transport",
    "scholarship", "hod", "examination",
]


@superadmin_bp.route("/api/users/staff", methods=["GET"])
@admin_only
def list_staff():
    """List all staff users (non-student, non-admin) with pagination, scoped to current university tenant."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    role_filter = request.args.get("role")
    status_filter = request.args.get("status")
    search = request.args.get("search", "").strip().lower()

    query = User.query.filter(
        User.role.in_(SUPERVISOR_ROLES),
        User.deleted_at.is_(None),
    )
    # Scope to active tenant if present
    tenant_id = getattr(g, "university_id", None)
    if tenant_id:
        query = query.filter((User.university_id == tenant_id) | (User.university_id.is_(None)))

    if role_filter:
        query = query.filter_by(role=role_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(
            db.or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
            )
        )
    query = query.order_by(User.created_at.desc())

    result = paginate_query(query, page=page, per_page=per_page)
    # Add department info to each user
    for item in result["items"]:
        dept_staff = DepartmentStaff.query.filter_by(user_id=item["id"]).first()
        if dept_staff and dept_staff.department:
            item["department"] = dept_staff.department.to_dict()
            item["staff_designation"] = dept_staff.designation
            item["is_department_head"] = dept_staff.is_head
        else:
            dept = Department.query.filter_by(role=item["role"]).first()
            item["department"] = dept.to_dict() if dept else None
    return jsonify({"success": True, "data": result})


@superadmin_bp.route("/api/users/staff", methods=["POST"])
@admin_only
@validate_json("email", "first_name", "last_name", "role")
def create_staff():
    """Create a new staff user with auto-generated temp password."""
    data = request.validated_data
    email = data.get("email", "").strip().lower()
    role = data.get("role", "").strip().lower()

    if role not in SUPERVISOR_ROLES:
        return jsonify({"success": False, "message": f"Invalid role. Must be one of: {', '.join(SUPERVISOR_ROLES)}"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "A user with this email already exists"}), 409

    temp_password = _generate_temp_password()
    tenant_id = getattr(g, "university_id", None)

    user = User(
        email=email,
        role=role,
        first_name=data.get("first_name", "").strip(),
        last_name=data.get("last_name", "").strip(),
        phone=data.get("phone", "").strip(),
        is_email_verified=True,
        status="active",
        university_id=tenant_id,
    )
    user.set_password(temp_password)
    db.session.add(user)
    db.session.flush()

    # Link to department by role
    dept = None
    if tenant_id:
        dept = Department.query.filter_by(role=role, is_active=True, university_id=tenant_id).first()
    if not dept:
        dept = Department.query.filter_by(role=role, is_active=True).first()

    if dept:
        staff_link = DepartmentStaff(
            user_id=user.id,
            department_id=dept.id,
            is_active=True,
            designation=data.get("designation", ""),
        )
        db.session.add(staff_link)

    # Audit log
    audit_uid = _get_admin_audit_user_id(user)
    if audit_uid:
        audit = AuditLog(
            user_id=audit_uid,
            action="create",
            resource_type="user",
            resource_id=user.id,
            university_id=tenant_id,
            details={"created_user": email, "role": role},
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Staff account created successfully for {email}",
        "data": {
            "user": user.to_dict(),
            "temporary_password": temp_password,
            "department": dept.to_dict() if dept else None,
        },
    }), 201


@superadmin_bp.route("/api/users/<user_id>/reset-password", methods=["POST"])
@admin_only
def reset_staff_password(user_id):
    """Reset a staff user's password (generates new temp password)."""
    user = User.query.filter_by(id=user_id).filter(User.deleted_at.is_(None)).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
    if user.role not in SUPERVISOR_ROLES:
        return jsonify({"success": False, "message": "Can only reset passwords for staff users"}), 400

    temp_password = _generate_temp_password()
    user.set_password(temp_password)

    audit_uid = _get_admin_audit_user_id(user)
    if audit_uid:
        audit = AuditLog(
            user_id=audit_uid,
            action="update",
            resource_type="user",
            resource_id=user.id,
            details={"action": "password_reset"},
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Password reset for {user.email}",
        "data": {"temporary_password": temp_password},
    })


@superadmin_bp.route("/api/users/<user_id>/status", methods=["PUT"])
@admin_only
@validate_json("status")
def update_user_status(user_id):
    """Activate or deactivate a user."""
    user = User.query.filter_by(id=user_id).filter(User.deleted_at.is_(None)).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    new_status = request.validated_data["status"]
    if new_status not in ("active", "inactive", "suspended"):
        return jsonify({"success": False, "message": "Invalid status"}), 400

    old_status = user.status
    user.status = new_status

    audit_uid = _get_admin_audit_user_id(user)
    if audit_uid:
        audit = AuditLog(
            user_id=audit_uid,
            action="update",
            resource_type="user",
            resource_id=user.id,
            details={"action": "status_change", "from": old_status, "to": new_status},
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
    db.session.commit()

    return jsonify({"success": True, "message": f"User status updated to {new_status}", "data": user.to_dict()})


@superadmin_bp.route("/api/users/<user_id>", methods=["DELETE"])
@admin_only
def delete_user(user_id):
    """Soft delete a user."""
    user = User.query.filter_by(id=user_id).filter(User.deleted_at.is_(None)).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
    if user.role == "super_admin":
        return jsonify({"success": False, "message": "Cannot delete super admin"}), 400

    user.deleted_at = datetime.now(timezone.utc)
    user.status = "inactive"

    audit_uid = _get_admin_audit_user_id(user)
    if audit_uid:
        audit = AuditLog(
            user_id=audit_uid,
            action="delete",
            resource_type="user",
            resource_id=user.id,
            details={"deleted_user": user.email},
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
    db.session.commit()

    return jsonify({"success": True, "message": "User deleted successfully"})


# ──────────────────────────────────────
# API: Students (list / search)
# ──────────────────────────────────────
@superadmin_bp.route("/api/users/students", methods=["GET"])
@admin_only
def list_students():
    """List all student users with pagination, scoped to university tenant."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "").strip().lower()
    status_filter = request.args.get("status")

    query = User.query.filter_by(role="student").filter(User.deleted_at.is_(None))
    
    tenant_id = getattr(g, "university_id", None)
    if tenant_id:
        query = query.filter((User.university_id == tenant_id) | (User.university_id.is_(None)))

    if status_filter:
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(
            db.or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
            )
        )
    query = query.order_by(User.created_at.desc())
    result = paginate_query(query, page=page, per_page=per_page)

    # Attach student profile to each user
    for item in result["items"]:
        u = User.query.get(item["id"])
        if u and u.student_profile:
            item["student"] = u.student_profile.to_dict()

    return jsonify({"success": True, "data": result})


# ──────────────────────────────────────
# API: All Users (for search / general)
# ──────────────────────────────────────
@superadmin_bp.route("/api/users")
@admin_only
def list_all_users():
    page = request.args.get("page", 1, type=int)
    role_filter = request.args.get("role")
    status_filter = request.args.get("status")

    query = User.query.filter(User.deleted_at.is_(None))
    tenant_id = getattr(g, "university_id", None)
    if tenant_id:
        query = query.filter((User.university_id == tenant_id) | (User.university_id.is_(None)))

    if role_filter:
        query = query.filter_by(role=role_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    query = query.order_by(User.created_at.desc())

    return jsonify({"success": True, "data": paginate_query(query, page=page, per_page=20)})


# ──────────────────────────────────────
# API: Applications Monitoring
# ──────────────────────────────────────
@superadmin_bp.route("/api/applications")
@admin_only
def list_all_applications():
    """List all applications with filters."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status_filter = request.args.get("status")
    dept_filter = request.args.get("department_id")
    search = request.args.get("search", "").strip().lower()

    query = NoDuesApplication.query.filter(NoDuesApplication.deleted_at.is_(None))

    if status_filter:
        query = query.filter_by(status=status_filter)
    if dept_filter:
        query = query.join(ApplicationDepartment).filter(
            ApplicationDepartment.department_id == dept_filter,
        )
    if search:
        query = query.join(Student).join(User).filter(
            db.or_(
                User.email.ilike(f"%{search}%"),
                Student.roll_number.ilike(f"%{search}%"),
                Student.enrollment_number.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
            )
        )

    query = query.order_by(NoDuesApplication.created_at.desc())
    result = paginate_query(query, page=page, per_page=per_page)

    # Enrich with student info
    for item in result["items"]:
        app_obj = NoDuesApplication.query.get(item["id"])
        if app_obj and app_obj.student:
            item["student"] = app_obj.student.to_dict()

    return jsonify({"success": True, "data": result})


@superadmin_bp.route("/api/applications/<app_id>")
@admin_only
def get_application_detail(app_id):
    """Get full detail of a specific application."""
    app_obj = NoDuesApplication.query.filter_by(id=app_id).filter(
        NoDuesApplication.deleted_at.is_(None),
    ).first()
    if not app_obj:
        return jsonify({"success": False, "message": "Application not found"}), 404

    return jsonify({
        "success": True,
        "data": {
            "application": app_obj.to_dict(),
            "student": app_obj.student.to_dict() if app_obj.student else None,
            "department_approvals": [ad.to_dict() for ad in app_obj.department_approvals],
            "documents": [doc.to_dict() for doc in app_obj.documents],
            "admit_card": app_obj.admit_card.to_dict() if app_obj.admit_card else None,
        },
    })


# ──────────────────────────────────────
# API: Audit Logs
# ──────────────────────────────────────
@superadmin_bp.route("/api/audit-logs")
@admin_only
def get_audit_logs():
    """Get paginated audit logs."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 30, type=int)
    action_filter = request.args.get("action")
    resource_filter = request.args.get("resource_type")

    query = AuditLog.query
    if action_filter:
        query = query.filter_by(action=action_filter)
    if resource_filter:
        query = query.filter_by(resource_type=resource_filter)
    query = query.order_by(AuditLog.created_at.desc())

    result = paginate_query(query, page=page, per_page=per_page)
    # Attach user email
    for item in result["items"]:
        if item.get("user_id"):
            u = User.query.get(item["user_id"])
            item["user_email"] = u.email if u else None
            item["user_name"] = u.full_name if u else None

    return jsonify({"success": True, "data": result})


# ──────────────────────────────────────
# API: Semester Management
# ──────────────────────────────────────
@superadmin_bp.route("/api/semesters", methods=["GET"])
@admin_only
def list_semesters():
    """List all semesters."""
    semesters = Semester.query.order_by(Semester.start_date.desc()).all()
    return jsonify({"success": True, "data": [s.to_dict() for s in semesters]})


@superadmin_bp.route("/api/semesters", methods=["POST"])
@admin_only
@validate_json("semester_number", "semester_name", "academic_year", "start_date", "end_date")
def create_semester():
    """Create a new semester."""
    data = request.validated_data

    # If this is set as current, unset others
    if data.get("is_current"):
        Semester.query.filter_by(is_current=True).update({"is_current": False})

    semester = Semester(
        semester_number=int(data["semester_number"]),
        semester_name=data["semester_name"],
        academic_year=data["academic_year"],
        start_date=datetime.fromisoformat(data["start_date"]).date(),
        end_date=datetime.fromisoformat(data["end_date"]).date(),
        is_current=bool(data.get("is_current", False)),
        is_clearance_open=bool(data.get("is_clearance_open", False)),
    )
    db.session.add(semester)

    audit_uid = _get_admin_audit_user_id()
    if audit_uid:
        audit = AuditLog(
            user_id=audit_uid,
            action="create",
            resource_type="semester",
            details={"semester": data["semester_name"], "year": data["academic_year"]},
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
    db.session.commit()

    return jsonify({"success": True, "message": "Semester created", "data": semester.to_dict()}), 201


@superadmin_bp.route("/api/semesters/<semester_id>", methods=["PUT"])
@admin_only
@validate_json()
def update_semester(semester_id):
    """Update a semester."""
    semester = Semester.query.get(semester_id)
    if not semester:
        return jsonify({"success": False, "message": "Semester not found"}), 404

    data = request.validated_data

    if data.get("is_current"):
        Semester.query.filter_by(is_current=True).update({"is_current": False})

    for field in ("semester_number", "semester_name", "academic_year", "is_current", "is_clearance_open", "is_fee_submission_open"):
        if field in data:
            setattr(semester, field, data[field])
    if "start_date" in data:
        semester.start_date = datetime.fromisoformat(data["start_date"]).date()
    if "end_date" in data:
        semester.end_date = datetime.fromisoformat(data["end_date"]).date()

    db.session.commit()
    return jsonify({"success": True, "message": "Semester updated", "data": semester.to_dict()})


@superadmin_bp.route("/api/semesters/<semester_id>", methods=["DELETE"])
@admin_only
def delete_semester(semester_id):
    semester = Semester.query.get(semester_id)
    if not semester:
        return jsonify({"success": False, "message": "Semester not found"}), 404
    db.session.delete(semester)
    db.session.commit()
    return jsonify({"success": True, "message": "Semester deleted"})


# ──────────────────────────────────────
# API: Departments
# ──────────────────────────────────────
@superadmin_bp.route("/api/departments", methods=["GET"])
@admin_only
def list_departments():
    """List all departments."""
    depts = Department.query.order_by(Department.display_order).all()
    return jsonify({"success": True, "data": [d.to_dict() for d in depts]})


@superadmin_bp.route("/api/departments", methods=["POST"])
@admin_only
@validate_json("code", "name", "role")
def create_department():
    """Create a new custom department ID."""
    data = request.validated_data
    code = data.get("code", "").strip().upper()
    name = data.get("name", "").strip()
    role = data.get("role", "").strip().lower()
    description = data.get("description", "").strip()
    display_order = int(data.get("display_order", 10))

    if Department.query.filter_by(code=code).first():
        return jsonify({"success": False, "message": f"Department with code '{code}' already exists"}), 409

    dept = Department(
        code=code,
        name=name,
        description=description,
        role=role,
        display_order=display_order,
        is_active=True,
    )
    db.session.add(dept)

    audit_uid = _get_admin_audit_user_id()
    if audit_uid:
        audit = AuditLog(
            user_id=audit_uid,
            action="create",
            resource_type="department",
            details={"code": code, "name": name, "role": role},
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
    db.session.commit()

    return jsonify({"success": True, "message": f"Department '{name}' created successfully", "data": dept.to_dict()}), 201


@superadmin_bp.route("/api/departments/<dept_id>", methods=["DELETE"])
@admin_only
def delete_department(dept_id):
    """Delete or deactivate a department."""
    dept = Department.query.get(dept_id)
    if not dept:
        return jsonify({"success": False, "message": "Department not found"}), 404

    dept.is_active = False
    audit_uid = _get_admin_audit_user_id()
    if audit_uid:
        audit = AuditLog(
            user_id=audit_uid,
            action="delete",
            resource_type="department",
            details={"dept_id": str(dept.id), "code": dept.code},
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
    db.session.commit()
    return jsonify({"success": True, "message": f"Department '{dept.name}' deactivated"})


# ──────────────────────────────────────
# API: Database Inspector (Task #13)
# ──────────────────────────────────────
@superadmin_bp.route("/api/database-inspector", methods=["GET"])
@admin_only
def database_inspector():
    """Returns real-time database table snapshot for Super Admin inspection."""
    table = request.args.get("table", "users").strip().lower()

    if table == "users":
        rows = User.query.order_by(User.created_at.desc()).limit(100).all()
        data = [
            {
                "id": str(u.id),
                "email": u.email,
                "role": u.role,
                "name": u.full_name,
                "status": u.status,
                "verified": u.is_email_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": u.last_login_at.isoformat() if u.last_login_at else "Never",
            }
            for u in rows
        ]
    elif table == "departments":
        rows = Department.query.order_by(Department.display_order).all()
        data = [
            {
                "id": str(d.id),
                "code": d.code,
                "name": d.name,
                "role": d.role,
                "display_order": d.display_order,
                "is_active": d.is_active,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in rows
        ]
    elif table == "students":
        rows = Student.query.limit(100).all()
        data = [
            {
                "id": str(s.id),
                "user_id": str(s.user_id),
                "roll_number": s.roll_number,
                "enrollment_number": s.enrollment_number,
                "course": s.course_name,
                "branch": s.branch,
                "semester": s.current_semester,
                "category": s.category,
            }
            for s in rows
        ]
    elif table == "applications":
        rows = NoDuesApplication.query.order_by(NoDuesApplication.created_at.desc()).limit(100).all()
        data = [
            {
                "id": str(a.id),
                "application_number": a.application_number,
                "student_id": str(a.student_id),
                "status": a.status,
                "progress": f"{a.progress_percentage}%",
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ]
    elif table == "admit_cards":
        rows = AdmitCard.query.order_by(AdmitCard.created_at.desc()).limit(100).all()
        data = [
            {
                "id": str(ac.id),
                "card_number": ac.card_number,
                "application_id": str(ac.application_id),
                "student_id": str(ac.student_id),
                "downloads": ac.download_count,
                "created_at": ac.created_at.isoformat() if ac.created_at else None,
            }
            for ac in rows
        ]
    else:
        return jsonify({"success": False, "message": "Invalid table requested"}), 400

    return jsonify({"success": True, "table": table, "total_records": len(data), "rows": data})



# ──────────────────────────────────────
# API: System Settings
# ──────────────────────────────────────
@superadmin_bp.route("/api/settings", methods=["GET"])
@admin_only
def get_settings():
    settings = SystemSetting.query.all()
    return jsonify({
        "success": True,
        "data": {
            s.setting_key: {
                "value": s.setting_value,
                "type": s.setting_type,
                "description": s.description,
            }
            for s in settings
        },
    })


@superadmin_bp.route("/api/settings/<key>", methods=["PUT"])
@admin_only
@validate_json("value")
def update_setting(key):
    setting = SystemSetting.query.filter_by(setting_key=key).first()
    if not setting:
        return jsonify({"success": False, "message": "Setting not found"}), 404
    setting.setting_value = request.validated_data["value"]
    db.session.commit()
    return jsonify({"success": True, "message": "Setting updated"})


@superadmin_bp.route("/api/settings/init", methods=["POST"])
@admin_only
def init_default_settings():
    """Create default system settings if they don't exist."""
    defaults = [
        ("clearance_open", "true", "bool", "Is the no-dues clearance currently open?", True),
        ("max_applications_per_semester", "3", "int", "Maximum applications a student can submit per semester", True),
        ("auto_approve_days", "7", "int", "Days after which pending approvals auto-expire", False),
        ("enable_notifications", "true", "bool", "Enable email/push notifications", True),
        ("maintenance_mode", "false", "bool", "Put the system in maintenance mode (only admin can access)", False),
    ]
    created = []
    for key, value, stype, desc, public in defaults:
        if not SystemSetting.query.filter_by(setting_key=key).first():
            s = SystemSetting(
                setting_key=key,
                setting_value=value,
                setting_type=stype,
                description=desc,
                is_public=public,
            )
            db.session.add(s)
            created.append(key)
    db.session.commit()
    return jsonify({"success": True, "message": f"Created {len(created)} default settings", "data": created})


# ──────────────────────────────────────
# API: Advanced Analytics
# ──────────────────────────────────────
@superadmin_bp.route("/api/analytics")
@admin_only
def get_analytics():
    """Get detailed real-time analytics for charts and KPIs."""
    days = request.args.get("days", 30, type=int)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    # 1. Realtime Date Range Map
    date_counts_apps = {}
    date_counts_reg = {}
    for i in range(days):
        d_str = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        date_counts_apps[d_str] = 0
        date_counts_reg[d_str] = 0

    daily_apps_query = (
        db.session.query(
            db.func.date(NoDuesApplication.created_at).label("date"),
            db.func.count().label("count"),
        )
        .filter(NoDuesApplication.created_at >= since)
        .group_by(db.func.date(NoDuesApplication.created_at))
        .all()
    )

    for row in daily_apps_query:
        if row.date:
            d_str = str(row.date)
            if d_str in date_counts_apps:
                date_counts_apps[d_str] = row.count

    daily_reg_query = (
        db.session.query(
            db.func.date(User.created_at).label("date"),
            db.func.count().label("count"),
        )
        .filter(User.created_at >= since)
        .group_by(db.func.date(User.created_at))
        .all()
    )

    for row in daily_reg_query:
        if row.date:
            d_str = str(row.date)
            if d_str in date_counts_reg:
                date_counts_reg[d_str] = row.count

    # 2. Role Distribution
    role_dist = (
        db.session.query(User.role, db.func.count().label("count"))
        .filter(User.deleted_at.is_(None))
        .group_by(User.role)
        .all()
    )

    # 3. Application Status Distribution
    status_dist = (
        db.session.query(
            NoDuesApplication.status, db.func.count().label("count")
        )
        .filter(NoDuesApplication.deleted_at.is_(None))
        .group_by(NoDuesApplication.status)
        .all()
    )

    # 4. Department Performance Metrics (Pending, Approved, Rejected per Department)
    departments = Department.query.filter_by(is_active=True).all()
    dept_perf = []
    for d in departments:
        pending_c = ApplicationDepartment.query.filter_by(department_id=d.id, status="pending").count()
        approved_c = ApplicationDepartment.query.filter_by(department_id=d.id, status="approved").count()
        rejected_c = ApplicationDepartment.query.filter_by(department_id=d.id, status="rejected").count()
        dept_perf.append({
            "code": d.code,
            "name": d.name,
            "role": d.role,
            "pending": pending_c,
            "approved": approved_c,
            "rejected": rejected_c,
        })

    # 5. Key System KPIs
    total_apps = NoDuesApplication.query.filter_by(deleted_at=None).count()
    total_students = Student.query.count()
    approved_apps = NoDuesApplication.query.filter_by(status="approved", deleted_at=None).count()
    rejected_apps = NoDuesApplication.query.filter_by(status="rejected", deleted_at=None).count()
    admit_cards = AdmitCard.query.count()

    approval_rate = round((approved_apps / total_apps * 100), 1) if total_apps > 0 else 0.0

    return jsonify({
        "success": True,
        "data": {
            "kpi": {
                "total_applications": total_apps,
                "total_students": total_students,
                "approved_applications": approved_apps,
                "rejected_applications": rejected_apps,
                "admit_cards_issued": admit_cards,
                "approval_rate": approval_rate,
            },
            "daily_applications": [
                {"date": k, "count": v} for k, v in date_counts_apps.items()
            ],
            "daily_registrations": [
                {"date": k, "count": v} for k, v in date_counts_reg.items()
            ],
            "role_distribution": [
                {"role": row.role, "count": row.count} for row in role_dist
            ],
            "application_status": [
                {"status": row.status, "count": row.count} for row in status_dist
            ],
            "department_performance": dept_perf,
        },
    })


# ──────────────────────────────────────
# API: Student Feedbacks & NPS Analytics
# ──────────────────────────────────────
@superadmin_bp.route("/api/feedbacks")
@admin_only
def get_feedbacks():
    """Get all student feedbacks with aggregated statistics, ratings distribution, and NPS score."""
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 15))
    rating_filter = request.args.get("rating")
    sentiment_filter = request.args.get("sentiment")
    search = (request.args.get("search") or "").strip().lower()

    # Query for statistics across all feedbacks
    all_feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()
    total_feedbacks = len(all_feedbacks)

    if total_feedbacks > 0:
        avg_rating = round(sum(f.overall_rating for f in all_feedbacks) / total_feedbacks, 2)
        
        # NPS Calculation: Promoters (9-10), Passives (7-8), Detractors (1-6)
        promoters = sum(1 for f in all_feedbacks if (f.nps_score or 10) >= 9)
        detractors = sum(1 for f in all_feedbacks if (f.nps_score or 10) <= 6)
        nps_score = round(((promoters - detractors) / total_feedbacks) * 100, 1)

        # Star breakdown
        rating_dist = {
            "5_star": sum(1 for f in all_feedbacks if f.overall_rating == 5),
            "4_star": sum(1 for f in all_feedbacks if f.overall_rating == 4),
            "3_star": sum(1 for f in all_feedbacks if f.overall_rating == 3),
            "2_star": sum(1 for f in all_feedbacks if f.overall_rating == 2),
            "1_star": sum(1 for f in all_feedbacks if f.overall_rating == 1),
        }

        # Sentiment breakdown
        sentiment_dist = {
            "positive": sum(1 for f in all_feedbacks if f.sentiment == "positive"),
            "neutral": sum(1 for f in all_feedbacks if f.sentiment == "neutral"),
            "constructive": sum(1 for f in all_feedbacks if f.sentiment == "constructive"),
        }

        # Feature satisfactions
        smooth_uploads = round((sum(1 for f in all_feedbacks if f.upload_experience == "smooth") / total_feedbacks) * 100, 1)
        helpful_ai = round((sum(1 for f in all_feedbacks if f.ai_helpfulness in ["extremely_helpful", "good"]) / total_feedbacks) * 100, 1)
        easy_navigation = round((sum(1 for f in all_feedbacks if f.ease_of_use in ["very_easy", "easy"]) / total_feedbacks) * 100, 1)
    else:
        avg_rating = 5.0
        nps_score = 100.0
        rating_dist = {"5_star": 0, "4_star": 0, "3_star": 0, "2_star": 0, "1_star": 0}
        sentiment_dist = {"positive": 0, "neutral": 0, "constructive": 0}
        smooth_uploads = 100.0
        helpful_ai = 100.0
        easy_navigation = 100.0

    # Filtered Query for table/feed list
    query = Feedback.query

    if rating_filter and rating_filter.isdigit():
        query = query.filter(Feedback.overall_rating == int(rating_filter))

    if sentiment_filter:
        query = query.filter(Feedback.sentiment == sentiment_filter)

    if search:
        # Join with user and student for name/email/roll search
        query = query.join(User, Feedback.user_id == User.id, isouter=True)\
                     .join(Student, Feedback.student_id == Student.id, isouter=True)\
                     .filter(
                         db.or_(
                             User.first_name.ilike(f"%{search}%"),
                             User.last_name.ilike(f"%{search}%"),
                             User.email.ilike(f"%{search}%"),
                             Student.roll_number.ilike(f"%{search}%"),
                             Feedback.comments.ilike(f"%{search}%")
                         )
                     )

    query = query.order_by(Feedback.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "total_feedbacks": total_feedbacks,
                "average_rating": avg_rating,
                "nps_score": nps_score,
                "rating_distribution": rating_dist,
                "sentiment_distribution": sentiment_dist,
                "satisfaction_metrics": {
                    "smooth_uploads_percent": smooth_uploads,
                    "helpful_ai_percent": helpful_ai,
                    "easy_navigation_percent": easy_navigation,
                }
            },
            "items": [f.to_dict() for f in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_prev": pagination.has_prev,
                "has_next": pagination.has_next,
            }
        }
    })


@superadmin_bp.route("/api/feedbacks/<feedback_id>", methods=["DELETE"])
@admin_only
def delete_feedback(feedback_id):
    """Delete a student feedback record (Super Admin moderation)."""
    feedback = Feedback.query.get(feedback_id)
    if not feedback:
        return jsonify({"success": False, "message": "Feedback record not found"}), 404

    db.session.delete(feedback)
    db.session.commit()

    return jsonify({"success": True, "message": "Feedback deleted successfully"})


@superadmin_bp.route("/api/export/full", methods=["GET", "POST"])
@jwt_required(optional=True)
def export_institutional_data():
    """Trigger and download comprehensive institutional data export archive."""
    import os
    import tempfile
    import uuid
    from flask import send_file, session
    from export.data_exporter import UniversityDataExporter
    
    user = None
    user_id = get_jwt_identity()
    if user_id:
        user = User.query.get(user_id)
    elif current_user and current_user.is_authenticated:
        user = current_user

    univ_id = session.get("university_id")

    # Authorized if super_admin OR logged in university leadership tenant
    if not (user and user.role == "super_admin") and not univ_id:
        return jsonify({"success": False, "message": "University Super Admin or Institutional Leader access required"}), 403

    temp_dir = tempfile.mkdtemp()
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(temp_dir, f"university_export_{timestamp_str}.zip")

    export_summary = UniversityDataExporter.export_to_zip(zip_path, include_documents=True)

    # Record tamper-evident audit event
    sa_user = User.query.filter_by(role="super_admin").first()
    if sa_user:
        try:
            audit = AuditLog(
                user_id=sa_user.id,
                action="download",
                resource_type="university_data",
                resource_id=sa_user.id,
                details={
                    "sha256": export_summary["archive_sha256"],
                    "counts": export_summary["manifest"]["counts"],
                },
                ip_address=get_client_ip(),
                user_agent=get_user_agent(),
            )
            db.session.add(audit)
            db.session.commit()
        except Exception:
            db.session.rollback()

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"SmartNoDues_Backup_{timestamp_str}.zip",
    )


# ──────────────────────────────────────
# API: Bulk CSV Student & Staff Imports
# ──────────────────────────────────────
@superadmin_bp.route("/api/users/students/import-csv", methods=["POST"])
@admin_only
def import_students_csv():
    """Bulk import student roster via CSV or JSON rows."""
    import csv
    import io
    from utils.tenant_resolver import get_current_tenant_id

    tenant_id = get_current_tenant_id()
    rows = []

    if "file" in request.files:
        file = request.files["file"]
        if not file.filename.endswith((".csv", ".txt")):
            return jsonify({"success": False, "message": "Please upload a valid .csv file."}), 400
        stream = io.StringIO(file.stream.read().decode("utf-8-sig", errors="ignore"))
        reader = csv.DictReader(stream)
        rows = list(reader)
    elif request.is_json:
        rows = request.json.get("rows", [])
    else:
        return jsonify({"success": False, "message": "CSV file or JSON rows required."}), 400

    created_count = 0
    skipped_count = 0
    errors = []

    for idx, row in enumerate(rows, start=1):
        email = (row.get("email") or row.get("Email") or "").strip().lower()
        roll_no = (row.get("roll_number") or row.get("Roll Number") or row.get("roll_no") or "").strip()
        first_name = (row.get("first_name") or row.get("First Name") or row.get("name") or "Student").strip()
        last_name = (row.get("last_name") or row.get("Last Name") or "").strip()
        course_name = (row.get("course_name") or row.get("Course") or "B.Tech").strip()
        branch = (row.get("branch") or row.get("Branch") or "CSE").strip()
        semester = int(row.get("current_semester") or row.get("Semester") or 1)
        batch = (row.get("batch_year") or row.get("Batch") or "2022-2026").strip()

        if not email or not roll_no:
            skipped_count += 1
            continue

        existing_user = User.query.filter_by(email=email).first()
        existing_student = Student.query.filter_by(roll_number=roll_no).first()

        if existing_user or existing_student:
            skipped_count += 1
            continue

        try:
            temp_pass = _generate_temp_password()
            user = User(
                email=email,
                role="student",
                first_name=first_name,
                last_name=last_name,
                is_email_verified=True,
                status="active",
                university_id=tenant_id,
            )
            user.set_password(temp_pass)
            db.session.add(user)
            db.session.flush()

            student = Student(
                user_id=user.id,
                roll_number=roll_no,
                enrollment_number=f"EN-{roll_no}",
                course_name=course_name,
                branch=branch,
                current_semester=semester,
                batch_year=batch,
                admission_year=int(batch.split("-")[0]) if "-" in batch else 2022,
                category="day_scholar",
                university_id=tenant_id,
            )
            db.session.add(student)
            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx} ({email}): {str(e)}")

    db.session.commit()
    return jsonify({
        "success": True,
        "message": f"Successfully imported {created_count} students ({skipped_count} skipped/existing).",
        "data": {
            "created": created_count,
            "skipped": skipped_count,
            "errors": errors,
        }
    })


@superadmin_bp.route("/api/users/staff/import-csv", methods=["POST"])
@admin_only
def import_staff_csv():
    """Bulk import staff roster via CSV or JSON rows."""
    import csv
    import io
    from utils.tenant_resolver import get_current_tenant_id

    tenant_id = get_current_tenant_id()
    rows = []

    if "file" in request.files:
        file = request.files["file"]
        if not file.filename.endswith((".csv", ".txt")):
            return jsonify({"success": False, "message": "Please upload a valid .csv file."}), 400
        stream = io.StringIO(file.stream.read().decode("utf-8-sig", errors="ignore"))
        reader = csv.DictReader(stream)
        rows = list(reader)
    elif request.is_json:
        rows = request.json.get("rows", [])
    else:
        return jsonify({"success": False, "message": "CSV file or JSON rows required."}), 400

    created_count = 0
    skipped_count = 0
    errors = []

    for idx, row in enumerate(rows, start=1):
        email = (row.get("email") or row.get("Email") or "").strip().lower()
        role = (row.get("role") or row.get("Role") or "accounts").strip().lower()
        first_name = (row.get("first_name") or row.get("First Name") or row.get("name") or "Staff").strip()
        last_name = (row.get("last_name") or row.get("Last Name") or "").strip()
        designation = (row.get("designation") or row.get("Designation") or "Officer").strip()

        if not email or role not in SUPERVISOR_ROLES:
            skipped_count += 1
            continue

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            skipped_count += 1
            continue

        try:
            temp_pass = _generate_temp_password()
            user = User(
                email=email,
                role=role,
                first_name=first_name,
                last_name=last_name,
                is_email_verified=True,
                status="active",
                university_id=tenant_id,
            )
            user.set_password(temp_pass)
            db.session.add(user)
            db.session.flush()

            # Link department
            dept = Department.query.filter_by(role=role, is_active=True).first()
            if dept:
                staff_link = DepartmentStaff(
                    user_id=user.id,
                    department_id=dept.id,
                    designation=designation,
                    is_active=True,
                )
                db.session.add(staff_link)

            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx} ({email}): {str(e)}")

    db.session.commit()
    return jsonify({
        "success": True,
        "message": f"Successfully imported {created_count} staff members ({skipped_count} skipped/existing).",
        "data": {
            "created": created_count,
            "skipped": skipped_count,
            "errors": errors,
        }
    })


# ──────────────────────────────────────
# API: University Whitelabel Branding
# ──────────────────────────────────────
@superadmin_bp.route("/api/university/branding", methods=["GET", "PUT"])
@admin_only
def manage_branding():
    """Retrieve or update university whitelabel branding."""
    from utils.tenant_resolver import get_current_tenant
    tenant = get_current_tenant()
    if not tenant:
        return jsonify({"success": False, "message": "University tenant context required."}), 404

    if request.method == "GET":
        return jsonify({
            "success": True,
            "data": {
                "university_name": tenant.name,
                "slug": tenant.slug,
                "custom_domain": tenant.custom_domain,
                "logo_url": tenant.logo_url,
                "favicon_url": tenant.favicon_url,
                "primary_color": tenant.primary_color,
                "accent_color": tenant.accent_color,
                "banner_text": tenant.banner_text,
                "sso_config": tenant.sso_config or {},
            }
        })

    data = request.get_json(silent=True) or request.form
    if "logo_url" in data:
        from utils.helpers import normalize_logo_url
        raw_logo = data.get("logo_url")
        tenant.logo_url = normalize_logo_url(raw_logo) if raw_logo else None
    if "primary_color" in data:
        tenant.primary_color = data.get("primary_color")
    if "accent_color" in data:
        tenant.accent_color = data.get("accent_color")
    if "banner_text" in data:
        tenant.banner_text = data.get("banner_text")
    if "custom_domain" in data:
        tenant.custom_domain = data.get("custom_domain")

    db.session.commit()
    return jsonify({
        "success": True,
        "message": "University branding updated successfully.",
        "data": tenant.to_dict()
    })


# ──────────────────────────────────────
# API: Full Institutional Tenant Dataset Export & Migration Package
# ──────────────────────────────────────
@superadmin_bp.route("/api/export/tenant-archive", methods=["GET"])
@superadmin_bp.route("/api/export/full", methods=["GET"])
@admin_only
def export_tenant_archive():
    """Generates and downloads a complete standalone JSON archive of this university's dataset for migration/backup."""
    from models.university import UniversityTenant
    from flask import Response
    import json

    tenant_id = _get_active_tenant_id()
    tenant = None
    if tenant_id:
        tenant = db.session.get(UniversityTenant, tenant_id)
    if not tenant:
        tenant = UniversityTenant.query.first()

    if not tenant:
        return jsonify({"success": False, "message": "No university tenant found."}), 404

    # 1. University Metadata
    univ_data = tenant.to_dict()

    # 2. Departments
    depts = Department.query.filter_by(university_id=tenant.id).all()
    if not depts:
        depts = Department.query.all()
    departments_data = [d.to_dict() for d in depts]

    # 3. Staff Users
    staff_users = User.query.filter(
        User.university_id == tenant.id,
        User.role != "student",
        User.deleted_at.is_(None)
    ).all()
    staff_data = [u.to_dict() for u in staff_users]

    # 4. Students
    students = Student.query.filter_by(university_id=tenant.id).all()
    students_data = [s.to_dict() for s in students]

    # 5. Applications
    applications = NoDuesApplication.query.filter_by(university_id=tenant.id).all()
    applications_data = []
    for app in applications:
        app_dict = app.to_dict()
        app_dict["department_approvals"] = [da.to_dict() for da in app.department_approvals]
        app_dict["documents"] = [doc.to_dict() for doc in app.documents]
        applications_data.append(app_dict)

    # 6. Admit Cards
    admit_cards = AdmitCard.query.join(NoDuesApplication).filter(NoDuesApplication.university_id == tenant.id).all()
    admit_cards_data = [ac.to_dict() for ac in admit_cards]

    # 7. Audit Logs
    audit_logs = AuditLog.query.filter(AuditLog.user_id.in_([u.id for u in staff_users] + [s.user_id for s in students])).limit(500).all()
    audits_data = [
        {
            "id": str(a.id),
            "action": a.action,
            "resource_type": a.resource_type,
            "details": a.details,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in audit_logs
    ]

    export_package = {
        "export_metadata": {
            "format": "SmartNoDues-Tenant-Migration-Archive",
            "version": "4.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "institution_name": tenant.name,
            "institution_slug": tenant.slug,
            "subscription_plan": tenant.subscription_plan,
            "total_students": len(students_data),
            "total_staff": len(staff_data),
            "total_applications": len(applications_data),
            "total_admit_cards": len(admit_cards_data),
        },
        "university": univ_data,
        "departments": departments_data,
        "staff": staff_data,
        "students": students_data,
        "applications": applications_data,
        "admit_cards": admit_cards_data,
        "audit_stream": audits_data,
    }

    json_output = json.dumps(export_package, indent=2)
    filename = f"{tenant.slug}_nodues_dataset_export.json"

    return Response(
        json_output,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
