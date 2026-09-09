import hashlib
import hmac
import io
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from flask import Blueprint, current_app, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from utils.auth import current_user_id
from utils.audit import record
from utils.pagination import paginate_query

from models.db import db
from sqlalchemy.exc import IntegrityError
from models.notification import notify
from models.payment import MaintenanceBill, Payment, PaymentWebhookEvent
from models.user import User
from models.work_order import WorkOrder

payments_bp = Blueprint("payments", __name__)




def razorpay_client():
    key_id = str(current_app.config.get("RAZORPAY_KEY_ID") or "").strip()
    secret = str(current_app.config.get("RAZORPAY_KEY_SECRET") or "").strip()
    if not key_id or not secret:
        return None, ({"error": "Razorpay is not configured on the server. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in the deployment environment."}, 503)
    try:
        import razorpay
        return razorpay.Client(auth=(key_id, secret)), None
    except Exception:
        current_app.logger.exception("Unable to initialize Razorpay client")
        return None, ({"error": "Razorpay payment service is unavailable on the server."}, 503)


def _amount_paise(amount):
    try:
        value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None
    paise = int(value * 100)
    # Razorpay's INR Orders API requires at least ₹1.00 (100 paise).
    if paise < 100:
        return None
    return paise


def _provider_error(exc):
    """Return a safe, useful Razorpay error without exposing credentials."""
    description = None
    try:
        payload = getattr(exc, "error", None)
        if isinstance(payload, dict):
            description = payload.get("description") or payload.get("reason")
        if not description and getattr(exc, "args", None):
            description = str(exc.args[0])
    except Exception:
        description = None
    if description:
        return str(description)[:300]
    return "Razorpay rejected the payment order."


def create_payment_order(*, uid, amount, description, receipt, notes, bill_id=None, work_order_id=None, payment_type="maintenance"):
    client, error = razorpay_client()
    if error:
        return None, error
    amount_paise = _amount_paise(amount)
    if amount_paise is None:
        return None, ({"error": "Payment amount must be at least ₹1.00 and must be a valid number."}, 400)

    # Razorpay requires a unique receipt of at most 40 characters.
    receipt = str(receipt or "").strip()[:32] + "-" + uuid.uuid4().hex[:7]
    notes = {str(k)[:255]: str(v)[:512] for k, v in (notes or {}).items()}
    try:
        order = client.order.create({"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes})
        order_id = str(order.get("id") or "").strip()
        if not order_id:
            raise RuntimeError("Razorpay returned an invalid order response")
        payment = Payment(user_id=uid, bill_id=bill_id, work_order_id=work_order_id, payment_type=payment_type,
                          amount=amount, description=description, status="created", razorpay_order_id=order_id)
        db.session.add(payment)
        db.session.commit()
        return {"order_id": order_id, "amount": amount_paise, "currency": "INR",
                "key_id": current_app.config["RAZORPAY_KEY_ID"], "name": "NestLedger", "description": description}, None
    except IntegrityError:
        db.session.rollback()
        # A second click/request can race the first one. Let the caller recover
        # the already-created local order instead of returning a 500.
        existing = None
        if bill_id:
            existing = Payment.query.filter_by(bill_id=bill_id, user_id=uid, status="created").order_by(Payment.id.desc()).first()
        elif work_order_id:
            existing = Payment.query.filter_by(work_order_id=work_order_id, user_id=uid, status="created").order_by(Payment.id.desc()).first()
        if existing and existing.razorpay_order_id:
            return {"order_id": existing.razorpay_order_id, "amount": _amount_paise(existing.amount),
                    "currency": "INR", "key_id": current_app.config["RAZORPAY_KEY_ID"],
                    "name": "NestLedger", "description": existing.description}, None
        current_app.logger.exception("Payment record could not be saved after Razorpay order creation")
        return None, ({"error": "The payment order was created but could not be saved. Please try again."}, 503)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Razorpay order creation failed")
        return None, ({"error": _provider_error(exc)}, 502)


@payments_bp.get("/bills")
@jwt_required()
def bills():
    uid = current_user_id()
    query = MaintenanceBill.query.filter_by(user_id=uid)
    status = (request.args.get("status") or "").strip().lower()
    if status: query = query.filter(MaintenanceBill.status == status)
    rows, meta = paginate_query(query.order_by(MaintenanceBill.id.desc()), default=15)
    return {"bills": [b.to_dict() for b in rows], "meta": meta}


@payments_bp.get("/payments")
@jwt_required()
def list_payments():
    uid = current_user_id()
    query = Payment.query.filter_by(user_id=uid)
    status = (request.args.get("status") or "").strip().lower()
    payment_type = (request.args.get("type") or "").strip().lower()
    if status: query = query.filter(Payment.status == status)
    if payment_type: query = query.filter(Payment.payment_type == payment_type)
    rows, meta = paginate_query(query.order_by(Payment.id.desc()), default=15)
    return {"payments": [p.to_dict() for p in rows], "meta": meta}


@payments_bp.post("/payments/create-order")
@jwt_required()
def create_order():
    uid = current_user_id(); data = request.get_json(silent=True) or {}
    bill = MaintenanceBill.query.filter_by(id=data.get("bill_id"), user_id=uid).first()
    if bill is None: return {"error": "Bill not found"}, 404
    if bill.status == "paid": return {"error": "Bill is already paid"}, 400
    pending = Payment.query.filter_by(bill_id=bill.id, user_id=uid, status="created").order_by(Payment.id.desc()).first()
    if pending and pending.razorpay_order_id:
        _, config_error = razorpay_client()
        if config_error:
            return config_error
        return {
            "order_id": pending.razorpay_order_id,
            "amount": _amount_paise(pending.amount),
            "currency": "INR",
            "key_id": current_app.config["RAZORPAY_KEY_ID"],
            "name": "NestLedger",
            "description": pending.description,
        }
    result, error = create_payment_order(uid=uid, amount=bill.amount, description=bill.description,
        receipt=f"NL-BILL-{bill.id}", notes={"user_id": str(uid), "bill_id": str(bill.id)}, bill_id=bill.id)
    return error or result


@payments_bp.post("/payments/work-order/create-order")
@jwt_required()
def create_work_order_payment():
    uid = current_user_id(); data = request.get_json(silent=True) or {}
    order = WorkOrder.query.filter_by(id=data.get("work_order_id"), resident_id=uid).first()
    if order is None: return {"error": "Work order not found"}, 404
    if order.vendor_id is None: return {"error": "A vendor must accept the request before payment"}, 400
    if order.status not in {"accepted", "in_progress", "completed"}: return {"error": "This work order is not ready for payment"}, 400
    if not order.amount or float(order.amount) <= 0: return {"error": "This work order has no payable amount"}, 400
    existing = Payment.query.filter_by(work_order_id=order.id, status="paid").first()
    if existing:
        return {"error": "Vendor payment has already been completed"}, 400
    pending = Payment.query.filter_by(work_order_id=order.id, status="created").order_by(Payment.id.desc()).first()
    if pending and pending.razorpay_order_id:
        _, config_error = razorpay_client()
        if config_error:
            return config_error
        return {
            "order_id": pending.razorpay_order_id,
            "amount": _amount_paise(pending.amount),
            "currency": "INR",
            "key_id": current_app.config["RAZORPAY_KEY_ID"],
            "name": "NestLedger",
            "description": pending.description,
        }
    result, error = create_payment_order(uid=uid, amount=order.amount,
        description=f"Vendor payment: {order.title}", receipt=f"NL-WORK-{order.id}",
        notes={"user_id": str(uid), "work_order_id": str(order.id), "vendor_id": str(order.vendor_id)},
        work_order_id=order.id, payment_type="vendor")
    return error or result


@payments_bp.post("/payments/verify")
@jwt_required()
def verify():
    uid = current_user_id()
    data = request.get_json(silent=True) or {}
    order_id = data.get("razorpay_order_id")
    payment_id = data.get("razorpay_payment_id")
    signature = data.get("razorpay_signature")
    if not all((order_id, payment_id, signature)):
        return {"error": "Incomplete payment verification data"}, 400

    payment = Payment.query.filter_by(user_id=uid, razorpay_order_id=order_id).first()
    if payment is None:
        return {"error": "Payment order not found"}, 404
    if payment.status == "paid":
        return {"message": "Payment already verified", "payment": payment.to_dict()}

    secret = str(current_app.config.get("RAZORPAY_KEY_SECRET") or "").strip()
    if not secret:
        return {"error": "Razorpay is not configured on the server."}, 503
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(signature)):
        return {"error": "Payment verification failed"}, 400

    # Verify the payment belongs to this order and matches the expected amount
    # before changing local state. Signature verification alone proves integrity
    # of the checkout response but does not replace server-side reconciliation.
    try:
        client, error = razorpay_client()
        if error:
            return error
        remote_payment = client.payment.fetch(payment_id)
        if str(remote_payment.get("order_id")) != str(order_id):
            return {"error": "Payment does not belong to this order"}, 400
        remote_amount = int(remote_payment.get("amount") or 0)
        expected_amount = _amount_paise(payment.amount)
        if expected_amount is None:
            return {"error": "Invalid local payment amount"}, 400
        if remote_amount != expected_amount:
            return {"error": "Payment amount mismatch"}, 400
        if remote_payment.get("status") not in {"authorized", "captured"}:
            return {"error": "Payment is not authorized or captured yet"}, 400
    except Exception:
        return {"error": "Unable to reconcile payment with Razorpay"}, 502

    _mark_payment_paid(payment, payment_id)
    return {"message": "Payment verified successfully", "payment": payment.to_dict()}


def _mark_payment_paid(payment, payment_id):
    if payment.status == "paid":
        return
    payment.status = "paid"
    payment.razorpay_payment_id = payment_id
    if payment.bill_id:
        bill = db.session.get(MaintenanceBill, payment.bill_id)
        if bill is not None:
            bill.status = "paid"
    record(payment.user_id, "payment.verified", "payment", payment.id,
           f"₹{payment.amount:,.0f} marked paid", commit=False)
    db.session.commit()
    try:
        notify(
            payment.user_id,
            "Payment Successful",
            f"Your payment of ₹{payment.amount:,.0f} was successful.",
            notif_type="payment",
        )
    except Exception:
        # Payment state is already committed; a notification failure must not
        # turn a successful payment verification into an HTTP 500.
        db.session.rollback()
        current_app.logger.exception("Payment notification creation failed")


@payments_bp.post("/payments/webhook")
def razorpay_webhook():
    raw_body = request.get_data(cache=True)
    signature = request.headers.get("X-Razorpay-Signature", "")
    webhook_secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET")
    if not webhook_secret or not signature:
        return {"error": "Webhook signature is not configured"}, 400

    expected = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return {"error": "Invalid webhook signature"}, 400

    event = request.get_json(silent=True) or {}
    event_id = request.headers.get("x-razorpay-event-id") or event.get("id")
    event_type = str(event.get("event") or "")
    if not event_id or not event_type:
        return {"error": "Invalid webhook payload"}, 400

    if PaymentWebhookEvent.query.filter_by(event_id=str(event_id)).first():
        return {"ok": True, "duplicate": True}

    payment_entity = (event.get("payload") or {}).get("payment", {}).get("entity", {})
    order_entity = (event.get("payload") or {}).get("order", {}).get("entity", {})
    order_id = payment_entity.get("order_id") or order_entity.get("id")
    payment_id = payment_entity.get("id")

    webhook_event = PaymentWebhookEvent(event_id=str(event_id), event_type=event_type)
    db.session.add(webhook_event)

    local_payment = Payment.query.filter_by(razorpay_order_id=order_id).first() if order_id else None
    if local_payment:
        if event_type in {"payment.captured", "order.paid"} and payment_id:
            _mark_payment_paid(local_payment, payment_id)
        elif event_type == "payment.failed" and local_payment.status != "paid":
            local_payment.status = "failed"
            db.session.commit()
        else:
            db.session.commit()
    else:
        db.session.commit()

    return {"ok": True}


def _receipt_pdf_response(payment):
    """Build a receipt PDF and return it as a native browser download."""
    from fpdf import FPDF
    from flask import Response

    payer = db.session.get(User, payment.user_id)

    def pdf_text(value):
        # Built-in Helvetica is latin-1 only. Replace unsupported characters
        # rather than letting a resident name/description crash PDF generation.
        return str(value if value is not None else "-").encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(29, 107, 75)
    pdf.cell(0, 12, pdf_text("NestLedger"), ln=1)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 6, pdf_text("Payment Receipt"), ln=1)
    pdf.ln(6)
    pdf.set_draw_color(220, 220, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)

    created = payment.created_at
    date_text = created.strftime("%d %b %Y, %I:%M %p") if hasattr(created, "strftime") else str(created or "-")
    rows = [
        ("Receipt No.", f"NL-{payment.id:06d}"),
        ("Date", date_text),
        ("Paid By", payer.name if payer else "-"),
        ("Description", payment.description or "-"),
        ("Payment Type", (payment.payment_type or "-").title()),
        ("Razorpay Payment ID", payment.razorpay_payment_id or "-"),
        ("Status", (payment.status or "-").title()),
    ]

    pdf.set_text_color(22, 34, 29)
    left_x = 10
    value_x = 65
    label_w = 55
    value_w = 135
    row_h = 9

    for label, value in rows:
        # Explicitly reset X for every row. This is important because
        # multi_cell() leaves the cursor at the end of the cell in some
        # FPDF/PyFPDF versions, which otherwise pushes the next label
        # progressively to the right.
        y = pdf.get_y()
        pdf.set_xy(left_x, y)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(label_w, row_h, pdf_text(label))

        pdf.set_xy(value_x, y)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(value_w, row_h, pdf_text(value))

        # Start the next row at the left margin, below the tallest cell.
        pdf.set_xy(left_x, max(y + row_h, pdf.get_y()))

    pdf.ln(6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(22, 34, 29)
    amount = float(payment.amount or 0)
    pdf.cell(0, 10, pdf_text(f"Amount Paid: Rs. {amount:,.2f}"), ln=1)
    pdf.ln(14)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(140, 140, 140)
    pdf.multi_cell(0, 5, pdf_text("This is a system-generated receipt from NestLedger and does not require a signature."))

    pdf_data = pdf.output(dest="S")
    # PyFPDF 1.x returns a latin-1 string; fpdf2 returns bytes.
    # Normalize both forms so Flask always receives valid PDF bytes.
    if isinstance(pdf_data, str):
        pdf_bytes = pdf_data.encode("latin-1")
    else:
        pdf_bytes = bytes(pdf_data)
    response = Response(pdf_bytes, status=200, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f'attachment; filename="NestLedger-Receipt-{payment.id}.pdf"'
    response.headers["Content-Length"] = str(len(pdf_bytes))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


def _receipt_owner_check(pid, uid):
    payment = db.session.get(Payment, pid)
    if payment is None:
        return None, ({"error": "Payment not found"}, 404)
    requester = db.session.get(User, uid)
    if payment.user_id != uid and not (requester is not None and requester.role == "admin"):
        return None, ({"error": "You are not authorized to view this receipt"}, 403)
    if payment.status != "paid":
        return None, ({"error": "A receipt is only available for completed payments"}, 400)
    return payment, None


@payments_bp.get("/payments/<int:pid>/receipt")
@jwt_required()
def download_receipt(pid):
    payment, error = _receipt_owner_check(pid, current_user_id())
    if error:
        return error
    return _receipt_pdf_response(payment)


@payments_bp.post("/payments/<int:pid>/receipt-link")
@jwt_required()
def create_receipt_link(pid):
    uid = current_user_id()
    payment, error = _receipt_owner_check(pid, uid)
    if error:
        return error
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt="nestledger-receipt-download",
    )
    token = serializer.dumps({"pid": payment.id, "uid": uid})
    return {"url": f"/api/payments/{payment.id}/receipt-download/{token}"}


@payments_bp.get("/payments/<int:pid>/receipt-download/<token>")
def native_receipt_download(pid, token):
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt="nestledger-receipt-download",
    )
    try:
        data = serializer.loads(token, max_age=120)
    except SignatureExpired:
        return {"error": "This receipt download link has expired. Please try again."}, 403
    except BadSignature:
        return {"error": "Invalid receipt download link"}, 403

    try:
        token_pid = int(data.get("pid", -1))
        token_uid = int(data.get("uid", -1))
    except (TypeError, ValueError):
        return {"error": "Invalid receipt download link"}, 403

    if token_pid != pid:
        return {"error": "Invalid receipt download link"}, 403
    payment, error = _receipt_owner_check(pid, token_uid)
    if error:
        return error
    return _receipt_pdf_response(payment)

