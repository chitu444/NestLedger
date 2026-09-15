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
    (6, "harden_financial_amount_precision", "_migration_6_financial_precision"),
    (7, "harden_apartment_claims", "_migration_7_apartment_claims"),
    (8, "add_idempotency_records", "_migration_8_idempotency_records"),
    (9, "enforce_financial_logical_uniqueness", "_migration_9_logical_uniqueness"),
    (10, "enforce_data_domain_constraints", "_migration_10_domain_constraints"),
    (11, "add_auth_rate_limit", "_migration_11_auth_rate_limit"),
    (12, "repair_integer_primary_key_generation", "_migration_12_integer_primary_key_generation"),
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

def _migration_7_apartment_claims():
    """Create the canonical 91-unit inventory and atomically backfill claims."""
    from utils.validators import APARTMENT_CODES
    tables = set(inspect(db.engine).get_table_names())
    if "user" not in tables:
        return
    db.session.execute(text("CREATE TABLE IF NOT EXISTS apartment_slot (code VARCHAR(10) PRIMARY KEY, claimed_by_user_id INTEGER UNIQUE REFERENCES \"user\"(id) ON DELETE SET NULL)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_apartment_slot_claimed_by_user_id ON apartment_slot (claimed_by_user_id)"))
    for code in APARTMENT_CODES:
        if db.engine.dialect.name == "postgresql":
            db.session.execute(text("INSERT INTO apartment_slot (code) VALUES (:code) ON CONFLICT (code) DO NOTHING"), {"code": code})
        else:
            db.session.execute(text("INSERT OR IGNORE INTO apartment_slot (code) VALUES (:code)"), {"code": code})

    duplicates = db.session.execute(text("SELECT apartment, COUNT(*) AS n FROM \"user\" WHERE role = 'resident' AND apartment IS NOT NULL GROUP BY apartment HAVING COUNT(*) > 1")).all()
    if duplicates:
        raise RuntimeError("Cannot create apartment claims: duplicate resident apartment assignments exist")
    allowed_sql = ",".join("'" + c + "'" for c in APARTMENT_CODES)
    invalid = db.session.execute(text("SELECT apartment FROM \"user\" WHERE role = 'resident' AND apartment IS NOT NULL AND apartment NOT IN (" + allowed_sql + ") LIMIT 1")).first()
    if invalid:
        raise RuntimeError(f"Cannot create apartment claims: invalid apartment {invalid[0]}")
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("UPDATE apartment_slot AS s SET claimed_by_user_id = u.id FROM \"user\" AS u WHERE u.role = 'resident' AND u.apartment = s.code AND (s.claimed_by_user_id IS NULL OR s.claimed_by_user_id = u.id)"))
    else:
        db.session.execute(text("UPDATE apartment_slot SET claimed_by_user_id = (SELECT id FROM \"user\" WHERE role = 'resident' AND apartment = apartment_slot.code) WHERE code IN (SELECT apartment FROM \"user\" WHERE role = 'resident')"))


def _ensure_integer_pk_generation(table_name: str):
    """Ensure PostgreSQL-created legacy integer PK tables generate IDs.

    Older additive migrations used ``INTEGER PRIMARY KEY``. PostgreSQL treats that
    as NOT NULL without an auto-generated value, unlike SQLite. Repair existing
    tables and make fresh migration-created tables safe.
    """
    if db.engine.dialect.name != "postgresql":
        return
    row = db.session.execute(text("""
        SELECT column_default, is_identity
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = :table_name
          AND column_name = 'id'
    """), {"table_name": table_name}).mappings().first()
    if not row:
        return
    if row["is_identity"] != "YES" and not row["column_default"]:
        db.session.execute(text(
            f'ALTER TABLE "{table_name}" ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY'
        ))
    seq = db.session.execute(text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
                             {"table_name": table_name}).scalar()
    if seq:
        db.session.execute(text(
            "SELECT setval(:seq, COALESCE((SELECT MAX(id) FROM \"" + table_name + "\"), 0) + 1, false)"
        ), {"seq": seq})


def _migration_8_idempotency_records():
    db.session.execute(text("CREATE TABLE IF NOT EXISTS idempotency_record (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES \"user\"(id), scope VARCHAR(220) NOT NULL, key VARCHAR(200) NOT NULL, request_hash VARCHAR(64) NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'processing', response_status INTEGER, response_body TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, CONSTRAINT uq_idempotency_scope_key UNIQUE (scope, key))"))
    cols = {c["name"] for c in inspect(db.session.connection()).get_columns("idempotency_record")}
    if "scope" not in cols:
        db.session.execute(text("ALTER TABLE idempotency_record ADD COLUMN scope VARCHAR(220)"))
        if db.engine.dialect.name == "postgresql":
            db.session.execute(text("UPDATE idempotency_record SET scope = 'user:' || COALESCE(CAST(user_id AS VARCHAR), 'anonymous') WHERE scope IS NULL"))
        else:
            db.session.execute(text("UPDATE idempotency_record SET scope = 'user:' || COALESCE(CAST(user_id AS TEXT), 'anonymous') WHERE scope IS NULL"))
    db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_idempotency_scope_key_idx ON idempotency_record (scope, key)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_idempotency_user_id ON idempotency_record (user_id)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_idempotency_created ON idempotency_record (created_at)"))
    _ensure_integer_pk_generation("idempotency_record")


def _migration_9_logical_uniqueness():
    tables = set(inspect(db.engine).get_table_names())
    if "maintenance_bill" in tables:
        duplicate = db.session.execute(text("SELECT user_id, lower(trim(month)) AS month_key FROM maintenance_bill GROUP BY user_id, lower(trim(month)) HAVING COUNT(*) > 1 LIMIT 1")).first()
        if duplicate:
            raise RuntimeError(f"Cannot enforce maintenance-bill uniqueness: duplicate bill exists for resident {duplicate[0]} / {duplicate[1]}")
        db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_bill_user_month ON maintenance_bill (user_id, lower(trim(month)))"))
    if "payment" in tables:
        duplicate_bill = db.session.execute(text("SELECT bill_id FROM payment WHERE status = 'paid' AND bill_id IS NOT NULL GROUP BY bill_id HAVING COUNT(*) > 1 LIMIT 1")).first()
        if duplicate_bill:
            raise RuntimeError(f"Cannot enforce paid-bill uniqueness: multiple paid payments exist for bill {duplicate_bill[0]}")
        duplicate_order = db.session.execute(text("SELECT work_order_id FROM payment WHERE status = 'paid' AND work_order_id IS NOT NULL GROUP BY work_order_id HAVING COUNT(*) > 1 LIMIT 1")).first()
        if duplicate_order:
            raise RuntimeError(f"Cannot enforce paid-work-order uniqueness: multiple paid payments exist for work order {duplicate_order[0]}")
        db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_paid_bill ON payment (bill_id) WHERE status = 'paid' AND bill_id IS NOT NULL"))
        db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_paid_work_order ON payment (work_order_id) WHERE status = 'paid' AND work_order_id IS NOT NULL"))


def _migration_10_domain_constraints():
    """Validate and add simple PostgreSQL domain checks without PL/pgSQL."""
    if db.engine.dialect.name != "postgresql":
        return
    checks = (
        ("maintenance_bill", "amount", "ck_maintenance_bill_amount_nonnegative", "amount >= 0"),
        ("payment", "amount", "ck_payment_amount_nonnegative", "amount >= 0"),
        ("expense", "amount", "ck_expense_amount_nonnegative", "amount >= 0"),
        ("invoice", "amount", "ck_invoice_amount_nonnegative", "amount >= 0"),
        ("quotation", "amount", "ck_quotation_amount_nonnegative", "amount >= 0"),
        ("work_order", "amount", "ck_work_order_amount_nonnegative", "amount >= 0"),
    )
    for table, column, name, expression in checks:
        if table not in set(inspect(db.engine).get_table_names()):
            continue
        bad = db.session.execute(text(f"SELECT 1 FROM {table} WHERE {column} < 0 LIMIT 1")).first()
        if bad:
            raise RuntimeError(f"Cannot enforce {name}: negative {column} data exists")
        exists = db.session.execute(text("SELECT 1 FROM pg_constraint WHERE conname = :name"), {"name": name}).first()
        if not exists:
            db.session.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expression})"))
    if "rating" in set(inspect(db.engine).get_table_names()):
        bad = db.session.execute(text("SELECT 1 FROM rating WHERE stars < 1 OR stars > 5 LIMIT 1")).first()
        if bad:
            raise RuntimeError("Cannot enforce rating range: existing stars value is outside 1..5")
        exists = db.session.execute(text("SELECT 1 FROM pg_constraint WHERE conname = 'ck_rating_stars_range'")).first()
        if not exists:
            db.session.execute(text("ALTER TABLE rating ADD CONSTRAINT ck_rating_stars_range CHECK (stars BETWEEN 1 AND 5)"))


def _migration_11_auth_rate_limit():
    db.session.execute(text("CREATE TABLE IF NOT EXISTS auth_rate_limit (id INTEGER PRIMARY KEY, scope VARCHAR(220) NOT NULL UNIQUE, failures INTEGER NOT NULL DEFAULT 0, window_started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, blocked_until TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_rate_limit_scope ON auth_rate_limit (scope)"))
    _ensure_integer_pk_generation("auth_rate_limit")


def _migration_12_integer_primary_key_generation():
    """Repair PostgreSQL integer PKs created by migrations 8 and 11."""
    _ensure_integer_pk_generation("idempotency_record")
    _ensure_integer_pk_generation("auth_rate_limit")


def migration_status():
    """Return migration metadata without creating or changing schema objects."""
    if "schema_migrations" not in set(inspect(db.engine).get_table_names()):
        return {"applied": [], "pending": [{"version": version, "name": name} for version, name, _ in MIGRATIONS], "current": 0, "latest": max((version for version, _, _ in MIGRATIONS), default=0)}
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
        except Exception:
            # A migration may raise a non-SQLAlchemy error (for example a
            # validation/runtime error). Always clear the transaction before
            # surfacing it so a serverless worker cannot reuse a failed session.
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


def _migration_6_financial_precision():
    """Convert financial amounts to exact two-decimal NUMERIC on PostgreSQL."""
    tables = ("maintenance_bill", "payment", "quotation", "invoice", "expense", "work_order")
    existing = set(inspect(db.engine).get_table_names())
    tables = [t for t in tables if t in existing]
    if db.engine.dialect.name != "postgresql":
        return
    for table in tables:
        bad = db.session.execute(text(
            f"SELECT COUNT(*) FROM {table} WHERE amount IS NULL OR amount < 0 "
            "OR amount > 9999999999.99 OR amount::text IN ('NaN', 'Infinity', '-Infinity')"
        )).scalar()
        if bad:
            raise RuntimeError(
                f"Cannot convert {table}.amount to NUMERIC(12,2): {bad} invalid financial amount(s) found."
            )
    for table in tables:
        db.session.execute(text(
            f"ALTER TABLE {table} ALTER COLUMN amount TYPE NUMERIC(12,2) "
            "USING ROUND(amount::numeric, 2)"
        ))
