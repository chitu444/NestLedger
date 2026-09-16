# NestLedger database migrations

NestLedger tracks additive schema upgrades in `schema_migrations` through `backend/utils/migrations.py`.

## Production rule

**Vercel application startup never creates or alters schema.** Cold starts are read-only with respect to database structure. Production migrations are explicit operations only:

```bash
python scripts/migrate.py status
python scripts/migrate.py migrate
python scripts/migrate.py status
```

Run the migration command against the same `DATABASE_URL` used by production before promoting a release that depends on a new migration. `/api/health` reports pending migrations without creating the migration table.

## Current migration history

- **1 — add_hardening_columns:** adds legacy-compatible `complaint.updated_at`, `vendor.user_id`, and `maintenance_bill.assigned_by_id` when missing.
- **2 — add_query_indexes:** creates composite indexes used by pagination, filtering, dashboards, and reports.
- **3 — enforce_pending_quote_uniqueness:** removes legacy duplicate pending quotes and enforces one pending quote per vendor/work order.
- **4 — enforce_resident_apartment_uniqueness:** normalizes resident apartments and enforces one resident owner per non-null apartment value.
- **5 — limit_apartment_inventory_to_a_m:** restricts resident apartment assignments to A-1 through M-7 on PostgreSQL; SQLite uses application validation.
- **6 — harden_financial_amount_precision:** converts PostgreSQL financial amount columns to `NUMERIC(12,2)` after validating existing data.
- **7 — harden_apartment_claims:** creates the canonical 91-row A–M × 7 inventory and atomically backfills resident ownership.
- **8 — add_idempotency_records:** creates replay records for authenticated/public write requests using an idempotency key and request hash.
- **9 — enforce_financial_logical_uniqueness:** enforces one maintenance bill per resident/month and one successful payment per bill/work order.
- **10 — enforce_data_domain_constraints:** enforces non-negative financial amounts and rating values from 1 through 5 on PostgreSQL.
- **11 — add_auth_rate_limit:** creates the database-backed sign-in throttling state.
- **12 — repair_integer_primary_key_generation:** repairs PostgreSQL identity generation for migration-created integer primary keys.

Migrations are additive and deliberately fail with a clear error when existing data is ambiguous in a way that would make a new constraint unsafe. They do not silently delete residents or financial records.

## Concurrency hardening

Application writes use PostgreSQL advisory locks and row locks where logical operations need serialization. Database unique constraints remain the final authority for apartment ownership, pending quotes, bills, and successful payments.
