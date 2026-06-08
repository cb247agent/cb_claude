"""
parse_mwcc_ahrefs_csvs.py — Parse manual Ahrefs CSV exports for MWCC.

Reads CSVs Tia drops into mwcc-inbox/ahrefs/ and writes state/mwcc-ahrefs.json
in the shape that renderMwccSeo() in docs/index.html expects.

This is the MANUAL fallback for when AHREFS_API_KEY is unavailable
(rotating token issue, June 2026). Replaces pull_mwcc_ahrefs.py for the
weekly cron until token is back.

EXPECTED CSV FILES in mwcc-inbox/ahrefs/:
  *backlinks-subdomains*.csv         — Full backlinks list (UTF-16, tab-delim)
  *_perf_*_14-29-25.csv              — Backlinks daily (referring domains, DR, URL Rating)
  *_perf_*_14-29-34.csv              — Organic daily (traffic, value, impressions, position buckets)
  *-perf-subdomains_month6_daily*.csv — Paid traffic daily
  *_overview-competitors*.csv        — Competitor matrix
  *_common-keywords_*.csv            — Shared keyword matrix
  *_perf_*_14-28-53.csv              — Big perf file with brand/intent splits

USAGE: python scripts/parse_mwcc_ahrefs_csvs.py
"""

import csv
import json
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INBOX_DIR = BASE_DIR / "mwcc-inbox" / "ahrefs"
STATE_DIR = BASE_DIR / "state"
OUT_FILE = STATE_DIR / "mwcc-ahrefs.json"

SITE = "myworldcc.com.au"


# ─── helpers ─────────────────────────────────────────────────────────────
def _num(v):
    """Strip whitespace + commas, return int/float or None."""
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("$", "")
    if s in ("", "-", "–"):
        return None
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return None


def _find(pattern):
    """Find ONE CSV in INBOX_DIR matching a glob, newest first."""
    if not INBOX_DIR.exists():
        return None
    matches = sorted(INBOX_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _read_csv(path, encoding="utf-8", delimiter=","):
    if not path or not path.exists():
        return []
    with open(path, encoding=encoding) as f:
        return list(csv.reader(f, delimiter=delimiter))


# ─── parsers per CSV ─────────────────────────────────────────────────────
def parse_organic_daily():
    """File: *_perf_*_14-29-34.csv — daily organic + SERP features.
    Returns: {today_row, prev_week_row, position_buckets}."""
    f = _find("*_perf_*_14-29-34.csv")
    rows = _read_csv(f)
    if not rows or len(rows) < 4:
        return {}
    header = [c.strip() for c in rows[0]]
    data_rows = rows[3:]  # skip Volume/Location header rows
    if not data_rows:
        return {}

    def _row_dict(r):
        return {header[i]: r[i].strip() for i in range(min(len(header), len(r)))}

    today = _row_dict(data_rows[-1])
    prev = _row_dict(data_rows[-8]) if len(data_rows) >= 8 else {}

    return {
        "date": today.get("Metric"),
        "organic_traffic": _num(today.get("Organic traffic")),
        "organic_traffic_value": _num(today.get("Organic traffic value")),
        "impressions": _num(today.get("Impressions")),
        "organic_pages": _num(today.get("Organic pages")),
        "position_buckets": {
            "1-3": _num(today.get("Organic positions: 1–3")),
            "4-10": _num(today.get("Organic positions: 4–10")),
            "11-20": _num(today.get("Organic positions: 11–20")),
            "21-50": _num(today.get("Organic positions: 21–50")),
            "51+": _num(today.get("Organic positions: 51+")),
        },
        "prev_week": {
            "organic_traffic": _num(prev.get("Organic traffic")) if prev else None,
            "impressions": _num(prev.get("Impressions")) if prev else None,
            "organic_traffic_value": _num(prev.get("Organic traffic value")) if prev else None,
        },
        "brand_splits": {
            "your_brand": _num(today.get("Organic traffic: Your brand (My World Child Care)")),
            "other_brands": _num(today.get("Organic traffic: Other brands")),
            "non_branded": _num(today.get("Organic traffic: Non-branded")),
        },
    }


def parse_backlinks_daily():
    """File: *_perf_*_14-29-25.csv — daily backlinks/DR/URL Rating.
    Returns: {referring_domains, domain_rating, url_rating, new_today, lost_today, wow}."""
    f = _find("*_perf_*_14-29-25.csv")
    rows = _read_csv(f)
    if not rows or len(rows) < 2:
        return {}
    header = [c.strip() for c in rows[0]]
    data_rows = rows[1:]

    def _row_dict(r):
        return {header[i]: r[i].strip() for i in range(min(len(header), len(r)))}

    today = _row_dict(data_rows[-1])
    # DR + URL Rating empty in latest row → search backward
    dr = _num(today.get("Domain Rating"))
    ur = _num(today.get("URL Rating"))
    if dr is None or ur is None:
        for r in reversed(data_rows):
            d = _row_dict(r)
            if dr is None:
                dr = _num(d.get("Domain Rating"))
            if ur is None:
                ur = _num(d.get("URL Rating"))
            if dr is not None and ur is not None:
                break

    prev = _row_dict(data_rows[-8]) if len(data_rows) >= 8 else {}
    return {
        "date": today.get("Metric"),
        "referring_domains_total": _num(today.get("Referring domains")),
        "domain_rating": dr,
        "url_rating": ur,
        "new_today": _num(today.get("New referring domains")),
        "lost_today": _num(today.get("Lost referring domains")),
        "prev_week": {
            "referring_domains_total": _num(prev.get("Referring domains")) if prev else None,
        },
    }


def parse_paid_daily():
    """File: *-perf-subdomains_month6_daily*.csv — paid traffic daily."""
    f = _find("*-perf-subdomains_month6_daily*.csv")
    rows = _read_csv(f)
    if not rows or len(rows) < 2:
        return {}
    header = [c.strip() for c in rows[0]]
    data_rows = rows[1:]

    def _row_dict(r):
        return {header[i]: r[i].strip() for i in range(min(len(header), len(r)))}

    today = _row_dict(data_rows[-1])
    return {
        "date": today.get("Date"),
        "paid_traffic": _num(today.get("Traffic (Monthly volume - All locations)")),
        "paid_cost": _num(today.get("Traffic cost (Monthly volume - All locations)")),
        "paid_keywords": _num(today.get("Paid keywords (Monthly volume - All locations)")),
        "paid_pages": _num(today.get("Paid pages (Monthly volume - All locations)")),
    }


def parse_backlinks_full():
    """File: *-backlinks-subdomains*.csv — UTF-16, tab-delim, full backlinks list.
    Returns: {total, recent_backlinks[], referring_domains[]}."""
    f = _find("*-backlinks-subdomains*.csv")
    if not f:
        return {}
    try:
        rows = _read_csv(f, encoding="utf-16", delimiter="\t")
    except Exception:
        rows = _read_csv(f, encoding="utf-8", delimiter="\t")
    if not rows or len(rows) < 2:
        return {}

    header = [c.strip().strip('"') for c in rows[0]]
    data_rows = rows[1:]

    def _row_dict(r):
        return {header[i]: r[i].strip().strip('"') for i in range(min(len(header), len(r)))}

    bl = [_row_dict(r) for r in data_rows]
    total = len(bl)

    # Recent backlinks — sort by First seen desc, take top 30
    def _first_seen(b):
        return b.get("First seen", "") or ""

    bl_sorted = sorted(bl, key=_first_seen, reverse=True)
    recent = []
    for b in bl_sorted[:30]:
        recent.append({
            "url_from": b.get("Referring page URL", ""),
            "title": b.get("Referring page title", ""),
            "domain_rating_source": _num(b.get("Domain rating")),
            "url_rating": _num(b.get("UR")),
            "first_seen": (b.get("First seen", "") or "")[:10],
            "anchor": b.get("Anchor", ""),
            "nofollow": b.get("Nofollow", "").lower() == "true",
            "target_url": b.get("Target URL", ""),
        })

    # Referring domains — dedupe + take highest-DR per domain
    domain_map = {}
    for b in bl:
        url = b.get("Referring page URL", "")
        m = re.match(r"https?://(?:www\.)?([^/]+)", url)
        if not m:
            continue
        domain = m.group(1).lower()
        dr = _num(b.get("Domain rating"))
        if domain not in domain_map or (dr or 0) > (domain_map[domain]["domain_rating"] or 0):
            domain_map[domain] = {
                "domain": domain,
                "domain_rating": dr,
                "domain_traffic": _num(b.get("Domain traffic")),
                "dofollow_links": 0,
            }
        # Count dofollow links
        is_nofollow = b.get("Nofollow", "").lower() == "true"
        if not is_nofollow:
            domain_map[domain]["dofollow_links"] += 1

    refdoms = sorted(domain_map.values(), key=lambda d: (d["domain_rating"] or 0), reverse=True)

    # Quality refdoms = DR40+
    quality = [d for d in refdoms if (d["domain_rating"] or 0) >= 40]

    return {
        "total_backlinks": total,
        "referring_domains_unique": len(refdoms),
        "quality_referring_domains_count": len(quality),
        "referring_domains": refdoms[:30],
        "recent_backlinks": recent,
    }


def parse_competitors():
    """File: *_overview-competitors*.csv — competitor matrix at most recent date."""
    f = _find("*_overview-competitors*.csv")
    rows = _read_csv(f)
    if not rows or len(rows) < 5:
        return {}

    domains_row = [c.strip() for c in rows[0]]
    metrics_row = [c.strip() for c in rows[1]]
    data_rows = rows[4:]
    if not data_rows:
        return {}
    last = [c.strip() for c in data_rows[-1]]

    # Map columns → (domain, metric)
    competitors = {}
    domain_pattern = re.compile(r"([a-z0-9.-]+\.[a-z]{2,})/?")
    for i in range(1, len(domains_row)):
        m = domain_pattern.search(domains_row[i].lower())
        if not m:
            continue
        domain = m.group(1).rstrip("/")
        metric = metrics_row[i] if i < len(metrics_row) else ""
        val = _num(last[i] if i < len(last) else "")
        if domain not in competitors:
            competitors[domain] = {"domain": domain}
        # Map metric to short key
        if "Organic traffic" in metric and "brand" not in metric.lower() and "intent" not in metric.lower():
            competitors[domain]["organic_traffic"] = val
        elif "Organic positions" in metric:
            competitors[domain]["organic_positions"] = val
        elif "Your brand" in metric or "Competitor's brand" in metric:
            competitors[domain]["brand_traffic"] = val
        elif "Informational" in metric:
            competitors[domain]["informational_traffic"] = val

    return {
        "date": last[0] if last else None,
        "competitors": list(competitors.values()),
    }


def parse_common_keywords():
    """File: *_common-keywords_*.csv — matrix of shared keywords between domains."""
    f = _find("*_common-keywords_*.csv")
    rows = _read_csv(f)
    if not rows or len(rows) < 2:
        return {}

    headers = [c.strip().rstrip("/") for c in rows[0]]
    matrix = {}
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        src = r[0].strip().rstrip("/")
        matrix[src] = {}
        for i in range(1, len(headers)):
            if i >= len(r):
                continue
            val = r[i].strip()
            if val == "-":
                continue
            matrix[src][headers[i]] = _num(val)
    return {"shared_keywords": matrix}


# ─── main ────────────────────────────────────────────────────────────────
def main():
    print(f"\n=== MWCC Ahrefs CSV Parse — {datetime.now():%Y-%m-%d %H:%M} ===")
    print(f"Inbox: {INBOX_DIR}")

    if not INBOX_DIR.exists():
        print(f"  ✗ Inbox not found: {INBOX_DIR}")
        return 1

    files = sorted(INBOX_DIR.glob("*.csv"))
    print(f"  Found {len(files)} CSV file(s)")
    if not files:
        return 1

    organic = parse_organic_daily()
    backlinks = parse_backlinks_daily()
    paid = parse_paid_daily()
    bl_full = parse_backlinks_full()
    comps = parse_competitors()
    common = parse_common_keywords()

    # Compose final shape
    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "manual_csv_export",
        "domain": SITE,

        # Headline KPIs
        "domain_rating": backlinks.get("domain_rating"),
        "url_rating": backlinks.get("url_rating"),
        "referring_domains_total": backlinks.get("referring_domains_total"),
        "backlinks_total": bl_full.get("total_backlinks"),
        "quality_referring_domains_count": bl_full.get("quality_referring_domains_count"),

        "organic_traffic": organic.get("organic_traffic"),
        "organic_traffic_value": organic.get("organic_traffic_value"),
        "impressions": organic.get("impressions"),
        "organic_pages": organic.get("organic_pages"),
        "position_buckets": organic.get("position_buckets", {}),

        "paid_traffic": paid.get("paid_traffic"),
        "paid_keywords": paid.get("paid_keywords"),
        "paid_cost": paid.get("paid_cost"),

        # WoW deltas (today vs 7 days ago)
        "wow": {
            "organic_traffic_prev": organic.get("prev_week", {}).get("organic_traffic"),
            "impressions_prev": organic.get("prev_week", {}).get("impressions"),
            "organic_traffic_value_prev": organic.get("prev_week", {}).get("organic_traffic_value"),
            "referring_domains_prev": backlinks.get("prev_week", {}).get("referring_domains_total"),
        },

        "brand_splits": organic.get("brand_splits", {}),

        # Lists for dashboard tables
        "referring_domains": bl_full.get("referring_domains", []),
        "recent_backlinks": bl_full.get("recent_backlinks", []),

        # Competitor data
        "competitor_overview": comps.get("competitors", []),
        "competitor_date": comps.get("date"),
        "shared_keywords": common.get("shared_keywords", {}),
    }

    STATE_DIR.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2))
    print(f"\n[saved] {OUT_FILE}")
    print(f"  Domain Rating: {out['domain_rating']}")
    print(f"  Referring domains: {out['referring_domains_total']}")
    print(f"  Backlinks total: {out['backlinks_total']}")
    print(f"  Quality refdoms (DR40+): {out['quality_referring_domains_count']}")
    print(f"  Organic traffic: {out['organic_traffic']}/month")
    print(f"  Organic value: ${out['organic_traffic_value']}/month")
    print(f"  Impressions: {out['impressions']}/month")
    print(f"  Paid traffic: {out['paid_traffic']}/month")
    print(f"  Competitor rows: {len(out['competitor_overview'])}")
    print(f"  Recent backlinks: {len(out['recent_backlinks'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
