from datetime import datetime

from models.db import db


class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), default="General")
    description = db.Column(db.Text)
    resident_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    apartment = db.Column(db.String(60))
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"), index=True)
    amount = db.Column(db.Float, default=0)
    due_date = db.Column(db.String(30))
    status = db.Column(db.String(30), default="open", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    vendor = db.relationship("Vendor")
    resident = db.relationship("User")

    def to_dict(self):
        # Local imports avoid a circular import at module load time (mirrors
        # the existing pattern in routes/work_orders.py for notify_many).
        from models.quotation import Quotation
        from models.rating import Rating
        from models.payment import Payment

        quotes_count = None
        if self.status == "open":
            quotes_count = Quotation.query.filter_by(
                work_order_id=self.id, status="pending"
            ).count()

        rating = Rating.query.filter_by(work_order_id=self.id).first()
        paid_payment = Payment.query.filter_by(work_order_id=self.id, status="paid").first()
        pending_payment = Payment.query.filter_by(work_order_id=self.id, status="created").first()

        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "resident_id": self.resident_id,
            "resident_name": self.resident.name if self.resident else None,
            "apartment": self.apartment,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor.name if self.vendor else "Unassigned",
            "vendor_service": self.vendor.service if self.vendor else None,
            "vendor_contact": self.vendor.contact if self.vendor else None,
            "amount": self.amount,
            "due_date": self.due_date,
            "status": self.status,
            "payment_status": "paid" if paid_payment else ("pending" if pending_payment else "unpaid"),
            "payment_id": paid_payment.id if paid_payment else (pending_payment.id if pending_payment else None),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "quotes_count": quotes_count,
            "rating": rating.to_dict() if rating else None,
        }
