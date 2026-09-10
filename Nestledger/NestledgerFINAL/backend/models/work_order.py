from datetime import datetime

from sqlalchemy import func

from models.db import db


class WorkOrder(db.Model):
    __table_args__ = (db.Index("ix_workorder_resident_status_created", "resident_id", "status", "created_at"), db.Index("ix_workorder_vendor_status_created", "vendor_id", "status", "created_at"),)
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

    vendor = db.relationship("Vendor", lazy="joined")
    resident = db.relationship("User", lazy="joined")

    @staticmethod
    def prime_summary(order_ids):
        """Prime only the work-order rows being serialized for this request."""
        ids = {int(x) for x in (order_ids or []) if x}
        if not ids:
            return
        from models.quotation import Quotation
        from models.rating import Rating
        from models.payment import Payment
        quote_counts = dict(
            db.session.query(Quotation.work_order_id, func.count(Quotation.id))
            .filter(Quotation.status == "pending", Quotation.work_order_id.in_(ids))
            .group_by(Quotation.work_order_id).all()
        )
        ratings = {r.work_order_id: r for r in Rating.query.filter(Rating.work_order_id.in_(ids)).all()}
        paid_ids = dict(
            db.session.query(Payment.work_order_id, func.min(Payment.id))
            .filter(Payment.status == "paid", Payment.work_order_id.in_(ids))
            .group_by(Payment.work_order_id).all()
        )
        pending_ids = dict(
            db.session.query(Payment.work_order_id, func.min(Payment.id))
            .filter(Payment.status == "created", Payment.work_order_id.in_(ids))
            .group_by(Payment.work_order_id).all()
        )
        db.session.info["nestledger_work_order_summary"] = {
            "ids": ids, "quote_counts": quote_counts, "ratings": ratings,
            "paid_ids": paid_ids, "pending_ids": pending_ids,
        }

    @staticmethod
    def _summary_cache(order_id=None):
        cache = db.session.info.get("nestledger_work_order_summary")
        if cache is None or (order_id and order_id not in cache.get("ids", set())):
            WorkOrder.prime_summary([order_id] if order_id else [])
            cache = db.session.info.get("nestledger_work_order_summary", {})
        return cache

    def to_dict(self):
        cache = self._summary_cache(self.id)
        quote_counts = cache["quote_counts"]
        rating = cache["ratings"].get(self.id)
        paid_id = cache["paid_ids"].get(self.id)
        pending_id = cache["pending_ids"].get(self.id)

        quotes_count = quote_counts.get(self.id, 0) if self.status == "open" else None

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
            "payment_status": "paid" if paid_id else ("pending" if pending_id else "unpaid"),
            "payment_id": paid_id or pending_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "quotes_count": quotes_count,
            "rating": rating.to_dict() if rating else None,
        }
