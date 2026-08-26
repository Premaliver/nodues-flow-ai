# type: ignore
# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false, reportUnusedImport=false
"""Student dashboard routes — enhanced application workflow."""

import os
import hashlib
from datetime import datetime, timezone

from flask import request, jsonify, render_template, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_login import login_required, current_user

from . import student_bp
try:
    from models import db
    from models.user import User
    from models.student import Student
    from models.course import Course, DigitalSignature
    from models.department import Department
    from models.semester import Semester
    from models.application import NoDuesApplication, ApplicationDepartment
    from models.document import Document
    from models.notification import Notification
    from models.audit_log import AuditLog
    from models.admit_card import AdmitCard
    from models.feedback import Feedback
    from utils.decorators import student_only
    from utils.helpers import (
        paginate_query, get_client_ip, get_user_agent,
        allowed_file, secure_file_path, calculate_file_hash,
    )
except ImportError:
    from backend.models import db
    from backend.models.user import User
    from backend.models.student import Student
    from backend.models.course import Course, DigitalSignature
    from backend.models.department import Department
    from backend.models.semester import Semester
    from backend.models.application import NoDuesApplication, ApplicationDepartment
    from backend.models.document import Document
    from backend.models.notification import Notification
    from backend.models.audit_log import AuditLog
    from backend.models.admit_card import AdmitCard
    from backend.models.feedback import Feedback
    from backend.utils.decorators import student_only
    from backend.utils.helpers import (
        paginate_query, get_client_ip, get_user_agent,
        allowed_file, secure_file_path, calculate_file_hash,
    )


@student_bp.route("/dashboard")
@login_required
@student_only
def dashboard():
    """Render student dashboard page."""
    univ = None
    if current_user and current_user.is_authenticated:
        user = User.query.get(current_user.id)
        if user and user.university_id:
            from models.university import UniversityTenant
            univ = UniversityTenant.query.get(user.university_id)
    return render_template("student/dashboard.html", university=univ)


@student_bp.route("/apply")
@login_required
@student_only
def apply_page():
    """Render student application form page with pre-fetched student data for instant loading."""
    student_data = {}
    univ = None
    if current_user and current_user.is_authenticated:
        user = User.query.get(current_user.id)
        if user:
            student_data = user.to_dict()
            student_prof = Student.query.filter_by(user_id=user.id).first()
            if student_prof:
                student_data.update(student_prof.to_dict())
            if user.university_id:
                from models.university import UniversityTenant
                univ = UniversityTenant.query.get(user.university_id)
                if univ:
                    student_data["university"] = univ.to_dict()
    return render_template("student/apply.html", student_data=student_data, university=univ)




def _get_authenticated_student_user():
    """Strictly resolve the active student user, preventing role leakage from stale tokens."""
    # 1. Check Flask-Login session first if active and role is student
    if current_user and current_user.is_authenticated and current_user.role == "student":
        u = User.query.get(current_user.id)
        if u and u.role == "student":
            return u

    # 2. Check JWT Identity
    jwt_id = get_jwt_identity()
    if jwt_id:
        jwt_user = User.query.get(jwt_id)
        if jwt_user and jwt_user.role == "student":
            return jwt_user

    # 3. Fallback to session user if role is student
    if current_user and current_user.is_authenticated and current_user.role == "student":
        return User.query.get(current_user.id)

    return None


@student_bp.route("/api/profile", methods=["GET", "PUT"])
@jwt_required(optional=True)
def get_profile():
    """Get or update student profile with full details."""
    user = _get_authenticated_student_user()
    if not user:
        return jsonify({"success": False, "message": "Access restricted. Active student login required."}), 403

    student_prof = Student.query.filter_by(user_id=user.id).first()
    if not student_prof:
        # Auto-create linked student profile record if missing
        full_name = f"{user.first_name} {user.last_name or ''}".strip()
        student_prof = Student(
            user_id=user.id,
            student_name=full_name or "Student",
            university_id=user.university_id,
            category="day_scholar",
            current_semester=1,
        )
        db.session.add(student_prof)
        db.session.commit()

    # Handle Profile Update
    if request.method == "PUT":
        req_data = request.get_json() or {}
        
        # 1. Update User basic info
        full_name = (req_data.get("full_name") or req_data.get("student_name") or "").strip()
        if full_name:
            parts = full_name.split(" ", 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""

        if "phone" in req_data:
            user.phone = req_data.get("phone", "").strip() or None

        # 2. Update Student Profile info
        if student_prof:
            if full_name:
                student_prof.student_name = full_name
            if "father_name" in req_data:
                student_prof.father_name = req_data.get("father_name", "").strip() or None
            if "mother_name" in req_data:
                student_prof.mother_name = req_data.get("mother_name", "").strip() or None
            if "guardian_phone" in req_data:
                student_prof.guardian_phone = req_data.get("guardian_phone", "").strip() or None
            elif "father_phone" in req_data:
                student_prof.guardian_phone = req_data.get("father_phone", "").strip() or None
            if "category" in req_data and req_data.get("category"):
                student_prof.category = req_data.get("category")
            if "course_name" in req_data and req_data.get("course_name"):
                student_prof.course_name = req_data.get("course_name").strip()
            if "branch" in req_data and req_data.get("branch"):
                student_prof.branch = req_data.get("branch").strip()
                from models.department import Department
                acad = Department.query.filter(Department.name.ilike(f"%{student_prof.branch}%")).first()
                if acad:
                    student_prof.academic_department_id = acad.id
            if "city" in req_data:
                student_prof.city = req_data.get("city", "").strip() or None
            if "state" in req_data:
                student_prof.state = req_data.get("state", "").strip() or None
            if "current_semester" in req_data and req_data.get("current_semester"):
                try:
                    student_prof.current_semester = int(req_data.get("current_semester"))
                except (ValueError, TypeError):
                    pass

        # 3. Create Audit Log
        audit = AuditLog(
            user_id=user.id,
            action="update",
            resource_type="student_profile",
            resource_id=student_prof.id if student_prof else user.id,
            details={"updated_fields": list(req_data.keys())},
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
        db.session.commit()

        data = user.to_dict()
        if student_prof:
            data.update(student_prof.to_dict())
        return jsonify({
            "success": True,
            "message": "Profile updated successfully!",
            "data": data
        })

    # GET Profile
    data = user.to_dict()
    if student_prof:
        data.update(student_prof.to_dict())

    if user.university_id:
        from models.university import UniversityTenant
        u = UniversityTenant.query.get(user.university_id)
        if u:
            data["university"] = {
                "id": str(u.id),
                "name": u.name,
                "slug": u.slug,
                "logo_url": u.logo_url,
            }

    return jsonify({"success": True, "data": data})


@student_bp.route("/api/departments")
@jwt_required()
def get_departments():
    """Get all active departments for selection."""
    depts = Department.query.filter_by(is_active=True).order_by(Department.display_order).all()
    return jsonify({
        "success": True,
        "data": [d.to_dict() for d in depts]
    })


@student_bp.route("/api/courses")
@jwt_required()
def get_courses():
    """Get all active courses."""
    courses = Course.query.filter_by(is_active=True).all()
    return jsonify({
        "success": True,
        "data": [c.to_dict() for c in courses]
    })


@student_bp.route("/api/courses/by-department/<dept_id>")
@jwt_required()
def get_courses_by_department(dept_id):
    """Get courses filtered by department."""
    courses = Course.query.filter_by(department_id=dept_id, is_active=True).all()
    return jsonify({
        "success": True,
        "data": [c.to_dict() for c in courses]
    })


@student_bp.route("/api/dashboard")
@jwt_required(optional=True)
def dashboard_data():
    """Get student dashboard data."""
    user = _get_authenticated_student_user()
    if not user:
        return jsonify({"success": False, "message": "Access restricted. Active student login required."}), 403

    student = Student.query.filter_by(user_id=user.id).first()
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

    # Get admit cards
    admit_cards = AdmitCard.query.filter_by(student_id=student.id).all()

    # Build response
    data = {
        "student": student.to_dict(),
        "current_semester": current_semester.to_dict() if current_semester else None,
        "applications": [app.to_dict() for app in applications],
        "admit_cards": [ac.to_dict() for ac in admit_cards],
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

    # Add University Branding if available
    university_info = None
    if student and student.university_id:
        from models.university import UniversityTenant
        u = UniversityTenant.query.get(student.university_id)
        if u:
            university_info = {
                "id": str(u.id),
                "name": u.name,
                "slug": u.slug,
                "logo_url": u.logo_url,
                "primary_color": u.primary_color,
                "accent_color": u.accent_color,
                "banner_text": u.banner_text
            }
    data["university"] = university_info

    return jsonify({"success": True, "data": data})



@student_bp.route("/api/documents/<app_id>")
@jwt_required()
def get_application_documents(app_id):
    """Get documents for an application (accessible by any authenticated department user)."""
    documents = Document.query.filter_by(application_id=app_id).all()
    return jsonify({
        "success": True,
        "data": [doc.to_dict() for doc in documents]
    })


@student_bp.route("/api/apply", methods=["POST"])
@jwt_required()
def create_application():
    """Create a new no-dues application with selected departments, documents, and signature."""
    user_id = get_jwt_identity()
    student = Student.query.filter_by(user_id=user_id).first()
    if not student:
        return jsonify({"success": False, "message": "Student profile not found"}), 404

    semester = Semester.query.filter_by(is_current=True, is_clearance_open=True).first()
    if not semester:
        semester = Semester.query.filter_by(is_current=True).first()
    if not semester:
        semester = Semester.query.order_by(Semester.created_at.desc()).first()
    if not semester:
        return jsonify({"success": False, "message": "No active semester configured for clearance"}), 400

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

    data = request.get_json(silent=True) or {}
    selected_depts = data.get("selected_departments", [])
    signature_data = data.get("signature", "") or ""

    # Hosteller default facilities if none passed
    if student.category == "hosteller" and not selected_depts:
        selected_depts = ["hostel", "mess"]

    # Find HOD department (auto-assigned matching student's branch/course)
    hod_dept = None
    student_branch = student.branch or student.course_name
    if student_branch:
        hod_dept = Department.query.filter(
            Department.role == "hod",
            Department.is_active == True,
            Department.name.ilike(f"%{student_branch}%")
        ).first()
    if not hod_dept:
        hod_dept = Department.query.filter_by(role="hod", is_active=True).first()
    if not hod_dept:
        hod_dept = Department.query.filter_by(role="hod").first()
    if not hod_dept:
        return jsonify({"success": False, "message": "HOD department not configured"}), 400

    # Determine workflow steps based on selected departments
    # Sequence: Facilities (Hostel/Mess/Transport/Scholarship) -> Academic HOD -> Accounts -> Examination
    active_workflow = []
    step_order = 1

    # 1. Add selected facility departments (hostel, mess, transport, scholarship)
    facility_order = ["hostel", "mess", "transport", "scholarship"]
    for dept_role in facility_order:
        if dept_role in selected_depts:
            dept = Department.query.filter_by(role=dept_role, is_active=True).first() or Department.query.filter_by(role=dept_role).first()
            if dept:
                active_workflow.append({
                    "department": dept,
                    "step_order": step_order,
                    "is_required": True,
                })
                step_order += 1

    # 2. Add Academic HOD Department
    if hod_dept:
        active_workflow.append({
            "department": hod_dept,
            "step_order": step_order,
            "is_required": True,
        })
        step_order += 1

    # 3. Add Accounts Department (Fee clearance & Financial Audit)
    accounts_dept = Department.query.filter_by(role="accounts", is_active=True).first() or Department.query.filter_by(role="accounts").first()
    if accounts_dept:
        active_workflow.append({
            "department": accounts_dept,
            "step_order": step_order,
            "is_required": True,
        })
        step_order += 1

    # 4. Add Examination Department (Final Clearance & Admit Card Generation)
    exam_dept = Department.query.filter_by(role="examination", is_active=True).first() or Department.query.filter_by(role="examination").first()
    if exam_dept:
        active_workflow.append({
            "department": exam_dept,
            "step_order": step_order,
            "is_required": True,
        })
        step_order += 1

    # Compute category based on student profile and selected departments
    category = "day_scholar"
    if student.category == "hosteller" or "hostel" in selected_depts:
        if "scholarship" in selected_depts:
            category = "scholarship_hosteller"
        else:
            category = "hosteller"
    else:
        if "transport" in selected_depts and "scholarship" in selected_depts:
            category = "scholarship_transport"
        elif "transport" in selected_depts:
            category = "transport_user"
        elif "scholarship" in selected_depts:
            category = "scholarship"
        else:
            category = "day_scholar"

    # Compute signature hash
    sig_hash = hashlib.sha256(signature_data.encode("utf-8")).hexdigest() if signature_data else ""

    # Create application with all new fields
    application = NoDuesApplication(
        student_id=student.id,
        semester_id=semester.id,
        category=category,
        hod_department_id=hod_dept.id if hod_dept else None,
        selected_departments=selected_depts,
        digital_signature=signature_data if signature_data else None,
        signature_hash=sig_hash,
        total_steps=len(active_workflow),
        status="draft",
    )
    db.session.add(application)
    db.session.flush()

    # Save digital signature record if provided
    if signature_data:
        digi_sig = DigitalSignature(
            user_id=user_id,
            signature_data=signature_data,
            signature_hash=sig_hash,
            ip_address=get_client_ip(),
        )
        db.session.add(digi_sig)

    # Create department approval entries for each step
    for step in active_workflow:
        dept_approval = ApplicationDepartment(
            application_id=application.id,
            department_id=step["department"].id,
            display_order=step["step_order"],
            is_required=step["is_required"],
            status="pending",
        )
        db.session.add(dept_approval)

    # Create notification for accounts department
    accounts_staff = User.query.filter_by(role="accounts").all()
    for staff in accounts_staff:
        notif = Notification(
            user_id=staff.id,
            type="application_submitted",
            title=f"New application from {student.student_name}",
            message=f"Application #{application.application_number} is pending clearance.",
            application_id=application.id,
        )
        db.session.add(notif)

    # Create audit log
    audit = AuditLog(
        user_id=user_id,
        action="create",
        resource_type="application",
        resource_id=application.id,
        details={
            "selected_departments": selected_depts,
            "category": category,
        },
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
    if not student:
        return jsonify({"success": False, "message": "Student profile not found"}), 404

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
    if not student:
        return jsonify({"success": False, "message": "Student profile not found"}), 404

    application = NoDuesApplication.query.filter_by(
        id=app_id, student_id=student.id
    ).first()

    if not application:
        return jsonify({"success": False, "message": "Application not found"}), 404

    if not application.can_submit() and application.status != "draft":
        return jsonify({"success": False, "message": "Application cannot be submitted"}), 400

    # Strictly enforce mandatory fee receipts check before submission
    uploaded_docs = Document.query.filter_by(application_id=application.id).all()
    uploaded_types = {d.document_type for d in uploaded_docs}
    if "exam_fee_receipt" not in uploaded_types or "next_sem_fee_receipt" not in uploaded_types:
        return jsonify({
            "success": False,
            "message": "Both Examination Fee Receipt and Next Semester Fee Receipt are strictly compulsory! Please upload both receipts to proceed with submission.",
        }), 400

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
    if not student:
        return jsonify({"success": False, "message": "Student profile not found"}), 404

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
    upload_folder = current_app.config.get("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
    file_path = secure_file_path(
        upload_folder,
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
    db.session.flush()

    # Create audit log
    audit = AuditLog(
        user_id=user_id,
        action="upload",
        resource_type="document",
        resource_id=document.id,
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


@student_bp.route("/api/admit-card/<card_number>/pdf")
@jwt_required(optional=True)
def download_admit_card_pdf(card_number):
    """Download Admit Card PDF for student."""
    card = AdmitCard.query.filter_by(card_number=card_number).first()
    if not card:
        return jsonify({"success": False, "message": "Admit card record not found"}), 404

    # If physical file missing, attempt on-the-fly PDF regeneration
    if not card.pdf_path or not os.path.exists(card.pdf_path):
        try:
            try:
                from blueprints.examination.routes import _generate_admit_card_pdf
            except ImportError:
                from backend.blueprints.examination.routes import _generate_admit_card_pdf

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

    card.is_downloaded = True
    card.download_count = (card.download_count or 0) + 1
    db.session.commit()

    return send_file(
        card.pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"AdmitCard_{card.card_number}.pdf",
    )


# ──────────────────────────────────────
# API: Student Experience Feedback
# ──────────────────────────────────────
@student_bp.route("/api/feedback", methods=["POST"])
@jwt_required(optional=True)
def submit_feedback():
    """Submit student experience feedback and ratings."""
    user = None
    user_id = get_jwt_identity()
    if user_id:
        user = User.query.get(user_id)
    elif current_user and current_user.is_authenticated:
        user = current_user

    if not user:
        return jsonify({"success": False, "message": "Authentication required to submit feedback"}), 401

    data = request.get_json(silent=True) or request.form

    overall_rating = int(data.get("overall_rating", 5))
    if overall_rating < 1 or overall_rating > 5:
        overall_rating = 5

    ease_of_use = data.get("ease_of_use", "easy")
    ai_helpfulness = data.get("ai_helpfulness", "good")
    upload_experience = data.get("upload_experience", "smooth")
    nps_score = int(data.get("nps_score", 10))
    comments = (data.get("comments") or "").strip()

    # Determine automated sentiment
    if overall_rating >= 4:
        sentiment = "positive"
    elif overall_rating == 3:
        sentiment = "neutral"
    else:
        sentiment = "constructive"

    student = getattr(user, "student_profile", None)
    if not student and hasattr(user, "id"):
        student = Student.query.filter_by(user_id=user.id).first()

    # Find latest application if available
    app_id = data.get("application_id")
    if not app_id and student:
        latest_app = NoDuesApplication.query.filter_by(student_id=student.id).order_by(NoDuesApplication.created_at.desc()).first()
        if latest_app:
            app_id = latest_app.id

    feedback = Feedback(
        user_id=user.id,
        student_id=student.id if student else None,
        application_id=app_id,
        overall_rating=overall_rating,
        ease_of_use=ease_of_use,
        ai_helpfulness=ai_helpfulness,
        upload_experience=upload_experience,
        nps_score=nps_score,
        comments=comments,
        sentiment=sentiment,
    )

    db.session.add(feedback)

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="create",
        resource_type="feedback",
        resource_id=feedback.id,
        details={"rating": overall_rating, "sentiment": sentiment},
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Thank you for your valuable feedback! Your response helps us continuously improve the NoDues platform.",
        "data": feedback.to_dict()
    }), 201


@student_bp.route("/api/feedback/status", methods=["GET"])
@jwt_required(optional=True)
def get_feedback_status():
    """Check if the current student has submitted feedback."""
    user = None
    user_id = get_jwt_identity()
    if user_id:
        user = User.query.get(user_id)
    elif current_user and current_user.is_authenticated:
        user = current_user

    if not user:
        return jsonify({"success": False, "has_submitted": False}), 200

    feedback = Feedback.query.filter_by(user_id=user.id).order_by(Feedback.created_at.desc()).first()
    return jsonify({
        "success": True,
        "has_submitted": feedback is not None,
        "last_feedback": feedback.to_dict() if feedback else None
    })



