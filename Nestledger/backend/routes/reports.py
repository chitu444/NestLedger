from collections import defaultdict
from datetime import datetime

from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.auth import current_user
from sqlalchemy import func

from models.complaint import Complaint
from models.db import db
from models.expense import Expense
from models.payment import MaintenanceBill, Payment
from models.rating import Rating
from models.user import User
from models.vendor import Vendor
from models.work_order import WorkOrder

reports_bp = Blueprint("reports", __name__)


def month_key(dt):
    return (dt.year, dt.month)


def month_label(year, month):
    return datetime(year, month, 1).strftime("%b")


def six_month_window():
    now = datetime.utcnow()
    months = []
    y, m = now.year, now.month
    for offset in range(5, -1, -1):
        mm = m - offset
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append((yy, mm))
    start_year, start_month = months[0]
    start = datetime(start_year, start_month, 1)
    return now, months, start


@reports_bp.get("/reports")
@jwt_required()
def reports():
    user = current_user()
    if user is None or user.role != "admin":
        return {"error": "Admin access required"}, 403

    # Keep the heavy BI route aggregate-first. The previous implementation
    # loaded every payment/expense/work-order row into Python on every refresh.
    collection = float(
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == "paid", Payment.bill_id.isnot(None))
        .scalar()
        or 0
    )
    expense_total = float(
        db.session.query(func.coalesce(func.sum(Expense.amount), 0)).scalar() or 0
    )
    billed = float(
        db.session.query(func.coalesce(func.sum(MaintenanceBill.amount), 0)).scalar() or 0
    )
    pending = max(billed - collection, 0)

    now, months, start = six_month_window()
    payments = (
        Payment.query.filter(Payment.status == "paid", Payment.bill_id.isnot(None), Payment.created_at >= start)
        .with_entities(Payment.created_at, Payment.amount)
        .all()
    )
    expenses = (
        Expense.query.filter(Expense.created_at >= start)
        .with_entities(Expense.created_at, Expense.amount, Expense.category)
        .all()
    )

    collected_by_month = defaultdict(float)
    expense_by_month = defaultdict(float)
    category_totals = defaultdict(float)
    for created_at, amount in payments:
        if created_at:
            collected_by_month[month_key(created_at)] += float(amount or 0)
    for created_at, amount, category in expenses:
        if created_at:
            expense_by_month[month_key(created_at)] += float(amount or 0)
        category_totals[category or "Other"] += float(amount or 0)

    monthly = [
        {
            "label": month_label(yy, mm),
            "collected": round(collected_by_month[(yy, mm)], 2),
            "expenses": round(expense_by_month[(yy, mm)], 2),
        }
        for yy, mm in months
    ]

    expense_categories = [
        {"label": k, "value": round(v, 2)}
        for k, v in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:7]
    ]

    complaint_counts = dict(
        db.session.query(Complaint.status, func.count(Complaint.id))
        .group_by(Complaint.status)
        .all()
    )
    complaint_rows = [
        {"label": label, "value": int(complaint_counts.get(key, 0))}
        for label, key in (("Open", "open"), ("In progress", "in_progress"), ("Resolved", "resolved"), ("Closed", "closed"))
    ]
    open_complaints = sum(v for k, v in complaint_counts.items() if k != "closed")
    open_work_orders = WorkOrder.query.filter(
        WorkOrder.status.notin_(("completed", "cancelled"))
    ).count()

    rating_rows = dict(
        db.session.query(
            Rating.vendor_id,
            func.avg(Rating.stars),
            func.count(Rating.id),
        )
        .group_by(Rating.vendor_id)
        .all()
    )
    job_rows = dict(
        db.session.query(WorkOrder.vendor_id, func.count(WorkOrder.id))
        .filter(WorkOrder.vendor_id.isnot(None))
        .group_by(WorkOrder.vendor_id)
        .all()
    )
    vendor_rows = []
    for vendor in Vendor.query.filter_by(status="active").order_by(Vendor.name).all():
        avg, _count = rating_rows.get(vendor.id, (None, 0))
        vendor_rows.append({
            "name": vendor.name,
            "service": vendor.service,
            "rating": round(float(avg), 1) if avg is not None else None,
            "jobs": int(job_rows.get(vendor.id, 0)),
        })
    vendor_rows.sort(key=lambda x: (x["rating"] is not None, x["rating"] or 0, x["jobs"]), reverse=True)

    rate = round(collection / billed * 100, 1) if billed else 0
    overdue = MaintenanceBill.query.filter(MaintenanceBill.status != "paid").count()
    insight = (
        "Collections are healthy; focus next on operational resolution."
        if rate >= 85 and open_complaints <= 3
        else "Prioritize overdue collections and unresolved issues from the operations queue."
        if pending > 0 or open_complaints > 0
        else "Your community has a clean operational picture right now."
    )

    return {
        "collection": round(collection, 2),
        "expenses": round(expense_total, 2),
        "pending": round(pending, 2),
        "pending_bills": overdue,
        "expense_count": Expense.query.count(),
        "collection_rate": rate,
        "open_complaints": open_complaints,
        "open_work_orders": open_work_orders,
        "monthly": monthly,
        "expense_categories": expense_categories,
        "complaints": complaint_rows,
        "vendors": vendor_rows,
        "insight": insight,
    }
