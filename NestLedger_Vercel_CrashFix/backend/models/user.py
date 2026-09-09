from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from models.db import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="resident", index=True)
    phone = db.Column(db.String(30))
    apartment = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(
        self,
        name: str,
        email: str,
        role: str = "resident",
        phone: str | None = None,
        apartment: str | None = None,
        password_hash: str | None = None,
    ):
        self.name = name
        self.email = email
        self.role = role
        self.phone = phone
        self.apartment = apartment
        if password_hash is not None:
            self.password_hash = password_hash

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "phone": self.phone,
            "apartment": self.apartment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
