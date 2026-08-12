"""Hostel department routes — hostel accommodation clearance."""

from datetime import datetime, timezone, timedelta

from flask import request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required

from . import hostel_bp
from models import db
from models.user import User
from models.student import Student
from models.department import Department
from models.application import NoDuesApplication, ApplicationDepartment
from models.notification import Notification
from models.audit_log import AuditLog
from utils.decorators import department_access, validate_json
from utils.helpers import paginate_query, get_client_ip, get_user_agent


@hostel_bp.route("/dashboard")
@login_required
@department_access("hostel")
def dashboard():
    """Render hostel dashboard."""
    return render_template("hostel/dashboard.html")


@hostel_bp.route("/api/dashboard")
@jwt_required()
def dashboard_data():
    """Get hostel dashboard data."""
    hostel_dept = Department.query.filter_by(role="hostel").first()

    pending_count = ApplicationDepartment.query.filter_by(
        department_id=hostel_dept.id,
        status="pending",
    ).count()

    in_review_count = ApplicationDepartment.query.filter_by(
        department_id=hostel_dept.id,
        status="in_review",
    ).count()

    approved_today = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id == hostel_dept.id,
        ApplicationDepartment.status == "approved",
        ApplicationDepartment.processed_at >= datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ),
    ).count()

    # Hosteller-only applications pending
    pending_apps = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id == hostel_dept.id,
            ApplicationDepartment.status == "pending",
            Student.category.in_([
                "hosteller", "hosteller_transport",
                "scholarship_hosteller", "hosteller_scholarship_transport",
            ]),
        )
        .order_by(NoDuesApplication.created_at.desc())
        .limit(10)
        .all()
    )

    pending_list = []
    for app_dept, app, student, user in pending_apps:
        pending_list.append({
            "application_id": str(app.id),
            "app_dept_id": str(app_dept.id),
            "application_number": app.application_number,
            "student_name": user.full_name,
            "roll_number": student.roll_number,
            "room_number": "",  # Will be populated from hostel system
            "hostel_block": "",
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        })

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "pending": pending_count,
                "in_review": in_review_count,
                "approved_today": approved_today,
            },
            "pending_applications": pending_list,
        },
    })


@hostel_bp.route("/api/applications")
@jwt_required()
def list_applications():
    """List applications pending hostel clearance."""
    hostel_dept = Department.query.filter_by(role="hostel").first()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status_filter = request.args.get("status", "pending")

    query = (
        db.session.query(ApplicationDepartment)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .filter(
            ApplicationDepartment.department_id == hostel_dept.id,
            ApplicationDepartment.status == status_filter,
        )
        .order_by(ApplicationDepartment.created_at.desc())
    )

    return jsonify({
        "success": True,
        "data": paginate_query(query, page=page, per_page=per_page),
    })


@hostel_bp.route("/api/process/<app_dept_id>", methods=["POST"])
@jwt_required()
@validate_json("action")
def process_application(app_dept_id):
    """Approve or reject a hostel application."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    hostel_dept = Department.query.filter_by(role="hostel").first()

    app_dept = ApplicationDepartment.query.filter_by(
        id=app_dept_id,
        department_id=hostel_dept.id,
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

    # Notify student
    notification = Notification(
        user_id=application.student.user_id,
        type="department_approved" if action == "approved" else "department_rejected",
        title=f"Hostel department {action} your application",
        message=remarks,
        application_id=application.id,
    )
    db.session.add(notification)

    audit = AuditLog(
        user_id=user_id,
        action="approve" if action == "approved" else "reject",
        resource_type="application_department",
        resource_id=app_dept.id,
        details={"department": "hostel", "action": action},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Application {action} successfully",
    })

