from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import func

from models.complaint import Complaint
from models.db import db
from models.expense import Expense
from models.payment import MaintenanceBill, Payment
from models.user import User
from models.vendor import Vendor
from models.work_order import WorkOrder
from utils.validators import REQUEST_CATEGORY_TO_JOB


dashboard_bp = Blueprint("dashboard", __name__)


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


def total_amount(query):
    return float(query.scalar() or 0)


@dashboard_bp.get("/dashboard")
@jwt_required()
def dashboard():
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    if user.role == "resident":
        bills = MaintenanceBill.query.filter_by(user_id=user.id).order_by(MaintenanceBill.id.desc()).all()
        payments = Payment.query.filter_by(user_id=user.id, status="paid").order_by(Payment.id.desc()).all()
        complaints = Complaint.query.filter_by(user_id=user.id).count()
        requests = WorkOrder.query.filter_by(resident_id=user.id).order_by(WorkOrder.id.desc()).all()

        return {
            "role": "resident",
            "user": user.to_dict(),
            "due": sum(b.amount for b in bills if b.status != "paid"),
            "paid": sum(p.amount for p in payments),
            "complaints": complaints,
            "recent_payments": [p.to_dict() for p in payments[:5]],
            "bills": [b.to_dict() for b in bills],
            "work_orders": [w.to_dict() for w in requests[:5]],
            "active_requests": sum(
                w.status not in {"completed", "cancelled"} for w in requests
            ),
        }

    if user.role == "vendor":
        profile = Vendor.query.filter_by(user_id=user.id).first()
        orders = (
            WorkOrder.query.filter_by(vendor_id=profile.id).order_by(WorkOrder.id.desc()).all()
            if profile
            else []
        )
        active = [w for w in orders if w.status in {"accepted", "in_progress"}]
        vendor_job = (profile.service or "").strip().lower() if profile else None
        allowed_categories = [
            category.title() for category, job in REQUEST_CATEGORY_TO_JOB.items()
            if job == vendor_job
        ]
        open_jobs = (
            WorkOrder.query.filter(
                WorkOrder.status == "open",
                WorkOrder.category.in_(allowed_categories),
            ).order_by(WorkOrder.id.desc()).all()
            if allowed_categories else []
        )

        return {
            "role": "vendor",
            "user": user.to_dict(),
            "vendor": profile.to_dict() if profile else None,
            "work_orders": [w.to_dict() for w in active],
            "open_jobs_count": len(open_jobs),
            "open_jobs": [w.to_dict() for w in open_jobs[:3]],
        }

    total_billed = total_amount(db.session.query(func.sum(MaintenanceBill.amount)))
    total_collected = total_amount(
        db.session.query(func.sum(Payment.amount)).filter(Payment.status == "paid")
    )
    total_expenses = total_amount(db.session.query(func.sum(Expense.amount)))
    total_pending = max(total_billed - total_collected, 0)
    balance = total_collected - total_expenses
    collection_rate = round((total_collected / total_billed) * 100, 2) if total_billed else 0.0

    return {
        "role": "admin",
        "user": user.to_dict(),
        "residents": User.query.filter_by(role="resident").count(),
        "vendors": User.query.filter_by(role="vendor").count(),
        "collection": total_collected,
        "expenses": total_expenses,
        "open_complaints": Complaint.query.filter(Complaint.status != "closed").count(),
        "work_orders": WorkOrder.query.count(),
        "open_work_orders": WorkOrder.query.filter_by(status="open").count(),
        "financials": {
            "total_billed": total_billed,
            "total_collected": total_collected,
            "total_pending": total_pending,
            "total_expenses": total_expenses,
            "balance": balance,
            "collection_rate": collection_rate,
        },
    }
