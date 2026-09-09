from flask import Blueprint
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import func

from models.complaint import Complaint
from models.db import db
from models.expense import Expense
from models.payment import Payment
from models.user import User


reports_bp = Blueprint("reports", __name__)


@reports_bp.get("/reports")
@jwt_required()
def reports():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None or user.role != "admin":
        return {"error": "Admin access required"}, 403

    collection = float(
        db.session.query(func.sum(Payment.amount))
        .filter(Payment.status == "paid")
        .scalar()
        or 0
    )
    expenses = float(db.session.query(func.sum(Expense.amount)).scalar() or 0)

    return {
        "collection": collection,
        "expenses": expenses,
        "open_complaints": Complaint.query.filter(
            Complaint.status != "closed"
        ).count(),
    }
