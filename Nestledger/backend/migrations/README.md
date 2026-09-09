# NestLedger database migrations

NestLedger now tracks additive database upgrades in the `schema_migrations` table and applies them at startup through `backend/utils/migrations.py`.

The current migration history is:

- **1 — add_hardening_columns:** adds legacy-compatible `complaint.updated_at`, `vendor.user_id`, and `maintenance_bill.assigned_by_id` when missing.
- **2 — add_query_indexes:** creates the composite indexes used by pagination, filtering, dashboard queries, and reports.

Migrations are intentionally additive and non-destructive. Existing data is not dropped or rewritten beyond backfilling `complaint.updated_at` from `created_at` when the column is introduced.

For a production deployment, keep the application release and migration code in the same deployment so an older database is upgraded before the new endpoints depend on the added fields/indexes.
