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


def _patch_to_supabase(rows: list) -> int:
    """PATCH source_agent (and parent_promo_id if present) on each row.
    Returns 0 if all succeeded, 1 if any failed."""
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }
    success, fail = 0, 0
    for a in rows:
        aid = a.get("id")
        if not aid:
            fail += 1
            continue
        body = {}
        if a.get("source_agent"):
            body["source_agent"] = a["source_agent"]
        if a.get("parent_promo_id"):
            body["parent_promo_id"] = a["parent_promo_id"]
        if not body:
            continue
        url = f"{SUPABASE_URL}/rest/v1/work_queue_actions?id=eq.{aid}"
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change without writing state or Supabase.")
    p.add_argument("--push-all", action="store_true",
                   help="PATCH every action's source_agent in Supabase, not just "
                        "state-file orphans. Use this after applying the SQL "
                        "migration when state is already clean but Supabase rows "
                        "are still missing source_agent.")
    args = p.parse_args()

    if not STATE_FILE.exists():
        print(f"[backfill] {STATE_FILE} not found — nothing to do")
        return 0

    wq = json.loads(STATE_FILE.read_text())
    actions = wq.get("actions") or []

    if args.push_all:
        # Push every action that HAS a source_agent in state to Supabase. No
        # derivation needed — state is already clean — we're just pushing the
        # known values to columns that didn't exist on prior sync attempts.
        orphans = [a for a in actions if a.get("source_agent")]
        print(f"[backfill] --push-all set — will PATCH all {len(orphans)} actions")
        if args.dry_run:
            print("[backfill] --dry-run set — exiting before PATCH")
            return 0
        return _patch_to_supabase(orphans)

    orphans = []
    for a in actions:
        cur = a.get("source_agent")
        if cur in (None, "", "?"):
            orphans.append(a)

    if not orphans:
        print("[backfill] No orphans found — nothing to do.")
        print("[backfill] Hint: state may already be clean while Supabase isn't.")
        print("[backfill] Run with --push-all to PATCH Supabase from state.")
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
    return _patch_to_supabase(orphans)


if __name__ == "__main__":
    raise SystemExit(main())
