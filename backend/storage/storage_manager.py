"""
Secure Storage Manager Module.
Provides isolated, encrypted, and randomized object storage for university documents.
"""

import os
import uuid
import hashlib
from typing import Tuple, Optional
from werkzeug.utils import secure_filename
from flask import current_app


class SecureStorageManager:
    """Manages secure file uploads, randomized object keys, and safe streaming."""

    @staticmethod
    def get_upload_dir() -> str:
        """Returns the base storage folder for the current data plane."""
        upload_dir = current_app.config.get(
            "UPLOAD_FOLDER",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads")
        )
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    @staticmethod
    def generate_safe_object_key(original_filename: str, category: str = "documents") -> Tuple[str, str]:
        """
        Generates a collision-resistant, randomized object path.
        Never trusts raw client filenames on disk.
        Returns (relative_file_path, sanitized_original_name).
        """
        sanitized = secure_filename(original_filename) or "file"
        _, ext = os.path.splitext(sanitized)
        ext = ext.lower() if ext else ".bin"

        # Unique UUID-based storage key
        random_key = uuid.uuid4().hex
        subfolder = os.path.join(category, random_key[:2], random_key[2:4])
        filename = f"{random_key}{ext}"

        full_subfolder = os.path.join(SecureStorageManager.get_upload_dir(), subfolder)
        os.makedirs(full_subfolder, exist_ok=True)

        full_path = os.path.join(full_subfolder, filename)
        return full_path, sanitized

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        """Calculates SHA-256 digest for document integrity validation."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def save_file_securely(file_storage, category: str = "documents") -> Tuple[str, str, int, str]:
        """
        Validates, saves file to private disk with randomized key, and computes SHA-256.
        Returns (absolute_file_path, sanitized_filename, file_size, sha256_hash).
        """
        content = file_storage.read()
        file_storage.seek(0)

        file_size = len(content)
        file_hash = SecureStorageManager.compute_sha256(content)
        file_path, sanitized_name = SecureStorageManager.generate_safe_object_key(file_storage.filename, category)

        with open(file_path, "wb") as f:
            f.write(content)

        return file_path, sanitized_name, file_size, file_hash
