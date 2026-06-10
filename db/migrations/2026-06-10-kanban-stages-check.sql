-- ────────────────────────────────────────────────────────────────────────────
-- Migration: Sync planner_status CHECK constraint with the new 5-stage kanban
-- Date: 10 Jun 2026
-- ────────────────────────────────────────────────────────────────────────────
--
-- WHY THIS MIGRATION EXISTS
-- ------------------------------------------------------------------------
-- Wave 1 (10 Jun 2026) renamed kanban stages in the dashboard:
--   Idea            → Proposed
--   Angela QC       → Brand Manager QC
--   Denver Approval → Brand Manager QC (merged · Denver's gate moved to
--                     the Proposed approval popup, not a kanban column)
--   (new)           → Rejected (hidden column)
--
-- Wave 1's migrate_kanban_stages.py was a DATA migration — it renamed
-- existing rows. The CHECK constraint in db/schema.sql was NOT updated,
-- so every cbState.planner.setStatus('Proposed' | 'Brand Manager QC' |
-- 'Rejected') call has been silently rejected by Supabase since Wave 1
-- shipped. Confirmed via REST probe 10 Jun 2026:
--   HTTP 400 · 23514 · planner_status_status_check violation
--
-- DOWNSTREAM EFFECT
-- ------------------------------------------------------------------------
-- - Items emitted with 'Proposed' status never wrote to Supabase. Local
--   cache shows the state correctly; other browsers can't sync.
-- - "Approved → In Progress" works (In Progress is in both lists).
-- - "Rejected" never persists. "Show rejected" toggle has nothing to
--   show beyond the current browser session.
--
-- WHAT TO RUN
-- ------------------------------------------------------------------------
-- Paste this whole file into Supabase Dashboard → SQL Editor → Run.
-- Idempotent: DROP IF EXISTS then ADD. Safe to re-run.
--
-- After this lands, the dashboard will start writing planner_status rows
-- with the new stage names successfully. Existing rows already use the
-- new names (Wave 1's migrate_kanban_stages.py made sure of that).
-- ────────────────────────────────────────────────────────────────────────────

BEGIN;

-- 1. Drop the stale constraint
ALTER TABLE public.planner_status
    DROP CONSTRAINT IF EXISTS planner_status_status_check;

-- 2. Recreate with the new 5-stage list + Rejected (hidden) + legacy keys
--    Legacy keys ('Idea', 'Angela QC', 'Denver Approval', 'Kelley QC') are
--    KEPT in the allow-list so any in-flight migration writes from old
--    browsers don't fail. Wave 1's localStorage IIFE migrates them client-
--    side on next page load; until the last team browser cycles, accept
--    both vocabularies.
ALTER TABLE public.planner_status
    ADD CONSTRAINT planner_status_status_check
    CHECK (status IN (
        -- Current vocabulary (Wave 1 · 10 Jun 2026)
        'Proposed',
        'In Progress',
        'Brand Manager QC',
        'Scheduled',
        'Published',
        'Rejected',
        -- Legacy vocabulary (still accepted until every browser cycles)
        'Idea',
        'Angela QC',
        'Kelley QC',
        'Denver Approval'
    ));

-- 3. Update default to match the new vocabulary
ALTER TABLE public.planner_status
    ALTER COLUMN status SET DEFAULT 'Proposed';

-- ────────────────────────────────────────────────────────────────────────────
-- Sanity check: every existing row should pass the new constraint.
-- The Wave 1 data migration already mapped Idea→Proposed and
-- Denver Approval→Angela QC. (Wave 1's intent was Brand Manager QC but the
-- script wrote 'Angela QC' — that's still allowed.)
-- ────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    bad_count integer;
BEGIN
    SELECT COUNT(*) INTO bad_count
    FROM public.planner_status
    WHERE status NOT IN (
        'Proposed','In Progress','Brand Manager QC','Scheduled','Published','Rejected',
        'Idea','Angela QC','Kelley QC','Denver Approval'
    );
    IF bad_count > 0 THEN
        RAISE EXCEPTION 'Migration failed: % rows have unknown status', bad_count;
    END IF;
    RAISE NOTICE 'Migration OK: all existing rows pass the new constraint';
END $$;

COMMIT;

-- ────────────────────────────────────────────────────────────────────────────
-- AFTER THIS MIGRATION, you can also normalise legacy rows in the data:
-- Optional follow-up (NOT done automatically — run only if you want every
-- existing 'Angela QC' / 'Denver Approval' row to become 'Brand Manager QC'):
--
--   UPDATE public.planner_status
--      SET status = 'Brand Manager QC'
--    WHERE status IN ('Angela QC','Kelley QC','Denver Approval');
--
-- Once every row uses the new vocabulary AND every team browser has
-- reloaded once, you can tighten the CHECK by dropping the legacy keys:
--
--   ALTER TABLE public.planner_status
--       DROP CONSTRAINT planner_status_status_check;
--   ALTER TABLE public.planner_status
--       ADD CONSTRAINT planner_status_status_check
--       CHECK (status IN (
--           'Proposed','In Progress','Brand Manager QC',
--           'Scheduled','Published','Rejected'
--       ));
-- ────────────────────────────────────────────────────────────────────────────
