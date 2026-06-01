"""
pull_ads_data.py — Parse Meta Ads CSV + Google Ads CSVs → structured JSON for agents.
Saves to state/meta-ads-data.json and state/google-ads-data.json.

Data sources:
- metaads/metaads.csv — all Meta Ads data (Malaga + Ellenbrook)
- googleads/Google Ads Malaga/*.csv — Google Ads Malaga weekly exports
- googleads/Google Ads Ellenbrook/*.csv — Google Ads Ellenbrook weekly exports
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
META_DIR = BASE_DIR / "metaads"
GADS_DIR = BASE_DIR / "googleads"


def parse_meta_ads():
    """Parse metaads.csv into structured JSON."""
    campaigns = defaultdict(lambda: {
        "account": "", "spend": 0, "impressions": 0, "clicks": 0,
        "reach": 0, "ads": {}, "age_genders": defaultdict(int), "weeks": set()
    })

    with open(META_DIR / "metaads.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("Campaign name"):
                continue
            camp = row["Campaign name"]
            c = campaigns[camp]
            c["account"] = row.get("Account name", "")
            try:
                c["spend"] += float(row.get("Amount spent (AUD)", 0) or 0)
                c["impressions"] += int(row.get("Impressions", 0) or 0)
                c["clicks"] += int(row.get("Link clicks", 0) or 0)
                c["reach"] += int(row.get("Reach", 0) or 0)
                week = row.get("Week", "")
                c["weeks"].add(week)
                age = row.get("Age", "?")
                gender = row.get("Gender", "?")
                c["age_genders"][f"{age} {gender}"] += int(row.get("Impressions", 0) or 0)
                ad_name = row.get("Ad name", "")
                if ad_name not in c["ads"]:
                    c["ads"][ad_name] = {"impressions": 0, "clicks": 0, "spend": 0}
                c["ads"][ad_name]["impressions"] += int(row.get("Impressions", 0) or 0)
                c["ads"][ad_name]["clicks"] += int(row.get("Link clicks", 0) or 0)
                c["ads"][ad_name]["spend"] += float(row.get("Amount spent (AUD)", 0) or 0)
            except (ValueError, TypeError):
                pass

    result = {"date_pulled": datetime.now().isoformat(), "accounts": {}}
    for camp, c in campaigns.items():
        c["cpc"] = round(c["spend"] / c["clicks"], 2) if c["clicks"] > 0 else 0
        c["ctr"] = round(c["clicks"] / c["impressions"] * 100, 2) if c["impressions"] > 0 else 0
        c["cpm"] = round(c["spend"] / c["impressions"] * 1000, 2) if c["impressions"] > 0 else 0
        c["top_ads"] = sorted(c["ads"].items(), key=lambda x: -x[1]["impressions"])[:3]
        c["top_demographics"] = sorted(c["age_genders"].items(), key=lambda x: -x[1])[:3]
        c["weeks"] = sorted(list(c["weeks"]))
        del c["ads"]
        del c["age_genders"]
        result["accounts"][camp] = dict(c)

    return result


def parse_google_ads_location(folder_path):
    """Parse all weekly CSVs in a Google Ads folder."""
    all_data = []
    for csv_file in sorted(folder_path.glob("*.csv")):
        with open(csv_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Split by "Search keyword\n" header which separates tables
        sections = content.split('Search keyword\n')
        if len(sections) < 2:
            continue

        # Parse each data section
        for section in sections[1:]:
            lines = [l for l in section.strip().split('\n') if l.strip()]
            if len(lines) < 3:
                continue

            # Find header to get column indices
            header = None
            data_start = 0
            for i, line in enumerate(lines):
                parts = line.split(',')
                if len(parts) > 10 and parts[0] == 'Search keyword':
                    header = line
                    data_start = i + 1
                    break

            if header is None:
                # No header row, try parsing directly
                data_start = 0

            # Parse data lines
            for line in lines[data_start:]:
                if not line.strip() or ',' not in line:
                    continue
                parts = line.split(',')
                if len(parts) < 13:
                    continue
                try:
                    keyword = parts[0].strip()
                    if not keyword:
                        continue
                    status = parts[1].strip() if len(parts) > 1 else ""
                    match_type = parts[3].strip() if len(parts) > 3 else ""
                    campaign = parts[4].strip() if len(parts) > 4 else ""
                    ad_group = parts[5].strip() if len(parts) > 5 else ""

                    clicks = int(parts[8]) if parts[8].strip().isdigit() else 0
                    impr = int(parts[9]) if parts[9].strip().isdigit() else 0
                    ctr_str = parts[10].replace('%','').strip() if len(parts) > 10 else "0"
                    ctr = float(ctr_str) if ctr_str.replace('.','').isdigit() else 0
                    avg_cpc = float(parts[11]) if parts[11].strip() else 0
                    cost = float(parts[12]) if parts[12].strip() else 0
                    conv_str = parts[16].strip() if len(parts) > 16 else "0"
                    conversions = float(conv_str) if conv_str.replace('.','').isdigit() else 0

                    all_data.append({
                        "keyword": keyword,
                        "status": status,
                        "match_type": match_type,
                        "campaign": campaign,
                        "ad_group": ad_group,
                        "clicks": clicks,
                        "impressions": impr,
                        "ctr": ctr,
                        "avg_cpc": avg_cpc,
                        "cost": cost,
                        "conversions": conversions,
                        "file": csv_file.name
                    })
                except (ValueError, IndexError):
                    continue

    return all_data


def aggregate_google_ads(data):
    """Aggregate Google Ads data by keyword."""
    by_kw = defaultdict(lambda: {"clicks": 0, "impressions": 0, "cost": 0, "conversions": 0, "campaigns": set(), "ad_groups": set()})
    for row in data:
        k = row["keyword"]
        by_kw[k]["clicks"] += row["clicks"]
        by_kw[k]["impressions"] += row["impressions"]
        by_kw[k]["cost"] += row["cost"]
        by_kw[k]["conversions"] += row["conversions"]
        by_kw[k]["campaigns"].add(row["campaign"])
        by_kw[k]["ad_groups"].add(row["ad_group"])

    result = {}
    for kw, d in by_kw.items():
        d["avg_cpc"] = round(d["cost"] / d["clicks"], 2) if d["clicks"] > 0 else 0
        d["ctr"] = round(d["clicks"] / d["impressions"] * 100, 1) if d["impressions"] > 0 else 0
        d["campaigns"] = list(d["campaigns"])
        d["ad_groups"] = list(d["ad_groups"])
        result[kw] = d
    return result


def parse_all_google_ads():
    """Parse all Google Ads data for Malaga + Ellenbrook."""
    malaga_data = parse_google_ads_location(GADS_DIR / "Google Ads Malaga")
    ellenbrook_data = parse_google_ads_location(GADS_DIR / "Google Ads Ellenbrook")

    return {
        "date_pulled": datetime.now().isoformat(),
        "malaga": {
            "keywords": aggregate_google_ads(malaga_data),
            "total_clicks": sum(r["clicks"] for r in malaga_data),
            "total_impressions": sum(r["impressions"] for r in malaga_data),
            "total_cost": sum(r["cost"] for r in malaga_data),
            "total_conversions": sum(r["conversions"] for r in malaga_data),
            "campaigns": list(set(r["campaign"] for r in malaga_data)),
        },
        "ellenbrook": {
            "keywords": aggregate_google_ads(ellenbrook_data),
            "total_clicks": sum(r["clicks"] for r in ellenbrook_data),
            "total_impressions": sum(r["impressions"] for r in ellenbrook_data),
            "total_cost": sum(r["cost"] for r in ellenbrook_data),
            "total_conversions": sum(r["conversions"] for r in ellenbrook_data),
            "campaigns": list(set(r["campaign"] for r in ellenbrook_data)),
        }
    }


def main():
    print("Parsing Meta Ads data...")
    meta_result = parse_meta_ads()
    out_meta = STATE_DIR / "meta-ads-data.json"
    out_meta.write_text(json.dumps(meta_result, indent=2))
    print(f"Meta Ads: {len(meta_result['accounts'])} campaigns saved to {out_meta}")

    print("Parsing Google Ads data...")
    gads_result = parse_all_google_ads()
    out_gads = STATE_DIR / "google-ads-data.json"
    out_gads.write_text(json.dumps(gads_result, indent=2))
    print(f"Google Ads: {len(gads_result['malaga']['campaigns'])} Malaga campaigns, {len(gads_result['ellenbrook']['campaigns'])} Ellenbrook campaigns saved to {out_gads}")

    return meta_result, gads_result


if __name__ == "__main__":
    main()