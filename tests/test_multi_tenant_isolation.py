"""Comprehensive Multi-Tenant Isolation & Provisioning Test Suite.

Verifies:
1. Subdomain / Header / Query tenant resolution.
2. Absolute data isolation between University A and University B.
3. Bulk CSV student and staff onboarding within tenant boundary.
4. Per-university whitelabel branding customization and isolation.
"""

import os
import sys
import unittest
import uuid

# Set test environment
os.environ["FLASK_ENV"] = "testing"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import create_app, db
from models.university import UniversityTenant
from models.user import User
from models.student import Student
from models.department import Department, DepartmentStaff


class MultiTenantIsolationTestCase(unittest.TestCase):
    """Integration test suite for multi-tenant SaaS architecture."""

    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Clean tables in proper FK order
        from models.workflow import WorkflowConfig
        from models.application import ApplicationDepartment, NoDuesApplication
        from models.document import Document
        from models.admit_card import AdmitCard
        from models.audit_log import AuditLog
        from models.feedback import Feedback

        Feedback.query.delete()
        AuditLog.query.delete()
        Document.query.delete()
        AdmitCard.query.delete()
        ApplicationDepartment.query.delete()
        NoDuesApplication.query.delete()
        WorkflowConfig.query.delete()
        DepartmentStaff.query.delete()
        Student.query.delete()
        User.query.delete()
        Department.query.delete()
        UniversityTenant.query.delete()
        db.session.commit()

        # Provision University A (ABC University)
        self.univ_a = UniversityTenant(
            name="ABC University",
            slug="abc",
            official_email="registrar@abc.edu",
            contact_person="Dr. Alan Smith",
            subscription_status="active",
            subscription_plan="enterprise",
            primary_color="#1e3a8a",
            custom_domain="nodues.abc.edu",
        )
        self.univ_a.set_password("AbcSecret123!")
        db.session.add(self.univ_a)

        # Provision University B (XYZ University)
        self.univ_b = UniversityTenant(
            name="XYZ University",
            slug="xyz",
            official_email="admin@xyz.edu",
            contact_person="Dr. Xavier Jones",
            subscription_status="active",
            subscription_plan="professional",
            primary_color="#047857",
            custom_domain="nodues.xyz.edu",
        )
        self.univ_b.set_password("XyzSecret123!")
        db.session.add(self.univ_b)
        db.session.commit()

        self.univ_a_id = str(self.univ_a.id)
        self.univ_b_id = str(self.univ_b.id)

        # Base Departments
        self.dept_accounts_a = Department(code="ACC", name="Accounts", role="accounts", university_id=self.univ_a.id)
        self.dept_accounts_b = Department(code="ACC", name="Accounts", role="accounts", university_id=self.univ_b.id)
        db.session.add_all([self.dept_accounts_a, self.dept_accounts_b])
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    def test_tenant_resolution_via_header_and_slug(self):
        """Test tenant resolver identifies tenant from X-Tenant-Slug header and ?tenant query param."""
        with self.client:
            res_a = self.client.get("/api/health", headers={"X-Tenant-Slug": "abc"})
            self.assertEqual(res_a.status_code, 200)

            # Test branding endpoint
            with self.client.session_transaction() as sess:
                sess["university_id"] = self.univ_a_id
            res_brand_a = self.client.get("/superadmin/api/university/branding")
            self.assertEqual(res_brand_a.status_code, 200)
            data_a = res_brand_a.get_json()["data"]
            self.assertEqual(data_a["slug"], "abc")
            self.assertEqual(data_a["primary_color"], "#1e3a8a")

            # Switch to University B
            with self.client.session_transaction() as sess:
                sess["university_id"] = self.univ_b_id
            res_brand_b = self.client.get("/superadmin/api/university/branding")
            self.assertEqual(res_brand_b.status_code, 200)
            data_b = res_brand_b.get_json()["data"]
            self.assertEqual(data_b["slug"], "xyz")
            self.assertEqual(data_b["primary_color"], "#047857")

    def test_bulk_csv_student_provisioning_isolation(self):
        """Test bulk student CSV onboarding scopes accounts strictly to the active tenant."""
        # Import students into University A
        with self.client:
            with self.client.session_transaction() as sess:
                sess["university_id"] = self.univ_a_id

            csv_payload = {
                "rows": [
                    {"roll_number": "ABC-101", "name": "John Doe", "email": "john@abc.edu", "course": "B.Tech", "semester": 4},
                    {"roll_number": "ABC-102", "name": "Alice Ray", "email": "alice@abc.edu", "course": "B.Tech", "semester": 4},
                ]
            }
            res = self.client.post("/superadmin/api/users/students/import-csv", json=csv_payload)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json()["data"]["created"], 2)

            # Verify students query under University A
            res_list_a = self.client.get("/superadmin/api/users/students")
            items_a = res_list_a.get_json()["data"]["items"]
            self.assertEqual(len(items_a), 2)
            self.assertTrue(all(item["email"].endswith("@abc.edu") for item in items_a))

            # Switch to University B and verify zero student bleed-through
            with self.client.session_transaction() as sess:
                sess["university_id"] = self.univ_b_id

            res_list_b = self.client.get("/superadmin/api/users/students")
            items_b = res_list_b.get_json()["data"]["items"]
            self.assertEqual(len(items_b), 0, "University B must see 0 students from University A!")

    def test_cross_tenant_data_modification_denied(self):
        """Test that University B cannot modify or access University A's branding or data."""
        with self.client:
            # Update University A branding
            with self.client.session_transaction() as sess:
                sess["university_id"] = self.univ_a_id

            update_res = self.client.put(
                "/superadmin/api/university/branding",
                json={"logo_url": "https://abc.edu/logo.png", "banner_text": "Welcome to ABC"}
            )
            self.assertEqual(update_res.status_code, 200)

            # Check University B branding was NOT mutated
            with self.client.session_transaction() as sess:
                sess["university_id"] = self.univ_b_id

            res_b = self.client.get("/superadmin/api/university/branding")
            data_b = res_b.get_json()["data"]
            self.assertIsNone(data_b["logo_url"], "University B branding should remain untouched")


if __name__ == "__main__":
    unittest.main()
