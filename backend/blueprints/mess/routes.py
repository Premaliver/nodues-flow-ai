# type: ignore
# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false, reportUnusedImport=false
"""Mess department routes — mess dues clearance management."""

from datetime import datetime, timezone, timedelta

from flask import request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required

from . import mess_bp
from models import db
from models.user import User
from models.student import Student
from models.department import Department
from models.application import NoDuesApplication, ApplicationDepartment
from models.notification import Notification
from models.audit_log import AuditLog
from utils.decorators import department_access, validate_json
from utils.helpers import paginate_query, get_client_ip, get_user_agent


@mess_bp.route("/dashboard")
@login_required
@department_access("mess")
def dashboard():
    from utils.tenant_helpers import get_current_context_university
    univ = get_current_context_university()
    return render_template("mess/dashboard.html", university=univ)


@mess_bp.route("/api/dashboard")
@jwt_required()
def dashboard_data():
    user_id = get_jwt_identity()
    user = None
    if user_id:
        try:
            import uuid as _uuid
            user = User.query.get(_uuid.UUID(str(user_id)))
        except Exception:
            user = User.query.get(user_id)
    u_id = user.university_id if user else None

    mess_dept = None
    if u_id:
        from utils.tenant_helpers import ensure_university_departments
        ensure_university_departments(u_id)
        mess_dept = Department.query.filter_by(role="mess", university_id=u_id).first()

    if not mess_dept:
        return jsonify({
            "success": True,
            "data": {
                "stats": {"pending": 0, "approved": 0, "rejected": 0, "total": 0},
                "pending_applications": []
            }
        })

    pending = ApplicationDepartment.query.filter_by(
        department_id=mess_dept.id, status="pending"
    ).count()
    approved = ApplicationDepartment.query.filter_by(
        department_id=mess_dept.id, status="approved"
    ).count()
    rejected = ApplicationDepartment.query.filter_by(
        department_id=mess_dept.id, status="rejected"
    ).count()

    total = pending + approved + rejected

    query = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id == mess_dept.id,
            ApplicationDepartment.status == "pending",
        )
    )
    if u_id:
        query = query.filter(NoDuesApplication.university_id == u_id)

    pending_apps = (
        query
        .order_by(NoDuesApplication.created_at.desc())
        .limit(10)
        .all()
    )

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "pending": pending,
                "approved": approved,
                "rejected": rejected,
                "total": total,
            },
            "pending_applications": [
                {
                    "application_id": str(app.id),
                    "app_dept_id": str(app_dept.id),
                    "application_number": app.application_number,
                    "student_name": user.full_name,
                    "roll_number": student.roll_number,
                    "course_name": student.course_name,
                    "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
                }
                for app_dept, app, student, user in pending_apps
            ],
        },
    })


@mess_bp.route("/api/process/<app_dept_id>", methods=["POST"])
@jwt_required()
@validate_json("action")
def process_application(app_dept_id):
    user_id = get_jwt_identity()
    mess_dept = Department.query.filter_by(role="mess").first()

    app_dept = ApplicationDepartment.query.filter_by(
        id=app_dept_id, department_id=mess_dept.id
    ).first()

    if not app_dept:
        return jsonify({"success": False, "message": "Application not found"}), 404

    data = request.validated_data
    action = data.get("action")
    remarks = data.get("remarks", "")

    if action not in ("approved", "rejected"):
        return jsonify({"success": False, "message": "Invalid action"}), 400

    app_dept.status = action
    app_dept.remarks = remarks
    app_dept.processed_at = datetime.now(timezone.utc)
    app_dept.processed_by = user_id

    application = NoDuesApplication.query.get(app_dept.application_id)

    if action == "approved":
        application.current_step += 1
        if application.status == "submitted":
            application.status = "in_review"
    else:
        application.status = "rejected"

    notification = Notification(
        user_id=application.student.user_id,
        type="department_approved" if action == "approved" else "department_rejected",
        title=f"Mess department {action} your application",
        message=remarks or f"Your application has been {action} by Mess Department.",
        application_id=application.id,
    )
    db.session.add(notification)

    audit = AuditLog(
        user_id=user_id,
        action="approve" if action == "approved" else "reject",
        resource_type="application_department",
        resource_id=app_dept.id,
        details={"application_id": str(application.id), "department": "mess", "action": action},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"success": True, "message": f"Application {action} successfully"})
