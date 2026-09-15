from models.db import db


class ApartmentSlot(db.Model):
    __tablename__ = "apartment_slot"
    code = db.Column(db.String(10), primary_key=True)
    claimed_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
