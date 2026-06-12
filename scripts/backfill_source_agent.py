"""
backfill_source_agent.py — one-shot backfill for orphan source_agent.

WHY
    28 actions in state/work-queue.json had source_agent set to None / '?' /
    empty string because the 6 rule emitters (gbp, social, membership, and
    the legacy seo / gads / meta) never set the field. The dashboard's
    Performance Review hit-rate-by-agent panel can't render rows it can't
    attribute.

    schema.to_jsonable() now derives source_agent from id prefix on every
    new write, so this script only needs to run once to fix the existing
    backlog.

WHAT IT DOES
    1. Load state/work-queue.json
    2. For each action with empty source_agent, derive from id prefix via
       schema.derive_source_agent()
    3. Save state file back
    4. PATCH every backfilled row in Supabase work_queue_actions
    5. Print summary

USAGE
    .venv/bin/python3.13 scripts/backfill_source_agent.py
    .venv/bin/python3.13 scripts/backfill_source_agent.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from work_queue.schema import derive_source_agent  # noqa: E402

STATE_FILE = BASE_DIR / "state" / "work-queue.json"

# Supabase secret key for PATCH (writable). Same credential the sync
# script uses. We use the publishable key first; if a row's RLS blocks the
# anon role, swap to SUPABASE_SECRET_KEY from .env.
SUPABASE_URL = "https://ckjwzwktuiavyfuolbgx.supabase.co"

_DOT_ENV = BASE_DIR / ".env"
if _DOT_ENV.exists():
    for line in _DOT_ENV.read_text().splitlines():
        if line.startswith("SUPABASE_SECRET_KEY="):
            os.environ["SUPABASE_SECRET_KEY"] = line.split("=", 1)[1].strip()
            break

SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY") or "sb_publishable_3giOfPJ92JW7DN8w9jPvoQ_cFo4rd0s"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change without writing state or Supabase.")
    args = p.parse_args()

    if not STATE_FILE.exists():
        print(f"[backfill] {STATE_FILE} not found — nothing to do")
        return 0

    wq = json.loads(STATE_FILE.read_text())
    actions = wq.get("actions") or []

    orphans = []
    for a in actions:
        cur = a.get("source_agent")
        if cur in (None, "", "?"):
            orphans.append(a)

    if not orphans:
        print("[backfill] No orphans found — nothing to do.")
        return 0

    print(f"[backfill] Found {len(orphans)} actions with missing source_agent")

    fixed = 0
    derived_by_kind: Counter[str] = Counter()
    unresolved: list[str] = []
    for a in orphans:
        aid = a.get("id") or ""
        derived = derive_source_agent(aid)
        if not derived:
            unresolved.append(aid)
            continue
        a["source_agent"] = derived
        derived_by_kind[derived] += 1
        fixed += 1

    print(f"[backfill] Derived source_agent for {fixed} / {len(orphans)}")
    for src, c in sorted(derived_by_kind.items(), key=lambda x: -x[1]):
        print(f"  · {src}: {c}")
    if unresolved:
        print(f"  ⚠️  {len(unresolved)} still unresolved (unknown id prefix):")
        for aid in unresolved[:5]:
            print(f"     {aid}")

    if args.dry_run:
        print("[backfill] --dry-run set — not writing state or Supabase")
        return 0

    # 1) Write state file
    STATE_FILE.write_text(json.dumps(wq, indent=2, default=str))
    print(f"[backfill] Wrote {STATE_FILE.relative_to(BASE_DIR)}")

    # 2) PATCH each row in Supabase
    print(f"[backfill] PATCHing {fixed} rows in Supabase...")
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }
    success = 0
    fail = 0
    for a in orphans:
        if a.get("source_agent") in (None, "", "?"):
            continue   # unresolved
        aid = a["id"]
        url = f"{SUPABASE_URL}/rest/v1/work_queue_actions?id=eq.{aid}"
        body = {"source_agent": a["source_agent"]}
        try:
            r = requests.patch(url, headers=headers, json=body, timeout=10)
            if r.status_code in (200, 204):
                success += 1
            else:
                fail += 1
                print(f"  ✗ {aid}: HTTP {r.status_code} — {r.text[:120]}")
        except Exception as e:
            fail += 1
            print(f"  ✗ {aid}: {e}")

    print(f"[backfill] Supabase: {success} updated, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
