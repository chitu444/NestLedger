from datetime import datetime
import secrets

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from models.db import db
from models.expense import Expense
from models.notification import notify
from models.payment import Payment, MaintenanceBill
from models.user import User
from models.vendor import Vendor
from models.work_order import WorkOrder
from utils.validators import required_text, valid_amount, valid_email, valid_password, valid_phone, VENDOR_JOB_TITLES, REQUEST_CATEGORY_TO_JOB


admin_bp = Blueprint("admin", __name__)


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


def require_admin():
    user = current_user()
    if user is None or user.role != "admin":
        return None
    return user


@admin_bp.get("/admin/users")
@jwt_required()
def users():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    return {
        "users": [
            user.to_dict()
            for user in User.query.order_by(User.id.desc()).all()
        ]
    }


@admin_bp.post("/admin/expenses")
@jwt_required()
def add_expense():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    data = request.get_json(silent=True) or {}
    category = str(data.get("category", "")).strip()
    description = str(data.get("description", "")).strip()

    for value, label in ((category, "Category"), (description, "Description")):
        ok, err = required_text(value, label, max_len=255)
        if not ok:
            return {"error": err}, 400

    ok, err = valid_amount(data.get("amount"), allow_zero=False)
    if not ok:
        return {"error": err}, 400
    amount = float(data.get("amount"))

    expense = Expense(
        category=category,
        description=description,
        amount=amount,
    )
    db.session.add(expense)
    db.session.commit()
    return {"expense": expense.to_dict()}, 201


@admin_bp.get("/admin/expenses")
@jwt_required()
def expenses():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    return {
        "expenses": [
            expense.to_dict()
            for expense in Expense.query.order_by(Expense.id.desc()).all()
        ]
    }


@admin_bp.post("/admin/residents")
@jwt_required()
def add_resident():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    apartment = str(data.get("apartment", "")).strip()

    for value, label, max_len in ((name, "Name", 120), (apartment, "Apartment / Flat", 60)):
        ok, err = required_text(value, label, max_len=max_len)
        if not ok:
            return {"error": err}, 400
    ok, err = valid_email(email)
    if not ok:
        return {"error": err}, 400
    ok, err = valid_phone(phone, required=True)
    if not ok:
        return {"error": err}, 400
    if User.query.filter_by(email=email).first():
        return {"error": "Email already registered"}, 409

    # URL-safe, sufficiently long temporary password. It is returned only once
    # to the authenticated admin so it can be handed to the resident securely.
    temporary_password = secrets.token_urlsafe(9)
    user = User(name=name, email=email, role="resident", phone=phone, apartment=apartment)
    user.set_password(temporary_password)
    db.session.add(user)
    db.session.commit()

    return {
        "message": "Resident account created successfully",
        "resident": user.to_dict(),
        "temporary_password": temporary_password,
    }, 201


@admin_bp.post("/admin/vendors")
@jwt_required()
def add_vendor():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    job_title = str(data.get("job_title", data.get("service", ""))).strip().lower()
    contact = str(data.get("contact", "")).strip()
    contract = str(data.get("contract", "")).strip() or None

    ok, err = required_text(name, "Name", max_len=150)
    if not ok:
        return {"error": err}, 400
    ok, err = valid_email(email)
    if not ok:
        return {"error": err}, 400
    ok, err = valid_password(password)
    if not ok:
        return {"error": err}, 400
    ok, err = valid_phone(contact, required=True)
    if not ok:
        return {"error": err}, 400
    if job_title not in VENDOR_JOB_TITLES:
        return {"error": "Job title must be one of: Plumber, Electrician, Carpenter, Painter, Cleaner"}, 400
    if User.query.filter_by(email=email).first():
        return {"error": "Email already registered"}, 409

    user = User(name=name, email=email, role="vendor", phone=contact, apartment=None)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    vendor = Vendor(
        user_id=user.id,
        name=name,
        service=job_title.title(),
        contact=contact,
        contract=contract,
        status="active",
    )
    db.session.add(vendor)
    db.session.commit()
    return {"message": "Vendor account created successfully", "vendor": vendor.to_dict(), "user": user.to_dict()}, 201


@admin_bp.get("/admin/vendors")
@jwt_required()
def vendor_list():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    return {
        "vendors": [
            vendor.to_dict()
            for vendor in Vendor.query.order_by(Vendor.id.desc()).all()
        ]
    }





@admin_bp.get("/admin/maintenance-bills")
@jwt_required()
def maintenance_bills():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    bills = MaintenanceBill.query.order_by(MaintenanceBill.id.desc()).all()
    return {"bills": [
        {
            **bill.to_dict(),
            "resident_name": bill.user.name if bill.user else None,
            "resident_email": bill.user.email if bill.user else None,
            "apartment": bill.user.apartment if bill.user else None,
        }
        for bill in bills
    ]}


@admin_bp.post("/admin/maintenance-bills")
@jwt_required()
def create_maintenance_bill():
    admin = require_admin()
    if admin is None:
        return {"error": "Admin access required"}, 403

    data = request.get_json(silent=True) or {}
    try:
        resident_id = int(data.get("resident_id"))
    except (TypeError, ValueError):
        return {"error": "A resident must be selected"}, 400

    resident = db.session.get(User, resident_id)
    if resident is None or resident.role != "resident":
        return {"error": "Invalid resident"}, 400

    ok, err = valid_amount(data.get("amount"), allow_zero=False)
    if not ok:
        return {"error": err}, 400

    month = str(data.get("month") or "").strip()
    due_date = str(data.get("due_date") or "").strip()
    description = str(data.get("description") or "Monthly Maintenance").strip()
    for value, label, max_len in ((month, "Billing month", 40), (due_date, "Due date", 30), (description, "Description", 255)):
        ok, err = required_text(value, label, max_len=max_len)
        if not ok:
            return {"error": err}, 400

    existing = MaintenanceBill.query.filter_by(user_id=resident.id, month=month).first()
    if existing:
        return {"error": f"A maintenance bill for {month} already exists for this resident"}, 409

    bill = MaintenanceBill(
        user_id=resident.id,
        amount=float(data.get("amount")),
        description=description,
        month=month,
        due_date=due_date,
        status="pending",
        assigned_by_id=admin.id,
    )
    db.session.add(bill)
    db.session.commit()

    notify(
        resident.id,
        "New Maintenance Bill",
        f"{bill.description} of ₹{bill.amount:,.0f} is due on {bill.due_date}.",
        notif_type="payment",
    )
    return {"message": "Maintenance bill assigned successfully", "bill": bill.to_dict()}, 201


@admin_bp.get("/admin/payments")
@jwt_required()
def payments():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    return {
        "payments": [
            payment.to_dict()
            for payment in Payment.query.order_by(Payment.id.desc()).all()
        ]
    }


def _score_vendor(orders):
    """Analytics-based vendor performance score (NOT an AI score).

    Formula, weighted out of 100:
      - Completion rate   50% -> completed / (completed + cancelled/withdrawn)
      - On-time rate      30% -> of completed jobs, share finished by due_date
      - Cancellation rate 20% -> penalizes accepted jobs that were withdrawn
                                 (i.e. 20% * (1 - cancellation_rate))

    "Withdrawn" jobs are ones this vendor accepted and later returned to the
    open board (WorkOrder.status back to "open" with no vendor_id) -- since
    that history isn't stored on the order itself, cancellation rate here
    counts orders with status "cancelled" that this vendor had accepted
    before a resident/admin cancelled them, which is the data actually
    available on the WorkOrder row.
    """
    completed = [o for o in orders if o.status == "completed"]
    cancelled = [o for o in orders if o.status == "cancelled"]
    active = [o for o in orders if o.status in {"accepted", "in_progress"}]
    total = len(orders)

    denom = len(completed) + len(cancelled)
    completion_rate = (len(completed) / denom) if denom else 1.0

    on_time = 0
    timed = 0
    for o in completed:
        if not o.due_date or not o.completed_at:
            continue
        due = _parse_loose_date(o.due_date)
        if due is None:
            continue
        timed += 1
        if o.completed_at.date() <= due:
            on_time += 1
    on_time_rate = (on_time / timed) if timed else 1.0

    cancellation_rate = (len(cancelled) / total) if total else 0.0

    score = (
        completion_rate * 50
        + on_time_rate * 30
        + (1 - cancellation_rate) * 20
    )

    durations = [
        (o.completed_at - o.accepted_at).total_seconds() / 3600
        for o in completed
        if o.accepted_at and o.completed_at
    ]
    avg_hours = round(sum(durations) / len(durations), 1) if durations else None

    return {
        "score": round(score, 1),
        "total_jobs": total,
        "completed_jobs": len(completed),
        "cancelled_jobs": len(cancelled),
        "active_jobs": len(active),
        "completion_rate": round(completion_rate * 100, 1),
        "on_time_completion_rate": round(on_time_rate * 100, 1) if timed else None,
        "average_completion_hours": avg_hours,
    }


def _parse_loose_date(value: str):
    """Best-effort parse of the free-text due_date field (e.g. '10 Sep 2026')."""
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


@admin_bp.get("/admin/vendor-performance")
@jwt_required()
def vendor_performance():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    results = []
    for vendor in Vendor.query.order_by(Vendor.name).all():
        orders = WorkOrder.query.filter_by(vendor_id=vendor.id).all()
        metrics = _score_vendor(orders)
        results.append({"vendor": vendor.to_dict(), **metrics})

    results.sort(key=lambda r: r["score"], reverse=True)
    return {"vendor_performance": results}
