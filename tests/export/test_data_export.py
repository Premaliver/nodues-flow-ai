"""
Tests for University Data Export and Self-Service Portability.
"""

import os
import zipfile
import tempfile
import json
import pytest
import uuid
from backend.app import create_app
from backend.models import db
from backend.models.user import User
from backend.models.student import Student
from backend.models.department import Department
from backend.export.data_exporter import UniversityDataExporter


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_university_data_export(app_ctx):
    """Verifies that full university data export generates valid ZIP with JSON, CSV, and MANIFEST."""
    # Seed mock user and student
    user = User(
        id=uuid.uuid4(),
        email="export_student@test.edu",
        first_name="Export",
        last_name="Test",
        role="student",
        status="active",
    )
    user.set_password("SecurePass123!")
    db.session.add(user)
    db.session.flush()

    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        roll_number="EXP2026",
        enrollment_number="EXPEN01",
    )
    db.session.add(student)

    dept = Department(name="Computer Science", code="CSE", is_active=True)
    db.session.add(dept)
    db.session.commit()

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
        zip_path = tf.name

    try:
        report = UniversityDataExporter.export_to_zip(zip_path, include_documents=False)
        assert os.path.exists(zip_path)
        assert report["file_size"] > 0
        assert report["manifest"]["counts"]["students"] >= 1
        assert report["manifest"]["counts"]["departments"] >= 1

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            assert "MANIFEST.json" in namelist
            assert "data/students.json" in namelist
            assert "data/students.csv" in namelist
            assert "data/departments.json" in namelist

            manifest_content = json.loads(zf.read("MANIFEST.json").decode("utf-8"))
            assert manifest_content["export_version"] == "1.0.0"
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
