"""HTTP idempotency for authenticated write operations.

Clients send Idempotency-Key. The first request stores a small replayable JSON
response; a retry with the same key returns that exact response instead of
executing the write again. Five-hundred responses are deliberately not cached.
"""
import hashlib
import json
import time
from functools import wraps

from flask import g, jsonify, make_response, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.exc import IntegrityError

from models.db import db
from models.idempotency import IdempotencyRecord
from utils.concurrency import lock_fingerprint

MAX_KEY = 180
PROCESSING_TTL = 90


def _request_hash():
    body = request.get_data(cache=True) or b""
    query = request.query_string or b""
    raw = request.method.encode() + b"\n" + request.path.encode() + b"\n" + query + b"\n" + body
    return hashlib.sha256(raw).hexdigest()


def _identity():
    try:
        value = get_jwt_identity()
        return int(value) if value is not None else None
    except (TypeError, ValueError, RuntimeError):
        return None


def idempotent(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        key = (request.headers.get("Idempotency-Key") or "").strip()
        if not key:
            return fn(*args, **kwargs)
        if len(key) > MAX_KEY:
            return {"error": "Idempotency-Key is too long"}, 400

        user_id = _identity()
        if user_id is None:
            # Public requests are scoped by normalized email when available.
            payload = request.get_json(silent=True) or {}
            email = str(payload.get("email", "")).strip().lower()
            if not email:
                return fn(*args, **kwargs)
            scope = f"anon:{email}"
        else:
            scope = f"user:{user_id}"

        request_hash = _request_hash()
        lock_fingerprint(f"idempotency:{scope}:{key}")
        record = IdempotencyRecord.query.filter_by(scope=scope, key=key).first()
        if record is not None:
            if record.request_hash != request_hash:
                return {"error": "This Idempotency-Key was already used for a different request"}, 409
            if record.status == "completed" and record.response_body is not None:
                try:
                    payload = json.loads(record.response_body)
                except (TypeError, ValueError):
                    payload = {"error": "Stored idempotent response is invalid"}
                return make_response(jsonify(payload), record.response_status or 200)
            age = time.time() - record.updated_at.timestamp() if record.updated_at else 0
            if age < PROCESSING_TTL:
                return {"error": "This request is already being processed. Please retry with the same Idempotency-Key shortly."}, 409
            record.status = "processing"
            record.updated_at = db.func.now()
        else:
            record = IdempotencyRecord(
                user_id=user_id,
                scope=scope,
                key=key,
                request_hash=request_hash,
                status="processing",
            )
            db.session.add(record)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                # Advisory locking normally prevents this race; retrying the lookup
                # makes the database unique constraint the final authority.
                record = IdempotencyRecord.query.filter_by(scope=scope, key=key).first()
                if record and record.request_hash == request_hash and record.status == "completed":
                    return make_response(jsonify(json.loads(record.response_body)), record.response_status or 200)
                return {"error": "This request is already being processed. Please retry with the same Idempotency-Key shortly."}, 409

        result = fn(*args, **kwargs)
        response = make_response(result)
        if 200 <= response.status_code < 500:
            payload = response.get_json(silent=True)
            if payload is not None:
                record.status = "completed"
                record.response_status = response.status_code
                record.response_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                record.updated_at = db.func.now()
                db.session.commit()
            else:
                db.session.delete(record)
                db.session.commit()
        else:
            db.session.delete(record)
            db.session.commit()
        return response

    return wrapped
