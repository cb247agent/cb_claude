"""
parse_mwcc_ops.py — Parses OWNA weekly exports for My World Childcare.

Reads from mwcc-inbox/:
  MYWORLD_REPORT*.xlsx  — revenue, wage %, enquiries, exits, enrolments per centre
  utilisation*.xlsx     — per-room daily occupancy (Mon–Fri) per centre

Saves to state/mwcc-ops.json

Usage:
  python scripts/parse_mwcc_ops.py              # reads from mwcc-inbox/
  python scripts/parse_mwcc_ops.py /custom/path # reads from a custom folder

Drop zone workflow:
  Every Monday before 2pm, drop MYWORLD_REPORT.xlsx + utilisation.xlsx into mwcc-inbox/
  The 2pm cron runs this script automatically.

Data notes:
  - Reporting convention (agreed 07 Jun 2026):
    · OWNA centre operations data → Mon–Fri (centres operate weekdays only).
      For 07 Jun report: 01–05 Jun 2026.
    · Digital marketing (GA4, GSC, Meta, Google Ads, Metricool/social) → Sat–Fri.
      Captures weekend digital activity that centres don't have.
      For 07 Jun report: 30 May – 05 Jun 2026.
  - The parser overrides the OWNA file's native period with the computed Mon-Fri
    window via compute_owna_week(). The original file-reported period is kept
    in output['period']['owna_file_period'] for reference.
  - Wage breach threshold: 42% (wage exc. leave) — NOT surfaced in marketing UI
    (HR/finance concern, not marketing). Available in data for ops tooling.
  - Compliance risk: room occupancy > 100%
  - Centre name mapping: OWNA uses 'WAKIKI' — canonical name is 'Waikiki'
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple


def compute_owna_week():
    """Compute the Mon→Fri window for the last completed working week.

    Convention agreed 07 Jun 2026 (Tia):
      OWNA centre operations data is Mon–Fri because centres only operate
      weekdays. Sat/Sun = closed = always zero. Reporting on Mon–Fri removes
      noise and aligns with how the team actually runs the business.

    Marketing scripts (GA4/GSC/Meta/Ads) report Sat–Fri (the wider 7-day
    window that captures weekend digital activity). These are documented as
    different windows by design.

    Returns (start_date_str, end_date_str) in YYYY-MM-DD format.
    end = last completed Friday
    start = same week's Monday = end - 4 days
    """
    today = datetime.today()
    days_since_friday = (today.weekday() - 4) % 7
    end_date   = today - timedelta(days=days_since_friday)
    start_date = end_date - timedelta(days=4)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

try:
    import openpyxl
except ImportError:
    print("[MWCC Ops] ERROR: openpyxl not installed.")
    print("           Run: pip install openpyxl")
    sys.exit(1)

BASE_DIR    = Path(__file__).resolve().parent.parent
INBOX_DIR   = BASE_DIR / "mwcc-inbox"
STATE_DIR   = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "mwcc-ops.json"

WAGE_BREACH_THRESHOLD = 42.0  # wage exc. leave % above this = breach

# OWNA centre name → canonical display name
CENTRE_MAP = {
    "ARMADALE OSHC":   "Armadale",
    "MIDVALE":         "Midvale",
    "ROCKINGHAM OSHC": "Rockingham",
    "SEVILLE GROVE":   "Seville Grove",
    "WAKIKI":          "Waikiki",   # OWNA spells it WAKIKI
    "WAIKIKI":         "Waikiki",
}

# Utilisation sheet name → canonical centre name
SHEET_CENTRE_MAP = {
    "Armadale":     "Armadale",
    "Midvale":      "Midvale",
    "Rockingham":   "Rockingham",
    "Seville Grove":"Seville Grove",
    "Wakiki":       "Waikiki",
    "Waikiki":      "Waikiki",
}

# Room name normalisation (lowercase → canonical)
ROOM_MAP = {
    "babies room":   "Babies",
    "toddlers room": "Toddlers",
    "kindy room":    "Kindy",
    "before school": "Before School",
    "after school":  "After School",
    "vacation care": "Vacation",
    "vacation":      "Vacation",
}


# ─────────────────────────────────────────────────────────────────
# File discovery
# ─────────────────────────────────────────────────────────────────

def _find_file(inbox: Path, prefix: str) -> Optional[Path]:
    """Find the most recently modified xlsx matching prefix* in inbox."""
    matches = sorted(inbox.glob(f"{prefix}*.xlsx"), key=lambda f: f.stat().st_mtime, reverse=True)
    if matches:
        return matches[0]
    exact = inbox / f"{prefix}.xlsx"
    return exact if exact.exists() else None


# ─────────────────────────────────────────────────────────────────
# MYWORLD_REPORT parser
# ─────────────────────────────────────────────────────────────────

def _parse_myworld_report(path: Path) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
    """
    Parse MYWORLD_REPORT.xlsx 'Weekly Report' sheet.

    Columns (confirmed from live file):
      1  Start Date             — the reporting week start (Monday)
      2  End Date               — the reporting week end (Sunday)
      3  Center                 — OWNA centre name
      4  Wage Inc Leave (%)
      5  Wage Exc Leave (%)     ← primary wage health metric
      6  Revenue ($)
      7  Roster Cost ($)
      8  Leave ($)
      9  Babies (%)             ← room occupancy %
     10  Todds (%)
     11  Kindy (%)
     12  B/S (%)                ← Before School
     13  A/S (%)                ← After School
     14  Vacation (%)
     15  Overall (%)            ← blended centre occupancy
     28  Enquiries
     29  Exits
     30  Enrollments

    Strategy: find max(Start Date), extract all 5 centre rows for that date.
    """
    print(f"[MWCC Ops] Parsing MYWORLD_REPORT: {path.name}")
    wb = openpyxl.load_workbook(path, data_only=True)

    if "Weekly Report" not in wb.sheetnames:
        print(f"[MWCC Ops]   ⚠️  Sheet 'Weekly Report' not found. Sheets: {wb.sheetnames}")
        return None, None, None

    ws = wb["Weekly Report"]

    # --- Find most recent Start Date ---
    max_date = None
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue
        try:
            d = row[0].date() if hasattr(row[0], "date") else datetime.fromisoformat(str(row[0])).date()
            if max_date is None or d > max_date:
                max_date = d
        except Exception:
            continue

    if not max_date:
        print("[MWCC Ops]   ⚠️  No valid dates found in MYWORLD_REPORT")
        return None, None, None

    print(f"[MWCC Ops]   Reporting week: {max_date}")

    def _f(v):
        try: return float(v or 0)
        except: return 0.0

    def _i(v):
        try: return int(float(v or 0))
        except: return 0

    result      = {}
    period_start = None
    period_end   = None

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue
        try:
            d = row[0].date() if hasattr(row[0], "date") else datetime.fromisoformat(str(row[0])).date()
        except Exception:
            continue
        if d != max_date:
            continue

        # Set period from first matching row
        if period_start is None:
            period_start = str(row[0])[:10]
            period_end   = str(row[1])[:10]

        centre_raw  = str(row[2]).strip().upper()
        centre_name = CENTRE_MAP.get(centre_raw, centre_raw.title())

        wage_exc = _f(row[4])
        wage_inc = _f(row[3])
        revenue  = _f(row[5])
        roster   = _f(row[6])
        leave    = _f(row[7])
        enrolments = _i(row[29])
        exits      = _i(row[28])

        result[centre_name] = {
            "name":               centre_name,
            "raw_name":           centre_raw,
            "revenue":            round(revenue, 2),
            "wage_inc_leave_pct": round(wage_inc, 2),
            "wage_exc_leave_pct": round(wage_exc, 2),
            "roster_cost":        round(roster, 2),
            "leave_cost":         round(leave, 2),
            "wage_breach":        wage_exc > WAGE_BREACH_THRESHOLD,
            # Room occupancy % from MYWORLD_REPORT (weekly avg, already rounded)
            "occupancy": {
                "Babies":         _i(row[8]),
                "Toddlers":       _i(row[9]),
                "Kindy":          _i(row[10]),
                "Before School":  _i(row[11]),
                "After School":   _i(row[12]),
                "Vacation":       _i(row[13]),
                "Overall":        _i(row[14]),
            },
            "enquiries":    _i(row[27]),
            "exits":        exits,
            "enrolments":   enrolments,
            "net_movement": enrolments - exits,
        }

    print(f"[MWCC Ops]   Centres loaded: {list(result.keys())}")
    return result, period_start, period_end


# ─────────────────────────────────────────────────────────────────
# Utilisation parser
# ─────────────────────────────────────────────────────────────────

def _parse_utilisation(path: Path) -> dict:
    """
    Parse utilisation xlsx → per-centre, per-room occupancy detail.

    Structure (one sheet per centre):
      Each sheet has multiple week blocks, each block:
        Header row  : ['Service Name', 'Mon DD, YYYY', 'Daily Capacity', 'MON...', ...]
        Room rows   : [service, room_name, capacity, mon, tue, wed, thu, fri, sat, sun]
        Total row   : ['', '', 'Total', ...]
        Occ % row   : ['', '', 'Daily Occupancy %', '55%', ...]
        Blank row   : (separator between weeks)

    Strategy: take the LAST header block (most recent week).
    Occupancy % = avg(Mon–Fri occupied) / capacity × 100
    Compliance risk = occupancy % > 100 (exceeds licensed capacity)
    """
    print(f"[MWCC Ops] Parsing utilisation: {path.name}")
    wb     = openpyxl.load_workbook(path, data_only=True)
    result = {}

    for sheet_name in wb.sheetnames:
        centre_name = SHEET_CENTRE_MAP.get(sheet_name)
        if not centre_name:
            print(f"[MWCC Ops]   Skipping unknown sheet: '{sheet_name}'")
            continue

        ws   = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))

        # Find all header rows (col[0] == 'Service Name')
        header_idx_list = [i for i, r in enumerate(rows) if r[0] == "Service Name"]
        if not header_idx_list:
            print(f"[MWCC Ops]   ⚠️  No week blocks found in sheet '{sheet_name}'")
            continue

        # Take the LAST week block
        last_idx  = header_idx_list[-1]
        header_row = rows[last_idx]
        week_label = str(header_row[1]) if header_row[1] else "unknown"

        # Collect block rows until blank or end of sheet
        block = []
        for row in rows[last_idx + 1:]:
            has_data = any(v is not None and str(v).strip() for v in row)
            if not has_data:
                break
            block.append(row)

        rooms          = {}
        daily_occ_pcts = []

        for row in block:
            col2 = str(row[2] or "").strip()

            # Total row — skip
            if col2 == "Total":
                continue

            # Daily Occupancy % row — capture Mon-Fri trend
            if col2 == "Daily Occupancy %":
                daily_occ_pcts = []
                for v in row[3:8]:   # Mon(3) Tue(4) Wed(5) Thu(6) Fri(7)
                    try:
                        pct = float(str(v or "0").replace("%", "").strip())
                        daily_occ_pcts.append(round(pct, 1))
                    except Exception:
                        daily_occ_pcts.append(0.0)
                continue

            # Room row — col[1] = room name
            room_raw = str(row[1] or "").strip()
            if not room_raw:
                continue

            room_name = ROOM_MAP.get(room_raw.lower(), room_raw)

            try:
                capacity = int(float(row[2] or 0))
            except Exception:
                capacity = 0

            # Mon–Fri values (cols index 3–7); skip Sat/Sun (8–9)
            daily_vals = []
            for v in row[3:8]:
                try:
                    daily_vals.append(int(float(v or 0)))
                except Exception:
                    daily_vals.append(0)

            # Average over active days only (ignore 0s on short weeks)
            active = [v for v in daily_vals if v > 0]
            avg    = round(sum(active) / len(active), 1) if active else 0.0
            occ    = round(avg / capacity * 100, 1) if capacity > 0 else 0.0

            rooms[room_name] = {
                "capacity":        capacity,
                "avg_daily":       avg,
                "occupancy_pct":   occ,
                "daily_mon_fri":   daily_vals,
                "compliance_risk": occ > 100.0,
            }

        result[centre_name] = {
            "week_label":     week_label,
            "rooms":          rooms,
            "daily_occ_pcts": daily_occ_pcts,
        }

        room_summary = "  ".join(
            f"{r}: {d['occupancy_pct']}%{'⚠' if d['compliance_risk'] else ''}"
            for r, d in rooms.items()
        )
        print(f"[MWCC Ops]   {centre_name}: {room_summary}")

    return result


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def parse_mwcc_ops(inbox_path=None):
    inbox = Path(inbox_path) if inbox_path else INBOX_DIR

    if not inbox.exists():
        msg = f"mwcc-inbox/ not found at {inbox}"
        print(f"[MWCC Ops] ⚠️  {msg}")
        print(f"[MWCC Ops]    Create it and drop MYWORLD_REPORT.xlsx + utilisation.xlsx there.")
        _write_empty(msg)
        return None

    report_file      = _find_file(inbox, "MYWORLD_REPORT")
    utilisation_file = _find_file(inbox, "utilisation")

    if not report_file and not utilisation_file:
        msg = "No xlsx files found in mwcc-inbox/"
        print(f"[MWCC Ops] ⚠️  {msg} — dropping empty ops state.")
        _write_empty(msg)
        return None

    # --- Parse MYWORLD_REPORT ---
    ops_data     = {}
    period_start = None
    period_end   = None

    if report_file:
        centres_data, period_start, period_end = _parse_myworld_report(report_file)
        if centres_data:
            ops_data = centres_data
    else:
        print("[MWCC Ops] ⚠️  MYWORLD_REPORT*.xlsx not found — revenue/wage/enquiry data missing")

    # --- Parse utilisation and merge room detail ---
    if utilisation_file:
        util_data = _parse_utilisation(utilisation_file)
        for centre_name, util in util_data.items():
            if centre_name in ops_data:
                # Merge: utilisation gives daily granularity, overrides MYWORLD_REPORT room %s
                ops_data[centre_name]["rooms_detail"]   = util["rooms"]
                ops_data[centre_name]["daily_occ_pcts"] = util["daily_occ_pcts"]
            else:
                # Centre appears only in utilisation (no financial data this week)
                ops_data[centre_name] = {
                    "name":           centre_name,
                    "rooms_detail":   util["rooms"],
                    "daily_occ_pcts": util["daily_occ_pcts"],
                }
    else:
        print("[MWCC Ops] ⚠️  utilisation*.xlsx not found — per-room daily data missing")

    # --- Network summary ---
    total_enquiries  = sum(c.get("enquiries",  0) for c in ops_data.values())
    total_exits      = sum(c.get("exits",      0) for c in ops_data.values())
    total_enrolments = sum(c.get("enrolments", 0) for c in ops_data.values())
    total_revenue    = sum(c.get("revenue",    0) for c in ops_data.values())

    breach_centres = [
        n for n, c in ops_data.items() if c.get("wage_breach", False)
    ]
    compliance_risk_rooms = [
        f"{centre} — {room}"
        for centre, c in ops_data.items()
        for room, d in c.get("rooms_detail", {}).items()
        if d.get("compliance_risk", False)
    ]

    # Override the period from the OWNA file with the canonical Mon-Fri window.
    # Convention: centres operate Mon-Fri only. OWNA's native Mon-Sun export
    # always has zeros for Sat/Sun anyway, so trimming to Mon-Fri removes noise
    # and aligns with how the team reports the business. Computed deterministically
    # from today's date so the dashboard always shows the canonical "last completed
    # working week" regardless of what the OWNA export's header row contains.
    file_period_start, file_period_end = period_start, period_end
    period_start, period_end = compute_owna_week()
    period_label = f"{period_start} to {period_end}"

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":        "mwcc",
        "period": {
            "start":  period_start,
            "end":    period_end,
            "label":  period_label,
            "note":   "OWNA centre operations data is Mon–Fri (centres operate weekdays only). Digital marketing scripts (GA4, GSC, Meta, Google Ads, Metricool) report Sat–Fri to capture weekend digital activity.",
            "owna_file_period": f"{file_period_start} to {file_period_end}" if file_period_start else "unknown",
        },
        "network_summary": {
            "total_enquiries":            total_enquiries,
            "total_enrolments":           total_enrolments,
            "total_exits":                total_exits,
            "net_movement":               total_enrolments - total_exits,
            "total_revenue":              round(total_revenue, 2),
            "centres_in_wage_breach":     breach_centres,
            "rooms_with_compliance_risk": compliance_risk_rooms,
        },
        "centres": ops_data,
        "source_files": {
            "myworld_report": report_file.name      if report_file      else None,
            "utilisation":    utilisation_file.name if utilisation_file else None,
        },
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))

    # --- Console summary ---
    print(f"\n[MWCC Ops] ✅ Saved → {OUTPUT_FILE}")
    print(f"[MWCC Ops] Period      : {period_label}")
    print(f"[MWCC Ops] Enquiries   : {total_enquiries}  |  Enrolments: {total_enrolments}  |  Exits: {total_exits}  |  Net: {total_enrolments - total_exits:+d}")
    print(f"[MWCC Ops] Revenue     : ${total_revenue:,.2f}")
    if breach_centres:
        print(f"[MWCC Ops] ⚠️  Wage breach (>{WAGE_BREACH_THRESHOLD}%): {', '.join(breach_centres)}")
    if compliance_risk_rooms:
        print(f"[MWCC Ops] ⚠️  Occupancy >100%: {', '.join(compliance_risk_rooms)}")

    return output


def _write_empty(reason: str):
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":        "mwcc",
        "available":    False,
        "skip_reason":  reason,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    inbox_arg = sys.argv[1] if len(sys.argv) > 1 else None
    parse_mwcc_ops(inbox_arg)
