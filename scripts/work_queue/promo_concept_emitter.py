"""
promo_concept_emitter.py — Generate monthly promo concepts (acquisition + retention).

Outputs TWO things:
  1. state/promo-pipeline.json   — full schema consumed by the dashboard
                                    Promo Pipeline + Asset Library pages
  2. New WorkQueueActions appended to state/work-queue.json — each child item
                                    of an acquisition/retention concept (reels,
                                    stories, EDM) carries parent_promo_id back
                                    to its concept, which lights up the
                                    "Awaiting Assets" badge on In Progress
                                    kanban cards when no GDrive URL is set yet.

Concept logic is heuristic-based (encodes Tia's strategic playbook from
CB_Brain/wiki/CB247-Knowledge-Base.md) and tuned weekly to live signals:

  ACQUISITION concepts fire from context/seasonal-calendar.md:
    - Active seasonal campaign continues in pipeline
    - Events within 60 days → "prep" concept
    - School holidays within 14 days → Kids Hub spotlight

  RETENTION concepts fire from state/membership-data.json:
    - future_cancellations ≥ 200       → save-call offer ("Don't Quit X")
    - "switched to another gym" reason → loyalty/community defence
    - top add-on uptake < 5% of base   → free trial month
    - "not using" reason ≥ 5           → "Welcome Back" check-in

A future v2 can swap the heuristic engine for a Claude-API call that reasons
across the same inputs and outputs the same JSON schema.

Run:
    .venv/bin/python3.13 scripts/work_queue/promo_concept_emitter.py
    python3 scripts/work_queue/promo_concept_emitter.py --dry-run       # preview only
    python3 scripts/work_queue/promo_concept_emitter.py --month 2026-07  # target month

Writes/updates:
    state/promo-pipeline.json
    state/work-queue.json  (merges new concept-child items)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

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

BASE_DIR = _HERE.parent.parent
STATE_DIR = BASE_DIR / "state"
MEMBERSHIP_FILE = STATE_DIR / "membership-data.json"
SEASONAL_FILE = BASE_DIR / "context" / "seasonal-calendar.md"
PROMO_FILE = STATE_DIR / "promo-pipeline.json"
WORK_QUEUE_FILE = STATE_DIR / "work-queue.json"

GENERATOR_VERSION = "1.0.0"  # First Wave 5 ship


# ── Inputs ────────────────────────────────────────────────────────────────────


def _load_membership() -> dict:
    if not MEMBERSHIP_FILE.exists():
        return {}
    try:
        return json.loads(MEMBERSHIP_FILE.read_text())
    except Exception as e:
        print(f"  ⚠️  Could not parse membership-data.json: {e}")
        return {}


def _load_seasonal() -> str:
    if not SEASONAL_FILE.exists():
        return ""
    return SEASONAL_FILE.read_text()


def _load_existing_promo_pipeline() -> dict:
    """Preserve in-flight promos: don't overwrite stages downstream of Concept."""
    if not PROMO_FILE.exists():
        return {"acquisition": [], "retention": []}
    try:
        return json.loads(PROMO_FILE.read_text())
    except Exception:
        return {"acquisition": [], "retention": []}


# ── Signal extraction (heuristic engine) ──────────────────────────────────────


def _membership_signals(mem: dict) -> dict:
    """Pull the numbers that drive retention concepts."""
    summary = mem.get("summary", {}) or {}
    totals = summary.get("totals", {}) or {}
    unique = summary.get("unique_base", {}) or {}
    cw = mem.get("cleverwaiver", {}) or {}
    would_return = cw.get("would_return", {}) or {}

    # Bucket "switched gym" responses (may appear in compound keys)
    switched_count = sum(v for k, v in would_return.items() if "switched" in k.lower())
    not_using_count = sum(v for k, v in would_return.items() if "not using" in k.lower())

    # Add-on penetration
    addons = mem.get("contracts", {}).get("addon_active", {}) or {}
    top_addon = max(addons.items(), key=lambda kv: kv[1]) if addons else (None, 0)

    return {
        "future_cancellations":       totals.get("FutureCancellations", 0),
        "future_cancellations_unique": (unique.get("future", {}) or {}).get("Total", 0),
        "new_contracts":              totals.get("NewContracts", 0),
        "ended_contracts":            totals.get("EndedContracts", 0),
        "switched_gym_responses":     switched_count,
        "not_using_responses":        not_using_count,
        "total_cleverwaiver":         cw.get("total_responses", 0),
        "top_addon_name":             top_addon[0],
        "top_addon_count":            top_addon[1],
        "addons_all":                 addons,
    }


# ── Seasonal parser ───────────────────────────────────────────────────────────


def _seasonal_events_within(days_ahead: int, seasonal_md: str) -> list[dict]:
    """Best-effort parse of seasonal-calendar.md ## tables for events within N days."""
    out = []
    today = date.today()

    # Active campaign block. Two flavours appear here:
    #   1. "← ACTIVE FROM..."   = campaign already in flight → owned by existing pipeline, skip
    #   2. "← WITHIN N DAYS → CAMPAIGN QUEUE NOW" = NEW campaign trigger → emit concept now
    active_match = re.search(r"## ACTIVE RIGHT NOW\s*\n(.*?)(?=\n##|\Z)", seasonal_md, re.DOTALL)
    if active_match:
        for line in active_match.group(1).split("\n\n"):
            line = line.strip()
            if not line or not line.startswith("**"):
                continue
            label_match = re.match(r"\*\*([^*]+)\*\*", line)
            if not label_match:
                continue
            label = label_match.group(1).strip()
            # Distinguish 'queue now' triggers from already-active campaigns
            is_queue_trigger = "QUEUE NOW" in line.upper() or "WITHIN" in line.upper()
            out.append({
                "label": label,
                "kind": "queue_now" if is_queue_trigger else "active",
                "raw": line[:200],
                "days_away": 0,
            })

    # UPCOMING table
    table_match = re.search(r"## UPCOMING.*?\n(\|.*?\n(?:\|.*?\n)+)", seasonal_md, re.DOTALL)
    if table_match:
        for row in table_match.group(1).split("\n"):
            cells = [c.strip() for c in row.split("|")]
            if len(cells) < 5 or cells[1] == "Date" or "---" in row:
                continue
            date_str, event, priority, trigger = cells[1], cells[2], cells[3], cells[4]
            event_date = _parse_event_date(date_str)
            if not event_date:
                continue
            days_away = (event_date - today).days
            if 0 <= days_away <= days_ahead:
                out.append({
                    "label": event,
                    "kind": "upcoming",
                    "priority": priority,
                    "trigger": trigger,
                    "date": event_date.isoformat(),
                    "days_away": days_away,
                })
    return out


def _parse_event_date(s: str) -> Optional[date]:
    """Parse seasonal calendar date strings: '7 Sep 2026', 'Oct–Nov 2026', '1 Jan 2027'."""
    s = s.strip()
    # Try specific date first: "7 Sep 2026", "1 Jan 2027"
    m = re.match(r"(\d+)\s+([A-Za-z]+)\s+(\d{4})", s)
    if m:
        day, mon, year = m.group(1), m.group(2), m.group(3)
        try:
            return datetime.strptime(f"{day} {mon} {year}", "%d %b %Y").date()
        except ValueError:
            try:
                return datetime.strptime(f"{day} {mon} {year}", "%d %B %Y").date()
            except ValueError:
                return None
    # "Oct–Nov 2026" or "Oct 2026" → first day of first month
    m = re.match(r"([A-Za-z]+)[^\d]*(\d{4})", s)
    if m:
        mon, year = m.group(1), m.group(2)
        try:
            return datetime.strptime(f"1 {mon} {year}", "%d %b %Y").date()
        except ValueError:
            return None
    return None


# ── Concept builders ──────────────────────────────────────────────────────────


def _build_acquisition_concepts(signals: dict, events: list[dict], month_iso: str) -> list[dict]:
    concepts: list[dict] = []

    for ev in events:
        ev_label_lower = ev["label"].lower()
        if ev["kind"] == "active":
            # Already-running campaigns stay in pipeline as-is — handled by merge logic.
            # We don't re-emit them; the existing pipeline file owns their state.
            continue
        # "queue_now" trigger from the ACTIVE block (e.g. WA School Holidays
        # WITHIN 21 DAYS) flows through the same branches as upcoming events.

        # School holidays → Kids Hub
        if "holiday" in ev_label_lower or "school" in ev_label_lower:
            concepts.append({
                "id": f"promo-kids-hub-{month_iso}",
                "track": "acquisition",
                "stage": "Concept",
                "label": "Kids Hub Holiday Spotlight",
                "subtitle": f"School holidays starting {ev.get('date','')} · Kids Hub family draw",
                "started": "",
                "ends": "",
                "phase": f"Concept · {ev.get('days_away',0)} days until holidays",
                "target_audience": "new_member",
                "offer": {
                    "headline": "Kids play. You train. Holiday family memberships.",
                    "pricing": "$11.95/wk all-access + free Kids Hub for school holidays",
                    "base": "No lock-in. Cancel after holidays if it doesn't work for you.",
                    "eligibility": "New family memberships (one adult + kids enrolled in Hub)",
                },
                "tone": "Warm / family / 'the gym that gets school routines'. ICP: Malaga Families + Ellenbrook Locals.",
                "rationale": f"School holidays drive parent stress around childcare + gym continuity. Kids Hub is CB247's biggest physical differentiator. {ev.get('days_away',0)}-day lead time fits the standard family decision window.",
                "asset_requirements": {
                    "reels": 4,
                    "stories": 8,
                    "static_posts": 3,
                    "edm_assets": 1,
                    "in_club_posters": 2,
                },
                "gdrive_folder_url": "",
                "child_actions": [],
                "metrics": {
                    "family_joins_target": 25,
                    "kids_hub_signup_target": 40,
                    "projected_revenue_lift": "$2,800/mo at full pipeline",
                },
            })
        # Father's Day → gift memberships
        elif "father" in ev_label_lower or "mother" in ev_label_lower:
            event_kind = "fathers" if "father" in ev_label_lower else "mothers"
            concepts.append({
                "id": f"promo-{event_kind}-day-gift-{month_iso}",
                "track": "acquisition",
                "stage": "Concept",
                "label": f"{ev['label']} Gift Memberships",
                "subtitle": f"{ev.get('date','')} · gift memberships + PT bundles",
                "started": "",
                "ends": "",
                "phase": f"Concept · {ev.get('days_away',0)} days until {ev['label']}",
                "target_audience": "new_member",
                "offer": {
                    "headline": f"Give the strongest gift. {ev['label']} bundles.",
                    "pricing": "3-month gift card $99 · 6-month $179 · 12-month $349 · PT add-on +$50",
                    "base": "Recipient picks home club. No-lock-in carries over after gift period.",
                    "eligibility": "Anyone (gift purchase). Recipient becomes new member.",
                },
                "tone": "Warm / heartfelt / strong / 'invest in someone you love'.",
                "rationale": f"{ev['label']} drives gift-purchase intent that competitor gyms ignore. PT bundle upsells on top of the gift purchase. {ev.get('days_away',0)} days = ideal lead for asset production + EDM warm-up.",
                "asset_requirements": {
                    "reels": 3,
                    "stories": 6,
                    "static_posts": 3,
                    "edm_assets": 2,
                    "landing_page": 1,
                },
                "gdrive_folder_url": "",
                "child_actions": [],
                "metrics": {
                    "gift_card_sales_target": 40,
                    "pt_bundle_attach_target": 15,
                    "projected_revenue_lift": "$5,200/mo + recurring after gift period",
                },
            })
        # Summer Prep / Beach Season → body confidence
        elif "summer" in ev_label_lower or "beach" in ev_label_lower:
            concepts.append({
                "id": f"promo-summer-prep-{month_iso}",
                "track": "acquisition",
                "stage": "Concept",
                "label": "Beach Season Starts Now",
                "subtitle": "Summer Prep · body confidence + consistency over crash diets",
                "started": "",
                "ends": "",
                "phase": f"Concept · {ev.get('days_away',0)} days until peak",
                "target_audience": "new_member",
                "offer": {
                    "headline": "Show up before summer shows up.",
                    "pricing": "$11.95/wk all-access · first 4 weeks free with 12-week commitment",
                    "base": "No-lock-in available · 12-week commit = best value",
                    "eligibility": "New members only",
                },
                "tone": "Confident / cinematic / honest about results requiring weeks not days. Avoid body shaming.",
                "rationale": "Pre-summer is the second-biggest acquisition window after January. CB247's no-lock-in differentiator outflanks Anytime/Revo on intent buyers.",
                "asset_requirements": {
                    "reels": 6,
                    "stories": 10,
                    "static_posts": 4,
                    "edm_assets": 1,
                    "landing_page": 1,
                    "in_club_posters": 2,
                },
                "gdrive_folder_url": "",
                "child_actions": [],
                "metrics": {
                    "new_joins_target": 100,
                    "twelve_week_attach_target": 40,
                    "projected_revenue_lift": "$14,200/mo at full pipeline",
                },
            })

    return concepts


def _build_retention_concepts(signals: dict, month_iso: str) -> list[dict]:
    concepts: list[dict] = []

    fc = signals["future_cancellations"]
    fc_unique = signals["future_cancellations_unique"]
    switched = signals["switched_gym_responses"]
    not_using = signals["not_using_responses"]
    top_addon = signals["top_addon_name"]
    top_addon_count = signals["top_addon_count"]

    # Rule 1: future_cancellations ≥ 200 → save-call offer
    if fc >= 200:
        revenue_recovery = int(0.30 * fc_unique * 48)  # 30% save × unique × $48/mo
        concepts.append({
            "id": f"promo-dont-quit-save-call-{month_iso}",
            "track": "retention",
            "stage": "Concept",
            "label": "Don't Quit — Save Call Offer",
            "subtitle": f"Save-call retention · future-cancel pool {fc_unique} unique members",
            "started": "",
            "ends": "",
            "phase": f"Concept · awaiting Monday approval",
            "target_audience": "at_risk_cancellation",
            "offer": {
                "headline": "Free Recovery month if you freeze instead of cancel.",
                "pricing": f"$0 add-on cost · {top_addon or 'Recovery'} bundled for 4 weeks",
                "base": f"Members in future-cancel pipeline ({fc_unique} currently unique)",
                "eligibility": "Active members in future-cancel pipeline who freeze for at least 4 weeks instead of cancelling.",
            },
            "tone": "Community-focused / supportive / 'we've got you' — quieter than acquisition.",
            "rationale": f"Future-cancel pool is {fc} ({fc_unique} unique). At 30% save rate × $48/mo = ~${revenue_recovery}/mo recovered revenue at zero CAC. Recovery is the top add-on ({top_addon_count} active) — bundling free as a 'stay' incentive aligns with what existing members already love.",
            "asset_requirements": {
                "reels": 3,
                "stories": 4,
                "edm_assets": 1,
                "save_call_script": 1,
            },
            "gdrive_folder_url": "",
            "child_actions": [],
            "metrics": {
                "future_cancel_pool": fc_unique,
                "save_rate_target": 30,
                "projected_revenue_saved": f"~${revenue_recovery}/mo at 30% save rate",
            },
        })

    # Rule 2: switched-to-other-gym ≥ 5 → loyalty/community defence
    if switched >= 5:
        concepts.append({
            "id": f"promo-stay-with-us-{month_iso}",
            "track": "retention",
            "stage": "Concept",
            "label": "Stay With Us — Community Defence",
            "subtitle": f"{switched} survey responses said 'switched to another gym' · loyalty perks",
            "started": "",
            "ends": "",
            "phase": "Concept · monthly perk + community series",
            "target_audience": "existing_member",
            "offer": {
                "headline": "We see you. Monthly perks for members who stay.",
                "pricing": "Free Recovery session per month · early access to group classes · monthly community event",
                "base": "Recurring monthly perk, no upgrade required",
                "eligibility": "Members 3+ months in",
            },
            "tone": "Community / 'this isn't a transaction, it's a club' / strong on what they get HERE that they won't get THERE.",
            "rationale": f"{switched} respondents flagged switching to another gym as why they'd return. Defence requires making CB247 feel like a community Anytime/Revo can't replicate. Recovery is the lever they don't have.",
            "asset_requirements": {
                "reels": 3,
                "stories": 6,
                "edm_assets": 2,
                "in_club_posters": 1,
            },
            "gdrive_folder_url": "",
            "child_actions": [],
            "metrics": {
                "switched_reduction_target_pct": 50,
                "perk_redemption_rate_target_pct": 60,
                "projected_revenue_saved": "~$3,200/mo (50% reduction × $48/mo × est. 67 members)",
            },
        })

    # Rule 3: top add-on penetration < 5% of new-contracts base → free trial
    if top_addon and top_addon_count > 0 and signals["new_contracts"] > 0:
        # Rough penetration approximation: top_addon vs active members
        # New contracts ~weekly; assume base of ~2400 active members
        if top_addon_count < 120:  # under 5% of est. base
            concepts.append({
                "id": f"promo-addon-trial-{month_iso}",
                "track": "retention",
                "stage": "Concept",
                "label": f"Try {top_addon} — Free Month",
                "subtitle": f"Top add-on '{top_addon}' has only {top_addon_count} active subscribers · headroom = recurring revenue",
                "started": "",
                "ends": "",
                "phase": "Concept · add-on trial campaign",
                "target_audience": "existing_member",
                "offer": {
                    "headline": f"Free month of {top_addon}. See why members love it.",
                    "pricing": "$0 for first month · auto-converts to $20/wk after 30 days unless cancelled",
                    "base": "Members 1+ month in",
                    "eligibility": "Members who haven't tried this add-on yet",
                },
                "tone": "Educational + genuine · 'this changes how you recover/train'.",
                "rationale": f"Only {top_addon_count} active subscribers on {top_addon} despite it being the most-popular add-on. Members who use it once almost always convert. Free month removes the perceived risk barrier. Zero marginal cost (existing facility).",
                "asset_requirements": {
                    "reels": 2,
                    "stories": 4,
                    "edm_assets": 1,
                },
                "gdrive_folder_url": "",
                "child_actions": [],
                "metrics": {
                    "trial_signup_target": 80,
                    "trial_to_paid_conversion_pct": 40,
                    "projected_add_on_revenue": "$2,560/mo recurring (80 × 40% × $20/wk × 4)",
                },
            })

    # Rule 4: "not using" ≥ 5 → welcome-back check-in
    if not_using >= 5:
        concepts.append({
            "id": f"promo-welcome-back-{month_iso}",
            "track": "retention",
            "stage": "Concept",
            "label": "Welcome Back — Check-In Series",
            "subtitle": f"{not_using} members said they 'weren't using it enough' · reactivation series",
            "started": "",
            "ends": "",
            "phase": "Concept · re-engagement EDM + free PT taster",
            "target_audience": "existing_member",
            "offer": {
                "headline": "Haven't trained in 14 days? Let's reset together.",
                "pricing": "Free 30-min PT session (existing members) · no commitment",
                "base": "Active members who haven't scanned in 14+ days",
                "eligibility": "Existing members in good standing",
            },
            "tone": "Caring / non-judgmental / supportive · 'we noticed you're missing and we want to help'.",
            "rationale": f"{not_using} survey respondents cited 'not using enough' as why they'd return. PT taster + scheduling assistance is the proven re-engagement lever. Catches members BEFORE they enter the cancel pipeline.",
            "asset_requirements": {
                "reels": 2,
                "stories": 4,
                "edm_assets": 2,
            },
            "gdrive_folder_url": "",
            "child_actions": [],
            "metrics": {
                "edm_open_target_pct": 35,
                "pt_booking_target": 50,
                "projected_revenue_saved": "~$1,800/mo (50 reactivated × $48/mo × 75% retention)",
            },
        })

    return concepts


# ── Child Work Queue items ────────────────────────────────────────────────────


def _emit_child_work_queue_items(concepts: list[dict], week: str) -> list[WorkQueueAction]:
    """For each concept, emit one WorkQueueAction per major asset type with
    parent_promo_id set. These will populate the kanban once approved."""
    out: list[WorkQueueAction] = []
    serial = 1
    today = date.today()

    for concept in concepts:
        req = concept.get("asset_requirements") or {}
        # Only emit for the headline formats — keep WQ lean
        for fmt in ("reels", "stories", "edm_assets", "landing_page", "save_call_script"):
            n = req.get(fmt)
            if not n or n <= 0:
                continue
            # Map format → category for the dashboard's source-page filter
            category_map = {
                "reels": "organic-social",
                "stories": "organic-social",
                "edm_assets": "membership",          # email goes through CRM
                "landing_page": "seo-organic",
                "save_call_script": "membership",
            }
            category = category_map.get(fmt, "organic-social")
            label_map = {
                "reels": "Capture + post",
                "stories": "Capture + post",
                "edm_assets": "Draft + send",
                "landing_page": "Build + publish",
                "save_call_script": "Write + train team",
            }
            verb = label_map.get(fmt, "Produce")
            action_id = make_action_id(f"promo-{fmt[:3]}", week, serial)
            serial += 1

            action = WorkQueueAction(
                id=action_id,
                source_page="organic-social" if category == "organic-social" else category,
                source_run_at=now_iso(),
                title=f"{verb} {n}× {fmt.replace('_', ' ')} for '{concept['label']}'",
                description=(
                    f"Child work item of promo '{concept['label']}' ({concept['id']}). "
                    f"Capture {n}× {fmt.replace('_', ' ')} on next monthly shoot day. "
                    f"Assets land in the promo's GDrive folder once Asset Creator processes them. "
                    f"Tone: {concept.get('tone', '—')}"
                ),
                owner="Brand Manager",
                owner_role="Brand Manager",
                priority="P2" if concept["track"] == "retention" else "P1",
                effort_hours=0.5 * n,
                category=category,
                data_quality="medium",
                projected_kpis=[ProjectedKPI(
                    metric="qualitative_assessment",
                    measurement_window_days=14,
                    target=1.0,
                    confidence="medium",
                )],
                parent_promo_id=concept["id"],
                source_agent="promo-concept-emitter",
            )
            out.append(action)
    return out


# ── Merging logic ─────────────────────────────────────────────────────────────


def _merge_promo_pipeline(existing: dict, new_acq: list[dict], new_ret: list[dict]) -> dict:
    """Preserve in-flight promos (anything past Concept stage). Add new Concepts
    that don't already exist by id. Existing Concepts get replaced (refresh)."""
    DOWNSTREAM = {"Approved", "Asset Shoot Scheduled", "In Production", "Active", "Performance Review"}

    def _merge_track(existing_list: list[dict], new_list: list[dict]) -> list[dict]:
        # Keep all in-flight (downstream) items
        kept = [p for p in (existing_list or []) if p.get("stage") in DOWNSTREAM]
        kept_ids = {p["id"] for p in kept}
        # Add new concepts that don't collide with in-flight ids
        for p in new_list:
            if p["id"] not in kept_ids:
                kept.append(p)
        return kept

    return {
        "generated_at": now_iso(),
        "generator": f"promo_concept_emitter v{GENERATOR_VERSION}",
        "acquisition": _merge_track(existing.get("acquisition", []), new_acq),
        "retention":   _merge_track(existing.get("retention", []),   new_ret),
    }


def _merge_work_queue(new_actions: list[WorkQueueAction]) -> dict:
    """Append new promo-child actions to state/work-queue.json. Idempotent by id."""
    if WORK_QUEUE_FILE.exists():
        try:
            existing = json.loads(WORK_QUEUE_FILE.read_text())
        except Exception:
            existing = {"actions": []}
    else:
        existing = {"actions": []}

    existing_ids = {a.get("id") for a in existing.get("actions", [])}
    added = 0
    for a in new_actions:
        if a.id in existing_ids:
            continue
        existing.setdefault("actions", []).append(to_jsonable(a))
        existing_ids.add(a.id)
        added += 1

    existing["generated_at"] = now_iso()
    existing["_promo_concept_added_this_run"] = added
    return existing


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files.")
    parser.add_argument("--month", default=None, help="Target month for concept IDs (YYYY-MM). Default: current month.")
    args = parser.parse_args()

    print(f"\n=== Promo Concept Emitter — {now_iso()} ===\n")

    month_iso = args.month or date.today().strftime("%Y-%m")
    week = week_iso()

    # Load inputs
    mem = _load_membership()
    seasonal = _load_seasonal()
    existing_pipeline = _load_existing_promo_pipeline()

    if not mem:
        print("  ⚠️  No membership-data.json — retention concepts will be skipped.")
    if not seasonal:
        print("  ⚠️  No seasonal-calendar.md — acquisition concepts will be skipped.")

    # Signals
    signals = _membership_signals(mem) if mem else {}
    events = _seasonal_events_within(60, seasonal) if seasonal else []

    print(f"Membership signals (Wave 5 retention triggers):")
    if signals:
        for k in ("future_cancellations", "future_cancellations_unique",
                  "switched_gym_responses", "not_using_responses",
                  "top_addon_name", "top_addon_count"):
            print(f"  {k}: {signals.get(k)}")
    else:
        print("  (no signals)")
    print()

    print(f"Seasonal events within 60 days ({len(events)}):")
    for ev in events:
        print(f"  - {ev['label']:38s} kind={ev['kind']:8s} days_away={ev.get('days_away','?')}")
    print()

    # Build concepts
    new_acquisition = _build_acquisition_concepts(signals, events, month_iso)
    new_retention = _build_retention_concepts(signals, month_iso)

    print(f"Generated {len(new_acquisition)} acquisition + {len(new_retention)} retention concepts for {month_iso}\n")

    for c in new_acquisition + new_retention:
        print(f"  [{c['track'].upper():11s}] {c['id']:55s} {c['label']}")

    # Build child Work Queue actions
    all_new_concepts = new_acquisition + new_retention
    new_actions = _emit_child_work_queue_items(all_new_concepts, week)
    print(f"\nGenerated {len(new_actions)} child Work Queue actions (each carries parent_promo_id).")

    # Validate WQ actions
    errs = []
    for a in new_actions:
        for e in a.validate():
            errs.append(f"{a.id}: {e}")
    if errs:
        print(f"\nVALIDATION ERRORS ({len(errs)}):")
        for e in errs[:20]:
            print(f"  - {e}")
        return 1
    print("All actions validate clean.")

    if args.dry_run:
        print("\n[dry-run] Nothing written.")
        return 0

    # Write promo pipeline
    merged_pipeline = _merge_promo_pipeline(existing_pipeline, new_acquisition, new_retention)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PROMO_FILE.write_text(json.dumps(merged_pipeline, indent=2, default=str))
    print(f"\n[promo-emitter] Wrote {PROMO_FILE.relative_to(BASE_DIR)} "
          f"({len(merged_pipeline['acquisition'])} acquisition · {len(merged_pipeline['retention'])} retention)")

    # Write work queue (append new child items)
    merged_wq = _merge_work_queue(new_actions)
    WORK_QUEUE_FILE.write_text(json.dumps(merged_wq, indent=2, default=str))
    print(f"[promo-emitter] Wrote {WORK_QUEUE_FILE.relative_to(BASE_DIR)} "
          f"(+{merged_wq.get('_promo_concept_added_this_run', 0)} new actions · "
          f"{len(merged_wq.get('actions', []))} total)")

    print()
    print("Next:")
    print("  1. Open the dashboard → Promo Pipeline → review concepts at next Monday meeting")
    print("  2. Approve concepts via View Details popup → moves them to 'Approved' stage")
    print("  3. Asset Library page → regenerate brief → Asset Creator captures on next shoot day")
    return 0


if __name__ == "__main__":
    sys.exit(main())
