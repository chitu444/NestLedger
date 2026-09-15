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

    user = db.relationship("User", backref="vendor_profile", uselist=False, lazy="joined")

    def to_dict(self):
        # Cache rating aggregates once per request; vendor tables otherwise
        # issue one extra query for every row.
        from sqlalchemy import func
        from models.rating import Rating

        cache = db.session.info.get("nestledger_vendor_ratings")
        if cache is None:
            rows = (
                db.session.query(
                    Rating.vendor_id,
                    func.avg(Rating.stars),
                    func.count(Rating.id),
                )
                .group_by(Rating.vendor_id)
                .all()
            )
            cache = {
                vendor_id: (round(float(avg), 1), int(count))
                for vendor_id, avg, count in rows
            }
            db.session.info["nestledger_vendor_ratings"] = cache

        average_rating, rating_count = cache.get(self.id, (None, 0))

        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "service": self.service,
            "contact": self.contact,
            "contract": self.contract,
            "status": self.status,
            "average_rating": average_rating,
            "rating_count": rating_count,
        }
