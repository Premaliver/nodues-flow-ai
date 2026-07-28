"""Seed data for all university courses organized by department."""

from datetime import datetime, timezone
from app import create_app
from models import db
from models.course import Course
from models.department import Department


def seed_courses():
    """Seed all university courses into the database."""
    app = create_app()
    with app.app_context():
        # Ensure departments exist first
        depts = {d.role: d for d in Department.query.all()}
        if not depts:
            print("No departments found. Run seed.py first.")
            return

        # Academic departments mapping
        academic_depts = {
            "CSE": "Computer Science & Engineering",
            "ECE": "Electronics & Communication Engineering",
            "EEE": "Electrical & Electronics Engineering",
            "ME": "Mechanical Engineering",
            "CE": "Civil Engineering",
            "AE": "Aerospace Engineering",
            "CHE": "Chemical Engineering",
            "IT": "Information Technology",
            "AI": "Artificial Intelligence & Machine Learning",
            "DS": "Data Science",
            "BBA": "Bachelor of Business Administration",
            "MBA": "Master of Business Administration",
            "BCA": "Bachelor of Computer Applications",
            "MCA": "Master of Computer Applications",
            "PHARM": "Pharmacy",
            "BIOTECH": "Biotechnology",
            "NURSING": "Nursing",
            "PHYSIO": "Physiotherapy",
            "EDU": "Education (B.Ed)",
            "LAW": "Law (LLB)",
            "JMC": "Journalism & Mass Communication",
            "HOTEL": "Hotel Management",
            "FASHION": "Fashion Design",
            "FINEARTS": "Fine Arts",
            "ARCH": "Architecture",
        }

        courses_data = [
            # Engineering & Technology
            ("B.Tech Computer Science Engineering", "CSE", "B.Tech", 4, 8),
            ("B.Tech Electronics & Communication Engineering", "ECE", "B.Tech", 4, 8),
            ("B.Tech Electrical & Electronics Engineering", "EEE", "B.Tech", 4, 8),
            ("B.Tech Mechanical Engineering", "ME", "B.Tech", 4, 8),
            ("B.Tech Civil Engineering", "CE", "B.Tech", 4, 8),
            ("B.Tech Aerospace Engineering", "AE", "B.Tech", 4, 8),
            ("B.Tech Chemical Engineering", "CHE", "B.Tech", 4, 8),
            ("B.Tech Information Technology", "IT", "B.Tech", 4, 8),
            ("B.Tech Artificial Intelligence & ML", "AI", "B.Tech", 4, 8),
            ("B.Tech Data Science", "DS", "B.Tech", 4, 8),
            ("M.Tech Computer Science Engineering", "CSE", "M.Tech", 2, 4),
            ("M.Tech Electronics & Communication Engineering", "ECE", "M.Tech", 2, 4),
            ("M.Tech Mechanical Engineering", "ME", "M.Tech", 2, 4),
            ("M.Tech Civil Engineering", "CE", "M.Tech", 2, 4),
            ("Ph.D Computer Science Engineering", "CSE", "Ph.D", 3, 6),
            ("Ph.D Electronics & Communication Engineering", "ECE", "Ph.D", 3, 6),
            ("Ph.D Mechanical Engineering", "ME", "Ph.D", 3, 6),

            # Computer Applications
            ("Bachelor of Computer Applications (BCA)", "BCA", "Bachelor", 3, 6),
            ("Master of Computer Applications (MCA)", "MCA", "Master", 2, 4),

            # Business & Management
            ("Bachelor of Business Administration (BBA)", "BBA", "Bachelor", 3, 6),
            ("Master of Business Administration (MBA)", "MBA", "Master", 2, 4),
            ("MBA in Finance", "MBA", "Master", 2, 4),
            ("MBA in Marketing", "MBA", "Master", 2, 4),
            ("MBA in Human Resources", "MBA", "Master", 2, 4),
            ("MBA in International Business", "MBA", "Master", 2, 4),
            ("Executive MBA", "MBA", "Master", 1, 2),

            # Pharmacy
            ("Bachelor of Pharmacy (B.Pharm)", "PHARM", "Bachelor", 4, 8),
            ("Master of Pharmacy (M.Pharm)", "PHARM", "Master", 2, 4),
            ("Pharm.D", "PHARM", "Doctorate", 6, 12),

            # Biotechnology
            ("B.Sc Biotechnology", "BIOTECH", "Bachelor", 3, 6),
            ("M.Sc Biotechnology", "BIOTECH", "Master", 2, 4),

            # Nursing
            ("Bachelor of Science in Nursing (B.Sc Nursing)", "NURSING", "Bachelor", 4, 8),
            ("Post Basic B.Sc Nursing", "NURSING", "Bachelor", 2, 4),
            ("M.Sc Nursing", "NURSING", "Master", 2, 4),

            # Physiotherapy
            ("Bachelor of Physiotherapy (BPT)", "PHYSIO", "Bachelor", 4, 8),
            ("Master of Physiotherapy (MPT)", "PHYSIO", "Master", 2, 4),

            # Education
            ("Bachelor of Education (B.Ed)", "EDU", "Bachelor", 2, 4),
            ("Master of Education (M.Ed)", "EDU", "Master", 2, 4),

            # Law
            ("Bachelor of Laws (LLB)", "LAW", "Bachelor", 3, 6),
            ("BA LLB (Hons)", "LAW", "Bachelor", 5, 10),
            ("BBA LLB (Hons)", "LAW", "Bachelor", 5, 10),
            ("Master of Laws (LLM)", "LAW", "Master", 1, 2),

            # Journalism & Mass Communication
            ("Bachelor of Journalism & Mass Communication (BJMC)", "JMC", "Bachelor", 3, 6),
            ("Master of Journalism & Mass Communication (MJMC)", "JMC", "Master", 2, 4),

            # Hotel Management
            ("Bachelor of Hotel Management (BHM)", "HOTEL", "Bachelor", 3, 6),
            ("Master of Hotel Management (MHM)", "HOTEL", "Master", 2, 4),
            ("Diploma in Hotel Management", "HOTEL", "Diploma", 1, 2),

            # Fashion Design
            ("Bachelor of Fashion Design (BFD)", "FASHION", "Bachelor", 3, 6),
            ("Master of Fashion Design (MFD)", "FASHION", "Master", 2, 4),

            # Fine Arts
            ("Bachelor of Fine Arts (BFA)", "FINEARTS", "Bachelor", 3, 6),
            ("Master of Fine Arts (MFA)", "FINEARTS", "Master", 2, 4),

            # Architecture
            ("Bachelor of Architecture (B.Arch)", "ARCH", "Bachelor", 5, 10),
            ("Master of Architecture (M.Arch)", "ARCH", "Master", 2, 4),

            # Diploma Programs
            ("Diploma in Computer Science", "CSE", "Diploma", 3, 6),
            ("Diploma in Mechanical Engineering", "ME", "Diploma", 3, 6),
            ("Diploma in Civil Engineering", "CE", "Diploma", 3, 6),
            ("Diploma in Electrical Engineering", "EEE", "Diploma", 3, 6),
            ("Diploma in Electronics Engineering", "ECE", "Diploma", 3, 6),
        ]

        count = 0
        for name, dept_code, level, duration_years, semesters in courses_data:
            # Find or use CSE as fallback
            dept = Department.query.filter_by(code=dept_code).first()
            if not dept:
                dept = Department.query.filter_by(code="CSE").first()
            if not dept:
                continue

            code = f"{dept_code}{count+1:03d}"
            existing = Course.query.filter_by(name=name).first()
            if not existing:
                course = Course(
                    name=name,
                    code=code,
                    department_id=dept.id,
                    duration_years=duration_years,
                    duration_semesters=semesters,
                    degree_level=level,
                    is_active=True,
                )
                db.session.add(course)
                count += 1

        db.session.commit()
        print(f"✓ {count} courses seeded successfully!")


if __name__ == "__main__":
    seed_courses()

