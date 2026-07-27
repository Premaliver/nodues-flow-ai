"""Workflow configuration model for approval routing."""

import uuid
from datetime import datetime, timezone
from . import db


class WorkflowConfig(db.Model):
    """Configurable approval workflow routing by student category."""

    __tablename__ = "workflow_config"

    id = db.Column(db.UUID, primary_key=True, default=uuid.uuid4)
    category = db.Column(
        db.Enum(
            "day_scholar", "hosteller", "transport_user", "scholarship",
            "hosteller_transport", "scholarship_hosteller",
            "scholarship_transport", "hosteller_scholarship_transport",
            name="student_category",
        ),
        nullable=False,
    )
    department_id = db.Column(db.UUID, db.ForeignKey("departments.id"), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    is_required = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("category", "department_id", name="uq_workflow_category_dept"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "category": self.category,
            "department_id": str(self.department_id),
            "step_order": self.step_order,
            "is_required": self.is_required,
            "is_active": self.is_active,
        }

    def __repr__(self) -> str:
        return f"<WorkflowConfig {self.category} step {self.step_order}>"

