"""
extract_promo_strategist_output.py — parse promo-concept-strategist output.

The promo-concept-strategist (agents/promo-concept-strategist.yml) writes a
markdown report with TWO fenced JSON blocks at the end:

    ```json proposed_promos
    {"acquisition": [ ... ], "retention": [ ... ]}
    ```

    ```json proposed_actions
    [ ... child WorkQueueAction objects ... ]
    ```

This script:
  1. Reads the markdown file
  2. Extracts both blocks
  3. Merges proposed_promos into state/promo-pipeline.json (preserving
     in-flight concepts past "Concept" stage — see _merge_promo_pipeline)
  4. Appends proposed_actions to state/work-queue.json (idempotent by id —
     same logic as existing emitters)
  5. Logs counts of inserted vs skipped vs preserved items

Runs in scripts/phases/phase1_data.sh as Step 1h0promo.2 immediately after
promo-concept-strategist completes. Monthly cadence (only fires when promo-
concept-strategist fires).

Usage:
    python3 scripts/work_queue/extract_promo_strategist_output.py \\
        --input outputs/promo-strategist/promo-strategist-2026-07-01.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parent.parent))

BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
PROMO_FILE = STATE_DIR / "promo-pipeline.json"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

# Stages that mean a concept is past "just an idea" — preserve these against
# being overwritten by a new strategist run on the same concept id.
DOWNSTREAM_STAGES = {
    "Approved", "Asset Shoot Scheduled", "In Production",
    "Active", "Performance Review",
}

# Same fenced-block extractor pattern as scripts/extract_agent_actions.py
_FENCED_RE = re.compile(
    r"```\s*json\s+(?P<tag>proposed_promos|proposed_actions)\s*\n"
    r"(?P<body>.*?)\n```",
    re.DOTALL,
)


def _extract_blocks(md: str) -> tuple[dict | None, list[dict] | None]:
    """Return (proposed_promos_dict, proposed_actions_list) — either may be None."""
    promos = actions = None
    for m in _FENCED_RE.finditer(md):
        tag = m.group("tag")
        body = m.group("body").strip()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            print(f"[extract-promo] WARN: {tag} block failed to parse — {exc}")
            continue
        if tag == "proposed_promos":
            if not isinstance(parsed, dict):
                print(f"[extract-promo] WARN: proposed_promos not a dict — got {type(parsed).__name__}")
                continue
            promos = parsed
        elif tag == "proposed_actions":
            if not isinstance(parsed, list):
                print(f"[extract-promo] WARN: proposed_actions not a list — got {type(parsed).__name__}")
                continue
            actions = parsed
    return promos, actions


def _merge_promo_pipeline(existing: dict, new_promos: dict) -> tuple[dict, dict]:
    """Preserve in-flight (downstream) concepts. Replace Concept-stage entries.
    Add new concept ids. Returns (merged, counts)."""
    counts = {"preserved": 0, "replaced": 0, "added": 0}

    def merge_track(existing_list: list[dict], new_list: list[dict]) -> list[dict]:
        # Always keep in-flight items (past Concept stage)
        kept = [p for p in (existing_list or []) if p.get("stage") in DOWNSTREAM_STAGES]
        kept_ids = {p["id"] for p in kept}
        counts["preserved"] += len(kept)

        # Index existing Concept-stage items by id (so we can REPLACE them
        # rather than duplicate when a strategist re-proposes)
        existing_by_id = {p["id"]: p for p in (existing_list or []) if p["id"] not in kept_ids}

        for p in new_list:
            if not isinstance(p, dict) or "id" not in p:
                continue
            if p["id"] in kept_ids:
                # Conflict — in-flight version wins, skip strategist proposal
                continue
            if p["id"] in existing_by_id:
                counts["replaced"] += 1
            else:
                counts["added"] += 1
            existing_by_id[p["id"]] = p

        return kept + list(existing_by_id.values())

    merged = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "promo-concept-strategist",
        "acquisition": merge_track(existing.get("acquisition", []), new_promos.get("acquisition", [])),
        "retention":   merge_track(existing.get("retention", []),   new_promos.get("retention", [])),
    }
    return merged, counts


def _merge_work_queue_actions(existing_payload, new_actions: list[dict]) -> tuple[list[dict], dict]:
    """Append new actions, skipping duplicates by id. Returns (items, counts)."""
    counts = {"added": 0, "skipped_dupe": 0, "skipped_invalid": 0}

    # work-queue.json can be either a list (top-level) or {items: [...]}
    if isinstance(existing_payload, list):
        items = list(existing_payload)
    else:
        items = list(existing_payload.get("items", existing_payload.get("actions", [])))

    existing_ids = {i.get("id") for i in items if isinstance(i, dict) and i.get("id")}

    for a in new_actions:
        if not isinstance(a, dict):
            counts["skipped_invalid"] += 1
            continue
        aid = a.get("id")
        if not aid:
            counts["skipped_invalid"] += 1
            continue
        if aid in existing_ids:
            counts["skipped_dupe"] += 1
            continue
        # Stamp source_agent if missing (so dashboard attribution works)
        a.setdefault("source_agent", "promo-concept-strategist")
        items.append(a)
        existing_ids.add(aid)
        counts["added"] += 1

    return items, counts


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Path to promo-strategist markdown output")
    args = p.parse_args()

    md_path = Path(args.input)
    if not md_path.exists():
        print(f"[extract-promo] Input not found: {md_path}")
        return 1

    md = md_path.read_text(encoding="utf-8")
    promos, actions = _extract_blocks(md)

    if promos is None and actions is None:
        print("[extract-promo] No JSON blocks found in strategist output — agent likely failed")
        return 0  # non-fatal — phase script continues

    # ── Merge proposed_promos → state/promo-pipeline.json ──
    if promos is not None:
        existing = {}
        if PROMO_FILE.exists():
            try:
                existing = json.loads(PROMO_FILE.read_text())
            except json.JSONDecodeError:
                print("[extract-promo] state/promo-pipeline.json was malformed — overwriting")
                existing = {}
        merged, counts = _merge_promo_pipeline(existing, promos)
        PROMO_FILE.write_text(json.dumps(merged, indent=2))
        print(f"[extract-promo] promo-pipeline.json: preserved={counts['preserved']} "
              f"replaced={counts['replaced']} added={counts['added']}")
    else:
        print("[extract-promo] No proposed_promos block — promo-pipeline.json unchanged")

    # ── Merge proposed_actions → state/work-queue.json ──
    if actions is not None:
        existing_payload = []
        if WORK_QUEUE_FILE.exists():
            try:
                existing_payload = json.loads(WORK_QUEUE_FILE.read_text())
            except json.JSONDecodeError:
                print("[extract-promo] state/work-queue.json was malformed — overwriting with new actions only")
                existing_payload = []

        items, counts = _merge_work_queue_actions(existing_payload, actions)

        # Preserve original shape if it was a dict wrapper
        if isinstance(existing_payload, dict):
            existing_payload["items"] = items
            existing_payload.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
            WORK_QUEUE_FILE.write_text(json.dumps(existing_payload, indent=2))
        else:
            WORK_QUEUE_FILE.write_text(json.dumps(items, indent=2))

        print(f"[extract-promo] work-queue.json: added={counts['added']} "
              f"skipped_dupe={counts['skipped_dupe']} skipped_invalid={counts['skipped_invalid']}")
    else:
        print("[extract-promo] No proposed_actions block — work-queue.json unchanged")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
