# type: ignore
# pyright: reportGeneralTypeIssues=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false
"""
Seed data script for Smart NoDues AI.
Provides initial institutional structure: departments, staff accounts, workflows, sample student & semester.
"""

import os
import sys
from datetime import datetime, timezone
from typing import no_type_check

# Ensure backend directory is in sys.path for standalone or subfolder execution
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from models import db
    from models.user import User
    from models.student import Student
    from models.department import Department, DepartmentStaff
    from models.semester import Semester
    from models.workflow import WorkflowConfig
except ImportError:
    from backend.models import db
    from backend.models.user import User
    from backend.models.student import Student
    from backend.models.department import Department, DepartmentStaff
    from backend.models.semester import Semester
    from backend.models.workflow import WorkflowConfig


@no_type_check
def seed_data() -> None:
    """Seed the database with sample data if empty."""
    db.create_all()

    # Seed default university tenant if empty
    from models.university import UniversityTenant
    if not UniversityTenant.query.first():
        print("[*] Seeding default university tenant...")
        demo_univ = UniversityTenant(
            name="Rayat Bahra University",
            slug="rayat-bahra-university",
            official_email="registrar@rayatbahra.edu",
            contact_person="Prof. Arvind Kumar",
            designation="Registrar",
            phone="+91-9876543210",
            website="https://rayatbahra.edu",
            state="Punjab",
            estimated_students=10000,
            subscription_status="unsubscribed",
            subscription_plan="none",
        )
        demo_univ.set_password("Prem@2004")
        db.session.add(demo_univ)
        db.session.commit()
        print("[OK] Demo university tenant seeded (registrar@rayatbahra.edu)!")

    # If users or departments already exist, do not re-seed them
    if User.query.first() or Department.query.first():
        return

    print("[*] Seeding database with institutional departments & users...")

    # 1. Create standard institutional departments
    departments_data = [
        ("ACC", "Accounts Department", "Financial clearance, fee verification", "accounts", 1),
        ("HOS", "Hostel Department", "Hostel accommodation clearance", "hostel", 2),
        ("MESS", "Mess Department", "Mess dues clearance", "mess", 3),
        ("TRP", "Transport Department", "Transport fee clearance", "transport", 4),
        ("SCH", "Scholarship Department", "Scholarship verification", "scholarship", 5),
        ("HOD", "Head of Department", "Academic clearance", "hod", 6),
        ("EXM", "Examination Department", "Final clearance and admit card", "examination", 7),
    ]
    for code, name, desc, role, order in departments_data:
        dept = Department(
            code=code,
            name=name,
            description=desc,
            role=role,
            display_order=order,
            is_active=True,
        )
        db.session.add(dept)
    db.session.commit()

    # 2. Create Master Super Admin User (Campus Controller)
    sa_user = User(
        email="kprem@rayatbahra.edu",
        role="super_admin",
        first_name="Prem",
        last_name="Admin",
        phone="+91-9876543210",
        is_email_verified=True,
        status="active",
    )
    sa_user.set_password("Prem@2004")
    db.session.add(sa_user)
    db.session.flush()

    # 3. Create current semester
    semester = Semester(
        semester_number=6,
        semester_name="Sixth Semester",
        academic_year="2025-2026",
        start_date=datetime(2025, 7, 1),
        end_date=datetime(2025, 12, 31),
        is_current=True,
        is_clearance_open=True,
    )
    db.session.add(semester)

    # 4. Create workflow configs
    all_depts = Department.query.order_by(Department.display_order).all()
    for idx, d in enumerate(all_depts):
        wf = WorkflowConfig(
            category="hosteller",
            department_id=d.id,
            step_order=idx + 1,
            is_required=True,
            is_active=True,
        )
        db.session.add(wf)

    # 5. Create default university tenant if none exists
    from models.university import UniversityTenant
    if not UniversityTenant.query.first():
        demo_univ = UniversityTenant(
            name="Rayat Bahra University",
            slug="rayat-bahra-university",
            official_email="registrar@rayatbahra.edu",
            contact_person="Prof. Arvind Kumar",
            designation="Registrar",
            phone="+91-9876543210",
            website="https://rayatbahra.edu",
            state="Punjab",
            estimated_students=10000,
            subscription_status="unsubscribed",
            subscription_plan="none",
        )
        demo_univ.set_password("Prem@2004")
        db.session.add(demo_univ)

    db.session.commit()
    print("[OK] Institutional database seeded successfully!")
