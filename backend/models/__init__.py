"""SQLAlchemy models for Smart NoDues AI."""

import uuid
from sqlalchemy.types import TypeDecorator, CHAR
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class GUID(TypeDecorator):
    """
    Custom GUID type that works with both SQLite and PostgreSQL.
    - PostgreSQL: stores as native UUID type
    - SQLite: stores as string (since SQLite has no native UUID)
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID
            return dialect.type_descriptor(UUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, str):
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)

    def sort_key_function(self, value):
        return value if isinstance(value, uuid.UUID) else uuid.UUID(value)


from .user import User
from .student import Student
from .department import Department, DepartmentStaff
from .semester import Semester
from .application import NoDuesApplication, ApplicationDepartment
from .document import Document, DocumentVerification
from .notification import Notification
from .audit_log import AuditLog
from .admit_card import AdmitCard
from .workflow import WorkflowConfig
from .system_setting import SystemSetting
from .course import Course, DigitalSignature
from .feedback import Feedback
from .university import UniversityTenant


