from datetime import datetime

from models.db import db


class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(40), default="COMMUNITY")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "tag": self.tag,
            "author_name": self.author.name if self.author else "Management",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
