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
    """Serve an uploaded document file inline (PDF, Image, etc.)."""
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"success": False, "message": "Document record not found"}), 404

    if not doc.file_path or not os.path.exists(doc.file_path):
        return jsonify({"success": False, "message": "Physical document file not found"}), 404

    mime = doc.mime_type or ("application/pdf" if doc.file_name.lower().endswith(".pdf") else "image/jpeg")
    return send_file(
        doc.file_path,
        mimetype=mime,
        as_attachment=False,
        download_name=doc.file_name,
    )


@api_bp.route("/documents/<app_id>")
def get_documents_by_app(app_id):
    """Get documents list for an application."""
    documents = Document.query.filter_by(application_id=app_id).all()
    return jsonify({
        "success": True,
        "data": [doc.to_dict() for doc in documents]
    })



