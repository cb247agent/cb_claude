"""
visual_regression.py — Wave C (12 Jun 2026) — headless dashboard screenshots
+ pixel-level diff against committed baselines.

Catches the class of bugs Wave A + B can't see — visual ones:
  - A kanban card rendered in the wrong column
  - Modal popup spacing broken after a CSS change
  - Teal accent silently changed to a blue tone
  - Text overflow / cut-off on a specific page
  - A button moved 50px and isn't clickable

USAGE
    # Full run — diff every page against committed baseline
    .venv/bin/python3.13 scripts/visual_regression.py

    # First-time setup: capture baselines from the current local build
    .venv/bin/python3.13 scripts/visual_regression.py --update-baselines

    # Against the live deployed dashboard (what cron uses)
    .venv/bin/python3.13 scripts/visual_regression.py --source live

    # Strict mode — exit 1 on any diff > THRESHOLD
    .venv/bin/python3.13 scripts/visual_regression.py --strict

WHERE BASELINES LIVE
    docs/baselines/{page}.png is the committed reference.
    After an INTENTIONAL UI change, re-run with --update-baselines and
    commit the new images. Reviewable in git PRs the same way code changes
    are — image diff renders inline on GitHub.

EXIT CODES
    0 = clean (or warn-only with findings)
    1 = --strict + diffs > threshold
    2 = the script itself errored

CALLED BY
    - scripts/qa.sh  (one-shot pre-push QA)
    - scripts/weekly-report.sh Step 1m  (against the live deployed dashboard)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
BASE_DIR = _HERE.parent
BASELINES_DIR = BASE_DIR / "docs" / "baselines"
CURRENT_DIR   = BASE_DIR / "logs" / "visual-regression-current"
DIFF_DIR      = BASE_DIR / "logs" / "visual-regression-diff"
LOG_DIR       = BASE_DIR / "logs"

# Diff threshold — % of pixels that differ before we flag it. Tuned for
# CB247: the dashboard has dynamic content (weekly numbers change) so we
# expect SOME drift week-on-week. >2% suggests a structural change.
DIFF_THRESHOLD_PCT = 2.0

# Dashboard URLs
LIVE_URL  = "https://cb247agent.github.io/cb_claude/"
LOCAL_URL = "file://" + str(BASE_DIR / "docs" / "index.html")

# Pages to screenshot (CB247 only — MWCC + KB pages can be added later).
# Each entry: (slug, data-page selector value, optional pre-shoot wait)
# The "pre" key gives the renderer extra time on data-heavy pages.
PAGES: list[dict] = [
    {"slug": "overview",          "data_page": "overview"},
    {"slug": "membership",        "data_page": "cb247-membership"},
    {"slug": "seo",               "data_page": "seo"},
    {"slug": "google-ads",        "data_page": "google-ads"},
    {"slug": "organic-social",    "data_page": "organic-social"},
    {"slug": "meta-ads",          "data_page": "meta-ads"},
    {"slug": "gbp",               "data_page": "gbp"},
    {"slug": "promo-pipeline",    "data_page": "promo-pipeline"},
    {"slug": "asset-library",     "data_page": "asset-library"},
    {"slug": "work-queue",        "data_page": "content-planner"},
    {"slug": "performance-review","data_page": "content-review"},
]

# Viewport — desktop default, what the team mostly uses
VIEWPORT = {"width": 1440, "height": 900}


# ── Screenshot capture ──────────────────────────────────────────────────────


async def _capture_all(source_url: str, out_dir: Path) -> list[str]:
    """Launch headless Chromium, navigate to source, screenshot each page.
    Returns list of slugs successfully captured."""
    out_dir.mkdir(parents=True, exist_ok=True)
    captured: list[str] = []

    from playwright.async_api import async_playwright   # local import — keeps import light when only diffing

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
            page = await ctx.new_page()
            print(f"[visreg] Loading {source_url} ...")
            await page.goto(source_url, wait_until="networkidle", timeout=30_000)
            # Dashboard has localStorage caches + Supabase realtime subscriptions
            # that finish rendering ~1-2s after networkidle. Wait for the SPA
            # to settle.
            await page.wait_for_timeout(2500)

            for spec in PAGES:
                slug      = spec["slug"]
                data_page = spec["data_page"]
                target    = out_dir / f"{slug}.png"

                # Click the sidebar nav item via its data-page attribute
                try:
                    await page.click(f'[data-page="{data_page}"]', timeout=5_000)
                except Exception as e:
                    print(f"[visreg] ⚠️  Could not click [data-page='{data_page}']: {e}")
                    continue

                # Wait for render — the dashboard has staged content loads
                await page.wait_for_timeout(1500)
                # Full-page screenshot so we see EVERYTHING, including
                # below-the-fold (kanban often extends past viewport)
                await page.screenshot(path=str(target), full_page=True)
                print(f"[visreg] ✓ captured {slug:<24s} → {target.relative_to(BASE_DIR)}")
                captured.append(slug)

            await ctx.close()
        finally:
            await browser.close()

    return captured


# ── Image diffing ───────────────────────────────────────────────────────────


def _diff_images(baseline_path: Path, current_path: Path, out_path: Path) -> dict:
    """Compare two PNGs pixel by pixel. Returns dict with diff stats."""
    from PIL import Image, ImageChops

    a = Image.open(baseline_path).convert("RGB")
    b = Image.open(current_path).convert("RGB")

    # If sizes differ, normalise to the SMALLER of the two so we can still
    # compute a meaningful overlap. Different sizes also count as drift,
    # so flag separately.
    size_drift = (a.size != b.size)
    if size_drift:
        target_size = (
            min(a.size[0], b.size[0]),
            min(a.size[1], b.size[1]),
        )
        a = a.crop((0, 0, *target_size))
        b = b.crop((0, 0, *target_size))

    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()

    # Count differing pixels (any channel non-zero)
    pixels = list(diff.getdata())
    diff_count = sum(1 for r, g, b_ in pixels if r != 0 or g != 0 or b_ != 0)
    total = len(pixels)
    diff_pct = (diff_count / total * 100) if total else 0.0

    # Write a visualisation: side-by-side, with diff highlighted
    if diff_count > 0:
        from PIL import Image as I
        composite = I.new("RGB", (a.size[0] * 3 + 20, a.size[1]), (255, 255, 255))
        composite.paste(a, (0, 0))
        composite.paste(b, (a.size[0] + 10, 0))
        # Diff in red on black
        diff_red = I.new("RGB", a.size, (0, 0, 0))
        red = I.new("RGB", a.size, (255, 0, 0))
        mask = diff.convert("L").point(lambda p: 255 if p > 0 else 0)
        diff_red.paste(red, (0, 0), mask)
        composite.paste(diff_red, (a.size[0] * 2 + 20, 0))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        composite.save(out_path)

    return {
        "size_drift":      size_drift,
        "diff_pixels":     diff_count,
        "total_pixels":    total,
        "diff_pct":        round(diff_pct, 3),
        "bbox":            list(bbox) if bbox else None,
        "viz":             str(out_path.relative_to(BASE_DIR)) if diff_count > 0 else None,
    }


# ── Orchestration ───────────────────────────────────────────────────────────


def _run_diff_pass(captured_slugs: list[str]) -> list[dict]:
    """For each captured slug, diff against the committed baseline.
    Returns list of findings (one per page)."""
    findings: list[dict] = []
    for slug in captured_slugs:
        baseline = BASELINES_DIR / f"{slug}.png"
        current  = CURRENT_DIR / f"{slug}.png"
        diff     = DIFF_DIR / f"{slug}.png"

        if not baseline.exists():
            findings.append({
                "slug":     slug,
                "severity": "WARN",
                "kind":     "no-baseline",
                "detail":   f"No baseline for {slug}. Run --update-baselines to seed.",
            })
            continue

        if not current.exists():
            findings.append({
                "slug":     slug,
                "severity": "ERROR",
                "kind":     "capture-missing",
                "detail":   f"Capture step did not produce {current.relative_to(BASE_DIR)}.",
            })
            continue

        stats = _diff_images(baseline, current, diff)
        sev = "INFO" if stats["diff_pct"] < DIFF_THRESHOLD_PCT else "ERROR"

        findings.append({
            "slug":          slug,
            "severity":      sev,
            "kind":          "diff" if stats["diff_pct"] > 0 else "match",
            "diff_pct":      stats["diff_pct"],
            "size_drift":    stats["size_drift"],
            "viz":           stats["viz"],
            "detail":        (
                f"{stats['diff_pct']:.2f}% pixels differ "
                f"({stats['diff_pixels']}/{stats['total_pixels']})"
                + (" · SIZE drifted" if stats["size_drift"] else "")
            ),
        })

    return findings


def _update_baselines(captured_slugs: list[str]) -> int:
    """Copy captured images over the committed baselines."""
    import shutil
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    updated = 0
    for slug in captured_slugs:
        src = CURRENT_DIR / f"{slug}.png"
        dst = BASELINES_DIR / f"{slug}.png"
        if src.exists():
            shutil.copy2(src, dst)
            updated += 1
            print(f"[visreg] baseline updated · {slug}.png")
    return updated


def main() -> int:
    p = argparse.ArgumentParser(description="Visual regression for the CB247 dashboard")
    p.add_argument("--source", choices=["local", "live"], default="local",
                   help="Which dashboard to screenshot (default: local docs/index.html)")
    p.add_argument("--update-baselines", action="store_true",
                   help="Save current captures as new baselines (use after intentional UI changes)")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 if any page exceeds DIFF_THRESHOLD_PCT")
    p.add_argument("--log", action="store_true",
                   help="Write findings JSON to logs/visual-regression-<date>.json")
    args = p.parse_args()

    source_url = LIVE_URL if args.source == "live" else LOCAL_URL
    print(f"[visreg] mode: {args.source}  ·  threshold: {DIFF_THRESHOLD_PCT}% pixel delta")

    # Step 1 — capture current screenshots
    captured = asyncio.run(_capture_all(source_url, CURRENT_DIR))
    print(f"[visreg] captured {len(captured)}/{len(PAGES)} pages")

    if args.update_baselines:
        n = _update_baselines(captured)
        print()
        print(f"[visreg] ✅ {n} baseline(s) updated. Commit docs/baselines/ to lock in.")
        return 0

    # Step 2 — diff against committed baselines
    findings = _run_diff_pass(captured)

    errors = [f for f in findings if f["severity"] == "ERROR"]
    warns  = [f for f in findings if f["severity"] == "WARN"]
    infos  = [f for f in findings if f["severity"] == "INFO"]

    print()
    print(f"[visreg] Findings: {len(errors)} ERROR · {len(warns)} WARN · {len(infos)} INFO")
    print()
    for f in findings:
        prefix = {"ERROR": "❌", "WARN": "⚠️ ", "INFO": "ℹ️ "}[f["severity"]]
        print(f"  {prefix} {f['slug']:<24s} {f['detail']}")
        if f.get("viz"):
            print(f"     side-by-side: {f['viz']}")

    if args.log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"visual-regression-{datetime.now().strftime('%Y-%m-%d')}.json"
        log_path.write_text(json.dumps({
            "ran_at":   datetime.utcnow().isoformat() + "Z",
            "source":   args.source,
            "threshold_pct": DIFF_THRESHOLD_PCT,
            "findings": findings,
        }, indent=2))
        print()
        print(f"[visreg] log → {log_path.relative_to(BASE_DIR)}")

    if args.strict and errors:
        print()
        print(f"[visreg] ❌ --strict + {len(errors)} above-threshold diff(s) → exit 1")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[visreg] ERROR: {e}", file=sys.stderr)
        sys.exit(2)
