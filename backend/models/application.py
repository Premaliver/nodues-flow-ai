"""No-Dues application and department approval tracking models."""

import uuid
import secrets
from datetime import datetime, timezone
from . import db, GUID


def generate_application_number() -> str:
    """Generate a unique application number."""
    year_part = datetime.now(timezone.utc).strftime("%Y")
    seq_part = secrets.token_hex(4).upper()
    return f"ND-{year_part}-{seq_part}"


class NoDuesApplication(db.Model):
    """Main no-dues application record."""

    __tablename__ = "no_dues_applications"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    application_number = db.Column(db.String(50), unique=True, nullable=False, index=True, default=generate_application_number)
    student_id = db.Column(
        GUID, db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    semester_id = db.Column(GUID, db.ForeignKey("semesters.id"), nullable=False)
    hod_department_id = db.Column(GUID, db.ForeignKey("departments.id"), nullable=True)
    status = db.Column(
        db.Enum(
            "draft", "submitted", "in_review", "approved", "rejected", "partially_approved",
            name="application_status",
        ),
        nullable=False, default="draft",
    )
    category = db.Column(
        db.Enum(
            "day_scholar", "hosteller", "transport_user", "scholarship",
            "hosteller_transport", "scholarship_hosteller",
            "scholarship_transport", "hosteller_scholarship_transport",
            name="student_category",
        ),
        nullable=False,
    )
    selected_departments = db.Column(db.JSON, nullable=True, default=list)
    digital_signature = db.Column(db.Text, nullable=True)
    signature_hash = db.Column(db.String(128), nullable=True)
    is_urgent = db.Column(db.Boolean, default=False)
    current_step = db.Column(db.Integer, default=0)
    total_steps = db.Column(db.Integer, nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    remarks = db.Column(db.Text)
    accounts_verified = db.Column(db.Boolean, default=False)
    accounts_verified_at = db.Column(db.DateTime(timezone=True))
    hod_approved = db.Column(db.Boolean, default=False)
    hod_approved_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at = db.Column(db.DateTime(timezone=True))

    # Tenant Isolation
    university_id = db.Column(GUID, db.ForeignKey("university_tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    # Relationships
    university = db.relationship("UniversityTenant", backref=db.backref("applications", lazy="dynamic"))
    student = db.relationship("Student", back_populates="applications")
    semester = db.relationship("Semester", back_populates="applications")
    hod_department = db.relationship("Department", foreign_keys=[hod_department_id])
    department_approvals = db.relationship(
        "ApplicationDepartment", back_populates="application",
        lazy="joined", order_by="ApplicationDepartment.display_order",
    )
    documents = db.relationship("Document", back_populates="application", lazy="joined")
    admit_card = db.relationship(
        "AdmitCard", back_populates="application",
        uselist=False, cascade="all, delete-orphan",
    )

    @property
    def progress_percentage(self) -> float:
        """Calculate application progress as percentage."""
        if self.total_steps == 0:
            return 0.0
        return round((self.current_step / self.total_steps) * 100, 1)

    def can_submit(self) -> bool:
        """Check if application is in a submittable state."""
        return self.status in ("draft",)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "application_number": self.application_number,
            "student_id": str(self.student_id),
            "semester_id": str(self.semester_id),
            "status": self.status,
            "category": self.category,
            "is_urgent": self.is_urgent,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "progress_percentage": self.progress_percentage,
            "university_id": str(self.university_id) if self.university_id else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "remarks": self.remarks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<NoDuesApplication {self.application_number} ({self.status})>"


class ApplicationDepartment(db.Model):
    """Department-specific approval tracking within an application."""

    __tablename__ = "application_departments"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    application_id = db.Column(
        GUID, db.ForeignKey("no_dues_applications.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    department_id = db.Column(GUID, db.ForeignKey("departments.id"), nullable=False)
    status = db.Column(
        db.Enum(
            "pending", "in_review", "approved", "rejected", "skipped",
            name="approval_status",
        ),
        nullable=False, default="pending",
    )
    assigned_to = db.Column(GUID, db.ForeignKey("users.id"))
    remarks = db.Column(db.Text)
    processed_at = db.Column(db.DateTime(timezone=True))
    processed_by = db.Column(GUID, db.ForeignKey("users.id"))
    display_order = db.Column(db.Integer, default=0)
    is_required = db.Column(db.Boolean, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("application_id", "department_id", name="uq_app_dept"),
    )

    # Relationships
    application = db.relationship("NoDuesApplication", back_populates="department_approvals")
    department = db.relationship("Department", back_populates="application_departments")
    assignee = db.relationship("User", foreign_keys=[assigned_to])
    processor = db.relationship("User", foreign_keys=[processed_by])

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "application_id": str(self.application_id),
            "department_id": str(self.department_id),
            "department_name": self.department.name if self.department else None,
            "department_code": self.department.code if self.department else None,
            "department_role": self.department.role if self.department else None,
            "status": self.status,
            "assigned_to": str(self.assigned_to) if self.assigned_to else None,
            "remarks": self.remarks,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "display_order": self.display_order,
            "is_required": self.is_required,
        }

    def __repr__(self) -> str:
        return f"<ApplicationDepartment {self.application_id} -> {self.department_id} ({self.status})>"

