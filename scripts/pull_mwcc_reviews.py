"""
pull_mwcc_reviews.py — MWCC review monitoring (5 GBPs + FB pages).

SCAFFOLDING — implementation BLOCKED pending API access.

Purpose:
    Pull reviews from all 5 MWCC centre Google Business Profiles + Facebook
    pages on a daily cadence. Classify sentiment. Alert Kelley when a
    negative review fires within the last 24 hours so response time stays
    under the brand standard (24h target per local-seo-optimizer skill).

Blocking dependencies (status 7 Jun 2026):
    1. Google Business Profile Reviews API (`mybusinessbusinesscalls`)
       - Status: requires same Google Cloud quota as the existing GBP
                 Performance API. That quota is at 0, awaiting Tia's
                 quota-increase request via GCP Console for project
                 chasingbetter-247.
       - When unblocked: query reviews per location ID per centre.
                          Centre IDs documented in MEMORY.md (Malaga ·
                          Ellenbrook); MWCC equivalents TBC after access.
    2. Facebook Graph API — page reviews (deprecated 2021)
       - Status: Meta deprecated the legacy `ratings` field on Page
                 Insights. Modern access requires "Recommendations" via
                 Page-level token + advanced permissions.
       - Alternative: Apify FB Reviews scraper actor — currently broken
                       per memory MEMORY.md project_apify_fixes.md.
                       Blocked on subscription top-up due 2026-06-02.
    3. Apify Google Reviews scraper
       - Status: Alternative to GBP API. Apify subscription is "once a
                 week" cadence (per memory) — daily review monitoring
                 would burn the weekly budget too fast.

Recommended unblock path (cheapest first):
    a. Tia submits GCP quota increase for `mybusinessbusinesscalls`.
       Expected approval ≈ 1-3 weeks based on historic Google response
       times.
    b. Once GBP API access lands, run this script daily at 8am AWST
       via launchd or cron. Output writes to
       `state/mwcc-reviews-history.json` (gitignored snapshot).
    c. Email digest extends — `send_mwcc_weekly_report.py` already
       sends to Tia only; adds a "Reviews last 7 days" block with
       any new <4-star reviews flagged for Kelley to respond.

Data model (when implemented):
    {
      "_updated_at": "<ISO>",
      "reviews": [
        {
          "centre": "Armadale",
          "source": "google" | "facebook",
          "review_id": "...",
          "review_url": "https://maps.google.com/...",
          "author": "[anonymised]",
          "rating": 5,
          "text": "...",
          "posted_at": "<ISO>",
          "response_status": "unanswered" | "responded" | "private_reply",
          "response_text": null,
          "sentiment_class": "positive" | "neutral" | "negative",
          "flagged_for_kelley": false,
          "flag_reason": null
        }
      ]
    }

Alert thresholds (when implemented):
    - Any 1-star review                         → flag for Kelley < 24h
    - 2-star review with text > 50 chars        → flag for Kelley < 24h
    - 3-star review with negative keyword       → flag for Kelley < 48h
    - >5 unanswered reviews (any rating) > 7 days → flag (response cadence breach)

Negative keywords to flag (childcare-specific):
    "unsafe", "injury", "ratio", "neglect", "rude", "expensive",
    "waitlist", "communication", "rotated educator", "different staff"

CB247 parity:
    CB247 has no equivalent review monitoring script — review responses
    handled manually via Metricool. If this MWCC implementation lands,
    refactor for CB247 reuse (Layer-1 module shared between businesses).

Current implementation:
    This script is a no-op. It logs the blocked status and exits 0 so
    the cron pipeline doesn't fail when it eventually wires this in.
"""

from __future__ import annotations

import json
import datetime as _dt
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
STATE_DIR   = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "mwcc-reviews-history.json"


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    placeholder = {
        "_updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "_status": "blocked",
        "_blocking": [
            "GBP Reviews API quota=0 — Tia submitting via GCP Console",
            "FB Pages reviews deprecated — Apify alternative on hold (subscription)",
            "Apify weekly cadence too slow for daily review monitoring",
        ],
        "reviews": [],
    }
    OUTPUT_FILE.write_text(json.dumps(placeholder, indent=2))
    print(f"[mwcc-reviews] BLOCKED — wrote placeholder → {OUTPUT_FILE.relative_to(BASE_DIR)}")
    print(f"[mwcc-reviews] Unblock: submit GCP quota increase + retest. See top of script for full spec.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
