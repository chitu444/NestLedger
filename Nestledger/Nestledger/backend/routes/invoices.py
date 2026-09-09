from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.auth import current_user

from models.db import db
from models.invoice import Invoice
from models.user import User
from models.vendor import Vendor
from utils.pagination import paginate_query


invoices_bp = Blueprint("invoices", __name__)


@invoices_bp.get("/invoices")
@jwt_required()
def invoices():
    user = current_user()
    if user is None:
        return {"error": "User not found"}, 404

    if user.role == "admin":
        query = Invoice.query
    elif user.role == "vendor":
        vendor = Vendor.query.filter_by(user_id=user.id).first()
        if vendor is None:
            return {"invoices": []}
        query = Invoice.query.filter_by(vendor_id=vendor.id)
    else:
        return {"error": "Admin or vendor access required"}, 403

    status = (request.args.get("status") or "").strip().lower()
    if status:
        query = query.filter(Invoice.status == status)
    rows, meta = paginate_query(query.order_by(Invoice.id.desc()), default=20)
    return {"invoices": [i.to_dict() for i in rows], "meta": meta}
