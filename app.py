import os
import sys

# Add the backend directory to the Python path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_path)

from app import create_app, socketio

# Determine environment
config_name = os.environ.get("FLASK_ENV", "development")

# Create application
app = create_app(config_name)

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = config_name == "development"

    print(f"[*] Smart NoDues AI starting on {host}:{port} ({config_name})")
    print(f"[*] University: {app.config['UNIVERSITY_NAME']}")
    print(f"[*] Support: {app.config['SUPPORT_EMAIL']}")

    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        allow_unsafe_werkzeug=True,
    )
