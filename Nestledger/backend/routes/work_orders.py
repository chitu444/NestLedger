from datetime import datetime

from flask import Blueprint, request
from sqlalchemy import select
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.auth import current_user

from models.db import db
from models.notification import notify
from models.quotation import Quotation
from models.rating import Rating
from models.user import User
from models.vendor import Vendor
from models.work_order import WorkOrder
from utils.validators import required_text, valid_amount, REQUEST_CATEGORY_TO_JOB
from utils.audit import record
from utils.pagination import paginate_query


workorders_bp = Blueprint("workorders", __name__)
VALID_STATUSES = {"open", "accepted", "in_progress", "completed", "cancelled"}
VALID_TRANSITIONS = {
    "open": {"accepted", "cancelled"},
    "accepted": {"in_progress", "open"},
    "in_progress": {"completed", "open"},
    "completed": set(),
    "cancelled": set(),
}


def can_transition(current, target):
    return target in VALID_TRANSITIONS.get(current, set())


def category_job(category: str):
    return REQUEST_CATEGORY_TO_JOB.get((category or "").strip().lower())


def canonical_category(category: str):
    value = (category or "").strip().lower()
    for label, job in REQUEST_CATEGORY_TO_JOB.items():
        if label == value:
            return label.title()
    return (category or "").strip()


def vendor_matches_order(vendor: Vendor, order: WorkOrder) -> bool:
    required_job = category_job(order.category)
    return required_job is not None and (vendor.service or "").strip().lower() == required_job



@workorders_bp.get("/work-orders")
@jwt_required()
def list_orders():
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    if user.role == "resident":
        query = WorkOrder.query.filter_by(resident_id=user.id)
    elif user.role == "vendor":
        profile = Vendor.query.filter_by(user_id=user.id, status="active").first()
        if profile is None:
            return {"work_orders": []}
        required_job = (profile.service or "").strip().lower()
        # Vendors see only open requests for their own job title, plus jobs
        # already assigned to them regardless of their current status.
        matching_categories = [
            category for category, job in REQUEST_CATEGORY_TO_JOB.items()
            if job == required_job
        ]
        matching_labels = [c.title() for c in matching_categories]
        query = WorkOrder.query.filter(
            db.or_(
                db.and_(WorkOrder.status == "open", db.func.lower(WorkOrder.category).in_([x.lower() for x in matching_labels])),
                WorkOrder.vendor_id == profile.id,
            )
        )
    else:
        query = WorkOrder.query

    status = (request.args.get("status") or "").strip().lower()
    search = (request.args.get("q") or "").strip()
    if status in VALID_STATUSES:
        query = query.filter(WorkOrder.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(WorkOrder.title.ilike(like), WorkOrder.category.ilike(like), WorkOrder.apartment.ilike(like)))
    orders, meta = paginate_query(query.order_by(WorkOrder.id.desc()), default=20)
    WorkOrder.prime_summary([order.id for order in orders])
    order_dicts = [order.to_dict() for order in orders]

    if user.role == "vendor":
        profile = Vendor.query.filter_by(user_id=user.id, status="active").first()
        if profile is not None and orders:
            pending_quotes = {
                q.work_order_id: q
                for q in Quotation.query.filter(
                    Quotation.vendor_id == profile.id,
                    Quotation.work_order_id.in_([o.id for o in orders]),
                    Quotation.status == "pending",
                ).all()
            }
            for order, order_dict in zip(orders, order_dicts):
                quote = pending_quotes.get(order.id)
                order_dict["my_quote"] = quote.to_dict() if quote else None

    return {"work_orders": order_dicts, "meta": meta}


@workorders_bp.post("/work-orders")
@jwt_required()
def create_order():
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404
    if user.role not in {"resident", "admin"}:
        return {"error": "Only residents or admins can post work orders"}, 403

    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()

    ok, err = required_text(title, "Title", max_len=200)
    if not ok:
        return {"error": err}, 400

    category = str(data.get("category") or "").strip()
    if category_job(category) is None:
        return {"error": "Category must be one of: Plumbing, Electrical, Carpentry, Painting, Cleaning"}, 400

    ok, err = valid_amount(data.get("amount") or 0)
    if not ok:
        return {"error": err}, 400
    amount = float(data.get("amount") or 0)

    order = WorkOrder(
        title=title,
        category=canonical_category(category)[:80],
        description=str(data.get("description") or "").strip() or None,
        amount=amount,
        due_date=str(data.get("due_date") or "").strip() or None,
    )

    if user.role == "resident":
        order.resident_id = user.id
        order.apartment = user.apartment
        order.status = "open"
    else:
        resident_id = data.get("resident_id")
        vendor_id = data.get("vendor_id")

        if resident_id:
            resident = db.session.get(User, int(resident_id))
            if resident is None or resident.role != "resident":
                return {"error": "Invalid resident"}, 400
            order.resident_id = resident.id
            order.apartment = resident.apartment

        if vendor_id:
            vendor = db.session.get(Vendor, int(vendor_id))
            if vendor is None:
                return {"error": "Invalid vendor"}, 400
            if vendor.status != "active":
                return {"error": "Selected vendor is inactive"}, 409
            if not vendor_matches_order(vendor, order):
                return {"error": "Selected vendor job title does not match this request category"}, 400
            order.vendor_id = vendor.id
            order.status = "accepted"
            order.accepted_at = datetime.utcnow()
        else:
            order.status = "open"

    db.session.add(order)
    db.session.commit()

    if order.status == "open":
        required_job = category_job(order.category)
        vendor_user_ids = [
            v.user_id for v in Vendor.query.filter_by(status="active").all()
            if v.user_id and (v.service or "").strip().lower() == required_job
        ]
        from models.notification import notify_many

        notify_many(
            vendor_user_ids,
            "New Job Available",
            f"A new {required_job.title()} job \"{order.title}\" is available on the job board.",
            notif_type="work_order",
        )

    return {"work_order": order.to_dict()}, 201


@workorders_bp.patch("/work-orders/<int:wid>/accept")
@jwt_required()
def accept_order(wid):
    user = current_user()
    if user is None or user.role != "vendor":
        return {"error": "Only vendors can accept work orders"}, 403

    profile = Vendor.query.filter_by(user_id=user.id, status="active").first()
    if profile is None:
        return {"error": "No vendor profile found for this account"}, 400

    order = db.session.execute(
        select(WorkOrder).where(WorkOrder.id == wid).with_for_update()
    ).scalar_one_or_none()
    if order is None:
        return {"error": "Work order not found"}, 404
    if order.status != "open" or order.vendor_id is not None:
        return {"error": "This work order is no longer available"}, 409
    if not vendor_matches_order(profile, order):
        return {"error": "This request is for a different vendor job title"}, 403

    order.vendor_id = profile.id
    order.status = "accepted"
    order.accepted_at = datetime.utcnow()
    db.session.commit()

    notify(
        order.resident_id,
        "Vendor Accepted",
        f"Your maintenance request \"{order.title}\" has been accepted by {profile.name}.",
        notif_type="work_order",
    )

    return {"work_order": order.to_dict()}


@workorders_bp.patch("/work-orders/<int:wid>/withdraw")
@jwt_required()
def withdraw_order(wid):
    """A vendor withdraws from a job they previously accepted.

    Business rule: withdrawal is only allowed before work is completed
    (accepted or in_progress). The job returns to the open board so
    another vendor can pick it up; it is not marked cancelled, since the
    resident's request is still valid and unfulfilled.
    """
    user = current_user()
    if user is None or user.role != "vendor":
        return {"error": "Only vendors can withdraw from a job"}, 403

    profile = Vendor.query.filter_by(user_id=user.id, status="active").first()
    if profile is None:
        return {"error": "No vendor profile found for this account"}, 400

    order = db.session.get(WorkOrder, wid)
    if order is None:
        return {"error": "Work order not found"}, 404
    if order.vendor_id != profile.id:
        return {"error": "You can only withdraw from jobs assigned to you"}, 403
    if order.status != "accepted":
        return {"error": "A job can only be withdrawn before work starts. Contact an administrator if work is already in progress."}, 400

    order.vendor_id = None
    order.status = "open"
    order.accepted_at = None
    db.session.commit()

    # Re-open only to vendors with the matching job title.
    from models.notification import notify_many
    required_job = category_job(order.category)
    notify_many(
        [v.user_id for v in Vendor.query.filter_by(status="active").all()
         if v.user_id and (v.service or "").strip().lower() == required_job],
        "Job Available Again",
        f"A {required_job.title()} job \"{order.title}\" is available again.",
        notif_type="work_order",
    )

    notify(
        order.resident_id,
        "Vendor Withdrew",
        f"The vendor withdrew from \"{order.title}\". It is open for other vendors again.",
        notif_type="work_order",
    )

    return {"work_order": order.to_dict()}


@workorders_bp.patch("/work-orders/<int:wid>/status")
@jwt_required()
def update_status(wid):
    user = current_user()
    order = db.session.get(WorkOrder, wid)

    if order is None:
        return {"error": "Work order not found"}, 404

    new_status = (request.get_json(silent=True) or {}).get("status")
    if new_status not in VALID_STATUSES:
        return {"error": "Invalid work order status"}, 400

    if not can_transition(order.status, new_status):
        return {"error": f"Cannot move a {order.status.replace('_', ' ')} work order to {new_status.replace('_', ' ')}"}, 409

    if user.role == "vendor":
        profile = Vendor.query.filter_by(user_id=user.id, status="active").first()
        if profile is None or order.vendor_id != profile.id:
            return {"error": "You can only update work orders assigned to you"}, 403
        if new_status not in {"in_progress", "completed"}:
            return {"error": "Vendors can only mark a job in progress or completed"}, 400
        if new_status == "in_progress" and order.status != "accepted":
            return {"error": "Only accepted jobs can be started"}, 400
        if new_status == "completed" and order.status != "in_progress":
            return {"error": "Only in-progress jobs can be completed"}, 400

    elif user.role == "resident":
        if order.resident_id != user.id:
            return {"error": "You can only manage your own requests"}, 403
        if new_status != "cancelled" or order.status != "open":
            return {"error": "Requests can only be cancelled while still open"}, 400

    elif user.role != "admin":
        return {"error": "Not authorized"}, 403

    old_status = order.status
    order.status = new_status
    if new_status == "completed":
        order.completed_at = datetime.utcnow()

    record(user.id, "work_order.status_changed", "work_order", order.id,
           f"{old_status} → {new_status}", commit=False)
    db.session.commit()

    if new_status == "completed":
        notify(
            order.resident_id,
            "Work Completed",
            f"Your maintenance request \"{order.title}\" has been completed.",
            notif_type="work_order",
        )
    elif new_status == "in_progress":
        notify(
            order.resident_id,
            "Work In Progress",
            f"Work has started on your request \"{order.title}\".",
            notif_type="work_order",
        )

    return {"work_order": order.to_dict()}


# ---------------------------------------------------------------------------
# Vendor quotations
# ---------------------------------------------------------------------------

@workorders_bp.post("/work-orders/<int:wid>/quotes")
@jwt_required()
def submit_quote(wid):
    """Vendor submits or updates a quote on an open work order.

    Submitting again while a pending quote already exists updates that
    quote in place instead of creating a second one -- a vendor only ever
    has one active (pending) quote per work order.
    """
    user = current_user()
    if user is None or user.role != "vendor":
        return {"error": "Only vendors can submit quotes"}, 403

    profile = Vendor.query.filter_by(user_id=user.id, status="active").first()
    if profile is None:
        return {"error": "No active vendor profile found for this account"}, 400

    order = db.session.get(WorkOrder, wid)
    if order is None:
        return {"error": "Work order not found"}, 404
    if order.status != "open" or order.vendor_id is not None:
        return {"error": "This work order is not open for quotes"}, 409
    if not vendor_matches_order(profile, order):
        return {"error": "This request is for a different vendor job title"}, 403

    data = request.get_json(silent=True) or {}
    ok, err = valid_amount(data.get("amount"), allow_zero=False)
    if not ok:
        return {"error": err}, 400
    amount = float(data.get("amount"))
    note = str(data.get("note") or "").strip()[:1000] or None

    existing = Quotation.query.filter_by(
        work_order_id=order.id, vendor_id=profile.id, status="pending"
    ).first()

    if existing:
        existing.amount = amount
        existing.note = note
        existing.updated_at = datetime.utcnow()
        quote = existing
        created = False
    else:
        quote = Quotation(
            work_order_id=order.id,
            vendor_id=profile.id,
            amount=amount,
            note=note,
            status="pending",
        )
        db.session.add(quote)
        created = True

    db.session.commit()

    if created and order.resident_id:
        notify(
            order.resident_id,
            "New Quote Received",
            f"{profile.name} quoted \u20b9{amount:,.0f} for \"{order.title}\".",
            notif_type="work_order",
        )

    return {"quote": quote.to_dict()}, 201 if created else 200


@workorders_bp.get("/work-orders/<int:wid>/quotes")
@jwt_required()
def list_quotes(wid):
    """Residents (order owner) and admins can view all quotes on an order.

    Vendors have their own dedicated history endpoint (GET /vendors/me/quotes)
    so this stays a resident/admin-only view and never leaks competing
    vendors' quotes to each other.
    """
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    order = db.session.get(WorkOrder, wid)
    if order is None:
        return {"error": "Work order not found"}, 404

    if user.role == "resident":
        if order.resident_id != user.id:
            return {"error": "You can only view quotes for your own requests"}, 403
    elif user.role != "admin":
        return {"error": "Not authorized"}, 403

    quotes = (
        Quotation.query.filter_by(work_order_id=order.id)
        .order_by(Quotation.amount.asc())
        .all()
    )
    return {"quotes": [q.to_dict() for q in quotes]}


@workorders_bp.patch("/work-orders/<int:wid>/quotes/<int:qid>/accept")
@jwt_required()
def accept_quote(wid, qid):
    """Resident/admin accepts one quote.

    This is the segregation-critical path: accepting assigns the vendor,
    moves the order out of "open", and flips every other pending quote on
    this same order to "rejected" so the losing vendors' boards clear
    immediately (they're notified too).
    """
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    order = db.session.execute(
        select(WorkOrder).where(WorkOrder.id == wid).with_for_update()
    ).scalar_one_or_none()
    if order is None:
        return {"error": "Work order not found"}, 404

    if user.role == "resident" and order.resident_id != user.id:
        return {"error": "You can only manage quotes on your own requests"}, 403
    if user.role not in {"resident", "admin"}:
        return {"error": "Not authorized"}, 403
    if order.status != "open" or order.vendor_id is not None:
        return {"error": "This work order is no longer open"}, 409

    quote = db.session.get(Quotation, qid, with_for_update=True)
    if quote is None or quote.work_order_id != order.id:
        return {"error": "Quote not found"}, 404
    if quote.status != "pending":
        return {"error": "This quote is no longer pending"}, 409

    vendor = db.session.get(Vendor, quote.vendor_id)
    if vendor is None or vendor.status != "active":
        return {"error": "Vendor is no longer active"}, 409

    quote.status = "accepted"
    order.vendor_id = vendor.id
    order.amount = quote.amount
    order.status = "accepted"
    order.accepted_at = datetime.utcnow()

    other_quotes = Quotation.query.filter(
        Quotation.work_order_id == order.id,
        Quotation.id != quote.id,
        Quotation.status == "pending",
    ).all()
    rejected_vendor_ids = []
    for other in other_quotes:
        other.status = "rejected"
        rejected_vendor_ids.append(other.vendor_id)

    db.session.commit()

    if vendor.user_id:
        notify(
            vendor.user_id,
            "Quote Accepted",
            f"Your quote of \u20b9{quote.amount:,.0f} for \"{order.title}\" was accepted.",
            notif_type="work_order",
        )
    for vid in rejected_vendor_ids:
        other_vendor = db.session.get(Vendor, vid)
        if other_vendor and other_vendor.user_id:
            notify(
                other_vendor.user_id,
                "Quote Not Selected",
                f"Your quote for \"{order.title}\" was not selected -- the resident chose another vendor.",
                notif_type="work_order",
            )

    return {"work_order": order.to_dict(), "quote": quote.to_dict()}


@workorders_bp.patch("/work-orders/<int:wid>/quotes/<int:qid>/reject")
@jwt_required()
def reject_quote(wid, qid):
    """Resident/admin declines a single quote without accepting another."""
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    order = db.session.get(WorkOrder, wid)
    if order is None:
        return {"error": "Work order not found"}, 404

    if user.role == "resident" and order.resident_id != user.id:
        return {"error": "You can only manage quotes on your own requests"}, 403
    if user.role not in {"resident", "admin"}:
        return {"error": "Not authorized"}, 403

    quote = db.session.get(Quotation, qid)
    if quote is None or quote.work_order_id != order.id:
        return {"error": "Quote not found"}, 404
    if quote.status != "pending":
        return {"error": "This quote is no longer pending"}, 409

    quote.status = "rejected"
    db.session.commit()

    vendor = db.session.get(Vendor, quote.vendor_id)
    if vendor and vendor.user_id:
        notify(
            vendor.user_id,
            "Quote Declined",
            f"Your quote for \"{order.title}\" was declined.",
            notif_type="work_order",
        )

    return {"quote": quote.to_dict()}


@workorders_bp.patch("/work-orders/<int:wid>/quotes/<int:qid>/withdraw")
@jwt_required()
def withdraw_quote(wid, qid):
    """A vendor withdraws their own pending quote."""
    user = current_user()
    if user is None or user.role != "vendor":
        return {"error": "Only vendors can withdraw their own quotes"}, 403

    profile = Vendor.query.filter_by(user_id=user.id, status="active").first()
    if profile is None:
        return {"error": "No vendor profile found for this account"}, 400

    quote = db.session.get(Quotation, qid)
    if quote is None or quote.work_order_id != wid:
        return {"error": "Quote not found"}, 404
    if quote.vendor_id != profile.id:
        return {"error": "You can only withdraw your own quotes"}, 403
    if quote.status != "pending":
        return {"error": "Only pending quotes can be withdrawn"}, 400

    quote.status = "withdrawn"
    db.session.commit()
    return {"quote": quote.to_dict()}


# ---------------------------------------------------------------------------
# Vendor ratings
# ---------------------------------------------------------------------------

@workorders_bp.post("/work-orders/<int:wid>/rating")
@jwt_required()
def rate_order(wid):
    """Resident rates the vendor + leaves remarks on a completed job.

    Exactly one rating per work order; the vendor's average rating and
    count are derived on the fly wherever a vendor is serialized
    (Vendor.to_dict), so this is the single source of truth.
    """
    user = current_user()
    if user is None or user.role != "resident":
        return {"error": "Only residents can rate a vendor"}, 403

    order = db.session.get(WorkOrder, wid)
    if order is None:
        return {"error": "Work order not found"}, 404
    if order.resident_id != user.id:
        return {"error": "You can only rate your own requests"}, 403
    if order.status != "completed":
        return {"error": "You can only rate a completed job"}, 400
    if order.vendor_id is None:
        return {"error": "This job has no vendor to rate"}, 400
    if Rating.query.filter_by(work_order_id=order.id).first() is not None:
        return {"error": "This job has already been rated"}, 409

    data = request.get_json(silent=True) or {}
    try:
        stars = int(data.get("stars"))
    except (TypeError, ValueError):
        return {"error": "Stars must be a whole number from 1 to 5"}, 400
    if stars < 1 or stars > 5:
        return {"error": "Stars must be between 1 and 5"}, 400
    remarks = str(data.get("remarks") or "").strip()[:1000] or None

    rating = Rating(
        work_order_id=order.id,
        vendor_id=order.vendor_id,
        resident_id=user.id,
        stars=stars,
        remarks=remarks,
    )
    db.session.add(rating)
    db.session.commit()

    vendor = db.session.get(Vendor, order.vendor_id)
    if vendor and vendor.user_id:
        notify(
            vendor.user_id,
            "New Rating Received",
            f"{user.name} rated your work on \"{order.title}\" {stars}/5.",
            notif_type="rating",
        )

    return {"rating": rating.to_dict()}, 201
