#!/usr/bin/env python
"""
Smart NoDues AI — Root Entry Point
Run this file from the project root to start the Flask development server.

Usage:
    py run.py
"""

import os
import sys

# Add the backend directory to the Python path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_path)

# Load .env file before creating the app
try:
    from dotenv import load_dotenv
    env_path = os.path.join(backend_path, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[OK] Loaded environment from {env_path}")
except ImportError:
    pass

from app import create_app, socketio

# Determine environment
config_name = os.environ.get("FLASK_ENV", "development")

# Create application
app = create_app(config_name)


if __name__ == "__main__":
    # Production: Render sets PORT env var, bind to 0.0.0.0 for port detection
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = config_name == "development"

    browser_url = f"http://0.0.0.0:{port}"

    print(f"[*] Smart NoDues AI starting on {host}:{port} ({config_name})")
    print(f"[*] Open in browser: http://127.0.0.1:{port}")
    print(f"[*] University: {app.config['UNIVERSITY_NAME']}")
    print(f"[*] Support: {app.config['SUPPORT_EMAIL']}")

    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        allow_unsafe_werkzeug=True,
    )

