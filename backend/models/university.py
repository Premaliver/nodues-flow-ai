"""University Tenant and Subscription model."""

import uuid
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, GUID


class UniversityTenant(db.Model):
    """University organization account managing subscriptions and access."""

    __tablename__ = "university_tenants"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    official_email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    contact_person = db.Column(db.String(200), nullable=False)
    designation = db.Column(db.String(150), default="Registrar / Dean")
    phone = db.Column(db.String(30))
    website = db.Column(db.String(255))
    address = db.Column(db.Text)
    state = db.Column(db.String(100))
    country = db.Column(db.String(100), default="India")
    estimated_students = db.Column(db.Integer, default=5000)

    # Subscription Lifecycle
    subscription_status = db.Column(
        db.Enum(
            "unsubscribed", "trial", "active", "grace_period", "suspended", "cancelled",
            name="university_sub_status",
        ),
        nullable=False,
        default="unsubscribed",
    )
    subscription_plan = db.Column(
        db.Enum(
            "none", "starter", "professional", "enterprise", "custom",
            name="university_sub_plan",
        ),
        nullable=False,
        default="none",
    )
    billing_cycle = db.Column(db.String(20), default="annual")  # "monthly" or "annual"
    subscribed_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    last_payment_id = db.Column(db.String(100))
    last_payment_amount = db.Column(db.Numeric(10, 2))
    license_token = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def has_active_subscription(self) -> bool:
        if self.subscription_status in ("active", "trial"):
            if not self.expires_at:
                return True
            now = datetime.now(timezone.utc)
            exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
            return now <= exp
        if self.subscription_status == "grace_period":
            return True
        return False

    def activate_subscription(self, plan: str, cycle: str = "annual", duration_days: int = 365, payment_id: str = None, amount: float = 0.0) -> None:
        now = datetime.now(timezone.utc)
        self.subscription_status = "active"
        self.subscription_plan = plan
        self.billing_cycle = cycle
        self.subscribed_at = now
        self.expires_at = now + timedelta(days=duration_days)
        self.last_payment_id = payment_id or f"PAY_{uuid.uuid4().hex[:10].upper()}"
        self.last_payment_amount = amount

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "official_email": self.official_email,
            "contact_person": self.contact_person,
            "designation": self.designation,
            "phone": self.phone,
            "website": self.website,
            "state": self.state,
            "country": self.country,
            "estimated_students": self.estimated_students,
            "subscription_status": self.subscription_status,
            "subscription_plan": self.subscription_plan,
            "billing_cycle": self.billing_cycle,
            "has_active_subscription": self.has_active_subscription,
            "subscribed_at": self.subscribed_at.isoformat() if self.subscribed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<UniversityTenant {self.name} ({self.subscription_status})>"
