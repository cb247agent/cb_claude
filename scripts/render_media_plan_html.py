"""
render_media_plan_html.py — render outputs/media-plans/*.md → docs/media-plans/*.html.

Mirror of render_playbook_html.py + render_drafts_html.py — re-uses the
same markdown renderer. Only differs in input/output directories + the
page tag label (so Joanne sees "Media Plan" instead of "Playbook" or "Draft").

WHY THIS EXISTS
    Path B's campaign-launch-strategist writes a full Meta + Google media
    plan as a markdown file to outputs/media-plans/. Joanne shouldn't have
    to open .md files in a code editor to read it — she needs an HTML page
    she can scroll through, the same way she opens playbook + draft pages
    from action briefs today.

INPUT
    outputs/media-plans/*.md (any media-plan markdown)

OUTPUT
    docs/media-plans/{slug}.html (served by GitHub Pages)
    state/media-plans-manifest.json (index for the dashboard)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "outputs" / "media-plans"
OUT_DIR = BASE_DIR / "docs" / "media-plans"
MANIFEST = BASE_DIR / "state" / "media-plans-manifest.json"

# Re-use the playbook renderer's markdown engine.
sys.path.insert(0, str(BASE_DIR / "scripts"))
import render_playbook_html as _rp  # noqa: E402


def render_one(md_path: Path) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = md_path.read_text(encoding="utf-8")
    slug = md_path.stem
    title = _rp._extract_title(md, slug.replace("-", " ").title())
    body_md = re.sub(r"^#\s+.+?\s*$", "", md, count=1, flags=re.M).lstrip()
    body_html = _rp._render_md(body_md)

    page = _rp._page(slug, body_html, title)
    page = page.replace("CB247 Playbook", "Media Plan")
    page = page.replace("outputs/playbooks/", "outputs/media-plans/")

    out_path = OUT_DIR / f"{slug}.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="Render a single media plan by filename (under outputs/media-plans/)")
    args = p.parse_args()

    if not SRC_DIR.exists():
        print(f"[render-media-plans] {SRC_DIR.relative_to(BASE_DIR)} not found — nothing to render")
        return 0

    files: list[Path]
    if args.file:
        target = SRC_DIR / args.file
        if not target.exists():
            print(f"[render-media-plans] {target} not found")
            return 1
        files = [target]
    else:
        files = sorted(SRC_DIR.glob("*.md"))

    manifest: dict = {"generated_at": datetime.now().isoformat(), "media_plans": {}}
    for f in files:
        out = render_one(f)
        manifest["media_plans"][f.stem] = {
            "source":        str(f.relative_to(BASE_DIR)),
            "rendered":      str(out.relative_to(BASE_DIR / "docs")),
            "size_bytes":    f.stat().st_size,
            "last_modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        }
        print(f"[render-media-plans] {f.name} → {out.relative_to(BASE_DIR)}")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"[render-media-plans] Wrote {len(files)} plan(s) · manifest at {MANIFEST.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
