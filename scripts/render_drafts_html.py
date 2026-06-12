"""
render_drafts_html.py — Render outputs/drafts/*.md → docs/drafts/*.html.

Mirror of render_playbook_html.py for the deliverable-drafter agent's
output. Re-uses the markdown renderer; only differs in input/output
directories + page tag label.

WHY THIS EXISTS
    Tia's principle: "agentic AI = pre-drafted action delivered to
    human. Human role = check + tweak + approve + execute, not write
    from scratch." When the deliverable-drafter agent produces an EDM /
    SMS / social-caption / ad-copy draft as a markdown file, this
    script converts it into a CB247-styled HTML page Angela / Joanne /
    Tia can view via the brief's "View the draft" button.

INPUT
    outputs/drafts/*.md (any markdown draft — edm-* / sms-* /
    social-* / ad-* prefixes are conventions, not requirements)

OUTPUT
    docs/drafts/{slug}.html — served by GitHub Pages
    state/drafts-manifest.json — index for the dashboard
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "outputs" / "drafts"
OUT_DIR = BASE_DIR / "docs" / "drafts"
MANIFEST = BASE_DIR / "state" / "drafts-manifest.json"

# Re-use render_playbook_html's converter. Both produce CB247-styled
# HTML pages from the same markdown subset.
sys.path.insert(0, str(BASE_DIR / "scripts"))
import render_playbook_html as _rp   # noqa: E402


def _tag_label(slug: str) -> str:
    """Convert a slug prefix into a human-readable tag for the hero."""
    if slug.startswith("edm-"):    return "EDM Draft"
    if slug.startswith("sms-"):    return "SMS Draft"
    if slug.startswith("social-"): return "Social Post Draft"
    if slug.startswith("ad-"):     return "Ad Copy Draft"
    return "Draft"


def render_one(md_path: Path) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = md_path.read_text(encoding="utf-8")
    slug = md_path.stem
    title = _rp._extract_title(md, slug.replace("-", " ").title())
    body_md = re.sub(r"^#\s+.+?\s*$", "", md, count=1, flags=re.M).lstrip()
    body_html = _rp._render_md(body_md)

    # Build the page using the playbook shell, then swap the hero tag
    # label so Angela knows at a glance whether she's looking at an
    # EDM / SMS / Social / Ad draft.
    page = _rp._page(slug, body_html, title)
    page = page.replace("CB247 Playbook", _tag_label(slug))
    page = page.replace("outputs/playbooks/", "outputs/drafts/")

    out_path = OUT_DIR / f"{slug}.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="Render a single draft by filename (under outputs/drafts/)")
    args = p.parse_args()

    if not SRC_DIR.exists():
        print(f"[render-drafts] {SRC_DIR.relative_to(BASE_DIR)} not found — nothing to render")
        return 0

    files: list[Path]
    if args.file:
        target = SRC_DIR / args.file
        if not target.exists():
            print(f"[render-drafts] {target} not found")
            return 1
        files = [target]
    else:
        files = sorted(SRC_DIR.glob("*.md"))

    manifest: dict = {"generated_at": datetime.now().isoformat(), "drafts": {}}
    for f in files:
        out = render_one(f)
        manifest["drafts"][f.stem] = {
            "type": _tag_label(f.stem),
            "source": str(f.relative_to(BASE_DIR)),
            "rendered": str(out.relative_to(BASE_DIR / "docs")),
            "size_bytes": f.stat().st_size,
            "last_modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        }
        print(f"[render-drafts] {f.name} → {out.relative_to(BASE_DIR)}")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"[render-drafts] Wrote {len(files)} draft(s) · manifest at {MANIFEST.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
