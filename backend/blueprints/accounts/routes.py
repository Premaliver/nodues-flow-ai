# type: ignore
# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false, reportUnusedImport=false
"""Accounts department routes — financial clearance management."""

from datetime import datetime, timezone, timedelta

from flask import request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required, current_user

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


def _get_authenticated_accounts_user():
    """Strictly resolve active accounts user from Flask-Login session or JWT."""
    try:
        if current_user and current_user.is_authenticated:
            u = db.session.get(User, current_user.id)
            if u and u.role in ("accounts", "super_admin"):
                return u
    except Exception:
        pass
    try:
        jwt_id = get_jwt_identity()
        if jwt_id:
            import uuid as _uuid
            try:
                uid = _uuid.UUID(str(jwt_id))
            except Exception:
                uid = jwt_id
            u = db.session.get(User, uid)
            if u and u.role == "accounts":
                return u
    except Exception:
        pass
    return None


def _get_accounts_depts(u_id=None):
    """Retrieve all accounts departments for this university with fallback."""
    accounts_depts = []
    if u_id:
        from utils.tenant_helpers import ensure_university_departments
        try:
            ensure_university_departments(u_id)
        except Exception:
            pass
        try:
            import uuid as _uuid
            u_uuid = _uuid.UUID(str(u_id))
        except Exception:
            u_uuid = u_id
        accounts_depts = Department.query.filter(
            Department.role == "accounts",
            (Department.university_id == u_uuid) | (Department.university_id == str(u_id)),
            Department.is_active == True,
        ).all()
    if not accounts_depts:
        accounts_depts = Department.query.filter_by(role="accounts", is_active=True).all()
    if not accounts_depts:
        accounts_depts = Department.query.filter_by(role="accounts").all()
    return accounts_depts


@accounts_bp.route("/dashboard")
@login_required
@department_access("accounts")
def dashboard():
    """Render accounts dashboard."""
    from utils.tenant_helpers import get_current_context_university
    univ = get_current_context_university()
    return render_template("accounts/dashboard.html", university=univ)


@accounts_bp.route("/api/dashboard")
@jwt_required(optional=True)
def dashboard_data():
    """Get accounts dashboard analytics data."""
    user = _get_authenticated_accounts_user()
    u_id = user.university_id if user else None
    
    accounts_depts = _get_accounts_depts(u_id)
    accounts_dept_ids = [d.id for d in accounts_depts]

    if not accounts_dept_ids:
        return jsonify({
            "success": True,
            "data": {
                "stats": {
                    "pending": 0, "in_review": 0,
                    "approved_today": 0, "rejected": 0,
                    "total_processed": 0,
                },
                "pending_applications": []
            }
        })

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Fetch submitted applications with pending accounts approval
    q = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id.in_(accounts_dept_ids),
            ApplicationDepartment.status == "pending",
            NoDuesApplication.status.in_(["submitted", "in_review", "partially_approved"]),
            NoDuesApplication.deleted_at.is_(None),
        )
    )
    if u_id:
        q = q.filter(
            (NoDuesApplication.university_id == u_id) | (NoDuesApplication.university_id == str(u_id))
        )

    all_pending = q.order_by(NoDuesApplication.created_at.desc()).all()

    # Sequential Gate for Accounts:
    # An application is ready for the Accountant if all prior required steps
    # (i.e. Campus Facilities with display_order < accounts.display_order) have already been approved!
    # For a Day Scholar (no campus facilities), display_order == 1, so prior_unapproved is None.
    # Therefore, Day Scholar applications appear IMMEDIATELY on the Accountant's dashboard!
    ready_applications = []
    for app_dept, app, student, stu_user in all_pending:
        prior_unapproved = ApplicationDepartment.query.filter(
            ApplicationDepartment.application_id == app.id,
            ApplicationDepartment.display_order < app_dept.display_order,
            ApplicationDepartment.is_required == True,
            ApplicationDepartment.status != "approved"
        ).first()

        if not prior_unapproved:
            ready_applications.append({
                "app_dept_id": str(app_dept.id),
                "application_id": str(app.id),
                "application_number": app.application_number,
                "student_name": stu_user.full_name,
                "roll_number": student.roll_number,
                "course_name": student.course_name,
                "branch": student.branch or "",
                "semester": student.current_semester,
                "submitted_at": app.submitted_at.isoformat() if app.submitted_at else (app.created_at.isoformat() if app.created_at else None),
                "created_at": app_dept.created_at.isoformat() if app_dept.created_at else None,
                "category": student.category,
                "status": app_dept.status,
                "remarks": app_dept.remarks or "",
            })

    in_review_count = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id.in_(accounts_dept_ids),
        ApplicationDepartment.status == "in_review",
    ).count()

    approved_today = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id.in_(accounts_dept_ids),
        ApplicationDepartment.status == "approved",
        ApplicationDepartment.processed_at >= today_start,
    ).count()

    rejected_count = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id.in_(accounts_dept_ids),
        ApplicationDepartment.status == "rejected",
    ).count()

    total_processed = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id.in_(accounts_dept_ids),
        ApplicationDepartment.status.in_(["approved", "rejected"]),
    ).count()

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "pending": len(ready_applications),
                "in_review": in_review_count,
                "approved_today": approved_today,
                "rejected": rejected_count,
                "total_processed": total_processed,
            },
            "pending_applications": ready_applications,
        },
    })


@accounts_bp.route("/api/applications")
@jwt_required(optional=True)
def list_applications():
    """List applications for accounts clearance with search and multi-status support."""
    user = _get_authenticated_accounts_user()
    u_id = user.university_id if user else None
    accounts_depts = _get_accounts_depts(u_id)
    accounts_dept_ids = [d.id for d in accounts_depts]

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    status_filter = request.args.get("status", "pending")
    search_term = request.args.get("search", "").strip()

    q = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id.in_(accounts_dept_ids),
            NoDuesApplication.deleted_at.is_(None),
        )
    )

    if status_filter == "pending":
        q = q.filter(
            ApplicationDepartment.status == "pending",
            NoDuesApplication.status.in_(["submitted", "in_review", "partially_approved"])
        )
    elif status_filter == "in_review":
        q = q.filter(ApplicationDepartment.status == "in_review")
    elif status_filter == "approved":
        q = q.filter(ApplicationDepartment.status == "approved")
    elif status_filter == "rejected":
        q = q.filter(ApplicationDepartment.status == "rejected")
    elif status_filter in ("processed", "completed"):
        q = q.filter(ApplicationDepartment.status.in_(["approved", "rejected"]))
    elif status_filter != "all":
        q = q.filter(ApplicationDepartment.status == status_filter)

    if u_id:
        q = q.filter(
            (NoDuesApplication.university_id == u_id) | (NoDuesApplication.university_id == str(u_id))
        )

    if search_term:
        term = f"%{search_term}%"
        q = q.filter(
            db.or_(
                NoDuesApplication.application_number.ilike(term),
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                Student.roll_number.ilike(term),
                Student.course_name.ilike(term),
                Student.branch.ilike(term),
            )
        )

    all_items = q.order_by(ApplicationDepartment.created_at.desc()).all()

    filtered_items = []
    for app_dept, app, student, stu_user in all_items:
        if status_filter == "pending":
            prior_unapproved = ApplicationDepartment.query.filter(
                ApplicationDepartment.application_id == app.id,
                ApplicationDepartment.display_order < app_dept.display_order,
                ApplicationDepartment.is_required == True,
                ApplicationDepartment.status != "approved"
            ).first()
            if prior_unapproved:
                continue

        filtered_items.append({
            "id": str(app_dept.id),
            "app_dept_id": str(app_dept.id),
            "application_id": str(app.id),
            "application_number": app.application_number,
            "student_name": stu_user.full_name,
            "roll_number": student.roll_number,
            "course_name": student.course_name,
            "branch": student.branch or "",
            "semester": student.current_semester,
            "created_at": app_dept.created_at.isoformat() if app_dept.created_at else None,
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else (app.created_at.isoformat() if app.created_at else None),
            "status": app_dept.status,
            "category": student.category,
            "remarks": app_dept.remarks or "",
            "processed_at": app_dept.processed_at.isoformat() if app_dept.processed_at else None,
        })

    total = len(filtered_items)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = filtered_items[start:end]

    return jsonify({
        "success": True,
        "data": {
            "items": paginated_items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if per_page else 1,
        },
    })


@accounts_bp.route("/api/process/<app_dept_id>", methods=["POST"])
@jwt_required(optional=True)
@validate_json("action")
def process_application(app_dept_id):
    """Approve or reject an application."""
    user = _get_authenticated_accounts_user()
    user_id = user.id if user else None
    if not user_id:
        jwt_id = get_jwt_identity()
        if jwt_id:
            import uuid as _uuid
            try:
                user_id = _uuid.UUID(str(jwt_id))
            except Exception:
                user_id = jwt_id

    app_dept = ApplicationDepartment.query.get(app_dept_id)
    if not app_dept:
        return jsonify({"success": False, "message": "Application clearance record not found"}), 404

    dept = Department.query.get(app_dept.department_id)
    if not dept or dept.role != "accounts":
        return jsonify({"success": False, "message": "Unauthorized: Step is not an Accounts clearance"}), 403

    data = request.validated_data
    action = data.get("action")
    remarks = data.get("remarks", "")

    if action in ("approved", "approve"):
        action = "approved"
    elif action in ("rejected", "reject"):
        action = "rejected"
    else:
        return jsonify({"success": False, "message": "Invalid action"}), 400

    if action == "approved":
        # Ensure all preceding facility steps are approved first
        prior_unapproved = ApplicationDepartment.query.filter(
            ApplicationDepartment.application_id == app_dept.application_id,
            ApplicationDepartment.display_order < app_dept.display_order,
            ApplicationDepartment.is_required == True,
            ApplicationDepartment.status != "approved"
        ).all()
        if prior_unapproved:
            pending_names = [p.department.name if p.department else f"Step #{p.display_order}" for p in prior_unapproved]
            return jsonify({
                "success": False,
                "message": f"Cannot approve yet. Preceding facilities verification pending: {', '.join(pending_names)}"
            }), 400

    # Update status
    app_dept.status = action
    app_dept.remarks = remarks
    app_dept.processed_at = datetime.now(timezone.utc)
    app_dept.processed_by = user_id

    # Get the application
    application = NoDuesApplication.query.get(app_dept.application_id)

    if action == "approved":
        app_dept.status = "approved"
        application.accounts_verified = True
        application.accounts_verified_at = datetime.now(timezone.utc)
        application.current_step = ApplicationDepartment.query.filter_by(
            application_id=application.id,
            status="approved",
        ).count()
        if application.status == "submitted":
            application.status = "in_review"

        # Sequential Workflow Progression:
        # Notify HOD department staff that financial clearance is complete and the application is now ready for HOD review!
        try:
            hod_users = []
            if application.university_id:
                hod_users = User.query.filter_by(role="hod", university_id=application.university_id).all()
            if not hod_users:
                hod_users = User.query.filter_by(role="hod").all()
            for hod_u in hod_users:
                notif = Notification(
                    user_id=hod_u.id,
                    type="application_submitted",
                    title=f"Application #{application.application_number} ready for HOD sign-off",
                    message=f"Financial clearance has been approved by Accounts. Academic verification is now pending on your desk.",
                    application_id=application.id,
                )
                db.session.add(notif)
        except Exception:
            pass
    else:
        app_dept.status = "rejected"
        application.status = "rejected"

    # Create notification for student
    try:
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
    except Exception:
        pass

    # Create audit log
    try:
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
    except Exception:
        pass

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

