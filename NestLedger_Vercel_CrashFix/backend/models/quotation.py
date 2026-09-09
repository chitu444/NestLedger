from datetime import datetime

from models.db import db

QUOTE_STATUSES = {"pending", "accepted", "rejected", "withdrawn"}


class Quotation(db.Model):
    """A vendor's price quote submitted against an open WorkOrder.

    A vendor may have at most one *pending* quote per work order (submitting
    again updates the existing pending quote rather than creating a
    duplicate). When a resident/admin accepts one quote, every other pending
    quote on that same work order is flipped to "rejected" in the same
    transaction -- see routes/work_orders.py:accept_quote.
    """

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(
        db.Integer,
        db.ForeignKey("work_order.id"),
        nullable=False,
        index=True,
    )
    vendor_id = db.Column(
        db.Integer,
        db.ForeignKey("vendor.id"),
        nullable=False,
        index=True,
    )
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    work_order = db.relationship("WorkOrder", backref=db.backref("quotations", lazy="dynamic"))
    vendor = db.relationship("Vendor", backref="quotes")

    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor.name if self.vendor else None,
            "vendor_service": self.vendor.service if self.vendor else None,
            "vendor_contact": self.vendor.contact if self.vendor else None,
            "amount": self.amount,
            "note": self.note,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
