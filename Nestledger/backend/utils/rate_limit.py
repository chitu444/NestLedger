from datetime import datetime, timedelta

from models.auth_rate_limit import AuthRateLimit
from models.db import db
from utils.concurrency import lock_fingerprint

WINDOW = timedelta(minutes=10)
BLOCK = timedelta(minutes=15)
MAX_FAILURES = 5


def _get(scope):
    lock_fingerprint(f"auth-rate:{scope}")
    row = db.session.query(AuthRateLimit).filter_by(scope=scope).with_for_update().first()
    now = datetime.utcnow()
    if row is None:
        # A PostgreSQL advisory transaction lock serializes normal concurrent
        # requests, but a serverless cold-start can still encounter a race at
        # the UNIQUE(scope) constraint. Use a savepoint so that a losing insert
        # does not poison the outer request transaction; then reuse the row that
        # won the race. This prevents the global IntegrityError handler from
        # turning a login into a misleading HTTP 409 Conflict.
        try:
            with db.session.begin_nested():
                row = AuthRateLimit(scope=scope, failures=0, window_started_at=now)
                db.session.add(row)
                db.session.flush()
        except Exception as exc:
            from sqlalchemy.exc import IntegrityError
            if not isinstance(exc, IntegrityError):
                raise
            row = (
                db.session.query(AuthRateLimit)
                .filter_by(scope=scope)
                .with_for_update()
                .first()
            )
            if row is None:
                raise
    elif now - row.window_started_at >= WINDOW:
        row.failures = 0
        row.window_started_at = now
        row.blocked_until = None
    return row, now


def action_allowed(action: str, email: str):
    row, now = _get(f"{action}:{email}")
    if row.blocked_until and row.blocked_until > now:
        remaining = max(1, int((row.blocked_until - now).total_seconds() // 60) + 1)
        db.session.commit()
        return False, f"Too many unsuccessful sign-in attempts. Please try again in about {remaining} minute(s)."
    db.session.commit()
    return True, None


def action_failure(action: str, email: str):
    row, now = _get(f"{action}:{email}")
    row.failures += 1
    if row.failures >= MAX_FAILURES:
        row.blocked_until = now + BLOCK
    db.session.commit()


def action_success(action: str, email: str):
    row = db.session.query(AuthRateLimit).filter_by(scope=f"{action}:{email}").first()
    if row:
        row.failures = 0
        row.blocked_until = None
        row.window_started_at = datetime.utcnow()
        db.session.commit()


def login_allowed(email: str): return action_allowed("login", email)
def login_failure(email: str): return action_failure("login", email)
def login_success(email: str): return action_success("login", email)
