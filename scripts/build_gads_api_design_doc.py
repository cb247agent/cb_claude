"""
build_gads_api_design_doc.py — Generate the Google Ads API Standard Access
application design document as a PDF.

Output: outputs/admin/cb247-google-ads-api-design-doc.pdf
"""

from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_PATH = BASE_DIR / "outputs" / "admin" / "cb247-google-ads-api-design-doc.pdf"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

TEAL = HexColor("#3FA69A")
DARK = HexColor("#1a1a1a")
MUTED = HexColor("#6b7280")

styles = getSampleStyleSheet()

H1 = ParagraphStyle(
    "H1", parent=styles["Heading1"],
    fontName="Helvetica-Bold", fontSize=18, leading=22,
    textColor=DARK, spaceAfter=8, spaceBefore=0,
)
H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"],
    fontName="Helvetica-Bold", fontSize=13, leading=16,
    textColor=TEAL, spaceAfter=6, spaceBefore=14,
)
BODY = ParagraphStyle(
    "Body", parent=styles["BodyText"],
    fontName="Helvetica", fontSize=10.5, leading=15,
    textColor=DARK, spaceAfter=6, alignment=TA_LEFT,
)
META = ParagraphStyle(
    "Meta", parent=styles["BodyText"],
    fontName="Helvetica", fontSize=9, leading=12,
    textColor=MUTED, spaceAfter=2,
)
BULLET = ParagraphStyle(
    "Bullet", parent=BODY, leftIndent=16, bulletIndent=4, spaceAfter=3,
)

doc = SimpleDocTemplate(
    str(OUT_PATH), pagesize=A4,
    leftMargin=22 * mm, rightMargin=22 * mm,
    topMargin=20 * mm, bottomMargin=20 * mm,
    title="CB247 Marketing Dashboard — Google Ads API Design Document",
    author="ChasingBetter247 Pty Ltd",
)

story = []

# ── Title block ──────────────────────────────────────────────────────────────
story.append(Paragraph("CB247 Marketing Dashboard", H1))
story.append(Paragraph("Google Ads API — Design Document", ParagraphStyle(
    "Subtitle", parent=H1, fontSize=13, textColor=TEAL, spaceAfter=14,
)))

meta_table = Table([
    ["Company",        "ChasingBetter247 Pty Ltd"],
    ["Location",       "Perth, Western Australia"],
    ["MCC Account",    "569-719-3495"],
    ["Tool Name",      "CB247 Marketing Performance Dashboard"],
    ["Tool Type",      "Internal read-only reporting dashboard"],
    ["Contact",        "cb_agent@chasingbetter.com.au"],
    ["Website",        "https://www.chasingbetter247.com.au/"],
    ["Date",           datetime.now().strftime("%B %Y")],
], colWidths=[36 * mm, 110 * mm])
meta_table.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 10),
    ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
    ("TEXTCOLOR", (1, 0), (1, -1), DARK),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LINEBELOW", (0, 0), (-1, -1), 0.25, HexColor("#e5e7eb")),
]))
story.append(meta_table)
story.append(Spacer(1, 14))

# ── 1. Purpose ────────────────────────────────────────────────────────────────
story.append(Paragraph("1. Purpose", H2))
story.append(Paragraph(
    "CB247 Marketing Performance Dashboard is an internal-only tool that "
    "consolidates Google Ads data alongside Google Analytics 4, Google "
    "Search Console, and Meta Ads into a single weekly view for the "
    "marketing team and management. The Google Ads API provides "
    "read-only access to campaign performance, search terms, Quality "
    "Scores, conversion action audits, and auction insights for weekly "
    "campaign optimisation decisions.",
    BODY,
))

# ── 2. Architecture ──────────────────────────────────────────────────────────
story.append(Paragraph("2. Architecture", H2))
arch_items = [
    ("Backend",        "Python 3.13 scripts running on a Mac mini in the CB247 office"),
    ("Storage",        "Local JSON files (state/*.json) — no cloud database"),
    ("Frontend",       "Static HTML dashboard hosted on GitHub Pages (private repository)"),
    ("Schedule",       "Weekly cron job at Monday 10:00 AM Perth time (AWST / UTC+8)"),
    ("Authentication", "OAuth 2.0 via Google Cloud Console (cb_agent@chasingbetter.com.au)"),
]
arch_table = Table(
    [[Paragraph(f"<b>{k}</b>", BODY), Paragraph(v, BODY)] for k, v in arch_items],
    colWidths=[32 * mm, 114 * mm],
)
arch_table.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
]))
story.append(arch_table)
story.append(Spacer(1, 6))
story.append(Paragraph("MCC structure: Two production accounts under MCC 569-719-3495:", BODY))
story.append(Paragraph("• Malaga (Customer ID: 937-134-0150)", BULLET))
story.append(Paragraph("• Ellenbrook (Customer ID: 821-783-6998)", BULLET))

# ── 3. API Usage ─────────────────────────────────────────────────────────────
story.append(Paragraph("3. API Usage", H2))
story.append(Paragraph(
    "All queries are <b>read-only</b> (GoogleAdsService.search). No mutations, "
    "no campaign edits, no ad creation. The system pulls the following "
    "resources weekly:",
    BODY,
))

api_table_data = [
    ["Resource", "Purpose", "Frequency"],
    ["campaign", "Campaign-level spend, clicks, impressions, conversions, CTR, CPC", "Weekly per account"],
    ["search_term_view", "Search terms triggering ads — negative-keyword identification", "Weekly per account"],
    ["keyword_view", "Keyword performance + Quality Score components (CTR, ad relevance, LP experience)", "Weekly per account"],
    ["conversion_action (segmented)", "Conversion action firing audit — verify tracking is intact", "Weekly per account"],
    ["auction_insight_view", "Competitor impression share and outranking share", "Weekly per account"],
]
api_table = Table(
    [
        [Paragraph(f"<b>{c}</b>" if i == 0 else c, BODY) for c in row]
        for i, row in enumerate(api_table_data)
    ],
    colWidths=[44 * mm, 76 * mm, 26 * mm],
)
api_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f0f2f5")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("GRID", (0, 0), (-1, -1), 0.25, HexColor("#e5e7eb")),
]))
story.append(api_table)
story.append(Spacer(1, 6))
story.append(Paragraph(
    "Estimated total operations per weekly pull: <b>4,000–8,000</b> across both accounts.",
    BODY,
))

# ── 4. Users and Access ──────────────────────────────────────────────────────
story.append(Paragraph("4. Users and Access", H2))
story.append(Paragraph(
    "The tool is <b>internal-only</b>. No external party or client has access.",
    BODY,
))
story.append(Paragraph(
    "• Marketing team: 3–5 people (Brand Manager, Web Dev, Paid Media specialist, Content team)",
    BULLET,
))
story.append(Paragraph(
    "• Management: 1–2 people (Director-level review of weekly KPIs)",
    BULLET,
))
story.append(Paragraph(
    "Access is controlled via GitHub Pages access list. No third-party developer "
    "or external contractor has access to the Google Ads API token or the dashboard.",
    BODY,
))

# ── 5. Data Handling ─────────────────────────────────────────────────────────
story.append(Paragraph("5. Data Handling", H2))
story.append(Paragraph(
    "• All data remains within CB247's own infrastructure (local files + private GitHub Pages site)",
    BULLET,
))
story.append(Paragraph(
    "• No data is shared with third parties",
    BULLET,
))
story.append(Paragraph(
    "• No data is resold or used for any purpose other than CB247's own marketing optimisation",
    BULLET,
))
story.append(Paragraph(
    "• Tokens and credentials are stored in .env files outside the public repository (in .gitignore)",
    BULLET,
))

# ── 6. Compliance ────────────────────────────────────────────────────────────
story.append(Paragraph("6. Compliance", H2))
story.append(Paragraph(
    "• Read-only API usage (no mutate operations)",
    BULLET,
))
story.append(Paragraph(
    "• OAuth 2.0 standard authentication flow",
    BULLET,
))
story.append(Paragraph(
    "• No App Conversion Tracking or Remarketing API used",
    BULLET,
))
story.append(Paragraph(
    "• Single developer token shared across two production accounts under one MCC",
    BULLET,
))

# ── 7. Why Standard Access Is Required ───────────────────────────────────────
story.append(Paragraph("7. Why Standard Access Is Required", H2))
story.append(Paragraph(
    "Basic Access (15,000 operations per day) is exhausted during a single "
    "weekly Monday pull when querying search_term_view and keyword_view "
    "across both production accounts with 16+ active campaigns. This causes "
    "incomplete data on the dashboard and forces partial pulls. Standard "
    "Access (40 million operations per day) provides comfortable headroom "
    "for the weekly pull plus occasional manual refreshes during the week.",
    BODY,
))

# ── Footer note ──────────────────────────────────────────────────────────────
story.append(Spacer(1, 18))
story.append(Paragraph(
    f"Submitted by ChasingBetter247 Pty Ltd · MCC 569-719-3495 · "
    f"Generated {datetime.now().strftime('%d %B %Y')}",
    META,
))

doc.build(story)
print(f"PDF written: {OUT_PATH}")
print(f"Size: {OUT_PATH.stat().st_size:,} bytes")
