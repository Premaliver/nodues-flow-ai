"""Examination department routes — final clearance and admit card generation."""

import os
import uuid
import json
import hmac
import hashlib
from datetime import datetime, timezone

from flask import request, jsonify, render_template, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required

from . import exam_bp
from models import db
from models.user import User
from models.student import Student
from models.department import Department
from models.semester import Semester
from models.application import NoDuesApplication, ApplicationDepartment
from models.document import Document
from models.notification import Notification
from models.audit_log import AuditLog
from models.admit_card import AdmitCard
from utils.decorators import department_access, validate_json
from utils.helpers import paginate_query, get_client_ip, get_user_agent, generate_hmac_signature


@exam_bp.route("/dashboard")
@login_required
@department_access("examination")
def dashboard():
    return render_template("examination/dashboard.html")


@exam_bp.route("/api/dashboard")
@jwt_required()
def dashboard_data():
    exam_dept = Department.query.filter_by(role="examination").first()

    ready = (
        db.session.query(NoDuesApplication)
        .join(
            ApplicationDepartment,
            NoDuesApplication.id == ApplicationDepartment.application_id,
        )
        .filter(
            ApplicationDepartment.department_id == exam_dept.id,
            ApplicationDepartment.status == "pending",
            NoDuesApplication.status.in_(["approved", "in_review"]),
        )
        .count()
    )

    approved = NoDuesApplication.query.filter_by(status="approved").count()
    rejected = NoDuesApplication.query.filter_by(status="rejected").count()
    admit_cards_issued = AdmitCard.query.count()

    pending_apps = (
        db.session.query(NoDuesApplication, Student, User)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            NoDuesApplication.status == "approved",
            ~NoDuesApplication.id.in_(
                db.session.query(AdmitCard.application_id)
            ),
        )
        .order_by(NoDuesApplication.updated_at.desc())
        .limit(10)
        .all()
    )

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "ready_for_clearance": ready,
                "approved": approved,
                "rejected": rejected,
                "admit_cards_issued": admit_cards_issued,
            },
            "pending_applications": [
                {
                    "application_id": str(app.id),
                    "application_number": app.application_number,
                    "student_name": user.full_name,
                    "roll_number": student.roll_number,
                    "course_name": student.course_name,
                    "semester": student.current_semester,
                    "completed_at": app.completed_at.isoformat() if app.completed_at else None,
                }
                for app, student, user in pending_apps
            ],
        },
    })


@exam_bp.route("/api/generate-admit-card/<application_id>", methods=["POST"])
@jwt_required()
def generate_admit_card(application_id):
    """Generate admit card with HMAC-signed QR code."""
    user_id = get_jwt_identity()
    exam_dept = Department.query.filter_by(role="examination").first()

    application = NoDuesApplication.query.get(application_id)
    if not application:
        return jsonify({"success": False, "message": "Application not found"}), 404

    if application.status != "approved":
        return jsonify({"success": False, "message": "Application must be fully approved"}), 400

    existing_card = AdmitCard.query.filter_by(application_id=application.id).first()
    if existing_card:
        return jsonify({
            "success": False,
            "message": "Admit card already generated",
            "data": existing_card.to_dict(),
        }), 409

    student = Student.query.get(application.student_id)
    semester_val = Semester.query.get(application.semester_id)

    card_number = f"AC-{student.roll_number}-{semester_val.semester_number}-{uuid.uuid4().hex[:8].upper()}"

    qr_data = json.dumps({
        "card_number": card_number,
        "roll_number": student.roll_number,
        "student_name": student.student_name,
        "application_number": application.application_number,
        "semester": semester_val.semester_number,
        "academic_year": semester_val.academic_year,
        "course": student.course_name,
        "branch": student.branch,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    })

    secret_key = current_app.config["JWT_SECRET_KEY"]
    hmac_signature = generate_hmac_signature(qr_data, secret_key)

    pdf_path = os.path.join(
        current_app.config["UPLOAD_FOLDER"],
        "admit_cards",
        f"{card_number}.pdf",
    )
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    admit_card = AdmitCard(
        application_id=application.id,
        student_id=student.id,
        semester_id=semester_val.id,
        card_number=card_number,
        pdf_path=pdf_path,
        qr_code_data=qr_data,
        hmac_signature=hmac_signature,
        verification_url=f"/verify-admit-card/{card_number}",
        generated_by=user_id,
        expires_at=semester_val.end_date,
    )
    db.session.add(admit_card)

    application.current_step = application.total_steps

    exam_approval = ApplicationDepartment.query.filter_by(
        application_id=application.id,
        department_id=exam_dept.id,
    ).first()
    if exam_approval:
        exam_approval.status = "approved"
        exam_approval.processed_at = datetime.now(timezone.utc)
        exam_approval.processed_by = user_id

    notification = Notification(
        user_id=student.user_id,
        type="admit_card_generated",
        title="Your admit card is ready!",
        message=f"Your admit card ({card_number}) has been generated.",
        application_id=application.id,
        data={"card_number": card_number},
    )
    db.session.add(notification)

    audit = AuditLog(
        user_id=user_id,
        action="generate",
        resource_type="admit_card",
        resource_id=admit_card.id,
        details={"application_id": str(application.id), "card_number": card_number},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Admit card generated successfully",
        "data": admit_card.to_dict(),
    }), 201


@exam_bp.route("/api/applications")
@jwt_required()
def list_applications():
    exam_dept = Department.query.filter_by(role="examination").first()
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", "approved")

    query = (
        db.session.query(ApplicationDepartment)
        .filter(
            ApplicationDepartment.department_id == exam_dept.id,
            ApplicationDepartment.status == status_filter,
        )
        .order_by(ApplicationDepartment.created_at.desc())
    )

    return jsonify({
        "success": True,
        "data": paginate_query(query, page=page, per_page=20),
    })
