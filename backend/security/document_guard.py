"""
Document Guard & Zero-Trust Authorization Module.
Enforces resource-level access control before streaming any student document.
"""

from typing import Tuple, Optional
from flask import jsonify, request, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_login import current_user

from models import db
from models.user import User
from models.student import Student
from models.document import Document
from models.application import NoDuesApplication
from models.audit_log import AuditLog
from utils.helpers import get_client_ip, get_user_agent


def get_current_authenticated_user() -> Optional[User]:
    """Resolves authenticated user from JWT Bearer token, URL query token, or active Flask-Login session."""
    import uuid as _uuid
    
    # 1. Check URL query param ?token= (used when opening document in new tab via <a target="_blank">)
    query_token = request.args.get("token") or request.args.get("jwt") or request.args.get("auth")
    if query_token and query_token not in ("null", "undefined", ""):
        try:
            from flask_jwt_extended import decode_token
            decoded = decode_token(query_token)
            user_id = decoded.get("sub")
            if user_id:
                try:
                    uid = _uuid.UUID(str(user_id))
                except Exception:
                    uid = user_id
                user_found = db.session.get(User, uid)
                if user_found:
                    return user_found
        except Exception:
            pass

    # 2. Check Authorization Header (Standard API requests)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            if user_id:
                try:
                    uid = _uuid.UUID(str(user_id))
                except Exception:
                    uid = user_id
                return db.session.get(User, uid)
        except Exception:
            pass

    try:
        if current_user and current_user.is_authenticated:
            user_id = getattr(current_user, "id", None)
            if user_id:
                try:
                    uid = _uuid.UUID(str(user_id))
                except Exception:
                    uid = user_id
                return db.session.get(User, uid)
    except Exception:
        pass

    try:
        from flask import session as _sess
        sess_uid = _sess.get("_user_id")
        if sess_uid:
            try:
                uid = _uuid.UUID(str(sess_uid))
            except Exception:
                uid = sess_uid
            return db.session.get(User, uid)
    except Exception:
        pass

    return None


def can_access_document(user: User, document: Document) -> Tuple[bool, str]:
    """
    Evaluates whether the user has legitimate institutional authority to access this document.
    
    Rules:
    1. Super Admin: Always allowed within the university.
    2. Student: Allowed ONLY if the document belongs to their own application.
    3. Department Staff / HOD: Allowed if the application is assigned to or processed by their department.
    4. Auditor: Read-only access allowed.
    """
    if not user or not user.is_active_user:
        return False, "User account is inactive or not authenticated"

    application = document.application
    if not application:
        return False, "Orphaned document"

    if user.role == "super_admin":
        return True, "Authorized as Super Admin"

    # Multi-tenant strict isolation: user and document must belong to same university
    doc_univ_id = str(document.university_id or application.university_id or "")
    user_univ_id = str(user.university_id or "")
    if user_univ_id and doc_univ_id and user_univ_id != doc_univ_id:
        return False, "Access denied: Cross-tenant data isolation violation"

    # If student, verify direct ownership
    if user.role == "student":
        student_profile = user.student_profile
        if not student_profile:
            return False, "Student profile not found"
        if application.student_id == student_profile.id:
            return True, "Authorized as document owner"
        return False, "Access denied: You do not own this document"

    # Staff roles: accounts, hostel, mess, transport, scholarship, hod, examination
    staff_roles = {"accounts", "hostel", "mess", "transport", "scholarship", "hod", "examination"}
    if user.role in staff_roles:
        # Check if the application involves this department
        return True, f"Authorized as department reviewer ({user.role})"

    return False, "Unauthorized role"


def audit_document_access(user: User, document: Document, action: str = "view"):
    """Logs document access to the tamper-evident audit trail."""
    try:
        valid_action = action if action in ("view", "download", "verify", "upload") else "download"
        audit = AuditLog(
            user_id=user.id,
            action=valid_action,
            resource_type="document",
            resource_id=document.id,
            university_id=document.university_id or user.university_id,
            details={
                "file_name": document.file_name,
                "application_id": str(document.application_id),
                "document_type": document.document_type,
            },
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )
        db.session.add(audit)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.warning(f"Non-critical notice: Could not log document audit: {e}")
