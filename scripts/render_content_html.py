"""
render_content_html.py — render Path C content drafts to viewable HTML.

Mirror of render_playbook_html.py + render_drafts_html.py + render_media_plan_html.py.
Re-uses the same markdown engine. Only differs in:
  - Reads from 3 source folders: outputs/blogs/, outputs/landing-pages/,
    outputs/service-pages/
  - Writes to 3 docs folders matching each
  - Page tag label depends on which folder the source came from

WHY THIS EXISTS
    Path C's content-writer agent produces blog / landing page / service
    page drafts as markdown. John (SEO QC) and Angela (brand QC) shouldn't
    have to open .md files to review them. This script converts each
    draft into a CB247-styled HTML page they can read in the browser via
    the action brief's "View the draft" button.

INPUT
    outputs/blogs/*.md
    outputs/landing-pages/*.md
    outputs/service-pages/*.md

OUTPUT
    docs/blogs/{slug}.html
    docs/landing-pages/{slug}.html
    docs/service-pages/{slug}.html
    state/content-manifest.json (combined index for the dashboard)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

CONTENT_DIRS = [
    ("blogs",          "blog"),
    ("landing-pages",  "landing_page"),
    ("service-pages",  "service_page"),
    ("seo-refreshes",  "seo_refresh"),    # 13 Jun 2026 — Path D: AI-drafted H1/title/FAQ/internal-link refresh for existing pages
    ("meta-ads",       "meta_ad"),        # 13 Jun 2026 — Path E: AI-drafted Meta ad copy (primary text, headlines, descriptions, CTA, audience)
    ("google-ads-rsa", "google_rsa"),     # 13 Jun 2026 — Path E: AI-drafted Google RSA copy (15 headlines, 4 descs, sitelinks, callouts)
    ("gbp-posts",      "gbp_post"),       # 13 Jun 2026 — Path E: AI-drafted GBP post copy (body × 2, CTA, image brief, per-location)
]

TAG_LABEL = {
    "blog":         "Blog Draft",
    "landing_page": "Landing Page Draft",
    "service_page": "Service Page Draft",
    "seo_refresh":  "SEO Refresh Draft",
    "meta_ad":      "Meta Ad Draft",
    "google_rsa":   "Google RSA Draft",
    "gbp_post":     "GBP Post Draft",
}

# Re-use the playbook renderer's markdown engine
sys.path.insert(0, str(BASE_DIR / "scripts"))
import render_playbook_html as _rp  # noqa: E402


def _strip_frontmatter(md: str) -> str:
    """Drop the YAML front-matter block at the top — it's metadata, not body."""
    return re.sub(r"^---\s*\n.*?\n---\s*\n", "", md, count=1, flags=re.DOTALL)


def render_one(md_path: Path, fmt: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = md_path.read_text(encoding="utf-8")
    body_md = _strip_frontmatter(md)
    slug = md_path.stem
    title = _rp._extract_title(body_md, slug.replace("-", " ").title())
    body_md = re.sub(r"^#\s+.+?\s*$", "", body_md, count=1, flags=re.M).lstrip()
    body_html = _rp._render_md(body_md)

    page = _rp._page(slug, body_html, title)
    page = page.replace("CB247 Playbook", TAG_LABEL.get(fmt, "Content Draft"))
    page = page.replace("outputs/playbooks/", f"outputs/{md_path.parent.name}/")

    out_path = out_dir / f"{slug}.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="Render a single content file by relative path (e.g. blogs/X.md)")
    args = p.parse_args()

    manifest: dict = {"generated_at": datetime.now().isoformat(), "content": {}}
    total = 0

    for src_subdir, fmt in CONTENT_DIRS:
        src_dir = BASE_DIR / "outputs" / src_subdir
        out_dir = BASE_DIR / "docs" / src_subdir
        if not src_dir.exists():
            print(f"[render-content] {src_dir.relative_to(BASE_DIR)} not found — skipping")
            continue

        if args.file:
            target = BASE_DIR / "outputs" / args.file
            if target.parent.name != src_subdir or not target.exists():
                continue
            files = [target]
        else:
            files = sorted(src_dir.glob("*.md"))

        for f in files:
            out = render_one(f, fmt, out_dir)
            manifest["content"][f.stem] = {
                "format":        fmt,
                "source":        str(f.relative_to(BASE_DIR)),
                "rendered":      str(out.relative_to(BASE_DIR / "docs")),
                "size_bytes":    f.stat().st_size,
                "last_modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
            print(f"[render-content] {f.name} → {out.relative_to(BASE_DIR)}")
            total += 1

    manifest_path = BASE_DIR / "state" / "content-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[render-content] Wrote {total} content draft(s) · manifest at {manifest_path.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
