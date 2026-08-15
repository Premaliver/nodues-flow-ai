"""
Keep-Alive Self-Ping Engine for Render / Cloud Free Instance Hosting.
Prevents server spin-down & 50s cold start delay by pinging /health every 10 minutes.
"""

import os
import time
import logging
import threading
import requests

logger = logging.getLogger(__name__)


def start_keep_alive(app=None):
    """
    Spawns a background daemon thread that pings the app's /health endpoint
    every 10 minutes if RENDER_EXTERNAL_URL or APP_URL environment variable is present.
    """
    app_url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("APP_URL")
    if not app_url:
        logger.info("Keep-alive self-ping background worker idle (set RENDER_EXTERNAL_URL or APP_URL in env to enable).")
        return

    health_url = app_url.rstrip("/") + "/health"

    def _ping_routine():
        logger.info(f"⚡ Keep-alive worker active. Target: {health_url}")
        while True:
            try:
                time.sleep(600)  # Ping every 10 minutes (Render spins down after 15 mins)
                response = requests.get(health_url, timeout=15)
                logger.info(f"✓ Keep-alive heartbeat status: {response.status_code}")
            except Exception as err:
                logger.warning(f"Keep-alive heartbeat notice: {err}")

    worker = threading.Thread(target=_ping_routine, daemon=True)
    worker.start()
