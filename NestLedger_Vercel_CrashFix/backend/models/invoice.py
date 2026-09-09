from datetime import datetime

from models.db import db


class Invoice(db.Model):
    __table_args__ = (db.Index("ix_invoice_vendor_status_created", "vendor_id", "status", "created_at"),)
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(
        db.Integer,
        db.ForeignKey("vendor.id"),
        nullable=False,
        index=True,
    )
    work_order_id = db.Column(db.Integer, index=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default="pending", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vendor = db.relationship("Vendor")

    def to_dict(self):
        return {
            "id": self.id,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor.name if self.vendor else "",
            "work_order_id": self.work_order_id,
            "amount": self.amount,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
