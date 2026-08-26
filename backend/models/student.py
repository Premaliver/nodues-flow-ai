"""Student model extending user profiles."""

import uuid
from datetime import datetime, timezone
from . import db, GUID


class Student(db.Model):
    """Extended student profile with academic information."""

    __tablename__ = "students"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(GUID, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    roll_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    enrollment_number = db.Column(db.String(50), unique=True, nullable=False)
    course_id = db.Column(GUID, db.ForeignKey("courses.id"), nullable=True)
    course_name = db.Column(db.String(200), nullable=False)
    branch = db.Column(db.String(200), nullable=False)
    academic_department_id = db.Column(GUID, db.ForeignKey("departments.id"), nullable=True)
    current_semester = db.Column(db.Integer, nullable=False)
    batch_year = db.Column(db.String(9), nullable=False)
    admission_year = db.Column(db.Integer, nullable=False)
    category = db.Column(
        db.Enum(
            "day_scholar", "hosteller", "transport_user", "scholarship",
            "hosteller_transport", "scholarship_hosteller",
            "scholarship_transport", "hosteller_scholarship_transport",
            name="student_category",
        ),
        nullable=False,
        default="day_scholar",
    )
    date_of_birth = db.Column(db.Date)
    father_name = db.Column(db.String(200))
    mother_name = db.Column(db.String(200))
    guardian_phone = db.Column(db.String(20))
    guardian_email = db.Column(db.String(255))
    permanent_address = db.Column(db.Text)
    current_address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pincode = db.Column(db.String(10))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Tenant Isolation
    university_id = db.Column(GUID, db.ForeignKey("university_tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Relationships
    university = db.relationship("UniversityTenant", backref=db.backref("students", lazy="dynamic"))
    user = db.relationship("User", back_populates="student_profile")
    course = db.relationship("Course", back_populates="students")
    academic_department = db.relationship("Department", foreign_keys=[academic_department_id])
    applications = db.relationship("NoDuesApplication", back_populates="student", lazy="dynamic")
    admit_cards = db.relationship("AdmitCard", back_populates="student", lazy="dynamic")

    @property
    def student_name(self) -> str:
        """Get student's full name from user."""
        return self.user.full_name if self.user else ""

    @student_name.setter
    def student_name(self, value: str):
        """Set student's name by updating the underlying user."""
        if self.user and value:
            parts = value.strip().split(" ", 1)
            self.user.first_name = parts[0]
            self.user.last_name = parts[1] if len(parts) > 1 else ""

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "roll_number": self.roll_number,
            "enrollment_number": self.enrollment_number,
            "course_id": str(self.course_id) if self.course_id else None,
            "course_name": self.course_name,
            "branch": self.branch,
            "academic_department_id": str(self.academic_department_id) if self.academic_department_id else None,
            "academic_department_name": self.academic_department.name if self.academic_department else None,
            "current_semester": self.current_semester,
            "batch_year": self.batch_year,
            "admission_year": self.admission_year,
            "category": self.category,
            "student_name": self.student_name,
            "father_name": self.father_name,
            "mother_name": self.mother_name,
            "guardian_phone": self.guardian_phone,
            "phone": self.user.phone if self.user else None,
            "email": self.user.email if self.user else None,
            "university_id": str(self.university_id) if self.university_id else None,
            "city": self.city,
            "state": self.state,
        }

    def __repr__(self) -> str:
        return f"<Student {self.roll_number}>"

