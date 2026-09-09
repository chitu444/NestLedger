from datetime import datetime

from models.db import db


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    category = db.Column(db.String(80), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="open", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref="complaints")

    # Ordered lifecycle used to render the resident-facing timeline.
    TIMELINE = ("open", "in_progress", "resolved", "closed")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "resident_name": self.user.name if self.user else "",
            "apartment": self.user.apartment if self.user else "",
            "category": self.category,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
