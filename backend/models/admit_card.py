"""Admit card model with QR code and HMAC signing."""

import uuid
from datetime import datetime, timezone
from . import db


class AdmitCard(db.Model):
    """Digitally signed admit card with QR verification."""

    __tablename__ = "admit_cards"

    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    application_id = db.Column(
        db.UUID, db.ForeignKey("no_dues_applications.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )
    student_id = db.Column(db.UUID, db.ForeignKey("students.id"), nullable=False, index=True)
    semester_id = db.Column(db.UUID, db.ForeignKey("semesters.id"), nullable=False)
    card_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    pdf_path = db.Column(db.Text, nullable=False)
    qr_code_data = db.Column(db.Text, nullable=False)
    qr_code_path = db.Column(db.Text)
    hmac_signature = db.Column(db.String(128), nullable=False)
    verification_url = db.Column(db.Text)
    is_downloaded = db.Column(db.Boolean, default=False)
    downloaded_at = db.Column(db.DateTime(timezone=True))
    download_count = db.Column(db.Integer, default=0)
    generated_by = db.Column(db.UUID, db.ForeignKey("users.id"), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    application = db.relationship("NoDuesApplication", back_populates="admit_card")
    student = db.relationship("Student", back_populates="admit_cards")
    semester = db.relationship("Semester", back_populates="admit_cards")
    generator = db.relationship("User", foreign_keys=[generated_by])

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "card_number": self.card_number,
            "student_id": str(self.student_id),
            "semester_id": str(self.semester_id),
            "application_id": str(self.application_id),
            "is_downloaded": self.is_downloaded,
            "download_count": self.download_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<AdmitCard {self.card_number}>"

