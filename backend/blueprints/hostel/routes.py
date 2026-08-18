# type: ignore
# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false, reportUnusedImport=false
"""Hostel department routes — hostel accommodation clearance management."""

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
    """Render hostel clearance dashboard."""
    return render_template("hostel/dashboard.html")


@hostel_bp.route("/api/dashboard")
@jwt_required()
def dashboard_data():
    """Get hostel dashboard data with all assigned applications."""
    hostel_dept = Department.query.filter_by(role="hostel").first()
    if not hostel_dept:
        return jsonify({"success": False, "message": "Hostel department not found"}), 404

    pending_count = ApplicationDepartment.query.filter_by(
        department_id=hostel_dept.id,
        status="pending",
    ).count()

    in_review_count = ApplicationDepartment.query.filter_by(
        department_id=hostel_dept.id,
        status="in_review",
    ).count()

    approved_count = ApplicationDepartment.query.filter_by(
        department_id=hostel_dept.id,
        status="approved",
    ).count()

    rejected_count = ApplicationDepartment.query.filter_by(
        department_id=hostel_dept.id,
        status="rejected",
    ).count()

    approved_today = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id == hostel_dept.id,
        ApplicationDepartment.status == "approved",
        ApplicationDepartment.processed_at >= datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ),
    ).count()

    # Query ALL pending & in_review applications assigned to hostel department
    pending_apps = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id == hostel_dept.id,
            ApplicationDepartment.status.in_(["pending", "in_review"]),
        )
        .order_by(NoDuesApplication.created_at.desc())
        .all()
    )

    # Query recent processed applications
    recent_processed = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id == hostel_dept.id,
            ApplicationDepartment.status.in_(["approved", "rejected"]),
        )
        .order_by(ApplicationDepartment.processed_at.desc())
        .limit(20)
        .all()
    )

    def serialize_row(app_dept, app, student, user):
        return {
            "application_id": str(app.id),
            "app_dept_id": str(app_dept.id),
            "application_number": app.application_number,
            "student_name": user.full_name,
            "roll_number": student.roll_number,
            "enrollment_number": student.enrollment_number or "—",
            "course_name": student.course_name or "—",
            "branch": student.branch or "—",
            "current_semester": student.current_semester or "—",
            "category": student.category or "hosteller",
            "phone": user.phone or student.guardian_phone or "—",
            "guardian_phone": student.guardian_phone or "—",
            "status": app_dept.status,
            "remarks": app_dept.remarks or "",
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else (app.created_at.isoformat() if app.created_at else None),
            "processed_at": app_dept.processed_at.isoformat() if app_dept.processed_at else None,
        }

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "pending": pending_count,
                "in_review": in_review_count,
                "approved": approved_count,
                "rejected": rejected_count,
                "approved_today": approved_today,
                "total": pending_count + in_review_count + approved_count + rejected_count,
            },
            "pending_applications": [serialize_row(*row) for row in pending_apps],
            "recent_processed": [serialize_row(*row) for row in recent_processed],
        },
    })


@hostel_bp.route("/api/process/<app_dept_id>", methods=["POST"])
@hostel_bp.route("/api/clearance", methods=["POST"])
@jwt_required()
def process_clearance(app_dept_id=None):
    """Approve or reject a hostel application clearance."""
    user_id = get_jwt_identity()
    hostel_dept = Department.query.filter_by(role="hostel").first()
    if not hostel_dept:
        return jsonify({"success": False, "message": "Hostel department not configured"}), 500

    data = request.get_json(silent=True) or {}
    target_app_dept_id = app_dept_id or data.get("app_dept_id")
    action = data.get("action") or data.get("status")
    remarks = data.get("remarks", "").strip()

    if not target_app_dept_id:
        return jsonify({"success": False, "message": "Application ID is required"}), 400

    if action not in ("approved", "rejected", "in_review"):
        return jsonify({"success": False, "message": "Invalid action. Must be 'approved', 'rejected', or 'in_review'"}), 400

    app_dept = ApplicationDepartment.query.filter_by(
        id=target_app_dept_id,
        department_id=hostel_dept.id,
    ).first()

    if not app_dept:
        return jsonify({"success": False, "message": "Application record not found for Hostel Department"}), 404

    app_dept.status = action
    app_dept.remarks = remarks
    app_dept.processed_at = datetime.now(timezone.utc)
    app_dept.processed_by = user_id

    application = NoDuesApplication.query.get(app_dept.application_id)
    if application:
        if action == "approved":
            application.current_step += 1
            if application.status == "submitted":
                application.status = "in_review"
            
            # Check if all department approvals are now approved
            all_approved = all(
                d.status == "approved" for d in application.department_approvals
            )
            if all_approved:
                application.status = "approved"
                application.completed_at = datetime.now(timezone.utc)
        elif action == "rejected":
            application.status = "rejected"

        # Notify student
        if application.student:
            notification = Notification(
                user_id=application.student.user_id,
                type="department_approved" if action == "approved" else "department_rejected",
                title=f"Hostel department {action} your application",
                message=remarks or f"Your clearance has been marked as {action} by Hostel Department.",
                application_id=application.id,
            )
            db.session.add(notification)

    audit = AuditLog(
        user_id=user_id,
        action="approve" if action == "approved" else ("reject" if action == "rejected" else "update"),
        resource_type="application_department",
        resource_id=app_dept.id,
        details={"department": "hostel", "action": action, "remarks": remarks},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Hostel clearance {action} successfully!",
    })
