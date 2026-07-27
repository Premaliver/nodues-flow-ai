"""
Deploy Fix Script - Run this once on Render after deployment.
Resets and seeds the database with correct schema and data.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db

app = create_app("production")

with app.app_context():
    # Create all tables with the fixed GUID types
    db.create_all()
    print("✓ Database tables created with fixed GUID types")

    from models.user import User
    from models.student import Student
    from models.department import Department, DepartmentStaff
    from models.semester import Semester
    from models.workflow import WorkflowConfig
    from models.system_setting import SystemSetting
    from datetime import datetime, timezone

    # Don't seed if data exists
    if User.query.first():
        print("→ Database already has data. Skipping seed.")
    else:
        # Create departments
        depts_data = [
            ("ACC", "Accounts Department", "Financial clearance, fee verification", "accounts", 1),
            ("HOS", "Hostel Department", "Hostel accommodation clearance", "hostel", 2),
            ("MESS", "Mess Department", "Mess dues clearance", "mess", 3),
            ("TRP", "Transport Department", "Transport fee clearance", "transport", 4),
            ("SCH", "Scholarship Department", "Scholarship verification", "scholarship", 5),
            ("HOD", "Head of Department", "Academic clearance", "hod", 6),
            ("EXM", "Examination Department", "Final clearance and admit card", "examination", 7),
        ]
        for code, name, desc, role, order in depts_data:
            db.session.add(Department(code=code, name=name, description=desc, role=role, display_order=order, is_active=True))
        db.session.commit()
        print("✓ 7 Departments created")

        # Create users
        users_data = [
            ("kprem@rayatbahra.edu", "super_admin", "Prem", "Kumar", "+91-9876543210"),
            ("accounts@rayatbahra.edu", "accounts", "Priya", "Sharma", "+91-9876543211"),
            ("hostel@rayatbahra.edu", "hostel", "Rajesh", "Kumar", "+91-9876543212"),
            ("mess@rayatbahra.edu", "mess", "Amit", "Verma", "+91-9876543213"),
            ("transport@rayatbahra.edu", "transport", "Sneha", "Patel", "+91-9876543214"),
            ("scholarship@rayatbahra.edu", "scholarship", "Vikram", "Singh", "+91-9876543215"),
            ("hod.cse@rayatbahra.edu", "hod", "Dr. Arvind", "Gupta", "+91-9876543216"),
            ("examination@rayatbahra.edu", "examination", "Neha", "Mehta", "+91-9876543217"),
            ("student@rayatbahra.edu", "student", "Aditi", "Sharma", "+91-9876543218"),
        ]
        created_users = []
        for email, role, fname, lname, phone in users_data:
            password = "Prem@2004" if role == "super_admin" else "123456"
            user = User(email=email, role=role, first_name=fname, last_name=lname, phone=phone, is_email_verified=True, status="active")
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            created_users.append(user)

        # Student profile
        su = created_users[-1]
        db.session.add(Student(
            user_id=su.id, roll_number="RBU/22CSE/0142", enrollment_number="ENR/2022/4257",
            course_name="B.Tech Computer Science Engineering", branch="Computer Science & Engineering",
            current_semester=6, batch_year="2022-2026", admission_year=2022, category="hosteller",
            father_name="Mr. Rajesh Sharma", mother_name="Mrs. Kavita Sharma",
            guardian_phone="+91-9876543219", guardian_email="rajesh.sharma@email.com",
            permanent_address="123, Sector 15, Chandigarh", city="Chandigarh", state="Punjab", pincode="160015",
        ))

        # Semester
        db.session.add(Semester(
            semester_number=6, semester_name="Sixth Semester", academic_year="2025-2026",
            start_date=datetime(2025, 7, 1), end_date=datetime(2025, 12, 31),
            is_current=True, is_clearance_open=True,
        ))

        # Workflow configs
        for i, dept in enumerate(Department.query.order_by(Department.display_order).all()):
            db.session.add(WorkflowConfig(category="hosteller", department_id=dept.id, step_order=i + 1, is_required=True, is_active=True))

        db.session.commit()

        print("✓ 9 Users created")
        print("✓ 1 Student profile created")
        print("✓ 1 Semester created")
        print("✓ 7 Workflow steps configured")

        # Verify passwords
        print("\n=== PASSWORD VERIFICATION ===")
        for u in User.query.all():
            expected_pw = "Prem@2004" if u.role == "super_admin" else "123456"
            ok = u.check_password(expected_pw)
            status = "✓ OK" if ok else "✗ FAIL"
            print(f"  {u.email} ({u.role}): {status}")

    print("\n" + "="*60)
    print("  DATABASE READY!")
    print("="*60)
    print("\n  Super Admin: kprem@rayatbahra.edu / Prem@2004")
    print("  Others: role@rayatbahra.edu / 123456")

