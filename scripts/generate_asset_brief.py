"""
generate_asset_brief.py — Bake the monthly Asset Creator brief (markdown).

The Asset Creator works in a monthly batch model. One shoot day per month
captures content for every active promo (acquisition + retention tracks).
This script reads the active promos + next shoot date and writes a single
consolidated brief to outputs/asset-briefs/{YYYY-MM}-brief.md.

Data source priority:
  1. state/promo-pipeline.json     (written by Wave 5 Promo Concept Generator)
  2. Embedded fallback below       (mirrors docs/index.html PROMO_PIPELINE_DATA
                                    until the JSON file exists)

Embedded ASSET_LIBRARY_DATA mirrors the JS constant of the same name. Keep
the two in sync — Tia edits the shoot schedule in docs/index.html and this
script picks it up the same week. (Wave 5 should externalise this to JSON.)

Run:
    python scripts/generate_asset_brief.py
    python scripts/generate_asset_brief.py --shoot 2026-07-23      # specific shoot date
    python scripts/generate_asset_brief.py --print                  # stdout, don't write file

Wave 4 follow-up: a sibling script send_asset_brief.py can email this file
to ASSET_CREATOR_EMAIL ~7 days before each shoot via cron.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "state" / "promo-pipeline.json"
OUTPUT_DIR = BASE_DIR / "outputs" / "asset-briefs"


# ── Embedded fallback (mirrors docs/index.html PROMO_PIPELINE_DATA) ───────────
# Keep in sync with the JS constant until Wave 5 externalises to state/.
PROMO_PIPELINE_DATA_FALLBACK = {
    "acquisition": [
        {
            "id": "promo-winter-is-coming-2026-06",
            "track": "acquisition",
            "stage": "In Production",
            "label": "Winter Is Coming",
            "subtitle": "3-month winter campaign framework (Jun-Aug)",
            "started": "2026-06-01",
            "ends": "2026-08-31",
            "phase": "Phase 2 — Main Launch (1 Jun)",
            "target_audience": "new_member",
            "offer": {
                "headline": "Tapered free months — earlier you join, more you get",
                "pricing": "June: 3 months free · July: 2 months · August: 1 month",
                "base": "$11.95/wk all-access base",
                "eligibility": "New members only",
            },
            "tone": "Strong / cinematic / high-energy / community-focused. \"Don't go backwards this winter.\"",
            "rationale": "Winter is the natural acquisition dip. Tapered offer creates urgency. Cinematic tone differentiates.",
            "asset_requirements": {
                "reels": 6, "stories": 12, "static_posts": 4,
                "edm_assets": 1, "landing_page": 1, "in_club_posters": 2,
            },
            "gdrive_folder_url": "",
            "metrics": {
                "new_joins_target": 80,
                "new_joins_actual": 63,
                "projected_revenue_lift": "$11,420/mo at full pipeline",
            },
        },
    ],
    "retention": [
        {
            "id": "promo-dont-quit-winter-2026-06",
            "track": "retention",
            "stage": "Concept",
            "label": "Don't Quit Winter",
            "subtitle": "Save-call retention offer · counterpart to Winter Is Coming",
            "started": "",
            "ends": "2026-08-31",
            "phase": "Awaiting Monday approval",
            "target_audience": "at_risk_cancellation",
            "offer": {
                "headline": "Free Recovery month if you freeze instead of cancel",
                "pricing": "$0 add-on cost · Sauna + Ice Bath through 31 August",
                "base": "Members in future-cancel pipeline (352 currently)",
                "eligibility": "Active members in future-cancel pipeline who freeze for at least 4 weeks instead of cancelling",
            },
            "tone": "Community-focused / supportive / \"we've got you\" — quieter than cinematic acquisition.",
            "rationale": "Future-cancel pipeline is 352 (4× new joins/wk). Recovery is the top add-on (19 active). Bundling free as a stay incentive = ~$4,800/mo recovered revenue at zero CAC.",
            "asset_requirements": {
                "reels": 3, "stories": 4, "edm_assets": 1, "save_call_script": 1,
            },
            "gdrive_folder_url": "",
            "metrics": {
                "future_cancel_pool": 352,
                "save_rate_target": 30,
                "projected_revenue_saved": "$4,800/mo",
            },
        },
        {
            "id": "promo-held-the-line-2026-07",
            "track": "retention",
            "stage": "Concept",
            "label": "Held the Line",
            "subtitle": "Loyalty perk for 6mo+ members · August reward",
            "started": "",
            "ends": "2026-08-31",
            "phase": "Concept · Aug rollout planned",
            "target_audience": "existing_member",
            "offer": {
                "headline": "Free Recovery month in August for members 6+ months in",
                "pricing": "$0 add-on · normally $20/wk",
                "base": "No upfront commitment required",
                "eligibility": "Members with 6+ months tenure",
            },
            "tone": "Community-focused · \"You stayed through winter, we've got you\" · gratitude angle.",
            "rationale": "Recovery trial → recurring add-on revenue + loyalty signal. Zero marginal cost (existing facility).",
            "asset_requirements": {
                "reels": 2, "stories": 4, "edm_assets": 1,
            },
            "gdrive_folder_url": "",
            "metrics": {
                "eligible_pool": "~2,400 members",
                "conversion_target": 25,
                "projected_add_on_revenue": "$2,000/mo recurring",
            },
        },
    ],
}

# Shoot schedule — same as JS ASSET_LIBRARY_DATA.shoot_schedule
SHOOT_SCHEDULE = [
    {"date": "2026-06-18", "location": "CB247 Ellenbrook", "status": "scheduled",
     "notes": "Phase 2 Winter Is Coming main launch + Don't Quit Winter retention intro"},
    {"date": "2026-07-23", "location": "CB247 Malaga",     "status": "planned",
     "notes": "Phase 3 Winter wrap + Held the Line teaser"},
    {"date": "2026-08-20", "location": "CB247 Ellenbrook", "status": "planned",
     "notes": "Held the Line August reward + Spring transition assets"},
]

ACTIVE_STAGES = {"Concept", "Approved", "Asset Shoot Scheduled", "In Production"}

AUDIENCE_LABELS = {
    "new_member":           "New Members",
    "existing_member":      "Existing Members",
    "at_risk_cancellation": "At-Risk · Future-Cancel Pipeline",
    "win_back_pool":        "Win-Back Pool",
}


def _load_promo_data() -> dict:
    """Prefer state/promo-pipeline.json (written by Wave 5), fall back to embedded."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            if "acquisition" in data and "retention" in data:
                return data
        except Exception as e:
            print(f"  ⚠️  Could not parse {STATE_FILE.relative_to(BASE_DIR)}: {e} — falling back to embedded data.")
    return PROMO_PIPELINE_DATA_FALLBACK


def _next_shoot(override: str | None = None) -> dict | None:
    if override:
        match = next((s for s in SHOOT_SCHEDULE if s["date"] == override), None)
        if match:
            return match
        # Build a synthetic entry for an arbitrary date
        return {"date": override, "location": "—", "status": "scheduled", "notes": "(date passed via --shoot)"}
    today = date.today()
    future = [s for s in SHOOT_SCHEDULE if s["status"] != "completed"
              and datetime.strptime(s["date"], "%Y-%m-%d").date() >= today]
    future.sort(key=lambda s: s["date"])
    return future[0] if future else None


def _active_promos(data: dict) -> list[dict]:
    out: list[dict] = []
    for track in ("acquisition", "retention"):
        for p in data.get(track, []):
            if p.get("stage") in ACTIVE_STAGES:
                out.append(p)
    return out


def _aggregate_assets(promos: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for p in promos:
        for k, v in (p.get("asset_requirements") or {}).items():
            if isinstance(v, (int, float)):
                totals[k] = totals.get(k, 0) + int(v)
    return totals


def _format_key(k: str) -> str:
    return k.replace("_", " ").title()


def _days_until(iso_date: str) -> int:
    target = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return (target - date.today()).days


def _build_brief(shoot: dict, promos: list[dict], totals: dict[str, int]) -> str:
    grand_total = sum(totals.values())
    shoot_iso = shoot["date"]
    shoot_dt = datetime.strptime(shoot_iso, "%Y-%m-%d")
    days = _days_until(shoot_iso)
    days_label = (
        f"Today" if days == 0 else
        f"{days} day{'s' if days != 1 else ''} away" if days > 0 else
        f"{abs(days)} day{'s' if abs(days) != 1 else ''} overdue"
    )

    lines: list[str] = []
    lines.append(f"# Asset Brief — {shoot_dt.strftime('%B %Y')}")
    lines.append("")
    lines.append(f"**Shoot date:** {shoot_iso} ({shoot_dt.strftime('%A, %d %B %Y')}) · _{days_label}_  ")
    lines.append(f"**Location:** {shoot['location']}  ")
    lines.append(f"**Focus:** {shoot['notes']}  ")
    lines.append(f"**Active promos:** {len(promos)}  ")
    lines.append(f"**Total assets to capture:** **{grand_total}** across {len(totals)} formats  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Consolidated totals table
    lines.append("## Consolidated Asset Totals")
    lines.append("")
    if totals:
        lines.append("| Asset Format | Quantity |")
        lines.append("|---|---:|")
        for k, v in sorted(totals.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {_format_key(k)} | {v} |")
        lines.append(f"| **TOTAL** | **{grand_total}** |")
    else:
        lines.append("_No active promos prepping for next shoot._")
    lines.append("")

    # Per-promo breakdown
    lines.append("---")
    lines.append("")
    lines.append("## Per-Promo Briefs")
    lines.append("")

    for p in promos:
        audience = AUDIENCE_LABELS.get(p.get("target_audience", ""), p.get("target_audience", "—"))
        lines.append(f"### {p['label']}")
        lines.append("")
        lines.append(f"- **Track:** {p['track'].title()}")
        lines.append(f"- **Audience:** {audience}")
        lines.append(f"- **Stage:** {p.get('stage', '—')}")
        lines.append(f"- **Subtitle:** {p.get('subtitle', '')}")
        lines.append("")
        offer = p.get("offer", {})
        if offer:
            lines.append(f"**Offer headline:** {offer.get('headline', '—')}  ")
            lines.append(f"**Pricing:** {offer.get('pricing', '—')}  ")
            lines.append(f"**Eligibility:** {offer.get('eligibility', '—')}  ")
            lines.append("")
        if p.get("tone"):
            lines.append(f"**Tone:** {p['tone']}")
            lines.append("")
        if p.get("rationale"):
            lines.append(f"**Why this matters:** {p['rationale']}")
            lines.append("")

        # Asset requirements
        reqs = p.get("asset_requirements") or {}
        if reqs:
            lines.append("**Assets to capture for this promo:**")
            lines.append("")
            for k, v in reqs.items():
                lines.append(f"- {v}× **{_format_key(k)}**")
            lines.append("")

        # GDrive folder
        gdrive = p.get("gdrive_folder_url") or ""
        if gdrive:
            lines.append(f"**Google Drive folder:** {gdrive}")
        else:
            lines.append("**Google Drive folder:** ⚠️ _Not set — paste URL into the promo before shoot day. Assets land here._")
        lines.append("")

        # Metrics
        metrics = p.get("metrics") or {}
        if metrics:
            lines.append("**Targets:**")
            for k, v in metrics.items():
                lines.append(f"- {_format_key(k)}: {v}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Production stack reminder
    lines.append("## Post-Shoot AI Production Stack")
    lines.append("")
    lines.append("After capture, process with:")
    lines.append("")
    lines.append("- **Opus Clip** — auto-cut long-form footage → reels + TikTok shorts ($15/mo)")
    lines.append("- **Captions** — AI captions + B-roll fillers + face tracking ($24/mo)")
    lines.append("- **Canva Pro** — static posts, stories, EDM headers, in-club posters ($15/mo)")
    lines.append("- **Midjourney** — concept art, alternative thumbnails, cinematic stills ($20/mo)")
    lines.append("")
    lines.append("Total stack: ~$74/mo (replaces external video editor + graphics contractor costs).")
    lines.append("")

    # Workflow reminder
    lines.append("## Workflow Reminder")
    lines.append("")
    lines.append("1. **Pre-shoot (T-7 days):** Brief Manager reviews this doc + confirms locations, equipment, talent.")
    lines.append("2. **Shoot day:** Capture all formats above in one session. Upload raw to the per-promo GDrive folder.")
    lines.append("3. **Post (T+1 to T+5):** Asset Creator processes via AI stack. Final deliverables → same folder, `/final` subfolder.")
    lines.append("4. **Hand-off:** Update each Promo Pipeline card with `gdrive_folder_url`. \"Awaiting Assets\" badges on the Work Queue kanban cards will clear automatically.")
    lines.append("5. **Publish:** Brand Manager QC → Scheduled → Published per the standard kanban flow.")
    lines.append("")

    lines.append(f"_Brief generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} · scripts/generate_asset_brief.py_")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the monthly Asset Creator brief (markdown).")
    parser.add_argument("--shoot", type=str, default=None,
                        help="ISO shoot date (e.g. 2026-07-23). Default: next upcoming shoot.")
    parser.add_argument("--print", dest="print_only", action="store_true",
                        help="Print the brief to stdout instead of writing the file.")
    args = parser.parse_args()

    data = _load_promo_data()
    shoot = _next_shoot(args.shoot)
    if not shoot:
        print("[asset-brief] ❌ No upcoming shoot found. Add one to SHOOT_SCHEDULE.", file=sys.stderr)
        return 1

    promos = _active_promos(data)
    totals = _aggregate_assets(promos)

    brief_md = _build_brief(shoot, promos, totals)

    if args.print_only:
        print(brief_md)
        return 0

    # Filename uses shoot's YYYY-MM
    shoot_dt = datetime.strptime(shoot["date"], "%Y-%m-%d")
    out_file = OUTPUT_DIR / f"{shoot_dt.strftime('%Y-%m')}-brief.md"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file.write_text(brief_md)

    grand_total = sum(totals.values())
    print(f"[asset-brief] ✅ Wrote {out_file.relative_to(BASE_DIR)}")
    print(f"[asset-brief]    Shoot: {shoot['date']} · {shoot['location']}")
    print(f"[asset-brief]    Active promos: {len(promos)} · Total assets: {grand_total}")
    print()
    print("Next:")
    print(f"  Email the brief to the Asset Creator 7 days before shoot.")
    print(f"  Path: {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
