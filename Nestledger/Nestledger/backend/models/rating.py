from datetime import datetime

from models.db import db


class Rating(db.Model):
    """A resident's rating + remarks for a vendor on one completed WorkOrder.

    Exactly one Rating per work order (enforced at the application layer in
    routes/work_orders.py:rate_order, and by the unique index here).
    """

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(
        db.Integer,
        db.ForeignKey("work_order.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    vendor_id = db.Column(
        db.Integer,
        db.ForeignKey("vendor.id"),
        nullable=False,
        index=True,
    )
    resident_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    stars = db.Column(db.Integer, nullable=False)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref=db.backref("rating", uselist=False))
    vendor = db.relationship("Vendor", backref="ratings")
    resident = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "vendor_id": self.vendor_id,
            "resident_id": self.resident_id,
            "resident_name": self.resident.name if self.resident else None,
            "stars": self.stars,
            "remarks": self.remarks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
