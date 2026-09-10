-- Documentation copy of migration 4. Runtime application is handled by utils/migrations.py.
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_resident_apartment ON "user" (apartment) WHERE role = 'resident' AND apartment IS NOT NULL;
