"""
pull_gbp.py — Pull Google Business Profile data for CB247 via Apify.

Source: state/apify-data.json → competitor_maps.targets
Saves to: state/gbp-data.json

No GBP API required. Apify scrapes Maps ratings, reviews, photos,
and completeness scores for CB247 Malaga, Ellenbrook, and competitors.
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
STATE_DIR   = BASE_DIR / "state"
APIFY_FILE  = STATE_DIR / "apify-data.json"
OUTPUT_FILE = STATE_DIR / "gbp-data.json"


def pull_gbp():
    """
    Extract GBP data from Apify competitor_maps.
    Returns structured dict with CB247 + competitor profiles.
    """
    if not APIFY_FILE.exists():
        print("[GBP] apify-data.json not found — run pull_apify.py first.")
        _write_empty("apify-data.json missing")
        return None

    try:
        apify = json.loads(APIFY_FILE.read_text())
    except Exception as e:
        print(f"[GBP] Failed to read apify-data.json: {e}")
        _write_empty(str(e))
        return None

    maps_data = apify.get("competitor_maps") or {}
    targets   = maps_data.get("targets") or []

    if not targets:
        print("[GBP] No targets in competitor_maps — check pull_apify.py.")
        _write_empty("no targets in competitor_maps")
        return None

    # ── Split CB247 vs competitors ──
    cb247     = [t for t in targets if t.get("type") == "cb247"]
    competitors = [t for t in targets if t.get("type") == "competitor"]

    malaga      = next((t for t in cb247 if t.get("location") == "Malaga"), {})
    ellenbrook  = next((t for t in cb247 if t.get("location") == "Ellenbrook"), {})

    # ── Build output ──
    result = {
        "source":       "apify",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "malaga": {
            "name":              malaga.get("title", "ChasingBetter247 Malaga"),
            "rating":            malaga.get("rating"),
            "reviews":           malaga.get("reviews"),
            "photos":            malaga.get("photos"),
            "address":           malaga.get("address"),
            "phone":             malaga.get("phone"),
            "website":           malaga.get("website"),
            "category":          malaga.get("category"),
            "hours_set":         malaga.get("hours_set"),
            "completeness":      malaga.get("completeness_score"),
            "permanently_closed": malaga.get("permanently_closed", False),
        },
        "ellenbrook": {
            "name":              ellenbrook.get("title", "ChasingBetter247 Ellenbrook"),
            "rating":            ellenbrook.get("rating"),
            "reviews":           ellenbrook.get("reviews"),
            "photos":            ellenbrook.get("photos"),
            "address":           ellenbrook.get("address"),
            "phone":             ellenbrook.get("phone"),
            "website":           ellenbrook.get("website"),
            "category":          ellenbrook.get("category"),
            "hours_set":         ellenbrook.get("hours_set"),
            "completeness":      ellenbrook.get("completeness_score"),
            "permanently_closed": ellenbrook.get("permanently_closed", False),
        },
        "competitors": [
            {
                "name":     c.get("title", c.get("query", "")),
                "location": c.get("location", ""),
                "rating":   c.get("rating"),
                "reviews":  c.get("reviews"),
                "photos":   c.get("photos"),
                "completeness": c.get("completeness_score"),
            }
            for c in competitors
        ],
        "summary": {
            "malaga_rating":         malaga.get("rating"),
            "malaga_reviews":        malaga.get("reviews"),
            "ellenbrook_rating":     ellenbrook.get("rating"),
            "ellenbrook_reviews":    ellenbrook.get("reviews"),
            "avg_rating":            round(
                ((malaga.get("rating") or 0) + (ellenbrook.get("rating") or 0)) / 2, 1
            ) if malaga.get("rating") and ellenbrook.get("rating") else None,
            "total_reviews":         (malaga.get("reviews") or 0) + (ellenbrook.get("reviews") or 0),
            "top_competitor_rating": max(
                (c.get("rating") or 0) for c in competitors
            ) if competitors else None,
        },
    }

    OUTPUT_FILE.write_text(json.dumps(result, indent=2))
    print(f"[GBP] Data extracted from Apify → {OUTPUT_FILE}")
    _print_summary(result)
    return result


def _write_empty(reason):
    OUTPUT_FILE.write_text(json.dumps({
        "source": "apify",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "available": False,
        "skip_reason": reason,
    }, indent=2))


def _print_summary(r):
    mal = r["malaga"]
    ell = r["ellenbrook"]
    print(f"  Malaga:      {mal['rating']} ⭐ ({mal['reviews']} reviews, {mal['photos']} photos)")
    print(f"  Ellenbrook:  {ell['rating']} ⭐ ({ell['reviews']} reviews, {ell['photos']} photos)")
    for c in r["competitors"]:
        print(f"  {c['name'][:35]:35} {c['rating']} ⭐ ({c['reviews']} reviews)")


if __name__ == "__main__":
    pull_gbp()
