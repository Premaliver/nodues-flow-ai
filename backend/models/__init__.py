"""SQLAlchemy models for Smart NoDues AI."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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

