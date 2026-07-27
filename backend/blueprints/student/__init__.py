"""Student dashboard blueprint."""

from flask import Blueprint

student_bp = Blueprint(
    "student",
    __name__,
    template_folder="../../templates/student",
    static_folder="../../static",
)

from . import routes  # noqa: E402, F401

