from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from models.complaint import Complaint
from models.db import db
from models.notification import notify
from models.user import User
from utils.validators import required_text, valid_status


complaints_bp = Blueprint("complaints", __name__)

VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}
STATUS_LABELS = {
    "open": "Open",
    "in_progress": "In Progress",
    "resolved": "Resolved",
    "closed": "Closed",
}


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


@complaints_bp.get("/complaints")
@jwt_required()
def list_complaints():
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    query = (
        Complaint.query
        if user.role in {"admin", "vendor"}
        else Complaint.query.filter_by(user_id=user.id)
    )

    return {
        "complaints": [
            complaint.to_dict()
            for complaint in query.order_by(Complaint.id.desc()).all()
        ]
    }


@complaints_bp.post("/complaints")
@jwt_required()
def create_complaint():
    user = current_user()
    data = request.get_json(silent=True) or {}

    category = str(data.get("category", "")).strip()
    subject = str(data.get("subject", "")).strip()
    description = str(data.get("description", "")).strip()

    for value, label in ((category, "Category"), (subject, "Subject")):
        ok, err = required_text(value, label, max_len=200)
        if not ok:
            return {"error": err}, 400

    ok, err = required_text(description, "Description", max_len=3000)
    if not ok:
        return {"error": err}, 400

    complaint = Complaint(
        user_id=user.id,
        category=category,
        subject=subject,
        description=description,
    )
    db.session.add(complaint)
    db.session.commit()

    return {"complaint": complaint.to_dict()}, 201


@complaints_bp.patch("/complaints/<int:cid>")
@jwt_required()
def update_complaint(cid):
    user = current_user()
    complaint = db.session.get(Complaint, cid)

    if complaint is None:
        return {"error": "Complaint not found"}, 404
    if user is None or user.role not in {"admin", "vendor"}:
        return {"error": "Only admin/vendor can update complaints"}, 403

    status = (request.get_json(silent=True) or {}).get("status", complaint.status)
    ok, err = valid_status(status, VALID_STATUSES)
    if not ok:
        return {"error": err}, 400

    complaint.status = status
    complaint.updated_at = datetime.utcnow()
    db.session.commit()

    notify(
        complaint.user_id,
        "Complaint Updated",
        f"Your {complaint.category.lower()} complaint \"{complaint.subject}\" is now {STATUS_LABELS.get(status, status)}.",
        notif_type="complaint",
    )

    return {"complaint": complaint.to_dict()}
