"""
refresh_seo_titles.py — one-shot refresh for SEO BUILD/OPTIMISE/PROTECT rows
that were emitted under the OLD title/description format (pre-11 Jun 2026).

Why this exists:
    Tia raised that "Build new content for 'X'" was too abstract — the team
    didn't know if the artifact was a blog, a service page, or a landing
    page. We rewrote seo_emitter.py to call out the artifact explicitly.
    But the emitter is week-idempotent + criteria-gated, so existing rows
    don't get re-emitted automatically — they need a one-shot rewrite.

What this does:
    1. Read state/work-queue.json
    2. Find rows whose title starts with "Build new content for" /
       "Optimise on-page for" / "Protect "
    3. Apply the new title/description format using the artifact classifier
    4. Write back to state/work-queue.json
    5. (Caller runs sync_to_supabase.py to push the new shape up)

Idempotent: re-running won't re-rewrite (already-new titles get skipped).

Run:
    .venv/bin/python3.13 scripts/work_queue/refresh_seo_titles.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from work_queue.seo_emitter import (  # noqa: E402
    _classify_seo_artifact,
    _deliverable_copy,
)


BASE_DIR = _HERE.parent.parent
WORK_QUEUE_FILE = BASE_DIR / "state" / "work-queue.json"


def _rewrite_build_row(row: dict) -> bool:
    """Rewrite a 'Build new content for X' row with the new artifact-explicit
    title + description. Returns True if mutated."""
    title = row.get("title", "")
    if not title.startswith("Build new content for"):
        return False

    # Pull keyword + baseline from projected_kpis (it's the source of truth)
    kpis = row.get("projected_kpis") or []
    pos_kpi = next((k for k in kpis if k.get("metric") == "gsc_position"), None)
    if not pos_kpi or not pos_kpi.get("keyword"):
        print(f"  · SKIP {row.get('id')} — no keyword in projected_kpis")
        return False

    keyword = pos_kpi["keyword"]
    baseline_pos = float(pos_kpi.get("baseline") or 0)

    # Pull impressions from the title's tail (was: "— N impressions, ranking #M")
    # Fall back to 0 if not present.
    import re
    m_impr = re.search(r"(\d+)\s+impressions", title)
    baseline_impr = int(m_impr.group(1)) if m_impr else 0

    clicks_kpi = next((k for k in kpis if k.get("metric") == "gsc_clicks_weekly"), None)
    baseline_clicks = int((clicks_kpi or {}).get("baseline") or 0)

    artifact_type, action_verb = _classify_seo_artifact(keyword)
    deliverable_desc = _deliverable_copy(artifact_type, keyword)

    new_title = (
        f"{action_verb}: '{keyword}' — {baseline_impr} impressions, ranking #{baseline_pos:.0f}"
    )
    new_desc = (
        f"Keyword '{keyword}' has {baseline_impr} weekly impressions but ranks #{baseline_pos:.0f}, "
        f"only generating {baseline_clicks} clicks. No dedicated page targeting this query.\n\n"
        f"Deliverable — {artifact_type.replace('-', ' ')}: {deliverable_desc}\n\n"
        f"Flow: AI drafts → Brand Manager QC → publish to Webflow. "
        f"Target: rank top 10 within 4 weeks."
    )

    row["title"] = new_title
    row["description"] = new_desc
    print(f"  ✏️  {row.get('id')} → {artifact_type:<13s} | {new_title[:60]}")
    return True


def _rewrite_optimise_row(row: dict) -> bool:
    title = row.get("title", "")
    if not title.startswith("Optimise on-page for"):
        return False
    desc = row.get("description", "")
    if "Brand Manager QC" in desc and "Deliverable" in desc:
        return False   # already in new format

    # Pull keyword + baseline
    kpis = row.get("projected_kpis") or []
    pos_kpi = next((k for k in kpis if k.get("metric") == "gsc_position"), None)
    if not pos_kpi or not pos_kpi.get("keyword"):
        return False
    keyword = pos_kpi["keyword"]
    baseline_pos = float(pos_kpi.get("baseline") or 0)
    target_pos = pos_kpi.get("target") or baseline_pos

    clicks_kpi = next((k for k in kpis if k.get("metric") == "gsc_clicks_weekly"), None)
    baseline_clicks = int((clicks_kpi or {}).get("baseline") or 0)

    # Pull impressions from description (was: "with N clicks and M impressions per week")
    import re
    m_impr = re.search(r"(\d+)\s+impressions", desc)
    baseline_impr = int(m_impr.group(1)) if m_impr else 0

    new_desc = (
        f"Keyword '{keyword}' is ranking #{baseline_pos:.1f} with {baseline_clicks} clicks "
        f"and {baseline_impr} impressions per week.\n\n"
        f"Deliverable — page edit (no new artifact): rewrite the title tag, meta description, "
        f"and H1 of the existing ranking page. Add 1–2 internal links from related content. "
        f"Tighten content depth if the page is thin.\n\n"
        f"Flow: SEO Specialist edits the page → Brand Manager QC → publish.\n\n"
        f"Target: push to #{int(target_pos)}."
    )
    row["description"] = new_desc
    print(f"  ✏️  {row.get('id')} → optimise (updated description) | {title[:60]}")
    return True


def _rewrite_protect_row(row: dict) -> bool:
    title = row.get("title", "")
    if not title.startswith("Protect "):
        return False
    desc = row.get("description", "")
    if "Deliverable" in desc:
        return False   # already in new format

    kpis = row.get("projected_kpis") or []
    pos_kpi = next((k for k in kpis if k.get("metric") == "gsc_position"), None)
    if not pos_kpi or not pos_kpi.get("keyword"):
        return False
    keyword = pos_kpi["keyword"]
    baseline_pos = float(pos_kpi.get("baseline") or 0)

    # Clicks from description
    import re
    m_clicks = re.search(r"generates (\d+) clicks", desc)
    baseline_clicks = int(m_clicks.group(1)) if m_clicks else 0

    new_desc = (
        f"This keyword ranks #{baseline_pos:.1f} and generates {baseline_clicks} clicks per week.\n\n"
        f"Deliverable — defensive work (no new artifact): build 1–2 new internal links from related "
        f"content, monitor for position decay, refresh the page date stamp if it hasn't been updated "
        f"in 90 days.\n\n"
        f"Flow: SEO Specialist runs the maintenance, no QC required for an internal-link tweak.\n\n"
        f"Target: hold position #{baseline_pos:.1f} ± 1."
    )
    row["description"] = new_desc
    print(f"  ✏️  {row.get('id')} → protect (updated description) | {title[:60]}")
    return True


def main() -> int:
    if not WORK_QUEUE_FILE.exists():
        print(f"[refresh-seo] {WORK_QUEUE_FILE} missing — nothing to refresh")
        return 0

    data = json.loads(WORK_QUEUE_FILE.read_text())
    actions = data.get("actions") or []

    print(f"[refresh-seo] inspecting {len(actions)} actions")

    rewritten = 0
    for row in actions:
        if row.get("source_page") != "seo-organic":
            continue
        if _rewrite_build_row(row):
            rewritten += 1
        elif _rewrite_optimise_row(row):
            rewritten += 1
        elif _rewrite_protect_row(row):
            rewritten += 1

    if rewritten == 0:
        print("[refresh-seo] no rows needed rewriting (already in new format)")
        return 0

    WORK_QUEUE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\n[refresh-seo] rewrote {rewritten} SEO row(s). Next: run sync_to_supabase.py to push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
