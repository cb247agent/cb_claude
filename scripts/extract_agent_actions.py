"""
extract_agent_actions.py — Extract structured WorkQueueAction proposals from
LLM agent markdown outputs and merge them into the work queue.

The "Agent Action Contract" (Tia direction 07 Jun 2026):
  Every agent's markdown output MUST end with a ```json proposed_actions
  block listing zero or more WorkQueueAction-shaped objects. This script:
    1. Walks outputs/ directories looking for markdown files newer than the
       last extraction
    2. Extracts the json block from each
    3. Validates against WorkQueueAction schema
    4. Tags each action with source_agent='<filename slug>'
    5. Merges into state/work-queue.json (for CB247) or
       state/mwcc-work-queue.json (for MWCC) based on --business flag
    6. Skips agents that produce no actions (the json block is empty list)

This makes agent recommendations measurable using the same closed loop as
rule-based emitters — solves the "verdicts are judgement calls" weakness.

Usage:
    python scripts/extract_agent_actions.py --business cb247
    python scripts/extract_agent_actions.py --business mwcc

Output:
    Merges new actions into state/<business>-work-queue.json (or
    state/work-queue.json for cb247). Existing actions are preserved;
    duplicates (by id) are skipped.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR     = Path(__file__).resolve().parent.parent
OUTPUTS_DIR  = BASE_DIR / "outputs"
STATE_DIR    = BASE_DIR / "state"

# Where to look for agent markdown outputs (per business)
AGENT_OUTPUT_PATHS = {
    "cb247": [
        OUTPUTS_DIR / "research",
        OUTPUTS_DIR / "blueprints",
        OUTPUTS_DIR / "seo",
        OUTPUTS_DIR / "creatives",
        # Wave B (11 Jun 2026) — dev-cycle agents produce proposed_actions too
        OUTPUTS_DIR / "qa",
        OUTPUTS_DIR / "security",
    ],
    "mwcc": [
        OUTPUTS_DIR / "mwcc",
    ],
}

# Work queue file (per business)
WORK_QUEUE_FILES = {
    "cb247": STATE_DIR / "work-queue.json",
    "mwcc":  STATE_DIR / "mwcc-work-queue.json",
}


# Regex to match a ```json proposed_actions block. Tolerates:
#   ```json proposed_actions
#   ```json proposed-actions
#   ```json  ← with no label (we still extract if the array looks like actions)
#   ```jsonc (some agents use jsonc for trailing commas)
ACTION_BLOCK_RE = re.compile(
    r"```(?:json|jsonc)(?:\s+proposed[_-]?actions)?\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)


def _slug_from_path(p: Path) -> str:
    """Derive a source_agent slug from the markdown filename.
    e.g. outputs/research/strategist-2026-06-09.md → 'strategist'
    """
    stem = p.stem
    # Strip date suffixes like -2026-06-09 or -final
    stem = re.sub(r"-\d{4}-\d{2}-\d{2}.*$", "", stem)
    stem = re.sub(r"-final$", "", stem)
    return stem


def _extract_from_markdown(md_path: Path) -> list[dict]:
    """Extract list of action dicts from a markdown file. Returns empty list
    if no contract block found or block is empty."""
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  [skip] Could not read {md_path.name}: {e}")
        return []

    matches = ACTION_BLOCK_RE.findall(text)
    if not matches:
        return []

    actions: list[dict] = []
    for block in matches:
        block = block.strip()
        if not block:
            continue
        # Strip trailing commas (jsonc compatibility)
        cleaned = re.sub(r",(\s*[\]\}])", r"\1", block)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"  [warn] {md_path.name}: invalid JSON in action block — {e}")
            continue

        if isinstance(parsed, list):
            actions.extend(parsed)
        elif isinstance(parsed, dict):
            # Allow either a list or a wrapper {"actions": [...]} or
            # {"proposed_actions": [...]} (Wave B agents sometimes wrap the
            # key explicitly — 11 Jun 2026)
            if "actions" in parsed and isinstance(parsed["actions"], list):
                actions.extend(parsed["actions"])
            elif "proposed_actions" in parsed and isinstance(parsed["proposed_actions"], list):
                actions.extend(parsed["proposed_actions"])
            else:
                actions.append(parsed)

    return actions


def _validate_action(a: dict, source_agent: str, business: str) -> tuple[dict | None, list[str]]:
    """Light validation. Returns (normalised action dict, errors).
    We don't enforce strict WorkQueueAction here — that happens at sync time —
    but we ensure the minimum viable shape exists."""
    errors: list[str] = []

    required = ["title", "owner", "priority"]
    for f in required:
        if not a.get(f):
            errors.append(f"missing '{f}'")

    if errors:
        return None, errors

    # Normalise + add source_agent
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # Derive id if not present
    if not a.get("id"):
        # e.g. strategist-act-2026w23-001
        wk = datetime.now().isocalendar()
        slug = source_agent.replace(" ", "_")
        a["id"] = f"{slug}-act-{wk.year}w{wk.week:02d}-{hash(a['title']) % 1000:03d}"

    # Set source_run_at + source_agent (the new contract field)
    a.setdefault("source_run_at", now)
    a["source_agent"] = source_agent

    # source_page is required by schema; default to category if missing
    if not a.get("source_page"):
        cat = (a.get("category") or "seo-organic").lower()
        # Map common category names → valid source_page values
        cat_map = {
            "seo": "seo-organic", "seo-organic": "seo-organic",
            "meta": "meta-ads", "meta-ads": "meta-ads",
            "google": "google-ads", "google-ads": "google-ads",
            "gbp": "gbp",
            "social": "organic-social", "organic-social": "organic-social",
            "enrolment": "enrolment", "enrollment": "enrolment",
            "membership": "membership",
        }
        a["source_page"] = cat_map.get(cat, cat)

    # Default data_quality + effort_hours
    a.setdefault("data_quality", "medium")
    a.setdefault("effort_hours", 2.0)
    a.setdefault("category", a["source_page"])
    a.setdefault("owner_role", "")
    # Wave B (11 Jun 2026) — agents sometimes use 'brief' instead of
    # 'description'; promote it so the rest of the pipeline sees the
    # canonical field name.
    if not a.get("description") and a.get("brief"):
        a["description"] = a.pop("brief")
    a.setdefault("description", "")
    a.setdefault("urgent", False)
    a.setdefault("related_actions", [])

    # Wave B (11 Jun 2026) — coerce projected_kpis dict-shape → list-shape.
    # Mirrors the logic in normalize_strategist_output.py so QA / security
    # agents that emit dict-shape KPIs get auto-cleaned too. Drop entries
    # with no usable target.
    kpis_in = a.get("projected_kpis")
    if isinstance(kpis_in, dict):
        coerced = []
        for metric_name, body in kpis_in.items():
            if isinstance(body, dict):
                # Ensure the metric name is set even if body doesn't include it
                body = {**body}
                body.setdefault("metric", metric_name)
                coerced.append(body)
            else:
                coerced.append({"metric": metric_name, "target": body})
        a["projected_kpis"] = coerced
    elif not isinstance(kpis_in, list):
        a["projected_kpis"] = []
    # Default measurement_window_days on any KPI missing it (extractor is
    # lenient here; sync-time validation is strict)
    for k in a.get("projected_kpis") or []:
        if isinstance(k, dict) and not k.get("measurement_window_days"):
            k["measurement_window_days"] = 14   # safe default

    # Ensure projected_kpis exists (can be empty for narrative-only actions,
    # though the contract document says it SHOULD have at least one)
    a.setdefault("projected_kpis", [])

    return a, []


def _load_work_queue(wq_file: Path) -> dict:
    """Load existing work-queue.json or return empty skeleton."""
    if not wq_file.exists():
        return {"generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "actions": []}
    try:
        data = json.loads(wq_file.read_text())
        if not isinstance(data, dict):
            return {"actions": []}
        data.setdefault("actions", [])
        return data
    except Exception as e:
        print(f"  [warn] Could not parse existing {wq_file.name}: {e} — starting fresh")
        return {"actions": []}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract WorkQueueAction proposals from agent markdown outputs")
    parser.add_argument("--business", required=True, choices=["cb247", "mwcc"],
                        help="Which work queue to merge into")
    parser.add_argument("--since-days", type=int, default=8,
                        help="Only look at markdown files modified in the last N days (default 8)")
    args = parser.parse_args()

    biz = args.business
    paths = AGENT_OUTPUT_PATHS[biz]
    wq_file = WORK_QUEUE_FILES[biz]

    cutoff = datetime.now().timestamp() - (args.since_days * 86400)

    # Find markdown files
    md_files: list[Path] = []
    for d in paths:
        if not d.exists():
            continue
        for f in d.rglob("*.md"):
            try:
                if f.stat().st_mtime >= cutoff:
                    md_files.append(f)
            except OSError:
                continue

    if not md_files:
        print(f"[extract-agent-actions] No agent markdown files in last {args.since_days} days for {biz}")
        return 0

    print(f"[extract-agent-actions] Scanning {len(md_files)} agent output(s) for {biz}...")

    all_new_actions: list[dict] = []
    for md in sorted(md_files):
        agent_slug = _slug_from_path(md)
        actions = _extract_from_markdown(md)
        if not actions:
            print(f"  [no-contract] {md.relative_to(BASE_DIR)} — agent did not include proposed_actions block")
            continue
        for a in actions:
            normalised, errs = _validate_action(a, source_agent=agent_slug, business=biz)
            if errs:
                print(f"  [skip] {md.name}: {a.get('title','(no title)')[:60]} — {', '.join(errs)}")
                continue
            all_new_actions.append(normalised)

    if not all_new_actions:
        print(f"[extract-agent-actions] No valid action proposals found")
        return 0

    # Merge into existing work queue, dedup by id
    wq = _load_work_queue(wq_file)
    existing_ids = {a.get("id") for a in wq["actions"]}
    added = 0
    for a in all_new_actions:
        if a["id"] in existing_ids:
            continue
        wq["actions"].append(a)
        existing_ids.add(a["id"])
        added += 1

    wq["last_agent_extract_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    wq_file.write_text(json.dumps(wq, indent=2, default=str))

    print(f"\n[extract-agent-actions] ✅ Merged {added} new agent actions into {wq_file.relative_to(BASE_DIR)}")
    print(f"[extract-agent-actions] Work queue total: {len(wq['actions'])} actions")

    # Per-agent summary
    if added > 0:
        from collections import Counter
        by_agent = Counter(a["source_agent"] for a in all_new_actions if a["id"] in {x["id"] for x in wq["actions"][-added:]})
        for agent, count in sorted(by_agent.items()):
            print(f"  · {agent}: {count} action(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
