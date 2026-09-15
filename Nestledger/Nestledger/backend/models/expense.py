from datetime import datetime

from models.db import db


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "description": self.description,
            "amount": self.amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
