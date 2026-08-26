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
    reset_otp_hash = db.Column(db.String(255), nullable=True)
    reset_otp_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = db.Column(db.DateTime(timezone=True))

    # Tenant Isolation
    university_id = db.Column(GUID, db.ForeignKey("university_tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Relationships
    university = db.relationship("UniversityTenant", backref=db.backref("users", lazy="dynamic"))
    student_profile = db.relationship("Student", back_populates="user", uselist=False)
    notifications = db.relationship("Notification", back_populates="user", lazy="dynamic")
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        """Hash and set password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)

    def set_reset_otp(self, otp: str, expires_in_minutes: int = 10) -> None:
        """Set hashed reset OTP with expiration."""
        import hashlib
        from datetime import timedelta
        self.reset_otp_hash = hashlib.sha256(otp.strip().encode("utf-8")).hexdigest()
        self.reset_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

    def verify_reset_otp(self, otp: str) -> bool:
        """Verify OTP matches and is not expired."""
        import hashlib
        if not self.reset_otp_hash or not self.reset_otp_expires_at:
            return False
        
        now = datetime.now(timezone.utc)
        # Ensure reset_otp_expires_at is timezone-aware
        expires_at = self.reset_otp_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            return False
        
        candidate_hash = hashlib.sha256(otp.strip().encode("utf-8")).hexdigest()
        return candidate_hash == self.reset_otp_hash

    def clear_reset_otp(self) -> None:
        """Clear reset OTP data after successful reset."""
        self.reset_otp_hash = None
        self.reset_otp_expires_at = None

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
            "university_id": str(self.university_id) if self.university_id else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"

