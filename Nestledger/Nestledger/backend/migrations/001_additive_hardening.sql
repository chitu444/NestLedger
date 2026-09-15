-- Documentation copy of migration 1. Runtime application is handled by utils/migrations.py.
ALTER TABLE complaint ADD COLUMN updated_at TIMESTAMP;
ALTER TABLE vendor ADD COLUMN user_id INTEGER;
ALTER TABLE maintenance_bill ADD COLUMN assigned_by_id INTEGER;
