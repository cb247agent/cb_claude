-- ────────────────────────────────────────────────────────────────────────────
-- Migration: promo_pipeline_state table — team's stage overrides on AI-proposed
--            promo concepts. Drives Path B's campaign-launch-strategist trigger.
-- Date: 13 Jun 2026
-- ────────────────────────────────────────────────────────────────────────────
--
-- WHY THIS MIGRATION EXISTS
-- ------------------------------------------------------------------------
-- Path B introduces a "performance-marketer" agent (campaign-launch-
-- strategist) that writes full Meta + Google media plans for promo
-- concepts. The trigger is: when Angela marks a concept "Approved" in the
-- Promo Pipeline dashboard, the daily phase1b_promo_launch.sh script picks
-- it up next morning and fires the strategist.
--
-- Before this migration, promo concepts existed only in
-- state/promo-pipeline.json (read-only from the dashboard's perspective).
-- The Promo Pipeline modal had a "Close" button but NO Approve/Reject/
-- Send-back-to-Concept buttons. To approve a concept, someone had to
-- manually edit the JSON file.
--
-- This table mirrors the work_queue planner_status pattern:
--   - Supabase is source of truth for stage transitions
--   - Realtime broadcasts so multiple browsers stay in sync
--   - JSON file (state/promo-pipeline.json) is the strategist's proposal;
--     Supabase row is the team's decision. Team's decision always wins.
--
-- WHAT TO RUN
-- ------------------------------------------------------------------------
-- Paste this whole file into Supabase Dashboard → SQL Editor → Run.
-- Idempotent: uses CREATE TABLE IF NOT EXISTS + idempotent RLS / publication.
--
-- After this lands, the dashboard's openPromoDetailModal exposes contextual
-- Approve / Reject / Send-back buttons that upsert into promo_pipeline_state.
-- phase1b_promo_launch.sh (cron'd daily 4am AWST) reads this table to
-- decide which concepts need a media plan.
-- ────────────────────────────────────────────────────────────────────────────

BEGIN;

-- ── 1. Table ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS promo_pipeline_state (
    id text PRIMARY KEY,                       -- concept id, e.g. promo-kids-hub-2026-06
    stage text NOT NULL CHECK (stage IN (
        'Concept',
        'Approved',
        'Asset Shoot Scheduled',
        'In Production',
        'Active',
        'Performance Review',
        'Rejected'
    )),
    notes text,                                -- e.g. rejection reason
    updated_by text,                           -- "Angela", "Denver", etc.
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE promo_pipeline_state IS
    'Team''s stage overrides on AI-proposed promo concepts. Source of truth for kanban + campaign-launch trigger. Synced realtime to all open dashboards. JSON file state/promo-pipeline.json is the AI proposal; this table is the team''s decision.';

-- ── 2. Auto-update trigger ──────────────────────────────────────────────
-- Reuse the same trigger function planner_status uses (created in db/schema.sql).
-- If the function doesn't exist (fresh project), create it here.
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS promo_pipeline_state_updated_at ON promo_pipeline_state;
CREATE TRIGGER promo_pipeline_state_updated_at
    BEFORE UPDATE ON promo_pipeline_state
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- ── 3. RLS — same pattern as planner_status (anon role full access) ─────
ALTER TABLE promo_pipeline_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anon read promo_pipeline_state"   ON promo_pipeline_state;
DROP POLICY IF EXISTS "Anon insert promo_pipeline_state" ON promo_pipeline_state;
DROP POLICY IF EXISTS "Anon update promo_pipeline_state" ON promo_pipeline_state;
DROP POLICY IF EXISTS "Anon delete promo_pipeline_state" ON promo_pipeline_state;

CREATE POLICY "Anon read promo_pipeline_state"
    ON promo_pipeline_state FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "Anon insert promo_pipeline_state"
    ON promo_pipeline_state FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "Anon update promo_pipeline_state"
    ON promo_pipeline_state FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Anon delete promo_pipeline_state"
    ON promo_pipeline_state FOR DELETE
    TO anon
    USING (true);

-- ── 4. REPLICA IDENTITY FULL — required for realtime postgres_changes ──
ALTER TABLE promo_pipeline_state REPLICA IDENTITY FULL;

-- ── 5. Add to realtime publication ──────────────────────────────────────
-- The supabase_realtime publication may or may not exist yet (depends on
-- whether realtime is already enabled). The DO block handles both cases.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE promo_pipeline_state;
        EXCEPTION
            WHEN duplicate_object THEN
                -- Already in the publication — fine
                NULL;
        END;
    END IF;
END $$;

COMMIT;

-- ── Verification queries — run these AFTER the migration to confirm ────
-- SELECT * FROM promo_pipeline_state;        -- Should be empty, table exists
-- INSERT INTO promo_pipeline_state (id, stage, updated_by)
--   VALUES ('test-promo-2026-06', 'Approved', 'tia-smoke-test');
-- SELECT id, stage, updated_at FROM promo_pipeline_state;
-- DELETE FROM promo_pipeline_state WHERE id = 'test-promo-2026-06';
