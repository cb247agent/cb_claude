"""
backfill_owner_roles.py — one-shot reassignment of action owners.

WHY
    Tia clarified team roles 12 Jun 2026:
      - Joanne: Meta Ads + Organic Social (TikTok/IG/FB) + QA
      - Angela: Brand Manager (only — no separate "Brand Manager" alias)
      - Denver: COO (approver, never an action owner)
      - Tia:    OS Owner, Google Ads
      - John:   SEO Specialist
      - Shauna: Asset Creator

    The state file + Supabase carry 82 actions emitted under the OLD
    convention:
      - meta_emitter actions went to Tia (should be Joanne)
      - social_emitter actions went to Shauna (should be Joanne)
      - qa-agent actions went to John/Tia (should be Joanne)
      - "Brand Manager" string used as owner (should be Angela + role)

    Emitters + strategist YAMLs have been patched for future runs. This
    script fixes the 82 existing rows.

WHAT IT DOES
    1. Load state/work-queue.json
    2. Apply owner reassignment rules per action (source_agent + category)
    3. Save state file
    4. PATCH each updated row in Supabase

USAGE
    .venv/bin/python3.13 scripts/backfill_owner_roles.py --dry-run
    .venv/bin/python3.13 scripts/backfill_owner_roles.py
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
STATE_FILE = BASE_DIR / "state" / "work-queue.json"

SUPABASE_URL = "https://ckjwzwktuiavyfuolbgx.supabase.co"
_DOT_ENV = BASE_DIR / ".env"
if _DOT_ENV.exists():
    for line in _DOT_ENV.read_text().splitlines():
        if line.startswith("SUPABASE_SECRET_KEY="):
            os.environ["SUPABASE_SECRET_KEY"] = line.split("=", 1)[1].strip()
            break
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY") or "sb_publishable_3giOfPJ92JW7DN8w9jPvoQ_cFo4rd0s"


def _new_owner(action: dict) -> tuple[str | None, str | None]:
    """Return (new_owner, new_owner_role) for this action, or (None, None)
    if no change is needed.

    Rule order matters — most specific wins:
      1. "Brand Manager" name → Angela + role (regardless of category)
      2. Meta-related actions → Joanne (Meta Ads Specialist)
      3. Organic social actions → Joanne (Organic Social)
      4. QA agent actions → Joanne (QA Specialist)
      5. SEO actions → John (already correct in most cases)
      6. GBP / Membership / Opportunity / Attribution actions → keep existing
    """
    cur_owner = (action.get("owner") or "").strip()
    cur_role = (action.get("owner_role") or "").strip()
    source_agent = (action.get("source_agent") or "").strip()
    source_page = (action.get("source_page") or "").strip()
    category = (action.get("category") or "").strip()

    # Rule 1 — Brand Manager string consolidation
    if cur_owner == "Brand Manager":
        return ("Angela", "Brand Manager")

    # Rule 2 — Meta ads
    if source_page == "meta-ads" or source_agent == "meta-strategist" or source_agent == "meta-emitter":
        if cur_owner != "Joanne" and cur_owner != "Shauna":
            # Tia, Angela, anyone else → Joanne (except Shauna who owns shoot)
            return ("Joanne", "Meta Ads Specialist")

    # Rule 3 — Organic social
    if source_page == "organic-social" or source_agent == "social-emitter":
        # Shauna actions stay only if they're new-asset creation (rare).
        # In current data, social-emitter put EVERYTHING on Shauna which is
        # wrong — switch to Joanne by default. Keep Shauna only if explicit
        # asset shoot brief.
        if "shoot" in (action.get("title") or "").lower() and cur_owner == "Shauna":
            return (None, None)  # genuine shoot action — keep Shauna
        if cur_owner != "Joanne":
            return ("Joanne", "Organic Social")

    # Rule 4 — QA agent
    if source_agent == "qa-agent":
        if cur_owner != "Joanne":
            return ("Joanne", "QA Specialist")

    # Rule 5 — Google Ads stays with Tia (no change needed — strategist
    # already assigns correctly)
    # Rule 6 — SEO stays with John (no change needed)
    # Rule 7 — GBP / Membership / Opportunity / Attribution stay with current

    return (None, None)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change without writing state or Supabase.")
    args = p.parse_args()

    if not STATE_FILE.exists():
        print(f"[backfill-owners] {STATE_FILE} not found — nothing to do")
        return 0

    wq = json.loads(STATE_FILE.read_text())
    actions = wq.get("actions") or []

    changes: list[tuple[str, str, str, str, str]] = []
    transitions: Counter[str] = Counter()
    for a in actions:
        new_owner, new_role = _new_owner(a)
        if new_owner is None:
            continue
        old_owner = (a.get("owner") or "?").strip()
        old_role = (a.get("owner_role") or "").strip()
        changes.append((a["id"], old_owner, old_role, new_owner, new_role))
        transitions[f"{old_owner} → {new_owner}"] += 1
        # Apply in-memory
        a["owner"] = new_owner
        a["owner_role"] = new_role

    if not changes:
        print("[backfill-owners] No actions need reassignment.")
        return 0

    print(f"[backfill-owners] {len(changes)} actions need reassignment:")
    for old_to_new, n in sorted(transitions.items(), key=lambda x: -x[1]):
        print(f"  · {old_to_new}: {n}")

    if args.dry_run:
        print("\n[backfill-owners] --dry-run set — no writes. Sample changes:")
        for (aid, oo, orl, no, nr) in changes[:6]:
            print(f"  {aid}: {oo!r} ({orl!r}) → {no!r} ({nr!r})")
        return 0

    # Write state file
    STATE_FILE.write_text(json.dumps(wq, indent=2, default=str))
    print(f"\n[backfill-owners] Wrote {STATE_FILE.relative_to(BASE_DIR)}")

    # PATCH each row in Supabase
    print(f"[backfill-owners] PATCHing {len(changes)} rows in Supabase...")
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }
    success, fail = 0, 0
    for (aid, oo, orl, no, nr) in changes:
        url = f"{SUPABASE_URL}/rest/v1/work_queue_actions?id=eq.{aid}"
        body = {"owner": no, "owner_role": nr}
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

    print(f"[backfill-owners] Supabase: {success} updated, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
