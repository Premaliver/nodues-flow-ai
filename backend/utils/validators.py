"""Input validation utilities for the application."""

import re
from typing import Optional, Tuple


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """Validate email address format."""
    if not email:
        return False, "Email is required"
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "Invalid email format"
    if len(email) > 255:
        return False, "Email too long"
    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """Validate password strength.
    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if not password:
        return False, "Password is required"
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if len(password) > 128:
        return False, "Password must be at most 128 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    return True, None


def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """Validate Indian phone number format."""
    if not phone:
        return True, None  # Phone is optional
    pattern = r"^\+?91?[6-9]\d{9}$"
    if not re.match(pattern, phone.replace(" ", "")):
        return False, "Invalid phone number format (must be Indian mobile number)"
    return True, None


def validate_pincode(pincode: str) -> Tuple[bool, Optional[str]]:
    """Validate Indian pincode (6 digits)."""
    if not pincode:
        return True, None
    if not re.match(r"^\d{6}$", pincode):
        return False, "Invalid pincode (must be 6 digits)"
    return True, None


def validate_roll_number(roll_number: str) -> Tuple[bool, Optional[str]]:
    """Validate university roll number format."""
    if not roll_number:
        return False, "Roll number is required"
    if len(roll_number) > 50:
        return False, "Roll number too long"
    return True, None


def validate_enrollment_number(enrollment: str) -> Tuple[bool, Optional[str]]:
    """Validate enrollment number format."""
    if not enrollment:
        return False, "Enrollment number is required"
    if len(enrollment) > 50:
        return False, "Enrollment number too long"
    return True, None


def validate_semester(semester: int) -> Tuple[bool, Optional[str]]:
    """Validate semester number (1-12)."""
    if not isinstance(semester, int) or semester < 1 or semester > 12:
        return False, "Semester must be between 1 and 12"
    return True, None


def validate_name(name: str, field_name: str = "Name") -> Tuple[bool, Optional[str]]:
    """Validate a person's name."""
    if not name:
        return False, f"{field_name} is required"
    if len(name) < 2:
        return False, f"{field_name} must be at least 2 characters"
    if len(name) > 100:
        return False, f"{field_name} must be at most 100 characters"
    if not re.match(r"^[a-zA-Z\s.\-']+$", name):
        return False, f"{field_name} contains invalid characters"
    return True, None


def validate_file_extension(filename: str, allowed_extensions: set) -> Tuple[bool, Optional[str]]:
    """Validate file extension against allowed set."""
    if not filename:
        return False, "Filename is required"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        return False, f"File type '{ext}' not allowed. Allowed: {', '.join(allowed_extensions)}"
    return True, None


def validate_file_size(file_size: int, max_size_mb: int = 16) -> Tuple[bool, Optional[str]]:
    """Validate file size doesn't exceed max."""
    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        return False, f"File size exceeds maximum of {max_size_mb}MB"
    if file_size <= 0:
        return False, "Invalid file size"
    return True, None


def sanitize_html(text: str) -> str:
    """Basic sanitization to prevent XSS."""
    import html
    return html.escape(text)


def validate_required_string(value: str, field_name: str, max_length: int = 255) -> Tuple[bool, Optional[str]]:
    """Validate a required string field."""
    if not value or not value.strip():
        return False, f"{field_name} is required"
    if len(value) > max_length:
        return False, f"{field_name} must be at most {max_length} characters"
    return True, None
