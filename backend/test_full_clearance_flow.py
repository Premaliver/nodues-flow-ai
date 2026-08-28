"""
Comprehensive End-to-End Verification Test Script for Smart NoDues AI.
Tests:
1. Student Application Submission with Compulsory Fee Receipts.
2. Document/Receipt Storage in Database & Availability via /api/documents/<app_id>.
3. Sequential Multi-Department Approvals (Hostel, Mess, Scholarship, Accounts, HOD).
4. Examination Department Preceding Clearance Validation & Admit Card Generation.
5. Super Admin Application & Document Visibility.
6. Public Admit Card Verification.
"""

import os
import sys
import io
import json

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from models.user import User
from models.student import Student
from models.university import UniversityTenant
from models.department import Department
from models.application import NoDuesApplication, ApplicationDepartment
from models.document import Document
from models.admit_card import AdmitCard
from models.semester import Semester
from flask_jwt_extended import create_access_token


def run_e2e_clearance_test():
    print("=" * 70)
    print("STARTING E2E CLEARANCE WORKFLOW & DOCUMENT VISIBILITY TEST")
    print("=" * 70)

    app = create_app("testing")
    with app.app_context():
        # Setup test data
        db.create_all()

        # 1. Ensure University
        univ = UniversityTenant.query.first()
        if not univ:
            univ = UniversityTenant(
                name="Apex Global University",
                slug="apex-global-univ",
                domain="apex.edu.in",
                is_active=True,
            )
            db.session.add(univ)
            db.session.flush()

        from utils.tenant_helpers import ensure_university_departments
        ensure_university_departments(univ.id)

        # 2. Ensure Active Semester
        from datetime import date, timedelta
        semester = Semester.query.filter_by(is_current=True).first()
        if not semester:
            semester = Semester(
                semester_number=8,
                semester_name="Semester 8 (2025-2026)",
                academic_year="2025-2026",
                start_date=date.today(),
                end_date=date.today() + timedelta(days=120),
                is_current=True,
                is_clearance_open=True,
            )
            db.session.add(semester)
            db.session.flush()

        # 3. Create or fetch Student User & Profile
        student_user = User.query.filter_by(email="student_test@apex.edu.in").first()
        if not student_user:
            student_user = User(
                email="student_test@apex.edu.in",
                first_name="Aarav",
                last_name="Sharma",
                role="student",
                status="active",
                university_id=univ.id,
            )
            student_user.set_password("StudentPass@123")
            db.session.add(student_user)
            db.session.flush()

        student_prof = Student.query.filter_by(user_id=student_user.id).first()
        if not student_prof:
            student_prof = Student(
                user_id=student_user.id,
                university_id=univ.id,
                roll_number="CSE2025-099",
                enrollment_number="ENR-2025-099",
                course_name="B.Tech Computer Science",
                branch="Computer Science & Engineering",
                current_semester=8,
                batch_year="2021-2025",
                admission_year=2021,
                category="hosteller",
                father_name="Rajesh Sharma",
                mother_name="Sunita Sharma",
                guardian_phone="9876543210",
            )
            db.session.add(student_prof)
            db.session.flush()

        # 4. Create Staff Users for each Department
        staff_roles = ["hostel", "mess", "scholarship", "accounts", "hod", "examination", "super_admin"]
        staff_user_ids = {}
        for role in staff_roles:
            user = User.query.filter_by(email=f"{role}_test@apex.edu.in").first()
            if not user:
                user = User(
                    email=f"{role}_test@apex.edu.in",
                    first_name=role.replace("_", " ").title(),
                    last_name="Officer",
                    role=role,
                    status="active",
                    university_id=univ.id,
                )
                user.set_password("StaffPass@123")
                db.session.add(user)
                db.session.flush()
            staff_user_ids[role] = str(user.id)

        student_user_id = str(student_user.id)
        db.session.commit()

        # Use Flask test client
        client = app.test_client()

        # Step A: Student creates Application
        student_token = create_access_token(identity=student_user_id)
        headers_student = {"Authorization": f"Bearer {student_token}"}

        # Clear existing applications for clean testing
        from models.notification import Notification
        from models.audit_log import AuditLog
        existing_apps = NoDuesApplication.query.filter_by(student_id=student_prof.id).all()
        for ea in existing_apps:
            # Delete approvals, docs, admit cards, notifications
            ApplicationDepartment.query.filter_by(application_id=ea.id).delete()
            Document.query.filter_by(application_id=ea.id).delete()
            AdmitCard.query.filter_by(application_id=ea.id).delete()
            Notification.query.filter_by(application_id=ea.id).delete()
            db.session.delete(ea)
        db.session.commit()

        print("\n[Step 1] Creating New No-Dues Application for Hosteller...")
        app_res = client.post(
            "/student/api/apply",
            headers=headers_student,
            json={"selected_departments": ["hostel", "mess", "scholarship"]},
        )
        print("Application Create Response:", app_res.status_code, app_res.get_json())
        assert app_res.status_code in (200, 201), "Failed to create application"
        app_json = app_res.get_json()
        app_id = app_json["data"]["application"]["id"]
        print(f"Created Application ID: {app_id}")

        # Step B: Student uploads Fee Receipts & Documents
        print("\n[Step 2] Uploading Compulsory Fee Receipts...")
        fake_exam_pdf = io.BytesIO(b"%PDF-1.4 Fake Examination Fee Receipt Content for Testing")
        up_res1 = client.post(
            f"/student/api/upload-document/{app_id}",
            headers=headers_student,
            data={"file": (fake_exam_pdf, "exam_fee_receipt_2025.pdf"), "document_type": "exam_fee_receipt"},
            content_type="multipart/form-data",
        )
        print("Upload Exam Fee Receipt:", up_res1.status_code, up_res1.get_json())
        assert up_res1.status_code == 201, "Exam receipt upload failed"
        exam_doc_id = up_res1.get_json()["data"]["document"]["id"]

        fake_next_pdf = io.BytesIO(b"%PDF-1.4 Fake Next Semester Fee Receipt Content for Testing")
        up_res2 = client.post(
            f"/student/api/upload-document/{app_id}",
            headers=headers_student,
            data={"file": (fake_next_pdf, "next_sem_fee_receipt_2025.pdf"), "document_type": "next_sem_fee_receipt"},
            content_type="multipart/form-data",
        )
        print("Upload Next Sem Fee Receipt:", up_res2.status_code, up_res2.get_json())
        assert up_res2.status_code == 201, "Next sem receipt upload failed"

        # Step C: Final Submit
        print("\n[Step 3] Submitting Application for Institutional Clearance...")
        sub_res = client.post(f"/student/api/submit/{app_id}", headers=headers_student)
        print("Submit Response:", sub_res.status_code, sub_res.get_json())
        assert sub_res.status_code == 200, "Submission failed"

        # Step D: Test Document Visibility Across All Roles
        print("\n[Step 4] Verifying Document Visibility via /api/documents/<app_id>...")
        for role in ["hostel", "mess", "scholarship", "accounts", "hod", "examination", "super_admin"]:
            tok = create_access_token(identity=staff_user_ids[role])
            doc_res = client.get(f"/api/documents/{app_id}", headers={"Authorization": f"Bearer {tok}"})
            assert doc_res.status_code == 200, f"Role {role} failed to access /api/documents: {doc_res.status_code}"
            doc_data = doc_res.get_json()["data"]
            print(f"Role [{role:12s}] sees {len(doc_data)} uploaded documents (Status: 200 OK)")
            assert len(doc_data) >= 2, f"Role {role} did not receive all uploaded documents"

        # Verify Document File Download / Streaming with Token
        print("\n[Step 5] Verifying Binary Document Streaming via /api/documents/file/<doc_id>?token=...")
        admin_tok = create_access_token(identity=staff_user_ids["super_admin"])
        stream_res = client.get(f"/api/documents/file/{exam_doc_id}?token={admin_tok}")
        assert stream_res.status_code == 200, f"Document stream failed: {stream_res.status_code}"
        assert stream_res.mimetype == "application/pdf", "MIME type mismatch"
        print(f"Document File Streamed Successfully ({len(stream_res.data)} bytes, Content-Type: {stream_res.mimetype})")

        # Step E: Sequential Department Clearance Workflow
        print("\n[Step 6] Executing Department Clearances Sequentially...")
        dept_approvals = ApplicationDepartment.query.filter_by(application_id=app_id).all()
        approvals = {ad.department.role: str(ad.id) for ad in dept_approvals}

        print(f"Application Department Clearance Steps: {list(approvals.keys())}")

        # 1. Hostel Clearance
        hostel_ad_id = approvals.get("hostel")
        assert hostel_ad_id is not None, "Hostel clearance step missing"
        h_tok = create_access_token(identity=staff_user_ids["hostel"])
        h_res = client.post(
            f"/hostel/api/process/{hostel_ad_id}",
            headers={"Authorization": f"Bearer {h_tok}"},
            json={"action": "approved", "remarks": "Room 402 inventory verified. No damages."},
        )
        print("Hostel Clearance:", h_res.status_code, h_res.get_json())
        assert h_res.status_code == 200

        # 2. Mess Clearance
        mess_ad_id = approvals.get("mess")
        assert mess_ad_id is not None, "Mess clearance step missing"
        m_tok = create_access_token(identity=staff_user_ids["mess"])
        m_res = client.post(
            f"/mess/api/process/{mess_ad_id}",
            headers={"Authorization": f"Bearer {m_tok}"},
            json={"action": "approved", "remarks": "Mess dues zero balance verified."},
        )
        print("Mess Clearance:", m_res.status_code, m_res.get_json())
        assert m_res.status_code == 200

        # 3. Scholarship Clearance
        sch_ad_id = approvals.get("scholarship")
        assert sch_ad_id is not None, "Scholarship clearance step missing"
        s_tok = create_access_token(identity=staff_user_ids["scholarship"])
        s_res = client.post(
            f"/scholarship/api/process/{sch_ad_id}",
            headers={"Authorization": f"Bearer {s_tok}"},
            json={"action": "approved", "remarks": "Scholarship disbursement cleared."},
        )
        print("Scholarship Clearance:", s_res.status_code, s_res.get_json())
        assert s_res.status_code == 200

        # 4. Accounts Clearance
        acc_ad_id = approvals.get("accounts")
        assert acc_ad_id is not None, "Accounts clearance step missing"
        a_tok = create_access_token(identity=staff_user_ids["accounts"])
        a_res = client.post(
            f"/accounts/api/process/{acc_ad_id}",
            headers={"Authorization": f"Bearer {a_tok}"},
            json={"action": "approved", "remarks": "Fee receipts audited and approved."},
        )
        print("Accounts Clearance:", a_res.status_code, a_res.get_json())
        assert a_res.status_code == 200

        # 5. Academic HOD Clearance
        hod_ad_id = approvals.get("hod")
        assert hod_ad_id is not None, "HOD clearance step missing"
        hod_tok = create_access_token(identity=staff_user_ids["hod"])
        hod_res = client.post(
            f"/hod/api/process/{hod_ad_id}",
            headers={"Authorization": f"Bearer {hod_tok}"},
            json={"action": "approved", "remarks": "All academic credits & labs verified."},
        )
        print("Academic HOD Clearance:", hod_res.status_code, hod_res.get_json())
        assert hod_res.status_code == 200

        # Step F: Examination Clearance & Admit Card Generation
        print("\n[Step 7] Examination Clearance & Admit Card Issuance...")
        exam_tok = create_access_token(identity=staff_user_ids["examination"])
        # Verify application is in Examination ready queue
        exam_dash_res = client.get("/examination/api/dashboard", headers={"Authorization": f"Bearer {exam_tok}"})
        print("Examination Dashboard:", exam_dash_res.status_code, exam_dash_res.get_json()["data"]["stats"])
        assert exam_dash_res.status_code == 200

        # Generate Admit Card
        card_res = client.post(f"/examination/api/generate-admit-card/{app_id}", headers={"Authorization": f"Bearer {exam_tok}"})
        print("Generate Admit Card:", card_res.status_code, card_res.get_json())
        assert card_res.status_code in (200, 201), "Admit card generation failed"
        card_data = card_res.get_json()["data"]
        card_number = card_data["card_number"]
        print(f"Issued Admit Card Number: {card_number}")

        # Step G: Super Admin Inspection
        print("\n[Step 8] Super Admin Dashboard Inspection...")
        admin_res = client.get(f"/superadmin/api/applications/{app_id}", headers={"Authorization": f"Bearer {admin_tok}"})
        print("Super Admin Application View:", admin_res.status_code)
        assert admin_res.status_code == 200
        admin_data = admin_res.get_json()["data"]
        print("Super Admin sees:")
        print("  - Application Status:", admin_data["application"]["status"])
        print("  - Department Approvals:", len(admin_data["department_approvals"]))
        print("  - Uploaded Documents:", len(admin_data["documents"]))
        print("  - Admit Card:", admin_data["admit_card"]["card_number"] if admin_data.get("admit_card") else "None")
        assert admin_data["application"]["status"] == "approved"
        assert len(admin_data["documents"]) >= 2
        assert admin_data["admit_card"] is not None

        # Step H: Student Dashboard and Admit Card Download
        print("\n[Step 9] Student Dashboard and Admit Card PDF Download...")
        dash_res = client.get("/student/api/dashboard", headers=headers_student)
        print("Student Dashboard Status:", dash_res.status_code)
        assert dash_res.status_code == 200
        s_dash = dash_res.get_json()["data"]
        assert len(s_dash.get("admit_cards", [])) > 0, "Student has no admit cards in dashboard"
        print(f"Student has {len(s_dash['admit_cards'])} issued admit card(s)")

        # Download Admit Card PDF
        pdf_res = client.get(f"/student/api/admit-card/{card_number}/pdf", headers=headers_student)
        print("Admit Card PDF Download Status:", pdf_res.status_code, f"({len(pdf_res.data)} bytes)")
        assert pdf_res.status_code == 200
        assert pdf_res.mimetype == "application/pdf"

        # Verify Public Web QR Verification URL
        print("\n[Step 10] Public Admit Card Verification Endpoint...")
        verify_res = client.get(f"/verify-admit-card/{card_number}")
        print("Public Verification Page Status:", verify_res.status_code)
        assert verify_res.status_code == 200

        # Step 11: Application Deletion / Cancel and Re-application Test
        print("\n[Step 11] Testing Application Cancellation / Deletion & Fresh Re-application...")
        del_res = client.post(f"/student/api/application/{app_id}/delete", headers=headers_student)
        print("Delete Application Status:", del_res.status_code, del_res.get_json())
        assert del_res.status_code == 200
        assert del_res.get_json()["success"] is True

        # Verify Student can create a brand new application immediately without 409 conflict
        re_create_res = client.post(
            "/student/api/apply",
            headers=headers_student,
            json={"selected_departments": ["hostel", "mess"]},
        )
        print("Re-Create Application Status:", re_create_res.status_code)
        assert re_create_res.status_code == 201
        new_app_id = re_create_res.get_json()["data"]["application"]["id"]
        print(f"Successfully Created Fresh Application ID: {new_app_id}")

        print("\n" + "=" * 70)
        print("ALL 11 VERIFICATION CHECKS (INCLUDING DELETE & RE-APPLY) PASSED PERFECTLY! 100% WORKING.")
        print("=" * 70)


if __name__ == "__main__":
    run_e2e_clearance_test()
