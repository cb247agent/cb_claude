-- ────────────────────────────────────────────────────────────────────────────
-- CB247 Marketing OS — Supabase schema
-- Apply via Supabase Dashboard → SQL Editor → New Query → paste + Run.
--
-- Three tables back the closed-loop work flow:
--   1. planner_status     — what stage each item is in
--   2. planner_approval   — per-item approval decisions + notes
--   3. work_queue_actions — typed actions emitted by Layer 4 emitters
--
-- All tables use REPLICA IDENTITY FULL so Supabase realtime broadcasts
-- include the full row data (required for postgres_changes events).
--
-- RLS policies are in db/policies.sql — apply that file AFTER this one.
--
-- To rebuild from scratch:
--   1. (optional) DROP TABLE … if you're starting clean
--   2. Run this file in SQL Editor
--   3. Run db/policies.sql in SQL Editor
--   4. Run db/realtime.sql in SQL Editor (publication setup)
-- ────────────────────────────────────────────────────────────────────────────


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 1: planner_status
-- ────────────────────────────────────────────────────────────────────────────
-- One row per item. Tracks which Kanban stage it's currently in.
-- item_id is shared across PLANNER_ITEMS (content) and work_queue_actions
-- (operational actions) — they live in the same id space.

CREATE TABLE IF NOT EXISTS public.planner_status (
    item_id      text PRIMARY KEY,
    status       text NOT NULL DEFAULT 'Proposed'
                 -- Wave 1 (10 Jun 2026) renamed stages. Legacy keys are
                 -- kept in the allow-list until every team browser cycles.
                 -- Migration: db/migrations/2026-06-10-kanban-stages-check.sql
                 CHECK (status IN (
                     'Proposed',         -- was 'Idea'
                     'In Progress',
                     'Brand Manager QC', -- merged Angela QC + Denver Approval
                     'Scheduled',
                     'Published',
                     'Rejected',         -- new (hidden column)
                     -- Legacy (kept for in-flight rows from old browsers)
                     'Idea',
                     'Angela QC',
                     'Kelley QC',
                     'Denver Approval'
                 )),
    updated_by   text,                          -- identity from "Who am I?" picker
    updated_at   timestamptz NOT NULL DEFAULT now()
);

-- Realtime broadcasts need full row data on UPDATE
ALTER TABLE public.planner_status REPLICA IDENTITY FULL;

COMMENT ON TABLE public.planner_status IS
    'Kanban stage for each Work Queue item. Synced realtime to all open dashboards.';
COMMENT ON COLUMN public.planner_status.item_id IS
    'Shared id space — content items (p1, p2, ...) and emitted actions (seo-act-2026w23-001, ...)';


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 2: planner_approval
-- ────────────────────────────────────────────────────────────────────────────
-- One row per item with an approval decision recorded. Captures Angela's
-- brand QC + Denver's COO sign-off + any rejection notes.

CREATE TABLE IF NOT EXISTS public.planner_approval (
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

ALTER TABLE public.planner_approval REPLICA IDENTITY FULL;

COMMENT ON TABLE public.planner_approval IS
    'Approval decisions per Work Queue item. Stage = planner_status; decision = planner_approval.';


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 3: work_queue_actions
-- ────────────────────────────────────────────────────────────────────────────
-- The Layer 4 emitter output. One row per typed action.
-- Mirrors the WorkQueueAction dataclass in scripts/work_queue/schema.py.

CREATE TABLE IF NOT EXISTS public.work_queue_actions (
    -- ── Identity ─────────────────────────────────────────────────────────
    id               text PRIMARY KEY,           -- e.g. seo-act-2026w23-001
    source_page      text NOT NULL
                     CHECK (source_page IN (
                         'seo-organic',
                         'meta-ads',
                         'google-ads',
                         'gbp',
                         'organic-social',
                         'membership',
                         'overview'
                     )),
    source_run_at    timestamptz NOT NULL,

    -- ── Display ──────────────────────────────────────────────────────────
    title            text NOT NULL,
    description      text NOT NULL DEFAULT '',
    owner            text,                       -- e.g. 'John', 'Angela'
    owner_role       text,
    priority         text NOT NULL DEFAULT 'P2'
                     CHECK (priority IN ('P1', 'P2', 'P3')),
    effort_hours     numeric(5,2),
    category         text,                       -- UI badge — seo / meta / gbp / etc.
    data_quality     text NOT NULL DEFAULT 'medium'
                     CHECK (data_quality IN ('high', 'medium', 'low')),

    -- ── Projection (filled at emit time) ─────────────────────────────────
    -- JSONB array of ProjectedKPI objects:
    --   [{metric, keyword?, keyword_pattern?, baseline?, target?,
    --     delta_min?, delta_max?, measurement_window_days, confidence?}, ...]
    projected_kpis   jsonb NOT NULL DEFAULT '[]'::jsonb,

    -- ── Flags ────────────────────────────────────────────────────────────
    urgent           boolean NOT NULL DEFAULT false,
    related_actions  jsonb NOT NULL DEFAULT '[]'::jsonb,

    -- ── Measurement (filled by measurement_runner.py) ────────────────────
    -- JSONB array of ActualKPI objects:
    --   [{metric, keyword?, baseline, target?, actual, delta?,
    --     target_hit?, status}, ...]
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

    -- ── Human input ──────────────────────────────────────────────────────
    notes_human      text NOT NULL DEFAULT '',

    -- ── Audit ────────────────────────────────────────────────────────────
    updated_at       timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.work_queue_actions REPLICA IDENTITY FULL;

-- Indexes for the common query shapes
CREATE INDEX IF NOT EXISTS idx_wqa_source_page ON public.work_queue_actions (source_page);
CREATE INDEX IF NOT EXISTS idx_wqa_priority    ON public.work_queue_actions (priority);
CREATE INDEX IF NOT EXISTS idx_wqa_unmeasured  ON public.work_queue_actions (id)
    WHERE actual_kpis IS NULL;

COMMENT ON TABLE public.work_queue_actions IS
    'Typed action recommendations emitted weekly by scripts/work_queue/*_emitter.py';
COMMENT ON COLUMN public.work_queue_actions.projected_kpis IS
    'JSONB array of {metric, baseline, target, measurement_window_days, ...} — see scripts/work_queue/schema.py';
COMMENT ON COLUMN public.work_queue_actions.actual_kpis IS
    'NULL until measurement_runner.py resolves the action post-window';
