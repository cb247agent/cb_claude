"""
find_pending_trend_rides.py — discover Trend-ride + Adapt-format actions
needing an AI draft.

Filters work-queue actions by:
  - source_page == "organic-social"
  - title starts with "Trend-ride" or "Adapt"

Skips actions whose draft already exists in outputs/trend-rides/.
Output: one `<action_id>|<slug>` per line on stdout.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORK_QUEUE = BASE_DIR / "state" / "work-queue.json"
OUT_DIR = BASE_DIR / "outputs" / "trend-rides"

TREND_VERB_RE = re.compile(r"^(Trend-ride|Adapt\s+high-engagement)", re.IGNORECASE)


def slugify(text: str, max_len: int = 60) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len].rstrip("-")


def main() -> int:
    if not WORK_QUEUE.exists():
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = {p.stem for p in OUT_DIR.glob("*.md")}

    data = json.loads(WORK_QUEUE.read_text())
    items = data.get("items", data) if isinstance(data, dict) else data
    if isinstance(items, dict):
        items = list(items.values())

    found = 0
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if item.get("source_page") != "organic-social":
            continue
        title = str(item.get("title", "")).strip()
        if not TREND_VERB_RE.match(title):
            continue
        action_id = item.get("id", "")
        if not action_id:
            continue
        slug = slugify(title)
        if not slug or slug in existing:
            continue
        print(f"{action_id}|{slug}")
        found += 1

    print(f"[find-trend-rides] {found} action(s) pending a draft", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
