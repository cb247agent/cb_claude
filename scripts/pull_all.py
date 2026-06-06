"""
pull_all.py — Runs all three Google data pipelines in sequence.
Saves GA4 + GSC + Google Ads data to state/*.json and timestamps last run.
Usage: python pull_all.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Fix: gRPC on macOS uses c-ares DNS resolver by default, which fails to resolve
# Google API hostnames (googleads.googleapis.com, analyticsdata.googleapis.com)
# in some network contexts. Force native macOS DNS resolver instead.
os.environ.setdefault("GRPC_DNS_RESOLVER", "native")

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
LAST_REFRESH = STATE_DIR / "last-refresh.json"


def log(msg, status="OK"):
    prefix = {"OK": "✅", "SKIP": "⏭", "FAIL": "❌"}.get(status, "ℹ")
    print(f"{prefix} {msg}")


def run_all():
    """Run GA4, GSC, and Google Ads pipelines in order."""
    print(f"\n{'='*50}")
    print(f"CB247 Google Data Pull — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    results = {}

    # GA4
    print("--- GA4 ---")
    try:
        import pull_ga4
        data = pull_ga4.pull_ga4()
        results["ga4"] = "success" if data else "no_data"
        log("GA4 pull complete")
    except Exception as e:
        results["ga4"] = f"error: {e}"
        log(f"GA4 pull failed: {e}", "FAIL")

    # GSC
    print("\n--- Google Search Console ---")
    try:
        import pull_gsc
        data = pull_gsc.pull_gsc()
        results["gsc"] = "success" if data else "no_data"
        log("GSC pull complete")
    except Exception as e:
        results["gsc"] = f"error: {e}"
        log(f"GSC pull failed: {e}", "FAIL")

    # Google Ads
    print("\n--- Google Ads ---")
    try:
        import pull_google_ads
        data = pull_google_ads.pull_google_ads()
        results["google_ads"] = "success" if data else "skipped"
        log("Google Ads pull complete" if data else "Google Ads skipped")
    except Exception as e:
        results["google_ads"] = f"error: {e}"
        log(f"Google Ads pull failed: {e}", "FAIL")

    # Google Business Profile
    print("\n--- Google Business Profile ---")
    try:
        import pull_gbp
        data = pull_gbp.pull_gbp()
        results["gbp"] = "success" if data else "skipped"
        log("GBP pull complete" if data else "GBP skipped (check API setup)")
    except Exception as e:
        results["gbp"] = f"error: {e}"
        log(f"GBP pull failed: {e}", "FAIL")

    # Meta Ads (Graph API → merges into ads-data.json under meta_ads)
    print("\n--- Meta Ads (Graph API) ---")
    try:
        import pull_meta
        data = pull_meta.pull_meta()
        results["meta_ads"] = "success" if data else "skipped"
        log("Meta Ads pull complete" if data else "Meta Ads skipped (token missing/expired)")
    except Exception as e:
        results["meta_ads"] = f"error: {e}"
        log(f"Meta Ads pull failed: {e}", "FAIL")

    # Ahrefs SEO data — EXCLUDED from daily refresh (unit cost control)
    # Ahrefs Lite plan: 100k units/month. Daily pulls would exhaust ~30k units/month on
    # a site this size. SEO rankings don't change day-to-day — weekly cadence is sufficient.
    # Ahrefs runs ONLY as part of the Monday weekly pipeline (weekly-report.sh Phase 1).
    # To run manually: python scripts/pull_ahrefs.py
    results["ahrefs"] = "skipped (weekly-only)"

    # Apify SERP + Google Maps — EXCLUDED from routine refresh (pay-per-event, cost control)
    # Apify runs ONLY as part of the Monday weekly pipeline (weekly-report.sh)
    # To run manually: python scripts/pull_apify.py
    results["apify"] = "skipped (weekly-only)"

    # Write last-refresh timestamp
    refresh_record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "human_readable": datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "results": results,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_REFRESH.write_text(json.dumps(refresh_record, indent=2))

    # ── Refresh dashboard data via inject scripts ──────────────────────────
    # Note: previously called bake-public-dashboard.py here, but that wipes
    # multi-business pages + Content Planner work + all uncommitted edits.
    # Inject scripts only refresh the data payloads inside <script id="..."> blocks
    # they own — leaving page structure, render functions, and Tier 1 work intact.
    # See: pending baker consolidation in MEMORY.md
    print("\n--- Refreshing dashboard data (inject scripts) ---")
    import subprocess, sys
    INJECT_SCRIPTS = [
        "inject-seo-extras.py",
        "inject-social-block.py",
        "inject-meta-ads.py",
        "inject-membership-data.py",
    ]
    for script in INJECT_SCRIPTS:
        try:
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "scripts" / script)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                log(f"inject: {script} OK")
            else:
                log(f"inject: {script} warning: {(result.stderr or result.stdout)[-200:]}", "SKIP")
        except Exception as e:
            log(f"inject: {script} skipped: {e}", "SKIP")

    print(f"\n{'='*50}")
    successes = [k for k, v in results.items() if v == "success"]
    print(f"Done. {len(successes)}/{len(results)} sources pulled successfully.")
    if successes:
        print(f"Success: {', '.join(successes)}")
    print(f"Refresh timestamp saved: {LAST_REFRESH}")
    print(f"{'='*50}\n")

    return results


if __name__ == "__main__":
    run_all()