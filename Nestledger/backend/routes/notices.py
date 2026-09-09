from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from models.db import db
from models.notice import Notice
from models.notification import notify_many
from models.user import User
from utils.validators import required_text


notices_bp = Blueprint("notices", __name__)


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


@notices_bp.get("/notices")
@jwt_required()
def list_notices():
    notices = Notice.query.order_by(Notice.id.desc()).all()
    return {"notices": [notice.to_dict() for notice in notices]}


@notices_bp.post("/notices")
@jwt_required()
def create_notice():
    user = current_user()
    if user is None or user.role != "admin":
        return {"error": "Admin access required"}, 403

    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()
    tag = str(data.get("tag") or "COMMUNITY").strip()[:40]

    for value, label in ((title, "Title"), (body, "Body")):
        ok, err = required_text(value, label, max_len=4000 if label == "Body" else 200)
        if not ok:
            return {"error": err}, 400

    notice = Notice(title=title, body=body, tag=tag, created_by=user.id)
    db.session.add(notice)
    db.session.commit()

    other_user_ids = [u.id for u in User.query.filter(User.id != user.id).all()]
    notify_many(
        other_user_ids,
        "New Community Notice",
        f"{title}: a new community notice has been published.",
        notif_type="notice",
    )

    return {"notice": notice.to_dict()}, 201


@notices_bp.delete("/notices/<int:nid>")
@jwt_required()
def delete_notice(nid):
    user = current_user()
    if user is None or user.role != "admin":
        return {"error": "Admin access required"}, 403

    notice = db.session.get(Notice, nid)
    if notice is None:
        return {"error": "Notice not found"}, 404

    db.session.delete(notice)
    db.session.commit()
    return {"message": "Notice deleted"}
