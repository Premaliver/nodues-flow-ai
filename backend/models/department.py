"""Department and staff models."""

import uuid
from datetime import datetime, timezone
from . import db, GUID


class Department(db.Model):
    """University department participating in the no-dues workflow."""

    __tablename__ = "departments"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    role = db.Column(
        db.Enum(
            "student", "accounts", "hostel", "mess", "transport",
            "scholarship", "hod", "examination", "super_admin",
            name="user_role",
        ),
        nullable=False,
    )
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Tenant Isolation
    university_id = db.Column(GUID, db.ForeignKey("university_tenants.id", ondelete="CASCADE"), nullable=True, index=True)

    __table_args__ = (
        db.UniqueConstraint("university_id", "code", name="uq_tenant_dept_code"),
    )

    # Relationships
    university = db.relationship("UniversityTenant", backref=db.backref("departments", lazy="dynamic"))
    staff_members = db.relationship("DepartmentStaff", back_populates="department", lazy="dynamic")
    application_departments = db.relationship("ApplicationDepartment", back_populates="department")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "role": self.role,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "university_id": str(self.university_id) if self.university_id else None,
        }

    def __repr__(self) -> str:
        return f"<Department {self.code}: {self.name}>"


class DepartmentStaff(db.Model):
    """Mapping between staff users and their departments."""

    __tablename__ = "department_staff"

    id = db.Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(GUID, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    department_id = db.Column(GUID, db.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    designation = db.Column(db.String(200))
    is_head = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("user_id", "department_id", name="uq_staff_dept"),
    )

    # Relationships
    user = db.relationship("User")
    department = db.relationship("Department", back_populates="staff_members")

    def __repr__(self) -> str:
        return f"<DepartmentStaff {self.user_id} -> {self.department_id}>"

