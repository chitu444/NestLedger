"""Atomic apartment ownership helpers.

PostgreSQL uses a dedicated inventory row as the concurrency boundary. The
legacy resident partial unique index remains as a second line of defence.
"""
from sqlalchemy import text

from models.apartment_slot import ApartmentSlot
from models.db import db
from utils.concurrency import lock_fingerprint
from utils.validators import valid_apartment


def claim_apartment(code: str, user_id: int):
    code = str(code or "").strip().upper()
    ok, err = valid_apartment(code, required=True)
    if not ok:
        return False, err
    lock_fingerprint(f"apartment-claim:{code}")
    slot = db.session.execute(
        db.select(ApartmentSlot).where(ApartmentSlot.code == code).with_for_update()
    ).scalar_one_or_none()
    if slot is None:
        return False, "Apartment inventory is not initialized. Run the production migration before registering residents."
    if slot.claimed_by_user_id not in (None, user_id):
        return False, f"Apartment {code} is already occupied"
    slot.claimed_by_user_id = user_id
    return True, None


def release_apartment(code: str, user_id: int):
    code = str(code or "").strip().upper()
    if not code:
        return
    lock_fingerprint(f"apartment-claim:{code}")
    slot = db.session.execute(
        db.select(ApartmentSlot).where(ApartmentSlot.code == code).with_for_update()
    ).scalar_one_or_none()
    if slot is not None and slot.claimed_by_user_id == user_id:
        slot.claimed_by_user_id = None


def apartment_status():
    rows = db.session.execute(
        db.select(ApartmentSlot.code, ApartmentSlot.claimed_by_user_id).order_by(ApartmentSlot.code)
    ).all()
    return rows
