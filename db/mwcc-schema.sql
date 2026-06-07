-- ────────────────────────────────────────────────────────────────────────────
-- MWCC (My World Childcare) Supabase schema
-- Apply via Supabase Dashboard → SQL Editor → New Query → paste + Run.
--
-- Mirrors db/schema.sql exactly but with mwcc_ prefix on every table.
-- This gives clean isolation from CB247 data — no query that targets
-- the wrong prefix can accidentally mix businesses.
--
-- Apply order:
--   1. This file (mwcc-schema.sql)
--   2. db/mwcc-policies.sql (RLS + realtime publication)
--
-- Both files are idempotent (IF NOT EXISTS) so safe to re-run.
-- ────────────────────────────────────────────────────────────────────────────


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 1: mwcc_planner_status
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.mwcc_planner_status (
    item_id      text PRIMARY KEY,
    status       text NOT NULL DEFAULT 'Idea'
                 CHECK (status IN (
                     'Idea',
                     'In Progress',
                     'Kelley QC',
                     'Denver Approval',
                     'Scheduled',
                     'Published'
                 )),
    updated_by   text,
    updated_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.mwcc_planner_status REPLICA IDENTITY FULL;

COMMENT ON TABLE public.mwcc_planner_status IS
    'Kanban stage for each MWCC Work Queue item. Mirrors CB247 pattern with Kelley QC instead of Angela QC.';


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 2: mwcc_planner_approval
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.mwcc_planner_approval (
    item_id      text PRIMARY KEY,
    decision     text NOT NULL DEFAULT 'pending'
                 CHECK (decision IN (
                     'approved',
                     'adjusted',
                     'rejected',
                     'pending'
                 )),
    notes        text DEFAULT '',
    updated_by   text,
    updated_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.mwcc_planner_approval REPLICA IDENTITY FULL;

COMMENT ON TABLE public.mwcc_planner_approval IS
    'Approval decisions per MWCC Work Queue item.';


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 3: mwcc_work_queue_actions
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.mwcc_work_queue_actions (
    id               text PRIMARY KEY,
    source_page      text NOT NULL
                     CHECK (source_page IN (
                         'seo-organic',
                         'meta-ads',
                         'google-ads',
                         'enrolment',
                         'overview'
                     )),
    source_run_at    timestamptz NOT NULL,

    title            text NOT NULL,
    description      text NOT NULL DEFAULT '',
    owner            text,
    owner_role       text,
    priority         text NOT NULL DEFAULT 'P2'
                     CHECK (priority IN ('P1', 'P2', 'P3')),
    effort_hours     numeric(5,2),
    category         text,
    data_quality     text NOT NULL DEFAULT 'medium'
                     CHECK (data_quality IN ('high', 'medium', 'low')),

    projected_kpis   jsonb NOT NULL DEFAULT '[]'::jsonb,

    urgent           boolean NOT NULL DEFAULT false,
    related_actions  jsonb NOT NULL DEFAULT '[]'::jsonb,

    actual_kpis      jsonb,
    overall_verdict  text
                     CHECK (overall_verdict IN (
                         'winner',
                         'partial_win',
                         'no_change',
                         'underperforming',
                         'pending'
                     )),
    measured_at      timestamptz,

    notes_human      text NOT NULL DEFAULT '',

    updated_at       timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.mwcc_work_queue_actions REPLICA IDENTITY FULL;

CREATE INDEX IF NOT EXISTS idx_mwcc_wqa_source_page ON public.mwcc_work_queue_actions (source_page);
CREATE INDEX IF NOT EXISTS idx_mwcc_wqa_priority    ON public.mwcc_work_queue_actions (priority);
CREATE INDEX IF NOT EXISTS idx_mwcc_wqa_unmeasured  ON public.mwcc_work_queue_actions (id)
    WHERE actual_kpis IS NULL;

COMMENT ON TABLE public.mwcc_work_queue_actions IS
    'Typed action recommendations emitted weekly by scripts/work_queue/mwcc_*_emitter.py';
COMMENT ON COLUMN public.mwcc_work_queue_actions.source_page IS
    'enrolment is MWCC-specific (replaces CB247 membership). Other values shared with CB247.';
