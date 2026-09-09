from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required

from models.db import db
from models.invoice import Invoice
from models.user import User
from models.vendor import Vendor


invoices_bp = Blueprint("invoices", __name__)


@invoices_bp.get("/invoices")
@jwt_required()
def invoices():
    user = db.session.get(User, int(get_jwt_identity()))
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

    return {
        "invoices": [
            invoice.to_dict()
            for invoice in query.order_by(Invoice.id.desc()).all()
        ]
    }
