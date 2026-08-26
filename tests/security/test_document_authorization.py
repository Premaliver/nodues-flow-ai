"""
Security tests for Document Authorization & BOLA/IDOR Prevention.
"""

import pytest
import uuid
from backend.app import create_app
from backend.models import db
from backend.models.user import User
from backend.models.student import Student
from backend.models.application import NoDuesApplication
from backend.models.document import Document
from backend.models.semester import Semester
from backend.security.document_guard import can_access_document


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_student_cannot_access_other_student_document(app_ctx):
    """
    IDOR / BOLA Prevention Test:
    Ensures Student A cannot view or download Student B's document.
    """
    # Create Student A
    user_a = User(
        id=uuid.uuid4(),
        email="student_a@test.edu",
        first_name="Alice",
        last_name="Smith",
        role="student",
        status="active",
    )
    user_a.set_password("SecurePass123!")
    db.session.add(user_a)
    db.session.flush()

    student_a = Student(
        id=uuid.uuid4(),
        user_id=user_a.id,
        roll_number="CS2026001",
        enrollment_number="EN001",
    )
    db.session.add(student_a)

    # Create Student B
    user_b = User(
        id=uuid.uuid4(),
        email="student_b@test.edu",
        first_name="Bob",
        last_name="Jones",
        role="student",
        status="active",
    )
    user_b.set_password("SecurePass123!")
    db.session.add(user_b)
    db.session.flush()

    student_b = Student(
        id=uuid.uuid4(),
        user_id=user_b.id,
        roll_number="CS2026002",
        enrollment_number="EN002",
    )
    db.session.add(student_b)

    # Create Semester
    sem = Semester(name="Spring 2026", code="SP26")
    db.session.add(sem)
    db.session.flush()

    # Create Application for Student B
    app_b = NoDuesApplication(
        id=uuid.uuid4(),
        student_id=student_b.id,
        semester_id=sem.id,
        category="day_scholar",
        total_steps=5,
    )
    db.session.add(app_b)
    db.session.flush()

    # Create Document owned by Student B
    doc_b = Document(
        id=uuid.uuid4(),
        application_id=app_b.id,
        document_type="semester_fee_receipt",
        file_name="receipt_student_b.pdf",
        file_path="/tmp/fake_receipt.pdf",
        file_size=1024,
        uploaded_by=user_b.id,
    )
    db.session.add(doc_b)
    db.session.commit()

    # TEST: Student A attempts to access Student B's document
    allowed_a, reason_a = can_access_document(user_a, doc_b)
    assert allowed_a is False
    assert "Access denied" in reason_a

    # TEST: Student B accesses their own document
    allowed_b, reason_b = can_access_document(user_b, doc_b)
    assert allowed_b is True
    assert "Authorized as document owner" in reason_b
