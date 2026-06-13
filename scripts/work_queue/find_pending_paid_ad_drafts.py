"""
find_pending_paid_ad_drafts.py — discover paid ad actions needing AI drafts.

Combined discovery for Meta ad + Google Ads RSA drafters. Filters work-queue
actions by source_page + verb prefix, skips actions that are pure optimization
(pause/scale/adjust), and skips actions whose draft already exists.

Output format (one per line):
    meta|<action_id>|<slug>
    gads|<action_id>|<slug>

phase1c_content_drafter.sh consumes this and fires the right drafter per row.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORK_QUEUE = BASE_DIR / "state" / "work-queue.json"
META_DIR   = BASE_DIR / "outputs" / "meta-ads"
GADS_DIR   = BASE_DIR / "outputs" / "google-ads-rsa"

# New-creative verbs — only these trigger drafting. Optimization actions
# (Pause / Scale / Adjust / Reduce / Lower budget) do NOT need new ad copy.
NEW_CREATIVE_RE = re.compile(
    r"^(Launch|Create|Write|Draft|Build|Add|Test\s+new|Run\s+new|Start)",
    re.IGNORECASE,
)


def slugify(text: str, max_len: int = 60) -> str:
    """Title → URL-safe slug. Matches Path D's algorithm."""
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len].rstrip("-")


def main() -> int:
    if not WORK_QUEUE.exists():
        print(f"[find-paid-ads] {WORK_QUEUE} not found — skipping", file=sys.stderr)
        return 0

    META_DIR.mkdir(parents=True, exist_ok=True)
    GADS_DIR.mkdir(parents=True, exist_ok=True)

    existing_meta = {p.stem for p in META_DIR.glob("*.md")}
    existing_gads = {p.stem for p in GADS_DIR.glob("*.md")}

    data = json.loads(WORK_QUEUE.read_text())
    items = data.get("items", data) if isinstance(data, dict) else data
    if isinstance(items, dict):
        items = list(items.values())

    found_meta = 0
    found_gads = 0

    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not NEW_CREATIVE_RE.match(title):
            continue
        action_id = item.get("id", "")
        if not action_id:
            continue
        slug = slugify(title)
        if not slug:
            continue

        if item.get("source_page") == "meta-ads":
            if slug in existing_meta:
                continue
            print(f"meta|{action_id}|{slug}")
            found_meta += 1
        elif item.get("source_page") == "google-ads":
            if slug in existing_gads:
                continue
            print(f"gads|{action_id}|{slug}")
            found_gads += 1

    print(f"[find-paid-ads] meta={found_meta} · gads={found_gads}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
