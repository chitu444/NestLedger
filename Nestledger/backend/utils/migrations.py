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
    (3, "enforce_pending_quote_uniqueness", "_migration_3_quote_integrity"),
    (4, "enforce_resident_apartment_uniqueness", "_migration_4_apartment_integrity"),
    (5, "limit_apartment_inventory_to_a_m", "_migration_5_apartment_inventory"),
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



def _migration_3_quote_integrity():
    """Remove legacy duplicate pending quotes, then enforce one pending quote per vendor/order."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "quotation" not in tables:
        return
    from models.quotation import Quotation
    pending = (
        Quotation.query
        .filter(Quotation.status == "pending")
        .order_by(Quotation.work_order_id, Quotation.vendor_id, Quotation.id.desc())
        .all()
    )
    seen = set()
    for quote in pending:
        key = (quote.work_order_id, quote.vendor_id)
        if key in seen:
            db.session.delete(quote)
        else:
            seen.add(key)
    db.session.flush()
    db.session.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_quotation_pending_vendor_order "
        "ON quotation (work_order_id, vendor_id) WHERE status = 'pending'"
    ))

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



def _migration_5_apartment_inventory():
    """Restrict the resident apartment inventory to blocks A through M, units 1 through 7."""
    allowed = {f"{chr(65+b)}-{u}" for b in range(13) for u in range(1, 8)}
    rows = db.session.execute(db.text("""
        SELECT apartment, COUNT(*) AS c FROM "user"
        WHERE role = 'resident' AND apartment IS NOT NULL
        GROUP BY apartment
    """)).mappings().all()
    outside = [str(r["apartment"]).strip().upper() for r in rows if str(r["apartment"] or "").strip().upper() not in allowed]
    if outside:
        raise RuntimeError(
            "Cannot restrict apartment inventory to A-1 through M-7 because existing resident assignments are outside the new inventory: "
            + ", ".join(outside)
        )
    # PostgreSQL supports ALTER TABLE ... ADD CONSTRAINT inside a DO block.
    # SQLite does not support DO/PLpgSQL (and cannot add a table CHECK constraint
    # with ALTER TABLE), so keep the migration portable: the application-level
    # validator is authoritative on SQLite while PostgreSQL gets a DB constraint.
    if db.engine.dialect.name == "postgresql":
        db.session.execute(db.text("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'ck_resident_apartment_inventory_a_m'
                ) THEN
                    ALTER TABLE "user" ADD CONSTRAINT ck_resident_apartment_inventory_a_m
                    CHECK (role <> 'resident' OR apartment IS NULL OR apartment ~ '^[A-M]-[1-7]$');
                END IF;
            END $$;
        """))
    elif db.engine.dialect.name == "sqlite":
        # SQLite cannot add a CHECK constraint to an existing table. All resident
        # creation/update paths validate the same A-1..M-7 inventory before commit,
        # and the unique partial index from migration 4 still enforces one owner.
        pass
    else:
        # Other SQLAlchemy dialects: do not execute PostgreSQL-specific SQL.
        pass
    db.session.commit()

def _migration_4_apartment_integrity():
    """Normalize valid apartment codes and prevent duplicate resident ownership."""
    inspector = inspect(db.engine)
    if "user" not in inspector.get_table_names():
        return
    # Normalize stored resident apartment codes before enforcing uniqueness.
    # This prevents values such as " a-1 " and "A-1" from bypassing the unique
    # index and then failing the PostgreSQL inventory CHECK constraint.
    resident_rows = db.session.execute(text("""
        SELECT id, apartment FROM "user"
        WHERE role = 'resident' AND apartment IS NOT NULL
    """)).mappings().all()
    for resident in resident_rows:
        normalized = str(resident["apartment"] or "").strip().upper()
        if normalized and normalized != resident["apartment"]:
            db.session.execute(text('UPDATE "user" SET apartment = :apartment WHERE id = :user_id'),
                               {"apartment": normalized, "user_id": resident["id"]})

    # Existing records outside the new A-1..M-7 inventory are preserved.
    # If duplicate assignments exist, preserve every resident but clear the later
    # duplicate assignments deterministically so the unique index can be created.
    rows = db.session.execute(text("""
        SELECT apartment, COUNT(*) AS c FROM "user"
        WHERE role = 'resident' AND apartment IS NOT NULL
        GROUP BY apartment HAVING COUNT(*) > 1
    """)).mappings().all()
    if rows:
        # The uniqueness index cannot be created while legacy data contains duplicate
        # apartment assignments. Do not delete residents or guess a new apartment for
        # them. Keep the first resident deterministically and clear the duplicate
        # assignments so those residents can be assigned an available apartment again.
        for row in rows:
            apartment = str(row["apartment"] or "").strip().upper()
            duplicate_ids = db.session.execute(text("""
                SELECT id FROM "user"
                WHERE role = 'resident' AND apartment = :apartment
                ORDER BY id
            """), {"apartment": apartment}).scalars().all()
            for duplicate_id in duplicate_ids[1:]:
                db.session.execute(text("""
                    UPDATE "user" SET apartment = NULL WHERE id = :user_id
                """), {"user_id": duplicate_id})
    db.session.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_user_resident_apartment
        ON "user" (apartment) WHERE role = 'resident' AND apartment IS NOT NULL
    """))
