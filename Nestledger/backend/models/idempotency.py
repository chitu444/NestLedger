from datetime import datetime

from models.db import db


class IdempotencyRecord(db.Model):
    __tablename__ = "idempotency_record"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    scope = db.Column(db.String(220), nullable=False)
    key = db.Column(db.String(200), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="processing")
    response_status = db.Column(db.Integer, nullable=True)
    response_body = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
        db.Index("ix_idempotency_created", "created_at"),
    )
