"""Mess department blueprint."""

from flask import Blueprint

mess_bp = Blueprint(
    "mess",
    __name__,
    template_folder="../../templates/mess",
    static_folder="../../static",
)

from . import routes  # noqa: E402, F401

