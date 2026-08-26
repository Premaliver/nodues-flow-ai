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

    # If users or departments already exist, do not overwrite
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

    # 2. Create users & roles
    users_data = [
        ("kprem@rayatbahra.edu", "super_admin", "Prem", "Kumar", "+91-9876543210", "Prem@2004"),
        ("accounts@rayatbahra.edu", "accounts", "Priya", "Sharma", "+91-9876543211", "123456"),
        ("hostel@rayatbahra.edu", "hostel", "Rajesh", "Kumar", "+91-9876543212", "123456"),
        ("mess@rayatbahra.edu", "mess", "Amit", "Verma", "+91-9876543213", "123456"),
        ("transport@rayatbahra.edu", "transport", "Sneha", "Patel", "+91-9876543214", "123456"),
        ("scholarship@rayatbahra.edu", "scholarship", "Vikram", "Singh", "+91-9876543215", "123456"),
        ("hod.cse@rayatbahra.edu", "hod", "Dr. Arvind", "Gupta", "+91-9876543216", "123456"),
        ("examination@rayatbahra.edu", "examination", "Neha", "Mehta", "+91-9876543217", "123456"),
        ("student@rayatbahra.edu", "student", "Aditi", "Sharma", "+91-9876543218", "123456"),
    ]

    for email, role, fname, lname, phone, pw in users_data:
        user = User(
            email=email,
            role=role,
            first_name=fname,
            last_name=lname,
            phone=phone,
            is_email_verified=True,
            status="active",
        )
        user.set_password(pw)
        db.session.add(user)
        db.session.flush()

        if role == "student":
            student = Student(
                user_id=user.id,
                roll_number="RBU/22CSE/0142",
                enrollment_number="ENR/2022/4257",
                course_name="B.Tech Computer Science Engineering",
                branch="Computer Science & Engineering",
                current_semester=6,
                batch_year="2022-2026",
                admission_year=2022,
                category="hosteller",
                father_name="Mr. Rajesh Sharma",
                mother_name="Mrs. Kavita Sharma",
                guardian_phone="+91-9876543219",
                guardian_email="rajesh.sharma@email.com",
                permanent_address="123, Sector 15, Chandigarh",
                city="Chandigarh",
                state="Punjab",
                pincode="160015",
            )
            db.session.add(student)
        elif role in ["accounts", "hostel", "mess", "transport", "scholarship", "hod", "examination"]:
            dept_record = Department.query.filter_by(role=role).first()
            if dept_record:
                staff_link = DepartmentStaff(
                    user_id=user.id,
                    department_id=dept_record.id,
                    is_active=True,
                )
                db.session.add(staff_link)

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

    db.session.commit()
    print("[OK] Institutional database seeded successfully!")
