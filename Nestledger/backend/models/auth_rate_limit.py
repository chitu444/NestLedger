from datetime import datetime

from models.db import db


class AuthRateLimit(db.Model):
    __tablename__ = "auth_rate_limit"
    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(220), nullable=False, unique=True, index=True)
    failures = db.Column(db.Integer, nullable=False, default=0)
    window_started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    blocked_until = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
