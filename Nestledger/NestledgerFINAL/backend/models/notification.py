from datetime import datetime

from models.db import db
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app


class Notification(db.Model):
    __table_args__ = (db.Index("ix_notification_user_read_created", "user_id", "is_read", "created_at"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(400), nullable=False)
    type = db.Column(db.String(40), default="general", index=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="notifications")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "type": self.type,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def notify(user_id, title, message, notif_type="general"):
    """Create and persist a single notification for one event.

    Call this exactly once, at the moment the real event happens (payment
    verified, status changed, vendor accepted, etc). Never call this from a
    polling/refresh handler -- that would create duplicate notifications on
    every dashboard refresh. Commits immediately so the notification is
    visible even if the caller's own commit already ran.
    """
    if not user_id:
        return None
    n = Notification(user_id=user_id, title=title, message=message, type=notif_type)
    try:
        db.session.add(n)
        db.session.commit()
        return n
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Notification creation failed")
        return None


def notify_many(user_ids, title, message, notif_type="general"):
    """Create the same notification for several users (e.g. a new notice)."""
    created = []
    for uid in {uid for uid in user_ids if uid}:
        n = Notification(user_id=uid, title=title, message=message, type=notif_type)
        db.session.add(n)
        created.append(n)
    try:
        db.session.commit()
        return created
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Bulk notification creation failed")
        return []
