"""Security utilities for authentication, encryption, and token management."""

import uuid
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token


class SecurityUtils:
    """Collection of security-related utility methods."""

    @staticmethod
    def generate_uuid() -> str:
        """Generate a UUID4 string."""
        return str(uuid.uuid4())

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_hex(length)

    @staticmethod
    def generate_reset_token() -> str:
        """Generate a password reset token."""
        return secrets.token_urlsafe(48)

    @staticmethod
    def generate_hmac_signature(data: str, secret: str = None) -> str:
        """Generate HMAC-SHA256 signature for data integrity."""
        if secret is None:
            secret = current_app.config.get("JWT_SECRET_KEY", "default-secret")
        return hmac.new(
            secret.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def verify_hmac_signature(data: str, signature: str, secret: str = None) -> bool:
        """Verify HMAC-SHA256 signature."""
        expected = SecurityUtils.generate_hmac_signature(data, secret)
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def generate_tokens(user_id: str, role: str, additional_claims: dict = None) -> dict:
        """Generate JWT access and refresh tokens."""
        claims = {
            "user_id": user_id,
            "role": role,
        }
        if additional_claims:
            claims.update(additional_claims)

        access_token = create_access_token(
            identity=user_id,
            additional_claims=claims,
            expires_delta=current_app.config.get(
                "JWT_ACCESS_TOKEN_EXPIRES", timedelta(hours=2)
            ),
        )
        refresh_token = create_refresh_token(
            identity=user_id,
            expires_delta=current_app.config.get(
                "JWT_REFRESH_TOKEN_EXPIRES", timedelta(days=30)
            ),
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(
                current_app.config.get(
                    "JWT_ACCESS_TOKEN_EXPIRES", timedelta(hours=2)
                ).total_seconds()
            ),
        }

    @staticmethod
    def hash_file_content(content: bytes) -> str:
        """Generate SHA-256 hash of file content for duplicate detection."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal."""
        # Remove path separators
        filename = filename.replace("/", "").replace("\\", "")
        # Remove null bytes
        filename = filename.replace("\x00", "")
        # Limit length
        if len(filename) > 200:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[:190] + "." + ext
        return filename

    @staticmethod
    def generate_card_number() -> str:
        """Generate unique admit card number."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_part = secrets.token_hex(4).upper()
        return f"ADC-{timestamp}-{random_part}"

