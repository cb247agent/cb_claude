"""
normalize_strategist_output.py — Post-process the seo-strategist agent's
markdown to normalise its `proposed_actions` JSON block so it passes the
WorkQueueAction schema.

WHY THIS EXISTS
    The LLM strategist (Option C build, 11 Jun 2026) generates actions but
    occasionally writes `projected_kpis` as a dict ({"gsc_position": {...}})
    instead of the required list-of-objects shape. It also sometimes uses
    invalid metric names (pages_4xx, schema_implemented) that aren't in
    VALID_METRICS in scripts/work_queue/schema.py.

    Rather than re-prompt the agent (expensive — Opus call), this script
    fixes the JSON in-place so the existing extract_agent_actions.py +
    sync_to_supabase.py pipeline downstream just works.

WHAT IT DOES
    1. Reads outputs/seo/seo-strategist-$DATE.md
    2. Finds the ```json proposed_actions block
    3. Normalises projected_kpis from dict → list shape
    4. Drops projections with invalid metric names (warns, doesn't fail)
    5. Adds measurement_window_days defaults if missing
    6. Drops non-schema fields ('type', 'projected_kpis' with no valid KPIs)
    7. Writes back

USAGE
    python scripts/work_queue/normalize_strategist_output.py
    python scripts/work_queue/normalize_strategist_output.py --date 2026-06-11

This should run BEFORE extract_agent_actions.py in weekly-report.sh.
Idempotent — re-running on already-clean JSON is a no-op.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date as _date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

# Import VALID_METRICS so we filter the same set the schema validates.
from work_queue.schema import VALID_METRICS  # noqa: E402

BASE_DIR = _HERE.parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"

# Default measurement window per metric — used when the strategist
# omits the field. SEO position takes 14 days to see a clean signal;
# new pages take 28 because indexing + ranking is slower.
DEFAULT_WINDOW_DAYS = {
    "gsc_position":           14,
    "gsc_clicks_weekly":      14,
    "gsc_impressions_weekly": 14,
    "gsc_ctr":                14,
    "ahrefs_domain_rating":   28,
    # Technical-SEO ops metrics — short window, these are fix-and-verify
    "pages_4xx":              7,
    "schema_implemented":     7,
    "duplicate_metas":        7,
    # Google Ads metrics (added 12 Jun 2026 for google-ads-strategist)
    "google_ads_cpa":             14,
    "google_ads_ctr":             14,
    "google_ads_cpc":             14,
    "google_ads_spend_weekly":    14,
    "google_ads_conversions_weekly":  14,
    "google_ads_clicks_weekly":   14,
    "ads_spend_saved_monthly":    30,
    "cumulative_ads_savings_monthly": 30,
    # Meta Ads metrics (added 12 Jun 2026 for meta-strategist)
    "meta_ctr":                   14,
    "meta_cpc":                   14,
    "meta_cpm":                   14,
    "meta_cpa":                   14,
    "meta_results_weekly":        14,
    "meta_ad_clicks_weekly":      14,
    "meta_ad_reach_weekly":       14,
}

# Block matcher mirrors extract_agent_actions.py
ACTION_BLOCK_RE = re.compile(
    r"(```(?:json|jsonc)(?:\s+proposed[_-]?actions)?\s*\n)(.*?)(\n```)",
    re.DOTALL | re.IGNORECASE,
)


def _normalise_projected_kpis(kpis, action_title: str) -> list:
    """Coerce projected_kpis into the list-of-objects shape the schema expects.

    Input shapes seen in the wild:
      - List of dicts (correct, returned as-is after metric filter)
      - Single dict keyed by metric name: {"gsc_position": {"baseline": X, "target": Y}}
      - Single dict with metric field: {"metric": "gsc_position", "baseline": X, "target": Y}
    """
    if isinstance(kpis, list):
        items = kpis
    elif isinstance(kpis, dict):
        # Distinguish single-KPI-dict from metric-keyed dict
        if "metric" in kpis:
            items = [kpis]
        else:
            items = []
            for metric, body in kpis.items():
                if isinstance(body, dict):
                    items.append({"metric": metric, **body})
                else:
                    items.append({"metric": metric, "target": body})
    else:
        return []

    cleaned: list = []
    for k in items:
        if not isinstance(k, dict):
            continue
        metric = k.get("metric")
        if not metric or metric not in VALID_METRICS:
            print(f"  · drop invalid KPI metric '{metric}' on action '{action_title[:50]}'")
            continue
        k.setdefault("measurement_window_days", DEFAULT_WINDOW_DAYS.get(metric, 14))
        # Strip nulls — schema wants either target OR (delta_min + delta_max)
        if k.get("target") is None and k.get("delta_min") is None:
            # Drop projections with no target — can't measure them
            print(f"  · drop KPI '{metric}' on '{action_title[:50]}' — no target/delta")
            continue
        cleaned.append(k)
    return cleaned


def _normalise_action(a: dict) -> dict | None:
    """Light cleanup. Returns None if action can't be salvaged."""
    if not isinstance(a, dict):
        return None
    # Drop non-schema fields the LLM sometimes adds
    a.pop("type", None)  # strategist sometimes adds "type": "Content"/"Ops"

    # Normalise projected_kpis
    a["projected_kpis"] = _normalise_projected_kpis(
        a.get("projected_kpis"), a.get("title", "")
    )

    # Strict-schema requirement: at least one valid KPI
    if not a["projected_kpis"]:
        print(f"  · DROP action — no valid KPIs left: {a.get('title', '')[:60]}")
        return None

    # source_page default for SEO actions
    a.setdefault("source_page", "seo-organic")
    a.setdefault("category", a["source_page"])
    return a


def normalise_markdown(md_path: Path) -> int:
    """Returns: number of valid actions written back to the file."""
    if not md_path.exists():
        print(f"[normalize] {md_path.relative_to(BASE_DIR)} missing — nothing to do")
        return 0

    text = md_path.read_text(encoding="utf-8")
    match = ACTION_BLOCK_RE.search(text)
    if not match:
        print(f"[normalize] No proposed_actions block in {md_path.name}")
        return 0

    head, body, tail = match.group(1), match.group(2), match.group(3)

    # Strip trailing commas (jsonc tolerance)
    cleaned_body = re.sub(r",(\s*[\]\}])", r"\1", body.strip())
    try:
        parsed = json.loads(cleaned_body)
    except json.JSONDecodeError as e:
        print(f"[normalize] ERROR — could not parse JSON in {md_path.name}: {e}")
        return 0

    if not isinstance(parsed, list):
        if isinstance(parsed, dict) and "actions" in parsed and isinstance(parsed["actions"], list):
            parsed = parsed["actions"]
        elif isinstance(parsed, dict) and "proposed_actions" in parsed and isinstance(parsed["proposed_actions"], list):
            # Some strategists (Google Ads, 12 Jun 2026) wrap their block in
            # {"proposed_actions": [...]} despite the contract calling for a
            # bare list. Be lenient; silently dropping would lose findings.
            parsed = parsed["proposed_actions"]
        else:
            parsed = [parsed]

    cleaned: list[dict] = []
    for a in parsed:
        normalised = _normalise_action(a)
        if normalised is not None:
            cleaned.append(normalised)

    new_body = json.dumps(cleaned, indent=2, ensure_ascii=False)
    new_block = f"{head}{new_body}{tail}"
    new_text = text[: match.start()] + new_block + text[match.end():]
    md_path.write_text(new_text, encoding="utf-8")

    print(f"[normalize] {md_path.name} — wrote {len(cleaned)} valid action(s) (was {len(parsed)})")
    return len(cleaned)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=_date.today().isoformat(),
                   help="Strategist run date (YYYY-MM-DD). Default: today.")
    args = p.parse_args()

    # Normalise EVERY strategist output of the form
    # outputs/{channel}/{channel}-strategist-{DATE}.md.
    # Channels currently: seo, google-ads (Option C #3, 12 Jun 2026).
    # Future: meta, gbp, social — auto-picked up by glob.
    pattern = f"*/*-strategist-{args.date}.md"
    found = list(OUTPUTS_DIR.glob(pattern))
    if not found:
        print(f"[normalize] no strategist outputs matching {pattern}")
        return 0
    for md in found:
        normalise_markdown(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
