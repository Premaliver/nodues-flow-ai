"""
Smart NoDues AI — Flask Application Factory
Enterprise-grade Flask application with modular blueprint architecture.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Ensure backend directory is present in sys.path for cloud WSGI servers (Render/Gunicorn)
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect

from config import config_by_name
from models import db

# Initialize extensions
bcrypt = Bcrypt()
jwt = JWTManager()
login_manager = LoginManager()
mail = Mail()
limiter = Limiter(key_func=get_remote_address)
socketio = SocketIO(cors_allowed_origins="*")
csrf = CSRFProtect()


def create_app(config_name: str = "default") -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder="static",
        static_url_path="/static",
        template_folder="templates",
    )

    # Load configuration
    config_obj = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_obj)

    # Load .env file if present
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    # Override config from environment
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", app.config["SECRET_KEY"])
    app.config["JWT_SECRET_KEY"] = os.environ.get(
        "JWT_SECRET_KEY", app.config["JWT_SECRET_KEY"]
    )

    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url


    # Initialize extensions
    db.init_app(app)
    from utils.db_manager import init_db_manager
    init_db_manager(app)

    bcrypt.init_app(app)
    jwt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config.get("SOCKETIO_CORS_ALLOWED_ORIGINS", "*")}})

    # Configure CSRF
    csrf.init_app(app)

    # Configure logging
    configure_logging(app)

    # Register JWT callbacks
    register_jwt_callbacks(jwt)

    # Register login manager callbacks
    register_login_callbacks(login_manager)

    # Register blueprints
    register_blueprints(app)

    @app.route("/health")
    @app.route("/api/health")
    @limiter.exempt
    def health_check():
        return {"status": "healthy", "service": "nodues-flow-ai"}, 200

    @app.route("/verify-clearance/<card_number>")
    @limiter.exempt
    def root_verify_clearance(card_number):
        from blueprints.examination.routes import public_verify_clearance
        return public_verify_clearance(card_number)

    # Register error handlers
    register_error_handlers(app)

    # Register CLI commands
    register_cli_commands(app)

    # Create upload directory
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Auto-seed on first run (development only)
    if config_name == "development":
        with app.app_context():
            _auto_seed(app)
    elif config_name == "production":
        with app.app_context():
            _auto_seed(app)

    # Initialize keep-alive self ping worker for cloud deployments (Render free tier)
    from utils.keep_alive import start_keep_alive
    start_keep_alive(app)

    app.logger.info(
        "Smart NoDues AI started in %s mode",
        config_name,
    )

    return app


def _auto_seed(app: Flask) -> None:
    """Auto-seed database with default users if empty."""
    from database.seed import seed_data
    try:
        seed_data()
    except Exception as e:
        app.logger.warning(f"Auto-seed notice: {e}")


def configure_logging(app: Flask) -> None:
    """Configure application logging with rotation."""
    log_level = logging.DEBUG if app.debug else logging.INFO
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    console_handler.setLevel(log_level)
    app.logger.addHandler(console_handler)

    # File handler with rotation
    log_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "logs"
    )
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(log_level)
    app.logger.addHandler(file_handler)

    app.logger.setLevel(log_level)


def register_jwt_callbacks(jwt_manager: JWTManager) -> None:
    """Register JWT error handlers."""

    @jwt_manager.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {"success": False, "message": "Token has expired"}, 401

    @jwt_manager.invalid_token_loader
    def invalid_token_callback(error):
        return {"success": False, "message": "Invalid token"}, 401

    @jwt_manager.unauthorized_loader
    def missing_token_callback(error):
        return {"success": False, "message": "Authorization token is missing"}, 401

    @jwt_manager.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return {"success": False, "message": "Fresh token required"}, 401

    @jwt_manager.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return {"success": False, "message": "Token has been revoked"}, 401


def register_login_callbacks(login_manager: LoginManager) -> None:
    """Register Flask-Login callbacks."""

    @login_manager.user_loader
    def load_user(user_id: str):
        import uuid
        from models.user import User

        try:
            return User.query.get(uuid.UUID(user_id))
        except (ValueError, AttributeError):
            return None

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, redirect, url_for

        # Return JSON for API requests
        if request.path.startswith("/api/") or request.headers.get("Accept") == "application/json":
            return {"success": False, "message": "Authentication required"}, 401

        # Redirect to login for browser requests
        return redirect(url_for("auth.login"))


def register_blueprints(app: Flask) -> None:
    """Register all Flask blueprints."""

    # Import blueprints here to avoid circular imports
    from blueprints.auth import auth_bp
    from blueprints.student import student_bp
    from blueprints.accounts import accounts_bp
    from blueprints.hostel import hostel_bp
    from blueprints.mess import mess_bp
    from blueprints.transport import transport_bp
    from blueprints.scholarship import scholarship_bp
    from blueprints.hod import hod_bp
    from blueprints.examination import exam_bp
    from blueprints.superadmin import superadmin_bp
    from blueprints.api import api_bp

    # Register with URL prefixes
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(accounts_bp, url_prefix="/accounts")
    app.register_blueprint(hostel_bp, url_prefix="/hostel")
    app.register_blueprint(mess_bp, url_prefix="/mess")
    app.register_blueprint(transport_bp, url_prefix="/transport")
    app.register_blueprint(scholarship_bp, url_prefix="/scholarship")
    app.register_blueprint(hod_bp, url_prefix="/hod")
    app.register_blueprint(exam_bp, url_prefix="/examination")
    app.register_blueprint(superadmin_bp, url_prefix="/superadmin")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Exempt auth routes from CSRF (they use JWT, not session cookies)
    csrf.exempt(auth_bp)

    # Root route — serve landing page
    @app.route("/")
    def index():
        return app.send_static_file("index.html")


def _is_api_request():
    """Check if the request is an API call (vs browser navigation)."""
    from flask import request
    return (request.path.startswith("/api/") or
            request.headers.get("Accept") == "application/json" or
            request.is_json)


def _render_error(title: str, message: str, code: int):
    """Render an HTML error page for browser requests, or JSON for API requests."""
    if _is_api_request():
        return {"success": False, "message": message}, code
    from flask import render_template
    return render_template("errors/error.html", title=title, message=message, code=code), code


def register_error_handlers(app: Flask) -> None:
    """Register global error handlers."""

    @app.errorhandler(400)
    def bad_request(error):
        return _render_error("Bad Request", "The request could not be understood.", 400)

    @app.errorhandler(403)
    def forbidden(error):
        return _render_error("Forbidden", "You don't have permission to access this resource.", 403)

    @app.errorhandler(404)
    def not_found(error):
        return _render_error("Page Not Found", "The page you're looking for doesn't exist.", 404)

    @app.errorhandler(405)
    def method_not_allowed(error):
        return _render_error("Method Not Allowed", "This method is not allowed for the requested URL.", 405)

    @app.errorhandler(429)
    def too_many_requests(error):
        return _render_error(
            "Too Many Requests",
            "Rate limit exceeded. Please try again later.",
            429,
        )

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error("Internal server error: %s", str(error))
        return _render_error("Server Error", "An unexpected error occurred. Please try again later.", 500)


def register_cli_commands(app: Flask) -> None:
    """Register Flask CLI commands."""

    @app.cli.command("init-db")
    def init_db_command():
        """Initialize database and create tables."""
        with app.app_context():
            db.create_all()
            print("Database tables created successfully!")

    @app.cli.command("seed-db")
    def seed_db_command():
        """Seed database with sample data."""
        from database.seed import seed_data

        with app.app_context():
            seed_data()
            print("Database seeded successfully!")

    @app.cli.command("drop-db")
    def drop_db_command():
        """Drop all database tables."""
        with app.app_context():
            db.drop_all()
            print("All tables dropped!")

    @app.cli.command("reset-db")
    def reset_db_command():
        """Reset database: drop all tables and recreate."""
        with app.app_context():
            db.drop_all()
            db.create_all()
            print("Database reset successfully!")
