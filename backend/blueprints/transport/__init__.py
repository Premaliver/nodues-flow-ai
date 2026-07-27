"""Transport department blueprint."""

from flask import Blueprint

transport_bp = Blueprint(
    "transport",
    __name__,
    template_folder="../../templates/transport",
    static_folder="../../static",
)

from . import routes  # noqa: E402, F401
