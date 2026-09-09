"""Database-backed finance queries kept out of HTTP route handlers."""
from sqlalchemy import func
from models.db import db
from models.expense import Expense
from models.payment import MaintenanceBill, Payment


def admin_summary():
    billed = float(db.session.query(func.coalesce(func.sum(MaintenanceBill.amount), 0)).scalar() or 0)
    collected = float(db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.status == 'paid').scalar() or 0)
    expenses = float(db.session.query(func.coalesce(func.sum(Expense.amount), 0)).scalar() or 0)
    pending = max(billed - collected, 0)
    return {
        'total_billed': billed,
        'total_collected': collected,
        'total_pending': pending,
        'total_expenses': expenses,
        'balance': collected - expenses,
        'collection_rate': round((collected / billed) * 100, 2) if billed else 0.0,
    }


def resident_summary(user_id):
    billed = float(db.session.query(func.coalesce(func.sum(MaintenanceBill.amount), 0)).filter(MaintenanceBill.user_id == user_id, MaintenanceBill.status != 'paid').scalar() or 0)
    collected = float(db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.user_id == user_id, Payment.status == 'paid').scalar() or 0)
    return {'due': billed, 'paid': collected}
