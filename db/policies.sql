-- ────────────────────────────────────────────────────────────────────────────
-- CB247 Marketing OS — Row Level Security policies
-- Apply AFTER db/schema.sql via Supabase Dashboard → SQL Editor.
--
-- Security model:
--   The dashboard is a static client-side HTML page deployed to GitHub Pages.
--   It uses the publishable (anon) key embedded in docs/index.html.
--   RLS is the ONLY protection layer between random visitors and the data.
--
--   Anon role is granted SELECT + INSERT + UPDATE + DELETE on all three
--   tables. That's intentional — the team operates the dashboard via the
--   anon role.
--
--   IMPORTANT: anyone with the URL can read + write these tables. We
--   accept that risk because:
--     1. No PII stored
--     2. No financial data stored
--     3. Vandalism is recoverable from daily Supabase backups
--     4. Adding auth would require a login flow the team finds friction
--
--   If you ever need to tighten this:
--     - Add Supabase Auth + email-based access
--     - Replace `using (true)` with `using (auth.uid() IS NOT NULL)`
--     - Restrict updated_by to match auth.email()
-- ────────────────────────────────────────────────────────────────────────────


-- ────────────────────────────────────────────────────────────────────────────
-- planner_status policies
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.planner_status ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "planner_status_select" ON public.planner_status;
CREATE POLICY "planner_status_select" ON public.planner_status
    FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "planner_status_insert" ON public.planner_status;
CREATE POLICY "planner_status_insert" ON public.planner_status
    FOR INSERT TO anon WITH CHECK (true);

DROP POLICY IF EXISTS "planner_status_update" ON public.planner_status;
CREATE POLICY "planner_status_update" ON public.planner_status
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "planner_status_delete" ON public.planner_status;
CREATE POLICY "planner_status_delete" ON public.planner_status
    FOR DELETE TO anon USING (true);


-- ────────────────────────────────────────────────────────────────────────────
-- planner_approval policies
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.planner_approval ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "planner_approval_select" ON public.planner_approval;
CREATE POLICY "planner_approval_select" ON public.planner_approval
    FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "planner_approval_insert" ON public.planner_approval;
CREATE POLICY "planner_approval_insert" ON public.planner_approval
    FOR INSERT TO anon WITH CHECK (true);

DROP POLICY IF EXISTS "planner_approval_update" ON public.planner_approval;
CREATE POLICY "planner_approval_update" ON public.planner_approval
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "planner_approval_delete" ON public.planner_approval;
CREATE POLICY "planner_approval_delete" ON public.planner_approval
    FOR DELETE TO anon USING (true);


-- ────────────────────────────────────────────────────────────────────────────
-- work_queue_actions policies
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.work_queue_actions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "work_queue_actions_select" ON public.work_queue_actions;
CREATE POLICY "work_queue_actions_select" ON public.work_queue_actions
    FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "work_queue_actions_insert" ON public.work_queue_actions;
CREATE POLICY "work_queue_actions_insert" ON public.work_queue_actions
    FOR INSERT TO anon WITH CHECK (true);

DROP POLICY IF EXISTS "work_queue_actions_update" ON public.work_queue_actions;
CREATE POLICY "work_queue_actions_update" ON public.work_queue_actions
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "work_queue_actions_delete" ON public.work_queue_actions;
CREATE POLICY "work_queue_actions_delete" ON public.work_queue_actions
    FOR DELETE TO anon USING (true);


-- ────────────────────────────────────────────────────────────────────────────
-- Realtime publication setup
-- ────────────────────────────────────────────────────────────────────────────
-- The dashboard subscribes to postgres_changes on all three tables.
-- Add them to the supabase_realtime publication so events broadcast.
-- (Replica identity full is set in schema.sql.)
--
-- These are idempotent — running again is safe.

ALTER PUBLICATION supabase_realtime ADD TABLE public.planner_status;
ALTER PUBLICATION supabase_realtime ADD TABLE public.planner_approval;
ALTER PUBLICATION supabase_realtime ADD TABLE public.work_queue_actions;
