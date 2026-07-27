"""Accounts department blueprint."""

from flask import Blueprint

accounts_bp = Blueprint(
    "accounts",
    __name__,
    template_folder="../../templates/accounts",
    static_folder="../../static",
)

from . import routes  # noqa: E402, F401

