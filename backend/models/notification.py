"""Notification model for real-time and stored notifications."""

import uuid
from datetime import datetime, timezone
from . import db, GUID


class Notification(db.Model):
    """User notification for real-time and persisted delivery."""

    __tablename__ = "notifications"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(GUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = db.Column(
        db.Enum(
            "application_submitted", "department_approved", "department_rejected",
            "application_completed", "admit_card_generated", "document_verified",
            "document_rejected", "reminder", "query", "system",
            name="notification_type",
        ),
        nullable=False,
    )
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text)
    data = db.Column(db.JSON)
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True))
    application_id = db.Column(GUID, db.ForeignKey("no_dues_applications.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = db.relationship("User", back_populates="notifications")

    def mark_as_read(self) -> None:
        """Mark notification as read."""
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "application_id": str(self.application_id) if self.application_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Notification {self.type}: {self.title} ({'read' if self.is_read else 'unread'})>"

