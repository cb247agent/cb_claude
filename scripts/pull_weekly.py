"""
pull_weekly.py — Runs paid-source data pulls (Google Ads, Meta Ads).

These sources have quota/credit costs, so they're EXCLUDED from the 4×/day
launchd data-refresh job (which runs pull_all.py for free Google APIs only)
and ONLY pulled once per week as part of the Monday weekly-report.sh cron.

What runs:
    pull_google_ads   — Google Ads API (quota-limited, Basic access pending Standard)
    pull_meta         — Meta Ads Graph API (rate-limited)

What does NOT run:
    pull_ahrefs   — frozen snapshot (out of credits); refresh manually
                    when subscription tops up
    pull_apify    — already weekly via weekly-report.sh Step 1c

Usage:
    python scripts/pull_weekly.py                   # full weekly pull
    python scripts/pull_weekly.py --skip-google-ads # Meta only
    python scripts/pull_weekly.py --skip-meta       # Google Ads only

Called from: scripts/weekly-report.sh Step 1a (Monday 10:00 AM AWST)
Created: 06 Jun 2026 as part of pull-cadence split (see pull_all.py header).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Fix: gRPC on macOS uses c-ares DNS resolver by default, which fails to resolve
# Google API hostnames in some network contexts. Force native macOS DNS resolver.
os.environ.setdefault("GRPC_DNS_RESOLVER", "native")

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
WEEKLY_LAST_REFRESH = STATE_DIR / "last-weekly-refresh.json"


def log(msg, status="OK"):
    prefix = {"OK": "✅", "SKIP": "⏭", "FAIL": "❌"}.get(status, "ℹ")
    print(f"{prefix} {msg}")


def run_weekly(skip_google_ads=False, skip_meta=False):
    """Run paid-source data pulls (Google Ads + Meta)."""
    print(f"\n{'='*50}")
    print(f"CB247 Weekly Paid-Source Pull — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    # Add scripts/ to sys.path so we can import sibling pull_* modules
    sys.path.insert(0, str(BASE_DIR / "scripts"))

    results = {}

    # Google Ads — quota-limited
    if skip_google_ads:
        results["google_ads"] = "skipped (flag)"
        log("Google Ads SKIPPED via --skip-google-ads flag", "SKIP")
    else:
        print("--- Google Ads ---")
        try:
            import pull_google_ads
            data = pull_google_ads.pull_google_ads()
            results["google_ads"] = "success" if data else "skipped"
            log("Google Ads pull complete" if data else "Google Ads skipped")
        except Exception as e:
            results["google_ads"] = f"error: {e}"
            log(f"Google Ads pull failed: {e}", "FAIL")

    # Meta Ads — Graph API rate-limited
    if skip_meta:
        results["meta_ads"] = "skipped (flag)"
        log("Meta Ads SKIPPED via --skip-meta flag", "SKIP")
    else:
        print("\n--- Meta Ads (Graph API) ---")
        try:
            import pull_meta
            data = pull_meta.pull_meta()
            results["meta_ads"] = "success" if data else "skipped"
            log("Meta Ads pull complete" if data else "Meta Ads skipped (token missing/expired)")
        except Exception as e:
            results["meta_ads"] = f"error: {e}"
            log(f"Meta Ads pull failed: {e}", "FAIL")

    # Note: Ahrefs + Apify intentionally NOT pulled here.
    #   Ahrefs: manual only — frozen snapshot used in inject-seo-extras.py
    #   Apify:  pulled by weekly-report.sh Step 1c (separately, weekly)

    # Write last-weekly-refresh timestamp (separate from last-refresh.json
    # which tracks the 4x/day free-source refresh).
    refresh_record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "human_readable": datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "results": results,
        "note": "Paid-source pull. Free sources tracked separately in last-refresh.json",
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    WEEKLY_LAST_REFRESH.write_text(json.dumps(refresh_record, indent=2))

    # Refresh paid-source inject blocks immediately so dashboard reflects new data.
    # (Free-source inject blocks will refresh next time pull_all.py runs every 6h.)
    print("\n--- Refreshing paid-source inject blocks ---")
    import subprocess
    PAID_INJECT_SCRIPTS = [
        "inject-meta-ads.py",
        "inject-google-ads.py",
    ]
    for script in PAID_INJECT_SCRIPTS:
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
    print(f"Done. {len(successes)}/{len(results)} paid sources pulled successfully.")
    if successes:
        print(f"Success: {', '.join(successes)}")
    print(f"Weekly refresh timestamp saved: {WEEKLY_LAST_REFRESH}")
    print(f"{'='*50}\n")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CB247 weekly paid-source data pull")
    parser.add_argument("--skip-google-ads", action="store_true",
                        help="Skip Google Ads pull (e.g. if quota exhausted)")
    parser.add_argument("--skip-meta", action="store_true",
                        help="Skip Meta Ads pull (e.g. if token expired)")
    args = parser.parse_args()
    run_weekly(skip_google_ads=args.skip_google_ads, skip_meta=args.skip_meta)


if __name__ == "__main__":
    main()
