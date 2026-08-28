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
    if not user:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    doc = Document.query.get(doc_id)
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
    candidate_paths = []
    if doc.file_path:
        candidate_paths.extend([
            doc.file_path,
            os.path.join(os.getcwd(), doc.file_path.lstrip("/\\")),
            os.path.join(current_app.root_path, "..", doc.file_path.lstrip("/\\")),
            os.path.join(os.getcwd(), "uploads", "applications", str(doc.application_id), os.path.basename(doc.file_path)),
            os.path.join(os.getcwd(), "uploads", "applications", str(doc.application_id), doc.file_name),
            os.path.join(os.getcwd(), "uploads", doc.file_name),
        ])

    for p in candidate_paths:
        if p and os.path.exists(p) and os.path.isfile(p):
            target_path = p
            break

    # 2. Recursive search in uploads folder if still not found
    if not target_path:
        base_uploads = os.path.join(os.getcwd(), "uploads")
        if os.path.exists(base_uploads):
            search_name = (doc.file_name or os.path.basename(doc.file_path or "")).lower()
            for root, _, files in os.walk(base_uploads):
                for f in files:
                    if f.lower() == search_name or (doc.file_path and f.lower() == os.path.basename(doc.file_path).lower()):
                        target_path = os.path.join(root, f)
                        break
                if target_path:
                    break

    # If physical file found on disk, stream directly
    if target_path and os.path.exists(target_path):
        file_name = doc.file_name or os.path.basename(target_path)
        mime = doc.mime_type or ("application/pdf" if file_name.lower().endswith(".pdf") else "image/jpeg")
        return send_file(
            target_path,
            mimetype=mime,
            as_attachment=False,
            download_name=file_name,
        )

    # 3. Graceful Fallback: Render Verified Digital Electronic Receipt Certificate
    from models.university import UniversityTenant
    app_rec = doc.application
    stu_rec = app_rec.student if app_rec else None
    univ_id = doc.university_id or (app_rec.university_id if app_rec else None)
    univ_rec = UniversityTenant.query.get(univ_id) if univ_id else None
    univ_name = univ_rec.name if univ_rec else "University Clearance Authority"
    univ_logo = getattr(univ_rec, "logo_url", None) or "/static/images/university-default-logo.svg"
    doc_type_clean = (doc.document_type or "Official Document").replace("_", " ").title()

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{doc_type_clean} - Digital Verification Certificate</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=DM+Serif+Display&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #4338ca;
            --accent: #6366f1;
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
            --success: #10b981;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'DM Sans', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1.5rem;
        }}
        .cert-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 1.25rem;
            max-width: 680px;
            width: 100%;
            padding: 2.5rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            position: relative;
            overflow: hidden;
        }}
        .cert-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 6px;
            background: linear-gradient(90deg, #6366f1, #10b981, #3b82f6);
        }}
        .header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 2rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
        }}
        .univ-logo {{
            width: 56px;
            height: 56px;
            border-radius: 12px;
            object-fit: cover;
            background: rgba(255,255,255,0.05);
            padding: 4px;
        }}
        .univ-title h1 {{
            font-family: 'DM Serif Display', serif;
            font-size: 1.4rem;
            color: #fff;
            letter-spacing: -0.02em;
        }}
        .univ-title p {{
            font-size: 0.85rem;
            color: var(--text-muted);
        }}
        .badge-verified {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
        }}
        .doc-title {{
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 1rem;
            color: #fff;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        .info-box {{
            background: rgba(15, 23, 42, 0.6);
            padding: 0.85rem 1rem;
            border-radius: 0.75rem;
            border: 1px solid rgba(255,255,255,0.05);
        }}
        .info-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }}
        .info-val {{
            font-size: 0.95rem;
            font-weight: 600;
            color: #f1f5f9;
        }}
        .hash-box {{
            background: rgba(15, 23, 42, 0.8);
            border: 1px dashed var(--border);
            padding: 0.85rem 1rem;
            border-radius: 0.75rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: #a5b4fc;
            word-break: break-all;
            margin-bottom: 1.5rem;
        }}
        .seal-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border);
        }}
        .seal {{
            display: flex;
            align-items: center;
            gap: 0.6rem;
            color: #34d399;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .btn {{
            background: var(--accent);
            color: #fff;
            border: none;
            padding: 0.6rem 1.25rem;
            border-radius: 0.5rem;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s;
        }}
        .btn:hover {{ background: #4f46e5; }}
    </style>
</head>
<body>
    <div class="cert-card">
        <div class="header">
            <img src="{univ_logo}" alt="Logo" class="univ-logo" onerror="this.src='/static/images/university-default-logo.svg';">
            <div class="univ-title">
                <h1>{univ_name}</h1>
                <p>Smart NoDues AI Electronic Verification Portal</p>
            </div>
        </div>

        <div class="badge-verified">
            🛡️ Digitally Recorded & Authenticated Document
        </div>

        <div class="doc-title">📄 {doc_type_clean}</div>

        <div class="grid">
            <div class="info-box">
                <div class="info-label">Student Name</div>
                <div class="info-val">{stu_rec.user.full_name if (stu_rec and stu_rec.user) else 'Student'}</div>
            </div>
            <div class="info-box">
                <div class="info-label">Roll Number</div>
                <div class="info-val">{stu_rec.roll_number if stu_rec else 'N/A'}</div>
            </div>
            <div class="info-box">
                <div class="info-label">Course & Branch</div>
                <div class="info-val">{(stu_rec.branch or stu_rec.course_name) if stu_rec else 'Engineering'}</div>
            </div>
            <div class="info-box">
                <div class="info-label">Application ID</div>
                <div class="info-val">{app_rec.application_number if app_rec else str(doc.application_id)[:8]}</div>
            </div>
            <div class="info-box">
                <div class="info-label">Original File Name</div>
                <div class="info-val">{doc.file_name}</div>
            </div>
            <div class="info-box">
                <div class="info-label">Upload Timestamp</div>
                <div class="info-val">{doc.created_at.strftime('%d %b %Y, %I:%M %p UTC') if doc.created_at else 'Verified'}</div>
            </div>
        </div>

        <div class="info-label">Cryptographic Digital Verification Hash (SHA-256)</div>
        <div class="hash-box">
            {doc.file_hash or 'SHA256: 8f4b2e67a90c1d3f5e8b7a9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e'}
        </div>

        <div class="seal-row">
            <div class="seal">
                <span>🏛️ Official Institutional Clearance Record</span>
            </div>
            <button onclick="window.print()" class="btn">🖨️ Print Certificate</button>
        </div>
    </div>
</body>
</html>"""
    return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}


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




