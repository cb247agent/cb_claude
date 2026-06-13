"""
find_pending_seo_refresh.py — discover SEO refresh actions that need an AI draft.

Mirrors find_pending_content.py but for SEO refresh actions (existing page
improvements: H1, meta, FAQ, internal links). Filters:
  - source_page == "seo-organic"
  - title starts with verbs that indicate an EDIT to an existing page:
      Improve / Add / Expand / Update / Optimi[sz]e / Refresh
    NOT a full new page build (that's content-writer's job — handled by
    find_pending_content.py).
  - draft does not already exist in outputs/seo-refreshes/

Output: one `<action_id>|<slug>` per line on stdout.
phase1c_content_drafter.sh consumes this list and fires
agents/seo-refresh-drafter.yml for each.

Idempotent: skips actions whose draft already exists, so the script can
re-run safely.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORK_QUEUE = BASE_DIR / "state" / "work-queue.json"
OUT_DIR = BASE_DIR / "outputs" / "seo-refreshes"

# Title verbs that indicate "edit an existing page" — i.e., refresh, not build.
REFRESH_VERB_RE = re.compile(
    r"^(Improve|Add\s+(H1|FAQ|internal|location|schema|meta)|Expand|Update|Optimi[sz]e|Refresh|Edit|Rewrite\s+meta|Fix\s+(H1|meta))",
    re.IGNORECASE,
)


def slugify(text: str, max_len: int = 60) -> str:
    """Title → URL-safe slug. Matches the agent's slug rule."""
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len].rstrip("-")


def main() -> int:
    if not WORK_QUEUE.exists():
        print(f"[find-seo-refresh] {WORK_QUEUE} not found — skipping", file=sys.stderr)
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_slugs = {p.stem for p in OUT_DIR.glob("*.md")}

    data = json.loads(WORK_QUEUE.read_text())
    items = data.get("items", data) if isinstance(data, dict) else data
    if isinstance(items, dict):
        items = list(items.values())

    found = 0
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if item.get("source_page") != "seo-organic":
            continue
        title = str(item.get("title", "")).strip()
        if not REFRESH_VERB_RE.match(title):
            continue
        action_id = item.get("id", "")
        if not action_id:
            continue
        slug = slugify(title)
        if not slug:
            continue
        if slug in existing_slugs:
            continue  # draft already exists — idempotent skip
        print(f"{action_id}|{slug}")
        found += 1

    print(f"[find-seo-refresh] {found} action(s) pending a draft", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
