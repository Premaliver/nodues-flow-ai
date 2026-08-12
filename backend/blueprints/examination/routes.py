"""Examination department routes — final clearance and admit card generation."""

import os
import io
import uuid
import json
import hmac
import hashlib
from datetime import datetime, timezone

from flask import request, jsonify, render_template, current_app, send_file
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


def _get_exam_dept():
    """Helper to fetch the examination department."""
    return Department.query.filter_by(role="examination").first()


def _is_preceding_clearance_complete(application_id, exam_dept_id) -> bool:
    """Verify that all department clearances prior to Examination are approved."""
    approvals = ApplicationDepartment.query.filter_by(application_id=application_id).all()
    exam_app = next((a for a in approvals if a.department_id == exam_dept_id), None)
    if not exam_app:
        # If no explicit examination step, check that all required steps are approved
        return all(a.status == "approved" for a in approvals if a.is_required)

    preceding = [a for a in approvals if a.is_required and a.display_order < exam_app.display_order]
    return all(a.status == "approved" for a in preceding)


@exam_bp.route("/dashboard")
@login_required
@department_access("examination")
def dashboard():
    return render_template("examination/dashboard.html")


@exam_bp.route("/api/dashboard")
@jwt_required()
def dashboard_data():
    """Get examination dashboard data — applications ready for admit cards."""
    exam_dept = _get_exam_dept()

    # Applications pending examination clearance (ready to generate admit card)
    ready_apps = (
        db.session.query(ApplicationDepartment, NoDuesApplication, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id == exam_dept.id,
            ApplicationDepartment.status == "pending",
            NoDuesApplication.status.in_(["submitted", "in_review"]),
            NoDuesApplication.deleted_at.is_(None),
        )
        .order_by(NoDuesApplication.created_at.desc())
        .all()
    )

    ready_list = []
    for app_dept, app, student, user in ready_apps:
        # Strictly verify that all preceding departments (Hostel/Mess/Transport/Scholarship/HOD/Accounts) have APPROVED
        if _is_preceding_clearance_complete(app.id, exam_dept.id):
            ready_list.append({
                "app_dept_id": str(app_dept.id),
                "application_id": str(app.id),
                "application_number": app.application_number,
                "student_name": user.full_name,
                "roll_number": student.roll_number,
                "course_name": student.course_name,
                "branch": student.branch,
                "semester": student.current_semester,
                "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
                "completed_at": app.completed_at.isoformat() if app.completed_at else None,
            })

    approved = NoDuesApplication.query.filter_by(
        status="approved", deleted_at=None
    ).count()
    rejected = NoDuesApplication.query.filter_by(
        status="rejected", deleted_at=None
    ).count()
    admit_cards_issued = AdmitCard.query.count()

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "ready_for_clearance": len(ready_list),
                "approved": approved,
                "rejected": rejected,
                "admit_cards_issued": admit_cards_issued,
            },
            "pending_applications": ready_list,
        },
    })


@exam_bp.route("/api/applications")
@jwt_required()
def list_applications():
    """List approved applications for the examination department."""
    exam_dept = _get_exam_dept()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status_filter = request.args.get("status", "approved")

    query = (
        db.session.query(ApplicationDepartment, Student, User)
        .join(NoDuesApplication, ApplicationDepartment.application_id == NoDuesApplication.id)
        .join(Student, NoDuesApplication.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .filter(
            ApplicationDepartment.department_id == exam_dept.id,
        )
        .order_by(ApplicationDepartment.created_at.desc())
    )

    if status_filter:
        query = query.filter(ApplicationDepartment.status == status_filter)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for app_dept, student, user in pagination.items:
        app = NoDuesApplication.query.get(app_dept.application_id)
        items.append({
            "id": str(app_dept.id),
            "app_dept_id": str(app_dept.id),
            "application_id": str(app_dept.application_id),
            "application_number": app.application_number if app else "N/A",
            "student_name": user.full_name,
            "roll_number": student.roll_number,
            "course_name": student.course_name,
            "semester": student.current_semester,
            "status": app_dept.status,
            "submitted_at": app.submitted_at.isoformat() if app and app.submitted_at else None,
            "created_at": app_dept.created_at.isoformat() if app_dept.created_at else None,
        })

    return jsonify({
        "success": True,
        "data": {
            "items": items,
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    })


@exam_bp.route("/api/admit-cards")
@jwt_required()
def list_admit_cards():
    """List all issued admit cards."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = (
        db.session.query(AdmitCard, Student, User)
        .join(Student, AdmitCard.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .order_by(AdmitCard.created_at.desc())
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for card, student, user in pagination.items:
        items.append({
            "id": str(card.id),
            "card_number": card.card_number,
            "application_id": str(card.application_id),
            "student_name": user.full_name,
            "roll_number": student.roll_number,
            "course_name": student.course_name,
            "semester": student.current_semester,
            "is_downloaded": card.is_downloaded,
            "download_count": card.download_count,
            "created_at": card.created_at.isoformat() if card.created_at else None,
            "expires_at": card.expires_at.isoformat() if card.expires_at else None,
            "verification_url": card.verification_url,
            "download_url": f"/examination/api/admit-card/{card.card_number}/pdf",
        })

    return jsonify({
        "success": True,
        "data": {
            "items": items,
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    })


def _generate_admit_card_pdf(card: AdmitCard, student: Student, semester: Semester,
                             application: NoDuesApplication, user: User) -> str:
    """Generate a real PDF admit card with QR code and return the file path."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    )
    from reportlab.lib.enums import TA_CENTER
    import qrcode

    # Build QR code image in memory
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=2,
    )
    qr.add_data(card.qr_code_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Prepare upload folder
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    admit_dir = os.path.join(upload_folder, "admit_cards")
    os.makedirs(admit_dir, exist_ok=True)

    pdf_path = os.path.join(admit_dir, f"{card.card_number}.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=20,
        textColor=colors.HexColor("#1a3a5c"),
        spaceAfter=4,
    )
    center_style = ParagraphStyle(
        "CenterStyle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=11,
    )
    label_style = ParagraphStyle(
        "LabelStyle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#555555"),
    )
    value_style = ParagraphStyle(
        "ValueStyle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#111111"),
    )

    university = current_app.config.get("UNIVERSITY_NAME", "Rayat Bahra University")
    app_name = current_app.config.get("APP_NAME", "Smart NoDues AI")

    story = []

    # Header
    story.append(Paragraph(university, title_style))
    story.append(Paragraph(f"<b>OFFICIAL EXAMINATION HALL TICKET / ADMIT CARD</b>", center_style))
    story.append(Paragraph(f"Verified & Issued via {app_name}", center_style))
    story.append(Spacer(1, 4 * mm))

    # Verification Badge Banner
    clearance_banner = Table(
        [[Paragraph("<font color='#065f46'><b>✓ ALL DEPARTMENTS NO-DUES CLEARANCE VERIFIED</b></font>", center_style)]],
        colWidths=[180 * mm],
    )
    clearance_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#d1fae5")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#059669")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(clearance_banner)
    story.append(Spacer(1, 4 * mm))

    # Card number banner
    card_banner = Table(
        [[Paragraph(f"<b>Card No:</b> {card.card_number}", center_style),
          Paragraph(f"<b>Semester:</b> {semester.semester_name} ({semester.academic_year})", center_style)]],
        colWidths=[90 * mm, 90 * mm],
    )
    card_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef3f8")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#1a3a5c")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c5d3e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(card_banner)
    story.append(Spacer(1, 6 * mm))

    # Student details
    details = [
        [Paragraph("<b>Student Name</b>", label_style), Paragraph(user.full_name, value_style)],
        [Paragraph("<b>Roll Number</b>", label_style), Paragraph(student.roll_number, value_style)],
        [Paragraph("<b>Enrollment No</b>", label_style), Paragraph(student.enrollment_number, value_style)],
        [Paragraph("<b>Course</b>", label_style), Paragraph(student.course_name, value_style)],
        [Paragraph("<b>Branch</b>", label_style), Paragraph(student.branch, value_style)],
        [Paragraph("<b>Current Semester</b>", label_style), Paragraph(str(student.current_semester), value_style)],
        [Paragraph("<b>Application No</b>", label_style), Paragraph(application.application_number, value_style)],
        [Paragraph("<b>Batch Year</b>", label_style), Paragraph(student.batch_year, value_style)],
        [Paragraph("<b>Father's Name</b>", label_style), Paragraph(student.father_name or "-", value_style)],
    ]

    details_table = Table(details, colWidths=[45 * mm, 135 * mm])
    details_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#1a3a5c")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c5d3e0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f8fb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 6 * mm))

    # QR code + expiry
    qr_table = Table(
        [[Image(qr_buffer, width=45 * mm, height=45 * mm),
          Paragraph(f"<b>Validity:</b> {card.expires_at.strftime('%d %b %Y') if card.expires_at else 'End of semester'}<br/><br/>"
                    f"<b>Verify at:</b><br/>{card.verification_url}<br/><br/>"
                    f"<font color='#888888'>Scan the QR code to verify the authenticity of this admit card.</font>", value_style)]],
        colWidths=[60 * mm, 120 * mm],
    )
    qr_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#1a3a5c")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(qr_table)
    story.append(Spacer(1, 8 * mm))

    # Signature footer
    sig_table = Table(
        [[Paragraph("", value_style), Paragraph("", value_style)],
         [Paragraph("________________________", center_style),
          Paragraph("________________________", center_style)],
         [Paragraph("Student Signature", center_style),
          Paragraph("Controller of Examinations", center_style)]],
        colWidths=[90 * mm, 90 * mm],
    )
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sig_table)

    doc.build(story)
    return pdf_path


@exam_bp.route("/api/generate-admit-card/<application_id>", methods=["POST"])
@jwt_required()
def generate_admit_card(application_id):
    """Generate admit card with HMAC-signed QR code and a real downloadable PDF."""
    user_id = get_jwt_identity()
    exam_dept = _get_exam_dept()

    application = NoDuesApplication.query.get(application_id)
    if not application:
        return jsonify({"success": False, "message": "Application not found"}), 404

    existing_card = AdmitCard.query.filter_by(application_id=application.id).first()
    if existing_card:
        return jsonify({
            "success": False,
            "message": "Admit card already generated",
            "data": existing_card.to_dict(),
        }), 409

    # Ensure all preceding department clearances (Hostel, Mess, Transport, Scholarship, HOD, Accounts) are approved
    if not _is_preceding_clearance_complete(application.id, exam_dept.id if exam_dept else None):
        return jsonify({
            "success": False,
            "message": "Cannot generate admit card. Preceding department clearances are still pending or rejected.",
        }), 400

    # Find the examination approval row for this application
    exam_approval = ApplicationDepartment.query.filter_by(
        application_id=application.id,
        department_id=exam_dept.id if exam_dept else None,
    ).first()

    # If there is no explicit examination step, allow generation if the application
    # has no pending required departments.
    if not exam_approval:
        pending_required = [
            ad for ad in application.department_approvals
            if ad.is_required and ad.status in ("pending", "in_review")
        ]
        if pending_required:
            return jsonify({
                "success": False,
                "message": "Application has pending department approvals",
            }), 400

    student = Student.query.get(application.student_id)
    if not student:
        return jsonify({"success": False, "message": "Student not found"}), 404

    semester = Semester.query.get(application.semester_id)
    if not semester:
        return jsonify({"success": False, "message": "Semester not found"}), 404

    student_user = User.query.get(student.user_id)

    card_number = f"AC-{student.roll_number}-{semester.semester_number}-{uuid.uuid4().hex[:8].upper()}"

    qr_data = json.dumps({
        "card_number": card_number,
        "roll_number": student.roll_number,
        "student_name": student_user.full_name if student_user else student.student_name,
        "application_number": application.application_number,
        "semester": semester.semester_number,
        "academic_year": semester.academic_year,
        "course": student.course_name,
        "branch": student.branch,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    })

    secret_key = current_app.config["JWT_SECRET_KEY"]
    hmac_signature = generate_hmac_signature(qr_data, secret_key)

    # Create the AdmitCard record (flush to get id)
    admit_card = AdmitCard(
        application_id=application.id,
        student_id=student.id,
        semester_id=semester.id,
        card_number=card_number,
        pdf_path="",  # placeholder, updated after PDF generation
        qr_code_data=qr_data,
        hmac_signature=hmac_signature,
        verification_url=f"/verify-admit-card/{card_number}",
        generated_by=user_id,
        expires_at=semester.end_date,
    )
    db.session.add(admit_card)
    db.session.flush()

    # Generate the actual PDF
    try:
        pdf_path = _generate_admit_card_pdf(
            admit_card, student, semester, application, student_user or student.user
        )
    except Exception as e:
        current_app.logger.error("Admit card PDF generation failed: %s", str(e))
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Failed to generate admit card PDF: {str(e)}",
        }), 500

    admit_card.pdf_path = pdf_path

    # Mark exam approval as approved
    if exam_approval:
        exam_approval.status = "approved"
        exam_approval.processed_at = datetime.now(timezone.utc)
        exam_approval.processed_by = user_id

    # Mark application as approved/completed
    application.status = "approved"
    application.completed_at = datetime.now(timezone.utc)
    application.current_step = application.total_steps

    # Notify student
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
        "data": {
            **admit_card.to_dict(),
            "student_name": student_user.full_name if student_user else student.student_name,
            "roll_number": student.roll_number,
            "download_url": f"/examination/api/admit-card/{card_number}/pdf",
        },
    }), 201


@exam_bp.route("/api/admit-card/<card_number>/pdf")
def download_admit_card(card_number):
    """Download/view the generated admit card PDF.
    
    Serves the PDF inline for viewing/downloading in browser tabs.
    """
    card = AdmitCard.query.filter_by(card_number=card_number).first()
    if not card:
        return jsonify({"success": False, "message": "Admit card not found"}), 404

    # If physical file missing, attempt on-the-fly PDF regeneration
    if not card.pdf_path or not os.path.exists(card.pdf_path):
        try:
            student = Student.query.get(card.student_id)
            semester = Semester.query.get(card.semester_id)
            application = NoDuesApplication.query.get(card.application_id)
            if student and semester and application:
                student_user = User.query.get(student.user_id) if student else None
                pdf_path = _generate_admit_card_pdf(
                    card, student, semester, application, student_user or student.user
                )
                card.pdf_path = pdf_path
                db.session.commit()
        except Exception as e:
            current_app.logger.error("Auto admit card PDF generation failed: %s", str(e))

    if not card.pdf_path or not os.path.exists(card.pdf_path):
        return jsonify({"success": False, "message": "Admit card PDF file not found"}), 404

    # Track download
    card.is_downloaded = True
    card.downloaded_at = datetime.now(timezone.utc)
    card.download_count = (card.download_count or 0) + 1
    db.session.commit()

    return send_file(
        card.pdf_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"{card.card_number}.pdf",
    )
