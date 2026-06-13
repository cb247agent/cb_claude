"""
find_pending_content.py — list AI-owned content actions that need drafting.

Used by scripts/phases/phase1c_content_drafter.sh.

Algorithm:
  1. Read state/work-queue.json
  2. Find actions where:
     - owner == "AI" OR owner_role contains "Content"
     - title starts with "Build blog:", "Build landing page:", or
       "Build service page:"
  3. For each, determine format from title prefix
  4. Check whether a draft already exists at outputs/{format}/{slug}-*.md
     (idempotent — skip if so)
  5. For each remaining, print "<action_id>|<format>" one per line

Output (stdout):
    seo-build-2026w24-001|blog
    seo-build-2026w24-008|landing_page
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
BASE_DIR = _HERE.parent.parent
WORK_QUEUE = BASE_DIR / "state" / "work-queue.json"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Title prefix → format → output subdir
FORMAT_MAP = {
    "build blog:":          ("blog",         "blogs"),
    "build landing page:":  ("landing_page", "landing-pages"),
    "build service page:":  ("service_page", "service-pages"),
}


def _slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s.strip("-")[:60]


def _has_draft(format_subdir: str, slug_hint: str) -> bool:
    """Return True if any file matching {slug_hint}*.md exists in outputs/{format_subdir}/."""
    folder = OUTPUTS_DIR / format_subdir
    if not folder.exists():
        return False
    # Glob matches any date suffix
    return any(folder.glob(f"{slug_hint}*.md"))


def _detect_format(title: str) -> tuple[str, str] | None:
    """Return (format_name, output_subdir) or None if unmatched."""
    t = (title or "").strip().lower()
    for prefix, (fmt, subdir) in FORMAT_MAP.items():
        if t.startswith(prefix):
            return fmt, subdir
    return None


def _topic_slug(title: str) -> str:
    """Extract topic from `Build blog: "X — subtitle"` and slugify."""
    # Try quoted form first
    m = re.search(r"['\"](.*?)['\"]", title or "")
    if m:
        topic = m.group(1)
    else:
        # Fall back: strip prefix
        topic = re.sub(r"^build\s+(blog|landing\s+page|service\s+page)\s*:\s*", "", title, flags=re.I).strip()
    # Slugify but keep it short for the prefix match
    return _slugify(topic)


def main() -> int:
    if not WORK_QUEUE.exists():
        print("[find-content] state/work-queue.json not found — nothing to draft", file=sys.stderr)
        return 0

    try:
        data = json.loads(WORK_QUEUE.read_text())
    except json.JSONDecodeError as exc:
        print(f"[find-content] work-queue.json malformed: {exc}", file=sys.stderr)
        return 1

    items = data if isinstance(data, list) else data.get("items") or data.get("actions") or []

    pending: list[tuple[str, str]] = []
    for a in items:
        if not isinstance(a, dict):
            continue
        aid = a.get("id")
        if not aid:
            continue

        owner = (a.get("owner") or "").strip()
        owner_role = (a.get("owner_role") or "").strip()
        if owner != "AI" and "Content" not in owner_role:
            continue

        title = a.get("title") or ""
        det = _detect_format(title)
        if not det:
            continue
        fmt, subdir = det

        slug = _topic_slug(title)
        if not slug:
            print(f"[find-content] WARN: {aid} title has no extractable topic: {title!r}",
                  file=sys.stderr)
            continue

        if _has_draft(subdir, slug):
            # Idempotent — already drafted
            continue

        pending.append((aid, fmt))

    for aid, fmt in pending:
        print(f"{aid}|{fmt}")

    print(f"[find-content] Found {len(pending)} content action(s) pending a draft", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
