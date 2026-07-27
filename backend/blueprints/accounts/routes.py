"""Accounts department routes — financial clearance management."""

from datetime import datetime, timezone, timedelta

from flask import request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required

from . import accounts_bp
from models import db
from models.user import User
from models.student import Student
from models.department import Department
from models.application import NoDuesApplication, ApplicationDepartment
from models.document import Document, DocumentVerification
from models.notification import Notification
from models.audit_log import AuditLog
from utils.decorators import department_access, validate_json
from utils.helpers import paginate_query, get_client_ip, get_user_agent


@accounts_bp.route("/dashboard")
@login_required
@department_access("accounts")
def dashboard():
    """Render accounts dashboard."""
    return render_template("accounts/dashboard.html")


@accounts_bp.route("/api/dashboard")
@jwt_required()
def dashboard_data():
    """Get accounts dashboard analytics data."""
    accounts_dept = Department.query.filter_by(role="accounts").first()
    user_id = get_jwt_identity()

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Statistics
    pending_count = ApplicationDepartment.query.filter_by(
        department_id=accounts_dept.id,
        status="pending",
    ).count()

    in_review_count = ApplicationDepartment.query.filter_by(
        department_id=accounts_dept.id,
        status="in_review",
    ).count()

    approved_today = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id == accounts_dept.id,
        ApplicationDepartment.status == "approved",
        ApplicationDepartment.processed_at >= today_start,
    ).count()

    rejected_count = ApplicationDepartment.query.filter_by(
        department_id=accounts_dept.id,
        status="rejected",
    ).count()

    total_processed = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id == accounts_dept.id,
        ApplicationDepartment.status.in_(["approved", "rejected"]),
    ).count()

    # Pending applications with full details
    pending_apps = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id == accounts_dept.id,
            ApplicationDepartment.status == "pending",
        )
        .order_by(NoDuesApplication.created_at.desc())
        .limit(10)
        .all()
    )

    pending_list = []
    for app_dept, app, student, user in pending_apps:
        pending_list.append({
            "application_id": str(app.id),
            "application_number": app.application_number,
            "student_name": user.full_name,
            "roll_number": student.roll_number,
            "course_name": student.course_name,
            "semester": student.current_semester,
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
            "category": student.category,
        })

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "pending": pending_count,
                "in_review": in_review_count,
                "approved_today": approved_today,
                "rejected": rejected_count,
                "total_processed": total_processed,
            },
            "pending_applications": pending_list,
        },
    })


@accounts_bp.route("/api/applications")
@jwt_required()
def list_applications():
    """List applications pending accounts clearance."""
    accounts_dept = Department.query.filter_by(role="accounts").first()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status_filter = request.args.get("status", "pending")

    query = (
        db.session.query(ApplicationDepartment)
        .filter(
            ApplicationDepartment.department_id == accounts_dept.id,
            ApplicationDepartment.status == status_filter,
        )
        .order_by(ApplicationDepartment.created_at.desc())
    )

    return jsonify({
        "success": True,
        "data": paginate_query(query, page=page, per_page=per_page),
    })


@accounts_bp.route("/api/process/<app_dept_id>", methods=["POST"])
@jwt_required()
@validate_json("action")
def process_application(app_dept_id):
    """Approve or reject an application."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    accounts_dept = Department.query.filter_by(role="accounts").first()

    app_dept = ApplicationDepartment.query.filter_by(
        id=app_dept_id,
        department_id=accounts_dept.id,
    ).first()

    if not app_dept:
        return jsonify({"success": False, "message": "Application not found"}), 404

    data = request.validated_data
    action = data.get("action")
    remarks = data.get("remarks", "")

    if action not in ("approved", "rejected"):
        return jsonify({"success": False, "message": "Invalid action"}), 400

    # Update status
    app_dept.status = action
    app_dept.remarks = remarks
    app_dept.processed_at = datetime.now(timezone.utc)
    app_dept.processed_by = user_id

    # Get the application
    application = NoDuesApplication.query.get(app_dept.application_id)

    if action == "approved":
        app_dept.status = "approved"
        application.current_step += 1

        # Check if all departments approved
        all_approved = all(
            ad.status == "approved"
            for ad in application.department_approvals
            if ad.is_required
        )
        if all_approved:
            application.status = "approved"
            application.completed_at = datetime.now(timezone.utc)

    else:
        app_dept.status = "rejected"
        application.status = "rejected"

    # Create notification for student
    notification = Notification(
        user_id=application.student.user_id,
        type="department_approved" if action == "approved" else "department_rejected",
        title=f"Accounts department {action} your application",
        message=remarks or f"Your application has been {action} by Accounts.",
        application_id=application.id,
        data={
            "department": "accounts",
            "action": action,
            "remarks": remarks,
        },
    )
    db.session.add(notification)

    # Create audit log
    audit = AuditLog(
        user_id=user_id,
        action="approve" if action == "approved" else "reject",
        resource_type="application_department",
        resource_id=app_dept.id,
        details={
            "application_id": str(application.id),
            "department": "accounts",
            "action": action,
            "remarks": remarks,
        },
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Application {action} successfully",
    })


@accounts_bp.route("/api/stats")
@jwt_required()
def get_stats():
    """Get accounts department statistics."""
    accounts_dept = Department.query.filter_by(role="accounts").first()

    # Daily processing stats for last 7 days
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    daily_stats = (
        db.session.query(
            db.func.date(ApplicationDepartment.processed_at).label("date"),
            db.func.count().label("count"),
            ApplicationDepartment.status,
        )
        .filter(
            ApplicationDepartment.department_id == accounts_dept.id,
            ApplicationDepartment.processed_at >= seven_days_ago,
        )
        .group_by(db.func.date(ApplicationDepartment.processed_at), ApplicationDepartment.status)
        .all()
    )

    # Monthly totals
    monthly_stats = (
        db.session.query(
            db.func.date_trunc("month", ApplicationDepartment.processed_at).label("month"),
            db.func.count().label("count"),
        )
        .filter(
            ApplicationDepartment.department_id == accounts_dept.id,
            ApplicationDepartment.processed_at >= seven_days_ago,
        )
        .group_by(db.func.date_trunc("month", ApplicationDepartment.processed_at))
        .all()
    )

    return jsonify({
        "success": True,
        "data": {
            "daily": [
                {"date": str(row.date), "count": row.count, "status": row.status}
                for row in daily_stats
            ],
            "monthly": [
                {"month": str(row.month), "count": row.count}
                for row in monthly_stats
            ],
        },
    })

