-- ────────────────────────────────────────────────────────────────────────────
-- Migration: Add draft_link column to work_queue_actions
-- Date: 11 Jun 2026
-- ────────────────────────────────────────────────────────────────────────────
--
-- WHY THIS MIGRATION EXISTS
-- ------------------------------------------------------------------------
-- Tia screenshot of "Improve organic content for 'gym ellenbrook perth'"
-- modal asked: "where is the blog draft?". Emitter rows surface the
-- opportunity (do this, here's why, here's the KPI) but have nowhere
-- to attach the actual draft artifact. PLANNER_ITEMS templates already
-- carry a `draftLink` field pointing to docs/blog-drafts/{slug}.html —
-- emitter rows need the same.
--
-- This column stores a URL (GitHub Pages blog-drafts, Google Doc,
-- Webflow draft, WordPress draft, etc.). The dashboard:
--   1. Auto-attaches a draft when the action's title slug matches a file
--      in docs/blog-drafts/ (via BLOG_DRAFTS_INDEX written by
--      scripts/inject-blog-drafts-index.py)
--   2. Lets the owner paste a draft URL in the modal once writing
--      starts — persists here, visible to whole team via Supabase
--
-- The column is nullable: ops actions never have a draft_link, and
-- content actions can be unfilled until the writer attaches one.
--
-- WHAT TO RUN
-- ------------------------------------------------------------------------
-- Paste this whole file into Supabase Dashboard → SQL Editor → Run.
-- Idempotent: ADD COLUMN IF NOT EXISTS. Safe to re-run.
-- ────────────────────────────────────────────────────────────────────────────

BEGIN;

ALTER TABLE public.work_queue_actions
    ADD COLUMN IF NOT EXISTS draft_link text;

COMMENT ON COLUMN public.work_queue_actions.draft_link IS
    'Optional URL to the draft artifact for content actions — Google Doc, '
    'GitHub Pages blog-drafts file, Webflow draft, WordPress draft. Set by '
    'the dashboard either via auto-scan (BLOG_DRAFTS_INDEX) or owner paste. '
    'Null for ops actions and content actions that haven''t been drafted yet.';

COMMIT;

-- ────────────────────────────────────────────────────────────────────────────
-- VERIFICATION
-- ────────────────────────────────────────────────────────────────────────────
-- After running this, the column should be visible:
--   SELECT column_name, data_type, is_nullable
--   FROM information_schema.columns
--   WHERE table_name = 'work_queue_actions' AND column_name = 'draft_link';
--
-- Expected output:
--   column_name | data_type | is_nullable
--   draft_link  | text      | YES
-- ────────────────────────────────────────────────────────────────────────────
