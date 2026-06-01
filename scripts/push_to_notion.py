"""
push_to_notion.py — Pushes CB247 performance data and SEO actions to Notion.

Creates/updates a Notion workspace with:
  📊 Weekly Performance  — Google Ads KPIs, SEO summary, domain health
  ✅ Action Tracker      — SEO tasks, technical tasks, ad actions (database)
  🔍 SEO Deliverables   — Status of all outputs/seo/ files
  📋 Team Briefings      — Meeting notes home (populated by /meeting commands)

SETUP (one-time, ~5 minutes):
  1. Go to: https://www.notion.so/my-integrations
     → New integration → Name: "CB247 Marketing Agent" → Submit
     → Copy "Internal Integration Token" → it's already in .env as NOTION_API_KEY ✅

  2. In Notion, create a page called "CB247 Marketing Hub"
     → Click "..." → Add connections → select "CB247 Marketing Agent"

  3. Copy the page ID from the URL:
     notion.so/CB247-Marketing-Hub-<THIS-PART-IS-THE-ID>
     → Add to .env: NOTION_PARENT_PAGE_ID=<paste-id-here>

  4. Run: python3 scripts/push_to_notion.py --setup
     → Creates all sub-pages and saves IDs to state/notion-ids.json

  5. Future runs (automated every Monday): python3 scripts/push_to_notion.py
     → Runs automatically at the end of weekly-report.sh
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

try:
    import requests
except ImportError:
    print("[Notion] requests not installed. Run: pip install requests")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
STATE_DIR = BASE_DIR / "state"
OUTPUTS_SEO_DIR = BASE_DIR / "outputs" / "seo"
NOTION_IDS_FILE = STATE_DIR / "notion-ids.json"

NOTION_API_KEY       = os.getenv("NOTION_API_KEY", "")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")
NOTION_VERSION       = "2022-06-28"
NOTION_BASE          = "https://api.notion.com/v1"


# =============================================================================
# Notion API Client
# =============================================================================

class NotionClient:
    def __init__(self, token):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    def _req(self, method, endpoint, body=None, retries=3):
        url = f"{NOTION_BASE}/{endpoint}"
        for attempt in range(retries):
            try:
                r = getattr(requests, method)(url, headers=self.headers, json=body, timeout=30)
                if r.status_code == 429:
                    wait = int(r.headers.get("Retry-After", 3))
                    print(f"[Notion] Rate limited — waiting {wait}s...")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except requests.HTTPError:
                if attempt == retries - 1:
                    print(f"[Notion] API error {r.status_code}: {r.text[:300]}")
                    raise
                time.sleep(1 + attempt)
        raise RuntimeError("[Notion] Max retries exceeded")

    def create_page(self, parent_id, title, children=None, icon="📊", is_db_item=False):
        parent_key = "database_id" if is_db_item else "page_id"
        body = {
            "parent": {parent_key: parent_id},
            "icon": {"type": "emoji", "emoji": icon},
            "properties": {
                "title": {"title": [{"text": {"content": title}}]}
            },
        }
        if children:
            body["children"] = children[:100]
        result = self._req("post", "pages", body)
        # Append remaining blocks if more than 100
        if children and len(children) > 100:
            time.sleep(0.3)
            self.append_blocks(result["id"], children[100:])
        return result

    def get_blocks(self, block_id):
        """Get all child blocks of a page or block."""
        results = []
        cursor = None
        while True:
            qs = "?page_size=100"
            if cursor:
                qs += f"&start_cursor={cursor}"
            resp = self._req("get", f"blocks/{block_id}/children{qs}")
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return results

    def delete_block(self, block_id):
        return self._req("delete", f"blocks/{block_id}")

    def clear_page(self, page_id):
        """Delete all blocks on a page (clean overwrite)."""
        blocks = self.get_blocks(page_id)
        for block in blocks:
            try:
                self.delete_block(block["id"])
                time.sleep(0.08)
            except Exception:
                pass

    def append_blocks(self, block_id, children):
        """Append blocks in batches of 100 (Notion API limit)."""
        for i in range(0, len(children), 100):
            batch = children[i:i + 100]
            self._req("patch", f"blocks/{block_id}/children", {"children": batch})
            if i + 100 < len(children):
                time.sleep(0.3)

    def create_database(self, parent_id, title, properties, icon="✅"):
        body = {
            "parent": {"page_id": parent_id},
            "icon": {"type": "emoji", "emoji": icon},
            "title": [{"text": {"content": title}}],
            "properties": properties,
        }
        return self._req("post", "databases", body)

    def query_database(self, db_id):
        results = []
        cursor = None
        while True:
            body = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            resp = self._req("post", f"databases/{db_id}/query", body)
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return results

    def create_db_item(self, db_id, properties, children=None):
        body = {"parent": {"database_id": db_id}, "properties": properties}
        if children:
            body["children"] = children[:100]
        return self._req("post", "pages", body)

    def update_page_icon(self, page_id, emoji):
        return self._req("patch", f"pages/{page_id}", {"icon": {"type": "emoji", "emoji": emoji}})


# =============================================================================
# Block Builders
# =============================================================================

def rt(text, bold=False, italic=False, color="default"):
    return {
        "type": "text",
        "text": {"content": str(text)[:2000]},
        "annotations": {"bold": bold, "italic": italic, "color": color},
    }

def h1(text):
    return {"object": "block", "type": "heading_1",
            "heading_1": {"rich_text": [rt(text)]}}

def h2(text):
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [rt(text)]}}

def h3(text):
    return {"object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [rt(text)]}}

def para(text, bold=False):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [rt(text, bold=bold)] if text else []}}

def bullet(text, bold=False):
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [rt(text, bold=bold)]}}

def divider():
    return {"object": "block", "type": "divider", "divider": {}}

def callout(text, icon="💡", color="blue_background"):
    return {
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": [rt(text)],
            "icon": {"type": "emoji", "emoji": icon},
            "color": color,
        }
    }

def todo(text, checked=False):
    return {
        "object": "block", "type": "to_do",
        "to_do": {"rich_text": [rt(text)], "checked": checked},
    }

def quote(text):
    return {"object": "block", "type": "quote",
            "quote": {"rich_text": [rt(text)]}}

def column_list(columns):
    """columns: list of lists — each inner list is the blocks for one column."""
    return {
        "object": "block",
        "type": "column_list",
        "column_list": {
            "children": [
                {"object": "block", "type": "column", "column": {"children": col}}
                for col in columns
            ]
        }
    }


# =============================================================================
# Content Builders
# =============================================================================

def pct_change(a, b):
    if not b:
        return "n/a"
    ch = ((a - b) / b) * 100
    arrow = "↑" if ch > 0 else "↓"
    return f"{arrow} {abs(ch):.1f}%"


def build_weekly_report_page_blocks(ga4, gsc, ads_data, apify=None):
    """Full weekly marketing report — dashboard layout with columns."""
    today = datetime.utcnow().strftime("%d %B %Y")
    gads_list   = (ads_data.get("google_ads") or []) if ads_data else []
    meta_list   = (ads_data.get("meta_ads")   or []) if ads_data else []
    latest_ads  = gads_list[0] if gads_list else {}
    prev_ads    = gads_list[1] if len(gads_list) > 1 else {}
    latest_meta = meta_list[0] if meta_list else {}
    prev_meta   = meta_list[1] if len(meta_list) > 1 else {}

    ga4_dr    = (ga4.get("date_range") or {}) if ga4 else {}
    ga4_start = ga4_dr.get("start", "?")
    ga4_end   = ga4_dr.get("end",   "?")
    gsc_dr    = (gsc.get("date_range") or {}) if gsc else {}
    gsc_start = gsc_dr.get("start", "?")
    gsc_end   = gsc_dr.get("end",   "?")

    ga4_c = (ga4.get("current")  or {}) if ga4 else {}
    ga4_p = (ga4.get("previous") or {}) if ga4 else {}
    sessions    = int(ga4_c.get("sessions",    0) or 0)
    p_sessions  = int(ga4_p.get("sessions",    0) or 0)
    convs       = int(ga4_c.get("conversions", 0) or 0)
    p_convs     = int(ga4_p.get("conversions", 0) or 0)
    users       = int(ga4_c.get("users",       0) or 0)
    new_users   = int(ga4_c.get("new_users",   0) or 0)
    p_users     = int(ga4_p.get("users",       0) or 0)
    conv_rate   = convs / sessions * 100 if sessions else 0
    p_conv_rate = p_convs / p_sessions * 100 if p_sessions else 0

    combined   = latest_ads.get("combined", {}) or {}
    p_combined = prev_ads.get("combined",   {}) or {}
    ads_spend  = combined.get("spend", 0)
    ads_cpa    = combined.get("cpa",   0)
    malaga_cpa     = (latest_ads.get("malaga",     {}) or {}).get("cpa", 0)
    ellenbrook_cpa = (latest_ads.get("ellenbrook", {}) or {}).get("cpa", 0)

    devices      = ga4.get("devices", []) if ga4 else []
    mob_sessions = next((int(d.get("sessions", 0) or 0) for d in devices if d.get("deviceCategory") == "mobile"), 0)
    mob_share    = mob_sessions / sessions * 100 if sessions else 0

    gsc_sum = (gsc.get("summary") or {}) if gsc else {}
    gsc_pos = gsc_sum.get("avg_position", 0) or 0
    gsc_ctr = gsc_sum.get("avg_ctr",      0) or 0

    blocks = []

    # ─────────────────────────────────────────────────────────────────────
    # HEADER
    # ─────────────────────────────────────────────────────────────────────
    blocks.append(callout(
        f"📅 Report period: {ga4_start} → {ga4_end}  |  Generated: {today}  |  Auto-updated every Monday",
        "🤖", "gray_background"
    ))
    blocks.append(divider())

    # ═════════════════════════════════════════════════════════════════════
    # 1. EXECUTIVE SUMMARY  (2-column: KPI snapshot | Worked + Attention)
    # ═════════════════════════════════════════════════════════════════════
    blocks.append(h1("📋 Executive Summary"))

    left_exec = [
        h3("🎯 KPI Snapshot"),
        bullet(f"Sessions:    {sessions:,}  ({pct_change(sessions, p_sessions)} WoW)"),
        bullet(f"Conversions: {convs}  ({pct_change(convs, p_convs)} WoW)"),
        bullet(f"Conv. Rate:  {conv_rate:.1f}%  (prior: {p_conv_rate:.1f}%)"),
        bullet(f"Mobile:      {mob_share:.0f}% of sessions"),
        para(""),
        h3("💰 Paid Ads Snapshot"),
        bullet(f"Google Spend:  ${ads_spend:.2f}"),
        bullet(f"Blended CPA:   ${ads_cpa:.2f}"),
        bullet(f"Malaga CPA:    ${malaga_cpa:.2f}{'  ⚠️' if malaga_cpa > 50 else '  ✅'}"),
        bullet(f"Ellenbrook CPA: ${ellenbrook_cpa:.2f}{'  ⚠️' if ellenbrook_cpa > 50 else '  ✅'}"),
    ]

    right_exec = [
        h3("✅ What Worked"),
        bullet("Organic search dominant — 35%+ of sessions"),
        bullet("Direct traffic converts strongly — brand recall holding"),
        bullet("Reformer Pilates top non-homepage destination"),
        para(""),
        h3("⚠️ Needs Attention"),
        bullet(f"Sessions {pct_change(sessions, p_sessions)} WoW — review paid channels"),
        bullet(f"Malaga CPA ${malaga_cpa:.2f} vs Ellenbrook ${ellenbrook_cpa:.2f}"),
        bullet("Mobile 82%+ — confirm Pilates + Contact UX mobile-ready"),
        para(""),
        h3("→ Actions"),
        bullet("Shift Google Ads budget to lower-CPA location"),
        bullet("Audit Reformer Pilates + Contact page on mobile"),
        bullet("Print QR review cards — brief front desk today"),
    ]

    blocks.append(column_list([left_exec, right_exec]))
    blocks.append(divider())

    # ═════════════════════════════════════════════════════════════════════
    # 2. GA4 + GSC  (2-column side by side)
    # ═════════════════════════════════════════════════════════════════════
    left_ga4 = [
        h2("📊 Google Analytics 4"),
        para(f"Period: {ga4_start} → {ga4_end}"),
        para(""),
        bullet(f"Sessions:    {sessions:,}  ({pct_change(sessions, p_sessions)})"),
        bullet(f"Users:       {users:,}  ({pct_change(users, p_users)})"),
        bullet(f"New Users:   {new_users:,}"),
        bullet(f"Conversions: {convs}  ({pct_change(convs, p_convs)})"),
        bullet(f"Conv. Rate:  {conv_rate:.1f}%"),
        bullet(f"Mobile:      {mob_share:.0f}% of sessions"),
    ]

    sources = (ga4.get("traffic_sources") or []) if ga4 else []
    total_s = sessions or 1
    if sources:
        left_ga4.append(para(""))
        left_ga4.append(h3("Traffic by Channel"))
        for src in sources[:6]:
            name  = src.get("sessionDefaultChannelGroup", "")
            s_val = int(src.get("sessions", 0) or 0)
            pct   = round(s_val / total_s * 100, 1)
            left_ga4.append(bullet(f"{name}  —  {pct}%  ({s_val:,})"))

    if gsc and gsc_sum:
        right_gsc = [
            h2("🔍 Search Console"),
            para(f"Period: {gsc_start} → {gsc_end}"),
            para(""),
            bullet(f"Clicks:      {gsc_sum.get('total_clicks', 0):,}"),
            bullet(f"Impressions: {gsc_sum.get('total_impressions', 0):,}"),
            bullet(f"Avg CTR:     {gsc_ctr * 100:.2f}%"),
            bullet(f"Avg Position: #{gsc_pos:.1f}"),
        ]
        top_q = (gsc.get("top_queries") or [])[:8]
        if top_q:
            right_gsc.append(para(""))
            right_gsc.append(h3("Top Queries"))
            for i, q in enumerate(top_q, 1):
                right_gsc.append(bullet(
                    f"#{i}  {q.get('query','')[:38]}  —  "
                    f"{q.get('clicks',0)} clicks  pos #{q.get('position',0):.1f}"
                ))
    else:
        right_gsc = [
            h2("🔍 Search Console"),
            para("No GSC data — run: python3 scripts/pull_gsc.py"),
        ]

    blocks.append(column_list([left_ga4, right_gsc]))

    # Top 10 pages (full width — too wide for columns)
    top_pages = (ga4.get("top_pages") or []) if ga4 else []
    if top_pages:
        blocks.append(para(""))
        blocks.append(h3("📄 Top Pages"))
        for i, pg in enumerate(top_pages[:10], 1):
            path  = pg.get("pagePath", "")
            views = int(pg.get("screenPageViews", 0) or 0)
            sess  = int(pg.get("sessions",        0) or 0)
            blocks.append(bullet(f"#{i}  {path}  —  {views:,} views  |  {sess:,} sessions"))

    blocks.append(divider())

    # ═════════════════════════════════════════════════════════════════════
    # 3. GOOGLE ADS  (combined header + 2-col Malaga | Ellenbrook)
    # ═════════════════════════════════════════════════════════════════════
    blocks.append(h1("📈 Google Ads — Paid Search"))

    if latest_ads:
        w_label    = latest_ads.get("week_label", "")
        p_spend    = p_combined.get("spend", 0)
        p_clicks   = int(p_combined.get("clicks", 0))
        clicks     = int(combined.get("clicks", 0))
        cpc        = combined.get("cpc", 0)
        ad_convs   = int(combined.get("conv", 0))
        p_ad_convs = int(p_combined.get("conv", 0))

        # Combined summary callout
        blocks.append(callout(
            f"Week: {w_label}  |  Spend: ${ads_spend:.2f} ({pct_change(ads_spend, p_spend)} WoW)  |  "
            f"Clicks: {clicks:,} ({pct_change(clicks, p_clicks)} WoW)  |  "
            f"Conv: {ad_convs} ({pct_change(ad_convs, p_ad_convs)} WoW)  |  "
            f"CPC: ${cpc:.2f}  |  CPA: ${ads_cpa:.2f}",
            "📈", "blue_background"
        ))
        blocks.append(para(""))

        # Malaga | Ellenbrook side by side
        def loc_col(loc_key, emoji):
            d = (latest_ads.get(loc_key) or {})
            p = (prev_ads.get(loc_key)   or {})
            if not d:
                return [h3(f"{emoji} {loc_key.title()}"), para("No data")]
            loc_cpa  = d.get("cpa", 0)
            cpa_flag = "  ⚠️ HIGH" if loc_cpa > 50 else "  ✅"
            return [
                h3(f"{emoji} {loc_key.title()}"),
                bullet(f"Spend:   ${d.get('spend',0):.2f}  (prior: ${p.get('spend',0):.2f})"),
                bullet(f"Clicks:  {int(d.get('clicks',0)):,}  |  CTR: {d.get('ctr',0):.2f}%"),
                bullet(f"Conv.:   {int(d.get('conv',0))}  |  CPA: ${loc_cpa:.2f}{cpa_flag}"),
            ]

        blocks.append(column_list([loc_col("malaga", "🟢"), loc_col("ellenbrook", "🔵")]))
        blocks.append(para(""))

        # 3-week trend
        blocks.append(h3("📅 3-Week Spend Trend"))
        for i, week in enumerate(gads_list[:3]):
            c     = week.get("combined", {}) or {}
            label = ("← This week  " if i == 0 else f"  -{i} week    ") + week.get("week_label", "")
            blocks.append(bullet(
                f"{label}  |  ${c.get('spend',0):.2f}  |  "
                f"{int(c.get('clicks',0)):,} clicks  |  "
                f"{int(c.get('conv',0))} conv  |  "
                f"CPA ${c.get('cpa',0):.2f}"
            ))

        # Campaign breakdown
        campaigns = latest_ads.get("campaigns", [])
        if campaigns:
            blocks.append(para(""))
            blocks.append(h3("Campaign Breakdown"))
            for c in campaigns[:8]:
                cpa_f = "  ⚠️" if c.get("cpa", 0) > 50 else ""
                blocks.append(bullet(
                    f"{c.get('name','—')[:42]}  |  "
                    f"${c.get('spend',0):.2f}  |  "
                    f"{int(c.get('clicks',0))} clicks  |  "
                    f"{int(c.get('conv',0))} conv  |  "
                    f"CPA ${c.get('cpa',0):.2f}{cpa_f}"
                ))
    else:
        blocks.append(para("No Google Ads data — run: python3 scripts/pull_google_ads.py"))
    blocks.append(divider())

    # ═════════════════════════════════════════════════════════════════════
    # 4. META ADS
    # ═════════════════════════════════════════════════════════════════════
    blocks.append(h1("📘 Meta Ads — Paid Social"))
    if latest_meta and (latest_meta.get("combined", {}) or {}).get("spend", 0) > 0:
        meta_combined   = latest_meta.get("combined", {}) or {}
        p_meta_combined = prev_meta.get("combined",   {}) or {}
        m_spend   = meta_combined.get("spend",  0)
        p_m_spend = p_meta_combined.get("spend", 0)
        m_impr    = int(meta_combined.get("impr",   0) or 0)
        m_reach   = int(meta_combined.get("reach",  0) or 0)
        m_clicks  = int(meta_combined.get("clicks", 0) or 0)
        m_ctr     = meta_combined.get("ctr", 0)

        blocks.append(callout(
            f"Week: {latest_meta.get('week_label','')}  |  Spend: ${m_spend:.2f} ({pct_change(m_spend, p_m_spend)} WoW)  |  "
            f"Impressions: {m_impr:,}  |  Reach: {m_reach/1000:.1f}K  |  Clicks: {m_clicks:,}  |  CTR: {m_ctr:.2f}%",
            "📘", "blue_background"
        ))

        meta_cols = []
        for loc in ["malaga", "ellenbrook"]:
            d = (latest_meta.get(loc) or {})
            if not d:
                continue
            emoji = "🟢" if loc == "malaga" else "🔵"
            meta_cols.append([
                h3(f"{emoji} Meta {loc.title()}"),
                bullet(f"Spend: ${d.get('spend',0):.2f}  |  CPM: ${d.get('cpm',0):.2f}  |  CPC: ${d.get('cpc',0):.2f}"),
                bullet(f"Impressions: {int(d.get('impr',0) or 0):,}  |  Reach: {int(d.get('reach',0) or 0):,}  |  Clicks: {int(d.get('clicks',0) or 0):,}"),
            ])
        if meta_cols:
            blocks.append(para(""))
            blocks.append(column_list(meta_cols))
    else:
        blocks.append(callout(
            "⚠️ Meta Ads account currently suspended — appeal lodged. "
            "Once reinstated: add META_ACCESS_TOKEN to .env → run python3 scripts/pull_meta.py",
            "📘", "yellow_background"
        ))
    blocks.append(divider())

    # ═════════════════════════════════════════════════════════════════════
    # 5. GBP LOCAL VISIBILITY  (2-col Malaga | Ellenbrook + strategy)
    # ═════════════════════════════════════════════════════════════════════
    blocks.append(h1("📍 Google Business Profile — Local Visibility"))

    if apify:
        targets     = apify.get("competitor_maps", {}).get("targets", [])
        competitors = apify.get("competitor_maps", {}).get("competitors", [])
        malaga_gbp  = next((t for t in targets if t.get("location") == "Malaga"),     {})
        ell_gbp     = next((t for t in targets if t.get("location") == "Ellenbrook"), {})

        left_gbp = [
            h3("🟢 Malaga"),
            bullet(f"⭐ Rating:   {malaga_gbp.get('rating','—')}"),
            bullet(f"💬 Reviews:  {malaga_gbp.get('reviews','—')}  (target: 530+)"),
            bullet(f"📸 Photos:   {malaga_gbp.get('photos','—')}  (target: 100+)"),
            bullet(f"✅ Profile:  {malaga_gbp.get('completeness_score','—')}% complete"),
        ]
        right_gbp = [
            h3("🔵 Ellenbrook"),
            bullet(f"⭐ Rating:   {ell_gbp.get('rating','—')}"),
            bullet(f"💬 Reviews:  {ell_gbp.get('reviews','—')}  (target: 280+)"),
            bullet(f"📸 Photos:   {ell_gbp.get('photos','—')}  (target: 100+)"),
            bullet(f"✅ Profile:  {ell_gbp.get('completeness_score','—')}% complete"),
        ]
        blocks.append(column_list([left_gbp, right_gbp]))

        if competitors:
            blocks.append(para(""))
            blocks.append(h3("Competitor Benchmarking"))
            for c in competitors[:6]:
                name    = (c.get("title") or c.get("query","—"))[:35]
                loc     = c.get("location","—")
                rating  = c.get("rating","—")
                reviews = c.get("reviews","—")
                blocks.append(bullet(f"{name} ({loc})  —  ⭐ {rating}  |  {reviews} reviews"))
    else:
        blocks.append(para("GBP data not available — run: python3 scripts/pull_apify.py"))

    blocks.append(para(""))
    blocks.append(callout(
        "🏆 CB247 leads Revo 3.5× on reviews (469 vs 134). "
        "Highest-ROI zero-cost action this week: print QR code review cards and brief front desk.",
        "🏆", "green_background"
    ))
    blocks.append(para(""))

    # GBP Strategy — 2 columns: Levers 1+2 left, Levers 3+4 right
    left_strat = [
        h3("Lever 1 — Review Velocity 🔥"),
        todo("Print QR code review cards (A5) — Malaga + Ellenbrook reception"),
        todo("Brief front desk on verbal review ask script"),
        todo("Set up WhatsApp template for new member 24hr follow-up"),
        todo("Add review link to monthly email newsletter footer"),
        todo("Respond to every new review within 24 hours"),
        para(""),
        h3("Lever 2 — Weekly GBP Posts (Tuesdays)"),
        todo("W1: $11.95/wk value vs competitors"),
        todo("W2: Sauna + ice bath feature spotlight"),
        todo("W3: Member challenge / community event"),
        todo("W4: Referral deal or new member promo"),
    ]
    right_strat = [
        h3("Lever 3 — Photo Strategy (10/month)"),
        todo("Upload: ice bath + sauna in use — unique differentiator"),
        todo("Upload: Kids Hub — children + smiling staff"),
        todo("Upload: wide gym floor shots — counter gymtimidation"),
        para(""),
        h3("Lever 4 — Profile Optimisation"),
        todo("Rewrite GBP descriptions with local keywords"),
        todo("Add services: Sauna, Ice Bath, Pilates, Kids Hub, FIFO Freeze"),
        todo("Seed Q&A with 6 pre-answered questions (incl. cancellation)"),
        todo("Verify 'Book' button → sign-up page (not homepage)"),
        para(""),
        h3("90-Day Targets"),
        bullet("Malaga reviews:    469 → 530+"),
        bullet("Ellenbrook reviews: 226 → 280+"),
        bullet("Photos each: 65/68 → 100+"),
        bullet("GBP views + clicks: +20% MoM"),
    ]
    blocks.append(column_list([left_strat, right_strat]))
    blocks.append(divider())

    # ═════════════════════════════════════════════════════════════════════
    # 6. KEY INSIGHTS  (2-column callout grid)
    # ═════════════════════════════════════════════════════════════════════
    blocks.append(h1("💡 Key Insights & Actions"))

    insights = [
        ("🔴 Google Ads Manager",
         f"Malaga CPA at ${malaga_cpa:.2f}",
         f"{'Elevated — compare with' if malaga_cpa > 50 else 'Monitor vs'} Ellenbrook (${ellenbrook_cpa:.2f}). Review audience + creative.",
         "red_background"),
        ("🟡 SEO Specialist",
         f"Sessions {pct_change(sessions, p_sessions)} WoW",
         "Investigate paid channel performance and cross-network attribution.",
         "yellow_background"),
        ("🟢 SEO Specialist",
         f"Organic at position #{gsc_pos:.1f}",
         f"CTR: {gsc_ctr*100:.1f}%. Protect with GBP optimisation and fresh content.",
         "green_background"),
        ("🟢 Google Ads Manager",
         "Direct Traffic Converts at 47%",
         "Strong brand recall — amplify awareness to grow this segment.",
         "green_background"),
        ("🟡 Developer",
         "Mobile UX Critical — 82% of Sessions",
         "Pilates and Contact pages are top conversion paths. Test on mobile now.",
         "yellow_background"),
        ("🟡 Content Creator",
         "Sauna + Ice Bath Invisible in Search",
         "Key differentiator not in top pages. Build dedicated landing page + SEO content.",
         "yellow_background"),
        ("🟢 Front Desk",
         "GBP Review Lead — Extend It",
         "3.5× ahead of Revo. QR code cards + verbal ask = $0 cost per review.",
         "green_background"),
        ("🟢 Content Creator",
         "GBP Posts Not Yet Active",
         "Free ranking signal. Schedule Tuesday posts: value → sauna → challenge → promo.",
         "green_background"),
    ]

    # Split into two columns of 4
    left_ins  = []
    right_ins = []
    for i, (tag, title, desc, color) in enumerate(insights):
        block = callout(f"{tag}  |  {title}\n{desc}", "💡", color)
        if i % 2 == 0:
            left_ins.append(block)
            left_ins.append(para(""))
        else:
            right_ins.append(block)
            right_ins.append(para(""))

    blocks.append(column_list([left_ins, right_ins]))
    blocks.append(divider())
    blocks.append(para(f"CB247 Marketing Report  |  Generated: {today}  |  Contact: tia@chasingbetter.com.au"))

    return blocks


def build_weekly_performance_blocks(ga4, gsc, gads):
    """Builds Notion blocks for the Weekly Performance page."""
    today = datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")
    blocks = []

    # Header
    blocks.append(callout(f"Auto-updated: {today}  |  CB247 Marketing Agent", "🤖", "gray_background"))
    blocks.append(divider())

    # ── GOOGLE ADS ─────────────────────────────────────────────────────────
    blocks.append(h2("📈 Google Ads — Last 7 Days"))

    if gads and gads.get("totals"):
        totals   = gads["totals"]
        accounts = gads.get("accounts", {})
        dr       = gads.get("date_range", {})

        blocks.append(para(f"Period: {dr.get('start','?')} → {dr.get('end','?')}"))
        blocks.append(para(""))

        spend = totals.get("spend", 0)
        blocks.append(bullet(f"💰  Total Spend: ${spend:,.2f}/week  (~${spend * 4.33:,.0f}/month estimated)", bold=True))
        blocks.append(bullet(f"🔄  Total Conversions: {totals.get('conversions', 0):.0f}"))
        blocks.append(bullet(f"👆  Total Clicks: {totals.get('clicks', 0):,}"))
        blocks.append(bullet(f"📉  Avg CPL: ${totals.get('cpl', 0):.2f}   (target: $20.00)"))
        blocks.append(para(""))

        for loc in ["Malaga", "Ellenbrook"]:
            if loc not in accounts:
                continue
            a = accounts[loc]
            cpl = a.get("cpl", 0)
            flag = "  ⚠️ over target" if cpl > 20 else "  ✅"
            blocks.append(h3(loc))
            blocks.append(bullet(f"Spend: ${a.get('spend', 0):.2f}  |  Clicks: {a.get('clicks', 0):,}  |  Conversions: {a.get('conversions', 0):.0f}"))
            blocks.append(bullet(f"CPL: ${cpl:.2f}{flag}"))

        # Best and worst campaigns
        live = [c for c in gads.get("campaigns", []) if c.get("spend", 0) > 0 and c.get("status") == "ENABLED"]
        if live:
            best = min(live, key=lambda x: x["spend"] / max(x.get("conversions", 0.001), 0.001))
            worst = max(live, key=lambda x: x["spend"] / max(x.get("conversions", 0.001), 0.001))
            best_cpl  = best["spend"] / max(best.get("conversions", 0.001), 0.001)
            worst_cpl = worst["spend"] / max(worst.get("conversions", 0.001), 0.001)
            blocks.append(para(""))
            blocks.append(callout(
                f"⭐ Best: {best['name']} ({best['location']}) — ${best_cpl:.2f} CPL  |  "
                f"⚠️ Watch: {worst['name']} ({worst['location']}) — ${worst_cpl:.2f} CPL",
                "📊", "green_background" if worst_cpl <= 20 else "yellow_background"
            ))
    else:
        blocks.append(para("No data — run: python3 scripts/pull_google_ads.py"))

    blocks.append(divider())

    # ── SEO / GSC ──────────────────────────────────────────────────────────
    blocks.append(h2("🔍 SEO — Google Search Console"))

    if gsc and gsc.get("summary"):
        s  = gsc["summary"]
        dr = gsc.get("date_range", {})
        blocks.append(para(f"Period: {dr.get('start','?')} → {dr.get('end','?')}"))
        blocks.append(para(""))
        blocks.append(bullet(f"🖱️  Organic Clicks: {s.get('total_clicks', 0):,}"))
        blocks.append(bullet(f"👁️  Impressions: {s.get('total_impressions', 0):,}"))
        blocks.append(bullet(f"📊  Avg CTR: {s.get('avg_ctr', 0) * 100:.1f}%"))
        blocks.append(bullet(f"📍  Avg Position: #{s.get('avg_position', 0):.1f}"))
        blocks.append(para(""))

        top_q = gsc.get("top_queries", [])[:5]
        if top_q:
            blocks.append(h3("Top 5 Queries"))
            for q in top_q:
                blocks.append(bullet(
                    f"{q.get('query','')}  →  {q.get('clicks',0)} clicks @ #{q.get('position',0):.1f}"
                ))

        # Brand dependency warning
        all_q     = gsc.get("top_queries", [])
        nb_clicks = sum(q.get("clicks", 0) for q in all_q
                        if "chasing" not in q.get("query", "").lower())
        total_cl  = s.get("total_clicks", 1)
        brand_pct = 100 - (nb_clicks / max(total_cl, 1) * 100)
        blocks.append(para(""))
        blocks.append(callout(
            f"⚠️ {brand_pct:.0f}% of organic clicks are brand-name searches. "
            f"Non-brand organic traffic: only {nb_clicks} clicks/week. "
            f"Goal: rank #1–3 for 'gym malaga' & 'gym ellenbrook' to break this dependency.",
            "📊", "yellow_background"
        ))
    else:
        blocks.append(para("No data — run: python3 scripts/pull_gsc.py"))

    blocks.append(divider())

    # ── DOMAIN HEALTH ──────────────────────────────────────────────────────
    blocks.append(h2("🏥 Domain Health"))
    blocks.append(bullet("Domain Rating (Ahrefs): 7 / 100  — target 20+ within 6 months"))
    blocks.append(bullet("Toxic backlinks: 37 domains detected (seoexpress.store & seo-anomaly.xyz)"))
    blocks.append(bullet("Disavow file: Ready → outputs/seo/disavow-2026-05-30.txt — submit to GSC"))
    blocks.append(bullet("Technical issues: 3 Critical · 6 High · 2 Medium  (Screaming Frog, May 2026)"))
    blocks.append(para(""))
    blocks.append(callout(
        "Priority order: Submit disavow → Fix H1s (29 pages) → Add schema (40 pages) → Publish /ellenbrook",
        "🎯", "blue_background"
    ))
    blocks.append(divider())

    # ── GA4 ────────────────────────────────────────────────────────────────
    if ga4 and ga4.get("current"):
        blocks.append(h2("📊 GA4 — Website Traffic"))
        c = ga4["current"]
        p = ga4.get("previous", {})
        sessions   = int(c.get("sessions", 0) or 0)
        p_sessions = int(p.get("sessions", 0) or 0)
        delta = sessions - p_sessions
        arrow = "↗️" if delta > 0 else ("↘️" if delta < 0 else "➡️")
        blocks.append(bullet(f"Sessions: {sessions:,}  {arrow}  ({'+' if delta >= 0 else ''}{delta:,} vs prev week)"))
        blocks.append(bullet(f"New Users: {c.get('new_users', '—')}"))
        blocks.append(bullet(f"Conversions: {c.get('conversions', '—')}"))
        blocks.append(divider())

    # ── GBP / LOCAL ────────────────────────────────────────────────────────
    blocks.append(h2("📍 Google Business Profile — Local Visibility"))
    apify_path = STATE_DIR / "apify-data.json"
    if apify_path.exists():
        try:
            apify = json.loads(apify_path.read_text())
            targets = apify.get("competitor_maps", {}).get("targets", [])
            malaga_gbp = next((t for t in targets if t.get("location") == "Malaga"), {})
            ell_gbp    = next((t for t in targets if t.get("location") == "Ellenbrook"), {})
            blocks.append(para("Source: Apify Maps scraper — re-run monthly with: python3 scripts/pull_apify.py"))
            blocks.append(para(""))
            blocks.append(h3("Malaga"))
            blocks.append(bullet(f"⭐  Rating: {malaga_gbp.get('rating', '—')}  |  Reviews: {malaga_gbp.get('reviews', '—')}  (target: 530+)"))
            blocks.append(bullet(f"📸  Photos: {malaga_gbp.get('photos', '—')}  (target: 100+)"))
            blocks.append(bullet(f"✅  Profile complete: {malaga_gbp.get('completeness_score', '—')}%"))
            blocks.append(h3("Ellenbrook"))
            blocks.append(bullet(f"⭐  Rating: {ell_gbp.get('rating', '—')}  |  Reviews: {ell_gbp.get('reviews', '—')}  (target: 280+)"))
            blocks.append(bullet(f"📸  Photos: {ell_gbp.get('photos', '—')}  (target: 100+)"))
            blocks.append(bullet(f"✅  Profile complete: {ell_gbp.get('completeness_score', '—')}%"))
            blocks.append(para(""))
            blocks.append(callout(
                "GBP strategy: print QR code review cards → brief front desk → weekly Tuesday posts → upload 10 new photos/month. "
                "Strategy doc: outputs/strategy/gbp-visibility-strategy-2026-05-31.md",
                "📍", "green_background"
            ))
        except Exception as e:
            blocks.append(para(f"GBP data unavailable: {e} — run python3 scripts/pull_apify.py"))
    else:
        blocks.append(para("GBP data not found — run: python3 scripts/pull_apify.py"))
    blocks.append(divider())

    # ── META ADS (suspended notice) ────────────────────────────────────────
    blocks.append(h2("📘 Meta Ads — Status"))
    blocks.append(callout(
        "⚠️ Meta Ads account is currently suspended (appeal lodged). "
        "Once reinstated: go to developers.facebook.com/tools/explorer → generate token → add META_ACCESS_TOKEN to .env → run python3 scripts/pull_meta.py",
        "📘", "yellow_background"
    ))
    blocks.append(divider())

    # Footer
    blocks.append(para(f"Generated by CB247 Marketing Agent | {today}"))
    blocks.append(para("Runs every Monday via: bash scripts/weekly-report.sh"))

    return blocks


def build_seo_deliverables_blocks():
    """Builds Notion blocks listing SEO outputs with status checklist."""
    today = datetime.utcnow().strftime("%d %B %Y")
    blocks = []

    blocks.append(callout(
        f"Last updated: {today}  |  Files at: CB_Marketing/outputs/seo/  |  "
        "All items require human implementation — review each file and action in priority order.",
        "🤖", "gray_background"
    ))
    blocks.append(divider())

    deliverables = [
        {
            "file": "disavow-2026-05-30.txt",
            "title": "Submit disavow file — 37 toxic domains",
            "priority": "🔴 CRITICAL",
            "action": "Go to search.google.com/search-console/disavow-links → upload file",
        },
        {
            "file": "redirect-map-2026-05-30.md",
            "title": "Fix 3 broken pages (301 redirects)",
            "priority": "🔴 CRITICAL",
            "action": "Add redirects in CMS settings or .htaccess (10-minute task)",
        },
        {
            "file": "h1-recommendations-2026-05-30.md",
            "title": "Add H1 tags to 29 pages",
            "priority": "🔴 CRITICAL",
            "action": "Dev task — file lists exact H1 text per page",
        },
        {
            "file": "schema-local-business-2026-05-30.md",
            "title": "Add LocalBusiness + FAQ schema markup (40 pages)",
            "priority": "🟠 HIGH",
            "action": "Copy 3 JSON-LD blocks into site <head> — see file for code",
        },
        {
            "file": "page-massage-2026-05-30.md",
            "title": "Expand /massage page  (1,300 searches/month at position #16)",
            "priority": "🟠 HIGH",
            "action": "Replace thin content with full page — paste from file into CMS",
        },
        {
            "file": "page-ellenbrook-2026-05-30.md",
            "title": "Create /ellenbrook landing page  (page does not exist)",
            "priority": "🟠 HIGH",
            "action": "Build new page in CMS — saves ~$386/week in ads once ranked",
        },
        {
            "file": "page-fifo-2026-05-30.md",
            "title": "Expand /resources/fifo-members page",
            "priority": "🟡 MEDIUM",
            "action": "Replace thin content — paste from file into CMS",
        },
        {
            "file": "page-kids-hub-2026-05-30.md",
            "title": "Expand /kids-hub + fix short title tag",
            "priority": "🟡 MEDIUM",
            "action": "Fix title tag + add H1 + replace thin content",
        },
        {
            "file": "blog-best-gym-malaga-2026-05-30.md",
            "title": "Publish blog: 'Best Gym in Malaga'",
            "priority": "🟡 MEDIUM",
            "action": "Publish at /blog/best-gym-in-malaga-perth — targets 'Malaga Gym' ad keyword ($137/wk)",
        },
    ]

    blocks.append(h2("📋 SEO Action Items — Priority Order"))
    blocks.append(para("Tick items as Done. Files are in: CB_Marketing/outputs/seo/"))
    blocks.append(para(""))

    for item in deliverables:
        blocks.append(todo(f"{item['priority']}  {item['title']}"))
        blocks.append(bullet(f"File: {item['file']}"))
        blocks.append(bullet(f"Action: {item['action']}"))
        blocks.append(para(""))

    blocks.append(divider())
    blocks.append(h2("📈 Expected Impact When Complete"))
    blocks.append(bullet("'gym malaga' organic ranking: #5–6 → #1–2  (6–12 weeks after H1s + content)"))
    blocks.append(bullet("'gym ellenbrook' organic ranking: #4 → #1  (4–8 weeks after /ellenbrook page live)"))
    blocks.append(bullet("Monthly paid ad savings: ~$1,900/month when 3 campaigns replaced by organic"))
    blocks.append(bullet("Domain Rating: 7 → 15+  (3–6 months with backlink building)"))
    blocks.append(bullet("'massage open now' ranking: #16 → #3  (after massage page expansion)"))

    return blocks


def get_initial_action_items():
    """Initial set of action items to populate the Action Tracker database."""
    return [
        # SEO
        {"name": "Submit disavow file to Google Search Console",     "priority": "Critical", "category": "SEO",        "assigned": "SEO Specialist"},
        {"name": "Fix 3 broken pages — add 301 redirects",           "priority": "Critical", "category": "Technical",  "assigned": "Developer"},
        {"name": "Add H1 tags to 29 pages",                          "priority": "Critical", "category": "SEO",        "assigned": "Developer"},
        {"name": "Add LocalBusiness schema markup (40 pages)",        "priority": "High",     "category": "Technical",  "assigned": "Developer"},
        {"name": "Expand /massage page (1,300 searches/month)",       "priority": "High",     "category": "Content",    "assigned": "Content Creator"},
        {"name": "Create /ellenbrook landing page (new)",             "priority": "High",     "category": "Content",    "assigned": "Content Creator"},
        {"name": "Expand /resources/fifo-members page",               "priority": "Medium",   "category": "Content",    "assigned": "Content Creator"},
        {"name": "Expand /kids-hub page + fix title tag",             "priority": "Medium",   "category": "Content",    "assigned": "Content Creator"},
        {"name": "Publish blog: Best Gym in Malaga",                  "priority": "Medium",   "category": "Content",    "assigned": "Content Creator"},
        {"name": "Build backlinks: True Local AU, Yellow Pages AU",   "priority": "Medium",   "category": "SEO",        "assigned": "SEO Specialist"},
        # Google Ads
        {"name": "Enable Google Business Profile APIs in GCP",        "priority": "High",     "category": "Technical",  "assigned": "Developer"},
        {"name": "Pause 'Malaga Gym' campaign when ranking #1–3",     "priority": "Low",      "category": "Google Ads", "assigned": "Google Ads Manager"},
        # GBP
        {"name": "Print QR code review cards — Malaga + Ellenbrook", "priority": "Critical", "category": "GBP",        "assigned": "Front Desk"},
        {"name": "Brief front desk on verbal review ask script",      "priority": "Critical", "category": "GBP",        "assigned": "Tia (Owner)"},
        {"name": "Rewrite GBP business descriptions (both locations)","priority": "High",     "category": "GBP",        "assigned": "Content Creator"},
        {"name": "Seed GBP Q&A with 6 pre-answered questions",       "priority": "High",     "category": "GBP",        "assigned": "Content Creator"},
        {"name": "Audit + complete all GBP Services/Products listings","priority": "High",    "category": "GBP",        "assigned": "Tia (Owner)"},
        {"name": "Upload 10 priority photos per location (sauna, ice bath, Kids Hub)", "priority": "High", "category": "GBP", "assigned": "Front Desk"},
        {"name": "Begin weekly GBP posts every Tuesday",              "priority": "Medium",   "category": "GBP",        "assigned": "Content Creator"},
        {"name": "Submit NAP listings to AU directories (True Local, Yelp, etc.)", "priority": "Medium", "category": "GBP", "assigned": "SEO Specialist"},
    ]


# =============================================================================
# Content Planner Setup
# =============================================================================

def setup_content_planner(client, parent_id):
    """
    Creates the CB247 Marketing Content Planner database in Notion.
    Columns: Week, Channel, Format, Location, Topic, Copy, Status, Assigned To,
             Asset Needed, Published URL.

    Run once with:  python3 scripts/push_to_notion.py --setup-planner
    """
    print("[Notion] Creating 📅 Marketing Content Planner database...")

    planner_props = {
        "Name": {"title": {}},                        # Post title / topic
        "Week": {"date": {}},                          # Week commencing date
        "Channel": {"select": {"options": [
            {"name": "GBP Post",   "color": "green"},
            {"name": "Instagram",  "color": "pink"},
            {"name": "TikTok",     "color": "red"},
            {"name": "Blog",       "color": "green"},
            {"name": "Email",      "color": "blue"},
            {"name": "Google Ads", "color": "orange"},
            {"name": "Facebook",   "color": "purple"},
        ]}},
        "Format": {"select": {"options": [
            {"name": "Reel / Video",  "color": "red"},
            {"name": "Story",         "color": "pink"},
            {"name": "Carousel",      "color": "orange"},
            {"name": "Static Image",  "color": "yellow"},
            {"name": "Post / Update", "color": "green"},
            {"name": "Article",       "color": "blue"},
            {"name": "Newsletter",    "color": "purple"},
            {"name": "Ad Copy",       "color": "gray"},
        ]}},
        "Location": {"select": {"options": [
            {"name": "Malaga",       "color": "green"},
            {"name": "Ellenbrook",   "color": "blue"},
            {"name": "Both",         "color": "green"},
        ]}},
        "Status": {"select": {"options": [
            {"name": "Idea",       "color": "gray"},
            {"name": "Draft",      "color": "yellow"},
            {"name": "In Review",  "color": "orange"},
            {"name": "Approved",   "color": "blue"},
            {"name": "Scheduled",  "color": "purple"},
            {"name": "Published",  "color": "green"},
        ]}},
        "Assigned To": {"select": {"options": [
            {"name": "Content Creator",    "color": "purple"},
            {"name": "SEO Specialist",     "color": "green"},
            {"name": "Google Ads Manager", "color": "blue"},
            {"name": "Front Desk",         "color": "yellow"},
            {"name": "Tia (Owner)",        "color": "red"},
        ]}},
        "Trend / Hook":      {"rich_text": {}},        # Hook or trend angle
        "Copy":              {"rich_text": {}},        # Draft post copy
        "CTA":               {"rich_text": {}},        # Call to action
        "Asset Needed":      {"checkbox": {}},         # Photo/video asset required?
        "Published URL":     {"url": {}},              # Live post / article URL
    }

    db = client.create_database(parent_id, "📅 Marketing Content Planner", planner_props, icon="📅")
    print(f"[Notion]   ✅ Content Planner created. DB ID: {db['id']}")

    # Save the new DB ID alongside existing IDs
    ids = {}
    if NOTION_IDS_FILE.exists():
        ids = json.loads(NOTION_IDS_FILE.read_text())
    ids["content_planner_db_id"] = db["id"]
    NOTION_IDS_FILE.write_text(json.dumps(ids, indent=2))
    print(f"[Notion]   ID saved → {NOTION_IDS_FILE}")

    # Seed with 4 weeks of content (one per channel rotation)
    seed_items = [
        {"name": "GBP Post W1 — $11.95/wk value highlight",    "channel": "GBP Post",   "format": "Post / Update", "location": "Both",        "assigned": "Content Creator", "status": "Idea"},
        {"name": "GBP Post W2 — Ice Bath + Sauna spotlight",    "channel": "GBP Post",   "format": "Post / Update", "location": "Malaga",      "assigned": "Content Creator", "status": "Idea"},
        {"name": "GBP Post W3 — Member challenge event",        "channel": "GBP Post",   "format": "Post / Update", "location": "Both",        "assigned": "Content Creator", "status": "Idea"},
        {"name": "GBP Post W4 — FIFO Freeze offer",             "channel": "GBP Post",   "format": "Post / Update", "location": "Both",        "assigned": "Content Creator", "status": "Idea"},
        {"name": "Reel — Cold plunge recovery routine",          "channel": "Instagram",  "format": "Reel / Video",  "location": "Malaga",      "assigned": "Content Creator", "status": "Idea"},
        {"name": "Carousel — Kids Hub walkthrough",              "channel": "Instagram",  "format": "Carousel",      "location": "Ellenbrook",  "assigned": "Content Creator", "status": "Idea"},
        {"name": "TikTok — '75 Hard at CB247 Malaga' POV",      "channel": "TikTok",     "format": "Reel / Video",  "location": "Malaga",      "assigned": "Content Creator", "status": "Idea"},
        {"name": "Blog — Best gym in Malaga (SEO)",              "channel": "Blog",       "format": "Article",       "location": "Malaga",      "assigned": "SEO Specialist",  "status": "Draft"},
        {"name": "Email — Monthly member newsletter",            "channel": "Email",      "format": "Newsletter",    "location": "Both",        "assigned": "Content Creator", "status": "Idea"},
    ]

    for item in seed_items:
        props = {
            "Name":        {"title":  [{"text": {"content": item["name"]}}]},
            "Channel":     {"select": {"name": item["channel"]}},
            "Format":      {"select": {"name": item["format"]}},
            "Location":    {"select": {"name": item["location"]}},
            "Assigned To": {"select": {"name": item["assigned"]}},
            "Status":      {"select": {"name": item["status"]}},
        }
        client.create_db_item(db["id"], props)
        time.sleep(0.2)

    print(f"[Notion]   ✅ Content Planner seeded with {len(seed_items)} items.")
    return db


# =============================================================================
# Workspace Setup (first run)
# =============================================================================

def setup_workspace(client, parent_id):
    """Creates the full Notion workspace structure. Run once with --setup."""
    print("[Notion] Setting up workspace structure...")
    ids = {}

    # 0. Weekly Marketing Report page (full report — management view)
    # NOTE: created with placeholder only; column_list blocks require append_blocks (not create_page children)
    print("[Notion]   Creating '📋 Weekly Marketing Report'...")
    wr = client.create_page(
        parent_id, "📋 Weekly Marketing Report",
        children=[callout("Loading report data…", "⏳", "gray_background")],
        icon="📋"
    )
    ids["weekly_report_page_id"] = wr["id"]
    time.sleep(0.5)

    # 1. Weekly Performance page
    print("[Notion]   Creating '📊 Weekly Performance'...")
    wp = client.create_page(
        parent_id, "📊 Weekly Performance",
        children=[para("This page auto-updates every Monday via the CB247 Marketing Agent.")],
        icon="📊"
    )
    ids["weekly_performance_page_id"] = wp["id"]
    time.sleep(0.5)

    # 2. Action Tracker database
    print("[Notion]   Creating '✅ Action Tracker' database...")
    db_props = {
        "Name": {"title": {}},
        "Status": {"select": {"options": [
            {"name": "Not Started", "color": "red"},
            {"name": "In Progress", "color": "yellow"},
            {"name": "Done",        "color": "green"},
            {"name": "Blocked",     "color": "orange"},
        ]}},
        "Priority": {"select": {"options": [
            {"name": "Critical", "color": "red"},
            {"name": "High",     "color": "orange"},
            {"name": "Medium",   "color": "yellow"},
            {"name": "Low",      "color": "blue"},
        ]}},
        "Category": {"select": {"options": [
            {"name": "SEO",        "color": "green"},
            {"name": "Google Ads", "color": "blue"},
            {"name": "Content",    "color": "purple"},
            {"name": "Technical",  "color": "gray"},
            {"name": "Meta Ads",   "color": "pink"},
            {"name": "GBP",        "color": "green"},
        ]}},
        "Assigned To": {"select": {"options": [
            {"name": "SEO Specialist",     "color": "green"},
            {"name": "Google Ads Manager", "color": "blue"},
            {"name": "Content Creator",    "color": "purple"},
            {"name": "Developer",          "color": "gray"},
            {"name": "Front Desk",         "color": "yellow"},
            {"name": "Tia (Owner)",        "color": "red"},
        ]}},
        "Due Date":        {"date": {}},
        "Outcome":         {"rich_text": {}},
        "Verified Working":{"checkbox": {}},
        "Notes":           {"rich_text": {}},
    }
    at_db = client.create_database(parent_id, "✅ Action Tracker", db_props, icon="✅")
    ids["action_tracker_db_id"] = at_db["id"]
    time.sleep(0.5)

    # Populate action tracker
    print("[Notion]   Populating Action Tracker...")
    for item in get_initial_action_items():
        props = {
            "Name":        {"title":  [{"text": {"content": item["name"]}}]},
            "Status":      {"select": {"name": "Not Started"}},
            "Priority":    {"select": {"name": item["priority"]}},
            "Category":    {"select": {"name": item["category"]}},
            "Assigned To": {"select": {"name": item.get("assigned", "Tia (Owner)")}},
        }
        client.create_db_item(ids["action_tracker_db_id"], props)
        time.sleep(0.2)

    # 3. SEO Deliverables page
    print("[Notion]   Creating '🔍 SEO Deliverables'...")
    seo_blocks = build_seo_deliverables_blocks()
    seo = client.create_page(parent_id, "🔍 SEO Deliverables", children=seo_blocks, icon="🔍")
    ids["seo_deliverables_page_id"] = seo["id"]
    time.sleep(0.5)

    # 4. Team Briefings page
    print("[Notion]   Creating '📋 Team Briefings'...")
    brief_blocks = [
        callout("Meeting notes and weekly briefings appear here. Use /meeting commands in Claude Code.", "📝", "blue_background"),
        divider(),
        h2("How to Use"),
        bullet("Before meetings: run /meeting prepare → AI generates data-backed recommendations"),
        bullet("During meeting: run /meeting record [your notes] → captures structured minutes"),
        bullet("After meeting: action items auto-added to the Action Tracker"),
        divider(),
        h2("Previous Briefings"),
        para("No briefings yet. Start with /meeting record in Claude Code."),
    ]
    br = client.create_page(parent_id, "📋 Team Briefings", children=brief_blocks, icon="📋")
    ids["team_briefings_page_id"] = br["id"]

    # Save IDs
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    NOTION_IDS_FILE.write_text(json.dumps(ids, indent=2))
    print(f"[Notion] IDs saved → {NOTION_IDS_FILE}")
    return ids


# =============================================================================
# Update Functions (weekly runs)
# =============================================================================

def load_json_path(path):
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception:
        return None


def update_weekly_report(client, page_id, ga4, gsc, ads_data, apify=None):
    print("[Notion] Updating Weekly Marketing Report...")
    client.clear_page(page_id)
    time.sleep(0.5)
    blocks = build_weekly_report_page_blocks(ga4, gsc, ads_data, apify)
    client.append_blocks(page_id, blocks)
    print(f"[Notion]   ✅ Weekly Marketing Report updated ({len(blocks)} blocks)")


def update_weekly_performance(client, page_id, ga4, gsc, gads):
    print("[Notion] Updating Weekly Performance...")
    client.clear_page(page_id)
    time.sleep(0.5)
    blocks = build_weekly_performance_blocks(ga4, gsc, gads)
    client.append_blocks(page_id, blocks)
    print(f"[Notion]   ✅ Weekly Performance updated ({len(blocks)} blocks)")


def update_seo_deliverables(client, page_id):
    print("[Notion] Updating SEO Deliverables...")
    client.clear_page(page_id)
    time.sleep(0.5)
    blocks = build_seo_deliverables_blocks()
    client.append_blocks(page_id, blocks)
    print(f"[Notion]   ✅ SEO Deliverables updated ({len(blocks)} blocks)")


# =============================================================================
# Main
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Push CB247 data to Notion workspace")
    parser.add_argument("--setup",            action="store_true", help="First-time setup: create workspace structure")
    parser.add_argument("--setup-planner",    action="store_true", help="Create the Marketing Content Planner database")
    parser.add_argument("--performance-only", action="store_true", help="Update weekly performance page only")
    parser.add_argument("--seo-only",         action="store_true", help="Update SEO deliverables page only")
    args = parser.parse_args()

    if not NOTION_API_KEY:
        print("[Notion] Skipping — NOTION_API_KEY not set in .env")
        return

    if args.setup and not NOTION_PARENT_PAGE_ID:
        print("[Notion] ERROR: NOTION_PARENT_PAGE_ID not set in .env")
        print()
        print("Quick setup (5 mins):")
        print("  1. notion.so/my-integrations → New integration → 'CB247 Marketing Agent'")
        print("     Token is already in .env as NOTION_API_KEY ✅")
        print()
        print("  2. In Notion: create page 'CB247 Marketing Hub'")
        print("     Click '...' → Add connections → CB247 Marketing Agent")
        print()
        print("  3. Copy the page ID from the URL:")
        print("     notion.so/CB247-Marketing-Hub-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        print("     Add to .env: NOTION_PARENT_PAGE_ID=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        print()
        print("  4. Re-run: python3 scripts/push_to_notion.py --setup")
        return

    client = NotionClient(NOTION_API_KEY)

    def load_json(path):
        try:
            return json.loads(path.read_text()) if path.exists() else None
        except Exception:
            return None

    ga4      = load_json(STATE_DIR / "ga4-data.json")
    gsc      = load_json(STATE_DIR / "gsc-data.json")
    gads     = load_json(STATE_DIR / "google-ads-data.json")
    ads_data = load_json(STATE_DIR / "ads-data.json")
    apify    = load_json(STATE_DIR / "apify-data.json")

    # ── First-time setup ───────────────────────────────────────────────────
    if args.setup:
        ids = setup_workspace(client, NOTION_PARENT_PAGE_ID)
        print()
        time.sleep(0.5)
        # Populate performance with current live data
        update_weekly_performance(client, ids["weekly_performance_page_id"], ga4, gsc, gads)
        time.sleep(0.3)
        if ids.get("weekly_report_page_id"):
            update_weekly_report(client, ids["weekly_report_page_id"], ga4, gsc, ads_data, apify)
        print()
        print("[Notion] ✅ Setup complete!")
        print("[Notion] Open Notion → CB247 Marketing Hub to see your workspace.")
        print()
        print("Share with your team:")
        print("  1. Open 'CB247 Marketing Hub' in Notion")
        print("  2. Click 'Share' → Invite by email → add team members")
        print("  3. Set each member's role: Full Access, Can Edit, or Can View")
        return

    # ── Update mode ────────────────────────────────────────────────────────
    if not NOTION_IDS_FILE.exists():
        print("[Notion] Workspace not set up. Run first:")
        print("  python3 scripts/push_to_notion.py --setup")
        return

    ids = json.loads(NOTION_IDS_FILE.read_text())

    if args.setup_planner:
        if not NOTION_PARENT_PAGE_ID:
            print("[Notion] ERROR: NOTION_PARENT_PAGE_ID not set in .env — run --setup first")
            return
        setup_content_planner(client, NOTION_PARENT_PAGE_ID)
        return

    if args.seo_only:
        update_seo_deliverables(client, ids["seo_deliverables_page_id"])
        return

    if args.performance_only:
        update_weekly_performance(client, ids["weekly_performance_page_id"], ga4, gsc, gads)
        return

    # Full update (default — runs every Monday)
    if ids.get("weekly_report_page_id"):
        update_weekly_report(client, ids["weekly_report_page_id"], ga4, gsc, ads_data, apify)
        time.sleep(0.3)
    update_weekly_performance(client, ids["weekly_performance_page_id"], ga4, gsc, gads)
    time.sleep(0.3)
    update_seo_deliverables(client, ids["seo_deliverables_page_id"])
    print()
    print("[Notion] ✅ All updates pushed.")
    print("[Notion] Open Notion → CB247 Marketing Hub to see live data.")


if __name__ == "__main__":
    main()
