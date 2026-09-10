from datetime import date
from calendar import month_name

from flask import Blueprint, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError
from utils.auth import current_user

from models.db import db
from models.payment import MaintenanceBill
from models.user import User
from models.vendor import Vendor
from utils.validators import (
    PUBLIC_ROLES,
    required_text,
    valid_email,
    valid_password,
    valid_phone,
    valid_apartment,
)


auth_bp = Blueprint("auth", __name__)


def get_current_user():
    return current_user()


@auth_bp.get("/apartments")
def apartments():
    """Return the 13x7 apartment map for public registration."""
    from utils.validators import APARTMENT_CODES
    occupied = {
        str(value).strip().upper()
        for (value,) in db.session.query(User.apartment)
        .filter(User.role == "resident", User.apartment.isnot(None))
        .all()
        if str(value or "").strip().upper() in APARTMENT_CODES
    }
    return {
        "apartments": [{"code": code, "occupied": code in occupied} for code in APARTMENT_CODES]
    }

@auth_bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    phone = str(data.get("phone", "")).strip()
    role = str(data.get("role", "resident")).strip().lower()

    ok, err = required_text(name, "Name", max_len=120)
    if not ok:
        return {"error": err}, 400

    ok, err = valid_email(email)
    if not ok:
        return {"error": err}, 400

    ok, err = valid_password(password)
    if not ok:
        return {"error": err}, 400

    ok, err = valid_phone(phone)
    if not ok:
        return {"error": err}, 400

    # Admin is never publicly selectable -- reject even if sent directly via API.
    if role not in PUBLIC_ROLES:
        return {"error": "Public registration is available for Residents only"}, 400

    if User.query.filter_by(email=email).first():
        return {"error": "Email already registered"}, 409

    # Public registration uses the fixed A-1 .. Z-7 inventory.
    apartment = str(data.get("apartment", "")).strip().upper() or None
    ok, err = valid_apartment(apartment, required=True)
    if not ok:
        return {"error": err}, 400
    if User.query.filter(User.role == "resident", User.apartment == apartment).first():
        return {"error": f"Apartment {apartment} is already occupied"}, 409
    if role == "vendor":
        apartment = None

    user = User(
        name=name,
        email=email,
        role=role,
        phone=phone or None,
        apartment=apartment,
    )
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return {"error": f"Apartment {apartment} is already occupied"}, 409

    if role == "vendor":
        vendor = Vendor(
            user_id=user.id,
            name=user.name,
            service=str(data.get("service", "")).strip() or "General Services",
            contact=user.phone or "Not provided",
            status="active",
        )
        db.session.add(vendor)
    else:
        today = date.today()
        month = month_name[today.month]
        next_month = today.month % 12 + 1
        next_year = today.year + (today.month // 12)
        # Keep the demo's monthly bill behavior, but avoid hard-coded 2026 dates.
        due_day = min(5, 28)
        bill = MaintenanceBill(
            user_id=user.id,
            amount=2500,
            description=f"{month} Maintenance",
            month=f"{month} {today.year}",
            due_date=f"{due_day:02d} {month_name[next_month]} {next_year}",
        )
        db.session.add(bill)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"error": f"Apartment {apartment} is already occupied"}, 409

    if role == "resident":
        from models.notification import notify

        notify(
            user.id,
            "New Maintenance Bill",
            f"{bill.description} of ₹{bill.amount:,.0f} is due on {bill.due_date}.",
            notif_type="payment",
        )

    return {"message": "Account created successfully", "user": user.to_dict()}, 201


@auth_bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "")).strip().lower()

    ok, err = valid_email(email)
    if not ok or not password:
        return {"error": "Invalid email or password"}, 401

    user = User.query.filter_by(email=email).first()
    password_ok = False
    if user is not None:
        try:
            password_ok = user.check_password(password)
        except (TypeError, ValueError):
            password_ok = False
    if user is None or not password_ok:
        return {"error": "Invalid email or password"}, 401

    # Keep role mismatch generic so the login endpoint does not disclose which
    # roles exist for a given email address.
    if role and role not in PUBLIC_ROLES | {"vendor", "admin"}:
        return {"error": "Invalid email or password"}, 401
    if role and user.role != role:
        return {"error": "Invalid email or password"}, 401

    token = create_access_token(identity=str(user.id))
    return {"message": "Login successful", "token": token, "user": user.to_dict()}


@auth_bp.post("/auth/forgot-password")
def forgot_password():
    """Resident self-service password change using the current temporary password.

    Admin-created residents receive a one-time temporary password displayed to the
    admin at creation. The resident can use this screen to replace it without
    logging in. This project has no email delivery service configured, so a reset
    email/token is intentionally not fabricated.
    """
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    current_password = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))

    ok, err = valid_email(email)
    if not ok:
        return {"error": err}, 400
    ok, err = valid_password(new_password)
    if not ok:
        return {"error": err}, 400

    user = User.query.filter_by(email=email, role="resident").first()
    password_ok = False
    if user is not None and current_password:
        try:
            password_ok = user.check_password(current_password)
        except (TypeError, ValueError):
            password_ok = False
    if user is None or not password_ok:
        return {"error": "Invalid resident email or temporary password"}, 400

    user.set_password(new_password)
    db.session.commit()
    return {"message": "Password changed successfully. You can now sign in."}


@auth_bp.get("/auth/me")
@jwt_required()
def me():
    user = get_current_user()
    if user is None:
        return {"error": "User not found"}, 404
    return {"user": user.to_dict()}


@auth_bp.put("/auth/profile")
@jwt_required()
def profile():
    user = get_current_user()
    if user is None:
        return {"error": "User not found"}, 404

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", user.name)).strip()
    phone = str(data.get("phone", user.phone or "")).strip()

    ok, err = required_text(name, "Name", max_len=120)
    if not ok:
        return {"error": err}, 400

    ok, err = valid_phone(phone)
    if not ok:
        return {"error": err}, 400

    user.name = name
    user.phone = phone or None
    if user.role != "vendor":
        apartment = str(data.get("apartment", user.apartment or "")).strip().upper()
        ok, err = valid_apartment(apartment, required=True)
        if not ok:
            return {"error": err}, 400
        if apartment != user.apartment and User.query.filter(User.role == "resident", User.apartment == apartment, User.id != user.id).first():
            return {"error": f"Apartment {apartment} is already occupied"}, 409
        user.apartment = apartment

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"error": f"Apartment {apartment} is already occupied"}, 409
    return {"user": user.to_dict()}
