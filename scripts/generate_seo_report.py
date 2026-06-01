"""
generate_seo_report.py — Unified weekly SEO report combining all data sources.
Generates markdown + HTML report with attachments list.
Save to outputs/seo/reports/ with date stamp.

Data sources: GA4, GSC, Ahrefs, Apify, Screaming Frog
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
OUTPUT_DIR = BASE_DIR / "outputs" / "seo" / "reports"
load_dotenv(BASE_DIR / ".env")

def load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return None

def pct(a, b):
    if b == 0: return "n/a"
    change = ((a - b) / b) * 100
    return f"{'+' if change > 0 else ''}{change:.1f}%"

def arrow(val, inverse=False):
    if val > 0: return "↗️" if not inverse else "↘️"
    if val < 0: return "↘️" if not inverse else "↗️"
    return "➡️"

def load_data():
    return {
        "gsc": load_json(STATE_DIR / "gsc-data.json"),
        "ga4": load_json(STATE_DIR / "ga4-data.json"),
        "ahrefs": load_json(STATE_DIR / "ahrefs-data.json"),
        "apify": load_json(STATE_DIR / "apify-data.json"),
        "sf": load_json(STATE_DIR / "screaming-frog-data.json"),
    }

def render_gsc(d):
    if not d:
        return "## GSC Data\n*No GSC data available. Run `pull_all.py` first.*\n"
    summary = d.get("summary", {})
    date_range = d.get("date_range", {})
    top_q = (d.get("top_queries", []) or [])[:10]
    top_p = (d.get("top_pages", []) or [])[:10]
    prev = d.get("previous_summary", {})

    rows_q = "\n".join(
        f"| {q['query']} | {q['clicks']} | {q['impressions']} | {q['ctr']*100:.1f}% | #{q['position']:.1f} |"
        for q in top_q
    ) or "| — | — | — | — |"
    rows_p = "\n".join(
        f"| {p['page'][:60]} | {p['clicks']} | {p['impressions']} | {p['ctr']*100:.1f}% | #{p['position']:.1f} |"
        for p in top_p
    ) or "| — | — | — | — |"

    return f"""## Google Search Console — {date_range.get('start','?')} to {date_range.get('end','?')}

### KPI Summary

| Metric | This Week | vs Prev Week | Trend |
|--------|-----------|--------------|-------|
| Clicks | {summary.get('total_clicks', 0):,} | {pct(summary.get('total_clicks',0), prev.get('total_clicks',0))} | {arrow(summary.get('total_clicks',0) - prev.get('total_clicks',0))} |
| Impressions | {summary.get('total_impressions', 0):,} | {pct(summary.get('total_impressions',0), prev.get('total_impressions',0))} | {arrow(summary.get('total_impressions',0) - prev.get('total_impressions',0))} |
| Avg CTR | {summary.get('avg_ctr',0)*100:.2f}% | {pct(summary.get('avg_ctr',0)*100, prev.get('avg_ctr',0)*100)} | {arrow(summary.get('avg_ctr',0) - prev.get('avg_ctr',0))} |
| Avg Position | {summary.get('avg_position',0):.1f} | {'better' if summary.get('avg_position',0) < prev.get('avg_position',0) else 'worse'} | {arrow(summary.get('avg_position',0) - prev.get('avg_position',0), inverse=True)} |

### Top 10 Queries

| Query | Clicks | Impressions | CTR | Position |
|-------|--------|-------------|-----|----------|
{rows_q}

### Top 10 Pages

| Page | Clicks | Impressions | CTR | Position |
|------|--------|-------------|-----|----------|
{rows_p}
"""

def render_ga4(d):
    if not d:
        return "## GA4 Data\n*No GA4 data available.*\n"
    current = d.get("current", {})
    previous = d.get("previous", {})
    sessions = int(current.get("sessions", 0) or 0)
    p_sessions = int(previous.get("sessions", 0) or 0)

    # Traffic sources breakdown
    sources_html = ""
    if d.get("traffic_sources"):
        rows = []
        for src in d["traffic_sources"][:8]:
            ch = src.get("sessionDefaultChannelGroup","")
            s = int(src.get("sessions",0))
            rows.append(f"| {ch} | {s:,} | {s*100/max(sessions,1):.1f}% |")
        sources_html = "\n".join(rows)
    else:
        sources_html = "| — | — | — |"

    return f"""## GA4 Analytics

### KPI Summary

| Metric | This Week | vs Prev Week | Trend |
|--------|-----------|--------------|-------|
| Total Sessions | {sessions:,} | {pct(sessions, p_sessions)} | {arrow(sessions - p_sessions)} |
| New Users | {current.get('new_users','—')} | {previous.get('new_users','—')} | — |
| Engaged Sessions | {current.get('engaged_sessions','—')} | {previous.get('engaged_sessions','—')} | — |
| Conversions | {current.get('conversions','N/A')} | {previous.get('conversions','—')} | — |

### Traffic Sources

| Channel | Sessions | % of Total |
|---------|----------|------------|
{sources_html}
"""

def render_ahrefs(d):
    if not d:
        return "## Ahrefs Data\n*No Ahrefs data available. Set AHREFS_API_KEY in .env*\n"
    dr = d.get("domain_rating", {})
    keywords = (d.get("organic_keywords", []) or [])[:20]
    new_lost = d.get("new_lost_links", {})
    anchors = (d.get("anchors", []) or [])[:15]

    dr_val = dr.get("domain_rating", "—") if isinstance(dr, dict) else "—"
    ref_domains = dr.get("ref_domains", "—") if isinstance(dr, dict) else "—"
    backlinks = dr.get("backlinks", "—") if isinstance(dr, dict) else "—"

    kw_rows = "\n".join(
        f"| {k.get('keyword','—')} | #{k.get('position','—')} | {k.get('volume','—')} | {k.get('cpc','—')} |"
        for k in keywords
    ) or "| — | — | — | — |"

    anchor_rows = "\n".join(
        f"| {a.get('anchor','—')} | {a.get('backlinks','—')} | {a.get('refpages','—')} |"
        for a in anchors
    ) or "| — | — | — |"

    new_links = (new_lost.get("new") or [])[:5]
    lost_links = (new_lost.get("lost") or [])[:5]
    new_rows = "\n".join(f"| {l.get('url','—')[:60]} | {l.get('first_seen','—')} |" for l in new_links) or "| — | — |"
    lost_rows = "\n".join(f"| {l.get('url','—')[:60]} | {l.get('last_seen','—')} |" for l in lost_links) or "| — | — |"

    return f"""## Ahrefs Backlink & Keyword Analytics
*Last pulled: {d.get('date_pulled','unknown')}*

### Domain Authority

| Metric | Value |
|--------|-------|
| Domain Rating (DR) | {dr_val} |
| Referring Domains | {ref_domains} |
| Total Backlinks | {backlinks} |

### Top Ranking Keywords

| Keyword | Position | Volume | CPC |
|---------|----------|--------|-----|
{kw_rows}

### Top Anchor Texts

| Anchor | Backlinks | Ref Pages |
|--------|----------|-----------|
{anchor_rows}

### New Links This Week

| URL | First Seen |
|-----|-----------|
{new_rows}

### Lost Links This Week

| URL | Last Seen |
|-----|-----------|
{lost_rows}
"""

def render_sf(d):
    if not d:
        return "## Screaming Frog Technical Audit\n*No data available. Run `run_screaming_frog.py` first.*\n"
    issues = d.get("issues") or []
    top_pages = d.get("top_pages") or []

    # Group by priority
    critical = [i for i in issues if i.get("priority") == "High" or "Critical" in i.get("name","")]
    medium = [i for i in issues if i.get("priority") == "Medium"]
    low = [i for i in issues if i.get("priority") == "Low"]

    def issue_rows(items):
        return "\n".join(
            f"| {i['name'][:60]} | {i['type']} | {i['count']} | {i['priority']} |"
            for i in items
        ) or "| — | — | — | — |"

    critical_rows = issue_rows(critical[:10])
    medium_rows = issue_rows(medium[:10])
    low_rows = issue_rows(low[:10])

    return f"""## Screaming Frog Technical SEO Audit
*Last crawled: {d.get('date_crawled','unknown')}*

### Issues by Priority

#### 🔴 Critical / High Priority Issues

| Issue | Type | Count | Priority |
|-------|------|-------|----------|
{critical_rows}

#### 🟡 Medium Priority Issues

| Issue | Type | Count | Priority |
|-------|------|-------|----------|
{medium_rows}

#### ⚪ Low Priority Issues

| Issue | Type | Count | Priority |
|-------|------|-------|----------|
{low_rows}

### Top Crawled Pages

| URL | Title | Words | Status |
|-----|-------|-------|--------|
{chr(10).join(f"| {p['url'][:60]} | {p.get('title','')[:40]} | {p.get('word_count','—')} | {p.get('status','—')} |" for p in top_pages[:15]) if top_pages else "| — | — | — | — |"}
"""

def render_apify(d):
    if not d:
        return "## Apify Content & Competitor Analysis\n*No Apify data available. Set APIFY_API_KEY in .env*\n"
    serp = d.get("competitor_serp") or []
    kw_track = d.get("keyword_tracking") or []

    serp_rows = ""
    for kw_data in serp[:5]:
        kw = kw_data.get("keyword", "")
        results = kw_data.get("results", [])
        if not results:
            continue
        top3 = results[:3]
        for r in top3:
            title = r.get("title", "")[:50]
            url = r.get("url", "")[:60]
            serp_rows += f"| {kw} | {title} | {url} |\n"

    if not serp_rows:
        serp_rows = "| — | — | — |\n"

    return f"""## Apify Content & SERP Analysis
*Last pulled: {d.get('date_pulled','unknown')}*

### Competitor SERP Snippets — Top Results by Keyword

| Keyword | Result Title | URL |
|---------|-------------|-----|
{serp_rows}

### Keyword Position Tracking

| Keyword | Position | Volume | Traffic |
|---------|----------|--------|---------|
{chr(10).join(f"| {k.get('keyword','—')} | #{k.get('position','—')} | {k.get('search_volume','—')} | {k.get('estimated_traffic','—')} |" for k in kw_track[:10]) if kw_track else "| — | — | — | — |"}
"""

def render_priority_actions(gsc, sf, apify):
    """Build priority actions based on all data."""
    actions = []

    # GSC opportunities
    gsc_queries = {q.get("query","").lower(): q for q in (gsc.get("top_queries",[]) or [])}
    for kw in ["gym malaga", "gym ellenbrook", "sauna malaga"]:
        q = gsc_queries.get(kw)
        if q:
            pos = q.get("position", 99)
            if pos > 10:
                actions.append({"action": f'"{kw}" ranking at #{pos:.0f} — needs backlinks + content boost', "priority": "P1", "status": "🔴 Critical"})

    # Screaming Frog issues
    if sf and sf.get("issues"):
        critical_issues = [i for i in sf["issues"] if i.get("priority") in ("High","Medium")]
        for i in critical_issues[:3]:
            actions.append({"action": f"{i['name'][:60]} — {i['count']} pages affected", "priority": "P2", "status": "🟡 Medium"})

    # Apify competitor gaps
    if apify and apify.get("competitor_serp"):
        for kw_data in apify["competitor_serp"][:3]:
            results = kw_data.get("results", [])
            for r in (results or [])[:1]:
                url = r.get("url","")
                if "revo" in url.lower() or "anytime" in url.lower():
                    actions.append({"action": f'Competitor outranking CB247 for "{kw_data["keyword"]}"', "priority": "P1", "status": "🔴 Critical"})

    if not actions:
        actions = [{"action": "All KPIs within target range — maintain current strategy", "priority": "P2", "status": "🟢 On Track"}]

    rows = "\n".join(f"| {a['action']} | {a['priority']} | {a['status']} |" for a in actions)
    return f"""## Priority Actions This Week

| Action | Priority | Status |
|--------|----------|--------|
{rows}
"""

def build_markdown_report(data):
    gsc = data.get("gsc", {})
    ga4 = data.get("ga4", {})
    ahrefs = data.get("ahrefs", {})
    sf = data.get("sf", {})
    apify = data.get("apify", {})
    today = datetime.now().strftime("%d %B %Y")

    md = f"""# CB247 Weekly SEO Report — {today}

> **Automated Report** | Generated by CB247 Marketing AI
> Data sources: GA4 · Google Search Console · Ahrefs · Apify · Screaming Frog

---

{render_gsc(gsc)}

---

{render_ga4(ga4)}

---

{render_ahrefs(ahrefs)}

---

{render_sf(sf)}

---

{render_apify(apify)}

---

{render_priority_actions(gsc, sf, apify)}

---

*Report generated: {datetime.now().isoformat()}*
"""
    return md

def build_html_report(md):
    """Convert markdown to basic HTML email-compatible report."""
    import html
    lines = md.split("\n")
    html_lines = ['<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">']
    html_lines += ['<style>']
    html_lines += ['body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0a0a0a;color:#fff;padding:32px}']
    html_lines += ['.container{max-width:800px;margin:0 auto}']
    html_lines += ['h1{color:#3FA69A;font-size:1.75rem;border-bottom:2px solid #3FA69A;padding-bottom:8px}']
    html_lines += ['h2{color:#3FA69A;font-size:1rem;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #222;padding-bottom:6px;margin-top:32px}']
    html_lines += ['table{width:100%;border-collapse:collapse;font-size:.875rem;margin-bottom:16px}']
    html_lines += ['th{color:#888;text-align:left;padding:8px 12px;border-bottom:1px solid #333;background:#111}']
    html_lines += ['td{padding:10px 12px;border-bottom:1px solid #1a1a1a;color:#ddd}']
    html_lines += ['tr:hover td{background:#141414}']
    html_lines += ['.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}']
    html_lines += ['.kpi{background:#141414;border:1px solid #222;border-radius:8px;padding:20px}']
    html_lines += ['.kpi .label{color:#888;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}']
    html_lines += ['.kpi .value{font-size:1.75rem;font-weight:700}']
    html_lines += ['.badge{display:inline-block;background:rgba(63,166,154,.15);color:#3FA69A;padding:2px 8px;border-radius:4px;font-size:.7rem}']
    html_lines += ['blockquote{{border-left:3px solid #3FA69A;padding:8px 16px;background:#111;margin:16px 0}}']
    html_lines += ['{{color:#aaa;font-size:.875rem}}']
    html_lines += ['</style></head><body><div class="container">']

    in_table = False
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            html_lines.append(f'<h1>{html.escape(line[2:])}</h1>')
        elif line.startswith("## "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f'<h2>{html.escape(line[3:])}</h2>')
        elif line.startswith("| ") and " | " in line and line.strip().endswith("|"):
            if not in_table:
                in_table = True
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if all(c.replace("-","").replace(":","") == "" for c in cols):
                continue
            if "---" in line:
                continue
            html_lines.append("<table>")
            for col in cols:
                html_lines.append(f"<th>{html.escape(col)}</th>")
            html_lines.append("</tr>")
            in_table = True
        elif line.startswith("> "):
            html_lines.append(f'<blockquote>{html.escape(line[2:])}</blockquote>')
        elif line.strip() == "":
            if in_table:
                html_lines.append("</table>")
                in_table = False
        else:
            text = html.escape(line)
            text = text.replace("**", "<strong>", 1).replace("**", "</strong>", 1) if "**" in line else text
            html_lines.append(f'<p>{text}</p>')

    if in_table:
        html_lines.append("</table>")

    html_lines.append("</div></body></html>")
    return "\n".join(html_lines)

def main():
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    date_readable = today.strftime("%d %B %Y")

    data = load_data()
    md = build_markdown_report(data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save markdown
    md_path = OUTPUT_DIR / f"full-seo-report-{date_str}.md"
    md_path.write_text(md)
    print(f"Markdown report: {md_path}")

    # Save HTML
    html = build_html_report(md)
    html_path = OUTPUT_DIR / f"full-seo-report-{date_str}.html"
    html_path.write_text(html)
    print(f"HTML report: {html_path}")

    # List all attachments
    attachments = [
        md_path,
        html_path,
        STATE_DIR / "gsc-data.json",
        STATE_DIR / "ga4-data.json",
        STATE_DIR / "ahrefs-data.json",
        STATE_DIR / "apify-data.json",
        STATE_DIR / "screaming-frog-data.json",
    ]
    existing_attachments = [str(a) for a in attachments if a.exists()]
    print(f"\nAttachments ({len(existing_attachments)} files):")
    for a in existing_attachments:
        print(f"  - {a}")

    return {
        "markdown": str(md_path),
        "html": str(html_path),
        "attachments": existing_attachments,
    }

if __name__ == "__main__":
    main()