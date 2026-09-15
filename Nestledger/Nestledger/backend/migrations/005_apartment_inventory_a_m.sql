-- Migration 5: limit resident apartment inventory to A-1 through M-7.
-- Existing residents outside this range must be reconciled before applying.
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM "user"
        WHERE role = 'resident' AND apartment IS NOT NULL
          AND apartment !~ '^[A-M]-[1-7]$'
    ) THEN
        RAISE EXCEPTION 'Existing resident apartment assignments fall outside A-1 through M-7; reconcile them before migration 5';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_resident_apartment_inventory_a_m') THEN
        ALTER TABLE "user" ADD CONSTRAINT ck_resident_apartment_inventory_a_m
        CHECK (role <> 'resident' OR apartment IS NULL OR apartment ~ '^[A-M]-[1-7]$');
    END IF;
END $$;
