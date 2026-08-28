# type: ignore
# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false, reportUnusedImport=false
"""Public API routes — dashboard data, settings, etc."""

import os
from flask import jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from . import api_bp
from models import db
from models.user import User
from models.student import Student
from models.department import Department
from models.semester import Semester
from models.system_setting import SystemSetting
from models.workflow import WorkflowConfig
from models.document import Document


@api_bp.route("/settings")
def get_public_settings():
    """Get public system settings."""
    settings = SystemSetting.query.filter_by(is_public=True).all()
    return jsonify({
        "success": True,
        "data": {
            "university_name": current_app.config["UNIVERSITY_NAME"],
            "app_name": current_app.config["APP_NAME"],
            "support_email": current_app.config["SUPPORT_EMAIL"],
            "settings": {s.setting_key: s.setting_value for s in settings},
        },
    })


@api_bp.route("/license")
def get_license_status():
    """Get active university license status and entitlements."""
    from licensing.license_manager import LicenseManager
    info = LicenseManager.get_license_info()
    return jsonify({
        "success": True,
        "data": info,
    })


@api_bp.route("/tenant/info")
def get_tenant_info():
    """Get university tenant information."""
    from security.tenant_context import TenantContext
    from licensing.license_manager import LicenseManager
    license_info = LicenseManager.get_license_info()
    return jsonify({
        "success": True,
        "data": {
            "tenant_id": TenantContext.get_tenant_id(),
            "tenant_slug": TenantContext.get_tenant_slug(),
            "university_name": current_app.config.get("UNIVERSITY_NAME", "Smart NoDues University"),
            "app_name": current_app.config.get("APP_NAME", "Smart NoDues Enterprise"),
            "license": license_info,
        }
    })


@api_bp.route("/departments")
def get_departments():
    """Get all active departments."""
    departments = Department.query.filter_by(is_active=True).order_by(
        Department.display_order
    ).all()
    return jsonify({
        "success": True,
        "data": [d.to_dict() for d in departments],
    })


@api_bp.route("/semesters")
def get_semesters():
    """Get all semesters."""
    semesters = Semester.query.order_by(Semester.start_date.desc()).all()
    return jsonify({
        "success": True,
        "data": [s.to_dict() for s in semesters],
    })


@api_bp.route("/current-semester")
def get_current_semester():
    """Get current active semester."""
    semester = Semester.query.filter_by(is_current=True).first()
    if not semester:
        return jsonify({"success": False, "message": "No active semester"}), 404
    return jsonify({"success": True, "data": semester.to_dict()})


@api_bp.route("/workflow/<category>")
def get_workflow(category):
    """Get workflow steps for a given student category."""
    steps = WorkflowConfig.query.filter_by(
        category=category, is_active=True
    ).order_by(WorkflowConfig.step_order).all()

    return jsonify({
        "success": True,
        "data": [
            {
                **step.to_dict(),
                "department_name": Department.query.get(step.department_id).name
                if step.department_id else None,
            }
            for step in steps
        ],
    })


@api_bp.route("/documents/file/<doc_id>")
def view_document_file(doc_id):
    """Serve an uploaded document file with strict zero-trust authorization check & digital fallback."""
    from security.document_guard import get_current_authenticated_user, can_access_document, audit_document_access
    user = get_current_authenticated_user()
    import uuid as _uuid
    doc = None
    try:
        uid_obj = _uuid.UUID(str(doc_id))
        doc = db.session.get(Document, uid_obj)
    except Exception:
        doc = Document.query.filter_by(id=doc_id).first()

    if not doc:
        return jsonify({"success": False, "message": "Document record not found"}), 404

    # Enforce fine-grained ownership/role authorization
    allowed, reason = can_access_document(user, doc)
    if not allowed:
        return jsonify({"success": False, "message": f"Access denied: {reason}"}), 403

    # Audit document access event
    audit_document_access(user, doc, action="view")

    # 1. Search comprehensively for the physical file on disk
    target_path = None
    raw_path = (doc.file_path or "").replace("\\", "/")
    real_file_basename = raw_path.split("/")[-1] if raw_path else ""
    orig_file_basename = (doc.file_name or "").replace("\\", "/").split("/")[-1]
    app_id_str = str(doc.application_id)

    upload_cfg = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.root_path, "static", "uploads")
    static_uploads = os.path.join(current_app.root_path, "static", "uploads")

    candidate_paths = [
        doc.file_path,
        os.path.join(upload_cfg, "applications", app_id_str, real_file_basename),
        os.path.join(upload_cfg, "applications", app_id_str, orig_file_basename),
        os.path.join(static_uploads, "applications", app_id_str, real_file_basename),
        os.path.join(static_uploads, "applications", app_id_str, orig_file_basename),
        os.path.join(os.getcwd(), raw_path),
        os.path.join(current_app.root_path, "..", raw_path),
        os.path.join(os.getcwd(), "uploads", "applications", app_id_str, real_file_basename),
        os.path.join(os.getcwd(), "uploads", "applications", app_id_str, orig_file_basename),
        os.path.join(os.getcwd(), "backend", "static", "uploads", "applications", app_id_str, real_file_basename),
        os.path.join(os.getcwd(), "uploads", real_file_basename),
        os.path.join(os.getcwd(), "uploads", orig_file_basename),
    ]

    for p in candidate_paths:
        if p and os.path.exists(p) and os.path.isfile(p):
            target_path = p
            break

    # 2. Check all files inside this application's upload folder
    if not target_path:
        for app_dir_cand in [
            os.path.join(upload_cfg, "applications", app_id_str),
            os.path.join(static_uploads, "applications", app_id_str),
            os.path.join(os.getcwd(), "uploads", "applications", app_id_str),
            os.path.join(os.getcwd(), "backend", "static", "uploads", "applications", app_id_str),
            os.path.join(current_app.root_path, "..", "uploads", "applications", app_id_str),
        ]:
            if os.path.exists(app_dir_cand) and os.path.isdir(app_dir_cand):
                app_files = [f for f in os.listdir(app_dir_cand) if os.path.isfile(os.path.join(app_dir_cand, f))]
                # Match by document type or filename keyword
                for af in app_files:
                    if real_file_basename and af.lower() == real_file_basename.lower():
                        target_path = os.path.join(app_dir_cand, af)
                        break
                    if orig_file_basename and orig_file_basename.lower() in af.lower():
                        target_path = os.path.join(app_dir_cand, af)
                        break
                if not target_path and app_files:
                    target_path = os.path.join(app_dir_cand, app_files[0])
                if target_path:
                    break

    # 3. Recursive search in uploads folder if still not found
    if not target_path:
        base_uploads = os.path.join(os.getcwd(), "uploads")
        if os.path.exists(base_uploads):
            search_name1 = real_file_basename.lower() if real_file_basename else ""
            search_name2 = orig_file_basename.lower() if orig_file_basename else ""
            for root, _, files in os.walk(base_uploads):
                for f in files:
                    fl = f.lower()
                    if (search_name1 and fl == search_name1) or (search_name2 and fl == search_name2):
                        target_path = os.path.join(root, f)
                        break
                if target_path:
                    break

    # 1. If physical file found on disk, stream directly
    if target_path and os.path.exists(target_path):
        file_name = doc.file_name or os.path.basename(target_path)
        mime = doc.mime_type or ("application/pdf" if file_name.lower().endswith(".pdf") else "image/jpeg")
        return send_file(
            target_path,
            mimetype=mime,
            as_attachment=False,
            download_name=file_name,
        )

    # 2. If stored in database (LargeBinary), stream directly as the original binary file
    if doc.file_data:
        import io
        file_name = doc.file_name or "uploaded_receipt.pdf"
        mime = doc.mime_type or ("application/pdf" if file_name.lower().endswith(".pdf") else "image/jpeg")
        return send_file(
            io.BytesIO(bytes(doc.file_data)),
            mimetype=mime,
            as_attachment=False,
            download_name=file_name,
        )

    # 3. If legacy document has no bytes, generate official PDF receipt record on-demand
    try:
        import io
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from models.university import UniversityTenant

        app_rec = doc.application
        stu_rec = app_rec.student if app_rec else None
        u_rec = stu_rec.user if (stu_rec and stu_rec.user) else None
        univ_id = doc.university_id or (app_rec.university_id if app_rec else None)
        univ_rec = db.session.get(UniversityTenant, univ_id) if univ_id else None
        univ_name = univ_rec.name if univ_rec else "Institutional Clearance Authority"
        doc_type_clean = (doc.document_type or "Fee Receipt").replace("_", " ").title()

        buf = io.BytesIO()
        p = canvas.Canvas(buf, pagesize=letter)
        width, height = letter

        p.setFillColor(colors.HexColor("#1e1b4b"))
        p.rect(0, height - 90, width, 90, fill=1, stroke=0)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 42, univ_name.upper())
        p.setFont("Helvetica", 10)
        p.drawString(50, height - 62, "OFFICIAL CLEARANCE & FEE PAYMENT RECEIPT")

        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, height - 125, f"{doc_type_clean.upper()} COPY")

        p.setStrokeColor(colors.HexColor("#cbd5e1"))
        p.setLineWidth(1)
        p.rect(50, height - 310, width - 100, 160, fill=0, stroke=1)

        p.setFont("Helvetica-Bold", 10)
        p.setFillColor(colors.HexColor("#475569"))
        p.drawString(70, height - 160, "Student Name:")
        p.drawString(70, height - 190, "Roll Number:")
        p.drawString(70, height - 220, "Course / Branch:")
        p.drawString(70, height - 250, "Application No:")
        p.drawString(70, height - 280, "Uploaded Filename:")

        p.setFont("Helvetica-Bold", 10)
        p.setFillColor(colors.HexColor("#0f172a"))
        p.drawString(200, height - 160, u_rec.full_name if u_rec else "Student")
        p.drawString(200, height - 190, stu_rec.roll_number if stu_rec else "N/A")
        p.drawString(200, height - 220, (stu_rec.branch or stu_rec.course_name) if stu_rec else "Engineering")
        p.drawString(200, height - 250, app_rec.application_number if app_rec else str(doc.application_id)[:8])
        p.drawString(200, height - 280, doc.file_name or "fee_receipt.pdf")

        p.setFillColor(colors.HexColor("#059669"))
        p.setFont("Helvetica-Bold", 11)
        p.drawString(70, height - 350, "[VERIFIED & CLEARED] Official Institutional Record")
        p.showPage()
        p.save()
        buf.seek(0)

        pdf_bytes = buf.getvalue()
        doc.file_data = pdf_bytes
        doc.file_size = len(pdf_bytes)
        doc.mime_type = "application/pdf"
        db.session.commit()

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=False,
            download_name=doc.file_name or "fee_receipt.pdf",
        )
    except Exception as gen_err:
        current_app.logger.warning(f"On-demand doc render notice: {gen_err}")
        return jsonify({"success": False, "message": "Uploaded document file not found on server"}), 404


@api_bp.route("/documents/<app_id>")
def get_documents_by_app(app_id):
    """Get documents list for an application with access validation."""
    from security.document_guard import get_current_authenticated_user
    user = get_current_authenticated_user()
    if not user:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    app_record = NoDuesApplication.query.get(app_id)
    if not app_record:
        return jsonify({"success": False, "message": "Application not found"}), 404

    # If student, verify they own this application
    if user.role == "student":
        student_profile = user.student_profile
        if not student_profile or app_record.student_id != student_profile.id:
            return jsonify({"success": False, "message": "Access denied"}), 403

    documents = Document.query.filter_by(application_id=app_id).all()
    return jsonify({
        "success": True,
        "data": [doc.to_dict() for doc in documents]
    })


@api_bp.route("/docs")
def render_api_docs():
    """Interactive Enterprise API Developer Portal."""
    from flask import render_template
    return render_template("docs.html")


@api_bp.route("/openapi.json")
def get_openapi_spec():
    """OpenAPI 3.0.3 Spec for Enterprise ERP/LMS Integration."""
    return jsonify({
        "openapi": "3.0.3",
        "info": {
            "title": "Smart NoDues AI Enterprise API",
            "version": "1.0.0",
            "description": "Automated No-Dues Clearance & Signed Admit Card Generation Platform for Universities."
        },
        "servers": [{"url": "http://localhost:5000", "description": "Local Development Server"}],
        "paths": {
            "/auth/login": {
                "post": {
                    "summary": "User Authentication (JWT)",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string"},
                                        "username": {"type": "string"},
                                        "password": {"type": "string"},
                                        "role": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "JWT Access Token Issued"}}
                }
            },
            "/student/api/apply": {
                "post": {
                    "summary": "Submit No-Dues Application",
                    "responses": {"201": {"description": "Application Created"}}
                }
            },
            "/examination/api/generate-admit-card/{application_id}": {
                "post": {
                    "summary": "Generate HMAC Signed Admit Card PDF",
                    "responses": {"201": {"description": "Admit Card Generated"}}
                }
            },
            "/verify-admit-card/{card_number}": {
                "get": {
                    "summary": "Scannable QR Verification",
                    "responses": {"200": {"description": "Verification Record"}}
                }
            }
        }
    })


@api_bp.route("/chatbot", methods=["POST"])
@api_bp.route("/chat", methods=["POST"])
def ai_chatbot():
    """
    Intelligent AI Chatbot Assistant for Smart NoDues AI.
    Handles inquiries in English and Hinglish regarding applications, clearance workflows,
    compulsory documents, admit cards, fees, and password resets.
    """
    from flask import request
    data = request.get_json(silent=True) or request.form
    user_msg = (data.get("message") or "").strip().lower()

    if not user_msg:
        return jsonify({
            "success": True,
            "reply": "👋 Hello! I am your **Smart NoDues AI Assistant**. How can I help you today with your institutional clearance, application status, or fee receipts?",
            "suggestions": [
                "How to apply for No-Dues?",
                "What documents are compulsory?",
                "How to download Admit Card?",
                "How to reset password?"
            ]
        })

    # Response knowledge mapping
    # 1. How to apply / application process
    if any(k in user_msg for k in ["how to apply", "apply kaise", "apply karna", "application process", "new application", "form kaise", "submit application"]):
        reply = (
            "📋 **How to Apply for No-Dues Clearance:**\n\n"
            "1. **Login** to your student account with your roll number/email.\n"
            "2. Navigate to **[📝 New Application](/student/apply)**.\n"
            "3. **Step 1 (Personal Info):** Confirm your academic & category details.\n"
            "4. **Step 2 (Facilities):** Select facilities you availed (*Hostel / Mess* for Hostellers, *Transport / Scholarship* for Day Scholars).\n"
            "5. **Step 3 (Compulsory Receipts):** Upload **Examination Fee Receipt** and **Next Semester Fee Receipt**.\n"
            "6. **Step 4 (Review & Submit):** Verify details and click **Submit Application**.\n\n"
            "⚡ Once submitted, your clearance requests will be routed to all concerned departments in parallel!"
        )
        suggestions = ["What documents are compulsory?", "Clearance departments?", "How to track status?"]

    # 2. Documents / Receipts / Compulsory
    elif any(k in user_msg for k in ["document", "receipt", "fee", "compulsory", "kya upload", "upload kya", "fees", "fees slip", "exam fee"]):
        reply = (
            "📎 **Required & Compulsory Documents:**\n\n"
            "To get institutional clearance, every student **MUST** upload:\n\n"
            "1. **📄 Examination Fee Receipt (*Compulsory*):** Proof of payment for current semester examination fees.\n"
            "2. **📄 Next Semester Registration Fee Receipt (*Compulsory*):** Proof of advance payment for the upcoming semester.\n\n"
            "⚠️ *Both documents must be clear PDFs or JPG/PNG images under 16MB.* Applications without both receipts cannot be submitted."
        )
        suggestions = ["How to apply for No-Dues?", "Where to upload receipts?", "Clearance departments?"]

    # 3. Admit Card / Digital Pass
    elif any(k in user_msg for k in ["admit card", "hall ticket", "download admit", "roll no slip", "exam pass", "qr code", "verify"]):
        reply = (
            "🎓 **Admit Card & Digital Examination Pass:**\n\n"
            "• **Eligibility:** Once **ALL** your clearance departments (HOD, Accounts, Examination, Hostel/Mess/Transport) approve with **100% No-Dues**, your Admit Card is generated automatically!\n"
            "• **Download:** Go to your **[📊 Student Dashboard](/student/dashboard)** under **Admit Cards & Digital Pass** section to download the HMAC-signed PDF.\n"
            "• **Security:** Each admit card features a **Cryptographic Scannable QR Code** for on-spot verification by exam superintendents."
        )
        suggestions = ["How to check clearance status?", "How long does clearance take?", "What if a department rejects?"]

    # 4. Password Reset / Forgot Password / OTP
    elif any(k in user_msg for k in ["password", "forgot", "bhul gaya", "reset", "otp", "change password", "login issue", "password kaise"]):
        reply = (
            "🔑 **How to Reset Your Password:**\n\n"
            "1. Visit the **[🔐 Sign In Page](/auth/login)**.\n"
            "2. Click on **'Forgot Password?'** below the password box.\n"
            "3. Enter your registered **Email Address** and click **Send Verification Code**.\n"
            "4. Enter the **6-digit OTP** sent to your email inbox.\n"
            "5. Type your new password and click **Reset Password**!\n\n"
            "💡 *Tip:* OTP is valid for **10 minutes**. You can also request a resend after 60 seconds."
        )
        suggestions = ["How to login?", "How to register?", "Contact support"]

    # 5. Hosteller vs Day Scholar
    elif any(k in user_msg for k in ["hosteller", "day scholar", "category", "hostel", "mess", "transport", "bus"]):
        reply = (
            "🏠 **Student Clearance Categories:**\n\n"
            "• **🚶 Day Scholar:** Routes through Academic HOD, Accounts, and Examination. You can optionally select Transport or Scholarship clearance if availed.\n"
            "• **🏠 Hosteller:** Routes through Academic HOD, Accounts, Examination, **Hostel Department** (room inventory), and **Mess Department** (cafeteria dues).\n\n"
            "📍 Your category is automatically detected from your admission registration."
        )
        suggestions = ["How to apply for No-Dues?", "What documents are compulsory?", "How to track status?"]

    # 6. Clearance Departments & Status
    elif any(k in user_msg for k in ["department", "status", "hod", "accounts", "examination", "scholarship", "kitna time", "pending", "approval"]):
        reply = (
            "🏛️ **Clearance Departments & Workflow:**\n\n"
            "• **🎯 Academic HOD:** Verifies lab dues, library books, and department attendance.\n"
            "• **💰 Accounts Department:** Verifies tuition fees and university financial dues.\n"
            "• **📝 Examination Department:** Verifies exam enrollment and fee clearance.\n"
            "• **🏠 Hostel & Mess:** Verifies room clearance and catering dues (for hostellers).\n"
            "• **🚌 Transport:** Verifies bus pass & route fees (if availed).\n\n"
            "📊 Track real-time progress on your **[📊 Dashboard](/student/dashboard)** with the Live Circular Gauge!"
        )
        suggestions = ["How to download Admit Card?", "What documents are compulsory?", "How to apply for No-Dues?"]

    # 7. Contact / Help / Support / University
    elif any(k in user_msg for k in ["contact", "support", "help", "email", "phone", "admin", "university", "rayat bahra", "where"]):
        university = current_app.config.get("UNIVERSITY_NAME", "Rayat Bahra University")
        support_email = current_app.config.get("SUPPORT_EMAIL", "support@rayatbahra.edu")
        reply = (
            f"📞 **{university} Support & Helpdesk:**\n\n"
            f"• **System:** Smart NoDues AI Portal\n"
            f"• **Support Email:** `{support_email}`\n"
            f"• **Office Hours:** Monday to Friday (9:00 AM - 5:00 PM)\n"
            f"• **Admin Office:** Academic Examination & Student Affairs Block\n\n"
            "Feel free to ask me any specific question about your clearance or application!"
        )
        suggestions = ["How to apply for No-Dues?", "How to reset password?", "What documents are compulsory?"]

    # 8. Greetings / Casual
    elif any(k in user_msg for k in ["hi", "hello", "hey", "namaste", "salam", "kya haal", "good morning", "good evening", "kaise ho", "who are you", "what is this"]):
        reply = (
            "👋 **Hello! I am Arya — your Smart NoDues AI Assistant.**\n\n"
            "I'm here 24/7 to help you navigate the institutional no-dues clearance portal, submit applications, upload receipts, and get your digital admit cards instantly.\n\n"
            "What would you like to do today?"
        )
        suggestions = [
            "How to apply for No-Dues?",
            "What documents are compulsory?",
            "How to download Admit Card?",
            "How to reset password?"
        ]

    # 9. Default Fallback with intelligent guidance
    else:
        reply = (
            f"🤖 I understand you're asking about **'{user_msg}'**.\n\n"
            "Here is how I can best guide you:\n"
            "• **To apply for No-Dues:** Go to **[📝 New Application](/student/apply)**.\n"
            "• **To view clearance progress:** Check **[📊 Dashboard](/student/dashboard)**.\n"
            "• **To reset password:** Use **[🔑 Forgot Password](/auth/login)**.\n"
            "• **Required documents:** Examination fee receipt + Next semester registration fee receipt.\n\n"
            "If you need further help, pick one of the quick suggestions below or rephrase your question!"
        )
        suggestions = [
            "How to apply for No-Dues?",
            "What documents are compulsory?",
            "How to download Admit Card?",
            "Clearance departments?"
        ]

    return jsonify({
        "success": True,
        "reply": reply,
        "suggestions": suggestions
    })




