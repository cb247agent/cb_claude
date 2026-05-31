"""
send_team_emails.py — Role-specific email delivery for CB247 Marketing OS.

APPROVAL FLOW:
  1. weekly-report.sh calls send_weekly_report.py --recipient tia  (OS report, Tia reviews)
  2. Tia runs: python send_team_emails.py --approve  (sends all team emails)
  3. OR individual: python send_team_emails.py --role jane

Emails sent (all Monday morning, after Tia approves):
  Ange   → Strategic brief + KPI snapshot + decisions needed
  Jane   → Full content pipeline for QC/approval
  John   → SEO brief + ranking report + technical tasks
  Mark   → Dev/technical task list with implementation details
  Agust  → Reel scripts + video briefs
  Ivan   → Reel scripts + video briefs
  Shauna → Content calendar + captions + blog drafts
  Joanne → APPROVED content only + posting schedule (after Jane approves)

Usage:
  python scripts/send_team_emails.py --approve        # Send all team emails
  python scripts/send_team_emails.py --role jane      # Send to Jane only
  python scripts/send_team_emails.py --dry-run        # Print emails without sending
  python scripts/send_team_emails.py --list           # List latest agent outputs

Requirements in .env:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
  TEAM_EMAIL_ANGE, TEAM_EMAIL_JANE, TEAM_EMAIL_JOHN, TEAM_EMAIL_MARK
  TEAM_EMAIL_AGUST, TEAM_EMAIL_IVAN, TEAM_EMAIL_SHAUNA, TEAM_EMAIL_JOANNE
"""

import argparse
import json
import os
import re
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR  = Path(__file__).resolve().parent.parent
OUTPUTS   = BASE_DIR / "outputs"
STATE_DIR = BASE_DIR / "state"
load_dotenv(BASE_DIR / ".env")

DATE = datetime.now().strftime("%Y-%m-%d")
WEEK = datetime.now().strftime("%-d %B %Y")   # e.g. "2 June 2026"

# ── SMTP config ──
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", ""))

# ── Team emails ──
TEAM = {
    "ange":   os.getenv("TEAM_EMAIL_ANGE",   "ange@chasingbetter247.com.au"),
    "jane":   os.getenv("TEAM_EMAIL_JANE",   "jane@chasingbetter247.com.au"),
    "john":   os.getenv("TEAM_EMAIL_JOHN",   "john@chasingbetter247.com.au"),
    "mark":   os.getenv("TEAM_EMAIL_MARK",   "mark@chasingbetter247.com.au"),
    "agust":  os.getenv("TEAM_EMAIL_AGUST",  "agust@chasingbetter247.com.au"),
    "ivan":   os.getenv("TEAM_EMAIL_IVAN",   "ivan@chasingbetter247.com.au"),
    "shauna": os.getenv("TEAM_EMAIL_SHAUNA", "shauna@chasingbetter247.com.au"),
    "joanne": os.getenv("TEAM_EMAIL_JOANNE", "joanne@chasingbetter247.com.au"),
}

BRAND_COLOR = "#3FA69A"
BRAND_DARK  = "#2d7a70"


# ─────────────────────────────────────────────
# File loaders
# ─────────────────────────────────────────────

def load_file(path):
    """Load text file content. Returns empty string if missing."""
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return f"[File not found: {p.name}]"


def load_json(path):
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def find_latest(folder, pattern):
    """Find the most recent file matching pattern in folder."""
    folder = Path(folder)
    matches = sorted(folder.glob(pattern), reverse=True)
    return matches[0] if matches else None


def get_output_paths():
    """Resolve the latest agent output files."""
    return {
        "strategy":   find_latest(OUTPUTS / "blueprints", f"weekly-strategy-{DATE}.md")
                      or find_latest(OUTPUTS / "blueprints", "weekly-strategy-*.md"),
        "seo":        find_latest(OUTPUTS / "seo",       f"weekly-seo-brief-{DATE}.md")
                      or find_latest(OUTPUTS / "seo",     "weekly-seo-brief-*.md"),
        "content":    find_latest(OUTPUTS / "content",    f"weekly-content-{DATE}.md")
                      or find_latest(OUTPUTS / "content",  "weekly-content-*.md"),
        "research":   find_latest(OUTPUTS / "research",   f"weekly-research-{DATE}.md")
                      or find_latest(OUTPUTS / "research",  "weekly-research-*.md"),
        "audience":   find_latest(OUTPUTS / "research",   f"audience-weekly-{DATE}.md")
                      or find_latest(OUTPUTS / "research",  "audience-weekly-*.md"),
        "competitor": find_latest(OUTPUTS / "research",   f"competitor-weekly-{DATE}.md")
                      or find_latest(OUTPUTS / "research",  "competitor-weekly-*.md"),
        "paid_ads":   find_latest(OUTPUTS / "research",   f"paid-ads-weekly-{DATE}.md")
                      or find_latest(OUTPUTS / "research",  "paid-ads-weekly-*.md"),
        "performance":find_latest(OUTPUTS / "research",   f"performance-week-{DATE}.md")
                      or find_latest(OUTPUTS / "research",  "performance-week-*.md"),
    }


def extract_section(text, heading, max_chars=3000):
    """Extract a section from markdown by heading (case-insensitive)."""
    if not text:
        return ""
    # Match ## HEADING or **HEADING** or # HEADING
    pattern = rf"(?:^|\n)#{1,3}\s*{re.escape(heading)}.*?\n(.*?)(?=\n#{1,3}\s|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()[:max_chars]
    return ""


# ─────────────────────────────────────────────
# HTML email builder
# ─────────────────────────────────────────────

def html_email(subject, recipient_name, role_tag, content_html, footer_note=""):
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f5; margin: 0; padding: 0; color: #1a1a1a; }}
  .wrapper {{ max-width: 680px; margin: 0 auto; background: #fff; }}
  .header {{ background: linear-gradient(135deg, {BRAND_COLOR} 0%, {BRAND_DARK} 100%);
             padding: 32px 40px; color: #fff; }}
  .header h1 {{ margin: 0 0 4px; font-size: 22px; font-weight: 700; }}
  .header p  {{ margin: 0; opacity: 0.85; font-size: 14px; }}
  .role-tag  {{ display: inline-block; background: rgba(255,255,255,0.2);
               border-radius: 20px; padding: 4px 14px; font-size: 12px;
               font-weight: 600; letter-spacing: 0.5px; margin-bottom: 12px; }}
  .body      {{ padding: 32px 40px; }}
  .section   {{ margin-bottom: 28px; }}
  .section h2 {{ font-size: 15px; font-weight: 700; color: {BRAND_COLOR};
                margin: 0 0 12px; text-transform: uppercase; letter-spacing: 0.5px;
                border-bottom: 2px solid {BRAND_COLOR}; padding-bottom: 6px; }}
  .kpi-grid  {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .kpi-card  {{ background: #f8fffe; border: 1px solid #e0f2ef; border-radius: 8px;
               padding: 14px 16px; }}
  .kpi-card .label {{ font-size: 11px; color: #666; text-transform: uppercase;
                      letter-spacing: 0.5px; margin-bottom: 4px; }}
  .kpi-card .value {{ font-size: 22px; font-weight: 700; color: {BRAND_COLOR}; }}
  .kpi-card .change {{ font-size: 12px; color: #666; margin-top: 2px; }}
  .task-list {{ list-style: none; padding: 0; margin: 0; }}
  .task-list li {{ padding: 10px 0; border-bottom: 1px solid #f0f0f0;
                   font-size: 14px; line-height: 1.5; }}
  .task-list li:last-child {{ border-bottom: none; }}
  .priority  {{ display: inline-block; border-radius: 4px; padding: 2px 8px;
               font-size: 11px; font-weight: 600; margin-right: 8px; }}
  .p-high    {{ background: #fff3cd; color: #856404; }}
  .p-critical{{ background: #f8d7da; color: #721c24; }}
  .p-medium  {{ background: #d1ecf1; color: #0c5460; }}
  .content-block {{ background: #f8fffe; border-left: 4px solid {BRAND_COLOR};
                    border-radius: 0 8px 8px 0; padding: 16px 20px;
                    margin-bottom: 16px; font-size: 14px; line-height: 1.6; }}
  .content-block pre {{ font-family: inherit; margin: 0; white-space: pre-wrap; }}
  .btn       {{ display: inline-block; background: {BRAND_COLOR}; color: #fff;
               text-decoration: none; padding: 12px 28px; border-radius: 6px;
               font-weight: 600; font-size: 14px; margin-top: 8px; }}
  .footer    {{ background: #f5f5f5; padding: 20px 40px; font-size: 12px;
               color: #999; border-top: 1px solid #e0e0e0; }}
  .tag       {{ display: inline-block; background: #e0f2ef; color: {BRAND_DARK};
               border-radius: 4px; padding: 2px 8px; font-size: 11px;
               font-weight: 600; margin: 2px; }}
  table      {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th         {{ background: {BRAND_COLOR}; color: #fff; padding: 8px 12px;
               text-align: left; font-weight: 600; }}
  td         {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
  tr:hover td{{ background: #f8fffe; }}
  .up        {{ color: #28a745; font-weight: 600; }}
  .down      {{ color: #dc3545; font-weight: 600; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <div class="role-tag">{role_tag}</div>
    <h1>CB247 Marketing OS</h1>
    <p>Week of {WEEK} &nbsp;·&nbsp; Good morning, {recipient_name} 👋</p>
  </div>
  <div class="body">
    {content_html}
  </div>
  <div class="footer">
    CB247 Marketing OS &nbsp;·&nbsp; {subject} &nbsp;·&nbsp; {DATE}
    {"<br>" + footer_note if footer_note else ""}
    <br>Dashboard: <a href="https://cb247agent.github.io/cb_claude/">cb247agent.github.io/cb_claude</a>
  </div>
</div>
</body>
</html>"""


def md_to_simple_html(md_text, max_chars=4000):
    """Very light markdown → HTML conversion for email body sections."""
    if not md_text:
        return "<p><em>No data available.</em></p>"
    text = md_text[:max_chars]
    lines = text.split("\n")
    html_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("### "):
            html_lines.append(f"<h4 style='color:{BRAND_COLOR};margin:16px 0 6px'>{line[4:]}</h4>")
        elif line.startswith("## "):
            html_lines.append(f"<h3 style='color:{BRAND_COLOR};margin:20px 0 8px'>{line[3:]}</h3>")
        elif line.startswith("# "):
            html_lines.append(f"<h2 style='color:{BRAND_COLOR};margin:20px 0 8px'>{line[2:]}</h2>")
        elif line.startswith("- ") or line.startswith("* "):
            html_lines.append(f"<li style='margin-bottom:6px'>{line[2:]}</li>")
        elif line.startswith("|"):
            html_lines.append(f"<tr><td>{line.replace('|','</td><td>').strip('</td><td>')}</td></tr>")
        else:
            html_lines.append(f"<p style='margin:6px 0;line-height:1.6'>{line}</p>")
    return "\n".join(html_lines)


def kpi_card(label, value, change=""):
    return f"""<div class="kpi-card">
  <div class="label">{label}</div>
  <div class="value">{value}</div>
  {"<div class='change'>" + change + "</div>" if change else ""}
</div>"""


# ─────────────────────────────────────────────
# Role-specific email builders
# ─────────────────────────────────────────────

def build_ange_email(paths):
    """Ange (Brand Manager) — Strategic brief + KPI snapshot + decisions needed."""
    strategy = load_file(paths["strategy"]) if paths["strategy"] else ""
    performance = load_file(paths["performance"]) if paths["performance"] else ""
    ga4 = load_json(STATE_DIR / "ga4-data.json")
    ahrefs = load_json(STATE_DIR / "ahrefs-data.json")

    sessions = (ga4.get("summary", {}) or {}).get("sessions", "–")
    conversions = (ga4.get("summary", {}) or {}).get("conversions", "–")
    organic_value = ((ahrefs.get("organic_value") or {}).get("current_week") or {}).get("organic_traffic_value")
    organic_value_str = f"${organic_value:,.0f}" if organic_value else "–"

    scorecard = extract_section(strategy, "WEEKLY SCORECARD", 800)
    priorities = extract_section(strategy, "TOP 5 PRIORITIES", 1500)
    decisions = extract_section(strategy, "DECISIONS NEEDED", 1200)
    narrative = extract_section(strategy, "WEEKLY NARRATIVE", 500)

    content = f"""
<div class="section">
  <h2>Weekly Scorecard</h2>
  <div class="kpi-grid">
    {kpi_card("Sessions", str(sessions), "this week")}
    {kpi_card("Conversions", str(conversions), "this week")}
    {kpi_card("Organic Value", organic_value_str, "equiv. ad spend replaced")}
    {kpi_card("Dashboard", '<a href="https://cb247agent.github.io/cb_claude/" style="color:#3FA69A;font-size:14px">View Live →</a>', "")}
  </div>
</div>

<div class="section">
  <h2>This Week's Narrative</h2>
  <div class="content-block">
    <pre>{narrative or "See strategy document for full narrative."}</pre>
  </div>
</div>

<div class="section">
  <h2>Top 5 Priorities</h2>
  <div class="content-block">
    <pre>{priorities or scorecard or "See attached strategy document."}</pre>
  </div>
</div>

<div class="section">
  <h2>Decisions Needed From You</h2>
  <div class="content-block" style="border-left-color:#dc3545">
    <pre>{decisions or "No decisions pending this week."}</pre>
  </div>
</div>
"""
    subject = f"CB247 Weekly Strategic Brief — {WEEK}"
    return subject, TEAM["ange"], html_email(subject, "Ange", "Brand Manager", content)


def build_jane_email(paths):
    """Jane (QC + Execution) — Full content pipeline for review."""
    content = load_file(paths["content"]) if paths["content"] else ""
    content_intel = load_file(paths["research"]) if paths["research"] else ""

    # Split content file into sections
    gbp_posts = extract_section(content, "GBP POSTS", 2000)
    social    = extract_section(content, "SOCIAL POSTS", 2000)
    reels     = extract_section(content, "REEL SCRIPTS", 2000)
    blog      = extract_section(content, "BLOG DRAFTS", 2000)
    meta_ads  = extract_section(content, "META AD COPY", 1500)
    reviews   = extract_section(content, "REVIEW RESPONSE", 1500)

    body = f"""
<div class="section">
  <h2>Your Job This Week</h2>
  <div class="content-block" style="border-left-color:#856404;background:#fff8e1">
    Review all content below. For each piece: ✅ Approve / ✏️ Edit / ❌ Reject.<br>
    <strong>Deadline: Wednesday EOD</strong> — Joanne needs approved content Thursday.<br>
    Reply to this email with changes, or edit the content doc directly.
  </div>
</div>

<div class="section">
  <h2>GBP Posts (4) — Google Business Profile</h2>
  <div class="content-block"><pre>{gbp_posts or "See attached content file."}</pre></div>
</div>

<div class="section">
  <h2>Social Posts (5) — Instagram + TikTok</h2>
  <div class="content-block"><pre>{social or "See attached content file."}</pre></div>
</div>

<div class="section">
  <h2>Reel Scripts (2) — For Agust + Ivan</h2>
  <div class="content-block"><pre>{reels or "See attached content file."}</pre></div>
</div>

<div class="section">
  <h2>Blog Drafts (2) — For John + Shauna to complete</h2>
  <div class="content-block"><pre>{blog or "See attached content file."}</pre></div>
</div>

<div class="section">
  <h2>Meta Ad Copy (3 variations) — When account reinstates</h2>
  <div class="content-block"><pre>{meta_ads or "See attached content file."}</pre></div>
</div>

<div class="section">
  <h2>Review Response Templates (5)</h2>
  <div class="content-block"><pre>{reviews or "See attached content file."}</pre></div>
</div>
"""
    subject = f"CB247 Content Pipeline — Needs Your Review — {WEEK}"
    note = "Once you approve, Tia will release the posting schedule to Joanne."
    return subject, TEAM["jane"], html_email(subject, "Jane", "QC + Execution", body, note)


def build_john_email(paths):
    """John (SEO) — Ranking report + quick wins + content briefs."""
    seo = load_file(paths["seo"]) if paths["seo"] else ""

    ranking_table  = extract_section(seo, "RANKING TABLE", 2500)
    quick_wins     = extract_section(seo, "QUICK WINS", 2000)
    brief_1        = extract_section(seo, "CONTENT BRIEF 1", 2000)
    brief_2        = extract_section(seo, "CONTENT BRIEF 2", 2000)
    backlinks      = extract_section(seo, "BACKLINK REPORT", 1500)
    organic_value  = extract_section(seo, "ORGANIC VALUE", 800)
    ads_offset     = extract_section(seo, "GOOGLE ADS OFFSET", 800)

    body = f"""
<div class="section">
  <h2>Organic Value This Week</h2>
  <div class="content-block">
    <pre>{organic_value or "See SEO brief for organic value data."}</pre>
  </div>
</div>

<div class="section">
  <h2>Keyword Ranking Table (20 priority KWs)</h2>
  <div class="content-block"><pre>{ranking_table or "See SEO brief for ranking data."}</pre></div>
</div>

<div class="section">
  <h2>Quick Wins — Do These First</h2>
  <div class="content-block" style="border-left-color:#28a745;background:#f0fff4">
    <pre>{quick_wins or "See SEO brief for quick wins."}</pre>
  </div>
</div>

<div class="section">
  <h2>Content Brief 1</h2>
  <div class="content-block"><pre>{brief_1 or "See SEO brief for content brief."}</pre></div>
</div>

<div class="section">
  <h2>Content Brief 2</h2>
  <div class="content-block"><pre>{brief_2 or "See SEO brief for content brief."}</pre></div>
</div>

<div class="section">
  <h2>Backlink Actions</h2>
  <div class="content-block"><pre>{backlinks or "See SEO brief for backlink report."}</pre></div>
</div>

<div class="section">
  <h2>Google Ads We Can Now Pause (SEO coverage)</h2>
  <div class="content-block" style="border-left-color:#28a745;background:#f0fff4">
    <pre>{ads_offset or "See SEO brief for pause recommendations."}</pre>
  </div>
</div>
"""
    subject = f"CB247 SEO Tasks — Week of {WEEK}"
    return subject, TEAM["john"], html_email(subject, "John", "SEO Specialist", body)


def build_mark_email(paths):
    """Mark (Web Developer) — Technical SEO tasks with implementation specifics."""
    seo = load_file(paths["seo"]) if paths["seo"] else ""

    quick_wins = extract_section(seo, "QUICK WINS", 3000)
    local_pack = extract_section(seo, "LOCAL PACK", 1000)

    body = f"""
<div class="section">
  <h2>Your Dev Tasks This Week</h2>
  <div class="content-block" style="border-left-color:#0c5460;background:#d1ecf1">
    These are technical SEO changes required to improve our organic rankings.
    Priority order: Critical → High → Medium.<br>
    Questions? Slack John (SEO) or Tia.
  </div>
</div>

<div class="section">
  <h2>Page-Level Fixes (from SEO agent)</h2>
  <div class="content-block">
    <pre>{quick_wins or "No dev tasks this week — check back Monday."}</pre>
  </div>
</div>

<div class="section">
  <h2>Technical Checklist</h2>
  <ul class="task-list">
    <li><span class="priority p-critical">Critical</span> Fix any broken internal links found by Ahrefs</li>
    <li><span class="priority p-high">High</span> Ensure all target pages have unique meta descriptions (&lt;160 chars)</li>
    <li><span class="priority p-high">High</span> Add LocalBusiness schema to Malaga + Ellenbrook location pages</li>
    <li><span class="priority p-medium">Medium</span> Compress images on top 5 pages (target &lt;100kb per image)</li>
    <li><span class="priority p-medium">Medium</span> Check Core Web Vitals on location pages (LCP &lt;2.5s)</li>
  </ul>
</div>

<div class="section">
  <h2>Local Pack Status</h2>
  <div class="content-block"><pre>{local_pack or "See SEO brief for local pack data."}</pre></div>
</div>
"""
    subject = f"CB247 Dev Tasks — Week of {WEEK}"
    return subject, TEAM["mark"], html_email(subject, "Mark", "Web Developer", body)


def build_video_email(paths, name, role):
    """Agust / Ivan (Video Editors) — Reel scripts + briefs."""
    content = load_file(paths["content"]) if paths["content"] else ""
    content_intel = load_file(paths["research"]) if paths["research"] else ""

    reels   = extract_section(content, "REEL SCRIPTS", 3000)
    audio   = extract_section(content_intel, "TRENDING AUDIO", 800)
    formats = extract_section(content_intel, "TOP 3 CONTENT FORMATS", 1500)

    body = f"""
<div class="section">
  <h2>Your Video Briefs This Week</h2>
  <div class="content-block" style="border-left-color:#6f42c1;background:#f3f0ff">
    2 reel scripts ready below. Each has: hook, scene breakdown, CTA, and audio suggestion.
    <strong>Deadline: Filmed + edited by Friday for Joanne to schedule.</strong>
  </div>
</div>

<div class="section">
  <h2>Reel Scripts</h2>
  <div class="content-block"><pre>{reels or "See content file for reel scripts."}</pre></div>
</div>

<div class="section">
  <h2>Trending Audio This Week</h2>
  <div class="content-block"><pre>{audio or "See content intel file for audio recommendations."}</pre></div>
</div>

<div class="section">
  <h2>Winning Formats Right Now</h2>
  <div class="content-block"><pre>{formats or "See content intel for format data."}</pre></div>
</div>
"""
    subject = f"CB247 Video Briefs — Week of {WEEK}"
    return subject, TEAM[name], html_email(subject, name.capitalize(), role, body)


def build_shauna_email(paths):
    """Shauna (CB247 Content Creator) — Captions + blog drafts + schedule."""
    content = load_file(paths["content"]) if paths["content"] else ""

    social   = extract_section(content, "SOCIAL POSTS", 3000)
    gbp      = extract_section(content, "GBP POSTS", 2000)
    blog     = extract_section(content, "BLOG DRAFTS", 2000)

    body = f"""
<div class="section">
  <h2>Your Content This Week</h2>
  <div class="content-block" style="border-left-color:#e83e8c;background:#fff0f6">
    All content below is AI-drafted. Review + personalise before posting.
    Jane needs to approve before anything goes live — she'll confirm by Wednesday.
  </div>
</div>

<div class="section">
  <h2>Social Captions (5) — Instagram + TikTok</h2>
  <div class="content-block"><pre>{social or "See content file for social posts."}</pre></div>
</div>

<div class="section">
  <h2>GBP Posts (4) — Google Business Profile</h2>
  <div class="content-block"><pre>{gbp or "See content file for GBP posts."}</pre></div>
</div>

<div class="section">
  <h2>Blog Drafts (2) — Complete + publish with John</h2>
  <div class="content-block"><pre>{blog or "See content file for blog drafts."}</pre></div>
</div>
"""
    subject = f"CB247 Content — Week of {WEEK}"
    note = "Content pending Jane's approval (by Wednesday). Questions? Ask Jane or Tia."
    return subject, TEAM["shauna"], html_email(subject, "Shauna", "Content Creator", body, note)


def build_joanne_email(paths):
    """Joanne (Social Posting) — APPROVED content + posting schedule."""
    content = load_file(paths["content"]) if paths["content"] else ""

    social = extract_section(content, "SOCIAL POSTS", 3000)
    gbp    = extract_section(content, "GBP POSTS", 2000)

    body = f"""
<div class="section">
  <h2>This Week's Posting Schedule</h2>
  <div class="content-block" style="border-left-color:#28a745;background:#f0fff4">
    ✅ All content below has been approved by Jane.<br>
    Post as scheduled — captions are copy-paste ready.
  </div>
</div>

<div class="section">
  <h2>Posting Schedule</h2>
  <table>
    <tr><th>Day</th><th>Platform</th><th>Content Type</th><th>Status</th></tr>
    <tr><td>Tuesday</td><td>Google Business Profile</td><td>GBP Post #1</td><td>✅ Approved</td></tr>
    <tr><td>Tuesday</td><td>Instagram</td><td>Social Post #1</td><td>✅ Approved</td></tr>
    <tr><td>Wednesday</td><td>TikTok</td><td>Reel (from Agust/Ivan)</td><td>✅ Approved</td></tr>
    <tr><td>Thursday</td><td>Instagram</td><td>Social Post #2</td><td>✅ Approved</td></tr>
    <tr><td>Friday</td><td>Instagram + TikTok</td><td>Reel #2</td><td>✅ Approved</td></tr>
  </table>
</div>

<div class="section">
  <h2>Approved Social Captions</h2>
  <div class="content-block"><pre>{social or "Content pending Jane's approval — you'll receive an update."}</pre></div>
</div>

<div class="section">
  <h2>GBP Posts</h2>
  <div class="content-block"><pre>{gbp or "GBP posts pending approval."}</pre></div>
</div>
"""
    subject = f"CB247 Approved Posts — Week of {WEEK}"
    note = "Approved by Jane. Post as scheduled. Questions → Tia."
    return subject, TEAM["joanne"], html_email(subject, "Joanne", "Social Posting", body, note)


# ─────────────────────────────────────────────
# Email sender
# ─────────────────────────────────────────────

def send_email(subject, to_email, html_body, dry_run=False):
    """Send HTML email via SMTP."""
    if dry_run:
        print(f"  [DRY RUN] Would send: {subject!r} → {to_email}")
        return True

    if not SMTP_USER or not SMTP_PASS:
        print(f"  ⚠️  SMTP not configured — would send to {to_email}: {subject}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM or SMTP_USER
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"  ✅ Sent → {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"  ❌ Failed → {to_email}: {e}")
        return False


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CB247 team email delivery")
    parser.add_argument("--approve",  action="store_true", help="Send all team emails")
    parser.add_argument("--role",     type=str, help="Send to one role: ange|jane|john|mark|agust|ivan|shauna|joanne")
    parser.add_argument("--dry-run",  action="store_true", help="Print without sending")
    parser.add_argument("--list",     action="store_true", help="List latest output files")
    parser.add_argument("--recipient", type=str, help="Alias for --role (used by weekly-report.sh)")
    parser.add_argument("--strategy-file", type=str)
    parser.add_argument("--seo-file",      type=str)
    parser.add_argument("--content-file",  type=str)
    parser.add_argument("--date",          type=str)
    args = parser.parse_args()

    # Support --recipient as alias for --role
    if args.recipient and not args.role:
        args.role = args.recipient

    paths = get_output_paths()

    # Override paths from CLI flags
    if args.strategy_file:
        paths["strategy"]  = Path(args.strategy_file)
    if args.seo_file:
        paths["seo"]       = Path(args.seo_file)
    if args.content_file:
        paths["content"]   = Path(args.content_file)

    if args.list:
        print(f"Latest agent outputs for {DATE}:")
        for name, path in paths.items():
            status = "✅" if path and Path(path).exists() else "❌"
            print(f"  {status} {name:<12} {path or 'NOT FOUND'}")
        return

    dry_run = args.dry_run

    # Build all emails
    builders = {
        "ange":   lambda: build_ange_email(paths),
        "jane":   lambda: build_jane_email(paths),
        "john":   lambda: build_john_email(paths),
        "mark":   lambda: build_mark_email(paths),
        "agust":  lambda: build_video_email(paths, "agust", "Video Editor"),
        "ivan":   lambda: build_video_email(paths, "ivan",  "Video Editor"),
        "shauna": lambda: build_shauna_email(paths),
        "joanne": lambda: build_joanne_email(paths),
    }

    # Special case: "tia" recipient means Tia's OS report via send_weekly_report.py
    if args.role == "tia":
        print("ℹ️  Tia's OS report is handled by send_weekly_report.py")
        print("   Run: python scripts/send_weekly_report.py")
        return

    if args.role:
        role = args.role.lower()
        if role not in builders:
            print(f"Unknown role: {role}. Choose from: {', '.join(builders.keys())}")
            sys.exit(1)
        subject, to_email, html = builders[role]()
        send_email(subject, to_email, html, dry_run)

    elif args.approve:
        print(f"Sending all team emails for week of {WEEK}...")
        results = {}
        for role, builder in builders.items():
            subject, to_email, html = builder()
            results[role] = send_email(subject, to_email, html, dry_run)

        print(f"\nSummary: {sum(results.values())}/{len(results)} emails sent")
        for role, ok in results.items():
            print(f"  {'✅' if ok else '❌'} {role:<10} → {TEAM[role]}")

    else:
        print("Usage:")
        print("  python send_team_emails.py --approve        # Send all team emails")
        print("  python send_team_emails.py --role jane      # Send to one person")
        print("  python send_team_emails.py --dry-run        # Preview without sending")
        print("  python send_team_emails.py --list           # Show available outputs")


if __name__ == "__main__":
    main()
