"""
push_dashboard.py — CB247 Visual Marketing Dashboard for Notion.

Builds a visual command-centre page matching the Agency OS style:

  ┌─────────────────────────────────────────────────────────────────┐
  │  🏠 CB247 Marketing Dashboard                                   │
  ├──────────────┬──────────────────────┬──────────────────────────┤
  │  📍 Nav      │  📊 Ad Spend Donut   │  📈 Performance Bar      │
  │  Quick acts  │     (chart image)    │      (chart image)       │
  │  Nav links   │  Malaga/Ellenbrook   │  Spend & Conversions     │
  ├──────────────┴──────────────────────┴──────────────────────────┤
  │  🔍 SEO Rankings Chart  │  🎨 Content Pipeline Chart           │
  │     (horizontal bar)    │     (doughnut)                       │
  ├─────────────────────────┴──────────────────────────────────────┤
  │  ✅ Priority Actions (todos)  │  📊 Live KPI Snapshot           │
  ├───────────────────────────────┴────────────────────────────────┤
  │  [Full sections: Performance · Actions · SEO · Campaigns]       │
  └─────────────────────────────────────────────────────────────────┘

Charts are rendered via QuickChart.io (free, no auth) and embedded as
Notion image blocks. They auto-update every Monday with fresh data.

Usage:
  python3 scripts/push_dashboard.py --setup    # First run
  python3 scripts/push_dashboard.py --update   # Refresh all data + charts
"""

import json
import os
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

try:
    import requests
except ImportError:
    print("[Dashboard] requests not installed. Run: pip install requests")
    sys.exit(1)

BASE_DIR   = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
STATE_DIR  = BASE_DIR / "state"

NOTION_API_KEY        = os.getenv("NOTION_API_KEY", "")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")
NOTION_VERSION        = "2022-06-28"
NOTION_BASE           = "https://api.notion.com/v1"

DASHBOARD_IDS_FILE = STATE_DIR / "dashboard-ids.json"
NOTION_IDS_FILE    = STATE_DIR / "notion-ids.json"
CAMPAIGN_OS_FILE   = STATE_DIR / "campaign-os-ids.json"

# CB247 brand colours
TEAL   = "#3FA69A"
CORAL  = "#FF6B6B"
GOLD   = "#FFCE56"
BLUE   = "#36A2EB"
PURPLE = "#9B59B6"
GREY   = "#E0E0E0"


# =============================================================================
# Notion Client
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
                    wait = int(r.headers.get("Retry-After", 5))
                    print(f"[Dashboard] Rate limited — waiting {wait}s...")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except requests.HTTPError:
                if attempt == retries - 1:
                    print(f"[Dashboard] API error {r.status_code}: {r.text[:300]}")
                    raise
                time.sleep(1 + attempt)
        raise RuntimeError("[Dashboard] Max retries exceeded")

    def create_page(self, parent_id, title, children=None, icon="🏠"):
        body = {
            "parent": {"page_id": parent_id},
            "icon": {"type": "emoji", "emoji": icon},
            "properties": {"title": {"title": [{"text": {"content": title}}]}},
        }
        if children:
            body["children"] = children[:100]
        result = self._req("post", "pages", body)
        if children and len(children) > 100:
            time.sleep(0.4)
            self.append_blocks(result["id"], children[100:])
        return result

    def append_blocks(self, block_id, children):
        for i in range(0, len(children), 100):
            batch = children[i:i + 100]
            self._req("patch", f"blocks/{block_id}/children", {"children": batch})
            if i + 100 < len(children):
                time.sleep(0.4)

    def clear_page(self, page_id):
        results, cursor = [], None
        while True:
            qs = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            resp = self._req("get", f"blocks/{page_id}/children{qs}")
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        for block in results:
            try:
                self._req("delete", f"blocks/{block['id']}")
                time.sleep(0.05)
            except Exception:
                pass


# =============================================================================
# Block Builders
# =============================================================================

def rt(text, bold=False, italic=False, color="default"):
    return {
        "type": "text",
        "text": {"content": str(text)[:2000]},
        "annotations": {"bold": bold, "italic": italic, "color": color},
    }

def page_mention(page_id):
    return {"type": "mention", "mention": {"type": "page", "page": {"id": page_id}},
            "annotations": {"bold": True, "color": "default"}}

def h1(text):
    return {"object": "block", "type": "heading_1",
            "heading_1": {"rich_text": [rt(text)], "is_toggleable": False}}

def h2(text):
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [rt(text)], "is_toggleable": False}}

def h3(text):
    return {"object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [rt(text)], "is_toggleable": False}}

def para(text="", bold=False, color="default"):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [rt(text, bold=bold, color=color)] if text else []}}

def para_link(prefix, page_id):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [rt(prefix, bold=True), page_mention(page_id)]}}

def bullet(text, bold=False, color="default"):
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [rt(text, bold=bold, color=color)]}}

def todo(text, checked=False):
    return {"object": "block", "type": "to_do",
            "to_do": {"rich_text": [rt(text)], "checked": checked}}

def divider():
    return {"object": "block", "type": "divider", "divider": {}}

def callout(text, icon="💡", color="blue_background", bold=False):
    return {"object": "block", "type": "callout",
            "callout": {"rich_text": [rt(text, bold=bold)],
                        "icon": {"type": "emoji", "emoji": icon}, "color": color}}

def image_block(url, caption=""):
    block = {"object": "block", "type": "image",
             "image": {"type": "external", "external": {"url": url}}}
    if caption:
        block["image"]["caption"] = [rt(caption, italic=True, color="gray")]
    return block

def col2(left, right):
    return {"object": "block", "type": "column_list",
            "column_list": {"children": [
                {"object": "block", "type": "column", "column": {"children": left}},
                {"object": "block", "type": "column", "column": {"children": right}},
            ]}}

def col3(left, mid, right):
    return {"object": "block", "type": "column_list",
            "column_list": {"children": [
                {"object": "block", "type": "column", "column": {"children": left}},
                {"object": "block", "type": "column", "column": {"children": mid}},
                {"object": "block", "type": "column", "column": {"children": right}},
            ]}}

def table(headers, rows):
    width = len(headers)
    header_row = {"object": "block", "type": "table_row",
                  "table_row": {"cells": [[rt(h, bold=True)] for h in headers]}}
    data_rows = [{"object": "block", "type": "table_row",
                  "table_row": {"cells": [[rt(str(c))] for c in row]}}
                 for row in rows]
    return {"object": "block", "type": "table",
            "table": {"table_width": width, "has_column_header": True,
                      "has_row_header": False, "children": [header_row] + data_rows}}


# =============================================================================
# Chart URL Builders  (QuickChart.io — free, no auth)
# =============================================================================

def _chart_url(cfg, w=520, h=320):
    """Encode a Chart.js config dict into a QuickChart.io image URL."""
    encoded = urllib.parse.quote(json.dumps(cfg, separators=(",", ":")), safe="")
    return f"https://quickchart.io/chart?w={w}&h={h}&bkg=white&c={encoded}"


def chart_ad_spend_donut(gads):
    """Doughnut: weekly spend split by location."""
    malaga, ellenbrook = 137, 386
    if gads:
        acc = gads.get("accounts", {})
        malaga     = round(acc.get("Malaga",      {}).get("spend", 137))
        ellenbrook = round(acc.get("Ellenbrook",  {}).get("spend", 386))
    total = malaga + ellenbrook
    cfg = {
        "type": "doughnut",
        "data": {
            "labels": [f"Ellenbrook  ${ellenbrook}/wk", f"Malaga  ${malaga}/wk"],
            "datasets": [{"data": [ellenbrook, malaga],
                          "backgroundColor": [TEAL, CORAL],
                          "borderWidth": 3, "borderColor": "#fff"}]
        },
        "options": {
            "plugins": {
                "title": {"display": True,
                          "text": f"Weekly Ad Spend  —  ${total}/wk total",
                          "font": {"size": 15, "weight": "bold"}, "color": "#1a1a1a"},
                "legend": {"position": "bottom",
                           "labels": {"font": {"size": 12}, "padding": 16}}
            },
            "cutout": "62%"
        }
    }
    return _chart_url(cfg, 480, 320)


def chart_performance_bar(gads):
    """Grouped bar: spend + conversions per location."""
    malaga_spend, ellenbrook_spend = 137, 386
    malaga_conv,  ellenbrook_conv  = 0, 0
    malaga_cpl,   ellenbrook_cpl   = 0, 0
    if gads:
        acc = gads.get("accounts", {})
        if "Malaga" in acc:
            malaga_spend = round(acc["Malaga"].get("spend", 137))
            malaga_conv  = round(acc["Malaga"].get("conversions", 0))
            malaga_cpl   = round(acc["Malaga"].get("cpl", 0))
        if "Ellenbrook" in acc:
            ellenbrook_spend = round(acc["Ellenbrook"].get("spend", 386))
            ellenbrook_conv  = round(acc["Ellenbrook"].get("conversions", 0))
            ellenbrook_cpl   = round(acc["Ellenbrook"].get("cpl", 0))
    cfg = {
        "type": "bar",
        "data": {
            "labels": ["Malaga", "Ellenbrook"],
            "datasets": [
                {"label": "Weekly Spend ($)",
                 "data": [malaga_spend, ellenbrook_spend],
                 "backgroundColor": TEAL,
                 "borderRadius": 5},
                {"label": "Conversions",
                 "data": [malaga_conv, ellenbrook_conv],
                 "backgroundColor": CORAL,
                 "borderRadius": 5},
                {"label": "CPL ($)",
                 "data": [malaga_cpl, ellenbrook_cpl],
                 "backgroundColor": GOLD,
                 "borderRadius": 5},
            ]
        },
        "options": {
            "plugins": {
                "title": {"display": True, "text": "Google Ads — Spend vs Conversions vs CPL",
                          "font": {"size": 15, "weight": "bold"}, "color": "#1a1a1a"},
                "legend": {"position": "bottom", "labels": {"font": {"size": 12}}}
            },
            "scales": {
                "y": {"beginAtZero": True,
                      "title": {"display": True, "text": "Value ($)"}}
            }
        }
    }
    return _chart_url(cfg, 520, 320)


def chart_seo_rankings(gsc):
    """Horizontal bar: organic position per keyword (lower = better)."""
    queries = ["gym malaga", "gym ellenbrook", "chasingbetter247",
               "gym near malaga", "massage malaga open now", "kids gym perth"]
    positions = [5.5, 4.0, 1.0, 8.0, 16.0, 12.0]
    targets   = [3,   3,   1,   3,    3,     3]

    # Try to use real GSC data
    if gsc and gsc.get("top_queries"):
        gsc_map = {q["query"].lower(): q.get("position", 99)
                   for q in gsc.get("top_queries", [])}
        for i, q in enumerate(queries):
            if q in gsc_map:
                positions[i] = round(gsc_map[q], 1)

    colours = [TEAL if p <= t else CORAL for p, t in zip(positions, targets)]
    cfg = {
        "type": "bar",
        "data": {
            "labels": queries,
            "datasets": [{
                "label": "Current Position",
                "data": positions,
                "backgroundColor": colours,
                "borderRadius": 4,
                "borderSkipped": False,
            }]
        },
        "options": {
            "indexAxis": "y",
            "plugins": {
                "title": {"display": True,
                          "text": "SEO Rankings  —  Current Organic Positions (lower = better)",
                          "font": {"size": 14, "weight": "bold"}, "color": "#1a1a1a"},
                "legend": {"display": False},
                "annotation": {
                    "annotations": {
                        "targetLine": {
                            "type": "line", "xMin": 3, "xMax": 3,
                            "borderColor": GOLD, "borderWidth": 2,
                            "borderDash": [6, 4],
                            "label": {"content": "Target #3", "enabled": True}
                        }
                    }
                }
            },
            "scales": {
                "x": {"beginAtZero": True, "max": 20, "reverse": False,
                      "title": {"display": True,
                                "text": "Position (lower = better | 🟢 on target | 🔴 needs work)"}}
            }
        }
    }
    return _chart_url(cfg, 560, 340)


def chart_content_pipeline():
    """Doughnut: content asset status breakdown."""
    cfg = {
        "type": "doughnut",
        "data": {
            "labels": ["Not Started  (5)", "Draft  (3)", "Published  (2)"],
            "datasets": [{
                "data": [5, 3, 2],
                "backgroundColor": [GREY, GOLD, TEAL],
                "borderWidth": 3, "borderColor": "#fff"
            }]
        },
        "options": {
            "plugins": {
                "title": {"display": True,
                          "text": "Content Pipeline  —  10 Assets",
                          "font": {"size": 15, "weight": "bold"}, "color": "#1a1a1a"},
                "legend": {"position": "bottom",
                           "labels": {"font": {"size": 12}, "padding": 16}}
            },
            "cutout": "60%"
        }
    }
    return _chart_url(cfg, 440, 300)


def chart_weekly_traffic(ga4):
    """Bar: sessions this week vs last week."""
    curr = 0
    prev = 0
    if ga4:
        curr = int(ga4.get("current",  {}).get("sessions", 0) or 0)
        prev = int(ga4.get("previous", {}).get("sessions", 0) or 0)
    cfg = {
        "type": "bar",
        "data": {
            "labels": ["Last Week", "This Week"],
            "datasets": [{
                "label": "Website Sessions",
                "data": [prev, curr],
                "backgroundColor": [GREY, TEAL],
                "borderRadius": 6
            }]
        },
        "options": {
            "plugins": {
                "title": {"display": True, "text": "Website Traffic — Sessions",
                          "font": {"size": 14, "weight": "bold"}, "color": "#1a1a1a"},
                "legend": {"display": False}
            },
            "scales": {"y": {"beginAtZero": True}}
        }
    }
    return _chart_url(cfg, 400, 260)


def chart_cpl_gauge(gads):
    """Bar chart showing CPL vs $20 target per location."""
    malaga_cpl, ellenbrook_cpl = 0, 0
    if gads:
        acc = gads.get("accounts", {})
        malaga_cpl     = round(acc.get("Malaga",     {}).get("cpl", 0), 2)
        ellenbrook_cpl = round(acc.get("Ellenbrook", {}).get("cpl", 0), 2)
    cfg = {
        "type": "bar",
        "data": {
            "labels": ["Malaga CPL", "Ellenbrook CPL", "Target CPL"],
            "datasets": [{
                "label": "Cost Per Lead ($)",
                "data": [malaga_cpl, ellenbrook_cpl, 20],
                "backgroundColor": [
                    TEAL  if malaga_cpl <= 20     else CORAL,
                    TEAL  if ellenbrook_cpl <= 20 else CORAL,
                    GOLD
                ],
                "borderRadius": 6
            }]
        },
        "options": {
            "plugins": {
                "title": {"display": True,
                          "text": "CPL vs $20 Target  —  🟢 on track  🔴 over target",
                          "font": {"size": 14, "weight": "bold"}, "color": "#1a1a1a"},
                "legend": {"display": False}
            },
            "scales": {
                "y": {"beginAtZero": True,
                      "title": {"display": True, "text": "Cost per Lead ($)"}}
            }
        }
    }
    return _chart_url(cfg, 420, 280)


# =============================================================================
# Section Builders
# =============================================================================

def build_nav_column(notion_ids, campaign_ids):
    """Left sidebar: quick-action buttons + navigation links."""
    b = []

    # Header
    b.append(callout("📍  Navigation", "🧭", "gray_background", bold=True))
    b.append(para(""))

    # Quick actions
    b.append(h3("⚡ Quick Actions"))
    b.append(callout("➕  New Campaign",         "🎯", "gray_background"))
    b.append(callout("➕  New Content Asset",    "🎨", "gray_background"))
    b.append(callout("➕  New Ad Spend Entry",   "💰", "gray_background"))
    b.append(callout("➕  New Task",             "✅", "gray_background"))
    b.append(para(""))

    # Nav links
    b.append(h3("🗂 Pages"))

    def nav(emoji, label, page_id):
        if page_id:
            return para_link(f"{emoji}  ", page_id)
        return bullet(f"{emoji}  {label}")

    b.append(nav("📊", "Weekly Performance",  notion_ids.get("weekly_performance_page_id")))
    b.append(nav("✅", "Action Tracker",       notion_ids.get("action_tracker_db_id")))
    b.append(nav("🔍", "SEO Deliverables",     notion_ids.get("seo_deliverables_page_id")))
    b.append(nav("📋", "Team Briefings",       notion_ids.get("team_briefings_page_id")))
    b.append(divider())
    b.append(nav("🎯", "Campaign Delivery OS",  campaign_ids.get("home_page_id")))
    b.append(nav("📋", "Campaigns",             campaign_ids.get("campaigns_db_id")))
    b.append(nav("🎨", "Content Assets",        campaign_ids.get("content_assets_db_id")))
    b.append(nav("💰", "Ad Spend Tracker",      campaign_ids.get("ad_spend_db_id")))
    b.append(para(""))

    # Quick stats strip
    b.append(h3("📊 At a Glance"))
    b.append(bullet("💰  Ad spend: $523/wk"))
    b.append(bullet("🟢  Live campaigns: 2"))
    b.append(bullet("🔴  Critical SEO tasks: 3"))
    b.append(bullet("📝  Content tracked: 10"))
    b.append(bullet("📍  Domain Rating: 7/100"))
    return b


def build_ad_spend_chart_col(gads):
    """Centre column: ad spend donut chart."""
    b = []
    b.append(image_block(
        chart_ad_spend_donut(gads),
        "Weekly spend split: Malaga vs Ellenbrook — auto-updated every Monday"
    ))
    b.append(para(""))
    b.append(h3("💰 Spend Breakdown"))
    malaga     = round((gads or {}).get("accounts", {}).get("Malaga",     {}).get("spend", 137))
    ellenbrook = round((gads or {}).get("accounts", {}).get("Ellenbrook", {}).get("spend", 386))
    b.append(bullet(f"Malaga:       ${malaga}/wk  (~${malaga * 4.33:,.0f}/mo)",     bold=True))
    b.append(bullet(f"Ellenbrook:   ${ellenbrook}/wk  (~${ellenbrook * 4.33:,.0f}/mo)", bold=True))
    b.append(bullet(f"Total:        ${malaga + ellenbrook}/wk  (~${(malaga + ellenbrook) * 4.33:,.0f}/mo)", bold=True))
    b.append(para(""))
    b.append(callout(
        "Goal: reduce to <$200/wk once 'gym malaga' + 'gym ellenbrook' hit organic #1–3",
        "🎯", "green_background"
    ))
    return b


def build_performance_chart_col(gads):
    """Right column: performance bar chart."""
    b = []
    b.append(image_block(
        chart_performance_bar(gads),
        "Google Ads performance by location — spend, conversions, CPL"
    ))
    b.append(para(""))
    b.append(h3("📈 CPL vs $20 Target"))
    b.append(image_block(
        chart_cpl_gauge(gads),
        "CPL gauge: 🟢 on target  🔴 over target"
    ))
    return b


def build_seo_chart_col(gsc):
    """Left col: SEO rankings chart."""
    b = []
    b.append(h2("🔍 SEO Rankings"))
    b.append(image_block(
        chart_seo_rankings(gsc),
        "Organic positions — 🟢 teal = at/above target  🔴 coral = needs improvement"
    ))
    b.append(para(""))
    if gsc and gsc.get("summary"):
        s = gsc["summary"]
        b.append(bullet(f"Organic clicks:   {s.get('total_clicks', 0):,}/wk"))
        b.append(bullet(f"Impressions:      {s.get('total_impressions', 0):,}"))
        b.append(bullet(f"Avg CTR:          {s.get('avg_ctr', 0) * 100:.1f}%"))
        b.append(bullet(f"Avg position:     #{s.get('avg_position', 0):.1f}"))
    else:
        b.append(callout("No GSC data — run: python3 scripts/pull_gsc.py", "⚠️", "yellow_background"))
    b.append(para(""))
    b.append(callout(
        "Target: 'gym malaga' #5→#1–3  |  'gym ellenbrook' #4→#1  |  Timeline: 6–12 weeks",
        "🎯", "blue_background"
    ))
    return b


def build_content_chart_col(ga4):
    """Right col: content pipeline + traffic chart."""
    b = []
    b.append(h2("🎨 Content Pipeline"))
    b.append(image_block(
        chart_content_pipeline(),
        "10 assets tracked: 2 published, 3 in draft, 5 not started"
    ))
    b.append(para(""))
    b.append(h2("📊 Website Traffic"))
    b.append(image_block(
        chart_weekly_traffic(ga4),
        "GA4 sessions: this week vs last week"
    ))
    if ga4 and ga4.get("current"):
        c = ga4["current"]
        p = ga4.get("previous", {})
        sess  = int(c.get("sessions", 0) or 0)
        prev  = int(p.get("sessions", 0) or 0)
        delta = sess - prev
        arrow = "↗️" if delta > 0 else ("↘️" if delta < 0 else "➡️")
        b.append(bullet(f"Sessions:    {sess:,}  {arrow}  ({'+' if delta >= 0 else ''}{delta} vs prev)"))
        b.append(bullet(f"New users:   {c.get('new_users', '—')}"))
        b.append(bullet(f"Conversions: {c.get('conversions', '—')}"))
    return b


def build_priority_actions_col():
    """Left col: priority action todos."""
    b = []
    b.append(h2("🔥 Priority Actions"))
    b.append(callout("Tick items as you complete them. Critical = this week.", "✅", "green_background"))
    b.append(para(""))
    b.append(h3("🔴 Critical — This Week"))
    b.append(todo("Submit disavow file (37 toxic domains) → GSC disavow tool"))
    b.append(todo("Fix 3 broken pages → add 301 redirects"))
    b.append(todo("Add H1 tags to 29 pages  (file: h1-recommendations-2026-05-30.md)"))
    b.append(para(""))
    b.append(h3("🟠 High — This Sprint"))
    b.append(todo("Add LocalBusiness schema markup (40 pages)"))
    b.append(todo("Expand /massage page  (1,300 searches/mo @ #16)"))
    b.append(todo("Create /ellenbrook landing page  (saves ~$386/wk ads)"))
    b.append(todo("Enable Google Business Profile APIs in GCP"))
    b.append(para(""))
    b.append(h3("🟡 Medium — This Month"))
    b.append(todo("Publish blog: Best Gym in Malaga Perth"))
    b.append(todo("Expand /resources/fifo-members page"))
    b.append(todo("Expand /kids-hub page + fix title tag"))
    b.append(todo("Build backlinks: True Local AU, Yellow Pages AU"))
    return b


def build_live_kpi_col(gads, gsc):
    """Right col: live KPI snapshot."""
    b = []
    today = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")
    b.append(h2("📊 Live KPI Snapshot"))
    b.append(callout(f"Auto-updated: {today}", "🤖", "gray_background"))
    b.append(para(""))

    b.append(h3("Google Ads"))
    if gads and gads.get("totals"):
        t     = gads["totals"]
        spend = t.get("spend", 0)
        cpl   = t.get("cpl", 0)
        flag  = "✅" if cpl <= 20 else "⚠️ over target"
        b.append(bullet(f"💰  Spend:       ${spend:,.2f}/wk", bold=True))
        b.append(bullet(f"🔄  Conversions: {t.get('conversions', 0):.0f}"))
        b.append(bullet(f"👆  Clicks:      {t.get('clicks', 0):,}"))
        b.append(bullet(f"📉  CPL:         ${cpl:.2f}  {flag}", bold=(cpl > 20)))
    else:
        b.append(bullet("No data — run: pull_google_ads.py"))
    b.append(para(""))

    b.append(h3("SEO / Organic"))
    if gsc and gsc.get("summary"):
        s = gsc["summary"]
        b.append(bullet(f"🖱️  Organic clicks:  {s.get('total_clicks', 0):,}/wk"))
        b.append(bullet(f"👁️  Impressions:     {s.get('total_impressions', 0):,}"))
        b.append(bullet(f"📊  Avg CTR:         {s.get('avg_ctr', 0) * 100:.1f}%"))
        b.append(bullet(f"📍  Avg position:    #{s.get('avg_position', 0):.1f}"))
    else:
        b.append(bullet("No data — run: pull_gsc.py"))
    b.append(para(""))

    b.append(h3("Domain Health"))
    b.append(bullet("Domain Rating:    7 / 100  (target: 20+)"))
    b.append(bullet("Toxic backlinks:  37 domains  (disavow ready)"))
    b.append(bullet("Technical issues: 3 Critical · 6 High · 2 Med"))
    b.append(para(""))

    b.append(h3("Campaigns"))
    b.append(table(
        ["Location", "Spend/wk", "CPL", "Status"],
        [
            ["Malaga",     "$137", f"${(gads or {}).get('accounts', {}).get('Malaga',     {}).get('cpl', 0):.0f}" if gads else "—", "🟢 Live"],
            ["Ellenbrook", "$386", f"${(gads or {}).get('accounts', {}).get('Ellenbrook', {}).get('cpl', 0):.0f}" if gads else "—", "🟢 Live"],
        ]
    ))
    return b


def build_campaign_overview():
    """Full campaign delivery table."""
    b = []
    b.append(h1("🎯 Campaign Delivery"))
    b.append(callout("All campaigns tracked below. Update status in the Campaign OS databases.", "🎯", "blue_background"))
    b.append(para(""))
    b.append(h2("Active Campaigns"))
    b.append(table(
        ["Campaign", "Status", "Type", "Location", "Budget/wk", "KPI Target"],
        [
            ["Malaga Membership — Google Ads",    "🟢 Live",        "Google Ads",  "Malaga",     "$137", "CPL ≤ $20"],
            ["Ellenbrook Membership — Google Ads","🟢 Live",        "Google Ads",  "Ellenbrook", "$386", "CPL ≤ $20"],
            ["Malaga SEO — Organic Rankings",     "🟡 In Delivery", "SEO Content", "Malaga",     "$0",   "'gym malaga' #5→#1–3"],
            ["Ellenbrook SEO — Landing Page",     "⚪ Planning",    "SEO Content", "Ellenbrook", "$0",   "'gym ellenbrook' #4→#1"],
            ["FIFO Retention Email",              "⚪ Planning",    "Email",       "Both",       "$0",   "Freeze rate ↓"],
            ["Kids Hub — School Holidays",        "⚪ Planning",    "Social",      "Both",       "$0",   "Trial sign-ups ↑ 20%"],
        ]
    ))
    b.append(para(""))
    b.append(h2("Content Pipeline"))
    b.append(table(
        ["Asset", "Type", "Platform", "Status", "Due"],
        [
            ["Malaga Google Ads Copy",         "Ad Copy",      "Google",   "✅ Published",   "—"],
            ["Ellenbrook Google Ads Copy",     "Ad Copy",      "Google",   "✅ Published",   "—"],
            ["Blog: Best Gym in Malaga",       "Blog Post",    "Website",  "📝 Draft",        "7 Jun"],
            ["H1 Tags — 29 Pages",             "On-page SEO",  "Website",  "⬜ Not Started", "7 Jun"],
            ["LocalBusiness Schema Markup",    "Technical",    "Website",  "⬜ Not Started", "7 Jun"],
            ["Massage Page Expansion",         "Landing Page", "Website",  "📝 Draft",        "14 Jun"],
            ["Ellenbrook Landing Page",        "Landing Page", "Website",  "📝 Draft",        "14 Jun"],
            ["FIFO Email Sequence",            "Email",        "Email",    "⬜ Not Started", "15 Jun"],
            ["Kids Hub — IG Posts (5x)",       "Social Post",  "Instagram","⬜ Not Started", "28 Jun"],
            ["Kids Hub — FB Event",            "Social Post",  "Facebook", "⬜ Not Started", "28 Jun"],
        ]
    ))
    return b


# =============================================================================
# Master Dashboard Builder
# =============================================================================

def build_dashboard(notion_ids, campaign_ids, ga4, gsc, gads):
    today = datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")
    spend = round((gads or {}).get("totals", {}).get("spend", 523))
    cpl   = round((gads or {}).get("totals", {}).get("cpl", 0), 2)
    clicks= (gads or {}).get("totals", {}).get("clicks", 0)
    organic = (gsc  or {}).get("summary", {}).get("total_clicks", 0)

    blocks = []

    # ── Status banner ──────────────────────────────────────────────────────
    blocks.append(callout(
        f"🏠 CB247 Marketing Dashboard  |  {today}  |  "
        f"Ad spend: ${spend}/wk  |  Organic clicks: {organic:,}/wk  |  "
        f"CPL: ${cpl}  |  Live campaigns: 2  |  Critical tasks: 3",
        "🤖", "blue_background", bold=True
    ))
    blocks.append(para(""))

    # ── Row 1: Nav | Ad Spend Donut | Performance Bar ─────────────────────
    nav_col     = build_nav_column(notion_ids, campaign_ids)
    spend_col   = build_ad_spend_chart_col(gads)
    perf_col    = build_performance_chart_col(gads)
    blocks.append(col3(nav_col, spend_col, perf_col))
    blocks.append(divider())

    # ── Row 2: SEO Rankings | Content Pipeline + Traffic ──────────────────
    seo_col     = build_seo_chart_col(gsc)
    content_col = build_content_chart_col(ga4)
    blocks.append(col2(seo_col, content_col))
    blocks.append(divider())

    # ── Row 3: Priority Actions | Live KPI Snapshot ───────────────────────
    actions_col = build_priority_actions_col()
    kpi_col     = build_live_kpi_col(gads, gsc)
    blocks.append(col2(actions_col, kpi_col))
    blocks.append(divider())

    # ── Campaign Overview (full width) ────────────────────────────────────
    blocks.extend(build_campaign_overview())
    blocks.append(divider())

    # ── Footer ────────────────────────────────────────────────────────────
    blocks.append(para(f"Generated by CB247 Marketing Agent  |  {today}", color="gray"))
    blocks.append(para("Auto-refreshes every Monday 11am AWST via: bash scripts/weekly-report.sh", color="gray"))

    return blocks


# =============================================================================
# Entry Point
# =============================================================================

def load_json(path):
    try:
        p = Path(path)
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


def run(client, is_setup=False):
    notion_ids   = load_json(NOTION_IDS_FILE)
    campaign_ids = load_json(CAMPAIGN_OS_FILE)
    ga4  = load_json(STATE_DIR / "ga4-data.json")
    gsc  = load_json(STATE_DIR / "gsc-data.json")
    gads = load_json(STATE_DIR / "google-ads-data.json")

    if is_setup:
        print("[Dashboard] Creating 🏠 CB247 Marketing Dashboard page...")
        page = client.create_page(
            NOTION_PARENT_PAGE_ID,
            "🏠 CB247 Marketing Dashboard",
            children=[para("Building dashboard — please wait...")],
            icon="🏠"
        )
        dashboard_id = page["id"]
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        DASHBOARD_IDS_FILE.write_text(json.dumps({"dashboard_page_id": dashboard_id}, indent=2))
        print(f"[Dashboard] Page created: {dashboard_id}")
        time.sleep(0.5)
    else:
        ids = load_json(DASHBOARD_IDS_FILE)
        if not ids.get("dashboard_page_id"):
            print("[Dashboard] Not set up. Run: python3 scripts/push_dashboard.py --setup")
            return
        dashboard_id = ids["dashboard_page_id"]

    print("[Dashboard] Clearing existing content...")
    client.clear_page(dashboard_id)
    time.sleep(0.5)

    print("[Dashboard] Building dashboard with charts...")
    blocks = build_dashboard(notion_ids, campaign_ids, ga4, gsc, gads)
    total  = len(blocks)

    print(f"[Dashboard] Pushing {total} blocks (including 6 chart images)...")
    client.append_blocks(dashboard_id, blocks)

    action = "created" if is_setup else "refreshed"
    print(f"[Dashboard] ✅ Dashboard {action}  ({total} blocks, 6 charts)")

    if is_setup:
        print()
        print("[Dashboard] Open Notion → CB247 Marketing Hub → 🏠 CB247 Marketing Dashboard")
        print()
        print("Charts on the dashboard:")
        print("  📊  Ad Spend Donut    — Malaga vs Ellenbrook weekly spend")
        print("  📈  Performance Bar   — Spend + Conversions + CPL per location")
        print("  📉  CPL Gauge         — CPL vs $20 target")
        print("  🔍  SEO Rankings      — Organic positions for 6 key queries")
        print("  🎨  Content Pipeline  — 10 assets by status")
        print("  📊  Traffic Bar       — Sessions this week vs last week")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CB247 Visual Marketing Dashboard")
    parser.add_argument("--setup",  action="store_true", help="First run: create dashboard page")
    parser.add_argument("--update", action="store_true", help="Refresh dashboard with latest data + charts")
    args = parser.parse_args()

    if not NOTION_API_KEY:
        print("[Dashboard] ERROR: NOTION_API_KEY not set in .env")
        return
    if args.setup and not NOTION_PARENT_PAGE_ID:
        print("[Dashboard] ERROR: NOTION_PARENT_PAGE_ID not set in .env")
        return

    client = NotionClient(NOTION_API_KEY)

    if args.setup:
        run(client, is_setup=True)
    elif args.update:
        run(client, is_setup=False)
    else:
        print("[Dashboard] Use --setup (first run) or --update (refresh)")
        print("  python3 scripts/push_dashboard.py --setup")
        print("  python3 scripts/push_dashboard.py --update")


if __name__ == "__main__":
    main()
