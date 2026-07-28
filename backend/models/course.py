"""Course model - all university courses with department associations."""

import uuid
from datetime import datetime, timezone
from . import db, GUID


class Course(db.Model):
    """University course/program offered by departments."""

    __tablename__ = "courses"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(300), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    department_id = db.Column(GUID, db.ForeignKey("departments.id"), nullable=False)
    duration_years = db.Column(db.Integer, nullable=False, default=4)
    duration_semesters = db.Column(db.Integer, nullable=False, default=8)
    degree_level = db.Column(db.String(50), nullable=False, default="Bachelor")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    department = db.relationship("Department", backref="courses")
    students = db.relationship("Student", back_populates="course", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "code": self.code,
            "department_id": str(self.department_id),
            "department_name": self.department.name if self.department else None,
            "duration_years": self.duration_years,
            "duration_semesters": self.duration_semesters,
            "degree_level": self.degree_level,
            "is_active": self.is_active,
        }

    def __repr__(self) -> str:
        return f"<Course {self.code}: {self.name}>"


class DigitalSignature(db.Model):
    """Student digital signature stored securely."""

    __tablename__ = "digital_signatures"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(GUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    signature_data = db.Column(db.Text, nullable=False)  # Base64 encoded signature image
    signature_hash = db.Column(db.String(128), nullable=False)  # SHA-256 hash
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationship
    user = db.relationship("User", backref="digital_signatures")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "signature_hash": self.signature_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<DigitalSignature for user {self.user_id}>"

