"""
opportunity_emitter.py — emit paid→organic SWITCH + organic-content-gap opportunities.

Closes Tia's stated strategic loop: reduce Google Ads spend by replacing
paid traffic with organic, AND identify content gaps where competitors
outrank CB247 on Page 1 organically.

Three action archetypes (priority order):
  1. PAUSE          — paid keywords where CB247 ranks GSC #1-#3 organically
                      (don't pause brand-defence keywords — exception list)
  2. REDUCE         — paid keywords where CB247 ranks GSC #4-#10 (50% budget cut)
  3. ORGANIC_OVERLAP — CB247 ranks #4-#10 on Apify SERP scrape AND named
                      competitor(s) sit ABOVE us — surfaces content/SEO gap.
                      Owner: John (SEO/Web). Different from PAUSE/REDUCE —
                      not about saving ad $, about climbing organic.

Each action carries a measurable projected_kpi:
  - PAUSE/REDUCE → ads_spend_saved_monthly (baseline=current, target=reduced)
  - ORGANIC_OVERLAP → gsc_clicks_weekly (baseline=current, target=+50%)

measurement_runner.py picks them up at verdict time and computes actuals.

Inputs:
    state/google-ads-data.json  → search_terms array (cost + impressions)
    state/gsc-data.json         → top_queries array (position + clicks)
    state/apify-data.json       → competitor_serp + keyword_tracking
                                  (Page-1 organic position vs competitors)

Output:
    Merged into state/work-queue.json (source_page='opportunity' or 'seo-organic').
    Picked up by sync_to_supabase.py in the same Phase 1 sequence.

Run:
    .venv/bin/python3.13 scripts/work_queue/opportunity_emitter.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parent.parent))

from work_queue.schema import (  # noqa: E402
    WorkQueueAction,
    ProjectedKPI,
    make_action_id,
    now_iso,
    week_iso,
    to_jsonable,
)


BASE_DIR        = _HERE.parent.parent
STATE_DIR       = BASE_DIR / "state"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

# ─── Tunable thresholds ───────────────────────────────────────────────────
PAUSE_MIN_WEEKLY_SPEND   = 5.0      # Only worth pausing if spending ≥$5/wk
PAUSE_MAX_GSC_POSITION   = 3.0      # Organic #1-#3 → pause paid

REDUCE_MIN_WEEKLY_SPEND  = 10.0     # Slightly higher bar for budget cut
REDUCE_GSC_POSITION_MIN  = 4.0
REDUCE_GSC_POSITION_MAX  = 10.0
REDUCE_BUDGET_CUT_PCT    = 0.50     # 50% of baseline

MAX_PAUSE_ACTIONS  = 5
MAX_REDUCE_ACTIONS = 3

# ─── ORGANIC_OVERLAP archetype (added 09 Jun 2026) ────────────────────────
# Surfaces keywords where CB247 ranks Page 1 (#4-#10) AND a named competitor
# sits in front. Different from PAUSE/REDUCE — this is about climbing
# organic, not saving ad spend.
ORGANIC_OVERLAP_POSITION_MIN = 2.0   # Already on Page 1 worth defending
ORGANIC_OVERLAP_POSITION_MAX = 10.0  # Below #10 is "build" territory (seo_emitter)
MAX_ORGANIC_OVERLAP_ACTIONS  = 5
# Generic platforms that aren't real "competitors" we'd write content against
# (excluding them from the competitor count — only real local rivals trigger).
GENERIC_COMPETITOR_PATTERNS = [
    r"instagram\.com", r"facebook\.com", r"reddit\.com",
    r"youtube\.com", r"tiktok\.com", r"yelp\.com",
    r"yellowpages\.com", r"truelocal\.com", r"hotfrog\.com",
]

# ─── Brand-defence keyword guard (NEVER pause these even if organic #1) ──
# Pausing brand keywords risks competitor poaching the SERP.
BRAND_DEFENCE_PATTERNS = [
    r"chasing\s*better",
    r"\bcb247\b",
    r"chasingbetter247",
]


def _is_brand_defence(term: str) -> bool:
    t = (term or "").lower()
    return any(re.search(p, t) for p in BRAND_DEFENCE_PATTERNS)


# ─── Data loaders ────────────────────────────────────────────────────────

def _load_search_terms() -> list[dict]:
    """Load Google Ads search-terms from this week's pull."""
    f = STATE_DIR / "google-ads-data.json"
    if not f.exists():
        print("[opportunity-emitter] state/google-ads-data.json missing")
        return []
    try:
        d = json.loads(f.read_text())
        return d.get("search_terms") or []
    except Exception as e:
        print(f"[opportunity-emitter] could not parse google-ads-data.json: {e}")
        return []


def _gsc_position_index() -> dict[str, dict]:
    """Build a {lowercased_query: {position, clicks, impressions, ctr}} map."""
    f = STATE_DIR / "gsc-data.json"
    if not f.exists():
        return {}
    try:
        d = json.loads(f.read_text())
    except Exception:
        return {}
    idx: dict[str, dict] = {}
    for q in (d.get("top_queries") or []):
        key = (q.get("query") or "").strip().lower()
        if key:
            idx[key] = q
    return idx


def _load_apify_serp() -> tuple[list[dict], list[dict]]:
    """Load competitor_serp + keyword_tracking from this week's Apify pull.

    Returns: (competitor_serp_list, keyword_tracking_list)
    Each competitor_serp entry: {keyword, organic:[{title,url,position}],...}
    Each keyword_tracking entry: {keyword, position, clicks, impressions, ctr}
    """
    f = STATE_DIR / "apify-data.json"
    if not f.exists():
        return [], []
    try:
        d = json.loads(f.read_text())
        return (d.get("competitor_serp") or [], d.get("keyword_tracking") or [])
    except Exception as e:
        print(f"[opportunity-emitter] could not parse apify-data.json: {e}")
        return [], []


def _domain(url: str) -> str:
    """Extract bare domain from URL (without www.)."""
    try:
        from urllib.parse import urlparse
        h = urlparse(url or "").netloc.lower()
        return h.replace("www.", "")
    except Exception:
        return ""


def _is_generic_platform(domain: str) -> bool:
    """Don't count IG / Reddit / FB as "competitors" we'd build content against."""
    return any(re.search(p, domain or "") for p in GENERIC_COMPETITOR_PATTERNS)


def _match_gsc(term: str, gsc_idx: dict[str, dict]) -> dict | None:
    """Find a GSC row matching this Ads search term. Exact match first, then
    suffix/substring fallback. Returns the matched GSC row or None."""
    if not term:
        return None
    t = term.lower().strip()
    if t in gsc_idx:
        return gsc_idx[t]
    # Try variant: GSC sometimes has 'chasing better malaga' vs Ads 'cb247 malaga'
    # Skip variant matching for now — exact + substring is enough for v1.
    for key, row in gsc_idx.items():
        if t in key or key in t:
            return row
    return None


# ─── Emitters ────────────────────────────────────────────────────────────

def _emit_pause(search_terms: list[dict], gsc_idx: dict[str, dict],
                week: str, start_serial: int) -> tuple[List[WorkQueueAction], int]:
    """Emit PAUSE actions for paid keywords MWCC ranks GSC #1-#3."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    # Build candidate list — keep all the data we need for ranking + brief
    candidates = []
    for st in search_terms:
        term = st.get("search_term", "")
        weekly_spend = float(st.get("cost") or 0)
        if weekly_spend < PAUSE_MIN_WEEKLY_SPEND:
            continue
        if _is_brand_defence(term):
            continue
        gsc_row = _match_gsc(term, gsc_idx)
        if not gsc_row:
            continue
        gsc_pos = gsc_row.get("position")
        if gsc_pos is None or gsc_pos > PAUSE_MAX_GSC_POSITION:
            continue
        # Compute projected monthly saving — weekly_spend × 4.3 (avg weeks/mo)
        # × 0.95 safety (organic CTR may need slight ramp-up)
        projected_monthly_saving = round(weekly_spend * 4.3 * 0.95, 2)
        candidates.append({
            "term":             term,
            "weekly_spend":     weekly_spend,
            "projected_saving": projected_monthly_saving,
            "campaign":         st.get("campaign", ""),
            "location":         st.get("location", ""),
            "gsc_position":     gsc_pos,
            "gsc_clicks":       gsc_row.get("clicks", 0),
            "gsc_ctr":          gsc_row.get("ctr", 0),
            "ads_clicks":       st.get("clicks", 0),
            "ads_conv":         st.get("conv", 0),
        })

    candidates.sort(key=lambda c: c["projected_saving"], reverse=True)

    for c in candidates[:MAX_PAUSE_ACTIONS]:
        baseline = round(c["weekly_spend"] * 4.3, 2)  # current monthly spend
        target   = 0
        action = WorkQueueAction(
            id=make_action_id("opp", week, serial),
            source_page="opportunity",
            source_run_at=ts,
            title=(
                f"Pause Google Ads for '{c['term']}' — projected ${c['projected_saving']:.0f}/mo saving "
                f"(organic #{c['gsc_position']:.1f})"
            ),
            description=(
                f"Currently spending ${c['weekly_spend']:.2f}/wk on this keyword "
                f"({c['campaign']}, {c['location'] or 'all locations'}). CB247 "
                f"ranks organic position #{c['gsc_position']:.1f} with "
                f"{c['gsc_clicks']} clicks/wk at {c['gsc_ctr']*100:.1f}% CTR. "
                f"Pausing paid will redirect that intent to organic at $0 cost. "
                f"Risk: low — strong organic CTR confirms users find us. "
                f"Action: pause keyword in Google Ads. Re-emit if organic clicks "
                f"drop materially after 2 weeks."
            ),
            owner="Tia",
            owner_role="OS Owner",
            priority="P1",
            effort_hours=0.5,
            category="opportunity",
            data_quality="high",
            projected_kpis=[ProjectedKPI(
                metric="ads_spend_saved_monthly",
                measurement_window_days=28,
                keyword=c["term"],
                baseline=baseline,
                target=target,
                confidence="high",
            )],
            source_agent="opportunity-emitter",
        )
        actions.append(action)
        serial += 1
    return actions, serial


def _emit_reduce(search_terms: list[dict], gsc_idx: dict[str, dict],
                 week: str, start_serial: int) -> tuple[List[WorkQueueAction], int]:
    """Emit REDUCE-50% actions for paid keywords ranking GSC #4-#10."""
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = []
    for st in search_terms:
        term = st.get("search_term", "")
        weekly_spend = float(st.get("cost") or 0)
        if weekly_spend < REDUCE_MIN_WEEKLY_SPEND:
            continue
        if _is_brand_defence(term):
            continue
        gsc_row = _match_gsc(term, gsc_idx)
        if not gsc_row:
            continue
        gsc_pos = gsc_row.get("position")
        if gsc_pos is None:
            continue
        if not (REDUCE_GSC_POSITION_MIN <= gsc_pos <= REDUCE_GSC_POSITION_MAX):
            continue
        projected_monthly_saving = round(weekly_spend * 4.3 * REDUCE_BUDGET_CUT_PCT, 2)
        candidates.append({
            "term":             term,
            "weekly_spend":     weekly_spend,
            "projected_saving": projected_monthly_saving,
            "campaign":         st.get("campaign", ""),
            "location":         st.get("location", ""),
            "gsc_position":     gsc_pos,
            "gsc_clicks":       gsc_row.get("clicks", 0),
        })

    candidates.sort(key=lambda c: c["projected_saving"], reverse=True)

    for c in candidates[:MAX_REDUCE_ACTIONS]:
        baseline = round(c["weekly_spend"] * 4.3, 2)
        target   = round(baseline * REDUCE_BUDGET_CUT_PCT, 2)
        action = WorkQueueAction(
            id=make_action_id("opp", week, serial),
            source_page="opportunity",
            source_run_at=ts,
            title=(
                f"Reduce Google Ads budget 50% on '{c['term']}' — projected "
                f"${c['projected_saving']:.0f}/mo saving (organic #{c['gsc_position']:.1f})"
            ),
            description=(
                f"Currently spending ${c['weekly_spend']:.2f}/wk on this keyword "
                f"({c['campaign']}). CB247 ranks organic #{c['gsc_position']:.1f} "
                f"with {c['gsc_clicks']} clicks/wk — organic is climbing but not yet "
                f"top-3. Cut budget 50% now; revisit when organic hits #3 to pause "
                f"entirely. Risk: low-medium. Action: halve daily budget on this "
                f"ad group. Re-evaluate after 14 days."
            ),
            owner="Tia",
            owner_role="OS Owner",
            priority="P2",
            effort_hours=0.3,
            category="opportunity",
            data_quality="high",
            projected_kpis=[ProjectedKPI(
                metric="ads_spend_saved_monthly",
                measurement_window_days=14,
                keyword=c["term"],
                baseline=baseline,
                target=target,
                confidence="medium",
            )],
            source_agent="opportunity-emitter",
        )
        actions.append(action)
        serial += 1
    return actions, serial


def _emit_organic_overlap(competitor_serp: list[dict], gsc_idx: dict[str, dict],
                          week: str, start_serial: int) -> tuple[List[WorkQueueAction], int]:
    """Emit SEO content-gap actions where CB247 ranks Page 1 (#4-#10)
    AND a named non-generic competitor sits ABOVE us on the SERP.

    Real-world signal: 'gym ellenbrook perth' — CB247 #3 organically, but
    ellenbrookfitness.com.au + arachnidgym.com.au rank above. That's a
    content gap on our Ellenbrook page — they're targeting the local
    modifier better than we are.

    Owner: John (SEO/Web Specialist). Different from PAUSE/REDUCE which
    target ad-spend savings — this targets organic-click uplift.
    """
    actions: List[WorkQueueAction] = []
    serial = start_serial
    ts = now_iso()

    candidates = []
    for serp in competitor_serp:
        keyword = (serp.get("keyword") or "").strip()
        if not keyword:
            continue
        if _is_brand_defence(keyword):
            continue
        organic = serp.get("organic") or []
        # Find CB247's position in organic
        cb_pos = None
        competitors_ahead = []
        for entry in organic:
            d = _domain(entry.get("url", ""))
            pos = entry.get("position") or 0
            if "chasingbetter247" in d:
                cb_pos = pos
                break
            # Anything before CB247 is a competitor — skip generic platforms
            if d and not _is_generic_platform(d):
                competitors_ahead.append({"domain": d, "position": pos,
                                          "title": entry.get("title", "")[:80]})

        if cb_pos is None:
            continue  # We don't rank at all — that's seo_emitter BUILD territory
        if not (ORGANIC_OVERLAP_POSITION_MIN <= cb_pos <= ORGANIC_OVERLAP_POSITION_MAX):
            continue
        if not competitors_ahead:
            continue  # We rank #2-#10 but no named competitor ahead — likely just IG/reddit, skip

        # Enrich with GSC data if available (for baseline clicks)
        gsc_match = _match_gsc(keyword, gsc_idx) or {}
        gsc_clicks = gsc_match.get("clicks", 0) or 0
        gsc_impressions = gsc_match.get("impressions", 0) or 0

        candidates.append({
            "keyword":           keyword,
            "cb_position":       cb_pos,
            "competitors_ahead": competitors_ahead[:3],   # top 3 real competitors
            "gsc_clicks":        gsc_clicks,
            "gsc_impressions":   gsc_impressions,
        })

    # Rank by "size of opportunity" — keywords with most impressions + best position first
    candidates.sort(key=lambda c: (-c["gsc_impressions"], c["cb_position"]))

    for c in candidates[:MAX_ORGANIC_OVERLAP_ACTIONS]:
        # Project: climbing from #N to #2 typically 2-3x clicks (CTR uplift).
        # Use observed GSC clicks where available; if zero, project from SERP impr.
        baseline_clicks = c["gsc_clicks"]
        # CTR uplift heuristic: position 4 → 2 ≈ ~2.5x, 6 → 3 ≈ ~3x, 10 → 5 ≈ ~3.5x
        ctr_uplift_factor = 2.5 if c["cb_position"] <= 5 else 3.0
        target_clicks = max(round(baseline_clicks * ctr_uplift_factor), baseline_clicks + 5)

        comp_names = ", ".join(comp["domain"] for comp in c["competitors_ahead"])
        comp_positions = ", ".join(
            f"#{comp['position']} {comp['domain']}" for comp in c["competitors_ahead"]
        )

        action = WorkQueueAction(
            id=make_action_id("opp", week, serial),
            source_page="seo-organic",
            source_run_at=ts,
            title=(
                f"Improve organic content for '{c['keyword']}' — outrank "
                f"{comp_names} (currently CB247 #{int(c['cb_position'])})"
            ),
            description=(
                f"CB247 ranks #{int(c['cb_position'])} on Google for '{c['keyword']}'. "
                f"Competitors above us: {comp_positions}. "
                f"{('GSC shows ' + str(baseline_clicks) + ' clicks/wk at ' + str(gsc_impressions := c['gsc_impressions']) + ' impressions — there is a measurable click pool to win. ') if baseline_clicks else 'Apify SERP confirms Page 1 placement; GSC has not tracked it yet (low impression volume or recently surfaced). '}"
                f"Action: improve the targeting landing page (add location modifier in title/H1, expand FAQ section addressing local intent, add internal links from /malaga and /ellenbrook pages). "
                f"Risk: low — we already rank Page 1, just need to climb. "
                f"Owner: John reviews + briefs Mark for content updates. "
                f"Projected: lift to top-3 within 6-8 weeks; ~2.5-3x organic clicks once at #2."
            ),
            owner="John",
            owner_role="SEO / Web",
            priority="P2",
            effort_hours=2.5,
            category="opportunity",
            data_quality="high" if baseline_clicks > 0 else "medium",
            projected_kpis=[ProjectedKPI(
                metric="gsc_clicks_weekly",
                measurement_window_days=42,   # 6 weeks for SEO uplift to land
                keyword=c["keyword"],
                baseline=float(baseline_clicks),
                target=float(target_clicks),
                confidence="medium",
            )],
            source_agent="opportunity-emitter",
        )
        actions.append(action)
        serial += 1
    return actions, serial


# ─── Pipeline orchestration ───────────────────────────────────────────────

def emit_all_opportunity_actions() -> List[WorkQueueAction]:
    """Top-level: load data, run emitters, return action list."""
    search_terms = _load_search_terms()
    gsc_idx      = _gsc_position_index()
    competitor_serp, keyword_tracking = _load_apify_serp()

    # PAUSE + REDUCE require BOTH ads search-terms AND GSC — skip if either missing
    pause_actions, reduce_actions = [], []
    if search_terms and gsc_idx:
        week = week_iso()
        pause_actions, next_serial = _emit_pause(search_terms, gsc_idx, week, 1)
        reduce_actions, next_serial = _emit_reduce(search_terms, gsc_idx, week, next_serial)
    else:
        if not search_terms:
            print("[opportunity-emitter] no Google Ads search terms — skipping PAUSE/REDUCE")
        if not gsc_idx:
            print("[opportunity-emitter] no GSC queries — skipping PAUSE/REDUCE")
        next_serial = 1

    # ORGANIC_OVERLAP only requires Apify SERP — independent path
    overlap_actions = []
    if competitor_serp:
        week = week_iso()
        overlap_actions, _ = _emit_organic_overlap(competitor_serp, gsc_idx, week, next_serial)
    else:
        print("[opportunity-emitter] no Apify SERP — skipping ORGANIC_OVERLAP")

    return pause_actions + reduce_actions + overlap_actions


def merge_with_existing(new_actions: List[WorkQueueAction]) -> dict:
    """Idempotent merge into state/work-queue.json. Replace any existing
    opportunity-emitter actions from this week — they get re-derived from
    the same source data, so re-emission should be a no-op semantically."""
    existing: dict = {"actions": []}
    if WORK_QUEUE_FILE.exists():
        try:
            existing = json.loads(WORK_QUEUE_FILE.read_text())
        except Exception:
            existing = {"actions": []}

    actions = existing.get("actions") or []
    # Strip prior opportunity-emitter actions from this week (avoid stacking)
    week = week_iso()
    actions = [
        a for a in actions
        if not (a.get("source_agent") == "opportunity-emitter"
                and (a.get("id") or "").split("-")[-2:-1] == [week.replace("W","w")])
    ]
    # Catch-all: strip ALL prior opportunity actions (simpler — they'll
    # re-emit if the underlying opportunity still exists)
    actions = [a for a in actions if a.get("source_agent") != "opportunity-emitter"]

    actions.extend(to_jsonable(a) for a in new_actions)
    existing["actions"] = actions
    existing["updated_at"] = now_iso()
    return existing


def main():
    print(f"[opportunity-emitter] {now_iso()}")
    new_actions = emit_all_opportunity_actions()

    # Validate before writing
    errors_found = False
    for a in new_actions:
        errs = a.validate()
        if errs:
            errors_found = True
            print(f"  ❌ {a.id}: {errs}")

    if errors_found:
        print("[opportunity-emitter] validation failed — refusing to write")
        sys.exit(1)

    merged = merge_with_existing(new_actions)
    WORK_QUEUE_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False))

    summary_by_type: dict = {}
    for a in new_actions:
        if a.source_page == "seo-organic":
            cat = "ORGANIC_OVERLAP"
        elif a.priority == "P1":
            cat = "PAUSE"
        else:
            cat = "REDUCE"
        summary_by_type[cat] = summary_by_type.get(cat, 0) + 1

    # Only sum SAVINGS for actions in the savings space (PAUSE + REDUCE) —
    # ORGANIC_OVERLAP measures clicks, not dollars, and would skew the headline.
    total_saving = sum(
        kpi.baseline - (kpi.target or 0)
        for a in new_actions for kpi in a.projected_kpis
        if a.source_page == "opportunity"
        and kpi.baseline is not None and kpi.target is not None
    )

    print(f"[opportunity-emitter] OK — {len(new_actions)} actions emitted")
    for cat, n in summary_by_type.items():
        print(f"    {cat:<16} {n}")
    print(f"    Total projected monthly saving (PAUSE+REDUCE): ${total_saving:.2f}")
    print(f"    Written to {WORK_QUEUE_FILE.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
