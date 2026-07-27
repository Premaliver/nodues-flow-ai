"""Document and AI verification models."""

import uuid
from datetime import datetime, timezone
from . import db


class Document(db.Model):
    """Uploaded documents/receipts within an application."""

    __tablename__ = "documents"

    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    application_id = db.Column(
        db.UUID, db.ForeignKey("no_dues_applications.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    document_type = db.Column(
        db.Enum(
            "semester_fee_receipt", "exam_fee_receipt", "library_clearance",
            "lab_clearance", "scholarship_document", "identity_proof", "other",
            name="document_type",
        ),
        nullable=False,
    )
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.Text, nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    mime_type = db.Column(db.String(100))
    file_hash = db.Column(db.String(64))
    status = db.Column(
        db.Enum("pending", "verified", "rejected", "duplicate", name="document_status"),
        nullable=False, default="pending",
    )
    verified_by = db.Column(db.UUID, db.ForeignKey("users.id"))
    verified_at = db.Column(db.DateTime(timezone=True))
    rejection_reason = db.Column(db.Text)
    uploaded_by = db.Column(db.UUID, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    application = db.relationship("NoDuesApplication", back_populates="documents")
    verification = db.relationship(
        "DocumentVerification", back_populates="document",
        uselist=False, cascade="all, delete-orphan",
        foreign_keys="DocumentVerification.document_id",
    )
    uploader = db.relationship("User", foreign_keys=[uploaded_by])

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "application_id": str(self.application_id),
            "document_type": self.document_type,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Document {self.file_name} ({self.status})>"


class DocumentVerification(db.Model):
    """AI verification results for uploaded documents."""

    __tablename__ = "document_verifications"

    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    document_id = db.Column(
        db.UUID, db.ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True, nullable=False,
    )
    is_verified = db.Column(db.Boolean, default=False)
    confidence_score = db.Column(db.Numeric(5, 2))
    extracted_data = db.Column(db.JSON)
    verification_details = db.Column(db.JSON)
    is_duplicate = db.Column(db.Boolean, default=False)
    duplicate_of_document_id = db.Column(db.UUID, db.ForeignKey("documents.id"))
    ai_processed_at = db.Column(db.DateTime(timezone=True))
    human_verified_at = db.Column(db.DateTime(timezone=True))
    human_verified_by = db.Column(db.UUID, db.ForeignKey("users.id"))
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    document = db.relationship("Document", back_populates="verification", foreign_keys=[document_id])
    duplicate_of = db.relationship("Document", foreign_keys=[duplicate_of_document_id])

    def to_verification_dict(self) -> dict:
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "is_verified": self.is_verified,
            "confidence_score": float(self.confidence_score) if self.confidence_score else None,
            "extracted_data": self.extracted_data,
            "verification_details": self.verification_details,
            "is_duplicate": self.is_duplicate,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        status = "verified" if self.is_verified else "pending"
        return f"<DocumentVerification for {self.document_id} ({status})>"
