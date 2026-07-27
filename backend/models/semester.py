"""Academic semester model."""

import uuid
from datetime import datetime, timezone
from . import db, GUID


class Semester(db.Model):
    """Academic semester definition."""

    __tablename__ = "semesters"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    semester_number = db.Column(db.Integer, nullable=False)
    semester_name = db.Column(db.String(100), nullable=False)
    academic_year = db.Column(db.String(9), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, default=False, index=True)
    is_fee_submission_open = db.Column(db.Boolean, default=False)
    is_clearance_open = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("semester_number", "academic_year", name="uq_semester_year"),
    )

    # Relationships
    applications = db.relationship("NoDuesApplication", back_populates="semester")
    admit_cards = db.relationship("AdmitCard", back_populates="semester")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "semester_number": self.semester_number,
            "semester_name": self.semester_name,
            "academic_year": self.academic_year,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_current": self.is_current,
            "is_clearance_open": self.is_clearance_open,
        }

    def __repr__(self) -> str:
        return f"<Semester {self.semester_name} ({self.academic_year})>"

