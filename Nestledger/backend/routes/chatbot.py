import json
import os
import urllib.error
import urllib.request

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.auth import current_user
from sqlalchemy import func

from models.complaint import Complaint
from models.db import db
from models.expense import Expense
from models.payment import MaintenanceBill, Payment
from models.user import User
from models.vendor import Vendor
from models.work_order import WorkOrder
from models.notice import Notice

chatbot_bp = Blueprint("chatbot", __name__)

LANGUAGES = {
    "en": "English",
    "ta": "Tamil",
    "ml": "Malayalam",
    "kn": "Kannada",
    "te": "Telugu",
    "hi": "Hindi",
}
ALLOWED_ACTIONS = {
    "dashboard", "payments", "complaints", "notices", "workorders", "receipts",
    "profile", "residents", "vendors", "expenses", "vendorperformance", "logout"
}
MAX_MESSAGE_LENGTH = 1000
MAX_HISTORY_ITEMS = 8
DEFAULT_MODEL = "gemini-2.5-flash"


def _current_user():
    try:
        return current_user()
    except (TypeError, ValueError):
        return None


def _money(value):
    return f"₹{float(value or 0):,.0f}"


def _authorized_context(user):
    """Build only data the authenticated user is allowed to see."""
    lines = [
        f"User role: {user.role}",
        f"User name: {user.name}",
        f"Apartment: {user.apartment or 'N/A'}",
    ]

    if user.role == "resident":
        pending = MaintenanceBill.query.filter_by(user_id=user.id).filter(MaintenanceBill.status != "paid").order_by(MaintenanceBill.id.desc()).limit(5).all()
        pending_count = MaintenanceBill.query.filter_by(user_id=user.id).filter(MaintenanceBill.status != "paid").count()
        paid_count = MaintenanceBill.query.filter_by(user_id=user.id, status="paid").count()
        due_total = float(db.session.query(func.coalesce(func.sum(MaintenanceBill.amount), 0)).filter(MaintenanceBill.user_id == user.id, MaintenanceBill.status != "paid").scalar() or 0)
        complaints = Complaint.query.filter_by(user_id=user.id).order_by(Complaint.id.desc()).limit(5).all()
        complaint_count = Complaint.query.filter_by(user_id=user.id).count()
        work_orders = WorkOrder.query.filter_by(resident_id=user.id).order_by(WorkOrder.id.desc()).limit(5).all()
        work_order_count = WorkOrder.query.filter_by(resident_id=user.id).count()

        lines += [
            "Resident financial details:",
            f"Total outstanding maintenance dues: {_money(due_total)}",
            f"Pending bills: {pending_count}",
            f"Paid bills: {paid_count}",
        ]
        for bill in pending:
            lines.append(f"Pending bill: {bill.month}; amount {_money(bill.amount)}; due {bill.due_date}; status {bill.status}")
        lines.append(f"Paid payments count: {Payment.query.filter_by(user_id=user.id, status='paid').count()}")
        lines.append(f"Resident complaints count: {complaint_count}")
        for item in complaints:
            lines.append(f"Complaint #{item.id}: {item.subject}; category {item.category}; status {item.status}")
        lines.append(f"Resident work orders count: {work_order_count}")
        for item in work_orders:
            lines.append(f"Work order #{item.id}: {item.title}; status {item.status}; amount {_money(item.amount)}")

    elif user.role == "vendor":
        profile = Vendor.query.filter_by(user_id=user.id, status="active").first()
        assigned = WorkOrder.query.filter_by(vendor_id=profile.id).order_by(WorkOrder.id.desc()).limit(5).all() if profile else []
        assigned_count = WorkOrder.query.filter_by(vendor_id=profile.id).count() if profile else 0
        active_count = WorkOrder.query.filter(WorkOrder.vendor_id == profile.id, WorkOrder.status.in_(("accepted", "in_progress"))).count() if profile else 0
        allowed_categories = []
        if profile:
            from utils.validators import REQUEST_CATEGORY_TO_JOB
            service=(profile.service or '').strip().lower()
            allowed_categories=[c.title() for c,j in REQUEST_CATEGORY_TO_JOB.items() if j==service]
        open_jobs = WorkOrder.query.filter(WorkOrder.status == "open", WorkOrder.category.in_(allowed_categories)).order_by(WorkOrder.id.desc()).limit(5).all() if allowed_categories else []
        lines += [
            "Vendor profile:",
            f"Service: {profile.service if profile else 'General Services'}",
            f"Assigned jobs: {assigned_count}",
            f"Active assigned jobs: {active_count}",
        ]
        for item in assigned:
            lines.append(f"Assigned work order #{item.id}: {item.title}; status {item.status}; amount {_money(item.amount)}")
        lines.append(f"Open jobs visible on board: {len(open_jobs)}")

    else:
        total_billed = float(db.session.query(func.coalesce(func.sum(MaintenanceBill.amount), 0)).scalar() or 0)
        total_collected = float(db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.status == "paid").scalar() or 0)
        total_expenses = float(db.session.query(func.coalesce(func.sum(Expense.amount), 0)).scalar() or 0)
        lines += [
            "Admin society overview:",
            f"Total billed: {_money(total_billed)}",
            f"Total collected: {_money(total_collected)}",
            f"Total outstanding: {_money(max(total_billed - total_collected, 0))}",
            f"Total expenses: {_money(total_expenses)}",
            f"Residents: {User.query.filter_by(role='resident').count()}",
            f"Vendors: {User.query.filter_by(role='vendor').count()}",
            f"Open complaints: {Complaint.query.filter(Complaint.status != 'closed').count()}",
            f"Open work orders: {WorkOrder.query.filter_by(status='open').count()}",
        ]

    notices = Notice.query.order_by(Notice.id.desc()).limit(5).all()
    lines.append("Latest community notices:")
    for notice in notices:
        lines.append(f"Notice #{notice.id}: {notice.title}; tag {notice.tag}; {notice.body[:300]}")

    vendors = Vendor.query.filter_by(status="active").order_by(Vendor.id.desc()).limit(5).all()
    lines.append("Active vendor directory:")
    for vendor in vendors:
        lines.append(f"Vendor: {vendor.name}; service {vendor.service}; contact {vendor.contact}")

    return "\n".join(lines)


def _local_fallback(user, message, lang):
    """Useful deterministic response when Gemini is unavailable; never fabricates data."""
    lower = message.lower()
    pending = MaintenanceBill.query.filter_by(user_id=user.id).filter(MaintenanceBill.status != "paid").all() if user.role == "resident" else []
    due = sum(b.amount for b in pending)
    action = None

    if any(x in lower for x in ("due", "dues", "owe", "payment", "pay", "bill", "maintenance", "நிலுவை", "கட்டணம்", "குடിശ്ശിക", "பಾವತಿ", "బకాయి", "भुगतान")):
        action = {"type": "navigate", "target": "payments", "label": "Open Payments"}
        replies = {
            "ta": f"உங்கள் தற்போதைய பராமரிப்பு நிலுவைத் தொகை {_money(due)}.",
            "ml": f"നിങ്ങളുടെ നിലവിലെ മെയിന്റനൻസ് കുടിശ്ശിക {_money(due)} ആണ്.",
            "kn": f"ನಿಮ್ಮ ಪ್ರಸ್ತುತ ನಿರ್ವಹಣಾ ಬಾಕಿ {_money(due)} ಆಗಿದೆ.",
            "te": f"మీ ప్రస్తుత నిర్వహణ బకాయి {_money(due)}.",
            "hi": f"आपका वर्तमान मेंटेनेंस बकाया {_money(due)} है।",
        }
        return {"reply": replies.get(lang, f"Your current maintenance dues are {_money(due)}."), "action": action, "fallback": True}

    if "complaint" in lower or "issue" in lower or "புகார்" in lower or "शिकायत" in lower:
        action = {"type": "navigate", "target": "complaints", "label": "Open Complaints"}
        return {"reply": "You can view your complaints and their current status on the Complaints page.", "action": action, "fallback": True}
    if "notice" in lower or "announcement" in lower or "அறிவிப்பு" in lower or "सूचना" in lower:
        action = {"type": "navigate", "target": "notices", "label": "Open Notices"}
        return {"reply": "You can view the latest community notices on the Notices page.", "action": action, "fallback": True}
    if "work order" in lower or "maintenance request" in lower or "repair" in lower:
        action = {"type": "navigate", "target": "workorders", "label": "Open Work Orders"}
        return {"reply": "You can view maintenance requests and work orders on the Work Orders page.", "action": action, "fallback": True}

    return {"reply": f"Hello {user.name}! I can help with dues, payments, complaints, notices, and maintenance requests.", "action": None, "fallback": True}


def _gemini(message, lang, history, context):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("GEMINI_CHAT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    lang_name = LANGUAGES.get(lang, "English")
    history_text = ""
    for item in history[-MAX_HISTORY_ITEMS:]:
        role = "User" if item.get("role") == "user" else "Assistant"
        parts = item.get("parts") or []
        text = str(parts[0].get("text", ""))[:1000] if parts and isinstance(parts[0], dict) else ""
        if text:
            history_text += f"{role}: {text}\n"

    system = f"""You are the NestLedger Community AI Assistant for an apartment community.
Answer in {lang_name}. Be concise, friendly, and factual.

SECURITY RULES:
- Use only the authorized context supplied below.
- Never reveal passwords, API keys, secrets, hashes, database internals, or private information about another resident.
- Never invent amounts, statuses, names, apartments, dates, or records.
- Do not expose raw database details.
- Navigation targets are limited to: dashboard, payments, complaints, notices, workorders, receipts, profile, residents, vendors, expenses, vendorperformance, logout.
- Use an action only when it genuinely helps the user navigate. Otherwise action must be null.
- If the user asks to perform a data-changing action, explain the appropriate page rather than pretending it was completed.

Return ONLY JSON with this shape:
{{"reply":"...","action":{{"type":"navigate","target":"payments","label":"Open Payments"}}}}
The action value may also be null.

AUTHORIZED USER CONTEXT:
{context}
"""

    prompt = f"{system}\n\nRECENT CONVERSATION:\n{history_text}\nCURRENT USER MESSAGE:\n{message}"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "reply": {"type": "STRING"},
                    "action": {
                        "anyOf": [
                            {
                                "type": "OBJECT",
                                "properties": {
                                    "type": {"type": "STRING"},
                                    "target": {"type": "STRING"},
                                    "label": {"type": "STRING"},
                                },
                                "required": ["type", "target", "label"],
                            },
                            {"type": "NULL"},
                        ]
                    },
                },
                "required": ["reply", "action"],
            },
        },
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
        reply = str(result.get("reply", "")).strip()
        action = result.get("action")
        if not reply:
            return None
        if action is not None:
            if not isinstance(action, dict) or action.get("type") != "navigate" or action.get("target") not in ALLOWED_ACTIONS:
                action = None
            else:
                action = {
                    "type": "navigate",
                    "target": action["target"],
                    "label": str(action.get("label") or "Open"),
                }
        return {"reply": reply, "action": action, "fallback": False}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        app_logger = __import__("logging").getLogger(__name__)
        app_logger.warning("Gemini chatbot request failed: %s", exc)
        return None


@chatbot_bp.post("/ai/chat")
@jwt_required()
def chat():
    user = _current_user()
    if user is None:
        return {"error": "User not found"}, 404

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    lang = str(data.get("lang", "en")).strip().lower()
    history = data.get("history") if isinstance(data.get("history"), list) else []

    if not message:
        return {"error": "Message is required"}, 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return {"error": "Message is too long"}, 400
    if lang not in LANGUAGES:
        lang = "en"

    context = _authorized_context(user)
    result = _gemini(message, lang, history, context)
    if result is None:
        result = _local_fallback(user, message, lang)
    return result
