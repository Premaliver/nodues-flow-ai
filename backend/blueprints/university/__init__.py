"""University Blueprint initialization."""

from flask import Blueprint

university_bp = Blueprint("university", __name__)

from . import routes
