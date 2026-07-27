"""Scholarship department blueprint."""

from flask import Blueprint

scholarship_bp = Blueprint(
    "scholarship",
    __name__,
    template_folder="../../templates/scholarship",
    static_folder="../../static",
)

from . import routes  # noqa: E402, F401
