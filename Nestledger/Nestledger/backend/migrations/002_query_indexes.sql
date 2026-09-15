-- Documentation copy of migration 2. Runtime application is handled by utils/migrations.py.
CREATE INDEX IF NOT EXISTS ix_payment_user_status_created ON payment (user_id, status, created_at);
CREATE INDEX IF NOT EXISTS ix_payment_bill_status ON payment (bill_id, status);
CREATE INDEX IF NOT EXISTS ix_bill_user_status_created ON maintenance_bill (user_id, status, created_at);
CREATE INDEX IF NOT EXISTS ix_workorder_resident_status ON work_order (resident_id, status);
CREATE INDEX IF NOT EXISTS ix_workorder_vendor_status ON work_order (vendor_id, status);
CREATE INDEX IF NOT EXISTS ix_workorder_status_created ON work_order (status, created_at);
CREATE INDEX IF NOT EXISTS ix_complaint_user_status_created ON complaint (user_id, status, created_at);
CREATE INDEX IF NOT EXISTS ix_notification_user_read_created ON notification (user_id, is_read, created_at);
CREATE INDEX IF NOT EXISTS ix_quote_order_vendor_status ON quotation (work_order_id, vendor_id, status);
CREATE INDEX IF NOT EXISTS ix_expense_created_category ON expense (created_at, category);
CREATE INDEX IF NOT EXISTS ix_notice_created ON notice (created_at);
CREATE INDEX IF NOT EXISTS ix_audit_actor_created ON audit_log (actor_id, created_at);
