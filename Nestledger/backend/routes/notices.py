from flask import Blueprint, request
from datetime import datetime, timedelta
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_
from utils.auth import current_user

from models.db import db
from models.notice import Notice
from models.notification import notify_many
from models.user import User
from utils.validators import required_text
from utils.pagination import paginate_query


notices_bp = Blueprint("notices", __name__)



@notices_bp.get("/notices")
@jwt_required()
def list_notices():
    query = Notice.query
    search = (request.args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Notice.title.ilike(like), Notice.body.ilike(like), Notice.tag.ilike(like)))
    notices, meta = paginate_query(query.order_by(Notice.id.desc()), default=15)
    return {"notices": [notice.to_dict() for notice in notices], "meta": meta}


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

    # Guard against accidental duplicate submits/retries of the same notice.
    # The frontend also disables the submit button while the request is pending.
    recent_cutoff = datetime.utcnow() - timedelta(seconds=30)
    duplicate = (
        Notice.query
        .filter(
            Notice.created_by == user.id,
            Notice.title == title,
            Notice.body == body,
            Notice.tag == tag,
            Notice.created_at >= recent_cutoff,
        )
        .order_by(Notice.id.desc())
        .first()
    )
    if duplicate is not None:
        return {"notice": duplicate.to_dict(), "duplicate": True}, 200

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
