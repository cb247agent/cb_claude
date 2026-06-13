"""
find_pending_gbp_posts.py — discover GBP post actions needing AI drafts.

Filters work-queue actions by:
  - source_page == "gbp"
  - title starts with new-post verbs: Post / Create / Write / Draft /
    Build / Launch / Publish / Add new GBP

Skips operational actions (Refresh photos, Drive reviews, Respond to
reviews, Close rating gap) — those need different artefacts, not post copy.

Output: one `<action_id>|<slug>` per line on stdout.
phase1c_content_drafter.sh consumes this and fires gbp-post-drafter for each.

Idempotent — skips actions whose draft already exists.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORK_QUEUE = BASE_DIR / "state" / "work-queue.json"
OUT_DIR = BASE_DIR / "outputs" / "gbp-posts"

# Verbs that trigger new POST copy drafting.
NEW_POST_VERB_RE = re.compile(
    r"^(Post|Create|Write|Draft|Build|Launch|Publish|Add\s+new\s+GBP)",
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
        print(f"[find-gbp-posts] {WORK_QUEUE} not found — skipping", file=sys.stderr)
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
        if item.get("source_page") != "gbp":
            continue
        title = str(item.get("title", "")).strip()
        if not NEW_POST_VERB_RE.match(title):
            continue
        action_id = item.get("id", "")
        if not action_id:
            continue
        slug = slugify(title)
        if not slug or slug in existing_slugs:
            continue
        print(f"{action_id}|{slug}")
        found += 1

    print(f"[find-gbp-posts] {found} action(s) pending a draft", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
