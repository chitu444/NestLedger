"""Shared authentication helpers.

JWT identities are untrusted input. Keep conversion and user lookup in one place
so malformed/expired identities become a normal unauthorized response instead of
raising ValueError and producing a 500.
"""
from flask_jwt_extended import get_jwt_identity
from models.db import db
from models.user import User


def current_user():
    raw = get_jwt_identity()
    try:
        user_id = int(raw)
    except (TypeError, ValueError):
        return None
    if user_id <= 0:
        return None
    return db.session.get(User, user_id)


def current_user_id():
    user = current_user()
    return user.id if user else None
