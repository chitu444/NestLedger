from models.db import db


class Vendor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        unique=True,
        nullable=True,
        index=True,
    )
    name = db.Column(db.String(150), nullable=False)
    service = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(30), nullable=False)
    contract = db.Column(db.String(100))
    status = db.Column(db.String(30), default="active", index=True)

    user = db.relationship("User", backref="vendor_profile", uselist=False)

    def to_dict(self):
        # Local import avoids a circular import at module load time.
        from models.rating import Rating

        stars = [
            r.stars for r in Rating.query.filter_by(vendor_id=self.id).all()
        ]
        average_rating = round(sum(stars) / len(stars), 1) if stars else None

        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "service": self.service,
            "contact": self.contact,
            "contract": self.contract,
            "status": self.status,
            "average_rating": average_rating,
            "rating_count": len(stars),
        }
