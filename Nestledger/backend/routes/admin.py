from datetime import datetime, timedelta
import secrets

from flask import Blueprint, request, Response, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.auth import current_user

from models.db import db
from models.audit_log import AuditLog
from models.complaint import Complaint
from models.expense import Expense
from models.invoice import Invoice
from models.notice import Notice
from models.notification import notify
from models.payment import Payment, MaintenanceBill
from models.user import User
from models.vendor import Vendor
from models.work_order import WorkOrder
from utils.validators import required_text, valid_amount, valid_email, valid_password, valid_phone, VENDOR_JOB_TITLES, REQUEST_CATEGORY_TO_JOB
from utils.pagination import paginate_query
from sqlalchemy import or_
import csv
import io

try:
    from openpyxl import Workbook
except ImportError:  # export feature is optional at import time
    Workbook = None


admin_bp = Blueprint("admin", __name__)



def require_admin():
    user = current_user()
    if user is None or user.role != "admin":
        return None
    return user


def _export_rows(resource):
    """Return (headers, rows, filename) for an admin export. No secrets/password hashes are included."""
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip().lower()

    if resource == "residents":
        query = User.query.filter(User.role == "resident")
        if q:
            like = f"%{q}%"
            query = query.filter(or_(User.name.ilike(like), User.email.ilike(like), User.apartment.ilike(like)))
        rows = query.order_by(User.id.desc()).all()
        return ["ID", "Name", "Email", "Phone", "Apartment", "Created At"], [
            [u.id, u.name, u.email, u.phone or "", u.apartment or "", u.created_at.isoformat() if u.created_at else ""] for u in rows
        ], "nestledger_residents"

    if resource == "vendors":
        query = Vendor.query
        if status in {"active", "inactive"}: query = query.filter(Vendor.status == status)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Vendor.name.ilike(like), Vendor.service.ilike(like), Vendor.contact.ilike(like)))
        rows = query.order_by(Vendor.id.desc()).all()
        return ["ID", "Name", "Service", "Contact", "Contract", "Status"], [
            [v.id, v.name, v.service, v.contact, v.contract or "", v.status] for v in rows
        ], "nestledger_vendors"

    if resource == "expenses":
        query = Expense.query
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Expense.category.ilike(like), Expense.description.ilike(like)))
        rows = query.order_by(Expense.id.desc()).all()
        return ["ID", "Category", "Description", "Amount", "Created At"], [
            [e.id, e.category, e.description, e.amount, e.created_at.isoformat() if e.created_at else ""] for e in rows
        ], "nestledger_expenses"

    if resource == "payments":
        query = Payment.query
        if status: query = query.filter(Payment.status == status)
        if q:
            like = f"%{q}%"
            query = query.join(User, Payment.user_id == User.id).filter(or_(User.name.ilike(like), User.email.ilike(like), Payment.description.ilike(like)))
        rows = query.order_by(Payment.id.desc()).all()
        return ["ID", "Date", "Resident", "Email", "Description", "Payment Type", "Amount", "Status", "Razorpay Order ID", "Razorpay Payment ID"], [
            [p.id, p.created_at.isoformat() if p.created_at else "", p.user.name if p.user else "", p.user.email if p.user else "", p.description or "", p.payment_type or "", p.amount, p.status, p.razorpay_order_id or "", p.razorpay_payment_id or ""] for p in rows
        ], "nestledger_payments"

    if resource == "maintenance-bills":
        query = MaintenanceBill.query
        if status: query = query.filter(MaintenanceBill.status == status)
        rows = query.order_by(MaintenanceBill.id.desc()).all()
        return ["ID", "Resident", "Email", "Apartment", "Month", "Description", "Amount", "Due Date", "Status", "Created At"], [
            [b.id, b.user.name if b.user else "", b.user.email if b.user else "", b.user.apartment if b.user else "", b.month, b.description or "", b.amount, b.due_date, b.status, b.created_at.isoformat() if b.created_at else ""] for b in rows
        ], "nestledger_maintenance_bills"

    if resource == "complaints":
        query = Complaint.query
        if status: query = query.filter(Complaint.status == status)
        if q:
            like = f"%{q}%"
            query = query.join(User, Complaint.user_id == User.id).filter(or_(Complaint.subject.ilike(like), Complaint.category.ilike(like), Complaint.description.ilike(like), User.name.ilike(like)))
        rows = query.order_by(Complaint.id.desc()).all()
        return ["ID", "Resident", "Email", "Category", "Subject", "Description", "Status", "Created At", "Updated At"], [
            [c.id, c.user.name if c.user else "", c.user.email if c.user else "", c.category, c.subject, c.description, c.status, c.created_at.isoformat() if c.created_at else "", c.updated_at.isoformat() if c.updated_at else ""] for c in rows
        ], "nestledger_complaints"

    if resource == "notices":
        query = Notice.query
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Notice.title.ilike(like), Notice.body.ilike(like), Notice.tag.ilike(like)))
        rows = query.order_by(Notice.id.desc()).all()
        return ["ID", "Title", "Tag", "Body", "Author", "Created At"], [
            [n.id, n.title, n.tag or "", n.body, n.author.name if n.author else "", n.created_at.isoformat() if n.created_at else ""] for n in rows
        ], "nestledger_notices"

    if resource == "work-orders":
        query = WorkOrder.query
        if status: query = query.filter(WorkOrder.status == status)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(WorkOrder.title.ilike(like), WorkOrder.category.ilike(like), WorkOrder.description.ilike(like), WorkOrder.apartment.ilike(like)))
        rows = query.order_by(WorkOrder.id.desc()).all()
        return ["ID", "Title", "Category", "Description", "Resident", "Apartment", "Vendor", "Amount", "Due Date", "Status", "Created At", "Accepted At", "Completed At"], [
            [w.id, w.title, w.category or "", w.description or "", w.resident.name if w.resident else "", w.apartment or "", w.vendor.name if w.vendor else "", w.amount or 0, w.due_date or "", w.status, w.created_at.isoformat() if w.created_at else "", w.accepted_at.isoformat() if w.accepted_at else "", w.completed_at.isoformat() if w.completed_at else ""] for w in rows
        ], "nestledger_work_orders"

    if resource == "invoices":
        query = Invoice.query
        if status: query = query.filter(Invoice.status == status)
        rows = query.order_by(Invoice.id.desc()).all()
        return ["ID", "Vendor", "Work Order ID", "Amount", "Status", "Created At"], [
            [i.id, i.vendor.name if i.vendor else "", i.work_order_id, i.amount, i.status, i.created_at.isoformat() if i.created_at else ""] for i in rows
        ], "nestledger_invoices"

    raise ValueError("Unsupported export")


@admin_bp.get("/admin/export/<resource>")
@jwt_required()
def export_admin_data(resource):
    if require_admin() is None:
        return {"error": "Admin access required"}, 403
    if resource not in {"residents", "vendors", "expenses", "payments", "maintenance-bills", "complaints", "notices", "work-orders", "invoices"}:
        return {"error": "Unsupported export"}, 404

    fmt = (request.args.get("format") or "csv").strip().lower()
    if fmt not in {"csv", "xlsx"}:
        return {"error": "Format must be csv or xlsx"}, 400
    if fmt == "xlsx" and Workbook is None:
        return {"error": "Excel export is not available on this server"}, 503

    headers, rows, base = _export_rows(resource)
    if fmt == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        response = Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8")
        response.headers["Content-Disposition"] = f'attachment; filename="{base}.csv"'
        response.headers["Cache-Control"] = "no-store"
        return response

    book = Workbook()
    sheet = book.active
    sheet.title = resource[:31].replace("-", " ").title()
    sheet.append(headers)
    for row in rows: sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]: cell.font = cell.font.copy(bold=True)
    for column in sheet.columns:
        letter = column[0].column_letter
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 45)
        sheet.column_dimensions[letter].width = max(width, 12)
    stream = io.BytesIO()
    book.save(stream)
    stream.seek(0)
    return send_file(stream, as_attachment=True, download_name=f"{base}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", max_age=0)


@admin_bp.get("/admin/users")
@jwt_required()
def users():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    query = User.query
    role = (request.args.get("role") or "").strip().lower()
    search = (request.args.get("q") or "").strip()
    if role in {"resident", "vendor", "admin"}: query = query.filter(User.role == role)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like), User.apartment.ilike(like)))
    rows, meta = paginate_query(query.order_by(User.id.desc()), default=24)
    return {"users": [u.to_dict() for u in rows], "meta": meta}


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

    # Server-side duplicate guard for double clicks, browser retries, or duplicate
    # frontend handlers. Exact matching within a short window is treated as one
    # submission; legitimate later expenses remain unaffected.
    recent_cutoff = datetime.utcnow() - timedelta(seconds=30)
    duplicate = (
        Expense.query
        .filter(
            Expense.category == category,
            Expense.description == description,
            Expense.amount == amount,
            Expense.created_at >= recent_cutoff,
        )
        .order_by(Expense.id.desc())
        .first()
    )
    if duplicate is not None:
        return {"expense": duplicate.to_dict(), "duplicate": True}, 200

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

    query = Expense.query
    search = (request.args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Expense.category.ilike(like), Expense.description.ilike(like)))
    rows, meta = paginate_query(query.order_by(Expense.id.desc()), default=20)
    return {"expenses": [e.to_dict() for e in rows], "meta": meta}


@admin_bp.post("/admin/residents")
@jwt_required()
def add_resident():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    apartment = str(data.get("apartment", "")).strip().upper()

    for value, label, max_len in ((name, "Name", 120),):
        ok, err = required_text(value, label, max_len=max_len)
        if not ok:
            return {"error": err}, 400
    ok, err = valid_email(email)
    if not ok:
        return {"error": err}, 400
    ok, err = valid_phone(phone, required=True)
    if not ok:
        return {"error": err}, 400
    ok, err = valid_apartment(apartment, required=True)
    if not ok:
        return {"error": err}, 400
    if User.query.filter(User.role == "resident", User.apartment == apartment).first():
        return {"error": f"Apartment {apartment} is already occupied"}, 409
    if User.query.filter_by(email=email).first():
        return {"error": "Email already registered"}, 409

    # URL-safe, sufficiently long temporary password. It is returned only once
    # to the authenticated admin so it can be handed to the resident securely.
    temporary_password = secrets.token_urlsafe(9)
    user = User(name=name, email=email, role="resident", phone=phone, apartment=apartment)
    user.set_password(temporary_password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"error": f"Apartment {apartment} is already occupied"}, 409

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

    query = Vendor.query
    status = (request.args.get("status") or "").strip().lower()
    search = (request.args.get("q") or "").strip()
    if status in {"active", "inactive"}: query = query.filter(Vendor.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Vendor.name.ilike(like), Vendor.service.ilike(like), Vendor.contact.ilike(like)))
    rows, meta = paginate_query(query.order_by(Vendor.id.desc()), default=20)
    return {"vendors": [v.to_dict() for v in rows], "meta": meta}





@admin_bp.get("/admin/residents/<int:resident_id>")
@jwt_required()
def resident_detail(resident_id):
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    resident = db.session.get(User, resident_id)
    if resident is None or resident.role != "resident":
        return {"error": "Resident not found"}, 404

    return {
        "resident": resident.to_dict(),
        "bills": [b.to_dict() for b in MaintenanceBill.query.filter_by(user_id=resident.id).order_by(MaintenanceBill.id.desc()).all()],
        "payments": [p.to_dict() for p in Payment.query.filter_by(user_id=resident.id).order_by(Payment.id.desc()).all()],
        "complaints": [c.to_dict() for c in resident.complaints],
        "work_orders": [w.to_dict() for w in WorkOrder.query.filter_by(resident_id=resident.id).order_by(WorkOrder.id.desc()).all()],
    }


@admin_bp.get("/admin/audit-log")
@jwt_required()
def audit_log():
    admin = current_user()
    if admin is None or admin.role != "admin":
        return {"error": "Admin access required"}, 403
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 100))
    except (TypeError, ValueError):
        limit = 50
    rows = AuditLog.query.order_by(AuditLog.id.desc()).limit(limit).all()
    return {"audit_log": [row.to_dict() for row in rows]}


@admin_bp.get("/admin/activity")
@jwt_required()
def activity():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    events = []
    for u in User.query.order_by(User.created_at.desc()).limit(12).all():
        events.append({"kind": "resident" if u.role == "resident" else u.role, "title": f"{u.name} joined NestLedger", "detail": u.email, "created_at": u.created_at.isoformat() if u.created_at else None})
    for payment in Payment.query.order_by(Payment.created_at.desc()).limit(12).all():
        events.append({"kind": "payment", "title": f"Payment {payment.status}", "detail": f"{payment.user.name if payment.user else 'Resident'} · ₹{payment.amount:,.0f}", "created_at": payment.created_at.isoformat() if payment.created_at else None})
    for complaint in Complaint.query.order_by(Complaint.created_at.desc()).limit(12).all():
        events.append({"kind": "complaint", "title": complaint.subject, "detail": f"{complaint.user.name if complaint.user else 'Resident'} · {complaint.status}", "created_at": complaint.created_at.isoformat() if complaint.created_at else None})
    for work in WorkOrder.query.order_by(WorkOrder.created_at.desc()).limit(12).all():
        events.append({"kind": "workorder", "title": work.title, "detail": f"{work.apartment or 'Community'} · {work.status}", "created_at": work.created_at.isoformat() if work.created_at else None})
    for audit in AuditLog.query.order_by(AuditLog.id.desc()).limit(12).all():
        events.append({"kind": "audit", "title": audit.action.replace("_", " ").title(), "detail": audit.detail or audit.entity_type, "created_at": audit.created_at.isoformat() if audit.created_at else None})
    events.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"events": events[:18]}


@admin_bp.get("/admin/maintenance-bills")
@jwt_required()
def maintenance_bills():
    if require_admin() is None:
        return {"error": "Admin access required"}, 403

    query = MaintenanceBill.query
    status = (request.args.get("status") or "").strip().lower()
    if status: query = query.filter(MaintenanceBill.status == status)
    bills, meta = paginate_query(query.order_by(MaintenanceBill.id.desc()), default=20)
    return {"bills": [
        {
            **bill.to_dict(),
            "resident_name": bill.user.name if bill.user else None,
            "resident_email": bill.user.email if bill.user else None,
            "apartment": bill.user.apartment if bill.user else None,
        }
        for bill in bills
    ], "meta": meta}


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

    query = Payment.query
    status = (request.args.get("status") or "").strip().lower()
    search = (request.args.get("q") or "").strip()
    if status: query = query.filter(Payment.status == status)
    if search:
        like = f"%{search}%"
        query = query.join(User, Payment.user_id == User.id).filter(or_(User.name.ilike(like), User.email.ilike(like), Payment.description.ilike(like)))
    rows, meta = paginate_query(query.order_by(Payment.id.desc()), default=20)
    return {"payments": [p.to_dict() for p in rows], "meta": meta}


def _score_vendor(orders):
    """Deterministic vendor performance score (0-100).

    The score is based on jobs actually assigned to the vendor:
      - Completion rate: 50% -> completed / all assigned jobs
      - On-time completion: 30% -> on-time completed / completed jobs
      - Reliability: 20% -> 1 - (cancelled / assigned jobs)

    Important safeguards:
      - A vendor with no jobs scores 0, never 100.
      - A vendor with active jobs but no completed jobs has 0% completion and
        0% on-time completion; active work cannot be counted as completed.
      - On-time completion is 0 when there are no completed jobs, rather than
        assuming a perfect rate.
      - Cancellation is measured against all jobs assigned to the vendor.
    """
    completed = [o for o in orders if o.status == "completed"]
    cancelled = [o for o in orders if o.status == "cancelled"]
    active = [o for o in orders if o.status in {"accepted", "in_progress"}]
    total = len(orders)

    if total == 0:
        return {
            "score": 0.0,
            "total_jobs": 0,
            "completed_jobs": 0,
            "cancelled_jobs": 0,
            "active_jobs": 0,
            "completion_rate": 0.0,
            "on_time_completion_rate": None,
            "average_completion_hours": None,
        }

    completion_rate = len(completed) / total

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

    # No completed work means there is no evidence of timely completion.
    # Treat it as zero for the performance score, not 100%.
    on_time_rate = (on_time / len(completed)) if completed else 0.0
    timed_on_time_rate = (on_time / timed) if timed else None
    cancellation_rate = len(cancelled) / total

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
        "on_time_completion_rate": round(timed_on_time_rate * 100, 1) if timed_on_time_rate is not None else None,
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

    vendors = Vendor.query.order_by(Vendor.name).all()
    orders_by_vendor = {}
    vendor_ids = [v.id for v in vendors]
    if vendor_ids:
        for order in WorkOrder.query.filter(WorkOrder.vendor_id.in_(vendor_ids)).all():
            orders_by_vendor.setdefault(order.vendor_id, []).append(order)

    results = []
    for vendor in vendors:
        metrics = _score_vendor(orders_by_vendor.get(vendor.id, []))
        results.append({"vendor": vendor.to_dict(), **metrics})

    results.sort(key=lambda r: r["score"], reverse=True)
    return {"vendor_performance": results}
