"""Centralized backend validation helpers.

Every route module should import validators from here instead of
re-implementing regexes or ad-hoc checks. Frontend validation exists for
UX only -- these functions are the source of truth and must always run
server-side before data is trusted.

Each ``valid_*`` function returns ``(is_valid: bool, error: str | None)``.
"""

import re
from datetime import datetime

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INDIAN_PHONE_RE = re.compile(r"^[6-9][0-9]{9}$")

VALID_ROLES = {"resident", "vendor", "admin"}
PUBLIC_ROLES = {"resident"}

VENDOR_JOB_TITLES = {"plumber", "electrician", "carpenter", "painter", "cleaner"}
REQUEST_CATEGORY_TO_JOB = {
    "plumbing": "plumber",
    "electrical": "electrician",
    "carpentry": "carpenter",
    "painting": "painter",
    "cleaning": "cleaner",
}


def valid_email(value: str):
    value = (value or "").strip()
    if not value:
        return False, "Email is required"
    if len(value) > 160:
        return False, "Email is too long"
    if not EMAIL_RE.match(value):
        return False, "Enter a valid email address"
    return True, None


def valid_phone(value: str, *, required: bool = False):
    value = (value or "").strip()
    if not value:
        if required:
            return False, "Phone number is required"
        return True, None
    digits = re.sub(r"\D", "", value)
    # Allow a leading country code (e.g. 91) before the 10-digit number.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not INDIAN_PHONE_RE.match(digits):
        return False, "Enter a valid 10-digit Indian phone number"
    return True, None


def valid_password(value: str):
    value = value or ""
    if not value:
        return False, "Password is required"
    if len(value) < 8:
        return False, "Password must be at least 8 characters"
    return True, None


def required_text(value: str, field_name: str = "This field", *, min_len: int = 1, max_len: int = 5000):
    value = (value or "").strip()
    if not value:
        return False, f"{field_name} is required"
    if len(value) < min_len:
        return False, f"{field_name} must be at least {min_len} characters"
    if len(value) > max_len:
        return False, f"{field_name} must be under {max_len} characters"
    return True, None


def valid_date(value: str, *, required: bool = False, fmt: str = "%Y-%m-%d"):
    """Validate a strict-format date string (used for structured date inputs).

    NestLedger also accepts free-text due dates (e.g. "10 Sep 2026") in a
    few legacy forms; those are treated as required_text, not valid_date.
    """
    value = (value or "").strip()
    if not value:
        if required:
            return False, "Date is required"
        return True, None
    try:
        datetime.strptime(value, fmt)
    except ValueError:
        return False, f"Enter a valid date in {fmt} format"
    return True, None


def valid_amount(value, *, allow_zero: bool = True):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return False, "Amount must be a valid number"
    if amount < 0:
        return False, "Amount cannot be negative"
    if not allow_zero and amount == 0:
        return False, "Amount must be greater than 0"
    return True, None


def valid_status(value: str, allowed: set):
    value = (value or "").strip()
    if value not in allowed:
        return False, f"Status must be one of: {', '.join(sorted(allowed))}"
    return True, None


def safe_string(value, max_len: int = 500) -> str:
    """Trim and cap a user-supplied string. Does not escape HTML -- the
    frontend is responsible for output escaping (see esc() in app.js)."""
    return str(value or "").strip()[:max_len]
