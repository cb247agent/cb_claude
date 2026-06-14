"""
inject_paid_ad_lists.py — embed lists of available Meta + Google Ads drafts
into docs/index.html so the View Brief renderer only shows the "View AI
Draft" button when the draft actually exists.

INPUT
    outputs/meta-ads/*.md          (Meta ad drafts)
    outputs/google-ads-rsa/*.md    (Google Ads RSA drafts)
    outputs/gbp-posts/*.md         (GBP post drafts — added 13 Jun 2026)

OUTPUT
    docs/index.html — injects a <script id="paid-ad-list-block"> tag that
    sets:
        window.AI_META_ADS    = [slug1, slug2, ...]
        window.AI_GOOGLE_RSAS = [slug1, slug2, ...]
        window.AI_GBP_POSTS   = [slug1, slug2, ...]

WHY THE rfind() PATTERN
    docs/index.html contains a JS template literal inside
    _renderProposedActionBriefHTML(row) that includes the literal string
    </body> (because the brief is a full HTML doc rendered into a blob://
    tab). A naive str.replace('</body>', ...) would corrupt that template
    literal — and DID, on 2026-06-13 (see Agent-Learnings.md). Always use
    rfind() so the splice happens at the file's ACTUAL closing </body>.

WHEN IT RUNS
    Wired into phase1c_content_drafter.sh — runs after render_content_html.py
    so the embedded lists always reflect what's actually been drafted.
"""

import json
import re
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
META_DIR    = BASE_DIR / "outputs" / "meta-ads"
GADS_DIR    = BASE_DIR / "outputs" / "google-ads-rsa"
GBP_DIR     = BASE_DIR / "outputs" / "gbp-posts"
TREND_DIR   = BASE_DIR / "outputs" / "trend-rides"
INDEX_PATH  = BASE_DIR / "docs" / "index.html"


def slugs_in(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.md") if p.is_file())


# 14 Jun 2026 — extract "Posting Schedule" block from each trend-ride .md
# so the action-list row can render a "Wed 17:30" chip without forcing the
# user to click into View AI Draft. Returns slug → {day, time, platform}.
_DAY_RE      = re.compile(r"-\s*Best\s*day:\s*([^\n]+)", re.IGNORECASE)
_TIME_RE     = re.compile(r"-\s*Best\s*time:\s*([^\n]+)", re.IGNORECASE)
_PLATFORM_RE = re.compile(r"-\s*Platform:\s*([^\n]+)", re.IGNORECASE)


def trend_ride_meta(directory: Path) -> dict[str, dict]:
    if not directory.exists():
        return {}
    out: dict[str, dict] = {}
    for p in sorted(directory.glob("*.md")):
        if not p.is_file():
            continue
        body = p.read_text(encoding="utf-8")
        day_m  = _DAY_RE.search(body)
        time_m = _TIME_RE.search(body)
        plat_m = _PLATFORM_RE.search(body)
        if not (day_m or time_m):
            continue
        out[p.stem] = {
            "day":      (day_m.group(1).strip()  if day_m  else ""),
            "time":     (time_m.group(1).strip() if time_m else ""),
            "platform": (plat_m.group(1).strip() if plat_m else ""),
        }
    return out


def inject() -> None:
    meta_slugs  = slugs_in(META_DIR)
    gads_slugs  = slugs_in(GADS_DIR)
    gbp_slugs   = slugs_in(GBP_DIR)
    trend_slugs = slugs_in(TREND_DIR)
    trend_meta  = trend_ride_meta(TREND_DIR)

    html = INDEX_PATH.read_text(encoding="utf-8")
    new_block = (
        '<script id="paid-ad-list-block">\n'
        '// CB247 available Meta + Google RSA + GBP post drafts — auto-generated\n'
        '// by scripts/inject_paid_ad_lists.py (runs from phase1c).\n'
        '// Brief renderer checks these lists before showing "View AI Draft".\n'
        f'window.AI_META_ADS    = {json.dumps(meta_slugs)};\n'
        f'window.AI_GOOGLE_RSAS = {json.dumps(gads_slugs)};\n'
        f'window.AI_GBP_POSTS   = {json.dumps(gbp_slugs)};\n'
        f'window.AI_TREND_RIDES = {json.dumps(trend_slugs)};\n'
        '// 14 Jun 2026 — slug → {day, time, platform} so the action row can\n'
        '// render a "Wed 17:30" chip without the user opening View AI Draft.\n'
        f'window.AI_TREND_RIDE_META = {json.dumps(trend_meta)};\n'
        '</script>'
    )

    if 'id="paid-ad-list-block"' in html:
        updated = re.sub(
            r'<script id="paid-ad-list-block">.*?</script>',
            lambda _: new_block,
            html,
            flags=re.DOTALL,
        )
        action = "replaced"
    else:
        # CRITICAL: use rfind() to splice at the file's ACTUAL closing </body>.
        # The brief renderer JS includes a template literal containing </body>
        # mid-function — str.replace would corrupt it.
        idx = html.rfind("</body>")
        if idx >= 0:
            updated = html[:idx] + new_block + "\n" + html[idx:]
            action = "inserted (at rightmost </body>)"
        else:
            updated = html + "\n" + new_block
            action = "appended"

    if updated == html:
        print("[paid-ad-list] WARN — no change to docs/index.html")
        return

    INDEX_PATH.write_text(updated, encoding="utf-8")
    print(f"[paid-ad-list] OK — {action} · meta={len(meta_slugs)} · gads={len(gads_slugs)} · gbp={len(gbp_slugs)} · trends={len(trend_slugs)}")


if __name__ == "__main__":
    inject()
