"""Super Admin blueprint for system management."""

from flask import Blueprint

superadmin_bp = Blueprint(
    "superadmin",
    __name__,
    template_folder="../../templates/superadmin",
    static_folder="../../static",
)

from . import routes  # noqa: E402, F401
