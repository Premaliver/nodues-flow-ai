"""
University Data Export & Portability Engine.
Generates authenticated, self-service data export packages containing
JSON/CSV datasets, document files, and SHA-256 integrity manifests.
"""

import os
import io
import csv
import json
import zipfile
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List

from flask import current_app
from models import db
from models.user import User
from models.student import Student
from models.department import Department, DepartmentStaff
from models.application import NoDuesApplication, ApplicationDepartment
from models.document import Document
from models.audit_log import AuditLog
from models.system_setting import SystemSetting
from security.tenant_context import TenantContext


class UniversityDataExporter:
    """Creates complete, portable export archives for institutional data ownership."""

    @staticmethod
    def export_to_zip(target_zip_path: str, include_documents: bool = True) -> Dict[str, Any]:
        """
        Builds a comprehensive export package.
        Returns metadata report with file counts, total size, and export SHA-256 digest.
        """
        export_timestamp = datetime.now(timezone.utc).isoformat()
        tenant_id = TenantContext.get_tenant_id()
        manifest: Dict[str, Any] = {
            "export_version": "1.0.0",
            "tenant_id": tenant_id,
            "university_name": current_app.config.get("UNIVERSITY_NAME", "Smart NoDues University"),
            "exported_at": export_timestamp,
            "counts": {},
            "files": {},
        }

        with zipfile.ZipFile(target_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Export Students
            students = Student.query.all()
            students_data = [s.to_dict() for s in students]
            manifest["counts"]["students"] = len(students_data)
            zf.writestr("data/students.json", json.dumps(students_data, indent=2, default=str))

            if students_data:
                csv_buf = io.StringIO()
                writer = csv.DictWriter(csv_buf, fieldnames=list(students_data[0].keys()))
                writer.writeheader()
                writer.writerows(students_data)
                zf.writestr("data/students.csv", csv_buf.getvalue())

            # 2. Export Applications & Approvals
            apps = NoDuesApplication.query.all()
            apps_data = []
            for a in apps:
                app_dict = a.to_dict()
                app_dict["approvals"] = [dept_app.to_dict() for dept_app in a.department_approvals]
                apps_data.append(app_dict)

            manifest["counts"]["applications"] = len(apps_data)
            zf.writestr("data/applications.json", json.dumps(apps_data, indent=2, default=str))

            # 3. Export Departments & Staff
            departments = Department.query.all()
            depts_data = [d.to_dict() for d in departments]
            manifest["counts"]["departments"] = len(depts_data)
            zf.writestr("data/departments.json", json.dumps(depts_data, indent=2, default=str))

            # 4. Export Audit Logs
            audits = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10000).all()
            audits_data = [a.to_dict() for a in audits]
            manifest["counts"]["audit_logs"] = len(audits_data)
            zf.writestr("data/audit_logs.json", json.dumps(audits_data, indent=2, default=str))

            # 5. Export Documents & Physical Files
            documents = Document.query.all()
            manifest["counts"]["documents"] = len(documents)
            docs_metadata = []

            for doc in documents:
                doc_dict = doc.to_dict()
                docs_metadata.append(doc_dict)

                if include_documents and doc.file_path and os.path.exists(doc.file_path):
                    try:
                        with open(doc.file_path, "rb") as df:
                            content = df.read()
                            file_hash = hashlib.sha256(content).hexdigest()
                            safe_name = f"documents/{doc.id}_{doc.file_name}"
                            zf.writestr(safe_name, content)
                            manifest["files"][safe_name] = {
                                "document_id": str(doc.id),
                                "sha256": file_hash,
                                "size_bytes": len(content),
                            }
                    except Exception as e:
                        current_app.logger.warning(f"Could not bundle document {doc.id}: {e}")

            zf.writestr("data/documents_metadata.json", json.dumps(docs_metadata, indent=2, default=str))

            # 6. Write Manifest
            zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, default=str))

        # Compute archive checksum
        with open(target_zip_path, "rb") as zf_read:
            archive_hash = hashlib.sha256(zf_read.read()).hexdigest()

        return {
            "archive_path": target_zip_path,
            "archive_sha256": archive_hash,
            "file_size": os.path.getsize(target_zip_path),
            "manifest": manifest,
        }
