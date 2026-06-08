"""
parse_mwcc_ahrefs_csvs.py — Parse manual Ahrefs CSV exports for MWCC.

Reads CSVs Tia drops into mwcc-inbox/ahrefs/ and writes state/mwcc-ahrefs.json
in the shape that renderMwccSeo() in docs/index.html expects.

This is the MANUAL fallback for when AHREFS_API_KEY is unavailable
(rotating token issue, June 2026). Replaces pull_mwcc_ahrefs.py for the
weekly cron until token is back.

EXPECTED FILES in mwcc-inbox/ahrefs/:
  Overview_*.pdf                     — Site Explorer Overview PDF (canonical headline KPIs)
  *backlinks-subdomains*.csv         — Full backlinks list (UTF-16, tab-delim)
  *_perf_*_14-29-25.csv              — Backlinks daily (referring domains, DR, URL Rating)
  *_perf_*_14-29-34.csv              — Organic daily (traffic, value, impressions, position buckets)
  *-perf-subdomains_month6_daily*.csv — Paid traffic daily
  *_overview-competitors*.csv        — Competitor matrix
  *_common-keywords_*.csv            — Shared keyword matrix
  *_perf_*_14-28-53.csv              — Big perf file with brand/intent splits

PDF is preferred for headline KPIs (DR, UR, Backlinks total, Ref domains,
Organic keywords, Organic traffic, Paid keywords) — CSVs are sometimes row-capped.
CSVs still provide row-level lists (backlinks list, refdomains list, competitor matrix).

USAGE: python scripts/parse_mwcc_ahrefs_csvs.py
"""

import csv
import json
import re
from datetime import datetime
from pathlib import Path

try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

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
    s = str(v).strip().replace(",", "").replace("$", "").lstrip("+")
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


def parse_overview_pdf():
    """File: Overview_*.pdf — Ahrefs Site Explorer Overview PDF.
    Authoritative source for headline KPIs (more reliable than CSVs which
    can be row-capped). Extracts DR, UR, Ahrefs Rank, Backlinks total +
    WoW delta, Ref domains total + delta, Organic keywords + delta,
    Top 3 keywords, Organic traffic + value, Paid keywords/traffic/cost,
    All-time totals, AI citations.

    Returns dict of headline KPIs. Empty dict if PDF missing or pdfplumber
    unavailable.
    """
    if not _HAS_PDFPLUMBER:
        return {}
    f = _find("Overview_*.pdf") or _find("overview_*.pdf") or _find("*Overview*.pdf")
    if not f:
        return {}
    try:
        with pdfplumber.open(f) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        print(f"  ⚠️  PDF parse error: {e}")
        return {}

    if not text:
        return {}

    # Translate Ahrefs private-use-area glyphs (icon font in their PDFs).
    # Preserve sign info from the delta arrows:
    #   U+E09D = up-arrow (green)  -> "+"
    #   U+E09E = down-arrow (red)  -> "-"
    #   U+E089 = position-dot icon -> strip
    text = text.replace("", "+").replace("", "-")
    text = re.sub(r"[-]", "", text)
    text = re.sub(r" +", " ", text)

    # Helper to extract "Label\nN [delta]" pattern
    def _grab(pattern, default=None):
        m = re.search(pattern, text, re.MULTILINE)
        if not m:
            return default
        try:
            return _num(m.group(1))
        except Exception:
            return default

    # Headline KPI block uses a particular order. Use regexes anchored to labels.
    # Patterns handle "Label\nvalue\ndelta" OR "Label\nvalue change"
    out = {
        "domain_rating": _grab(r"DR\s*\n\s*(\d+)"),
        "url_rating": _grab(r"\bUR\s*\n\s*(\d+)"),
        "ahrefs_rank": _grab(r"AR\s+([\d,]+)"),
        "ahrefs_rank_change": _grab(r"AR\s+[\d,]+\s+([\-\d,]+)"),
        "backlinks_total": _grab(r"Backlinks\s+Ref\.\s*domains[^\n]*\n\s*([\d,]+)"),
        "ref_domains_total": _grab(r"Backlinks\s+Ref\.\s*domains[^\n]*\n\s*[\d,]+\s+([\d,]+)"),
        "organic_keywords_total": _grab(r"Organic keywords\s+Organic traffic[^\n]*\n\s*\d+\s+\d+\s*\n\s*(\d+)"),
        "organic_traffic": _grab(r"Organic keywords\s+Organic traffic[^\n]*\n\s*\d+\s+(\d+)"),
        "paid_keywords": _grab(r"Paid keywords\s+Paid traffic[^\n]*\n\s*(\d+)"),
        "paid_traffic": _grab(r"Paid keywords\s+Paid traffic[^\n]*\n\s*\d+\s+(\d+)"),
    }

    # Second-pass cleaner regexes — looser to handle Ahrefs PDF layout quirks
    # Headline block looks like:
    #   DR UR Organic keywords Organic traffic
    #   6 0 17 151
    #   1 9
    #   AR 26,165,129 400,630 Top 3 11 2 Value $92 40
    #   Backlinks Ref. domains Paid keywords Paid traffic
    #   805 206 3 4
    #   304 106 2 1
    #   All time 4.3K All time 362 Ads 3 2 Cost $5
    m = re.search(
        r"DR\s+UR\s+Organic keywords\s+Organic traffic\s*\n"
        r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\n"
        r"\s*([+\-\d,]+)\s+([+\-\d,]+)",
        text,
    )
    if m:
        out["domain_rating"] = _num(m.group(1))
        out["url_rating"] = _num(m.group(2))
        out["organic_keywords_total"] = _num(m.group(3))
        out["organic_traffic"] = _num(m.group(4))
        out["organic_keywords_change"] = _num(m.group(5))
        out["organic_traffic_change"] = _num(m.group(6))

    # Top 3 + Value block: "AR 26,165,129 400,630 Top 3 11 2 Value $92 40"
    m = re.search(
        r"AR\s+([\d,]+)\s+([+\-\d,]+)\s+Top 3\s+(\d+)\s+([+\-\d,]+)\s+Value\s+\$?([\d,]+)\s+([+\-\d,]+)",
        text,
    )
    if m:
        out["ahrefs_rank"] = _num(m.group(1))
        out["ahrefs_rank_change"] = _num(m.group(2))
        out["top_3_keywords"] = _num(m.group(3))
        out["top_3_keywords_change"] = _num(m.group(4))
        out["organic_traffic_value"] = _num(m.group(5))
        out["organic_traffic_value_change"] = _num(m.group(6))

    # Backlinks / Ref domains / Paid block: 4 values then 4 changes
    m = re.search(
        r"Backlinks\s+Ref\.\s*domains\s+Paid keywords\s+Paid traffic\s*\n"
        r"\s*([\d,]+)\s+([\d,]+)\s+(\d+)\s+(\d+)\s*\n"
        r"\s*([+\-\d,]+)\s+([+\-\d,]+)\s+([+\-\d,]+)\s+([+\-\d,]+)",
        text,
    )
    if m:
        out["backlinks_total"] = _num(m.group(1))
        out["ref_domains_total"] = _num(m.group(2))
        out["paid_keywords"] = _num(m.group(3))
        out["paid_traffic"] = _num(m.group(4))
        out["backlinks_change"] = _num(m.group(5))
        out["ref_domains_change"] = _num(m.group(6))
        out["paid_keywords_change"] = _num(m.group(7))
        out["paid_traffic_change"] = _num(m.group(8))

    # All-time totals: "All time 4.3K All time 362 Ads 3 2 Cost $5"
    m = re.search(
        r"All time\s+([\d.]+K?)\s+All time\s+([\d,]+)\s+Ads\s+(\d+)\s+([+\-\d,]+)\s+Cost\s+\$?([\d,]+)",
        text,
    )
    if m:
        # 4.3K → 4300
        bl_all = m.group(1)
        if bl_all.endswith("K"):
            out["backlinks_all_time"] = int(float(bl_all[:-1]) * 1000)
        else:
            out["backlinks_all_time"] = _num(bl_all)
        out["ref_domains_all_time"] = _num(m.group(2))
        out["ads_count"] = _num(m.group(3))
        out["ads_change"] = _num(m.group(4))
        out["paid_cost"] = _num(m.group(5))

    # AI citations (currently all zero but worth tracking when MWCC starts ranking)
    ai = {}
    for platform in ("AI Mode", "Gemini", "Perplexity", "Copilot", "Grok"):
        m = re.search(rf"{re.escape(platform)}\s+(\d+)\s+(\d+)", text)
        if m:
            ai[platform.lower().replace(" ", "_")] = {
                "citations": _num(m.group(1)),
                "pages": _num(m.group(2)),
            }
    m = re.search(r"AIO \(search queries\)\s+(\d+)\s+(\d+)", text)
    if m:
        ai["aio_search_queries"] = {"citations": _num(m.group(1)), "pages": _num(m.group(2))}
    m = re.search(r"AI Overviews\s*\n\s*(\d+)", text)
    if m:
        ai["ai_overviews_total"] = _num(m.group(1))
    m = re.search(r"ChatGPT\s*\n\s*(\d+)", text)
    if m:
        ai["chatgpt_total"] = _num(m.group(1))
    if ai:
        out["ai_citations"] = ai

    return {k: v for k, v in out.items() if v is not None}


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
    pdf_kpis = parse_overview_pdf()  # authoritative for headline numbers

    # PDF takes priority over CSV for headline KPIs (CSV exports are sometimes
    # row-capped — PDF shows the true totals from Ahrefs Site Explorer Overview).
    def _prefer(pdf_val, csv_val):
        return pdf_val if pdf_val is not None else csv_val

    # Compose final shape
    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "manual_pdf_csv_export" if pdf_kpis else "manual_csv_export",
        "domain": SITE,

        # Headline KPIs (PDF preferred; CSVs are fallback)
        "domain_rating": _prefer(pdf_kpis.get("domain_rating"), backlinks.get("domain_rating")),
        "url_rating": _prefer(pdf_kpis.get("url_rating"), backlinks.get("url_rating")),
        "ahrefs_rank": pdf_kpis.get("ahrefs_rank"),
        "ahrefs_rank_change": pdf_kpis.get("ahrefs_rank_change"),

        "referring_domains_total": _prefer(pdf_kpis.get("ref_domains_total"), backlinks.get("referring_domains_total")),
        "ref_domains_change_mom": pdf_kpis.get("ref_domains_change"),
        "ref_domains_all_time": pdf_kpis.get("ref_domains_all_time"),

        "backlinks_total": _prefer(pdf_kpis.get("backlinks_total"), bl_full.get("total_backlinks")),
        "backlinks_change_mom": pdf_kpis.get("backlinks_change"),
        "backlinks_all_time": pdf_kpis.get("backlinks_all_time"),
        "quality_referring_domains_count": bl_full.get("quality_referring_domains_count"),

        "organic_keywords_total": pdf_kpis.get("organic_keywords_total"),
        "organic_keywords_change_mom": pdf_kpis.get("organic_keywords_change"),
        "top_3_keywords": pdf_kpis.get("top_3_keywords"),
        "top_3_keywords_change_mom": pdf_kpis.get("top_3_keywords_change"),

        "organic_traffic": _prefer(pdf_kpis.get("organic_traffic"), organic.get("organic_traffic")),
        "organic_traffic_change_mom": pdf_kpis.get("organic_traffic_change"),
        "organic_traffic_value": _prefer(pdf_kpis.get("organic_traffic_value"), organic.get("organic_traffic_value")),
        "organic_traffic_value_change_mom": pdf_kpis.get("organic_traffic_value_change"),
        "impressions": organic.get("impressions"),
        "organic_pages": organic.get("organic_pages"),
        "position_buckets": organic.get("position_buckets", {}),

        "paid_traffic": _prefer(pdf_kpis.get("paid_traffic"), paid.get("paid_traffic")),
        "paid_traffic_change_mom": pdf_kpis.get("paid_traffic_change"),
        "paid_keywords": _prefer(pdf_kpis.get("paid_keywords"), paid.get("paid_keywords")),
        "paid_keywords_change_mom": pdf_kpis.get("paid_keywords_change"),
        "paid_cost": _prefer(pdf_kpis.get("paid_cost"), paid.get("paid_cost")),
        "ads_count": pdf_kpis.get("ads_count"),
        "ads_change_mom": pdf_kpis.get("ads_change"),

        # AI citations (LLMs.txt era — track even when zero)
        "ai_citations": pdf_kpis.get("ai_citations", {}),

        # WoW deltas (today vs 7 days ago — from CSVs, separate from PDF MoM)
        "wow": {
            "organic_traffic_prev": organic.get("prev_week", {}).get("organic_traffic"),
            "impressions_prev": organic.get("prev_week", {}).get("impressions"),
            "organic_traffic_value_prev": organic.get("prev_week", {}).get("organic_traffic_value"),
            "referring_domains_prev": backlinks.get("prev_week", {}).get("referring_domains_total"),
        },

        "brand_splits": organic.get("brand_splits", {}),

        # Lists for dashboard tables (CSV-only — PDF doesn't include row-level)
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
    print(f"  Source: {out['source']}")
    print(f"  Domain Rating: {out['domain_rating']} · URL Rating: {out['url_rating']}")
    if out.get('ahrefs_rank'):
        print(f"  Ahrefs Rank: {out['ahrefs_rank']:,} (Δ {out.get('ahrefs_rank_change') or '—'})")
    print(f"  Backlinks: {out['backlinks_total']} (MoM Δ {out.get('backlinks_change_mom') or '—'}, all-time {out.get('backlinks_all_time') or '—'})")
    print(f"  Ref domains: {out['referring_domains_total']} (MoM Δ {out.get('ref_domains_change_mom') or '—'}, all-time {out.get('ref_domains_all_time') or '—'})")
    print(f"  Quality refdoms (DR40+): {out['quality_referring_domains_count']}")
    print(f"  Organic keywords: {out.get('organic_keywords_total') or '—'} (Top 3: {out.get('top_3_keywords') or '—'})")
    print(f"  Organic traffic: {out['organic_traffic']}/month (MoM Δ {out.get('organic_traffic_change_mom') or '—'})")
    print(f"  Organic value: ${out['organic_traffic_value']}/month (MoM Δ ${out.get('organic_traffic_value_change_mom') or '—'})")
    print(f"  Impressions: {out['impressions']}/month")
    print(f"  Paid traffic: {out['paid_traffic']}/month · Paid keywords: {out['paid_keywords']}")
    print(f"  Competitor rows: {len(out['competitor_overview'])}")
    print(f"  Recent backlinks: {len(out['recent_backlinks'])}")
    if out.get('ai_citations'):
        ai = out['ai_citations']
        ai_total = sum(v.get('citations', 0) if isinstance(v, dict) else 0 for v in ai.values())
        print(f"  AI citations: {ai_total} total across {len([k for k in ai if isinstance(ai[k], dict)])} platforms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
