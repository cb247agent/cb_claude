"""
find_launch_ready_promos.py — list promo ids that need a media plan.

Used by scripts/phases/phase1b_promo_launch.sh to discover which Approved
concepts haven't been processed by the campaign-launch-strategist yet.

Algorithm:
  1. Read state/promo-pipeline.json — every concept
  2. Read Supabase promo_pipeline_state — team's stage overrides
  3. Merge: Supabase stage wins over JSON stage
  4. Filter to concepts where stage IN {'Approved', 'Asset Shoot Scheduled'}
  5. For each, check whether outputs/media-plans/media-plan-{id}-*.md
     already exists — if yes, skip (idempotent)
  6. For each remaining, ALSO check that all enriched fields are present
     (audience_seed, conversion_event, budget_envelope, historical_cpa_baseline,
     launch_window, kill_criteria, creative_hints) — if missing, log warning
     and skip
  7. Print qualifying concept ids one per line to stdout

Output (stdout):
    promo-kids-hub-2026-06
    promo-fathers-day-gift-2026-08

If Supabase isn't reachable, falls back to JSON-only stage info (so the
script can still run during local development).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
MEDIA_PLANS_DIR = BASE_DIR / "outputs" / "media-plans"
PROMO_FILE = STATE_DIR / "promo-pipeline.json"

LAUNCH_READY_STAGES = {"Approved", "Asset Shoot Scheduled"}

REQUIRED_ENRICHED_FIELDS = (
    "audience_seed",
    "conversion_event",
    "budget_envelope",
    "historical_cpa_baseline",
    "launch_window",
    "kill_criteria",
    "creative_hints",
)


def _load_promo_pipeline() -> list[dict]:
    """Load all concepts (acquisition + retention) from state/promo-pipeline.json."""
    if not PROMO_FILE.exists():
        print("[find-launch] state/promo-pipeline.json not found — no concepts to launch",
              file=sys.stderr)
        return []
    try:
        data = json.loads(PROMO_FILE.read_text())
    except json.JSONDecodeError as exc:
        print(f"[find-launch] promo-pipeline.json malformed: {exc}", file=sys.stderr)
        return []
    return list(data.get("acquisition", [])) + list(data.get("retention", []))


def _fetch_supabase_stages() -> dict[str, str]:
    """Return {concept_id: stage} from Supabase promo_pipeline_state.
    Empty dict if Supabase unreachable — caller falls back to JSON stages."""
    try:
        import urllib.request
        import urllib.error
    except ImportError:
        return {}

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        print("[find-launch] SUPABASE_URL/KEY not set — using JSON stages only",
              file=sys.stderr)
        return {}

    endpoint = f"{url.rstrip('/')}/rest/v1/promo_pipeline_state?select=id,stage"
    req = urllib.request.Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"[find-launch] Supabase fetch failed ({exc}) — using JSON stages only",
              file=sys.stderr)
        return {}

    return {r["id"]: r.get("stage", "") for r in rows if isinstance(r, dict) and "id" in r}


def _has_media_plan(concept_id: str) -> bool:
    """Check if outputs/media-plans/media-plan-{concept_id}-*.md exists."""
    if not MEDIA_PLANS_DIR.exists():
        return False
    pattern = f"media-plan-{concept_id}-*.md"
    return any(MEDIA_PLANS_DIR.glob(pattern))


def _is_enriched(concept: dict) -> tuple[bool, list[str]]:
    """Check all enriched fields are present on the concept.
    Returns (is_complete, list_of_missing_fields)."""
    missing = [f for f in REQUIRED_ENRICHED_FIELDS if not concept.get(f)]
    return len(missing) == 0, missing


def main() -> int:
    concepts = _load_promo_pipeline()
    if not concepts:
        return 0

    supabase_stages = _fetch_supabase_stages()

    launch_ready_ids: list[str] = []
    for c in concepts:
        cid = c.get("id")
        if not cid:
            continue

        # Stage resolution — Supabase wins over JSON
        stage = supabase_stages.get(cid, c.get("stage", ""))
        if stage not in LAUNCH_READY_STAGES:
            continue

        # Idempotent — skip if media plan already exists
        if _has_media_plan(cid):
            continue

        # Enrichment check — skip + warn if fields missing
        is_complete, missing = _is_enriched(c)
        if not is_complete:
            print(
                f"[find-launch] WARN: concept {cid} stage={stage} but missing enriched fields: {missing}. "
                f"Re-run promo-concept-strategist before launching.",
                file=sys.stderr,
            )
            continue

        launch_ready_ids.append(cid)

    # Print one per line — phase1b_promo_launch.sh consumes via while-read
    for cid in launch_ready_ids:
        print(cid)

    print(f"[find-launch] Found {len(launch_ready_ids)} launch-ready concept(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
