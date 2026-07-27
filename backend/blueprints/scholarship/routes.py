"""Scholarship department routes — scholarship verification."""

from datetime import datetime, timezone

from flask import request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required

from . import scholarship_bp
from models import db
from models.department import Department
from models.application import ApplicationDepartment, NoDuesApplication
from models.student import Student
from models.user import User
from models.notification import Notification
from models.audit_log import AuditLog
from utils.decorators import department_access, validate_json
from utils.helpers import get_client_ip, get_user_agent


@scholarship_bp.route("/dashboard")
@login_required
@department_access("scholarship")
def dashboard():
    return render_template("scholarship/dashboard.html")


@scholarship_bp.route("/api/dashboard")
@jwt_required()
def dashboard_data():
    sch_dept = Department.query.filter_by(role="scholarship").first()

    pending = ApplicationDepartment.query.filter_by(
        department_id=sch_dept.id, status="pending"
    ).count()
    approved = ApplicationDepartment.query.filter_by(
        department_id=sch_dept.id, status="approved"
    ).count()
    rejected = ApplicationDepartment.query.filter_by(
        department_id=sch_dept.id, status="rejected"
    ).count()

    pending_apps = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id == sch_dept.id,
            ApplicationDepartment.status == "pending",
        )
        .order_by(NoDuesApplication.created_at.desc())
        .limit(10)
        .all()
    )

    return jsonify({
        "success": True,
        "data": {
            "stats": {"pending": pending, "approved": approved, "rejected": rejected},
            "pending_applications": [
                {
                    "application_id": str(app.id),
                    "application_number": app.application_number,
                    "student_name": user.full_name,
                    "roll_number": student.roll_number,
                    "scholarship_type": student.category,
                    "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
                }
                for app_dept, app, student, user in pending_apps
            ],
        },
    })


@scholarship_bp.route("/api/process/<app_dept_id>", methods=["POST"])
@jwt_required()
@validate_json("action")
def process_application(app_dept_id):
    user_id = get_jwt_identity()
    sch_dept = Department.query.filter_by(role="scholarship").first()

    app_dept = ApplicationDepartment.query.filter_by(
        id=app_dept_id, department_id=sch_dept.id
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
    else:
        application.status = "rejected"

    notification = Notification(
        user_id=application.student.user_id,
        type="department_approved" if action == "approved" else "department_rejected",
        title=f"Scholarship department {action} your application",
        message=remarks,
        application_id=application.id,
    )
    db.session.add(notification)

    audit = AuditLog(
        user_id=user_id,
        action="approve" if action == "approved" else "reject",
        resource_type="application_department",
        resource_id=app_dept.id,
        details={"application_id": str(application.id), "department": "scholarship", "action": action},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"success": True, "message": f"Application {action} successfully"})
