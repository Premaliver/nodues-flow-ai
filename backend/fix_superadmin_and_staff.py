"""
Ensure default super admin, department staff, and default data exist without deleting registered student users.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from models.user import User
from models.student import Student
from models.department import Department, DepartmentStaff
from sqlalchemy import text

app = create_app("development")

with app.app_context():
    # Safely alter table if missing columns in existing DB engine
    try:
        db.session.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS course_id UUID;"))
        db.session.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS academic_department_id UUID;"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Notice on migration alter:", e)

    db.create_all()

    # Create missing default departments
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
        if not Department.query.filter_by(code=code).first():
            db.session.add(Department(code=code, name=name, description=desc, role=role, display_order=order, is_active=True))
    db.session.commit()

    # Create missing default users
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
    for email, role, fname, lname, phone in users_data:
        if not User.query.filter_by(email=email).first():
            password = "Prem@2004" if role == "super_admin" else "123456"
            user = User(email=email, role=role, first_name=fname, last_name=lname, phone=phone, is_email_verified=True, status="active")
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            if role == "student":
                db.session.add(Student(
                    user_id=user.id, roll_number="RBU/22CSE/0142", enrollment_number="ENR/2022/4257",
                    course_name="B.Tech Computer Science Engineering", branch="Computer Science & Engineering",
                    current_semester=6, batch_year="2022-2026", admission_year=2022, category="hosteller",
                    father_name="Mr. Rajesh Sharma", mother_name="Mrs. Kavita Sharma", guardian_phone="+91-9876543219",
                    permanent_address="123, Sector 15, Chandigarh", city="Chandigarh", state="Punjab", pincode="160015",
                ))
            elif role in ["accounts", "hostel", "mess", "transport", "scholarship", "hod", "examination"]:
                dept = Department.query.filter_by(role=role).first()
                if dept:
                    db.session.add(DepartmentStaff(user_id=user.id, department_id=dept.id, is_active=True))

    db.session.commit()
    print("✓ Successfully ensured Super Admin and default accounts exist while preserving registered student accounts.")
