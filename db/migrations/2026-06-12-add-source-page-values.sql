-- ────────────────────────────────────────────────────────────────────────────
-- Migration: align work_queue_actions.source_page CHECK constraint with
-- scripts/work_queue/schema.py's VALID_SOURCE_PAGES set.
-- Date: 12 Jun 2026
-- ────────────────────────────────────────────────────────────────────────────
--
-- WHY THIS MIGRATION EXISTS
-- ------------------------------------------------------------------------
-- The Wave A schema-drift detector (scripts/check_supabase_schema_drift.py)
-- found that Python declares 'enrolment' + 'opportunity' as valid
-- source_page values, but db/schema.sql only has the original 7:
-- seo-organic, meta-ads, google-ads, gbp, organic-social, membership,
-- overview.
--
-- The Python additions happened on 09 Jun 2026 when:
--   - mwcc_enrolment_emitter.py started writing source_page='enrolment'
--   - opportunity_emitter.py started writing source_page='opportunity'
-- The SQL never caught up. Upserts succeed because Supabase's actual
-- CHECK constraint must have been altered manually (or never had the
-- constraint enforced after a previous migration). Either way, the SQL
-- file and code are out of sync — the dev-cycle detector flagged it.
--
-- This migration brings the CHECK constraint to a known good state that
-- matches schema.py.
--
-- WHAT TO RUN
-- ------------------------------------------------------------------------
-- Paste this whole file into Supabase Dashboard → SQL Editor → Run.
-- Idempotent: drops and re-adds the CHECK constraint by name.

BEGIN;

-- Drop the existing constraint (name may vary if a prior migration
-- already touched it — try the canonical Postgres-generated name first,
-- then fall back to dropping any CHECK on source_page).
DO $$
DECLARE
    cn text;
BEGIN
    FOR cn IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class      rel ON rel.oid = con.conrelid
        JOIN pg_attribute  att ON att.attrelid = rel.oid
                              AND att.attnum  = ANY(con.conkey)
        WHERE rel.relname = 'work_queue_actions'
          AND att.attname = 'source_page'
          AND con.contype = 'c'
    LOOP
        EXECUTE format('ALTER TABLE public.work_queue_actions DROP CONSTRAINT %I', cn);
    END LOOP;
END $$;

-- Add the canonical constraint.
ALTER TABLE public.work_queue_actions
    ADD CONSTRAINT work_queue_actions_source_page_check
    CHECK (source_page IN (
        'seo-organic',
        'meta-ads',
        'google-ads',
        'gbp',
        'organic-social',
        'membership',
        'enrolment',     -- MWCC childcare equivalent (added 09 Jun 2026)
        'opportunity',   -- paid→organic switch tracking (added 09 Jun 2026)
        'overview'
    ));

COMMIT;

-- ────────────────────────────────────────────────────────────────────────────
-- VERIFICATION
-- ────────────────────────────────────────────────────────────────────────────
-- After running, the dev-cycle detector should report a clean state:
--   .venv/bin/python3.13 scripts/check_supabase_schema_drift.py
-- Expected output: "✅ No drift detected."
--
-- And a manual check confirms the constraint matches:
--   SELECT pg_get_constraintdef(con.oid)
--   FROM pg_constraint con
--   JOIN pg_class rel ON rel.oid = con.conrelid
--   WHERE rel.relname = 'work_queue_actions'
--     AND con.conname LIKE '%source_page%';
-- ────────────────────────────────────────────────────────────────────────────
