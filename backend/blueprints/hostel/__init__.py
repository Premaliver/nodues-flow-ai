"""Hostel department blueprint."""

from flask import Blueprint

hostel_bp = Blueprint(
    "hostel",
    __name__,
    template_folder="../../templates/hostel",
    static_folder="../../static",
)

from . import routes  # noqa: E402, F401

