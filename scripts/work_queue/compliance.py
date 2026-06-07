"""
compliance.py — pre-sync compliance gate for Work Queue actions.

Validates actions before they reach Supabase / the dashboard. Per-business
rule sets — CB247 has fitness/wellness compliance constraints, MWCC has
regulatory (ACECQA / NQS / ACL) constraints.

Used by:
    - scripts/work_queue/mwcc_sync_to_supabase.py
    - (future) scripts/work_queue/sync_to_supabase.py (CB247 — when needed)
    - (future) scripts/extract_agent_actions.py — extraction-time gate

Returns (clean: bool, reason: Optional[str]). If clean=False, the caller
must NOT upsert the action and SHOULD log it to a rejections file.
"""

from __future__ import annotations

import re
from typing import Tuple, Optional, List, Dict

# ── Banned patterns per business ────────────────────────────────────────────
#
# Each pattern is (regex, reason). Patterns are case-insensitive. Regex
# matches against title + description concatenated.
#
# Add new patterns at the bottom — never remove without auditing impact
# (an existing rejection log may rely on the reason text).

MWCC_BANNED_PATTERNS: List[Tuple[str, str]] = [
    # ── ACL undefendable superlatives ────────────────────────────────────
    (
        r"\bbest\s+(childcare|daycare|early\s+learning|child\s+care|childhood)\b",
        "Comparative superlative ('best [service]') — undefendable under Australian Consumer Law",
    ),
    (
        r"\b(premier|leading|top|#1|number\s+one|no\.?\s*1)\s+(childcare|daycare|early\s+learning|child\s+care|centre|early\s+childhood)\b",
        "Comparative superlative — undefendable under Australian Consumer Law",
    ),
    (
        r"\bperth['']?s\s+(best|leading|premier|top|#1|number\s+one)\b",
        "City-level superlative — undefendable under Australian Consumer Law",
    ),
    # ── Outcome guarantees (forbidden in childcare marketing) ─────────────
    (
        r"\bguarantee[ds]?\s+(your|the|that|to|a)?\s*child(ren)?\b",
        "Cannot guarantee child outcomes — strip 'guaranteed' or rephrase",
    ),
    (
        r"\bguarantee[ds]?\s+(reading|learning|development|outcome|placement|spot|enrolment)\b",
        "Cannot guarantee developmental outcome or enrolment placement",
    ),
    (
        r"\bguarantee[ds]?\s+(your\s+child\s+will|kids?\s+will)\b",
        "Cannot guarantee what a child will do",
    ),
    # ── Award claims without named award ─────────────────────────────────
    (
        r"\baward[\s-]?winning\b",
        "'Award-winning' requires named, current, verifiable award — cite the award by name",
    ),
    # ── NQS rating claims (need verification against state file) ─────────
    (
        r"\bnqs\s+(rating|rated|level)\s+\d",
        "NQS rating claim must match current verified rating in state/mwcc-nqs-ratings.json",
    ),
    (
        r"\b(exceeding|meeting|excellent|working\s+towards)\s+(nqs|rating|rated)\b",
        "NQS rating tier claim must match current verified rating",
    ),
    # ── Specialised service claims without basis ─────────────────────────
    (
        r"\bspecialis[ze]d\s+(therapy|therapist|psycholog|paediatric|allied\s+health)\b",
        "Specialised therapy claim requires qualified specialist on staff — cite the qualification",
    ),
    # ── Competitor name-drop (basic — extend as competitors emerge) ──────
    (
        r"\bbetter\s+than\s+(goodstart|nido|kindi[cC]are|care\s+for\s+kids|midvale\s+hub)\b",
        "Disparaging competitor comparison — rephrase neutrally",
    ),
]

CB247_BANNED_PATTERNS: List[Tuple[str, str]] = [
    # Placeholder — populate when CB247 adopts the gate.
    # Likely candidates: medical/therapeutic claims, weight-loss guarantees,
    # outcome promises ("guaranteed results in X weeks").
]

RULES_BY_BUSINESS: Dict[str, List[Tuple[str, str]]] = {
    "mwcc":  MWCC_BANNED_PATTERNS,
    "cb247": CB247_BANNED_PATTERNS,
    # Future: "kb", "sp"
}


def check_action(action: dict, business: str) -> Tuple[bool, Optional[str]]:
    """Check a Work Queue action against the business compliance rules.

    Args:
        action: dict matching WorkQueueAction shape — checks title + description
        business: 'cb247' | 'mwcc' | 'kb' | 'sp'

    Returns:
        (clean, reason)
        - clean=True, reason=None      → action OK to upsert
        - clean=False, reason='...'    → action MUST be blocked, with reason
    """
    rules = RULES_BY_BUSINESS.get(business.lower(), [])
    if not rules:
        return True, None

    haystack = " ".join([
        str(action.get("title") or ""),
        str(action.get("description") or ""),
    ]).lower()

    for pattern, reason in rules:
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            return False, reason

    return True, None


def check_actions(actions: List[dict], business: str) -> Tuple[List[dict], List[dict]]:
    """Split a list of actions into (clean, rejected).

    Rejected actions get a `_rejection_reason` field added for logging.

    Returns:
        (clean_actions, rejected_actions_with_reason)
    """
    clean: List[dict] = []
    rejected: List[dict] = []
    for action in actions:
        ok, reason = check_action(action, business)
        if ok:
            clean.append(action)
        else:
            # Tag the rejection for the caller's log
            rejected.append({**action, "_rejection_reason": reason})
    return clean, rejected


if __name__ == "__main__":
    # Quick smoke test
    samples = [
        {"title": "Build landing page for best childcare in Armadale",
         "description": "Target keyword."},
        {"title": "Optimise CCS calculator page",
         "description": "Improve conversion."},
        {"title": "Run ad: Guaranteed your child will love it",
         "description": "Meta ad copy."},
        {"title": "Showcase award-winning programme",
         "description": "Programme highlight."},
        {"title": "Run ad: NQS rated 5 across all centres",
         "description": "Trust signal."},
    ]
    print("Compliance gate smoke test (MWCC rules)")
    print("=" * 60)
    for s in samples:
        ok, reason = check_action(s, "mwcc")
        flag = "✅ CLEAN" if ok else "🚫 REJECTED"
        print(f"{flag}  {s['title']}")
        if not ok:
            print(f"          reason: {reason}")
    print()
    print("CB247 rules (currently no patterns — all pass):")
    for s in samples:
        ok, reason = check_action(s, "cb247")
        flag = "✅ CLEAN" if ok else "🚫 REJECTED"
        print(f"{flag}  {s['title']}")
