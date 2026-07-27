"""HOD department blueprint."""

from flask import Blueprint

hod_bp = Blueprint(
    "hod",
    __name__,
    template_folder="../../templates/hod",
    static_folder="../../static",
)

from . import routes  # noqa: E402, F401
