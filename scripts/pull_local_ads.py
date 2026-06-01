"""
pull_local_ads.py — Reads Google Ads and Meta Ads CSV exports and produces
a unified state/ads-data.json for the performance agent and dashboards.
"""

import json
import csv
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "ads-data.json"


# ── Google Ads helpers ──────────────────────────────────────────────────────────

def parse_google_ads_file(filepath):
    """Parse a single Google Ads CSV (skip first 2 rows, use 3rd as headers)."""
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        next(reader)
        headers = next(reader)
        for row in reader:
            if len(row) >= max(len(headers), 16) and row[0].strip():
                rows.append(dict(zip(headers, row)))
    return rows


def google_ads_summary(csv_dir):
    """Returns list of week dicts with malaga/ellenbrook/combined metrics + campaign breakdown."""
    weeks = {}
    for loc in ["Ellenbrook", "Malaga"]:
        loc_dir = Path(csv_dir) / f"Google Ads {loc}"
        if not loc_dir.exists():
            continue
        for csv_file in sorted(loc_dir.glob("*.csv")):
            rows = parse_google_ads_file(csv_file)
            stem = csv_file.stem
            week_label = stem
            if week_label not in weeks:
                weeks[week_label] = {
                    "malaga":            {"spend": 0.0, "clicks": 0, "impr": 0, "conv": 0},
                    "ellenbrook":        {"spend": 0.0, "clicks": 0, "impr": 0, "conv": 0},
                    "campaigns_malaga":   [],
                    "campaigns_ellenbrook": [],
                }
            key = loc.lower()

            # Aggregate totals + per-campaign
            camp_spend = defaultdict(float)
            camp_clicks = defaultdict(int)
            camp_impr = defaultdict(int)
            camp_conv = defaultdict(int)

            for row in rows:
                try:
                    status = row.get("Search keyword status", "").strip()
                    if status == "Paused":
                        continue
                    campaign = row.get("Campaign", "Unknown").strip()
                    clicks = int(float(row.get("Clicks", 0) or 0))
                    impr   = int(float(row.get("Impr.", "0").replace(",", "") or 0))
                    cost   = float(row.get("Cost", 0) or 0)
                    conv   = int(float(row.get("Conversions", 0) or 0))
                    weeks[week_label][key]["clicks"] += clicks
                    weeks[week_label][key]["impr"]   += impr
                    weeks[week_label][key]["spend"]  += cost
                    weeks[week_label][key]["conv"]   += conv
                    camp_spend[campaign]  += cost
                    camp_clicks[campaign] += clicks
                    camp_impr[campaign]   += impr
                    camp_conv[campaign]   += conv
                except (ValueError, TypeError):
                    pass

            camp_key = f"campaigns_{key}"
            camp_list = []
            for camp_name in camp_spend:
                c_spend  = round(camp_spend[camp_name], 2)
                c_clicks = camp_clicks[camp_name]
                c_impr   = camp_impr[camp_name]
                c_conv   = camp_conv[camp_name]
                camp_list.append({
                    "name":   camp_name,
                    "spend":  c_spend,
                    "clicks": c_clicks,
                    "impr":   c_impr,
                    "conv":   c_conv,
                    "cpc":    round(c_spend / c_clicks, 2) if c_clicks else 0.0,
                    "cpa":    round(c_spend / c_conv, 2) if c_conv else 0.0,
                    "ctr":    round(c_clicks / c_impr * 100, 2) if c_impr else 0.0,
                })
            camp_list.sort(key=lambda x: x["spend"], reverse=True)
            weeks[week_label][camp_key] = camp_list

    # Sort by week ending date (second date in label, e.g. "10May26" from "04May26-10May26")
    def week_end_date(item):
        wl, _ = item
        end_str = wl.split("-")[1]
        return datetime.strptime(end_str, "%d%b%y")

    result = []
    for wl, data in sorted(weeks.items(), key=week_end_date, reverse=True):
        for loc_key in ["malaga", "ellenbrook"]:
            d = data[loc_key]
            d["cpc"] = round(d["spend"] / d["clicks"], 2) if d["clicks"] else 0.0
            d["cpa"] = round(d["spend"] / d["conv"],   2) if d["conv"]   else 0.0
            d["ctr"] = round(d["clicks"] / d["impr"] * 100, 2) if d["impr"] else 0.0
            d["cpm"] = round(d["spend"] / d["impr"] * 1000, 2) if d["impr"] else 0.0

        combined_spend  = data["malaga"]["spend"]  + data["ellenbrook"]["spend"]
        combined_clicks = data["malaga"]["clicks"] + data["ellenbrook"]["clicks"]
        combined_impr   = data["malaga"]["impr"]   + data["ellenbrook"]["impr"]
        combined_conv   = data["malaga"]["conv"]   + data["ellenbrook"]["conv"]

        # Merge campaigns from both locations for combined view
        all_camps = data["campaigns_malaga"] + data["campaigns_ellenbrook"]
        combined_camps = defaultdict(lambda: {"spend": 0.0, "clicks": 0, "impr": 0, "conv": 0})
        for c in all_camps:
            n = c["name"]
            combined_camps[n]["spend"]  += c["spend"]
            combined_camps[n]["clicks"] += c["clicks"]
            combined_camps[n]["impr"]   += c["impr"]
            combined_camps[n]["conv"]   += c["conv"]
        campaigns_combined = []
        for name, vals in combined_camps.items():
            cs = round(vals["spend"], 2)
            cc = vals["clicks"]
            ci = vals["impr"]
            cv = vals["conv"]
            campaigns_combined.append({
                "name":   name,
                "spend":  cs,
                "clicks": cc,
                "impr":   ci,
                "conv":   cv,
                "cpc":    round(cs / cc, 2) if cc else 0.0,
                "cpa":    round(cs / cv, 2) if cv else 0.0,
                "ctr":    round(cc / ci * 100, 2) if ci else 0.0,
            })
        campaigns_combined.sort(key=lambda x: x["spend"], reverse=True)

        result.append({
            "week_label": wl,
            "malaga":     data["malaga"],
            "ellenbrook": data["ellenbrook"],
            "combined": {
                "spend":  round(combined_spend,  2),
                "clicks": combined_clicks,
                "impr":   combined_impr,
                "conv":   combined_conv,
                "cpc":    round(combined_spend  / combined_clicks, 2) if combined_clicks else 0.0,
                "cpa":    round(combined_spend  / combined_conv,   2) if combined_conv   else 0.0,
                "ctr":    round(combined_clicks / combined_impr * 100, 2) if combined_impr else 0.0,
                "cpm":    round(combined_spend  / combined_impr * 1000, 2) if combined_impr else 0.0,
            },
            "campaigns": campaigns_combined,
        })
    return result


# ── Meta Ads helpers ────────────────────────────────────────────────────────────

def iso_week_label(dt):
    """Returns human-readable week label from a date, e.g. '27Apr26-03May26'."""
    monday = dt - __import__('datetime').timedelta(days=dt.weekday())
    sunday = monday + __import__('datetime').timedelta(days=6)
    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    m_day  = f"{monday.day:02d}"
    s_day  = f"{sunday.day:02d}"
    m_mon  = months[monday.month - 1]
    s_mon  = months[sunday.month - 1]
    yr     = str(monday.year)[-2:]
    return f"{m_day}{m_mon}{yr}-{s_day}{s_mon}{yr}"


def _get_val(row, *names):
    for n in names:
        if n in row:
            v = row[n]
            if isinstance(v, str) and v.strip():
                return v
    return None


def parse_meta_ads(meta_dir):
    """
    Reads Meta_Malaga.csv and Meta_Ellenbrook.csv from meta_dir/Malaga/
    and meta_dir/Ellenbrook/. Aggregates daily rows into ISO weeks.
    Per-campaign (Ad name) breakdown included.
    """
    weeks = {}

    for loc, fname in [("malaga", "Meta_Malaga.csv"), ("ellenbrook", "Meta_Ellenbrook.csv")]:
        csv_path = Path(meta_dir) / loc.capitalize() / fname
        if not csv_path.exists():
            print(f"  [Meta Ads] File not found: {csv_path} — skipping")
            continue

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                date_str = row.get("Reporting starts", "").strip()
                if not date_str:
                    continue
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                iso = dt.isocalendar()[:2]
                if iso not in weeks:
                    weeks[iso] = {
                        "malaga":            {"spend": 0.0, "impr": 0, "reach": 0, "clicks": 0},
                        "ellenbrook":        {"spend": 0.0, "impr": 0, "reach": 0, "clicks": 0},
                        "ads_malaga":        [],
                        "ads_ellenbrook":    [],
                    }

                try:
                    ad_name  = row.get("Ad name", "Unknown").strip()

                    spend_raw  = _get_val(row,
                        "Amount spent (AUD) (May 4, 2026-May 10, 2026)",
                        "Amount spent (AUD) (May 11, 2026-May 17, 2026)",
                        "Amount spent (AUD)")
                    impr_raw   = _get_val(row,
                        "Impressions (May 4, 2026-May 10, 2026)",
                        "Impressions (May 11, 2026-May 17, 2026)",
                        "Impressions")
                    reach_raw  = _get_val(row,
                        "Reach (May 4, 2026-May 10, 2026)",
                        "Reach (May 11, 2026-May 17, 2026)",
                        "Reach")
                    clicks_raw = _get_val(row,
                        "Link clicks (May 4, 2026-May 10, 2026)",
                        "Link clicks (May 11, 2026-May 17, 2026)",
                        "Link clicks")

                    spend  = float(spend_raw  or 0)
                    impr   = int(float(impr_raw  or 0))
                    reach  = int(float(reach_raw  or 0))
                    clicks = int(float(clicks_raw or 0))
                    weeks[iso][loc]["spend"]  += spend
                    weeks[iso][loc]["impr"]   += impr
                    weeks[iso][loc]["reach"]  += reach
                    weeks[iso][loc]["clicks"] += clicks

                    # Per-ad aggregation
                    ads_key = f"ads_{loc}"
                    ads_list = weeks[iso].get(ads_key, [])
                    # Find existing ad entry by name
                    ad_entry = next((a for a in ads_list if a["name"] == ad_name), None)
                    if ad_entry is None:
                        ad_entry = {"name": ad_name, "spend": 0.0, "impr": 0, "reach": 0, "clicks": 0}
                        ads_list.append(ad_entry)
                    ad_entry["spend"]  += spend
                    ad_entry["impr"]   += impr
                    ad_entry["reach"] += reach
                    ad_entry["clicks"] += clicks
                    weeks[iso][ads_key] = ads_list

                except (ValueError, TypeError):
                    pass

    # Build sorted result
    def meta_week_end_date(iso_key):
        return datetime.fromisocalendar(iso_key[0], iso_key[1], 7)

    result = []
    for iso_key in sorted(weeks.keys(), key=meta_week_end_date, reverse=True):
        malaga_d     = weeks[iso_key]["malaga"]
        ellenbrook_d = weeks[iso_key]["ellenbrook"]

        for d in [malaga_d, ellenbrook_d]:
            d["ctr"] = round(d["clicks"] / d["impr"] * 100, 2) if d["impr"] else 0.0
            d["cpm"] = round(d["spend"]  / d["impr"] * 1000, 2) if d["impr"] else 0.0
            d["cpc"] = round(d["spend"]  / d["clicks"], 2) if d["clicks"] else 0.0

        # Per-ad summaries with computed rates
        def compute_ads(ads_list):
            result_ads = []
            for a in ads_list:
                a_spend = round(a["spend"], 2)
                a_clicks = a["clicks"]
                a_impr = a["impr"]
                result_ads.append({
                    "name":   a["name"],
                    "spend":  a_spend,
                    "impr":   a_impr,
                    "reach":  a["reach"],
                    "clicks": a_clicks,
                    "ctr":    round(a_clicks / a_impr * 100, 2) if a_impr else 0.0,
                    "cpm":    round(a_spend / a_impr * 1000, 2) if a_impr else 0.0,
                    "cpc":    round(a_spend / a_clicks, 2) if a_clicks else 0.0,
                })
            result_ads.sort(key=lambda x: x["spend"], reverse=True)
            return result_ads

        ads_malaga     = compute_ads(weeks[iso_key].get("ads_malaga", []))
        ads_ellenbrook = compute_ads(weeks[iso_key].get("ads_ellenbrook", []))

        # Merge both locations for combined view
        combined_ads = defaultdict(lambda: {"spend": 0.0, "impr": 0, "reach": 0, "clicks": 0})
        for ads_list in [ads_malaga, ads_ellenbrook]:
            for a in ads_list:
                combined_ads[a["name"]]["spend"]  += a["spend"]
                combined_ads[a["name"]]["impr"]   += a["impr"]
                combined_ads[a["name"]]["reach"]  += a["reach"]
                combined_ads[a["name"]]["clicks"] += a["clicks"]
        ads_combined = compute_ads([
            {"name": n, **v} for n, v in combined_ads.items()
        ])

        dt_monday = datetime.fromisocalendar(iso_key[0], iso_key[1], 1)
        week_label = iso_week_label(dt_monday)

        combined_spend  = malaga_d["spend"]  + ellenbrook_d["spend"]
        combined_impr   = malaga_d["impr"]   + ellenbrook_d["impr"]
        combined_reach  = malaga_d["reach"]  + ellenbrook_d["reach"]
        combined_clicks = malaga_d["clicks"] + ellenbrook_d["clicks"]

        result.append({
            "week_label":   week_label,
            "malaga":       malaga_d,
            "ellenbrook":   ellenbrook_d,
            "combined": {
                "spend":  round(combined_spend,  2),
                "impr":   combined_impr,
                "reach":  combined_reach,
                "clicks": combined_clicks,
                "ctr":    round(combined_clicks / combined_impr * 100, 2) if combined_impr else 0.0,
                "cpm":    round(combined_spend  / combined_impr * 1000, 2) if combined_impr else 0.0,
                "cpc":    round(combined_spend  / combined_clicks, 2) if combined_clicks else 0.0,
            },
            "ads": ads_combined,
        })

    return result


# ── Main ────────────────────────────────────────────────────────────────────────

def pull_local_ads():
    google_csv_dir = BASE_DIR / "googleads"
    meta_dir       = BASE_DIR / "metaads"

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source":       "local CSV exports",
        "google_ads": google_ads_summary(google_csv_dir) if google_csv_dir.exists() else [],
        "meta_ads":  parse_meta_ads(meta_dir),
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Combined ads data saved to {OUTPUT_FILE}")
    return output


if __name__ == "__main__":
    pull_local_ads()