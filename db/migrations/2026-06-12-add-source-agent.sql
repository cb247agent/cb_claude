-- ─────────────────────────────────────────────────────────────────────────
-- Migration: add source_agent + parent_promo_id columns to work_queue_actions
-- Author: closed-loop completion, 12 Jun 2026
-- Why: source_agent is required for per-agent hit-rate tracking on the
--      Performance Review page. parent_promo_id was added to the Python
--      schema in Wave 5 (10 Jun 2026) but never propagated to the DB.
--      sync_to_supabase.py was silently dropping both fields.
-- Safety: ADD COLUMN IF NOT EXISTS is idempotent — safe to re-run.
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE public.work_queue_actions
    ADD COLUMN IF NOT EXISTS source_agent text;

ALTER TABLE public.work_queue_actions
    ADD COLUMN IF NOT EXISTS parent_promo_id text;

-- Index for per-agent hit-rate queries
CREATE INDEX IF NOT EXISTS idx_wqa_source_agent
    ON public.work_queue_actions (source_agent);

-- After running this, re-run scripts/backfill_source_agent.py to
-- populate source_agent on the 28 historical orphan rows.

COMMENT ON COLUMN public.work_queue_actions.source_agent IS
    'Emitter or LLM agent that produced this action. Examples: gbp-emitter, seo-strategist, opportunity-emitter. NULL not allowed for new rows by application convention (schema.derive_source_agent() auto-fills).';
COMMENT ON COLUMN public.work_queue_actions.parent_promo_id IS
    'When this action is a child deliverable of a parent promo concept (Wave 5), holds the promo id. Used for cascade rendering on the Asset Library page.';
