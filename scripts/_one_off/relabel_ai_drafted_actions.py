"""
relabel_ai_drafted_actions.py — one-off retitle of promo-concept-emitter actions.

WHY THIS EXISTS (13 Jun 2026)
    Before today's Path B, humans drafted EDM bodies + SMS variants + save-
    call playbooks + meta ad copy from scratch. The promo_concept_emitter's
    verb map reflected that: "Draft + send", "Write + train team", "Draft +
    launch".

    Path B introduced deliverable-drafter + playbook-writer + campaign-
    launch-strategist — all of which now pre-draft those deliverables. The
    human's actual job became Review + tweak + approve + execute. The OLD
    titles still in state/work-queue.json mislead Angela and Joanne into
    thinking they need to draft from scratch.

    This one-off script:
      1. Reads state/work-queue.json
      2. Finds every promo-concept-emitter action (id prefix promo-)
      3. Updates the title verb per the new map (matching the strategist
         YAML at agents/promo-concept-strategist.yml)
      4. Writes back, then runs scripts/work_queue/sync_to_supabase.py so
         the dashboard reflects the change immediately.

    Idempotent — re-running on already-relabelled actions is a no-op.

USAGE
    python3 scripts/_one_off/relabel_ai_drafted_actions.py
    python3 scripts/_one_off/relabel_ai_drafted_actions.py --dry-run

ARCHIVE
    After Tia confirms the change looks right on the dashboard, delete this
    script. It's a one-time migration, not a recurring tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORK_QUEUE = BASE_DIR / "state" / "work-queue.json"

# Match the updated verb map in agents/promo-concept-strategist.yml.
# Key = id prefix (first 9 chars per emitter's f"promo-{fmt[:3]}" pattern).
# Value = (old verb to find, new verb to substitute).
RENAME_MAP = {
    "promo-edm": ("Draft + send",      "Review + send"),
    "promo-sms": ("Draft + send",      "Review + send"),
    "promo-ree": ("Capture + post",    "Caption-review + capture + post"),
    "promo-sto": ("Capture + post",    "Caption-review + capture + post"),
    "promo-sav": ("Write + train team", "Review + train team"),
    "promo-met": ("Draft + launch",    "Review + launch"),
    # promo-lan (landing_page) intentionally NOT in the map — title stays
    # "Build + publish" because John still writes the page from scratch.
}


def _relabel_item(item: dict, dry_run: bool) -> tuple[bool, str | None]:
    """Apply the verb rename. Returns (changed, old_title_or_None)."""
    if not isinstance(item, dict):
        return False, None
    item_id = item.get("id") or ""
    if not item_id.startswith("promo-"):
        return False, None

    # Extract prefix — promo-edm-act-... → promo-edm
    prefix = item_id.rsplit("-act-", 1)[0]
    rename = RENAME_MAP.get(prefix)
    if rename is None:
        return False, None  # promo-lan or unknown

    old_verb, new_verb = rename
    title = item.get("title") or ""
    if old_verb not in title:
        return False, None  # already relabelled or never matched (idempotent)

    new_title = title.replace(old_verb, new_verb, 1)
    if not dry_run:
        item["title"] = new_title
    return True, title


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = p.parse_args()

    if not WORK_QUEUE.exists():
        print(f"[relabel] {WORK_QUEUE} not found", file=sys.stderr)
        return 1

    raw = json.loads(WORK_QUEUE.read_text())
    items = raw if isinstance(raw, list) else raw.get("items") or raw.get("actions") or []
    if not items:
        print("[relabel] work-queue is empty — nothing to do")
        return 0

    changed_count = 0
    for it in items:
        did, old = _relabel_item(it, args.dry_run)
        if did:
            changed_count += 1
            print(f"  • {it.get('id')}")
            print(f"    -  {old}")
            print(f"    +  {it.get('title')}")

    print()
    print(f"[relabel] {'WOULD UPDATE' if args.dry_run else 'UPDATED'} {changed_count} action(s) of {len(items)} total")

    if args.dry_run:
        return 0

    if changed_count == 0:
        print("[relabel] No changes — work-queue.json untouched")
        return 0

    # Persist — BUG fix 13 Jun 2026: state/work-queue.json carries BOTH
    # "items" and "actions" lists (historical schema duplication). The
    # sync_to_supabase.py reads from "actions". The original write logic
    # used elif which only updated one key — leaving Supabase stale.
    # Now we update EVERY list key that's present in the source dict.
    if isinstance(raw, list):
        WORK_QUEUE.write_text(json.dumps(items, indent=2))
    else:
        for k in ("items", "actions"):
            if k in raw:
                raw[k] = items
        WORK_QUEUE.write_text(json.dumps(raw, indent=2))

    print(f"[relabel] Wrote state/work-queue.json — run scripts/work_queue/sync_to_supabase.py next")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
