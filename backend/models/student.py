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
    course_name = db.Column(db.String(200), nullable=False)
    branch = db.Column(db.String(200), nullable=False)
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

    # Relationships
    user = db.relationship("User", back_populates="student_profile")
    applications = db.relationship("NoDuesApplication", back_populates="student", lazy="dynamic")
    admit_cards = db.relationship("AdmitCard", back_populates="student", lazy="dynamic")

    @property
    def student_name(self) -> str:
        """Get student's full name from user."""
        return self.user.full_name if self.user else ""

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "roll_number": self.roll_number,
            "enrollment_number": self.enrollment_number,
            "course_name": self.course_name,
            "branch": self.branch,
            "current_semester": self.current_semester,
            "batch_year": self.batch_year,
            "admission_year": self.admission_year,
            "category": self.category,
            "student_name": self.student_name,
            "father_name": self.father_name,
            "mother_name": self.mother_name,
            "city": self.city,
            "state": self.state,
        }

    def __repr__(self) -> str:
        return f"<Student {self.roll_number}>"

