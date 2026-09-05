# type: ignore
# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false, reportUnusedImport=false
"""HOD department routes — academic clearance management."""

from datetime import datetime, timezone

from flask import request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required, current_user

from . import hod_bp
from models import db
from models.department import Department
from models.application import ApplicationDepartment, NoDuesApplication
from models.student import Student
from models.user import User
from models.notification import Notification
from models.audit_log import AuditLog
from utils.decorators import department_access, validate_json
from utils.helpers import get_client_ip, get_user_agent


def _get_authenticated_hod_user():
    """Strictly resolve the active HOD user from session or JWT."""
    try:
        if current_user and current_user.is_authenticated:
            u = db.session.get(User, current_user.id)
            if u and u.role in ("hod", "super_admin"):
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
            if u and u.role == "hod":
                return u
    except Exception:
        pass
    return None


@hod_bp.route("/dashboard")
@login_required
@department_access("hod")
def dashboard():
    from utils.tenant_helpers import get_current_context_university
    univ = get_current_context_university()
    return render_template("hod/dashboard.html", university=univ)


@hod_bp.route("/api/dashboard")
@jwt_required(optional=True)
def dashboard_data():
    user = _get_authenticated_hod_user()
    u_id = user.university_id if user else None

    hod_depts = []
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
        hod_depts = Department.query.filter(
            Department.role == "hod",
            (Department.university_id == u_uuid) | (Department.university_id == str(u_id)),
            Department.is_active == True,
        ).all()
    if not hod_depts:
        hod_depts = Department.query.filter_by(role="hod", is_active=True).all()
    if not hod_depts:
        hod_depts = Department.query.filter_by(role="hod").all()

    hod_dept_ids = [d.id for d in hod_depts]

    if not hod_dept_ids:
        return jsonify({
            "success": True,
            "data": {
                "stats": {"pending": 0, "approved": 0, "rejected": 0, "total": 0},
                "pending_applications": []
            }
        })

    approved = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id.in_(hod_dept_ids),
        ApplicationDepartment.status == "approved"
    ).count()
    rejected = ApplicationDepartment.query.filter(
        ApplicationDepartment.department_id.in_(hod_dept_ids),
        ApplicationDepartment.status == "rejected"
    ).count()

    query = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id.in_(hod_dept_ids),
            ApplicationDepartment.status == "pending",
            NoDuesApplication.status.in_(["submitted", "in_review", "partially_approved"]),
            NoDuesApplication.deleted_at.is_(None),
        )
    )
    if u_id:
        query = query.filter(
            (NoDuesApplication.university_id == u_id) | (NoDuesApplication.university_id == str(u_id))
        )

    all_pending = (
        query
        .order_by(NoDuesApplication.created_at.desc())
        .limit(30)
        .all()
    )

    # Sequential Gate for HOD:
    # An application is ONLY ready for Academic HOD review once ALL preceding steps
    # (specifically Accounts & Finance, plus any Campus Facilities) ARE APPROVED!
    # If Accounts is still pending, the application stays with Accounts and does NOT show on HOD dashboard.
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
                "application_id": str(app.id),
                "app_dept_id": str(app_dept.id),
                "application_number": app.application_number,
                "student_name": stu_user.full_name,
                "roll_number": student.roll_number,
                "course_name": student.course_name,
                "branch": student.branch,
                "semester": student.current_semester,
                "submitted_at": app.submitted_at.isoformat() if app.submitted_at else (app.created_at.isoformat() if app.created_at else None),
                "category": student.category,
            })

    pending_count = len(ready_applications)

    return jsonify({
        "success": True,
        "data": {
            "stats": {"pending": pending_count, "approved": approved, "rejected": rejected, "total": pending_count + approved + rejected},
            "pending_applications": ready_applications,
        },
    })


@hod_bp.route("/api/process/<app_dept_id>", methods=["POST"])
@jwt_required(optional=True)
@validate_json("action")
def process_application(app_dept_id):
    user = _get_authenticated_hod_user()
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
    if not dept or dept.role != "hod":
        return jsonify({"success": False, "message": "Unauthorized: Step is not an Academic HOD clearance"}), 403

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
        # Ensure all preceding steps (Facilities and Accounts) are approved first
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
                "message": f"Cannot approve yet. Preceding departmental verification pending: {', '.join(pending_names)}"
            }), 400

    app_dept.status = action
    app_dept.remarks = remarks
    app_dept.processed_at = datetime.now(timezone.utc)
    app_dept.processed_by = user_id

    application = NoDuesApplication.query.get(app_dept.application_id)
    if action == "approved":
        application.hod_approved = True
        application.hod_approved_at = datetime.now(timezone.utc)
        application.current_step = ApplicationDepartment.query.filter_by(
            application_id=application.id,
            status="approved",
        ).count()
        if application.status == "submitted":
            application.status = "in_review"

        # Sequential Workflow Progression:
        # Notify Examination department staff that HOD clearance is complete and Admit Card can be released!
        try:
            exam_users = []
            if application.university_id:
                exam_users = User.query.filter_by(role="examination", university_id=application.university_id).all()
            if not exam_users:
                exam_users = User.query.filter_by(role="examination").all()
            for ex_u in exam_users:
                notif = Notification(
                    user_id=ex_u.id,
                    type="application_submitted",
                    title=f"Application #{application.application_number} ready for Admit Card Release",
                    message=f"HOD academic clearance has been approved. Preceding clearances are complete. Ready for cryptographic Admit Card generation.",
                    application_id=application.id,
                )
                db.session.add(notif)
        except Exception:
            pass
    else:
        app_dept.status = "rejected"
        application.status = "rejected"

    try:
        notification = Notification(
            user_id=application.student.user_id,
            type="department_approved" if action == "approved" else "department_rejected",
            title=f"HOD {action} your application",
            message=remarks or f"Academic clearance has been {action} by HOD.",
            application_id=application.id,
        )
        db.session.add(notification)
    except Exception:
        pass

    try:
        audit = AuditLog(
            user_id=user_id,
            action="approve" if action == "approved" else "reject",
            resource_type="application_department",
            resource_id=app_dept.id,
            details={"application_id": str(application.id), "department": "hod", "action": action, "remarks": remarks},
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
    except Exception:
        pass

    db.session.commit()

    return jsonify({"success": True, "message": f"Application {action} successfully"})
