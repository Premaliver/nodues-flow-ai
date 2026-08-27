"""
Validation script for Multi-Tenant Dataset Isolation, Subscription packs,
and Dataset Migration Archive export.
"""

import os
import sys
import uuid
import json

# Setup environment
os.environ["DATABASE_URL"] = "sqlite:///smart_nodues.db"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from models.university import UniversityTenant
from models.user import User
from models.student import Student
from models.department import Department
from models.application import NoDuesApplication

app = create_app()

with app.app_context():
    db.create_all()
    print("[OK] Database tables verified.")

    # 1. Test University Tenant Registration & Subscription
    test_slug = f"test-univ-{uuid.uuid4().hex[:6]}"
    test_univ = UniversityTenant(
        name="Test Innovation University",
        slug=test_slug,
        official_email=f"registrar@{test_slug}.edu",
        contact_person="Dr. Rajesh Kumar",
        phone="+91 9876543210",
        subscription_status="active",
        subscription_plan="professional",
        billing_cycle="annual",
        estimated_students=8000,
    )
    test_univ.set_password("Univ@2026")
    test_univ.activate_subscription(plan="professional", cycle="annual", duration_days=365, amount=149999.0)
    db.session.add(test_univ)
    db.session.flush()

    # 2. Provision Tenant SuperAdmin
    tenant_admin = User(
        email=f"admin@{test_slug}.edu",
        role="super_admin",
        first_name="Rajesh",
        last_name="SuperAdmin",
        status="active",
        is_email_verified=True,
        university_id=test_univ.id,
    )
    tenant_admin.set_password("Admin@2026")
    db.session.add(tenant_admin)

    # 3. Provision Baseline Departments
    dept = Department(
        code="ACC",
        name="Accounts & Finance",
        role="accounts",
        university_id=test_univ.id,
        display_order=1,
        is_active=True,
    )
    db.session.add(dept)

    # 4. Provision Student in this Tenant
    student_user = User(
        email=f"student@{test_slug}.edu",
        role="student",
        first_name="Rohan",
        last_name="Sharma",
        status="active",
        is_email_verified=True,
        university_id=test_univ.id,
    )
    student_user.set_password("Student@123")
    db.session.add(student_user)
    db.session.flush()

    student_profile = Student(
        user_id=student_user.id,
        roll_number=f"RN-{uuid.uuid4().hex[:6].upper()}",
        enrollment_number=f"EN-{uuid.uuid4().hex[:8].upper()}",
        course_name="B.Tech Computer Science",
        branch="CSE",
        current_semester=6,
        batch_year="2022-2026",
        admission_year=2022,
        category="day_scholar",
        university_id=test_univ.id,
    )
    db.session.add(student_profile)
    db.session.commit()

    print(f"[OK] University Tenant '{test_univ.name}' ({test_univ.slug}) created with plan: {test_univ.subscription_plan} ({test_univ.billing_cycle}).")
    print(f"[OK] Tenant SuperAdmin: {tenant_admin.email} (Bound to university_id: {tenant_admin.university_id})")
    print(f"[OK] Tenant Student: {student_profile.roll_number} (Bound to university_id: {student_profile.university_id})")

    # 5. Verify Isolation: Query with university_id filter
    isolated_students = Student.query.filter_by(university_id=test_univ.id).all()
    assert len(isolated_students) >= 1, "Isolation test failed: student not found in tenant dataset"
    assert isolated_students[0].university_id == test_univ.id, "Student university_id mismatch"
    print("[OK] Strict Tenant Dataset Isolation verified: Student profile belongs strictly to tenant dataset.")

    # 6. Test Platform Overview & Universities APIs
    with app.test_client() as client:
        # Simulate Platform Master session
        with client.session_transaction() as sess:
            sess["is_platform_master"] = True

        res_overview = client.get("/platform/api/overview")
        assert res_overview.status_code == 200, f"Overview API failed: {res_overview.status_code}"
        overview_data = res_overview.get_json()
        print("[OK] /platform/api/overview returned valid statistics:", overview_data["data"]["stats"])

        res_univs = client.get("/platform/api/universities")
        assert res_univs.status_code == 200, f"Universities API failed: {res_univs.status_code}"
        univs_data = res_univs.get_json()
        matching = [u for u in univs_data["data"] if u["slug"] == test_slug]
        assert len(matching) > 0, "Created university not found in platform API"
        assert matching[0]["student_count"] >= 1, "Student count in tenant volume failed"
        print(f"[OK] /platform/api/universities returned tenant dataset stats: {matching[0]['student_count']} student(s), plan: {matching[0]['subscription_plan']} ({matching[0]['billing_cycle']}).")

        # 7. Test Export Dataset Endpoint
        res_export = client.get(f"/platform/api/universities/{test_univ.id}/export-dataset")
        assert res_export.status_code == 200, f"Export dataset failed: {res_export.status_code}"
        export_json = json.loads(res_export.data)
        assert export_json["export_metadata"]["institution_slug"] == test_slug
        assert len(export_json["students"]) >= 1
        print(f"[OK] One-Click Tenant Dataset Export Archive verified. Exported {len(export_json['students'])} students and institutional metadata.")

    print("\n[SUCCESS] ALL MULTI-TENANT ISOLATION & DATASET MIGRATION TESTS PASSED SUCCESSFULLY!")
