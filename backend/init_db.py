"""
Initialize the database with tables and seed data.
Run: python init_db.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from datetime import datetime, timezone

app = create_app("development")

with app.app_context():
    db.create_all()
    print("✓ Database tables created")

    from models.user import User
    from models.student import Student
    from models.department import Department, DepartmentStaff
    from models.semester import Semester
    from models.workflow import WorkflowConfig
    from models.system_setting import SystemSetting

    # Don't seed if data exists
    if User.query.first():
        print("→ Database already has data. Skipping seed.")
    else:
        # Create departments
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
            dept = Department(code=code, name=name, description=desc, role=role, display_order=order, is_active=True)
            db.session.add(dept)
        db.session.commit()
        print("✓ 7 Departments created")

        # Create users for each role
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
            ("premkumar.officia0@gmail.com", "student", "Prem", "Kumar", "+91-9876543210"),
            ("premkumar78142@gmail.com", "student", "Prem", "Kumar", "+91-9876543210"),
        ]
        created_users = []
        for email, role, fname, lname, phone in users_data:
            password = "Prem@2004" if role == "super_admin" else "123456"
            user = User(
                email=email,
                role=role,
                first_name=fname,
                last_name=lname,
                phone=phone,
                is_email_verified=True,
                status="active",
            )
            # Use User.set_password() which uses werkzeug.security (compatible with User.check_password())
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            created_users.append(user)

        # Create student profile
        student_user = created_users[-1]  # student@rayatbahra.edu
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

        # Create workflow configs for hosteller category
        departments = Department.query.order_by(Department.display_order).all()
        for i, dept in enumerate(departments):
            wf = WorkflowConfig(
                category="hosteller",
                department_id=dept.id,
                step_order=i + 1,
                is_required=True,
                is_active=True,
            )
            db.session.add(wf)

        db.session.commit()
        print("✓ 9 Users created")
        print("✓ 1 Student profile created")
        print("✓ 1 Semester created")
        print("✓ 7 Workflow steps configured for hosteller")
        print()
        print("="*50)
        print(" SUPER ADMIN (login via username)")
        print(" Username: KPrem / Password: Prem@2004")
        print("="*50)
        print(" STAFF/STUDENT (login via email)")
        print(" accounts@rayatbahra.edu / 123456")
        print(" hostel@rayatbahra.edu / 123456")
        print(" mess@rayatbahra.edu / 123456")
        print(" transport@rayatbahra.edu / 123456")
        print(" scholarship@rayatbahra.edu / 123456")
        print(" hod.cse@rayatbahra.edu / 123456")
        print(" examination@rayatbahra.edu / 123456")
        print(" student@rayatbahra.edu / 123456")
        print("="*50)

