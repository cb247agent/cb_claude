#!/usr/bin/env python3
"""
Google Ads CSV Importer
Reads Malaga + Ellenbrook Google Ads CSVs → outputs aggregated JSON to state/google-ads-data.json
"""
import csv
import json
import sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
MALAGA_CSV = BASE / "googleads" / "google_ads_malaga.csv"
ELLENBROOK_CSV = BASE / "googleads" / "google_ads_ellenbrook.csv"
OUTPUT = BASE / "state" / "google-ads-data.json"

def parse_number(val):
    """Parse CSV number string to float, handle empty/0 values."""
    if not val or val in ('0', '0.00', '-'): return 0.0
    val = val.replace('%', '').replace(',', '').strip()
    try:
        return float(val)
    except ValueError:
        return 0.0

def parse_campaigns(csv_path, account_name):
    """Parse a Google Ads CSV and return account-level + campaign-level aggregates."""
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        raw_lines = [l.rstrip('\n') for l in f if l.strip()]
        # Skip first 2 rows (title label + date range), then DictReader finds header at row 2
        data_lines = raw_lines[2:]
        reader = csv.DictReader(data_lines)
        for row in reader:
            clicks = parse_number(row.get('Clicks', '0'))
            cost = parse_number(row.get('Cost', '0'))
            conv = parse_number(row.get('Conversions', '0'))
            impr = parse_number(row.get('Impr.', '0'))
            ctr = parse_number(row.get('CTR', '0'))
            avg_cpc = parse_number(row.get('Avg. CPC', '0'))
            status = row.get('Search keyword status', 'Unknown').strip()

            if clicks == 0 and cost == 0:
                continue  # Skip zero-activity rows

            rows.append({
                'keyword': row.get('Search keyword', '').strip(),
                'match_type': row.get('Search keyword match type', '').strip(),
                'campaign': row.get('Campaign', '').strip(),
                'ad_group': row.get('Ad group', '').strip(),
                'status': status,
                'clicks': clicks,
                'impressions': impr,
                'ctr': ctr,
                'avg_cpc': avg_cpc,
                'cost': cost,
                'conversions': conv,
                'view_through_conv': parse_number(row.get('View-through conv.', '0')),
            })

    # Aggregate by campaign
    campaigns = {}
    for r in rows:
        c = r['campaign']
        if c not in campaigns:
            campaigns[c] = {'name': c, 'clicks': 0, 'cost': 0, 'conversions': 0, 'impressions': 0, 'keywords': []}
        campaigns[c]['clicks'] += r['clicks']
        campaigns[c]['cost'] += r['cost']
        campaigns[c]['conversions'] += r['conversions']
        campaigns[c]['impressions'] += r['impressions']
        campaigns[c]['keywords'].append(r)

    # Account totals
    total_clicks = sum(r['clicks'] for r in rows)
    total_cost = sum(r['cost'] for r in rows)
    total_conv = sum(r['conversions'] for r in rows)
    total_impr = sum(r['impressions'] for r in rows)

    return {
        'account': account_name,
        'file': str(csv_path.name),
        'date_range': {'start': '2026-04-27', 'end': '2026-05-08'},
        'total_clicks': total_clicks,
        'total_cost': total_cost,
        'total_conversions': total_conv,
        'total_impressions': total_impr,
        'avg_cpc': round(total_cost / total_clicks, 2) if total_clicks > 0 else 0,
        'cpl': round(total_cost / total_conv, 2) if total_conv > 0 else 0,
        'ctr': round(total_clicks / total_impr * 100, 2) if total_impr > 0 else 0,
        'roas': round(total_conv * 11.95 / total_cost, 2) if total_cost > 0 else 0,  # $11.95/wk membership
        'campaigns': list(campaigns.values()),
        'all_keywords': rows,
    }

def main():
    malaga = parse_campaigns(MALAGA_CSV, 'Malaga')
    ellenbrook = parse_campaigns(ELLENBROOK_CSV, 'Ellenbrook')

    combined = {
        'generated_at': datetime.now().isoformat(),
        'available': True,
        'skip_reason': None,
        'date_range': {'start': '2026-04-27', 'end': '2026-05-08'},
        'accounts': [malaga, ellenbrook],
        'combined': {
            'total_clicks': malaga['total_clicks'] + ellenbrook['total_clicks'],
            'total_cost': malaga['total_cost'] + ellenbrook['total_cost'],
            'total_conversions': malaga['total_conversions'] + ellenbrook['total_conversions'],
            'total_impressions': malaga['total_impressions'] + ellenbrook['total_impressions'],
        }
    }

    combined['combined']['avg_cpc'] = round(combined['combined']['total_cost'] / combined['combined']['total_clicks'], 2) if combined['combined']['total_clicks'] > 0 else 0
    combined['combined']['cpl'] = round(combined['combined']['total_cost'] / combined['combined']['total_conversions'], 2) if combined['combined']['total_conversions'] > 0 else 0
    combined['combined']['roas'] = round(combined['combined']['total_conversions'] * 11.95 / combined['combined']['total_cost'], 2) if combined['combined']['total_cost'] > 0 else 0

    OUTPUT.write_text(json.dumps(combined, indent=2))
    print(f"✅ Written to {OUTPUT}")
    print(f"   Malaga:    clicks={malaga['total_clicks']}, cost=${malaga['total_cost']:.2f}, conv={malaga['total_conversions']}, ROAS={malaga['roas']}x")
    print(f"   Ellenbrook: clicks={ellenbrook['total_clicks']}, cost=${ellenbrook['total_cost']:.2f}, conv={ellenbrook['total_conversions']}, ROAS={ellenbrook['roas']}x")
    print(f"   Combined:  clicks={combined['combined']['total_clicks']}, cost=${combined['combined']['total_cost']:.2f}, conv={combined['combined']['total_conversions']}, ROAS={combined['combined']['roas']}x")

if __name__ == '__main__':
    main()