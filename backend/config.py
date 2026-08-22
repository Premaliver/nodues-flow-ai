"""
Smart NoDues AI - Configuration Module
All environment-specific settings for the Flask application.
"""

import os
from datetime import timedelta
try:
    from dotenv import load_dotenv
    # Load .env from backend directory or project root
    for env_path in [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    ]:
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
            break
except ImportError:
    pass


def _get_db_uri(default_uri: str) -> str:
    """Helper to fetch DATABASE_URL from env and fix legacy postgres:// prefix for SQLAlchemy."""
    uri = os.environ.get("DATABASE_URL", default_uri)
    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri


class BaseConfig:
    """Base configuration shared across all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-this-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    SQLALCHEMY_DATABASE_URI = _get_db_uri("postgresql://postgres:postgres@localhost:5432/nodues_ai")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "max_overflow": 20,
    }

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "static", "uploads"
    )
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "premkumar.pro03@gmail.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "nslszfdxedigekru")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "Smart NoDues AI <premkumar.pro03@gmail.com>"
    )

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "true").lower() == "true"
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "2000 per hour; 300 per minute")
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")

    SOCKETIO_CORS_ALLOWED_ORIGINS = os.environ.get(
        "CORS_ORIGINS", "http://localhost:5000"
    ).split(",")

    UNIVERSITY_NAME = "Rayat Bahra University"
    APP_NAME = "Smart NoDues AI"
    SUPPORT_EMAIL = "support@rayatbahra.edu"
    ITEMS_PER_PAGE = 20


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False

    # If DATABASE_URL is set in environment (e.g. Render / Cloud deployment), use it!
    # Otherwise fall back to local SQLite for local dev machine.
    db_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "nodues_ai_dev.db")).replace("\\", "/")
    SQLALCHEMY_DATABASE_URI = _get_db_uri("sqlite:///" + db_file_path)
    SQLALCHEMY_ENGINE_OPTIONS = BaseConfig.SQLALCHEMY_ENGINE_OPTIONS if os.environ.get("DATABASE_URL") else {}


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    db_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "nodues_ai_prod.db")).replace("\\", "/")
    SQLALCHEMY_DATABASE_URI = _get_db_uri("sqlite:///" + db_file_path)
    SQLALCHEMY_ENGINE_OPTIONS = BaseConfig.SQLALCHEMY_ENGINE_OPTIONS if os.environ.get("DATABASE_URL") else {}


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = (
        "postgresql://postgres:postgres@localhost:5432/nodues_ai_test"
    )
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


