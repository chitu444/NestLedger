"""Small, versioned, additive database migrations for NestLedger.

This intentionally avoids destructive migrations and works with the SQLite/PostgreSQL
engines supported by the app. New deployments still create the current schema first;
these migrations are for safely upgrading older databases.
"""
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from models.db import db

MIGRATIONS = (
    (1, "add_hardening_columns", "_migration_1_hardening_columns"),
    (2, "add_query_indexes", "_migration_2_query_indexes"),
)


def _ensure_table():
    db.session.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, applied_at TIMESTAMP NOT NULL)"
    ))
    db.session.commit()


def _migration_1_hardening_columns():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "complaint" in tables:
        cols = {c["name"] for c in inspector.get_columns("complaint")}
        if "updated_at" not in cols:
            db.session.execute(text("ALTER TABLE complaint ADD COLUMN updated_at TIMESTAMP"))
            db.session.execute(text("UPDATE complaint SET updated_at = created_at WHERE updated_at IS NULL"))

    if "vendor" in tables:
        cols = {c["name"] for c in inspector.get_columns("vendor")}
        if "user_id" not in cols:
            db.session.execute(text("ALTER TABLE vendor ADD COLUMN user_id INTEGER"))
        db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_vendor_user_id ON vendor (user_id)"))

    if "maintenance_bill" in tables:
        cols = {c["name"] for c in inspector.get_columns("maintenance_bill")}
        if "assigned_by_id" not in cols:
            db.session.execute(text("ALTER TABLE maintenance_bill ADD COLUMN assigned_by_id INTEGER"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_maintenance_bill_assigned_by_id ON maintenance_bill (assigned_by_id)"))


def _migration_2_query_indexes():
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_payment_user_status_created ON payment (user_id, status, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_payment_bill_status ON payment (bill_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_bill_user_status_created ON maintenance_bill (user_id, status, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_workorder_resident_status ON work_order (resident_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_workorder_vendor_status ON work_order (vendor_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_workorder_status_created ON work_order (status, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_complaint_user_status_created ON complaint (user_id, status, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_notification_user_read_created ON notification (user_id, is_read, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_quote_order_vendor_status ON quotation (work_order_id, vendor_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_expense_created_category ON expense (created_at, category)",
        "CREATE INDEX IF NOT EXISTS ix_notice_created ON notice (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_audit_actor_created ON audit_log (actor_id, created_at)",
    )
    tables = set(inspect(db.engine).get_table_names())
    for statement in statements:
        table = statement.split(" ON ", 1)[1].split(" ", 1)[0]
        if table in tables:
            db.session.execute(text(statement))


def migration_status():
    """Return applied and pending migration metadata without changing the schema."""
    _ensure_table()
    applied_rows = db.session.execute(
        text("SELECT version, name, applied_at FROM schema_migrations ORDER BY version")
    ).mappings().all()
    applied = {row["version"] for row in applied_rows}
    pending = [
        {"version": version, "name": name}
        for version, name, _ in MIGRATIONS
        if version not in applied
    ]
    return {
        "applied": [dict(row) for row in applied_rows],
        "pending": pending,
        "current": max(applied, default=0),
        "latest": max((version for version, _, _ in MIGRATIONS), default=0),
    }


def _migration_lock():
    """Serialize migration execution on PostgreSQL; SQLite relies on its DB lock."""
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(8473921)"))


def run_migrations():
    """Apply all pending additive migrations exactly once."""
    _ensure_table()
    _migration_lock()
    applied = {row[0] for row in db.session.execute(
        text("SELECT version FROM schema_migrations ORDER BY version")
    ).all()}
    for version, name, fn_name in MIGRATIONS:
        if version in applied:
            continue
        try:
            globals()[fn_name]()
            db.session.execute(
                text("INSERT INTO schema_migrations (version, name, applied_at) VALUES (:v, :n, CURRENT_TIMESTAMP)"),
                {"v": version, "n": name},
            )
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
    return migration_status()
