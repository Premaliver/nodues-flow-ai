"""User model for authentication and role management."""

import uuid
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db, GUID


class User(UserMixin, db.Model):
    """Central user model for all roles (students, staff, admins)."""

    __tablename__ = "users"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum(
            "student", "accounts", "hostel", "mess", "transport",
            "scholarship", "hod", "examination", "super_admin",
            name="user_role",
        ),
        nullable=False,
        default="student",
    )
    status = db.Column(
        db.Enum(
            "active", "inactive", "suspended", "graduated", "withdrawn",
            name="user_status",
        ),
        nullable=False,
        default="active",
    )
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    profile_image_url = db.Column(db.Text)
    is_email_verified = db.Column(db.Boolean, default=False)
    is_mfa_enabled = db.Column(db.Boolean, default=False)
    last_login_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    student_profile = db.relationship("Student", back_populates="user", uselist=False)
    notifications = db.relationship("Notification", back_populates="user", lazy="dynamic")
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        """Hash and set password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        """Return full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active_user(self) -> bool:
        """Check if user is active."""
        return self.status == "active"

    @property
    def is_super_admin(self) -> bool:
        """Check if user is super admin."""
        return self.role == "super_admin"

    def to_dict(self) -> dict:
        """Serialize user to dictionary."""
        return {
            "id": str(self.id),
            "email": self.email,
            "role": self.role,
            "status": self.status,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "phone": self.phone,
            "profile_image_url": self.profile_image_url,
            "is_email_verified": self.is_email_verified,
            "is_mfa_enabled": self.is_mfa_enabled,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"

