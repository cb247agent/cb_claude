"""
extract_content_writer_output.py — emit Review + publish follow-up actions.

When content-writer.yml writes a draft to outputs/blogs/ /
outputs/landing-pages/ / outputs/service-pages/, this script:

  1. Scans those 3 folders for .md files
  2. For each file, checks whether a "Review + publish" action already
     exists in state/work-queue.json referencing this file
     (idempotent — skips if so)
  3. Emits a new WorkQueueAction with:
       - title: "Review + publish {format}: \"{topic}\""
       - owner: John (SEO Specialist)
       - owner_role: "SEO Specialist (SEO QC) + Angela brand QC before publish"
       - description: brief + draft path + checklist
       - projected_kpis: gsc_clicks_weekly (baseline = current, target +50%)
       - category: "seo-organic"
       - source_agent: "content-writer"
       - parent_action_id: (the original Build action id — pulled from
         the YAML front-matter "source_action" field)

Runs in phase1c_content_drafter.sh after content-writer completes, before
sync_to_supabase.

Idempotent — re-running on already-emitted follow-ups is a no-op.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
WORK_QUEUE = STATE_DIR / "work-queue.json"
OUTPUTS = BASE_DIR / "outputs"

FORMAT_DIRS = {
    "blog":         OUTPUTS / "blogs",
    "landing_page": OUTPUTS / "landing-pages",
    "service_page": OUTPUTS / "service-pages",
}

FORMAT_LABELS = {
    "blog":         "blog",
    "landing_page": "landing page",
    "service_page": "service page",
}


def _parse_frontmatter(md: str) -> dict:
    """Extract YAML front-matter from a markdown file. Returns empty dict if absent."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", md, flags=re.DOTALL)
    if not m:
        return {}
    out: dict = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip().strip('"').strip("'")
        out[k.strip()] = v
    return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _existing_actions(items: list[dict]) -> set[str]:
    """Return set of draft file paths already referenced by some Review action."""
    refs: set[str] = set()
    for a in items:
        if not isinstance(a, dict):
            continue
        if not (a.get("source_agent") == "content-writer" or "Review + publish" in (a.get("title") or "")):
            continue
        desc = a.get("description") or ""
        for m in re.finditer(r"outputs/(blogs|landing-pages|service-pages)/[\w\-.]+\.md", desc):
            refs.add(m.group(0))
    return refs


def _make_action(md_path: Path, fmt: str, fm: dict) -> dict | None:
    """Build a Review + publish WorkQueueAction dict from a draft file + its YAML front-matter."""
    rel_path = f"outputs/{md_path.parent.name}/{md_path.name}"
    topic = fm.get("title") or fm.get("primary_keyword") or md_path.stem.replace("-", " ").title()
    keyword = fm.get("primary_keyword") or "(no keyword in front matter)"
    label = FORMAT_LABELS.get(fmt, fmt)
    slug = fm.get("slug") or md_path.stem

    week_iso = datetime.now(timezone.utc).strftime("%Yw%V")
    # Build a deterministic id so re-runs of this extractor don't duplicate.
    safe_slug = re.sub(r"[^a-z0-9\-]", "", slug.lower())[:24]
    action_id = f"content-review-{safe_slug}-{week_iso}"

    description = (
        f"AI-drafted {label} ready for review. "
        f"Primary keyword: '{keyword}'. "
        f"Draft at {rel_path}. "
        f"Before publishing: (1) John verifies SEO structure (H1, H2 hierarchy, "
        f"meta description 140-155 chars, internal links 2-5, JSON-LD schema). "
        f"(2) Angela verifies brand voice + compliance (no competitor names, "
        f"no banned phrases, $11.95/wk anchor, paid add-ons not bundled). "
        f"(3) Publish via CMS and submit URL to GSC for indexing. "
        f"Verdict at 28 days based on gsc_clicks_weekly."
    )

    return {
        "id":              action_id,
        "source_page":     "seo-organic",
        "source_run_at":   _now_iso(),
        "title":           f"Review + publish {label}: \"{topic}\"",
        "description":     description,
        "owner":           "John",
        "owner_role":      "SEO Specialist (SEO QC) + Angela brand QC before publish",
        "priority":        "P2",
        "effort_hours":    1.5,
        "category":        "seo-organic",
        "data_quality":    "high",
        "projected_kpis":  [{
            "metric": "gsc_clicks_weekly",
            "baseline": 0,
            "target": 5,
            "measurement_window_days": 28,
            "confidence": "medium",
        }],
        "source_agent":    "content-writer",
    }


def main() -> int:
    if not WORK_QUEUE.exists():
        print(f"[extract-content] {WORK_QUEUE} not found — nothing to emit")
        return 0

    raw = json.loads(WORK_QUEUE.read_text())
    items = raw if isinstance(raw, list) else raw.get("items") or raw.get("actions") or []

    referenced = _existing_actions(items)
    new_actions: list[dict] = []

    for fmt, folder in FORMAT_DIRS.items():
        if not folder.exists():
            continue
        for md_path in sorted(folder.glob("*.md")):
            rel_path = f"outputs/{md_path.parent.name}/{md_path.name}"
            if rel_path in referenced:
                continue  # already has a Review action

            try:
                fm = _parse_frontmatter(md_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[extract-content] WARN: could not read {md_path}: {exc}")
                continue

            action = _make_action(md_path, fmt, fm)
            if action:
                new_actions.append(action)

    if not new_actions:
        print("[extract-content] No new Review + publish actions to emit")
        return 0

    existing_ids = {a.get("id") for a in items if isinstance(a, dict)}
    appended = 0
    for a in new_actions:
        if a["id"] in existing_ids:
            continue
        items.append(a)
        existing_ids.add(a["id"])
        appended += 1

    if appended == 0:
        print("[extract-content] All candidate actions already exist by id — nothing to add")
        return 0

    # Persist — update BOTH "items" and "actions" lists (sync reads from "actions")
    if isinstance(raw, list):
        WORK_QUEUE.write_text(json.dumps(items, indent=2))
    else:
        for k in ("items", "actions"):
            if k in raw:
                raw[k] = items
        raw["last_agent_extract_at"] = _now_iso()
        WORK_QUEUE.write_text(json.dumps(raw, indent=2))

    print(f"[extract-content] Appended {appended} Review + publish action(s) to work-queue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
