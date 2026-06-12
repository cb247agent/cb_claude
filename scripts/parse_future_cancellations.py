"""
parse_future_cancellations.py — Convert PGM future-cancellation CSV export
into a styled HTML page Reception can work from.

WHY THIS EXISTS
    The Membership page's #1 prioritised action is "Run save-call programme
    for the future-cancellation pipeline (~279 people)." Without the actual
    list of people, the action isn't executable. Tia exports the list from
    PGM (Members > Reports > Future Cancellations, next 30 days), drops the
    CSV into cb247-inbox/, and this script renders a clickable HTML page
    every team member can call from.

INPUT
    cb247-inbox/future-cancellations-YYYY-MM-DD.csv
    Expected columns (extra columns ignored, missing ones blank):
      name · phone · email · club · cancel_effective_date · join_date ·
      cancel_reason · member_id · addons_active · notes

OUTPUT
    docs/lists/future-cancellations-YYYY-MM-DD.html
      — styled table, sorted by cancel_effective_date ascending so the
        most urgent calls surface first
    state/future-cancellations-manifest.json
      — points the dashboard at the latest list (path + count + date)

USAGE
    python scripts/parse_future_cancellations.py            # newest CSV
    python scripts/parse_future_cancellations.py --file ... # explicit
    python scripts/parse_future_cancellations.py --date 2026-06-12

The Membership prioritised list action description links to
docs/lists/future-cancellations-{today}.html. If the file exists, the View
Details popup shows "View the list (N people)" — otherwise it shows the
"Drop the CSV at cb247-inbox/..." instruction.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date as _date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INBOX_DIR = BASE_DIR / "cb247-inbox"
OUTPUT_DIR = BASE_DIR / "docs" / "lists"
STATE_FILE = BASE_DIR / "state" / "future-cancellations-manifest.json"

# CB247 palette (mirrors the rest of the dashboard)
TEAL = "#3FA69A"
TEAL_DEEP = "#2d7d72"
TEAL_MIST = "#f0fdf4"
DARK = "#1a1a2e"


def _escape(s) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _normalize_phone(s: str) -> str:
    """Light cleanup so 'tel:' links work."""
    if not s:
        return ""
    digits = re.sub(r"[^\d+]", "", s)
    return digits


def _parse_date(s: str) -> _date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _days_until(d: _date | None) -> int | None:
    if d is None:
        return None
    return (d - _date.today()).days


def _urgency_tone(days_until: int | None) -> tuple[str, str, str]:
    """Background, foreground, label for the urgency chip."""
    if days_until is None:
        return ("#f3f4f6", "#6b7280", "unknown")
    if days_until < 0:
        return ("#fee2e2", "#991b1b", f"{abs(days_until)}d overdue")
    if days_until <= 3:
        return ("#fee2e2", "#991b1b", f"{days_until}d")
    if days_until <= 7:
        return ("#fef3c7", "#92400e", f"{days_until}d")
    return ("#dcfce7", "#166534", f"{days_until}d")


def _suggested_approach(reason: str) -> str:
    """Map cancel reason → first-line save-call approach hint.
    Reception briefs Angela on what's worked; this seeds the first call."""
    r = (reason or "").strip().lower()
    if "not using" in r:
        return "Habit-build: offer free 1:1 program review + class re-introduction. Highlight 24/7 access."
    if "relocating" in r:
        return "Confirm move date + suburb. If still in Perth, transfer to nearest CB247. If leaving Perth, polite close."
    if "unsure" in r:
        return "Discovery: what would tip the decision? Offer freeze (FIFO-friendly, no contract) before downgrade."
    if "endofcontract" in r or "end of contract" in r:
        return "Renewal: highlight Recovery add-on uptake (+19 members signed up this month) and Kids Hub."
    if "switched" in r or "another gym" in r:
        return "Differentiator: sauna + ice bath, traditional bath, 24/7. Match on price if competitor is genuinely cheaper."
    if "turned" in r:
        return "URGENT — escalate to Angela. Service complaint requires personal outreach within 24h."
    if "debt" in r or "payment" in r:
        return "Reception: arrears arrangement options. Do NOT offer freeze (won't fix payment issue)."
    return "Open with: 'We noticed your membership is set to end on [DATE] — is there anything we can do?'"


def _find_latest_csv() -> Path | None:
    if not INBOX_DIR.exists():
        return None
    files = sorted(INBOX_DIR.glob("future-cancellations-*.csv"))
    # Skip the template
    files = [f for f in files if "template" not in f.name.lower()]
    return files[-1] if files else None


def _load_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k.strip(): (v or "").strip() for k, v in r.items() if k})
    return rows


def _render_html(rows: list[dict], source_csv: Path, run_date: str) -> str:
    # Sort by urgency (cancel_effective_date ascending, then unknown last)
    def sort_key(r):
        d = _parse_date(r.get("cancel_effective_date", ""))
        return (d is None, d or _date(9999, 1, 1))
    rows = sorted(rows, key=sort_key)

    # Group by club for per-section totals
    clubs: dict[str, list] = {}
    for r in rows:
        clubs.setdefault(r.get("club") or "—", []).append(r)

    table_rows = []
    for i, r in enumerate(rows, start=1):
        d = _parse_date(r.get("cancel_effective_date", ""))
        days = _days_until(d)
        bg, fg, label = _urgency_tone(days)
        urgency_chip = (
            f"<span style='background:{bg};color:{fg};font-size:10.5px;"
            f"font-weight:700;padding:3px 10px;border-radius:99px;"
            f"letter-spacing:.02em;white-space:nowrap'>{_escape(label)}</span>"
        )
        phone_raw = r.get("phone") or ""
        phone_tel = _normalize_phone(phone_raw)
        phone_link = (
            f"<a href='tel:{phone_tel}' style='color:{TEAL_DEEP};"
            f"font-weight:600;text-decoration:none;font-variant-numeric:tabular-nums'>"
            f"{_escape(phone_raw)}</a>"
            if phone_tel else "<span style='color:#9ca3af'>—</span>"
        )
        reason = r.get("cancel_reason") or "—"
        approach = _suggested_approach(reason)
        addons = r.get("addons_active") or ""
        notes = r.get("notes") or ""
        table_rows.append(f"""
        <tr id='row-{i}' style='border-bottom:1px solid #f0f2f5'>
          <td style='padding:10px 6px;color:var(--muted);font-size:11px;text-align:center'>{i}</td>
          <td style='padding:10px 8px'>
            <div style='font-size:13px;font-weight:700;color:{DARK}'>{_escape(r.get('name','—'))}</div>
            <div style='font-size:10.5px;color:#6b7280;margin-top:2px'>
              {_escape(r.get('member_id',''))} {f"· {_escape(r.get('club','—'))}" if r.get('club') else ''}
            </div>
            {f"<div style='font-size:10.5px;color:#92400e;margin-top:3px'><b>Add-ons:</b> {_escape(addons)}</div>" if addons else ""}
          </td>
          <td style='padding:10px 8px;font-size:12px;white-space:nowrap'>{phone_link}</td>
          <td style='padding:10px 8px;font-size:11.5px;white-space:nowrap'>
            <div>{_escape(r.get('cancel_effective_date','—'))}</div>
            <div style='margin-top:4px'>{urgency_chip}</div>
          </td>
          <td style='padding:10px 8px;font-size:12px;color:#374151'>{_escape(reason)}</td>
          <td style='padding:10px 8px;font-size:11.5px;color:#374151;line-height:1.5;max-width:280px'>
            {_escape(approach)}
            {f"<div style='margin-top:6px;color:#6b7280;font-style:italic;font-size:10.5px'>PGM note: {_escape(notes)}</div>" if notes else ""}
          </td>
          <td style='padding:10px 8px;text-align:center'>
            <select onchange='markOutcome(this,{i})' style='font-size:11px;padding:4px 6px;border:1px solid #e5e7eb;border-radius:4px;background:#fff;font-family:inherit'>
              <option value=''>—</option>
              <option value='saved'>Saved</option>
              <option value='freeze'>Froze</option>
              <option value='downgrade'>Downgraded</option>
              <option value='lost'>Lost</option>
              <option value='noanswer'>No answer</option>
              <option value='callback'>Callback</option>
            </select>
          </td>
        </tr>""")

    club_summary = " · ".join(
        f"<b>{_escape(c)}</b> {len(v)}" for c, v in sorted(clubs.items(), key=lambda kv: -len(kv[1]))
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width,initial-scale=1.0'>
<title>CB247 Save-Call List · {run_date}</title>
<style>
  :root {{
    --teal: {TEAL};
    --teal-deep: {TEAL_DEEP};
    --teal-mist: {TEAL_MIST};
    --dark: {DARK};
    --muted: #6b7280;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f2f5;color:var(--dark);line-height:1.55}}
  .page{{max-width:1200px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 0 32px rgba(0,0,0,.05)}}
  .hero{{background:linear-gradient(135deg,var(--dark) 0%,#2a2a4e 100%);color:#fff;padding:28px 36px}}
  .hero-tag{{display:inline-block;font-size:11px;color:var(--teal);font-weight:700;letter-spacing:2px;text-transform:uppercase;background:rgba(63,166,154,.15);padding:5px 12px;border-radius:99px;margin-bottom:8px}}
  .hero h1{{font-size:28px;font-weight:800;margin-bottom:8px}}
  .hero-sub{{font-size:13px;color:rgba(255,255,255,.7);margin-bottom:18px}}
  .hero-stats{{display:flex;gap:24px;flex-wrap:wrap}}
  .hero-stat{{display:flex;flex-direction:column}}
  .hero-stat .label{{font-size:10px;color:rgba(255,255,255,.6);text-transform:uppercase;letter-spacing:1px;font-weight:600;margin-bottom:3px}}
  .hero-stat .value{{font-size:22px;font-weight:700;color:#fff;font-variant-numeric:tabular-nums}}
  .controls{{padding:18px 36px;border-bottom:1px solid #f0f2f5;background:#fafbfc;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
  .controls input{{padding:8px 12px;border:1px solid #e5e7eb;border-radius:6px;font-size:13px;font-family:inherit;min-width:240px}}
  .controls input:focus{{outline:none;border-color:var(--teal)}}
  .controls select{{padding:8px 12px;border:1px solid #e5e7eb;border-radius:6px;font-size:13px;font-family:inherit}}
  table{{width:100%;border-collapse:collapse;font-size:12.5px}}
  thead tr{{background:var(--teal-mist);border-bottom:2px solid #d1fae5}}
  thead th{{padding:11px 8px;text-align:left;font-size:10.5px;letter-spacing:.06em;color:var(--teal-deep);text-transform:uppercase;font-weight:700}}
  tbody tr:hover{{background:#fafbfc}}
  tbody tr.outcome-saved{{background:#dcfce7 !important}}
  tbody tr.outcome-lost{{background:#fef2f2 !important;opacity:.7}}
  tbody tr.outcome-freeze, tbody tr.outcome-downgrade{{background:#fef9c3 !important}}
  .footer{{padding:20px 36px;background:#fafbfc;border-top:1px solid #f0f2f5;font-size:11px;color:var(--muted)}}
  .footer code{{background:#e5e7eb;padding:2px 6px;border-radius:3px}}
  @media print{{
    body{{background:#fff}}
    .controls{{display:none}}
    .hero{{background:var(--dark) !important;-webkit-print-color-adjust:exact}}
    table{{font-size:10.5px}}
  }}
</style>
</head>
<body>
<div class='page'>
  <header class='hero'>
    <div class='hero-tag'>CB247 Save-Call List</div>
    <h1>Future-Cancellation Pipeline — {len(rows)} people</h1>
    <div class='hero-sub'>Generated {run_date} from {_escape(source_csv.name)} · sorted by urgency (soonest cancel first)</div>
    <div class='hero-stats'>
      <div class='hero-stat'><div class='label'>Total to call</div><div class='value'>{len(rows)}</div></div>
      <div class='hero-stat'><div class='label'>Per club</div><div class='value' style='font-size:14px;padding-top:6px'>{club_summary}</div></div>
      <div class='hero-stat'><div class='label'>Save-rate target</div><div class='value'>30%</div></div>
      <div class='hero-stat'><div class='label'>Expected saves</div><div class='value'>~{round(len(rows) * 0.3)}</div></div>
    </div>
  </header>

  <div class='controls'>
    <input id='search' type='text' placeholder='Search name, phone, member ID, reason…' oninput='filterTable()'>
    <select id='clubFilter' onchange='filterTable()'>
      <option value=''>All clubs</option>
      {''.join(f"<option value='{_escape(c)}'>{_escape(c)} ({len(v)})</option>" for c, v in sorted(clubs.items(), key=lambda kv: -len(kv[1])))}
    </select>
    <button onclick='window.print()' style='padding:8px 14px;background:var(--teal);color:#fff;border:none;border-radius:6px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit'>Print</button>
    <div style='margin-left:auto;font-size:11px;color:var(--muted)'>Outcomes save to localStorage so you can resume later</div>
  </div>

  <table>
    <thead>
      <tr>
        <th style='width:36px;text-align:center'>#</th>
        <th>Member</th>
        <th style='width:130px'>Phone</th>
        <th style='width:120px'>Cancel</th>
        <th style='width:160px'>Reason</th>
        <th>Suggested Approach</th>
        <th style='width:110px;text-align:center'>Outcome</th>
      </tr>
    </thead>
    <tbody id='rows'>
      {''.join(table_rows)}
    </tbody>
  </table>

  <div class='footer'>
    Source CSV: <code>{_escape(str(source_csv.relative_to(BASE_DIR)))}</code> · Generated by <code>scripts/parse_future_cancellations.py</code> ·
    Drop a fresh CSV at <code>cb247-inbox/future-cancellations-YYYY-MM-DD.csv</code> any time and re-run to refresh.
  </div>
</div>

<script>
  const STORAGE_KEY = 'cb247-save-call-outcomes-{run_date}';
  const outcomes = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');

  // Restore prior outcomes
  Object.entries(outcomes).forEach(([idx, val]) => {{
    const row = document.getElementById('row-' + idx);
    if (!row) return;
    const sel = row.querySelector('select');
    if (sel) sel.value = val;
    if (val) row.classList.add('outcome-' + val);
  }});

  function markOutcome(sel, idx) {{
    const row = document.getElementById('row-' + idx);
    if (!row) return;
    // Strip old outcome classes
    Array.from(row.classList).forEach(c => {{ if (c.startsWith('outcome-')) row.classList.remove(c); }});
    if (sel.value) row.classList.add('outcome-' + sel.value);
    outcomes[idx] = sel.value;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(outcomes));
  }}

  function filterTable() {{
    const q = (document.getElementById('search').value || '').toLowerCase();
    const club = document.getElementById('clubFilter').value;
    document.querySelectorAll('#rows tr').forEach(tr => {{
      const text = tr.innerText.toLowerCase();
      const matchesQ = !q || text.includes(q);
      const matchesClub = !club || text.includes(club.toLowerCase());
      tr.style.display = (matchesQ && matchesClub) ? '' : 'none';
    }});
  }}
</script>
</body>
</html>"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="Explicit CSV path. Default: newest in cb247-inbox/")
    p.add_argument("--date", default=_date.today().isoformat(),
                   help="Date label for the output HTML. Default: today.")
    args = p.parse_args()

    if args.file:
        csv_path = Path(args.file)
    else:
        csv_path = _find_latest_csv()

    if csv_path is None:
        print("[future-cancels] No future-cancellations-*.csv found in cb247-inbox/")
        print("[future-cancels] Expected: cb247-inbox/future-cancellations-YYYY-MM-DD.csv")
        print("[future-cancels] Template: cb247-inbox/future-cancellations-template.csv")
        return 0   # not a failure — just nothing to do this run

    if not csv_path.exists():
        print(f"[future-cancels] {csv_path} does not exist")
        return 1

    rows = _load_csv(csv_path)
    if not rows:
        print(f"[future-cancels] {csv_path.name} has 0 rows")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = _render_html(rows, csv_path, args.date)
    out_path = OUTPUT_DIR / f"future-cancellations-{args.date}.html"
    out_path.write_text(html, encoding="utf-8")

    # Manifest so the dashboard can point at the latest list without
    # guessing dates.
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "source_csv": str(csv_path.relative_to(BASE_DIR)),
        "list_path": str(out_path.relative_to(BASE_DIR / "docs")),
        "date": args.date,
        "count": len(rows),
        "per_club": {},
    }
    for r in rows:
        c = r.get("club") or "—"
        manifest["per_club"][c] = manifest["per_club"].get(c, 0) + 1
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(manifest, indent=2))

    print(f"[future-cancels] Parsed {len(rows)} rows from {csv_path.name}")
    print(f"[future-cancels] Wrote {out_path.relative_to(BASE_DIR)}")
    print(f"[future-cancels] Manifest: {STATE_FILE.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
