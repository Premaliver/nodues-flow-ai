"""Examination department blueprint."""

from flask import Blueprint

exam_bp = Blueprint(
    "examination",
    __name__,
    template_folder="../../templates/examination",
    static_folder="../../static",
)

from . import routes  # noqa: E402, F401
