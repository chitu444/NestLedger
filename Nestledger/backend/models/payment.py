from datetime import datetime

from models.db import db


class MaintenanceBill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), default="Monthly Maintenance")
    month = db.Column(db.String(40), nullable=False)
    due_date = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(30), default="pending", index=True)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id], backref="bills")
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": self.amount,
            "description": self.description,
            "month": self.month,
            "due_date": self.due_date,
            "status": self.status,
            "assigned_by_id": self.assigned_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PaymentWebhookEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(160), nullable=False, unique=True, index=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    bill_id = db.Column(
        db.Integer,
        db.ForeignKey("maintenance_bill.id"),
        nullable=True,
        index=True,
    )
    work_order_id = db.Column(
        db.Integer,
        db.ForeignKey("work_order.id"),
        nullable=True,
        index=True,
    )
    payment_type = db.Column(db.String(40), default="maintenance", index=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), default="Maintenance")
    status = db.Column(db.String(30), default="created", index=True)
    razorpay_order_id = db.Column(db.String(120), unique=True)
    razorpay_payment_id = db.Column(db.String(120), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="payments")
    bill = db.relationship("MaintenanceBill", backref="payments")
    work_order = db.relationship("WorkOrder", backref="payments")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else None,
            "bill_id": self.bill_id,
            "work_order_id": self.work_order_id,
            "payment_type": self.payment_type,
            "amount": self.amount,
            "description": self.description,
            "status": self.status,
            "razorpay_order_id": self.razorpay_order_id,
            "razorpay_payment_id": self.razorpay_payment_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
