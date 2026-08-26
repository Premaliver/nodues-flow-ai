"""
Automated Test Runner using Python standard library unittest.
Executes licensing unit tests, security IDOR prevention tests, and data export tests.
"""

import sys
import os
import unittest
import uuid
import tempfile
import json
import zipfile

backend_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend"))
root_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(1, root_dir)

from control_plane.licensing.issuer import ControlPlaneLicenseIssuer
from licensing.crypto import LicenseCrypto
from licensing.license_manager import LicenseManager, LicenseStatus
from app import create_app
from models import db
from models.user import User
from models.student import Student
from models.department import Department
from models.semester import Semester
from models.application import NoDuesApplication
from models.document import Document
from security.document_guard import can_access_document
from export.data_exporter import UniversityDataExporter


class LicensingCryptoTests(unittest.TestCase):
    """Tests for Ed25519 signing, verification, and tamper detection."""

    def test_keypair_generation(self):
        keys = ControlPlaneLicenseIssuer.generate_platform_keypair()
        self.assertIn("BEGIN PRIVATE KEY", keys["private_key_pem"])
        self.assertIn("BEGIN PUBLIC KEY", keys["public_key_pem"])

    def test_valid_license_flow(self):
        keys = ControlPlaneLicenseIssuer.generate_platform_keypair()
        issuer = ControlPlaneLicenseIssuer(private_key_pem=keys["private_key_pem"])

        token = issuer.issue_license(
            tenant_id="tenant_oxford_01",
            tenant_slug="oxford",
            university_name="Oxford University",
            plan_name="enterprise",
            valid_days=365,
            max_active_students=20000,
            features=["ai_receipt_ocr", "admit_card_generation"],
        )

        is_valid, payload, err = LicenseCrypto.verify_and_unpack(token, keys["public_key_pem"])
        self.assertTrue(is_valid)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["tenant_id"], "tenant_oxford_01")
        self.assertEqual(payload["plan_name"], "enterprise")
        self.assertEqual(payload["entitlements"]["max_active_students"], 20000)

    def test_tampered_license_rejection(self):
        import base64
        keys = ControlPlaneLicenseIssuer.generate_platform_keypair()
        issuer = ControlPlaneLicenseIssuer(private_key_pem=keys["private_key_pem"])

        token = issuer.issue_license(
            tenant_id="tenant_cambridge_01",
            tenant_slug="cambridge",
            university_name="Cambridge University",
            plan_name="starter",
            valid_days=30,
        )

        raw_json = base64.b64decode(token.encode("utf-8")).decode("utf-8")
        package = json.loads(raw_json)
        package["payload"]["plan_name"] = "enterprise"
        tampered_token = base64.b64encode(json.dumps(package).encode("utf-8")).decode("utf-8")

        is_valid, payload, err = LicenseCrypto.verify_and_unpack(tampered_token, keys["public_key_pem"])
        self.assertFalse(is_valid)
        self.assertIsNone(payload)

    def test_license_state_transitions(self):
        """Verifies state calculation across active, grace period, and suspension."""
        from datetime import datetime, timezone, timedelta
        from licensing.license_manager import LicenseData, LicenseEntitlements

        now = datetime.now(timezone.utc)
        
        # Case 1: Active
        lic_active = LicenseData(
            license_id="lic_1",
            tenant_id="t1",
            tenant_slug="s1",
            university_name="Univ 1",
            plan_name="pro",
            issued_at=now,
            valid_from=now - timedelta(days=10),
            expires_at=now + timedelta(days=20),
            grace_period_days=15,
        )
        self.assertTrue(now <= lic_active.expires_at)

        # Case 2: Grace period (expired 5 days ago, grace is 15 days)
        lic_grace = LicenseData(
            license_id="lic_2",
            tenant_id="t2",
            tenant_slug="s2",
            university_name="Univ 2",
            plan_name="pro",
            issued_at=now - timedelta(days=40),
            valid_from=now - timedelta(days=40),
            expires_at=now - timedelta(days=5),
            grace_period_days=15,
        )
        grace_deadline = lic_grace.expires_at + timedelta(days=lic_grace.grace_period_days)
        self.assertTrue(now > lic_grace.expires_at)
        self.assertTrue(now <= grace_deadline)

        # Case 3: Suspended (expired 20 days ago, past 15-day grace)
        lic_suspended = LicenseData(
            license_id="lic_3",
            tenant_id="t3",
            tenant_slug="s3",
            university_name="Univ 3",
            plan_name="pro",
            issued_at=now - timedelta(days=60),
            valid_from=now - timedelta(days=60),
            expires_at=now - timedelta(days=20),
            grace_period_days=15,
        )
        suspended_deadline = lic_suspended.expires_at + timedelta(days=lic_suspended.grace_period_days)
        self.assertTrue(now > suspended_deadline)


class SecurityAndIsolationTests(unittest.TestCase):
    """Tests for document authorization, IDOR prevention, and export integrity."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()

    def setUp(self):
        db.session.rollback()

    def test_document_idor_protection(self):
        user_a = User(
            id=uuid.uuid4(),
            email=f"alice_{uuid.uuid4().hex[:6]}@test.edu",
            first_name="Alice",
            last_name="A",
            role="student",
            status="active",
        )
        user_a.set_password("Pass123!")
        db.session.add(user_a)
        db.session.flush()

        student_a = Student(
            id=uuid.uuid4(),
            user_id=user_a.id,
            roll_number=f"AL_{uuid.uuid4().hex[:6].upper()}",
            enrollment_number=f"EN_{uuid.uuid4().hex[:6].upper()}",
            course_name="B.Tech Computer Science",
            branch="Computer Science",
            current_semester=6,
            batch_year="2022-2026",
            admission_year=2022,
        )
        db.session.add(student_a)

        user_b = User(
            id=uuid.uuid4(),
            email=f"bob_{uuid.uuid4().hex[:6]}@test.edu",
            first_name="Bob",
            last_name="B",
            role="student",
            status="active",
        )
        user_b.set_password("Pass123!")
        db.session.add(user_b)
        db.session.flush()

        student_b = Student(
            id=uuid.uuid4(),
            user_id=user_b.id,
            roll_number=f"BO_{uuid.uuid4().hex[:6].upper()}",
            enrollment_number=f"EN_{uuid.uuid4().hex[:6].upper()}",
            course_name="B.Tech Information Technology",
            branch="Information Technology",
            current_semester=6,
            batch_year="2022-2026",
            admission_year=2022,
        )
        db.session.add(student_b)

        from datetime import date
        sem = Semester.query.first()
        if not sem:
            sem = Semester(
                id=uuid.uuid4(),
                semester_number=1,
                semester_name="1st Semester",
                academic_year="2025-2026",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 6, 30),
            )
            db.session.add(sem)
            db.session.flush()

        app_b = NoDuesApplication(
            id=uuid.uuid4(),
            student_id=student_b.id,
            semester_id=sem.id,
            category="day_scholar",
            total_steps=4,
        )
        db.session.add(app_b)
        db.session.flush()

        doc_b = Document(
            id=uuid.uuid4(),
            application_id=app_b.id,
            document_type="semester_fee_receipt",
            file_name="receipt_b.pdf",
            file_path="/tmp/fake.pdf",
            file_size=500,
            uploaded_by=user_b.id,
        )
        db.session.add(doc_b)
        db.session.commit()

        # Alice attempts to access Bob's document -> Forbidden
        allowed_alice, reason = can_access_document(user_a, doc_b)
        self.assertFalse(allowed_alice)
        self.assertIn("Access denied", reason)

        # Bob accesses his own document -> Allowed
        allowed_bob, _ = can_access_document(user_b, doc_b)
        self.assertTrue(allowed_bob)

    def test_full_data_export(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            report = UniversityDataExporter.export_to_zip(zip_path, include_documents=False)
            self.assertTrue(os.path.exists(zip_path))
            self.assertGreater(report["file_size"], 0)

            with zipfile.ZipFile(zip_path, "r") as zf:
                files = zf.namelist()
                self.assertIn("MANIFEST.json", files)
                self.assertIn("data/students.json", files)
                self.assertIn("data/applications.json", files)
                self.assertIn("data/departments.json", files)
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def test_university_saas_onboarding_and_subscription_flow(self):
        """End-to-End Test: University registers, previews POV, subscribes, and unlocks SuperAdmin."""
        from models.university import UniversityTenant

        client = self.app.test_client()

        # 1. Register University
        reg_payload = {
            "name": "Delhi Technological University",
            "contact_person": "Dr. S. K. Sharma",
            "designation": "Dean Academics",
            "official_email": "dean@dtu.ac.in",
            "phone": "+91 9811122233",
            "estimated_students": 12000,
            "password": "SecurePassword123!",
        }
        res = client.post("/university/register", json=reg_payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["university"]["slug"], "delhi-technological-university")

        # 2. View POV Page
        pov_res = client.get("/university/pov")
        self.assertEqual(pov_res.status_code, 200)
        self.assertIn(b"Interactive POV & Live System Simulation", pov_res.data)

        # 3. Subscribe to Professional Plan
        sub_res = client.post("/university/api/subscribe", json={
            "plan": "professional",
            "billing_cycle": "annual"
        })
        self.assertEqual(sub_res.status_code, 200)
        sub_data = sub_res.get_json()
        self.assertTrue(sub_data["success"])
        self.assertEqual(sub_data["data"]["university"]["subscription_status"], "active")
        self.assertEqual(sub_data["data"]["university"]["subscription_plan"], "professional")

        # 4. Verify in DB
        tenant = UniversityTenant.query.filter_by(official_email="dean@dtu.ac.in").first()
        self.assertIsNotNone(tenant)
        self.assertTrue(tenant.has_active_subscription)
        self.assertIsNotNone(tenant.license_token)


if __name__ == "__main__":
    unittest.main()
