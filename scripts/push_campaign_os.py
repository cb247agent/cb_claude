"""
push_campaign_os.py — CB247 Campaign Delivery OS for Notion.

Creates a full campaign management workspace under CB247 Marketing Hub:
  🎯 Campaign Delivery OS  — Home page with navigation + status overview
  📋 Campaigns DB          — Master list: status, type, location, budget, dates, KPI
  🎨 Content Assets DB     — Every deliverable: copy, creatives, blogs, emails, ads
  💰 Ad Spend Tracker DB   — Weekly spend by campaign and platform

Relations:
  Content Assets → Campaigns (via relation)
  Ad Spend       → Campaigns (via relation)

Usage:
  python3 scripts/push_campaign_os.py --setup    # First run: builds full structure
  python3 scripts/push_campaign_os.py --update   # Refresh home page KPI callouts
"""

import json
import os
import sys
import time
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

try:
    import requests
except ImportError:
    print("[CampaignOS] requests not installed. Run: pip install requests")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
STATE_DIR = BASE_DIR / "state"
OS_IDS_FILE = STATE_DIR / "campaign-os-ids.json"

NOTION_API_KEY        = os.getenv("NOTION_API_KEY", "")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "")
NOTION_VERSION        = "2022-06-28"
NOTION_BASE           = "https://api.notion.com/v1"


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
                    print(f"[CampaignOS] Rate limited — waiting {wait}s...")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except requests.HTTPError:
                if attempt == retries - 1:
                    print(f"[CampaignOS] API error {r.status_code}: {r.text[:300]}")
                    raise
                time.sleep(1 + attempt)
        raise RuntimeError("[CampaignOS] Max retries exceeded")

    def create_page(self, parent_id, title, children=None, icon="📋", cover=None):
        body = {
            "parent": {"page_id": parent_id},
            "icon": {"type": "emoji", "emoji": icon},
            "properties": {"title": {"title": [{"text": {"content": title}}]}},
        }
        if cover:
            body["cover"] = {"type": "external", "external": {"url": cover}}
        if children:
            body["children"] = children[:100]
        result = self._req("post", "pages", body)
        if children and len(children) > 100:
            time.sleep(0.3)
            self.append_blocks(result["id"], children[100:])
        return result

    def create_database(self, parent_id, title, properties, icon="📋"):
        body = {
            "parent": {"page_id": parent_id},
            "icon": {"type": "emoji", "emoji": icon},
            "title": [{"text": {"content": title}}],
            "properties": properties,
        }
        return self._req("post", "databases", body)

    def create_db_item(self, db_id, properties, children=None):
        body = {"parent": {"database_id": db_id}, "properties": properties}
        if children:
            body["children"] = children[:100]
        return self._req("post", "pages", body)

    def append_blocks(self, block_id, children):
        for i in range(0, len(children), 100):
            batch = children[i:i + 100]
            self._req("patch", f"blocks/{block_id}/children", {"children": batch})
            if i + 100 < len(children):
                time.sleep(0.3)

    def clear_page(self, page_id):
        results = []
        cursor = None
        while True:
            qs = "?page_size=100"
            if cursor:
                qs += f"&start_cursor={cursor}"
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

    def update_page(self, page_id, properties=None, icon=None):
        body = {}
        if properties:
            body["properties"] = properties
        if icon:
            body["icon"] = {"type": "emoji", "emoji": icon}
        return self._req("patch", f"pages/{page_id}", body)


# =============================================================================
# Block Builders
# =============================================================================

def rt(text, bold=False, italic=False, color="default", link=None):
    obj = {
        "type": "text",
        "text": {"content": str(text)[:2000]},
        "annotations": {"bold": bold, "italic": italic, "color": color},
    }
    if link:
        obj["text"]["link"] = {"url": link}
    return obj

def h1(text):
    return {"object": "block", "type": "heading_1",
            "heading_1": {"rich_text": [rt(text)]}}

def h2(text):
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [rt(text)]}}

def h3(text):
    return {"object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [rt(text)]}}

def para(text="", bold=False):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [rt(text, bold=bold)] if text else []}}

def bullet(text, bold=False):
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [rt(text, bold=bold)]}}

def numbered(text):
    return {"object": "block", "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": [rt(text)]}}

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

def toggle(title, children=None):
    block = {
        "object": "block", "type": "toggle",
        "toggle": {"rich_text": [rt(title, bold=True)], "children": children or []}
    }
    return block

def column_list(left_blocks, right_blocks):
    """Two-column layout block."""
    return {
        "object": "block",
        "type": "column_list",
        "column_list": {
            "children": [
                {"object": "block", "type": "column", "column": {"children": left_blocks}},
                {"object": "block", "type": "column", "column": {"children": right_blocks}},
            ]
        }
    }


# =============================================================================
# Database Schemas
# =============================================================================

def campaigns_db_schema():
    return {
        "Name": {"title": {}},
        "Status": {"select": {"options": [
            {"name": "Planning",       "color": "gray"},
            {"name": "Brief Approved", "color": "purple"},
            {"name": "In Delivery",    "color": "yellow"},
            {"name": "Live",           "color": "green"},
            {"name": "Paused",         "color": "orange"},
            {"name": "Complete",       "color": "blue"},
        ]}},
        "Type": {"select": {"options": [
            {"name": "Google Ads",    "color": "blue"},
            {"name": "Meta Ads",      "color": "pink"},
            {"name": "SEO Content",   "color": "green"},
            {"name": "Email",         "color": "purple"},
            {"name": "Social",        "color": "orange"},
            {"name": "Event",         "color": "yellow"},
            {"name": "Brand",         "color": "red"},
        ]}},
        "Location": {"select": {"options": [
            {"name": "Malaga",      "color": "blue"},
            {"name": "Ellenbrook",  "color": "green"},
            {"name": "Both",        "color": "purple"},
        ]}},
        "Weekly Budget ($)": {"number": {"format": "dollar"}},
        "Start Date":         {"date": {}},
        "End Date":           {"date": {}},
        "KPI Target":         {"rich_text": {}},
        "Owner":              {"rich_text": {}},
        "Notes":              {"rich_text": {}},
    }


def content_assets_db_schema(campaigns_db_id):
    return {
        "Asset Name": {"title": {}},
        "Campaign": {"relation": {
            "database_id": campaigns_db_id,
            "single_property": {},
        }},
        "Type": {"select": {"options": [
            {"name": "Ad Copy",       "color": "blue"},
            {"name": "Creative",      "color": "pink"},
            {"name": "Video",         "color": "red"},
            {"name": "Blog Post",     "color": "green"},
            {"name": "Email",         "color": "purple"},
            {"name": "SMS",           "color": "yellow"},
            {"name": "Social Post",   "color": "orange"},
            {"name": "Landing Page",  "color": "gray"},
        ]}},
        "Platform": {"select": {"options": [
            {"name": "Google",    "color": "blue"},
            {"name": "Meta",      "color": "pink"},
            {"name": "Instagram", "color": "orange"},
            {"name": "Facebook",  "color": "blue"},
            {"name": "Email",     "color": "purple"},
            {"name": "Website",   "color": "green"},
            {"name": "TikTok",    "color": "red"},
            {"name": "SMS",       "color": "yellow"},
        ]}},
        "Status": {"select": {"options": [
            {"name": "Not Started", "color": "gray"},
            {"name": "Draft",       "color": "yellow"},
            {"name": "In Review",   "color": "orange"},
            {"name": "Approved",    "color": "blue"},
            {"name": "Scheduled",   "color": "purple"},
            {"name": "Published",   "color": "green"},
        ]}},
        "Due Date": {"date": {}},
        "Owner":    {"rich_text": {}},
        "Notes":    {"rich_text": {}},
    }


def ad_spend_db_schema(campaigns_db_id):
    return {
        "Item":     {"title": {}},
        "Campaign": {"relation": {
            "database_id": campaigns_db_id,
            "single_property": {},
        }},
        "Platform": {"select": {"options": [
            {"name": "Google Ads", "color": "blue"},
            {"name": "Meta Ads",   "color": "pink"},
            {"name": "Other",      "color": "gray"},
        ]}},
        "Weekly ($)":  {"number": {"format": "dollar"}},
        "Monthly ($)": {"number": {"format": "dollar"}},
        "Period":      {"date": {}},
        "Status": {"select": {"options": [
            {"name": "Pending",   "color": "yellow"},
            {"name": "Confirmed", "color": "green"},
            {"name": "Invoiced",  "color": "blue"},
            {"name": "Paused",    "color": "red"},
        ]}},
        "Notes": {"rich_text": {}},
    }


# =============================================================================
# Pre-populated Data
# =============================================================================

def get_campaigns():
    """CB247's current active campaigns + planned."""
    today = date.today().isoformat()
    return [
        {
            "name": "Malaga Membership — Google Ads",
            "status": "Live",
            "type": "Google Ads",
            "location": "Malaga",
            "budget": 137,
            "start": "2026-01-01",
            "end": None,
            "kpi": "CPL ≤ $20 | Target: 7 conversions/week",
            "owner": "Tia",
            "notes": "Targeting 'gym malaga' keyword. Pause when organic hits #1–3.",
        },
        {
            "name": "Ellenbrook Membership — Google Ads",
            "status": "Live",
            "type": "Google Ads",
            "location": "Ellenbrook",
            "budget": 386,
            "start": "2026-01-01",
            "end": None,
            "kpi": "CPL ≤ $20 | Target: 19 conversions/week",
            "owner": "Tia",
            "notes": "High spend — /ellenbrook SEO page is priority to reduce dependency.",
        },
        {
            "name": "Malaga SEO — Organic Rankings",
            "status": "In Delivery",
            "type": "SEO Content",
            "location": "Malaga",
            "budget": 0,
            "start": "2026-05-30",
            "end": None,
            "kpi": "'gym malaga' from #5 → #1–3 within 12 weeks",
            "owner": "Tia",
            "notes": "H1 fixes + blog post + schema = expected 6–12 weeks to #1.",
        },
        {
            "name": "Ellenbrook SEO — New Landing Page",
            "status": "Planning",
            "type": "SEO Content",
            "location": "Ellenbrook",
            "budget": 0,
            "start": "2026-06-01",
            "end": None,
            "kpi": "'gym ellenbrook' from #4 → #1 within 8 weeks. Saves ~$386/wk ads.",
            "owner": "Tia",
            "notes": "File ready: outputs/seo/page-ellenbrook-2026-05-30.md — needs publishing.",
        },
        {
            "name": "FIFO Members — Retention Email",
            "status": "Planning",
            "type": "Email",
            "location": "Both",
            "budget": 0,
            "start": "2026-06-01",
            "end": None,
            "kpi": "Freeze rate ↓ | Re-activation rate ↑ 10%",
            "owner": "Tia",
            "notes": "Target FIFO members going off-roster. Promote freeze benefit.",
        },
        {
            "name": "Kids Hub — School Holidays Promo",
            "status": "Planning",
            "type": "Social",
            "location": "Both",
            "budget": 0,
            "start": "2026-07-01",
            "end": "2026-07-20",
            "kpi": "Kids Hub trial sign-ups ↑ 20% during school holidays",
            "owner": "Tia",
            "notes": "School holidays July 5–20. Instagram + Facebook organic.",
        },
    ]


def get_content_assets():
    """CB247 content assets — maps to campaign index (0-based)."""
    return [
        # Malaga Google Ads (campaign index 0)
        {"name": "Malaga Membership — Google Responsive Search Ads", "campaign_idx": 0,
         "type": "Ad Copy", "platform": "Google", "status": "Published",
         "due": "2026-01-01", "owner": "Tia",
         "notes": "Live in Google Ads. Review copy monthly for CTR improvements."},
        # Ellenbrook Google Ads (campaign index 1)
        {"name": "Ellenbrook Membership — Google Responsive Search Ads", "campaign_idx": 1,
         "type": "Ad Copy", "platform": "Google", "status": "Published",
         "due": "2026-01-01", "owner": "Tia",
         "notes": "Live in Google Ads. High CPL — review ad copy and landing page."},
        # Malaga SEO (campaign index 2)
        {"name": "Blog: Best Gym in Malaga Perth", "campaign_idx": 2,
         "type": "Blog Post", "platform": "Website", "status": "Draft",
         "due": "2026-06-07", "owner": "Tia",
         "notes": "File: outputs/seo/blog-best-gym-malaga-2026-05-30.md — ready to publish."},
        {"name": "H1 Tags — 29 Pages Fix", "campaign_idx": 2,
         "type": "Landing Page", "platform": "Website", "status": "Not Started",
         "due": "2026-06-07", "owner": "Tia",
         "notes": "File: outputs/seo/h1-recommendations-2026-05-30.md — dev task, 29 pages."},
        {"name": "LocalBusiness Schema Markup", "campaign_idx": 2,
         "type": "Landing Page", "platform": "Website", "status": "Not Started",
         "due": "2026-06-07", "owner": "Tia",
         "notes": "File: outputs/seo/schema-local-business-2026-05-30.md — copy JSON-LD into <head>."},
        {"name": "Massage Page Expansion", "campaign_idx": 2,
         "type": "Landing Page", "platform": "Website", "status": "Draft",
         "due": "2026-06-14", "owner": "Tia",
         "notes": "File: outputs/seo/page-massage-2026-05-30.md — 1,300 searches/month at #16."},
        # Ellenbrook SEO (campaign index 3)
        {"name": "Ellenbrook Location Landing Page", "campaign_idx": 3,
         "type": "Landing Page", "platform": "Website", "status": "Draft",
         "due": "2026-06-14", "owner": "Tia",
         "notes": "File: outputs/seo/page-ellenbrook-2026-05-30.md — page doesn't exist yet."},
        # FIFO Email (campaign index 4)
        {"name": "FIFO Freeze — Email Sequence (4 emails + 2 SMS)", "campaign_idx": 4,
         "type": "Email", "platform": "Email", "status": "Not Started",
         "due": "2026-06-15", "owner": "Tia",
         "notes": "Brief in outputs/seo/page-fifo-2026-05-30.md. Run /email-funnel skill."},
        # Kids Hub (campaign index 5)
        {"name": "Kids Hub — School Holidays Instagram Posts (5x)", "campaign_idx": 5,
         "type": "Social Post", "platform": "Instagram", "status": "Not Started",
         "due": "2026-06-28", "owner": "Tia",
         "notes": "School holidays Jul 5–20. Use Kids Hub photos. Run /content-agent."},
        {"name": "Kids Hub — Facebook Event Post", "campaign_idx": 5,
         "type": "Social Post", "platform": "Facebook", "status": "Not Started",
         "due": "2026-06-28", "owner": "Tia",
         "notes": "Create Facebook event for Kids Hub school holiday sessions."},
    ]


def get_ad_spend():
    """Current weekly ad spend entries."""
    return [
        {"item": "Malaga Membership — Google Ads (May 2026)", "campaign_idx": 0,
         "platform": "Google Ads", "weekly": 137, "monthly": 593,
         "period": "2026-05-01", "status": "Confirmed",
         "notes": "~$593/month. Pause target: when 'gym malaga' hits organic #1–3."},
        {"item": "Ellenbrook Membership — Google Ads (May 2026)", "campaign_idx": 1,
         "platform": "Google Ads", "weekly": 386, "monthly": 1672,
         "period": "2026-05-01", "status": "Confirmed",
         "notes": "~$1,672/month. Highest priority to reduce via /ellenbrook SEO page."},
    ]


# =============================================================================
# Home Page Content
# =============================================================================

def build_home_blocks(ids):
    """Builds the Campaign Delivery OS home page."""
    today = datetime.utcnow().strftime("%d %B %Y")
    blocks = []

    # Header callout
    blocks.append(callout(
        f"CB247 Campaign Delivery OS  |  Last updated: {today}  |  "
        "Total weekly ad spend: $523  |  2 campaigns live  |  4 SEO tasks in delivery",
        "🎯", "blue_background"
    ))
    blocks.append(divider())

    # Quick actions
    blocks.append(h2("⚡ Quick Actions"))
    blocks.append(para("Use the database links below to add items:"))
    blocks.append(bullet("📋  New campaign → open Campaigns DB → + New"))
    blocks.append(bullet("🎨  New content asset → open Content Assets DB → + New"))
    blocks.append(bullet("💰  New spend entry → open Ad Spend Tracker DB → + New"))
    blocks.append(divider())

    # Status overview
    blocks.append(h2("📊 Live Status — May 2026"))
    blocks.append(para(""))

    # Left column: campaigns summary / Right column: spend summary
    left = [
        h3("🟢 Live Campaigns"),
        bullet("Malaga Membership — Google Ads  |  $137/wk  |  CPL target $20"),
        bullet("Ellenbrook Membership — Google Ads  |  $386/wk  |  CPL target $20"),
        para(""),
        h3("🟡 In Delivery"),
        bullet("Malaga SEO — H1 fixes + blog post + schema"),
        para(""),
        h3("⚪ Planning"),
        bullet("Ellenbrook SEO Landing Page"),
        bullet("FIFO Retention Email"),
        bullet("Kids Hub School Holidays"),
    ]
    right = [
        h3("💰 Weekly Ad Spend"),
        bullet("Malaga: $137/wk  (~$593/mo)"),
        bullet("Ellenbrook: $386/wk  (~$1,672/mo)"),
        bullet("Total: $523/wk  (~$2,265/mo)", bold=True),
        para(""),
        h3("🎯 SEO Pipeline"),
        bullet("🔴 Critical: H1 tags (29 pages)"),
        bullet("🔴 Critical: Disavow file (37 toxic domains)"),
        bullet("🟠 High: Ellenbrook landing page"),
        bullet("🟡 Medium: Malaga blog post"),
    ]
    blocks.append(column_list(left, right))
    blocks.append(divider())

    # Priorities this week
    blocks.append(h2("🔥 This Week's Priorities"))
    blocks.append(todo("Submit disavow file → GSC disavow tool (search.google.com/search-console/disavow-links)"))
    blocks.append(todo("Fix 3 broken pages → add 301 redirects (file: redirect-map-2026-05-30.md)"))
    blocks.append(todo("Add H1 tags to 29 pages (file: h1-recommendations-2026-05-30.md)"))
    blocks.append(todo("Publish blog post: Best Gym in Malaga Perth (file: blog-best-gym-malaga-2026-05-30.md)"))
    blocks.append(todo("Create Ellenbrook landing page (file: page-ellenbrook-2026-05-30.md)"))
    blocks.append(divider())

    # How to use
    blocks.append(h2("📖 How to Use This OS"))
    blocks.append(numbered("Browse the 3 databases below (Campaigns, Content Assets, Ad Spend)"))
    blocks.append(numbered("When starting a task → change Status to 'In Delivery'"))
    blocks.append(numbered("When complete → change Status to 'Complete' or 'Published'"))
    blocks.append(numbered("Every Monday — Weekly Performance page auto-updates with Google Ads + SEO data"))
    blocks.append(numbered("Add meeting notes → Team Briefings page → run /meeting commands in Claude Code"))
    blocks.append(divider())

    # Workflow guide
    blocks.append(h2("🔄 Campaign Workflow"))
    blocks.append(para("Planning → Brief Approved → In Delivery → Live → Complete", bold=True))
    blocks.append(para(""))
    blocks.append(bullet("Planning: Idea captured, KPI defined, budget set"))
    blocks.append(bullet("Brief Approved: Brief reviewed, assets assigned, timeline confirmed"))
    blocks.append(bullet("In Delivery: Content being created, ads being built"))
    blocks.append(bullet("Live: Campaign is running, assets published"))
    blocks.append(bullet("Complete: Campaign ended, performance reviewed, learnings documented"))
    blocks.append(divider())

    # SEO impact projections
    blocks.append(h2("📈 SEO Impact — When Delivered"))
    blocks.append(callout(
        "'gym malaga' #5 → #1–3  |  'gym ellenbrook' #4 → #1  |  "
        "Monthly ad savings: ~$1,900/month  |  Domain Rating 7 → 15+",
        "💡", "green_background"
    ))
    blocks.append(divider())
    blocks.append(para(f"Generated by CB247 Marketing Agent | {today}"))

    return blocks


# =============================================================================
# Setup
# =============================================================================

def setup(client, parent_id):
    print("[CampaignOS] Building Campaign Delivery OS...")
    ids = {}

    # ── 1. Home page ────────────────────────────────────────────────────────
    print("[CampaignOS]   Creating 🎯 Campaign Delivery OS home page...")
    home = client.create_page(
        parent_id,
        "🎯 Campaign Delivery OS",
        children=[para("Setting up...")],
        icon="🎯"
    )
    ids["home_page_id"] = home["id"]
    time.sleep(0.5)

    # ── 2. Campaigns DB ─────────────────────────────────────────────────────
    print("[CampaignOS]   Creating 📋 Campaigns database...")
    campaigns_db = client.create_database(
        ids["home_page_id"],
        "📋 Campaigns",
        campaigns_db_schema(),
        icon="📋"
    )
    ids["campaigns_db_id"] = campaigns_db["id"]
    time.sleep(0.5)

    # ── 3. Content Assets DB (with relation to Campaigns) ──────────────────
    print("[CampaignOS]   Creating 🎨 Content Assets database...")
    assets_db = client.create_database(
        ids["home_page_id"],
        "🎨 Content Assets",
        content_assets_db_schema(ids["campaigns_db_id"]),
        icon="🎨"
    )
    ids["content_assets_db_id"] = assets_db["id"]
    time.sleep(0.5)

    # ── 4. Ad Spend Tracker DB (with relation to Campaigns) ────────────────
    print("[CampaignOS]   Creating 💰 Ad Spend Tracker database...")
    spend_db = client.create_database(
        ids["home_page_id"],
        "💰 Ad Spend Tracker",
        ad_spend_db_schema(ids["campaigns_db_id"]),
        icon="💰"
    )
    ids["ad_spend_db_id"] = spend_db["id"]
    time.sleep(0.5)

    # ── 5. Populate Campaigns DB ────────────────────────────────────────────
    print("[CampaignOS]   Populating Campaigns database...")
    campaign_page_ids = []
    for c in get_campaigns():
        props = {
            "Name":              {"title":  [{"text": {"content": c["name"]}}]},
            "Status":            {"select": {"name": c["status"]}},
            "Type":              {"select": {"name": c["type"]}},
            "Location":          {"select": {"name": c["location"]}},
            "Weekly Budget ($)": {"number": c["budget"]},
            "KPI Target":        {"rich_text": [{"text": {"content": c["kpi"]}}]},
            "Owner":             {"rich_text": [{"text": {"content": c["owner"]}}]},
            "Notes":             {"rich_text": [{"text": {"content": c["notes"]}}]},
        }
        if c["start"]:
            props["Start Date"] = {"date": {"start": c["start"]}}
        if c["end"]:
            props["End Date"] = {"date": {"start": c["end"]}}

        page = client.create_db_item(ids["campaigns_db_id"], props)
        campaign_page_ids.append(page["id"])
        time.sleep(0.25)

    print(f"[CampaignOS]   ✅ {len(campaign_page_ids)} campaigns added")

    # ── 6. Populate Content Assets DB ──────────────────────────────────────
    print("[CampaignOS]   Populating Content Assets database...")
    for asset in get_content_assets():
        idx = asset["campaign_idx"]
        campaign_id = campaign_page_ids[idx] if idx < len(campaign_page_ids) else None

        props = {
            "Asset Name": {"title":  [{"text": {"content": asset["name"]}}]},
            "Type":       {"select": {"name": asset["type"]}},
            "Platform":   {"select": {"name": asset["platform"]}},
            "Status":     {"select": {"name": asset["status"]}},
            "Owner":      {"rich_text": [{"text": {"content": asset["owner"]}}]},
            "Notes":      {"rich_text": [{"text": {"content": asset["notes"]}}]},
        }
        if asset.get("due"):
            props["Due Date"] = {"date": {"start": asset["due"]}}
        if campaign_id:
            props["Campaign"] = {"relation": [{"id": campaign_id}]}

        client.create_db_item(ids["content_assets_db_id"], props)
        time.sleep(0.25)

    print(f"[CampaignOS]   ✅ {len(get_content_assets())} content assets added")

    # ── 7. Populate Ad Spend DB ─────────────────────────────────────────────
    print("[CampaignOS]   Populating Ad Spend Tracker...")
    for spend in get_ad_spend():
        idx = spend["campaign_idx"]
        campaign_id = campaign_page_ids[idx] if idx < len(campaign_page_ids) else None

        props = {
            "Item":        {"title":  [{"text": {"content": spend["item"]}}]},
            "Platform":    {"select": {"name": spend["platform"]}},
            "Weekly ($)":  {"number": spend["weekly"]},
            "Monthly ($)": {"number": spend["monthly"]},
            "Status":      {"select": {"name": spend["status"]}},
            "Notes":       {"rich_text": [{"text": {"content": spend["notes"]}}]},
        }
        if spend.get("period"):
            props["Period"] = {"date": {"start": spend["period"]}}
        if campaign_id:
            props["Campaign"] = {"relation": [{"id": campaign_id}]}

        client.create_db_item(ids["ad_spend_db_id"], props)
        time.sleep(0.25)

    print(f"[CampaignOS]   ✅ {len(get_ad_spend())} spend entries added")

    # ── 8. Update home page with full content ──────────────────────────────
    print("[CampaignOS]   Building home page content...")
    client.clear_page(ids["home_page_id"])
    time.sleep(0.3)
    home_blocks = build_home_blocks(ids)
    client.append_blocks(ids["home_page_id"], home_blocks)
    print(f"[CampaignOS]   ✅ Home page built ({len(home_blocks)} blocks)")

    # ── 9. Save IDs ─────────────────────────────────────────────────────────
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OS_IDS_FILE.write_text(json.dumps(ids, indent=2))
    print(f"[CampaignOS] IDs saved → {OS_IDS_FILE}")

    return ids


def update_home(client):
    """Refresh the home page KPI callouts with latest data."""
    if not OS_IDS_FILE.exists():
        print("[CampaignOS] Not set up yet. Run: python3 scripts/push_campaign_os.py --setup")
        return
    ids = json.loads(OS_IDS_FILE.read_text())
    print("[CampaignOS] Refreshing home page...")
    client.clear_page(ids["home_page_id"])
    time.sleep(0.3)
    blocks = build_home_blocks(ids)
    client.append_blocks(ids["home_page_id"], blocks)
    print(f"[CampaignOS] ✅ Home page refreshed ({len(blocks)} blocks)")


# =============================================================================
# Main
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="CB247 Campaign Delivery OS for Notion")
    parser.add_argument("--setup",  action="store_true", help="First run: build full OS structure")
    parser.add_argument("--update", action="store_true", help="Refresh home page KPI summary")
    args = parser.parse_args()

    if not NOTION_API_KEY:
        print("[CampaignOS] ERROR: NOTION_API_KEY not set in .env")
        return

    if not NOTION_PARENT_PAGE_ID and args.setup:
        print("[CampaignOS] ERROR: NOTION_PARENT_PAGE_ID not set in .env")
        return

    client = NotionClient(NOTION_API_KEY)

    if args.setup:
        ids = setup(client, NOTION_PARENT_PAGE_ID)
        print()
        print("[CampaignOS] ✅ Campaign Delivery OS is live!")
        print("[CampaignOS] Open Notion → CB247 Marketing Hub → 🎯 Campaign Delivery OS")
        print()
        print("What's inside:")
        print("  📋 Campaigns       — 6 campaigns pre-loaded (2 live, 1 in delivery, 3 planning)")
        print("  🎨 Content Assets  — 10 assets with status + due dates + file references")
        print("  💰 Ad Spend        — 2 entries ($523/wk total) with monthly projections")
        print()
        print("Next steps:")
        print("  1. Open the OS in Notion and review each database")
        print("  2. Assign owners to each content asset")
        print("  3. Update status as work is completed")
        print("  4. Add new campaigns as they're planned")
        return

    if args.update:
        update_home(client)
        return

    print("[CampaignOS] Specify --setup (first run) or --update (refresh home page)")
    print("  python3 scripts/push_campaign_os.py --setup")
    print("  python3 scripts/push_campaign_os.py --update")


if __name__ == "__main__":
    main()
