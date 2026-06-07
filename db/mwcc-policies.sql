-- ────────────────────────────────────────────────────────────────────────────
-- MWCC (My World Childcare) Row Level Security policies
-- Apply AFTER db/mwcc-schema.sql via Supabase Dashboard → SQL Editor.
--
-- Same security model as CB247 — anon role granted full CRUD on all three
-- mwcc_* tables. RLS is the only protection layer between random visitors
-- and the data. Acceptable because:
--   1. No PII stored
--   2. No financial data stored
--   3. Vandalism recoverable from Supabase backups
--
-- To tighten: add Supabase Auth, replace `using (true)` with
-- `using (auth.uid() IS NOT NULL)`.
-- ────────────────────────────────────────────────────────────────────────────


-- ────────────────────────────────────────────────────────────────────────────
-- mwcc_planner_status policies
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.mwcc_planner_status ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "mwcc_planner_status_select" ON public.mwcc_planner_status;
CREATE POLICY "mwcc_planner_status_select" ON public.mwcc_planner_status
    FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "mwcc_planner_status_insert" ON public.mwcc_planner_status;
CREATE POLICY "mwcc_planner_status_insert" ON public.mwcc_planner_status
    FOR INSERT TO anon WITH CHECK (true);

DROP POLICY IF EXISTS "mwcc_planner_status_update" ON public.mwcc_planner_status;
CREATE POLICY "mwcc_planner_status_update" ON public.mwcc_planner_status
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "mwcc_planner_status_delete" ON public.mwcc_planner_status;
CREATE POLICY "mwcc_planner_status_delete" ON public.mwcc_planner_status
    FOR DELETE TO anon USING (true);


-- ────────────────────────────────────────────────────────────────────────────
-- mwcc_planner_approval policies
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.mwcc_planner_approval ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "mwcc_planner_approval_select" ON public.mwcc_planner_approval;
CREATE POLICY "mwcc_planner_approval_select" ON public.mwcc_planner_approval
    FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "mwcc_planner_approval_insert" ON public.mwcc_planner_approval;
CREATE POLICY "mwcc_planner_approval_insert" ON public.mwcc_planner_approval
    FOR INSERT TO anon WITH CHECK (true);

DROP POLICY IF EXISTS "mwcc_planner_approval_update" ON public.mwcc_planner_approval;
CREATE POLICY "mwcc_planner_approval_update" ON public.mwcc_planner_approval
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "mwcc_planner_approval_delete" ON public.mwcc_planner_approval;
CREATE POLICY "mwcc_planner_approval_delete" ON public.mwcc_planner_approval
    FOR DELETE TO anon USING (true);


-- ────────────────────────────────────────────────────────────────────────────
-- mwcc_work_queue_actions policies
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.mwcc_work_queue_actions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "mwcc_work_queue_actions_select" ON public.mwcc_work_queue_actions;
CREATE POLICY "mwcc_work_queue_actions_select" ON public.mwcc_work_queue_actions
    FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "mwcc_work_queue_actions_insert" ON public.mwcc_work_queue_actions;
CREATE POLICY "mwcc_work_queue_actions_insert" ON public.mwcc_work_queue_actions
    FOR INSERT TO anon WITH CHECK (true);

DROP POLICY IF EXISTS "mwcc_work_queue_actions_update" ON public.mwcc_work_queue_actions;
CREATE POLICY "mwcc_work_queue_actions_update" ON public.mwcc_work_queue_actions
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "mwcc_work_queue_actions_delete" ON public.mwcc_work_queue_actions;
CREATE POLICY "mwcc_work_queue_actions_delete" ON public.mwcc_work_queue_actions
    FOR DELETE TO anon USING (true);


-- ────────────────────────────────────────────────────────────────────────────
-- Realtime publication
-- ────────────────────────────────────────────────────────────────────────────
ALTER PUBLICATION supabase_realtime ADD TABLE public.mwcc_planner_status;
ALTER PUBLICATION supabase_realtime ADD TABLE public.mwcc_planner_approval;
ALTER PUBLICATION supabase_realtime ADD TABLE public.mwcc_work_queue_actions;
