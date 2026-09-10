# NestLedger database migrations

NestLedger now tracks additive database upgrades in the `schema_migrations` table and applies them at startup through `backend/utils/migrations.py`.

The current migration history is:

- **1 — add_hardening_columns:** adds legacy-compatible `complaint.updated_at`, `vendor.user_id`, and `maintenance_bill.assigned_by_id` when missing.
- **2 — add_query_indexes:** creates the composite indexes used by pagination, filtering, dashboard queries, and reports.
- **3 — enforce_pending_quote_uniqueness:** removes legacy duplicate pending quotes for the same vendor/work order, then enforces one pending quote per vendor/work order at the database level.
- **4 — enforce_resident_apartment_uniqueness:** enforces one resident owner per non-null apartment value at the database level; valid new registrations use the fixed A-1 through Z-7 inventory.

Migrations are intentionally additive and non-destructive. Existing data is not dropped or rewritten beyond backfilling `complaint.updated_at` from `created_at` when the column is introduced and collapsing duplicate pending quotes so the new uniqueness rule can be applied.

For a production deployment, keep the application release and migration code in the same deployment so an older database is upgraded before the new endpoints depend on the added fields/indexes.

### Concurrency hardening (application-level)

The current codebase also uses row locks for work-order acceptance/quote acceptance and reconciles Razorpay payment capture/amount/currency before changing local payment state. These changes do not require a new schema migration.

