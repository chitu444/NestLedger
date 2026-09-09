"""Small query services for operational dashboard aggregates."""
from sqlalchemy import func
from models.db import db
from models.complaint import Complaint
from models.work_order import WorkOrder


def complaint_counts():
    return {status: int(count) for status, count in db.session.query(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status).all()}


def open_work_orders_count():
    return WorkOrder.query.filter_by(status='open').count()
