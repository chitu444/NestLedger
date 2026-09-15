from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.auth import current_user

from models.db import db
from models.notification import Notification
from models.user import User
from utils.pagination import paginate_query


notifications_bp = Blueprint("notifications", __name__)



@notifications_bp.get("/notifications")
@jwt_required()
def list_notifications():
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    query = Notification.query.filter_by(user_id=user.id)
    items, meta = paginate_query(query.order_by(Notification.id.desc()), default=30, maximum=50)
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return {"notifications": [n.to_dict() for n in items], "unread_count": unread, "meta": meta}


@notifications_bp.patch("/notifications/<int:nid>/read")
@jwt_required()
def mark_read(nid):
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    notif = db.session.get(Notification, nid)
    if notif is None or notif.user_id != user.id:
        return {"error": "Notification not found"}, 404

    notif.is_read = True
    db.session.commit()
    return {"notification": notif.to_dict()}


@notifications_bp.patch("/notifications/read-all")
@jwt_required()
def mark_all_read():
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return {"message": "All notifications marked as read"}
