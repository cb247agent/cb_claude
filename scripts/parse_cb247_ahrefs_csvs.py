"""
parse_cb247_ahrefs_csvs.py — Parse manual Ahrefs CSV/PDF exports for CB247.

CB247 mirror of parse_mwcc_ahrefs_csvs.py. Reads exports Tia drops into
cb247-inbox/ahrefs/ and writes:
  state/ahrefs-data.json                       (rich format — bake-dashboard reads)
  state/ahrefs-snapshot-YYYY-MM-DD.json        (flat format — inject-seo-extras reads)

This is the MANUAL fallback for when Ahrefs API token is unavailable
(token exhaustion after 1 June 2026 cron run). Replaces pull_ahrefs.py
for the weekly cron until token is restored.

EXPECTED FILES in cb247-inbox/ahrefs/ (filenames carry timestamps,
parser identifies them by header-column heuristics for robustness):
  Overview_*.pdf                           — Site Explorer Overview PDF
                                             (canonical headline KPIs)
  *_perf_*.csv (×3, distinguished by cols) — Big perf | backlinks | organic+SERP
  *-organic-keywords-hist_*.csv            — Daily keyword bucket history
  *-organic-positions-his_*.csv            — Daily position bucket history
  *-perf-subdomains_all_d_*.csv            — Daily paid traffic/cost/keywords
  *-perf-subdomains_month_*.csv            — Monthly organic subdomain
  *_orgcompetitors-map_su_*.csv            — Competitor WoW traffic comparison
  *_overview-competitors_*.csv             — Competitor matrix snapshots

PDF is preferred for headline KPIs (DR, UR, backlinks total, ref domains,
organic kws, organic traffic) — CSVs sometimes carry empty cells on the
most-recent day before Ahrefs settles. CSVs provide row-level history
and competitor comparisons that aren't in the PDF.

USAGE: python scripts/parse_cb247_ahrefs_csvs.py
"""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

BASE_DIR = Path(__file__).resolve().parent.parent
INBOX_DIR = BASE_DIR / "cb247-inbox" / "ahrefs"
STATE_DIR = BASE_DIR / "state"
OUT_RICH_FILE = STATE_DIR / "ahrefs-data.json"
SITE = "chasingbetter247.com.au"


# ─── helpers ─────────────────────────────────────────────────────────────
def _num(v):
    """Strip whitespace + commas + $, return int/float or None.

    Handles Ahrefs shorthand:
      "1.8K"  → 1800
      "3.9K"  → 3900
      "22M"   → 22_000_000
    """
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("$", "").lstrip("+")
    if s in ("", "-", "–"):
        return None
    # K/M/B suffix
    mult = 1
    if s.endswith("K") or s.endswith("k"):
        mult = 1_000
        s = s[:-1]
    elif s.endswith("M") or s.endswith("m"):
        mult = 1_000_000
        s = s[:-1]
    elif s.endswith("B") or s.endswith("b"):
        mult = 1_000_000_000
        s = s[:-1]
    try:
        if "." in s:
            return int(float(s) * mult) if mult > 1 else float(s)
        return int(s) * mult
    except ValueError:
        return None


def _find_one(pattern):
    """Find ONE file in INBOX_DIR matching a glob, newest first by mtime."""
    if not INBOX_DIR.exists():
        return None
    matches = sorted(INBOX_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _find_all(pattern):
    """Find ALL files matching a glob, newest first."""
    if not INBOX_DIR.exists():
        return []
    return sorted(INBOX_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)


def _read_csv(path):
    if not path or not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.reader(f))


def _last_non_empty(rows, col_idx):
    """Walk rows from end; return first non-empty value at col_idx (or None)."""
    for r in reversed(rows):
        if col_idx < len(r):
            v = _num(r[col_idx])
            if v is not None:
                return v
    return None


# ─── perf_*.csv router — 3 files share a glob, distinguished by headers ───
def _classify_perf_csv(path):
    """Inspect first row to determine which of the 3 perf reports this is.
    Returns one of: 'backlinks' | 'organic_serp' | 'brand_intent' | None."""
    rows = _read_csv(path)
    if not rows:
        return None
    header = [c.strip() for c in rows[0]]
    if "Domain Rating" in header and "URL Rating" in header:
        return "backlinks"
    # Both organic_serp and brand_intent have lots of cols — distinguish by SERP Features
    has_serp = any("SERP Features" in c for c in header)
    has_intent = any("by intent" in c for c in header)
    has_referring = "Referring domains" in header
    if has_serp:
        return "organic_serp"
    if has_intent and has_referring:
        # brand_intent CSV has Referring domains in col 1 (no SERP cols)
        return "brand_intent"
    return None


def _load_perf_files():
    """Pre-classify all *_perf_*.csv files. Returns dict of {type: path}."""
    classified = {}
    for f in _find_all("*_perf_*.csv"):
        # Skip subdomain perf files — different naming pattern handled separately
        if "perf-subdomains" in f.name:
            continue
        kind = _classify_perf_csv(f)
        if kind and kind not in classified:
            classified[kind] = f
    return classified


# ─── parsers per CSV ─────────────────────────────────────────────────────
def parse_backlinks_daily(perf_files):
    """*_perf_*.csv classified as 'backlinks' — daily DR/UR/refdoms/new/lost.
    Returns {referring_domains_total, domain_rating, url_rating, new_today,
             lost_today, prev_week}."""
    f = perf_files.get("backlinks")
    rows = _read_csv(f)
    if len(rows) < 2:
        return {}
    header = [c.strip() for c in rows[0]]
    data = rows[1:]

    def _col(name):
        try:
            return header.index(name)
        except ValueError:
            return -1

    rd_i  = _col("Referring domains")
    dr_i  = _col("Domain Rating")
    ur_i  = _col("URL Rating")
    new_i = _col("New referring domains")
    lost_i = _col("Lost referring domains")

    today_row = data[-1]
    prev_row = data[-8] if len(data) >= 8 else []

    return {
        "date": today_row[0].strip() if today_row else None,
        "referring_domains_total": _last_non_empty(data, rd_i) if rd_i >= 0 else None,
        "domain_rating": _last_non_empty(data, dr_i) if dr_i >= 0 else None,
        "url_rating": _last_non_empty(data, ur_i) if ur_i >= 0 else None,
        "new_today": _num(today_row[new_i]) if new_i >= 0 and new_i < len(today_row) else None,
        "lost_today": _num(today_row[lost_i]) if lost_i >= 0 and lost_i < len(today_row) else None,
        "prev_week": {
            "referring_domains_total": _num(prev_row[rd_i]) if rd_i >= 0 and rd_i < len(prev_row) else None,
        },
    }


def parse_organic_serp_daily(perf_files):
    """*_perf_*.csv classified as 'organic_serp' — daily organic + SERP features.
    Returns {date, organic_traffic, organic_traffic_value, impressions,
             organic_pages, position_buckets, serp_features, prev_week}."""
    f = perf_files.get("organic_serp")
    rows = _read_csv(f)
    if len(rows) < 2:
        return {}
    header = [c.strip() for c in rows[0]]
    data = rows[1:]

    def _col(name):
        try:
            return header.index(name)
        except ValueError:
            return -1

    def _row_dict(r):
        return {header[i]: r[i].strip() if i < len(r) else "" for i in range(len(header))}

    today = _row_dict(data[-1])
    prev = _row_dict(data[-8]) if len(data) >= 8 else {}

    # SERP features owned — accumulate non-zero
    serp_features = {}
    for k, v in today.items():
        if k.startswith("SERP Features: ") and k.endswith("(Owned)"):
            n = _num(v)
            if n is not None and n > 0:
                feat = k[len("SERP Features: "):-len(" (Owned)")]
                serp_features[feat] = n

    return {
        "date": today.get("Metric"),
        "organic_traffic": _num(today.get("Organic traffic")),
        "organic_traffic_value": _num(today.get("Organic traffic value")),
        "impressions": _num(today.get("Impressions")),
        "organic_pages": _num(today.get("Organic pages")),
        "position_buckets": {
            "1-3":   _num(today.get("Organic positions: 1–3")),
            "4-10":  _num(today.get("Organic positions: 4–10")),
            "11-20": _num(today.get("Organic positions: 11–20")),
            "21-50": _num(today.get("Organic positions: 21–50")),
            "51+":   _num(today.get("Organic positions: 51+")),
        },
        "serp_features_owned": serp_features,
        "prev_week": {
            "organic_traffic": _num(prev.get("Organic traffic")) if prev else None,
            "impressions": _num(prev.get("Impressions")) if prev else None,
            "organic_traffic_value": _num(prev.get("Organic traffic value")) if prev else None,
        },
        # brand_splits + intent_splits surfaced via parse_brand_intent below
    }


def parse_brand_intent_daily(perf_files):
    """*_perf_*.csv classified as 'brand_intent' — brand/non-brand + intent splits."""
    f = perf_files.get("brand_intent")
    rows = _read_csv(f)
    if len(rows) < 2:
        return {}
    header = [c.strip() for c in rows[0]]
    data = rows[1:]
    today = {header[i]: data[-1][i].strip() if i < len(data[-1]) else "" for i in range(len(header))}

    return {
        "brand_splits": {
            "your_brand":   _num(today.get("Organic traffic: Your brand (ChasingBetter247)")),
            "other_brands": _num(today.get("Organic traffic: Other brands")),
            "non_branded":  _num(today.get("Organic traffic: Non-branded")),
        },
        "intent_splits": {
            "informational": _num(today.get("Organic traffic by intent: Informational")),
            "navigational":  _num(today.get("Organic traffic by intent: Navigational")),
            "commercial":    _num(today.get("Organic traffic by intent: Commercial")),
            "transactional": _num(today.get("Organic traffic by intent: Transactional")),
            "branded":       _num(today.get("Organic traffic by intent: Branded")),
            "local":         _num(today.get("Organic traffic by intent: Local")),
        },
    }


def parse_paid_subdomain_daily():
    """*-perf-subdomains_all_d_*.csv — daily paid traffic/cost/keywords/pages."""
    f = _find_one("*-perf-subdomains_all_d_*.csv")
    rows = _read_csv(f)
    if len(rows) < 2:
        return {}
    header = [c.strip() for c in rows[0]]
    today = rows[-1]
    today_d = {header[i]: today[i].strip() if i < len(today) else "" for i in range(len(header))}
    return {
        "date": today_d.get("Date"),
        "paid_traffic":  _num(today_d.get("Traffic (Monthly volume - All locations)")),
        "paid_cost":     _num(today_d.get("Traffic cost (Monthly volume - All locations)")),
        "paid_keywords": _num(today_d.get("Paid keywords (Monthly volume - All locations)")),
        "paid_pages":    _num(today_d.get("Paid pages (Monthly volume - All locations)")),
    }


def parse_organic_subdomain_monthly():
    """*-perf-subdomains_month_*.csv — monthly organic pages + traffic."""
    f = _find_one("*-perf-subdomains_month_*.csv")
    rows = _read_csv(f)
    if len(rows) < 2:
        return {}
    header = [c.strip() for c in rows[0]]
    today = rows[-1]
    today_d = {header[i]: today[i].strip() if i < len(today) else "" for i in range(len(header))}
    return {
        "date": today_d.get("Date"),
        "organic_pages_monthly":   _num(today_d.get("Organic pages (Monthly volume - All locations)")),
        "organic_traffic_monthly": _num(today_d.get("Organic traffic (Monthly volume - All locations)")),
    }


def parse_position_history():
    """*-organic-positions-his_*.csv — 183 days of position bucket history.
    Returns dict {date: {1-3, 4-10, 11-20, 21-50, 51+}} for last 30 days."""
    f = _find_one("*-organic-positions-his_*.csv")
    rows = _read_csv(f)
    if len(rows) < 2:
        return []
    out = []
    for r in rows[1:]:
        if len(r) < 6:
            continue
        out.append({
            "date":  r[0].strip(),
            "1-3":   _num(r[1]),
            "4-10":  _num(r[2]),
            "11-20": _num(r[3]),
            "21-50": _num(r[4]),
            "51+":   _num(r[5]),
        })
    return out[-30:]   # last 30 days for chart


def parse_keyword_history():
    """*-organic-keywords-hist_*.csv — 183 days of keyword bucket history."""
    f = _find_one("*-organic-keywords-hist_*.csv")
    rows = _read_csv(f)
    if len(rows) < 2:
        return []
    out = []
    for r in rows[1:]:
        if len(r) < 6:
            continue
        out.append({
            "date":  r[0].strip(),
            "1-3":   _num(r[1]),
            "4-10":  _num(r[2]),
            "11-20": _num(r[3]),
            "21-50": _num(r[4]),
            "51+":   _num(r[5]),
        })
    return out[-30:]


def parse_competitor_wow():
    """*_orgcompetitors-map_su_*.csv — competitor WoW traffic comparison.
    Returns list of {competitor, mode, previous/current traffic + value, deltas, pages}."""
    f = _find_one("*_orgcompetitors-map_su_*.csv")
    rows = _read_csv(f)
    if len(rows) < 2:
        return []
    header = [c.strip() for c in rows[0]]
    data = rows[1:]
    out = []
    for r in data:
        d = {header[i]: r[i].strip() if i < len(r) else "" for i in range(len(header))}
        out.append({
            "competitor":       d.get("Competitor"),
            "mode":             d.get("Mode"),
            "previous_traffic": _num(d.get("Previous traffic")),
            "current_traffic":  _num(d.get("Current traffic")),
            "traffic_change":   _num(d.get("Traffic change")),
            "previous_value":   _num(d.get("Previous traffic value")),
            "current_value":    _num(d.get("Current traffic value")),
            "value_change":     _num(d.get("Traffic value change")),
            "previous_pages":   _num(d.get("Previous # of pages")),
            "current_pages":    _num(d.get("Current # of pages")),
            "pages_change":     _num(d.get("Pages change")),
        })
    return out


def parse_competitors_matrix():
    """*_overview-competitors_*.csv — current row from competitor matrix.
    Multiple snapshot files exist; use newest. Returns {date, competitors:[...]}."""
    f = _find_one("*_overview-competitors_*.csv")
    rows = _read_csv(f)
    if not rows or len(rows) < 5:
        return {}
    domains_row = [c.strip() for c in rows[0]]
    metrics_row = [c.strip() for c in rows[1]]
    data = rows[4:]
    if not data:
        return {}
    last = [c.strip() for c in data[-1]]
    competitors = {}
    domain_pattern = re.compile(r"([a-z0-9.-]+\.[a-z]{2,})/?")
    for i in range(1, len(domains_row)):
        m = domain_pattern.search(domains_row[i].lower())
        if not m:
            continue
        domain = m.group(1).rstrip("/")
        metric = metrics_row[i] if i < len(metrics_row) else ""
        val = _num(last[i] if i < len(last) else "")
        comp = competitors.setdefault(domain, {"domain": domain})
        if "Organic traffic" in metric and "brand" not in metric.lower() and "intent" not in metric.lower():
            comp["organic_traffic"] = val
        elif "Organic positions" in metric:
            comp["organic_positions"] = val
        elif "Your brand" in metric or "Competitor's brand" in metric:
            comp["brand_traffic"] = val
        elif "Informational" in metric:
            comp["informational_traffic"] = val
    return {
        "date": last[0] if last else None,
        "competitors": list(competitors.values()),
    }


def parse_overview_pdf():
    """Overview_*.pdf — Site Explorer Overview, canonical headline KPIs."""
    if not _HAS_PDFPLUMBER:
        return {}
    f = _find_one("Overview_*.pdf") or _find_one("overview_*.pdf") or _find_one("*Overview*.pdf")
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

    # Translate Ahrefs private-use-area glyphs (icon font in their PDFs)
    text = text.replace("", "+").replace("", "-")
    text = re.sub(r"[-]", "", text)
    text = re.sub(r" +", " ", text)

    out = {}

    # Headline: DR UR Organic keywords Organic traffic
    #   7 0 60 1.8K          (values; "1.8K" can carry suffix)
    #   11 114               (changes; one int per metric, sign stripped)
    # The 4-value row carries DR, UR, kw_total, organic_traffic.
    # The next short row carries the DELTAS for kw + traffic (DR/UR change
    # only emit when they actually move — usually omitted).
    m = re.search(
        r"DR\s+UR\s+Organic keywords\s+Organic traffic\s*\n"
        r"\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+[KMB]?)\s*\n"
        r"\s*([\d.+\-]+[KMB]?)\s+([\d.+\-]+[KMB]?)",
        text,
    )
    if m:
        out["domain_rating"] = _num(m.group(1))
        out["url_rating"] = _num(m.group(2))
        out["organic_keywords_total"] = _num(m.group(3))
        out["organic_traffic"] = _num(m.group(4))
        out["organic_keywords_change"] = _num(m.group(5))
        out["organic_traffic_change"] = _num(m.group(6))

    # AR + Top 3 + Value line:
    #   AR 22,311,321 +586,342 Top 3 40 +7 Value $604 +137
    #      <rank>     <Δrank>  Top 3 <top3> <Δtop3> Value $<val> <Δval>
    # (deltas get a "+" or "-" prefix from the glyph translation above)
    m = re.search(
        r"AR\s+([\d,]+)\s+([+\-]?[\d,]+)\s+Top 3\s+(\d+)\s+([+\-]?[\d,]+)\s+Value\s+\$?([\d,]+)\s+([+\-]?[\d,]+)",
        text,
    )
    if m:
        out["ahrefs_rank"] = _num(m.group(1))
        out["ahrefs_rank_change"] = _num(m.group(2))
        out["top_3_keywords"] = _num(m.group(3))
        out["top_3_keywords_change"] = _num(m.group(4))
        out["organic_traffic_value"] = _num(m.group(5))
        out["organic_traffic_value_change"] = _num(m.group(6))

    # Backlinks / Ref domains / Paid block:
    #   Backlinks Ref. domains Paid keywords Paid traffic
    #     724 266 1 1            (values)
    #     +342 +135 +1 +1        (changes — with "+"/"-" prefix from glyph translation)
    m = re.search(
        r"Backlinks\s+Ref\.\s*domains\s+Paid keywords\s+Paid traffic\s*\n"
        r"\s*([\d,]+)\s+([\d,]+)\s+(\d+)\s+(\d+)\s*\n"
        r"\s*([+\-]?[\d,]+)\s+([+\-]?[\d,]+)\s+([+\-]?\d+)\s+([+\-]?\d+)",
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

    # All-time + Ads block:
    #   All time 3.9K All time 521 Ads 1 +1 Cost $1
    m = re.search(
        r"All time\s+([\d.]+[KMB]?)\s+All time\s+([\d,]+)\s+Ads\s+(\d+)\s+([+\-]?[\d,]+)\s+Cost\s+\$?([\d,]+)",
        text,
    )
    if m:
        out["backlinks_all_time"] = _num(m.group(1))
        out["ref_domains_all_time"] = _num(m.group(2))
        out["ads_count"] = _num(m.group(3))
        out["ads_change"] = _num(m.group(4))
        out["paid_cost"] = _num(m.group(5))

    return out


# ─── Build output ────────────────────────────────────────────────────────
def build_rich_data():
    """Combine all parsed sources into the rich ahrefs-data.json shape."""
    perf_files = _load_perf_files()
    pdf  = parse_overview_pdf()
    bl   = parse_backlinks_daily(perf_files)
    org  = parse_organic_serp_daily(perf_files)
    brand = parse_brand_intent_daily(perf_files)
    paid = parse_paid_subdomain_daily()
    org_mo = parse_organic_subdomain_monthly()
    pos_hist = parse_position_history()
    kw_hist = parse_keyword_history()
    comp_wow = parse_competitor_wow()
    comp_mx = parse_competitors_matrix()

    # PDF wins for headline KPIs (more reliable than CSV's empty-cell issue
    # on the most-recent day). CSV provides yesterday's authoritative values
    # for daily metrics (DR/UR are slow-moving so CSV's last-non-empty works).
    dr = pdf.get("domain_rating") or bl.get("domain_rating")
    ur = pdf.get("url_rating") or bl.get("url_rating")
    refdoms_total = pdf.get("ref_domains_total") or bl.get("referring_domains_total")

    # WoW deltas
    refdoms_wow = None
    if refdoms_total and bl.get("prev_week", {}).get("referring_domains_total"):
        refdoms_wow = refdoms_total - bl["prev_week"]["referring_domains_total"]

    organic_traffic_wow_pct = None
    if org.get("organic_traffic") and org.get("prev_week", {}).get("organic_traffic"):
        prev = org["prev_week"]["organic_traffic"]
        if prev:
            organic_traffic_wow_pct = round(
                (org["organic_traffic"] - prev) / prev * 100, 1
            )

    organic_value_wow_pct = None
    if org.get("organic_traffic_value") and org.get("prev_week", {}).get("organic_traffic_value"):
        prev = org["prev_week"]["organic_traffic_value"]
        if prev:
            organic_value_wow_pct = round(
                (org["organic_traffic_value"] - prev) / prev * 100, 1
            )

    return {
        "_meta": {
            "source": "Manual CSV/PDF export from Ahrefs UI",
            "as_of_date": datetime.now().strftime("%Y-%m-%d"),
            "parser_run_at": datetime.now(timezone.utc).isoformat(),
            "frozen_reason": "Ahrefs API token unavailable; using manual cb247-inbox/ahrefs exports",
            "inbox_dir": str(INBOX_DIR.relative_to(BASE_DIR)),
        },
        "site": SITE,
        "date_pulled": datetime.now(timezone.utc).isoformat(),

        # Headline KPIs (PDF preferred, CSV fallback)
        "domain_rating": dr,
        "domain_rating_target": 10,
        "url_rating": ur,
        "ahrefs_rank": pdf.get("ahrefs_rank"),
        "ahrefs_rank_change": pdf.get("ahrefs_rank_change"),

        # Backlinks
        "backlinks_total": pdf.get("backlinks_total"),
        "backlinks_change": pdf.get("backlinks_change"),
        "backlinks_all_time": pdf.get("backlinks_all_time"),

        # Referring domains
        "total_refdoms": refdoms_total,
        "refdoms_wow_change": refdoms_wow,
        "refdoms_change_pdf": pdf.get("ref_domains_change"),
        "refdoms_all_time": pdf.get("ref_domains_all_time"),
        "new_refdoms_today": bl.get("new_today"),
        "lost_refdoms_today": bl.get("lost_today"),
        # Quality refdoms count not available in CSV exports (no per-domain list)
        "quality_refdoms_count": None,

        # Organic keywords
        "organic_keywords_total": pdf.get("organic_keywords_total"),
        "organic_keywords_change": pdf.get("organic_keywords_change"),
        "top_3_keywords": pdf.get("top_3_keywords"),
        "top_3_keywords_change": pdf.get("top_3_keywords_change"),

        # Organic traffic + value
        "organic_traffic": pdf.get("organic_traffic") or org.get("organic_traffic"),
        "organic_traffic_change": pdf.get("organic_traffic_change"),
        "organic_traffic_wow_pct": organic_traffic_wow_pct,
        "organic_traffic_value": pdf.get("organic_traffic_value") or org.get("organic_traffic_value"),
        "organic_traffic_value_change": pdf.get("organic_traffic_value_change"),
        "organic_value_wow_pct": organic_value_wow_pct,
        # Per-week derivation (organic_traffic_value is monthly; / 4.3 ≈ weekly)
        "organic_value_per_week": round((pdf.get("organic_traffic_value") or 0) / 4.3) if pdf.get("organic_traffic_value") else None,

        # Impressions + pages
        "impressions": org.get("impressions"),
        "organic_pages": org.get("organic_pages") or org_mo.get("organic_pages_monthly"),

        # Position buckets (CURRENT, from organic_serp CSV last row)
        "position_buckets": org.get("position_buckets") or {},

        # SERP features owned
        "serp_features_owned": org.get("serp_features_owned") or {},

        # Brand/intent splits
        "brand_splits": brand.get("brand_splits") or {},
        "intent_splits": brand.get("intent_splits") or {},

        # Paid (from PDF — most reliable)
        "paid_keywords": pdf.get("paid_keywords"),
        "paid_traffic": pdf.get("paid_traffic"),
        "paid_cost": pdf.get("paid_cost"),
        "paid_keywords_change": pdf.get("paid_keywords_change"),
        "paid_traffic_change": pdf.get("paid_traffic_change"),

        # History arrays for trend charts (last 30 days)
        "position_history": pos_hist,
        "keyword_history": kw_hist,

        # Competitor intel
        "competitor_wow": comp_wow,        # 5-6 rows of WoW comparison
        "competitors_matrix": comp_mx,     # current snapshot of competitor matrix

        # Lists not available from CSV exports (would need backlinks-subdomains CSV)
        "top_pages": None,
        "referring_domains": None,
        "recent_backlinks": None,
        "broken_backlinks": None,
        "anchors": None,
        "keyword_gap": None,
        "site_audit": None,

        # Fields the dashboard SEO render expects (preserved from frozen 1 Jun shape)
        "organic_value_vs_paid_multiple": None,
        "paid_spend_per_week": pdf.get("paid_cost"),
    }


def write_outputs(data):
    """Write rich ahrefs-data.json + dated snapshot."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Rich format (read by bake-dashboard, work-queue emitters)
    OUT_RICH_FILE.write_text(json.dumps(data, indent=2, default=str))
    print(f"✅ {OUT_RICH_FILE.relative_to(BASE_DIR)}")

    # 2. Dated snapshot (read by inject-seo-extras)
    snapshot_date = data["_meta"]["as_of_date"]
    snapshot_file = STATE_DIR / f"ahrefs-snapshot-{snapshot_date}.json"
    snapshot_file.write_text(json.dumps(data, indent=2, default=str))
    print(f"✅ {snapshot_file.relative_to(BASE_DIR)}")


def main():
    print(f"[parse-cb247-ahrefs] reading {INBOX_DIR.relative_to(BASE_DIR)}/")
    if not INBOX_DIR.exists():
        print(f"[parse-cb247-ahrefs] inbox missing — skipping (drop Ahrefs CSV+PDF exports into {INBOX_DIR} to enable)")
        return 0
    files = list(INBOX_DIR.glob("*.csv")) + list(INBOX_DIR.glob("*.pdf"))
    if not files:
        print(f"[parse-cb247-ahrefs] no files in inbox — skipping (this is the safe no-op case)")
        return 0

    # Idempotency guard: if state/ahrefs-data.json is NEWER than the newest
    # inbox file, the inbox hasn't changed since the last parse — skip to avoid
    # clobbering a fresher pull_ahrefs.py API result that may have run after.
    if OUT_RICH_FILE.exists():
        try:
            newest_inbox = max(f.stat().st_mtime for f in files)
            state_mtime = OUT_RICH_FILE.stat().st_mtime
            if state_mtime > newest_inbox + 60:   # 60s grace
                print(f"[parse-cb247-ahrefs] state/ahrefs-data.json newer than inbox — skipping")
                print(f"   (Drop fresh CSVs to re-trigger; or rm state/ahrefs-data.json to force.)")
                return 0
        except Exception:
            pass

    print(f"   found {len(files)} files — parsing")

    data = build_rich_data()
    write_outputs(data)

    # Headline summary so you can sanity-check the parse
    def _d(k, default="—"):
        v = data.get(k)
        return default if v is None else v

    def _delta(k):
        v = data.get(k)
        if v is None:
            return ""
        return f" ({'+' if v >= 0 else ''}{v})"

    print(f"\n📊 Headline KPIs (as of {data['_meta']['as_of_date']}):")
    print(f"   DR:                {_d('domain_rating')}  / target {_d('domain_rating_target')}")
    print(f"   UR:                {_d('url_rating')}")
    print(f"   Organic keywords:  {_d('organic_keywords_total')}{_delta('organic_keywords_change')}")
    print(f"   Top-3 keywords:    {_d('top_3_keywords')}{_delta('top_3_keywords_change')}")
    print(f"   Referring domains: {_d('total_refdoms')}{_delta('refdoms_change_pdf')}")
    print(f"   Organic traffic:   {_d('organic_traffic')}/mo")
    print(f"   Organic value:     ${_d('organic_traffic_value')}/mo  (~${_d('organic_value_per_week')}/wk)")
    print(f"   Backlinks total:   {_d('backlinks_total')}")
    print(f"   Paid traffic/$:    {_d('paid_traffic')} traffic / ${_d('paid_cost')} cost")
    print(f"   Competitor WoW:    {len(data['competitor_wow'])} competitors tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
