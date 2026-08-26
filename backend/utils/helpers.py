"""Helper utility functions for the application."""

import os
import uuid
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Optional

from werkzeug.utils import secure_filename


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename while preserving extension."""
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    unique_name = f"{uuid.uuid4().hex}_{int(datetime.now(timezone.utc).timestamp())}"
    return f"{unique_name}.{ext}" if ext else unique_name


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if the file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in allowed_extensions


def secure_file_path(upload_folder: str, subfolder: str, filename: str) -> str:
    """Create a secure file path within the upload folder."""
    safe_name = secure_filename(generate_unique_filename(filename))
    directory = os.path.join(upload_folder, subfolder)
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, safe_name)


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file for duplicate detection."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def generate_hmac_signature(data: str, secret_key: str) -> str:
    """Generate HMAC-SHA256 signature for QR code data."""
    return hmac.new(
        secret_key.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_hmac_signature(data: str, signature: str, secret_key: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = generate_hmac_signature(data, secret_key)
    return hmac.compare_digest(expected, signature)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def paginate_query(query, page: int = 1, per_page: int = 20):
    """Paginate a SQLAlchemy query and return structured result."""
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [item.to_dict() for item in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def get_client_ip() -> str:
    """Extract client IP address from request."""
    from flask import request

    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    return request.remote_addr or "0.0.0.0"


def get_user_agent() -> str:
    """Extract user agent from request."""
    from flask import request

    return request.headers.get("User-Agent", "")


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime."""
    if not date_str:
        return None
    from dateutil import parser
    return parser.parse(date_str)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for storage."""
    safe = secure_filename(filename)
    if not safe:
        return generate_unique_filename(filename)
    return safe


def normalize_logo_url(url: Optional[str]) -> Optional[str]:
    """Resolve webpage and image host links (e.g. kommodo.ai, imgur, drive, dropbox) to direct raw image URLs."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None

    # Google Drive share link
    if "drive.google.com" in url and "/file/d/" in url:
        try:
            file_id = url.split("/file/d/")[1].split("/")[0]
            return f"https://drive.google.com/uc?export=view&id={file_id}"
        except Exception:
            pass

    # Dropbox share link
    if "dropbox.com" in url:
        return url.replace("?dl=0", "?raw=1")

    # Kommodo.ai share link
    if "kommodo.ai/i/" in url:
        try:
            import urllib.request
            import re
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                og = re.findall(r'property="og:image"\s+content="([^"]+)"', html)
                if og:
                    return og[0]
                imgs = re.findall(r'https?://[^\s"\'<>]+\.(?:png|jpg|jpeg|webp)', html)
                if imgs:
                    return imgs[0]
        except Exception:
            pass

    # If it is a generic HTML page that contains og:image
    if not any(url.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif')):
        try:
            import urllib.request
            import re
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                ctype = resp.headers.get('Content-Type', '')
                if 'text/html' in ctype:
                    html = resp.read().decode('utf-8', errors='ignore')
                    og = re.findall(r'property="og:image"\s+content="([^"]+)"', html)
                    if og:
                        return og[0]
        except Exception:
            pass

    return url

