from datetime import datetime

from flask import Blueprint
from flask_jwt_extended import jwt_required
from utils.auth import current_user

from models.notice import Notice
from models.complaint import Complaint
from models.db import db
from models.payment import MaintenanceBill, Payment
from models.user import User
from models.vendor import Vendor
from models.work_order import WorkOrder
from utils.validators import REQUEST_CATEGORY_TO_JOB, normalize_vendor_services
from services.finance import admin_summary, resident_summary
from services.operations import complaint_counts, open_work_orders_count


dashboard_bp = Blueprint("dashboard", __name__)



@dashboard_bp.get("/dashboard")
@jwt_required()
def dashboard():
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    if user.role == "resident":
        bills = MaintenanceBill.query.filter_by(user_id=user.id).order_by(MaintenanceBill.id.desc()).all()
        payments = (
            Payment.query.filter_by(user_id=user.id, status="paid")
            .order_by(Payment.id.desc())
            .limit(5)
            .all()
        )
        finance = resident_summary(user.id)
        due = finance["due"]
        paid = finance["paid"]
        complaints = Complaint.query.filter_by(user_id=user.id).count()
        active_requests = WorkOrder.query.filter(
            WorkOrder.resident_id == user.id,
            WorkOrder.status.notin_(("completed", "cancelled")),
        ).count()
        requests = (
            WorkOrder.query.filter_by(resident_id=user.id)
            .order_by(WorkOrder.id.desc())
            .limit(5)
            .all()
        )

        return {
            "role": "resident",
            "user": user.to_dict(),
            "due": due,
            "paid": paid,
            "complaints": complaints,
            "recent_payments": [p.to_dict() for p in payments],
            "bills": [b.to_dict() for b in bills],
            "work_orders": [w.to_dict() for w in requests],
            "active_requests": active_requests,
            "paid_count": Payment.query.filter_by(user_id=user.id, status="paid").count(),
            "pending_bills": [b.to_dict() for b in bills if b.status != "paid"][:3],
            "recent_notices": [n.to_dict() for n in Notice.query.order_by(Notice.id.desc()).limit(3).all()],
        }

    if user.role == "vendor":
        profile = Vendor.query.filter_by(user_id=user.id, status="active").first()
        orders = (
            WorkOrder.query.filter(
                WorkOrder.vendor_id == profile.id,
                WorkOrder.status.in_(("accepted", "in_progress")),
            )
            .order_by(WorkOrder.id.desc())
            .limit(20)
            .all()
            if profile
            else []
        )
        vendor_jobs = normalize_vendor_services(profile.service) if profile else []
        allowed_categories = [
            category.title()
            for category, job in REQUEST_CATEGORY_TO_JOB.items()
            if job in vendor_jobs
        ]
        open_jobs = (
            WorkOrder.query.filter(
                WorkOrder.status == "open",
                WorkOrder.category.in_(allowed_categories),
            )
            .order_by(WorkOrder.id.desc())
            .limit(3)
            .all()
            if allowed_categories
            else []
        )
        open_jobs_count = (
            WorkOrder.query.filter(
                WorkOrder.status == "open",
                WorkOrder.category.in_(allowed_categories),
            ).count()
            if allowed_categories
            else 0
        )

        return {
            "role": "vendor",
            "user": user.to_dict(),
            "vendor": profile.to_dict() if profile else None,
            "work_orders": [w.to_dict() for w in orders],
            "open_jobs_count": open_jobs_count,
            "open_jobs": [w.to_dict() for w in open_jobs],
        }

    finance = admin_summary()
    total_billed = finance["total_billed"]
    total_collected = finance["total_collected"]
    total_expenses = finance["total_expenses"]
    total_pending = finance["total_pending"]
    balance = finance["balance"]
    collection_rate = finance["collection_rate"]
    complaint_breakdown = complaint_counts()

    recent_activity = []
    for item in User.query.order_by(User.created_at.desc()).limit(5).all():
        recent_activity.append({"kind": "resident" if item.role == "resident" else item.role, "title": f"{item.name} joined NestLedger", "detail": item.email, "created_at": item.created_at.isoformat() if item.created_at else None})
    for item in Payment.query.order_by(Payment.created_at.desc()).limit(5).all():
        recent_activity.append({"kind": "payment", "title": f"Payment {item.status}", "detail": f"{item.user.name if item.user else 'Resident'} · ₹{item.amount:,.0f}", "created_at": item.created_at.isoformat() if item.created_at else None})
    for item in Complaint.query.order_by(Complaint.created_at.desc()).limit(5).all():
        recent_activity.append({"kind": "complaint", "title": item.subject, "detail": f"{item.user.name if item.user else 'Resident'} · {item.status}", "created_at": item.created_at.isoformat() if item.created_at else None})
    for item in WorkOrder.query.order_by(WorkOrder.created_at.desc()).limit(5).all():
        recent_activity.append({"kind": "workorder", "title": item.title, "detail": f"{item.apartment or 'Community'} · {item.status}", "created_at": item.created_at.isoformat() if item.created_at else None})
    recent_activity.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return {
        "role": "admin",
        "user": user.to_dict(),
        "residents": User.query.filter_by(role="resident").count(),
        "vendors": User.query.filter_by(role="vendor").count(),
        "collection": total_collected,
        "expenses": total_expenses,
        "open_complaints": sum(v for k, v in complaint_breakdown.items() if k != "closed"),
        "work_orders": WorkOrder.query.count(),
        "open_work_orders": open_work_orders_count(),
        "complaint_breakdown": {
            status: int(complaint_breakdown.get(status, 0))
            for status in ("open", "in_progress", "resolved", "closed")
        },
        "recent_notices": [n.to_dict() for n in Notice.query.order_by(Notice.id.desc()).limit(4).all()],
        "recent_activity": recent_activity[:8],
        "financials": {
            "total_billed": total_billed,
            "total_collected": total_collected,
            "total_pending": total_pending,
            "total_expenses": total_expenses,
            "balance": balance,
            "collection_rate": collection_rate,
        },
    }
