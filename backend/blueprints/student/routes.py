"""Student dashboard routes."""

import os
import uuid
from datetime import datetime, timezone

from flask import request, jsonify, render_template, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required, current_user

from . import student_bp
from models import db
from models.user import User
from models.student import Student
from models.department import Department
from models.semester import Semester
from models.application import NoDuesApplication, ApplicationDepartment
from models.document import Document, DocumentVerification
from models.notification import Notification
from models.audit_log import AuditLog
from models.admit_card import AdmitCard
from models.workflow import WorkflowConfig
from utils.decorators import student_only, validate_json
from utils.helpers import (
    paginate_query, get_client_ip, get_user_agent,
    allowed_file, secure_file_path, calculate_file_hash,
)


@student_bp.route("/dashboard")
@login_required
@student_only
def dashboard():
    """Render student dashboard page."""
    return render_template("student/dashboard.html")


@student_bp.route("/api/dashboard")
@jwt_required()
def dashboard_data():
    """Get student dashboard data."""
    user_id = get_jwt_identity()
    student = Student.query.filter_by(user_id=user_id).first()
    if not student:
        return jsonify({"success": False, "message": "Student profile not found"}), 404

    # Get current semester
    current_semester = Semester.query.filter_by(is_current=True).first()

    # Get applications
    applications = NoDuesApplication.query.filter_by(
        student_id=student.id
    ).order_by(NoDuesApplication.created_at.desc()).all()

    # Get recent notifications
    recent_notifications = Notification.query.filter_by(
        user_id=user_id, is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()

    # Build response
    data = {
        "student": student.to_dict(),
        "current_semester": current_semester.to_dict() if current_semester else None,
        "applications": [app.to_dict() for app in applications],
        "application_count": len(applications),
        "pending_count": sum(1 for a in applications if a.status == "submitted"),
        "approved_count": sum(1 for a in applications if a.status == "approved"),
        "rejected_count": sum(1 for a in applications if a.status == "rejected"),
        "notifications": [n.to_dict() for n in recent_notifications],
        "unread_notification_count": len(recent_notifications),
    }

    # Add current application progress if exists
    active_app = next((a for a in applications if a.status in ("draft", "submitted", "in_review")), None)
    if active_app:
        data["active_application"] = active_app.to_dict()
        data["department_approvals"] = [
            ad.to_dict() for ad in active_app.department_approvals
        ]

    return jsonify({"success": True, "data": data})


@student_bp.route("/api/apply", methods=["POST"])
@jwt_required()
def create_application():
    """Create a new no-dues application."""
    user_id = get_jwt_identity()
    student = Student.query.filter_by(user_id=user_id).first()
    if not student:
        return jsonify({"success": False, "message": "Student profile not found"}), 404

    semester = Semester.query.filter_by(is_current=True, is_clearance_open=True).first()
    if not semester:
        return jsonify({"success": False, "message": "Clearance is not currently open"}), 400

    # Check for existing active application
    existing = NoDuesApplication.query.filter(
        NoDuesApplication.student_id == student.id,
        NoDuesApplication.semester_id == semester.id,
        NoDuesApplication.status.in_(["draft", "submitted", "in_review"]),
        NoDuesApplication.deleted_at.is_(None),
    ).first()

    if existing:
        return jsonify({
            "success": False,
            "message": "You already have an active application",
            "data": {"application": existing.to_dict()},
        }), 409

    # Determine workflow based on student category
    workflow_steps = WorkflowConfig.query.filter_by(
        category=student.category, is_active=True
    ).order_by(WorkflowConfig.step_order).all()

    if not workflow_steps:
        return jsonify({
            "success": False,
            "message": "No workflow configured for your category. Contact administration.",
        }), 400

    # Create application
    application = NoDuesApplication(
        student_id=student.id,
        semester_id=semester.id,
        category=student.category,
        total_steps=len([w for w in workflow_steps if w.is_required]),
        status="draft",
    )
    db.session.add(application)
    db.session.flush()

    # Create department approval entries
    for step in workflow_steps:
        dept_approval = ApplicationDepartment(
            application_id=application.id,
            department_id=step.department_id,
            display_order=step.step_order,
            is_required=step.is_required,
            status="pending",
        )
        db.session.add(dept_approval)

    # Create audit log
    audit = AuditLog(
        user_id=user_id,
        action="create",
        resource_type="application",
        resource_id=application.id,
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Application created successfully",
        "data": {"application": application.to_dict()},
    }), 201


@student_bp.route("/api/application/<app_id>")
@jwt_required()
def get_application(app_id):
    """Get application details with all approvals and documents."""
    user_id = get_jwt_identity()
    student = Student.query.filter_by(user_id=user_id).first()

    application = NoDuesApplication.query.filter_by(
        id=app_id, student_id=student.id
    ).first()

    if not application:
        return jsonify({"success": False, "message": "Application not found"}), 404

    documents = Document.query.filter_by(application_id=application.id).all()
    admit_card = AdmitCard.query.filter_by(application_id=application.id).first()

    return jsonify({
        "success": True,
        "data": {
            "application": application.to_dict(),
            "department_approvals": [ad.to_dict() for ad in application.department_approvals],
            "documents": [doc.to_dict() for doc in documents],
            "admit_card": admit_card.to_dict() if admit_card else None,
        },
    })


@student_bp.route("/api/submit/<app_id>", methods=["POST"])
@jwt_required()
def submit_application(app_id):
    """Submit application for processing."""
    user_id = get_jwt_identity()
    student = Student.query.filter_by(user_id=user_id).first()

    application = NoDuesApplication.query.filter_by(
        id=app_id, student_id=student.id
    ).first()

    if not application:
        return jsonify({"success": False, "message": "Application not found"}), 404

    if not application.can_submit():
        return jsonify({"success": False, "message": "Application cannot be submitted"}), 400

    application.status = "submitted"
    application.submitted_at = datetime.now(timezone.utc)

    # Create audit log
    audit = AuditLog(
        user_id=user_id,
        action="update",
        resource_type="application",
        resource_id=application.id,
        details={"action": "submit"},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Application submitted successfully",
        "data": {"application": application.to_dict()},
    })


@student_bp.route("/api/upload-document/<app_id>", methods=["POST"])
@jwt_required()
def upload_document(app_id):
    """Upload a document/receipt for an application."""
    user_id = get_jwt_identity()
    student = Student.query.filter_by(user_id=user_id).first()

    application = NoDuesApplication.query.filter_by(
        id=app_id, student_id=student.id
    ).first()

    if not application:
        return jsonify({"success": False, "message": "Application not found"}), 404

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No file selected"}), 400

    # Validate file
    allowed_ext = current_app.config.get("ALLOWED_EXTENSIONS", {"pdf", "png", "jpg", "jpeg", "webp"})
    if not allowed_file(file.filename, allowed_ext):
        return jsonify({"success": False, "message": "File type not allowed"}), 400

    # Save file
    document_type = request.form.get("document_type", "other")
    file_path = secure_file_path(
        current_app.config["UPLOAD_FOLDER"],
        f"applications/{app_id}",
        file.filename,
    )
    file.save(file_path)

    # Calculate hash for duplicate detection
    file_hash = calculate_file_hash(file_path)

    # Create document record
    document = Document(
        application_id=application.id,
        document_type=document_type,
        file_name=file.filename,
        file_path=file_path,
        file_size=os.path.getsize(file_path),
        mime_type=file.content_type,
        file_hash=file_hash,
        uploaded_by=user_id,
        status="pending",
    )
    db.session.add(document)

    # Create audit log
    audit = AuditLog(
        user_id=user_id,
        action="upload",
        resource_type="document",
        details={"type": document_type, "file_name": file.filename},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Document uploaded successfully",
        "data": {"document": document.to_dict()},
    }), 201


@student_bp.route("/api/notifications")
@jwt_required()
def get_notifications():
    """Get student notifications."""
    user_id = get_jwt_identity()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Notification.query.filter_by(user_id=user_id).order_by(
        Notification.created_at.desc()
    )

    return jsonify({
        "success": True,
        "data": paginate_query(query, page=page, per_page=per_page),
    })

