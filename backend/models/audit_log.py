"""Audit log model for complete system audit trail."""

import uuid
from datetime import datetime, timezone
from . import db


class AuditLog(db.Model):
    """Complete audit trail for all system actions."""

    __tablename__ = "audit_logs"

    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.UUID, db.ForeignKey("users.id"), index=True)
    action = db.Column(
        db.Enum(
            "create", "update", "delete", "approve", "reject",
            "upload", "download", "login", "logout", "verify", "generate",
            name="audit_action",
        ),
        nullable=False,
    )
    resource_type = db.Column(db.String(100), nullable=False)
    resource_id = db.Column(db.UUID)
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    session_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = db.relationship("User", back_populates="audit_logs")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.resource_type}>"

