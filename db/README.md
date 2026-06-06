# db/ — Supabase schema + RLS

This folder holds the SQL needed to rebuild the CB247 Supabase backend.

## Files

| File | Purpose |
|---|---|
| `schema.sql` | Three table DDLs + indexes + replica identity |
| `policies.sql` | RLS policies + realtime publication setup |

## How to apply (from scratch)

1. Create a new Supabase project (or reuse the existing
   `ckjwzwktuiavyfuolbgx` project).
2. Go to **Supabase Dashboard → SQL Editor → New Query**.
3. Paste `schema.sql`, click **Run**. You should see "Success. No rows
   returned." three times (one per table).
4. New Query → paste `policies.sql` → Run. Same success.
5. Verify in **Database → Tables**: you should see `planner_status`,
   `planner_approval`, `work_queue_actions`.
6. Verify in **Database → Replication → supabase_realtime**: all three
   tables should be in the publication.
7. Update the `SUPABASE_URL` and `SUPABASE_KEY` constants in:
   - `scripts/work_queue/sync_to_supabase.py`
   - `scripts/work_queue/measurement_runner.py`
   - `docs/index.html` (search for `_SUPABASE_URL`)

## How to update an existing schema

These SQL files are **idempotent** — `IF NOT EXISTS` clauses + `DROP
POLICY IF EXISTS` mean you can re-run them safely on a live database
without dropping data.

To add a new column:
1. Edit `schema.sql` to include the new column.
2. Write a one-off migration SQL with `ALTER TABLE ... ADD COLUMN IF
   NOT EXISTS ...` and run it in SQL Editor.
3. Update `schema.sql` so re-applying from scratch produces the same
   shape.

## Security note

RLS is configured so the anon role can do everything on all three
tables. That's intentional — the dashboard is client-side and uses the
publishable key. See policy comments in `policies.sql` for the threat
model and tightening options.

## When to rebuild

Realistically, you don't need to rebuild unless:
- The Supabase project is migrated to a new account
- The free tier runs out and you migrate to a paid plan with fresh
  project
- You want to spin up a staging environment for safe testing

In all three cases, apply these files to the new project, update the
constants in code, and you're back online.
