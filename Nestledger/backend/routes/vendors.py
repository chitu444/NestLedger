from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required

from models.db import db
from models.quotation import Quotation
from models.user import User
from models.vendor import Vendor


vendors_bp = Blueprint("vendors", __name__)


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


@vendors_bp.get("/vendors/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        return {"error": "User not found"}, 404
    return {"user": user.to_dict()}


@vendors_bp.get("/vendors/me/quotes")
@jwt_required()
def my_quotes():
    """A vendor's full quote history across every work order, regardless of
    status. Kept separate from GET /work-orders so a vendor's lost bids
    (won by another vendor) never clutter their Open/Accepted/In-Progress/
    Completed job board -- that's the segregation fix in practice.
    """
    user = current_user()
    if user is None or user.role != "vendor":
        return {"error": "Only vendors can view their quote history"}, 403

    profile = Vendor.query.filter_by(user_id=user.id).first()
    if profile is None:
        return {"quotes": []}

    quotes = (
        Quotation.query.filter_by(vendor_id=profile.id)
        .order_by(Quotation.id.desc())
        .all()
    )

    result = []
    for quote in quotes:
        item = quote.to_dict()
        order = quote.work_order
        item["work_order_title"] = order.title if order else None
        item["work_order_status"] = order.status if order else None
        item["work_order_category"] = order.category if order else None
        item["work_order_apartment"] = order.apartment if order else None
        result.append(item)

    return {"quotes": result}
