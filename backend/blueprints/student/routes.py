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
    import uuid as _uuid
    # 1. Check Flask-Login session first if active and role is student
    try:
        if current_user and current_user.is_authenticated and current_user.role == "student":
            user_id = getattr(current_user, "id", None)
            if user_id:
                try:
                    uid = _uuid.UUID(str(user_id))
                except Exception:
                    uid = user_id
                u = db.session.get(User, uid)
                if u and u.role == "student":
                    return u
    except Exception:
        pass

    # 2. Check JWT Identity
    try:
        jwt_id = get_jwt_identity()
        if jwt_id:
            try:
                u_id = _uuid.UUID(str(jwt_id))
            except Exception:
                u_id = jwt_id
            jwt_user = db.session.get(User, u_id)
            if jwt_user and jwt_user.role == "student":
                return jwt_user
    except Exception:
        pass

    # 3. Check flask session['_user_id']
    try:
        from flask import session as _flask_sess
        sess_user_id = _flask_sess.get("_user_id")
        if sess_user_id:
            try:
                su_id = _uuid.UUID(str(sess_user_id))
            except Exception:
                su_id = sess_user_id
            su = db.session.get(User, su_id)
            if su and su.role == "student":
                return su
    except Exception:
        pass

    return None


def _ensure_student_profile(user: User) -> Student:
    """Ensure a linked Student record exists with all required non-null fields populated."""
    student_prof = Student.query.filter_by(user_id=user.id).first()
    if student_prof:
        return student_prof

    import secrets
    curr_year = datetime.now(timezone.utc).year
    rand_suffix = secrets.token_hex(3).upper()
    roll = f"STU-{curr_year}-{rand_suffix}"
    enroll = f"ENR-{curr_year}-{rand_suffix}"

    student_prof = Student(
        user_id=user.id,
        roll_number=roll,
        enrollment_number=enroll,
        course_name="B.Tech Computer Science",
        branch="Computer Science & Engineering",
        current_semester=1,
        batch_year=f"{curr_year}-{curr_year+4}",
        admission_year=curr_year,
        category="day_scholar",
        university_id=user.university_id,
    )
    db.session.add(student_prof)
    db.session.commit()
    return student_prof


@student_bp.route("/api/profile", methods=["GET", "PUT"])
@jwt_required(optional=True)
def get_profile():
    """Get or update student profile with full details."""
    user = _get_authenticated_student_user()
    if not user:
        return jsonify({"success": False, "message": "Access restricted. Active student login required."}), 403

    student_prof = _ensure_student_profile(user)

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
@jwt_required(optional=True)
def get_departments():
    """Get all active departments for selection (scoped to student's university)."""
    user = _get_authenticated_student_user()
    univ_id = user.university_id if user else None
    if univ_id:
        depts = Department.query.filter_by(university_id=univ_id, is_active=True).order_by(Department.display_order).all()
        if not depts:
            depts = Department.query.filter_by(is_active=True).order_by(Department.display_order).all()
    else:
        depts = Department.query.filter_by(is_active=True).order_by(Department.display_order).all()
    return jsonify({
        "success": True,
        "data": [d.to_dict() for d in depts]
    })


@student_bp.route("/api/courses")
@jwt_required(optional=True)
def get_courses():
    """Get all active courses."""
    courses = Course.query.filter_by(is_active=True).all()
    return jsonify({
        "success": True,
        "data": [c.to_dict() for c in courses]
    })


@student_bp.route("/api/courses/by-department/<dept_id>")
@jwt_required(optional=True)
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
        user_id=user.id, is_read=False
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

    # Add University Branding strictly from student's registered university
    university_info = None
    if student and student.university_id:
        from models.university import UniversityTenant
        u = db.session.get(UniversityTenant, student.university_id)
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
def get_application_documents(app_id):
    """Get documents for an application."""
    documents = Document.query.filter_by(application_id=app_id).all()
    return jsonify({
        "success": True,
        "data": [doc.to_dict() for doc in documents]
    })


@student_bp.route("/api/upload-document/<app_id>", methods=["POST"])
@jwt_required(optional=True)
def upload_document(app_id):
    """Upload a document/receipt for an application."""
    try:
        user = _get_authenticated_student_user()
        if not user:
            return jsonify({"success": False, "message": "Access restricted. Active student login required."}), 401

        student = _ensure_student_profile(user)

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

        # Map document types to model enum
        doc_type_mapping = {
            "fee_receipt": "semester_fee_receipt",
            "tuition_fee": "semester_fee_receipt",
            "semester_fee": "semester_fee_receipt",
            "semester_fee_receipt": "semester_fee_receipt",
            "exam_fee": "exam_fee_receipt",
            "exam_fee_receipt": "exam_fee_receipt",
            "next_sem_fee": "next_sem_fee_receipt",
            "next_sem_fee_receipt": "next_sem_fee_receipt",
            "hostel_dues": "other",
            "hostel_receipt": "other",
            "mess_bill": "other",
            "mess_receipt": "other",
            "transport_pass": "other",
            "transport_receipt": "other",
            "scholarship_doc": "scholarship_document",
            "scholarship_document": "scholarship_document",
            "library_clearance": "library_clearance",
            "library_receipt": "library_clearance",
            "lab_clearance": "lab_clearance",
            "identity_proof": "identity_proof",
            "other": "other",
            "other_document": "other",
        }
        raw_doc_type = request.form.get("document_type", "other")
        document_type = doc_type_mapping.get(raw_doc_type, "other")

        upload_folder = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.root_path, "static", "uploads"))
        app_dir = os.path.join(upload_folder, "applications", str(app_id))
        os.makedirs(app_dir, exist_ok=True)
        
        file_bytes = file.read()
        if not file_bytes:
            return jsonify({"success": False, "message": "Uploaded file is empty"}), 400

        from werkzeug.utils import secure_filename
        import time, hashlib
        clean_orig_name = secure_filename(file.filename) or "receipt.pdf"
        unique_name = f"{int(time.time())}_{clean_orig_name}"
        full_save_path = os.path.join(app_dir, unique_name)
        with open(full_save_path, "wb") as f_out:
            f_out.write(file_bytes)

        # Calculate hash for integrity
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Create document record with explicit tenant isolation and database persistence
        document = Document(
            application_id=application.id,
            document_type=document_type,
            file_name=file.filename,
            file_path=full_save_path,
            file_data=file_bytes,
            file_size=len(file_bytes),
            mime_type=file.content_type or ("application/pdf" if file.filename.lower().endswith(".pdf") else "image/jpeg"),
            file_hash=file_hash,
            uploaded_by=user.id,
            university_id=student.university_id or application.university_id or user.university_id,
            status="pending",
        )
        db.session.add(document)
        db.session.flush()

        # Create audit log
        try:
            audit = AuditLog(
                user_id=user.id,
                action="upload",
                resource_type="document",
                resource_id=document.id,
                university_id=document.university_id or user.university_id,
                details={"type": document_type, "file_name": file.filename},
                ip_address=get_client_ip(),
                user_agent=get_user_agent(),
            )
            db.session.add(audit)
        except Exception:
            pass

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Document uploaded successfully",
            "data": {"document": document.to_dict()},
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error uploading document: {e}")
        return jsonify({"success": False, "message": f"Document upload failed: {str(e)}"}), 500


@student_bp.route("/api/apply", methods=["POST"])
@jwt_required(optional=True)
def create_application():
    """Create a new no-dues application with selected departments, documents, and signature."""
    try:
        user = _get_authenticated_student_user()
        if not user:
            return jsonify({"success": False, "message": "Access restricted. Active student login required."}), 401

        student = _ensure_student_profile(user)

        semester = Semester.query.filter_by(is_current=True, is_clearance_open=True).first()
        if not semester:
            semester = Semester.query.filter_by(is_current=True).first()
        if not semester:
            semester = Semester.query.order_by(Semester.created_at.desc()).first()
        if not semester:
            # Auto-create default active semester if missing
            from datetime import date
            semester = Semester(
                semester_number=1,
                semester_name="Semester 1 (2025-2026)",
                academic_year="2025-2026",
                start_date=date.today(),
                end_date=date.today(),
                is_current=True,
                is_clearance_open=True,
            )
            db.session.add(semester)
            db.session.commit()

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

        u_id = student.university_id
        if u_id:
            from utils.tenant_helpers import ensure_university_departments
            try:
                ensure_university_departments(u_id)
            except Exception as e:
                current_app.logger.warning(f"Error ensuring university departments: {e}")

        # Find HOD department (auto-assigned matching student's branch/course within this university)
        hod_dept = None
        student_branch = student.branch or student.course_name
        if student_branch and u_id:
            hod_dept = Department.query.filter(
                Department.role == "hod",
                Department.university_id == u_id,
                Department.is_active == True,
                Department.name.ilike(f"%{student_branch}%")
            ).first()
        if not hod_dept and u_id:
            hod_dept = Department.query.filter_by(role="hod", university_id=u_id, is_active=True).first()
        if not hod_dept and u_id:
            hod_dept = Department.query.filter_by(role="hod", university_id=u_id).first()
        if not hod_dept and u_id:
            hod_count = Department.query.filter_by(role="hod", university_id=u_id).count()
            code_suffix = f"_{hod_count + 1}" if hod_count > 0 else ""
            hod_dept = Department(
                university_id=u_id,
                code=f"HOD{code_suffix}"[:20],
                name=f"Head of Department ({student_branch or 'Academic'})",
                role="hod",
                display_order=6,
                is_active=True
            )
            db.session.add(hod_dept)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                hod_dept = Department.query.filter_by(role="hod", university_id=u_id).first()

        if not hod_dept:
            hod_dept = Department.query.filter_by(role="hod", is_active=True).first()

        # Determine workflow steps based on selected departments
        # Sequence: Facilities (Hostel/Mess/Transport/Scholarship) -> Academic HOD -> Accounts -> Examination
        active_workflow = []
        step_order = 1

        # 1. Add selected facility departments (hostel, mess, transport, scholarship)
        from utils.tenant_helpers import STANDARD_DEPARTMENTS
        facility_order = ["hostel", "mess", "transport", "scholarship"]
        for dept_role in facility_order:
            if dept_role in selected_depts:
                dept = None
                if u_id:
                    dept = Department.query.filter(
                        Department.role == dept_role,
                        (Department.university_id == u_id) | (Department.university_id == str(u_id)),
                        Department.is_active == True
                    ).first()
                if not dept and u_id:
                    dept_spec = next((d for d in STANDARD_DEPARTMENTS if d["role"] == dept_role), None)
                    if dept_spec:
                        dept = Department(
                            university_id=u_id,
                            code=dept_spec["code"],
                            name=dept_spec["name"],
                            role=dept_role,
                            display_order=dept_spec["display_order"],
                            is_active=True
                        )
                        db.session.add(dept)
                        try:
                            db.session.commit()
                        except Exception:
                            db.session.rollback()
                            dept = Department.query.filter(
                                Department.role == dept_role,
                                Department.university_id == u_id
                            ).first()
                if dept:
                    active_workflow.append({
                        "department": dept,
                        "step_order": step_order,
                        "is_required": True,
                    })
                    step_order += 1

        # 2. Add Accounts Department (Fee clearance & Financial Audit)
        accounts_dept = None
        if u_id:
            accounts_dept = Department.query.filter(
                Department.role == "accounts",
                (Department.university_id == u_id) | (Department.university_id == str(u_id)),
                Department.is_active == True
            ).first()
        if not accounts_dept and u_id:
            accounts_dept = Department(
                university_id=u_id,
                code="ACC",
                name="Accounts & Finance",
                role="accounts",
                display_order=7,
                is_active=True
            )
            db.session.add(accounts_dept)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                accounts_dept = Department.query.filter(
                    Department.role == "accounts",
                    Department.university_id == u_id
                ).first()

        if accounts_dept:
            active_workflow.append({
                "department": accounts_dept,
                "step_order": step_order,
                "is_required": True,
            })
            step_order += 1

        # 3. Add Academic HOD Department
        if hod_dept:
            active_workflow.append({
                "department": hod_dept,
                "step_order": step_order,
                "is_required": True,
            })
            step_order += 1

        # 4. Add Examination Department (Final Clearance & Admit Card Generation)
        exam_dept = None
        if u_id:
            exam_dept = Department.query.filter(
                Department.role == "examination",
                (Department.university_id == u_id) | (Department.university_id == str(u_id)),
                Department.is_active == True
            ).first()
        if not exam_dept and u_id:
            exam_dept = Department(
                university_id=u_id,
                code="EXAM",
                name="Examination Department",
                role="examination",
                display_order=8,
                is_active=True
            )
            db.session.add(exam_dept)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                exam_dept = Department.query.filter(
                    Department.role == "examination",
                    Department.university_id == u_id
                ).first()
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
            university_id=student.university_id,
        )
        db.session.add(application)
        db.session.flush()

        # Save digital signature record if provided
        if signature_data:
            try:
                digi_sig = DigitalSignature(
                    user_id=user.id,
                    signature_data=signature_data,
                    signature_hash=sig_hash,
                    ip_address=get_client_ip(),
                )
                db.session.add(digi_sig)
            except Exception as e:
                current_app.logger.warning(f"Error saving digital signature: {e}")

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

        # Notify university staff members
        try:
            accounts_staff = []
            if u_id:
                accounts_staff = User.query.filter_by(role="accounts", university_id=u_id).all()

            for staff in accounts_staff:
                notif = Notification(
                    user_id=staff.id,
                    type="application_submitted",
                    title=f"New application from {student.student_name}",
                    message=f"Application #{application.application_number} is pending clearance.",
                    application_id=application.id,
                )
                db.session.add(notif)
        except Exception as e:
            current_app.logger.warning(f"Notification creation skipped: {e}")

        # Create audit log
        try:
            audit = AuditLog(
                user_id=user.id,
                action="create",
                resource_type="application",
                resource_id=application.id,
                details={
                    "selected_departments": selected_depts,
                    "category": category,
                    "university_id": str(u_id) if u_id else None,
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
            "message": "Application created successfully",
            "data": {"application": application.to_dict()},
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating application: {e}")
        return jsonify({"success": False, "message": f"Application initialization failed: {str(e)}"}), 500


@student_bp.route("/api/application/<app_id>")
@jwt_required(optional=True)
def get_application(app_id):
    """Get application details with all approvals and documents."""
    try:
        user = _get_authenticated_student_user()
        if not user:
            return jsonify({"success": False, "message": "Access restricted. Active student login required."}), 401

        student = _ensure_student_profile(user)

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
    except Exception as e:
        current_app.logger.error(f"Error fetching application: {e}")
        return jsonify({"success": False, "message": f"Error fetching application: {str(e)}"}), 500


@student_bp.route("/api/application/<app_id>/delete", methods=["DELETE", "POST"])
@student_bp.route("/api/application/<app_id>/cancel", methods=["DELETE", "POST"])
@student_bp.route("/api/application/delete/<app_id>", methods=["DELETE", "POST"])
@student_bp.route("/api/application/cancel/<app_id>", methods=["DELETE", "POST"])
@jwt_required(optional=True)
def delete_or_cancel_application(app_id):
    """Delete or cancel an existing clearance application so the student can submit a fresh one."""
    try:
        user = _get_authenticated_student_user()
        if not user:
            return jsonify({"success": False, "message": "Access restricted. Active student login required."}), 401

        student = _ensure_student_profile(user)

        application = NoDuesApplication.query.filter_by(
            id=app_id, student_id=student.id
        ).first()

        if not application:
            return jsonify({"success": False, "message": "Application not found or already removed."}), 404

        app_num = application.application_number or str(app_id)[:8]

        # 1. Clean notifications referencing this application
        Notification.query.filter_by(application_id=application.id).delete()
        # 2. Clean uploaded documents referencing this application
        Document.query.filter_by(application_id=application.id).delete()
        # 3. Clean admit cards referencing this application
        AdmitCard.query.filter_by(application_id=application.id).delete()
        # 4. Clean department approvals referencing this application
        ApplicationDepartment.query.filter_by(application_id=application.id).delete()

        # 5. Delete application record completely
        db.session.delete(application)

        # 6. Create audit log
        try:
            audit = AuditLog(
                user_id=user.id,
                action="delete",
                resource_type="application",
                resource_id=app_id,
                university_id=student.university_id,
                details={"action": "student_deleted_application", "app_number": app_num},
                ip_address=get_client_ip(),
                user_agent=get_user_agent(),
            )
            db.session.add(audit)
        except Exception:
            pass

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Application #{app_num} has been successfully deleted. You can now submit a fresh application!",
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelling application: {e}")
        return jsonify({"success": False, "message": f"Could not delete application: {str(e)}"}), 500


@student_bp.route("/api/submit/<app_id>", methods=["POST"])
@jwt_required(optional=True)
def submit_application(app_id):
    """Submit application for processing."""
    try:
        user = _get_authenticated_student_user()
        if not user:
            return jsonify({"success": False, "message": "Access restricted. Active student login required."}), 401

        student = _ensure_student_profile(user)

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
        try:
            audit = AuditLog(
                user_id=user.id,
                action="update",
                resource_type="application",
                resource_id=application.id,
                details={"action": "submit"},
                ip_address=get_client_ip(),
                user_agent=get_user_agent(),
            )
            db.session.add(audit)
        except Exception:
            pass

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Application submitted successfully",
            "data": {"application": application.to_dict()},
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error submitting application: {e}")
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


@student_bp.route("/api/documents/file/<doc_id>")
def student_view_document_file(doc_id):
    """Forward document viewing to main api blueprint handler."""
    from blueprints.api.routes import view_document_file
    return view_document_file(doc_id)



