"""
compute_mwcc_funnel.py — derive MWCC enrolment funnel from real data.

Stitches together two existing data sources to give Tia + Kelley a
weekly per-centre funnel without waiting for purpose-built GA4 events:

    Web sessions (GA4)
      ↓
    Conversions (GA4 key_events — proxy for enquiry form submits)
      ↓
    Enquiries (OWNA — verified phone/walk-in/online enquiries)
      ↓
    Enrolments (OWNA — confirmed starts)
      ↓
    Exits (OWNA — confirmed leavers)

Network-wide funnel is computed from GA4 totals + OWNA totals.
Per-centre funnel is computed from OWNA per-centre fields (GA4 can't
attribute per-centre without UTM landing-page tags — flagged as TODO).

Output: state/mwcc-funnel.json — consumed by future dashboard widget
        renderMwccConversionFunnel + by the email digest "Funnel Health"
        section.

Run:
    python3 scripts/compute_mwcc_funnel.py

Wired into:
    Add to scripts/weekly-report-mwcc.sh after Step 4 (ops parse) and
    Step 1 (GA4 pull) complete. Both inputs must exist for funnel to
    compute. Graceful degrade: if GA4 missing, web step shows null;
    if OWNA missing, per-centre block shows null.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Dict, Any

BASE_DIR    = Path(__file__).resolve().parent.parent
STATE_DIR   = BASE_DIR / "state"
GA4_FILE    = STATE_DIR / "mwcc-ga4.json"
OPS_FILE    = STATE_DIR / "mwcc-ops.json"
OUTPUT_FILE = STATE_DIR / "mwcc-funnel.json"


def _load_json(p: Path) -> Dict[str, Any] | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"[funnel] ERROR reading {p.name}: {e}")
        return None


def _pct(numer, denom):
    if not denom:
        return None
    return round(100.0 * numer / denom, 1)


def main() -> int:
    ga4 = _load_json(GA4_FILE)
    ops = _load_json(OPS_FILE)

    if ga4 is None and ops is None:
        print("[funnel] No GA4 or OWNA data — nothing to compute")
        return 0

    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()

    # ── Network-wide funnel ──────────────────────────────────────
    network: Dict[str, Any] = {
        "period_label": None,
        "web_sessions": None,
        "web_conversions": None,
        "enquiries": None,
        "enrolments": None,
        "exits": None,
        "net_movement": None,
        "session_to_conversion_pct": None,
        "enquiry_to_enrolment_pct": None,
        "conversion_to_enquiry_pct": None,
    }

    if ga4 and ga4.get("current"):
        cur = ga4["current"]
        network["web_sessions"]    = cur.get("sessions")
        network["web_conversions"] = cur.get("key_events")
        network["period_label"]    = f"{ga4.get('date_range', {}).get('start')} → {ga4.get('date_range', {}).get('end')}"
        if network["web_sessions"] and network["web_conversions"]:
            network["session_to_conversion_pct"] = _pct(
                network["web_conversions"], network["web_sessions"]
            )

    if ops and ops.get("network_summary"):
        net = ops["network_summary"]
        network["enquiries"]    = net.get("total_enquiries")
        network["enrolments"]   = net.get("total_enrolments")
        network["exits"]        = net.get("total_exits")
        network["net_movement"] = net.get("net_movement")
        if network["enquiries"] and network["enrolments"] is not None:
            network["enquiry_to_enrolment_pct"] = _pct(
                network["enrolments"], network["enquiries"]
            )
        if (
            network["web_conversions"]
            and network["enquiries"]
            and network["web_conversions"] > 0
        ):
            # Loose — web conversions (key_events) MIGHT be enquiry form
            # submits, OR might include other events. Treat as upper bound.
            network["conversion_to_enquiry_pct"] = _pct(
                network["enquiries"], network["web_conversions"]
            )

    # ── Per-centre funnel ────────────────────────────────────────
    centres = []
    if ops and ops.get("centres"):
        for centre_key, c in ops["centres"].items():
            row = {
                "centre": c.get("name") or centre_key,
                "enquiries":  c.get("enquiries"),
                # Per-centre enrolments aren't in the network_summary
                # rollup — the OWNA per-centre block doesn't break out
                # enrolments per centre directly. Mark as not-attributable
                # and let Kelley fill in via the form.
                "enrolments": None,
                "exits":      None,
                "enquiry_to_enrolment_pct": None,
                "_note": "OWNA per-centre breakdown for enrolments/exits not currently parsed — see parse_mwcc_ops.py to extend. Use network_summary for now.",
            }
            centres.append(row)

    # ── Compose output ───────────────────────────────────────────
    output = {
        "_generated_at": now_iso,
        "_inputs": {
            "ga4_file": str(GA4_FILE.relative_to(BASE_DIR)) if ga4 else "MISSING",
            "ops_file": str(OPS_FILE.relative_to(BASE_DIR)) if ops else "MISSING",
        },
        "network": network,
        "centres": centres,
        "_dashboard_widget_spec": {
            "location": "docs/index.html — new render function renderMwccConversionFunnel (call from renderMwccOverview right above Per-centre cards)",
            "data_source": "state/mwcc-funnel.json (loaded into cbState.mwccFunnel on page load)",
            "render_shape": [
                "1. Section title: 'Enrolment Funnel — week of [period_label]'",
                "2. 5-stage horizontal funnel: Web sessions → Web conversions → Enquiries → Enrolments — Exits",
                "3. Conversion % between each stage shown on connecting arrows",
                "4. Each stage card: number + WoW delta arrow + colour by health (green/amber/red)",
                "5. Below funnel: 'What's leaking?' callout — points to weakest stage",
            ],
            "ga4_event_setup_required": [
                "GA4 key_events count (110 this week) is too aggregate. To get a clean tour-form-submit count, add the following custom event in Google Tag Manager:",
                "  event_name: tour_form_submit",
                "  trigger: form submission where form has class .mwcc-tour-form OR url contains /book-tour",
                "  mark as conversion in GA4 admin",
                "After 2-3 weeks of data, swap network.web_conversions to read this specific event count instead of total key_events.",
            ],
            "owna_parse_extension_required": [
                "Extend scripts/parse_mwcc_ops.py to populate per-centre enrolments + exits (currently only network_summary).",
                "OWNA Excel has the data — the per-centre extraction logic isn't running yet.",
                "When that's done, the per-centre funnel becomes meaningful and the email digest can show 'Midvale enrolment rate dropped to 12% — 3rd week in a row'.",
            ],
        },
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"[funnel] ✅ Wrote → {OUTPUT_FILE.relative_to(BASE_DIR)}")
    print(f"[funnel]    Period:      {network.get('period_label') or 'n/a'}")
    print(f"[funnel]    Sessions:    {network.get('web_sessions')}")
    print(f"[funnel]    Conversions: {network.get('web_conversions')}")
    print(f"[funnel]    Enquiries:   {network.get('enquiries')}")
    print(f"[funnel]    Enrolments:  {network.get('enrolments')}")
    print(f"[funnel]    Net move:    {network.get('net_movement')}")
    if network.get("enquiry_to_enrolment_pct") is not None:
        print(f"[funnel]    Enquiry → Enrolment: {network['enquiry_to_enrolment_pct']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
