"""System settings model for global configuration."""

import uuid
from datetime import datetime, timezone
from . import db


class SystemSetting(db.Model):
    """Key-value store for global system configuration."""

    __tablename__ = "system_settings"

    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    setting_key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    setting_value = db.Column(db.Text, nullable=False)
    setting_type = db.Column(db.String(50), default="string")
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False)
    updated_by = db.Column(db.UUID, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "key": self.setting_key,
            "value": self.setting_value,
            "type": self.setting_type,
            "description": self.description,
            "is_public": self.is_public,
        }

    def __repr__(self) -> str:
        return f"<SystemSetting {self.setting_key}>"

