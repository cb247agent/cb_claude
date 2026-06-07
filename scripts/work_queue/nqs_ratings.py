"""
nqs_ratings.py — NQS rating registry helper for MWCC compliance gate.

ACECQA assigns each MWCC centre an NQS (National Quality Standard) rating
tier. Marketing copy that cites a rating must match the current verified
rating. This helper loads context/mwcc-nqs-ratings.json and exposes:

    load_ratings()      -> Dict[centre_name, rating_record]
    is_citation_ok(centre, claimed_tier) -> (ok: bool, reason: str)

The compliance gate (compliance.py) currently auto-blocks ALL NQS claims
by default — until centres are verified in the registry AND a content
piece is explicitly flagged as `verified_nqs_claim: true`.

This module is consumed by:
    - scripts/work_queue/compliance.py — verification of explicit claims
    - (future) docs/index.html — display current ratings on dashboard

Run as a smoke test:
    python3 scripts/work_queue/nqs_ratings.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Tuple

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
CONTEXT_DIR = BASE_DIR / "context"
RATINGS_FILE = CONTEXT_DIR / "mwcc-nqs-ratings.json"

# Acceptable tiers per ACECQA
VALID_TIERS = {
    "Significant Improvement Required",
    "Working Towards NQS",
    "Meeting NQS",
    "Exceeding NQS",
    "Excellent",
}

# Lowercase synonyms a copywriter might use → canonical tier
TIER_SYNONYMS = {
    "exceeding":              "Exceeding NQS",
    "exceeding nqs":          "Exceeding NQS",
    "meeting":                "Meeting NQS",
    "meeting nqs":            "Meeting NQS",
    "working towards":        "Working Towards NQS",
    "working towards nqs":    "Working Towards NQS",
    "excellent":              "Excellent",
    "significant improvement required": "Significant Improvement Required",
}


def _normalise_tier(s: str) -> Optional[str]:
    """Map a free-text claim ('exceeding', 'NQS Meeting') to canonical tier."""
    if not s:
        return None
    return TIER_SYNONYMS.get(s.strip().lower())


def load_ratings() -> Dict[str, dict]:
    """Load the rating registry. Returns dict keyed by centre name (case-insensitive lookup later)."""
    if not RATINGS_FILE.exists():
        return {}
    try:
        data = json.loads(RATINGS_FILE.read_text())
    except Exception:
        return {}
    out: Dict[str, dict] = {}
    for r in data.get("ratings", []):
        centre = r.get("centre")
        if centre:
            out[centre.strip().lower()] = r
    return out


def is_citation_ok(centre: str, claimed_tier: str) -> Tuple[bool, str]:
    """Check if a marketing piece can cite the given NQS tier for the given centre.

    Args:
        centre: e.g. 'Armadale' (case-insensitive)
        claimed_tier: free-text claim, e.g. 'exceeding' or 'Meeting NQS'

    Returns:
        (ok, reason)
        - (True, 'verified') when the centre is in the registry AND
          ok_to_cite_in_marketing=true AND the canonical tier matches
        - (False, '<reason>') otherwise
    """
    ratings = load_ratings()
    record = ratings.get((centre or "").strip().lower())
    if not record:
        return False, f"Centre '{centre}' not in NQS rating registry"

    if not record.get("ok_to_cite_in_marketing"):
        return False, (
            f"Centre '{centre}' rating not yet cleared for marketing "
            f"(ok_to_cite_in_marketing=false in context/mwcc-nqs-ratings.json)"
        )

    canonical = _normalise_tier(claimed_tier)
    if not canonical:
        return False, (
            f"Claimed tier '{claimed_tier}' not recognised — must be one of "
            f"{sorted(VALID_TIERS)}"
        )

    actual = record.get("current_rating")
    if not actual:
        return False, f"Centre '{centre}' has no current_rating recorded yet"

    if canonical.lower() != str(actual).strip().lower():
        return False, (
            f"Claimed tier '{canonical}' does not match verified rating "
            f"'{actual}' for '{centre}'"
        )

    return True, "verified"


if __name__ == "__main__":
    print("NQS Rating Registry — smoke test")
    print("=" * 60)
    ratings = load_ratings()
    print(f"Loaded {len(ratings)} centre rating records:")
    for centre_lc, rec in ratings.items():
        rating = rec.get("current_rating") or "(not yet set)"
        ok = rec.get("ok_to_cite_in_marketing", False)
        print(f"  {rec['centre']:<15} rating={rating:<25} cite_ok={ok}")

    print()
    print("Citation checks:")
    test_cases = [
        ("Armadale", "Exceeding NQS"),
        ("Midvale", "meeting"),
        ("Unknown Centre", "Exceeding NQS"),
        ("Armadale", "ultimate rating"),
    ]
    for centre, tier in test_cases:
        ok, reason = is_citation_ok(centre, tier)
        flag = "✅" if ok else "🚫"
        print(f"  {flag}  centre={centre!r:<22} tier={tier!r:<25} → {reason}")
