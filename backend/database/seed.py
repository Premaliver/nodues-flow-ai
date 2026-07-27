"""
Seed data script for Smart NoDues AI.
Run via: flask seed-db
"""

from datetime import datetime, timezone

from app import create_app, bcrypt
from models import db
from models.user import User
from models.student import Student
from models.semester import Semester


def seed_data() -> None:
    """Seed the database with sample data for development."""
    from models.department import Department

    # Check if data already exists
    if User.query.first():
        print("Database already contains data. Skipping seed.")
        return

    # Create departments if they don't exist
    if Department.query.count() == 0:
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
        print("✓ Departments created")

# Create super admin
    admin = User(
        email="kprem@rayatbahra.edu",
        password_hash=bcrypt.generate_password_hash("Prem@2004").decode("utf-8"),
        role="super_admin",
        first_name="Prem",
        last_name="Kumar",
        phone="+91-9876543210",
        is_email_verified=True,
        status="active",
    )
    db.session.add(admin)

# Create Accounts staff
    accounts_user = User(
        email="accounts@rayatbahra.edu",
        password_hash=bcrypt.generate_password_hash("Accounts@123").decode("utf-8"),
        role="accounts",
        first_name="Priya",
        last_name="Sharma",
        phone="+91-9876543211",
        is_email_verified=True,
        status="active",
    )
    db.session.add(accounts_user)

    # Create Hostel staff
    hostel_user = User(
        email="hostel@rayatbahra.edu",
        password_hash=bcrypt.generate_password_hash("Hostel@123").decode("utf-8"),
        role="hostel",
        first_name="Rajesh",
        last_name="Kumar",
        phone="+91-9876543212",
        is_email_verified=True,
        status="active",
    )
    db.session.add(hostel_user)

    # Create Mess staff
    mess_user = User(
        email="mess@rayatbahra.edu",
        password_hash=bcrypt.generate_password_hash("Mess@123").decode("utf-8"),
        role="mess",
        first_name="Amit",
        last_name="Verma",
        phone="+91-9876543213",
        is_email_verified=True,
        status="active",
    )
    db.session.add(mess_user)

    # Create Transport staff
    transport_user = User(
        email="transport@rayatbahra.edu",
        password_hash=bcrypt.generate_password_hash("Transport@123").decode("utf-8"),
        role="transport",
        first_name="Sneha",
        last_name="Patel",
        phone="+91-9876543214",
        is_email_verified=True,
        status="active",
    )
    db.session.add(transport_user)

    # Create Scholarship staff
    scholarship_user = User(
        email="scholarship@rayatbahra.edu",
        password_hash=bcrypt.generate_password_hash("Scholarship@123").decode("utf-8"),
        role="scholarship",
        first_name="Vikram",
        last_name="Singh",
        phone="+91-9876543215",
        is_email_verified=True,
        status="active",
    )
    db.session.add(scholarship_user)

    # Create HOD
    hod_user = User(
        email="hod.cse@rayatbahra.edu",
        password_hash=bcrypt.generate_password_hash("HOD@123").decode("utf-8"),
        role="hod",
        first_name="Dr. Arvind",
        last_name="Gupta",
        phone="+91-9876543216",
        is_email_verified=True,
        status="active",
    )
    db.session.add(hod_user)

    # Create Examination staff
    exam_user = User(
        email="examination@rayatbahra.edu",
        password_hash=bcrypt.generate_password_hash("Exam@123").decode("utf-8"),
        role="examination",
        first_name="Neha",
        last_name="Mehta",
        phone="+91-9876543217",
        is_email_verified=True,
        status="active",
    )
    db.session.add(exam_user)

    # Create Sample Student User
    student_user = User(
        email="student@rayatbahra.edu",
        password_hash=bcrypt.generate_password_hash("Student@123").decode("utf-8"),
        role="student",
        first_name="Aditi",
        last_name="Sharma",
        phone="+91-9876543218",
        is_email_verified=True,
        status="active",
    )
    db.session.add(student_user)
    db.session.flush()

    # Create Student Profile
    student = Student(
        user_id=student_user.id,
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

    # Create current semester
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

    db.session.commit()
    print("✓ Seed data inserted successfully!")
    print("  - 9 users created (1 admin, 7 staff, 1 student)")
    print("  - 1 student profile created")
    print("  - 1 semester created")
    print("  - 7 departments created")

