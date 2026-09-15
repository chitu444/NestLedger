from collections import defaultdict
from datetime import datetime
import logging

from flask import Blueprint
from flask_jwt_extended import verify_jwt_in_request
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from utils.auth import current_user
from models.complaint import Complaint
from models.db import db
from models.expense import Expense
from models.payment import MaintenanceBill, Payment
from models.rating import Rating
from models.vendor import Vendor
from models.work_order import WorkOrder

reports_bp = Blueprint("reports", __name__)
log = logging.getLogger(__name__)


def month_key(dt):
    return (dt.year, dt.month)


def month_label(year, month):
    return datetime(year, month, 1).strftime("%b")


def six_month_window():
    now = datetime.utcnow()
    months = []
    y, m = now.year, now.month
    for offset in range(5, -1, -1):
        mm, yy = m - offset, y
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append((yy, mm))
    yy, mm = months[0]
    return now, months, datetime(yy, mm, 1)


def _empty_report():
    now, months, _ = six_month_window()
    return {
        "collection": 0, "expenses": 0, "pending": 0, "pending_bills": 0,
        "expense_count": 0, "collection_rate": 0, "open_complaints": 0,
        "open_work_orders": 0,
        "monthly": [{"label": month_label(y, m), "collected": 0, "expenses": 0} for y, m in months],
        "expense_categories": [],
        "complaints": [{"label": x, "value": 0} for x in ("Open", "In progress", "Resolved", "Closed")],
        "vendors": [],
        "insight": "No community activity has been recorded yet.",
        "generated_at": now.isoformat(timespec="seconds"),
    }


@reports_bp.get("/reports")
def reports():
    """Admin BI endpoint. Always returns a predictable JSON shape on valid admin sessions."""
    # Verify the JWT inside the route so malformed/legacy tokens cannot escape
    # the endpoint as a ValueError (which previously became the misleading
    # generic 400 "invalid value" response).
    try:
        verify_jwt_in_request()
    except Exception:
        log.exception("BI authentication failed")
        return {"ok": False, "error": {"code": "INVALID_TOKEN", "message": "Your session token is invalid. Please sign in again."}}, 401

    user = current_user()
    if user is None:
        return {"ok": False, "error": {"code": "USER_NOT_FOUND", "message": "Your session is no longer valid. Please sign in again."}}, 401
    if user.role != "admin":
        return {"ok": False, "error": {"code": "ADMIN_REQUIRED", "message": "Admin access required."}}, 403

    try:
        collection = float(db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.status == "paid", Payment.bill_id.isnot(None)
        ).scalar() or 0)
        expense_total = float(db.session.query(func.coalesce(func.sum(Expense.amount), 0)).scalar() or 0)
        billed = float(db.session.query(func.coalesce(func.sum(MaintenanceBill.amount), 0)).scalar() or 0)
        pending = max(billed - collection, 0)

        now, months, start = six_month_window()
        payment_rows = Payment.query.filter(
            Payment.status == "paid", Payment.bill_id.isnot(None), Payment.created_at >= start
        ).with_entities(Payment.created_at, Payment.amount).all()
        expense_rows = Expense.query.filter(
            Expense.created_at >= start
        ).with_entities(Expense.created_at, Expense.amount, Expense.category).all()

        collected_by_month, expense_by_month, category_totals = defaultdict(float), defaultdict(float), defaultdict(float)
        for created_at, amount in payment_rows:
            if created_at:
                collected_by_month[month_key(created_at)] += float(amount or 0)
        for created_at, amount, category in expense_rows:
            if created_at:
                expense_by_month[month_key(created_at)] += float(amount or 0)
            category_totals[str(category or "Other")] += float(amount or 0)

        monthly = [{
            "label": month_label(y, m),
            "collected": round(collected_by_month[(y, m)], 2),
            "expenses": round(expense_by_month[(y, m)], 2),
        } for y, m in months]
        expense_categories = [
            {"label": k, "value": round(v, 2)}
            for k, v in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:8]
        ]

        complaint_counts = dict(db.session.query(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status).all())
        complaint_rows = [{"label": label, "value": int(complaint_counts.get(key, 0))}
                          for label, key in (("Open", "open"), ("In progress", "in_progress"), ("Resolved", "resolved"), ("Closed", "closed"))]
        open_complaints = sum(v for k, v in complaint_counts.items() if k != "closed")
        open_work_orders = WorkOrder.query.filter(WorkOrder.status.notin_(("completed", "cancelled"))).count()

        rating_rows = dict(db.session.query(Rating.vendor_id, func.avg(Rating.stars), func.count(Rating.id)).group_by(Rating.vendor_id).all())
        job_rows = dict(db.session.query(WorkOrder.vendor_id, func.count(WorkOrder.id)).filter(WorkOrder.vendor_id.isnot(None)).group_by(WorkOrder.vendor_id).all())
        vendor_rows = []
        for vendor in Vendor.query.filter_by(status="active").order_by(Vendor.name).all():
            avg, _count = rating_rows.get(vendor.id, (None, 0))
            vendor_rows.append({"name": vendor.name, "service": vendor.service or "General Services",
                                "rating": round(float(avg), 1) if avg is not None else None,
                                "jobs": int(job_rows.get(vendor.id, 0))})
        vendor_rows.sort(key=lambda x: (x["rating"] is not None, x["rating"] or 0, x["jobs"]), reverse=True)

        rate = round(collection / billed * 100, 1) if billed else 0
        overdue = MaintenanceBill.query.filter(MaintenanceBill.status != "paid").count()
        insight = ("Collections are healthy; focus next on operational resolution." if rate >= 85 and open_complaints <= 3 else
                   "Prioritize overdue collections and unresolved issues from the operations queue." if pending > 0 or open_complaints > 0 else
                   "Your community has a clean operational picture right now.")

        return {"ok": True, "collection": round(collection, 2), "expenses": round(expense_total, 2),
                "pending": round(pending, 2), "pending_bills": overdue, "expense_count": Expense.query.count(),
                "collection_rate": rate, "open_complaints": open_complaints, "open_work_orders": open_work_orders,
                "monthly": monthly, "expense_categories": expense_categories, "complaints": complaint_rows,
                "vendors": vendor_rows, "insight": insight, "generated_at": now.isoformat(timespec="seconds")}
    except SQLAlchemyError:
        db.session.rollback()
        log.exception("BI report database query failed")
        return {"ok": False, "error": {"code": "REPORT_DATABASE_ERROR", "message": "Business Intelligence data is temporarily unavailable."}}, 503
    except Exception:
        db.session.rollback()
        log.exception("Unexpected BI report failure")
        return {"ok": False, "error": {"code": "REPORT_ERROR", "message": "Business Intelligence could not be loaded."}}, 500
