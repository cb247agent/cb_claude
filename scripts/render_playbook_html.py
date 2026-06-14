"""
render_playbook_html.py — Render outputs/playbooks/*.md as styled HTML
pages at docs/playbooks/*.html so non-technical team members (Angela,
Reception, Joanne) can view playbooks via the dashboard.

WHY THIS EXISTS
    The membership-strategist's "Run save-call programme" / "Refresh
    Unsure-objection playbook" actions reference markdown files at
    outputs/playbooks/*.md. Angela can't open .md files. This script
    converts each one into a CB247-styled HTML page that the brief's
    "View the playbook" button links to.

    Pairs with agents/playbook-writer.yml — the writer agent produces
    the .md, this renders it as HTML on the same weekly cycle.

INPUT
    outputs/playbooks/*.md (any markdown file)

OUTPUT
    docs/playbooks/{slug}.html — served by GitHub Pages
    state/playbooks-manifest.json — index of {slug → path + date + size}

USAGE
    python scripts/render_playbook_html.py
    python scripts/render_playbook_html.py --file dont-quit-winter-save-call.md

Wired into scripts/phases/phase1_data.sh after the playbook-writer agent
runs, before the briefs regenerate.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date as _date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "outputs" / "playbooks"
OUT_DIR = BASE_DIR / "docs" / "playbooks"
MANIFEST = BASE_DIR / "state" / "playbooks-manifest.json"

TEAL       = "#3FA69A"
TEAL_DEEP  = "#2d7d72"
TEAL_MIST  = "#f0fdf4"
DARK       = "#1a1a2e"


# ─── minimal markdown → HTML renderer ────────────────────────────────────
# Handles the subset of markdown the CB247 playbooks actually use:
# headings (# / ## / ###), bold (**), italic (*), inline code (`),
# fenced code (```), unordered lists (- / *), ordered lists (1.),
# blockquotes (>), horizontal rules (---), links [t](url), pipe tables.
def _render_md(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    in_code = False
    code_lang = ""
    code_buf: list[str] = []
    list_stack: list[str] = []   # 'ul' or 'ol'
    para_buf: list[str] = []

    def flush_para():
        if para_buf:
            txt = " ".join(para_buf).strip()
            if txt:
                out.append(f"<p>{_inline(txt)}</p>")
            para_buf.clear()

    def close_lists():
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    def open_list(kind: str):
        if list_stack and list_stack[-1] == kind:
            return
        close_lists()
        list_stack.append(kind)
        out.append(f"<{kind}>")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code
        m = re.match(r"^```(\w*)\s*$", line)
        if m:
            if in_code:
                out.append(f'<pre class="code"><code>{html.escape(chr(10).join(code_buf))}</code></pre>')
                code_buf.clear()
                in_code = False
                code_lang = ""
            else:
                flush_para()
                close_lists()
                in_code = True
                code_lang = m.group(1)
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # Table (simple pipe table)
        if i + 1 < len(lines) and "|" in line and re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", lines[i + 1]):
            flush_para()
            close_lists()
            header_cells = [_inline(c.strip()) for c in line.strip().strip("|").split("|")]
            out.append("<table>")
            out.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in header_cells) + "</tr></thead>")
            i += 2  # skip header + separator
            out.append("<tbody>")
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                row_cells = [_inline(c.strip()) for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{c}</td>" for c in row_cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue

        # Headings
        if m := re.match(r"^(#{1,6})\s+(.+?)\s*$", line):
            flush_para()
            close_lists()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^\s*---+\s*$", line) or re.match(r"^\s*\*\*\*+\s*$", line):
            flush_para()
            close_lists()
            out.append("<hr>")
            i += 1
            continue

        # Blockquote
        if line.startswith(">"):
            flush_para()
            close_lists()
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_lines.append(lines[i].lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + _inline(" ".join(quote_lines)) + "</blockquote>")
            continue

        # Lists
        if m := re.match(r"^\s*[\-\*]\s+(.+?)\s*$", line):
            flush_para()
            open_list("ul")
            out.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue
        if m := re.match(r"^\s*\d+\.\s+(.+?)\s*$", line):
            flush_para()
            open_list("ol")
            out.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        # Blank line → end paragraph
        if line.strip() == "":
            flush_para()
            close_lists()
            i += 1
            continue

        # Default: accumulate into paragraph
        para_buf.append(line.strip())
        i += 1

    flush_para()
    close_lists()
    return "\n".join(out)


def _inline(s: str) -> str:
    """Inline markdown: bold, italic, code, images, links. Order matters."""
    # Escape HTML first
    s = html.escape(s, quote=False)
    # Inline code (must come before bold/italic to protect backtick content)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    # Bold then italic
    s = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\w)\*([^\*]+)\*(?!\w)", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", s)
    # Images — MUST come before links (links would match the [alt](src) part
    # and leave a stray "!" otherwise). 14 Jun 2026 — added to support
    # asset previews in trend-ride + content drafts.
    s = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        r'<img src="\2" alt="\1" style="max-width:520px;width:100%;height:auto;border-radius:8px;border:1px solid #e5e7eb;display:block;margin:14px 0">',
        s,
    )
    # Links
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank">\1</a>', s)
    return s


# ─── page shell ──────────────────────────────────────────────────────────
def _page(slug: str, body: str, title_h1: str) -> str:
    today = _date.today().isoformat()
    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width,initial-scale=1.0'>
<title>{html.escape(title_h1)} · CB247 Playbook</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f2f5;color:{DARK};line-height:1.65}}
  .page{{max-width:880px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 0 32px rgba(0,0,0,.05)}}
  .hero{{background:linear-gradient(135deg,{DARK} 0%,#2a2a4e 100%);color:#fff;padding:32px 44px}}
  .hero-tag{{display:inline-block;font-size:11px;color:{TEAL};font-weight:700;letter-spacing:2px;text-transform:uppercase;background:rgba(63,166,154,.15);padding:5px 12px;border-radius:99px;margin-bottom:10px}}
  .hero h1{{font-size:26px;font-weight:800;line-height:1.3}}
  .hero-sub{{font-size:12.5px;color:rgba(255,255,255,.65);margin-top:10px}}
  main{{padding:32px 44px}}
  main h1{{font-size:22px;font-weight:800;margin:28px 0 12px;color:{DARK}}}
  main h2{{font-size:18px;font-weight:700;margin:24px 0 10px;padding-bottom:6px;border-bottom:2px solid {TEAL};display:inline-block;color:{DARK}}}
  main h3{{font-size:14.5px;font-weight:700;margin:18px 0 8px;color:{TEAL_DEEP};text-transform:uppercase;letter-spacing:.04em}}
  main h4{{font-size:13.5px;font-weight:700;margin:14px 0 6px;color:{DARK}}}
  main p{{margin:0 0 12px;font-size:13.5px}}
  main ul,main ol{{margin:0 0 14px;padding-left:24px;font-size:13.5px}}
  main li{{margin-bottom:5px}}
  main blockquote{{background:{TEAL_MIST};border-left:4px solid {TEAL};padding:12px 16px;margin:14px 0;border-radius:0 6px 6px 0;font-size:14px;color:{DARK};font-style:italic;font-weight:600}}
  main hr{{border:none;border-top:1px solid #e5e7eb;margin:24px 0}}
  main code{{background:#f3f4f6;color:{TEAL_DEEP};padding:1px 6px;border-radius:3px;font-family:Menlo,Monaco,monospace;font-size:11.5px}}
  main pre.code{{background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:12px 14px;overflow-x:auto;margin:0 0 14px}}
  main pre.code code{{background:none;color:{DARK};padding:0}}
  main a{{color:{TEAL_DEEP};font-weight:600}}
  main table{{width:100%;border-collapse:collapse;font-size:12.5px;margin:0 0 14px}}
  main thead{{background:{TEAL_MIST}}}
  main th{{padding:8px 10px;text-align:left;font-size:10.5px;color:{TEAL_DEEP};text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #d1fae5}}
  main td{{padding:9px 10px;border-bottom:1px solid #f0f2f5;vertical-align:top}}
  main strong{{color:{DARK}}}
  .footer{{padding:18px 44px;text-align:center;background:#fafbfc;border-top:1px solid #f0f2f5}}
  .footer a{{display:inline-block;background:{TEAL_DEEP};color:#fff;text-decoration:none;padding:11px 24px;border-radius:6px;font-size:13px;font-weight:700}}
  .footer .meta{{font-size:10.5px;color:#9ca3af;margin-top:10px}}
  @media print{{
    body{{background:#fff}}
    .hero{{background:{DARK} !important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
    .footer a{{display:none}}
  }}
</style>
</head>
<body>
<div class='page'>
  <header class='hero'>
    <div class='hero-tag'>CB247 Playbook</div>
    <h1>{html.escape(title_h1)}</h1>
    <div class='hero-sub'>Rendered {today} · source: <code style='background:rgba(255,255,255,.1);color:rgba(255,255,255,.85);padding:2px 6px;border-radius:3px'>outputs/playbooks/{html.escape(slug)}.md</code></div>
  </header>
  <main>
{body}
  </main>
  <div class='footer'>
    <a href='https://cb247agent.github.io/cb_claude/'>← Back to Marketing OS</a>
    <div class='meta'>CB247 Marketing OS · Playbook · Rendered {today}</div>
  </div>
</div>
</body>
</html>"""


def _extract_title(md: str, fallback: str) -> str:
    """Pull the first H1 as the page title."""
    if m := re.search(r"^#\s+(.+?)\s*$", md, flags=re.M):
        return m.group(1)
    return fallback


def render_one(md_path: Path) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = md_path.read_text(encoding="utf-8")
    slug = md_path.stem
    # Strip the first H1 so the hero owns it (avoid double titles)
    title = _extract_title(md, slug.replace("-", " ").title())
    body_md = re.sub(r"^#\s+.+?\s*$", "", md, count=1, flags=re.M).lstrip()
    body_html = _render_md(body_md)
    page = _page(slug, body_html, title)
    out_path = OUT_DIR / f"{slug}.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="Render a single playbook by filename (under outputs/playbooks/)")
    args = p.parse_args()

    if not SRC_DIR.exists():
        print(f"[render-playbook] {SRC_DIR.relative_to(BASE_DIR)} not found — nothing to render")
        return 0

    files: list[Path]
    if args.file:
        target = SRC_DIR / args.file
        if not target.exists():
            print(f"[render-playbook] {target} not found")
            return 1
        files = [target]
    else:
        files = sorted(SRC_DIR.glob("*.md"))

    manifest: dict = {"generated_at": datetime.now().isoformat(), "playbooks": {}}
    for f in files:
        out = render_one(f)
        manifest["playbooks"][f.stem] = {
            "source": str(f.relative_to(BASE_DIR)),
            "rendered": str(out.relative_to(BASE_DIR / "docs")),
            "size_bytes": f.stat().st_size,
            "last_modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        }
        print(f"[render-playbook] {f.name} → {out.relative_to(BASE_DIR)}")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"[render-playbook] Wrote {len(files)} playbook(s) · manifest at {MANIFEST.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
