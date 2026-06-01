#!/usr/bin/env python3
"""
recommendation_engine.py — Generate pre-meeting recommendations for CB247

Analyzes current performance data (GA4, GSC, Google Ads) and generates
actionable recommendations for management meetings.

Usage:
    python recommendation_engine.py              # Generate all recommendations
    python recommendation_engine.py --limit 5    # Top 5 recommendations only
    python recommendation_engine.py --format markdown  # Output as markdown

KPI Benchmarks (from marketing strategy):
    Meta Ads: CPM <$12, CPC <$1.50, CPL <$25
    Google: CTR >4%, CPC <$3, Conv Rate >5%
    Organic: Bounce Rate <55%, GSC CTR >3%
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from argparse import ArgumentParser

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
OUTPUT_DIR = BASE_DIR / "outputs" / "meetings"


def load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return None


def get_kpi_status(metric_name, current, benchmark):
    """Determine KPI status vs benchmark."""
    if current is None:
        return "unknown"

    if metric_name in ["cpm", "cpc", "cpl", "bounce_rate"]:
        # Lower is better
        if current <= benchmark * 0.9:
            return "exceeds"
        elif current <= benchmark:
            return "meets"
        elif current <= benchmark * 1.2:
            return "below"
        else:
            return "misses"
    else:
        # Higher is better
        if current >= benchmark * 1.1:
            return "exceeds"
        elif current >= benchmark:
            return "meets"
        elif current >= benchmark * 0.8:
            return "below"
        else:
            return "misses"


def analyze_meta_ads(ads_data):
    """Analyze Meta Ads performance and generate recommendations."""
    recommendations = []

    if not ads_data:
        return recommendations

    campaigns = ads_data.get("campaigns", [])
    for campaign in campaigns:
        name = campaign.get("name", "Unknown")
        metrics = campaign.get("metrics", {})

        cpm = metrics.get("cpm")
        cpc = metrics.get("cpc")
        cpl = metrics.get("cpl")

        # CPM check
        if cpm and cpm > 12:
            recommendations.append({
                "type": "meta_cpm",
                "priority": "high" if cpm > 15 else "medium",
                "title": f"Reduce CPM for {name}",
                "description": f"Current CPM ${cpm:.2f} exceeds benchmark $12",
                "kpis": {"cpm": {"current": cpm, "benchmark": 12}},
                "projected_impact": f"CPM reduction of ${cpm - 12:.2f} could save ${(cpm - 12) * metrics.get('impressions', 0) / 1000:.0f} per 1K impressions",
                "action": "Optimize targeting, refresh creative, adjust bid strategy"
            })

        # CPL check
        if cpl and cpl > 25:
            recommendations.append({
                "type": "meta_cpl",
                "priority": "high" if cpl > 35 else "medium",
                "title": f"Improve CPL for {name}",
                "description": f"Current CPL ${cpl:.2f} exceeds benchmark $25",
                "kpis": {"cpl": {"current": cpl, "benchmark": 25}},
                "projected_impact": f"CPL reduction to $25 would improve lead volume by {((cpl - 25) / cpl * 100):.0f}%",
                "action": "Test new ad copy, narrow audience, improve landing page"
            })

    return recommendations


def analyze_google_ads(ads_data):
    """Analyze Google Ads performance and generate recommendations."""
    recommendations = []

    if not ads_data:
        return recommendations

    campaigns = ads_data.get("campaigns", [])
    for campaign in campaigns:
        name = campaign.get("name", "Unknown")
        metrics = campaign.get("metrics", {})

        ctr = metrics.get("ctr")
        cpc = metrics.get("cpc")
        conv_rate = metrics.get("conversion_rate")

        # CTR check
        if ctr and ctr < 4:
            recommendations.append({
                "type": "google_ctr",
                "priority": "medium",
                "title": f"Improve CTR for {name}",
                "description": f"Current CTR {ctr:.2f}% is below benchmark 4%",
                "kpis": {"ctr": {"current": ctr, "benchmark": 4}},
                "projected_impact": f"CTR improvement to 4%+ would increase clicks by {((4 - ctr) / ctr * 100):.0f}%",
                "action": "Rewrite ad copy, add sitelinks, test new headlines"
            })

        # CPC check
        if cpc and cpc > 3:
            recommendations.append({
                "type": "google_cpc",
                "priority": "high" if cpc > 4 else "medium",
                "title": f"Reduce CPC for {name}",
                "description": f"Current CPC ${cpc:.2f} exceeds benchmark $3",
                "kpis": {"cpc": {"current": cpc, "benchmark": 3}},
                "projected_impact": f"CPC reduction to $3 would improve efficiency by {((cpc - 3) / cpc * 100):.0f}%",
                "action": "Improve Quality Score, tighten keyword matching, adjust bids"
            })

    return recommendations


def analyze_organic(ga4_data, gsc_data):
    """Analyze organic search performance and generate recommendations."""
    recommendations = []

    # GA4 bounce rate check
    if ga4_data:
        bounce_rate = ga4_data.get("current", {}).get("bounce_rate")
        if bounce_rate and bounce_rate > 55:
            recommendations.append({
                "type": "organic_bounce",
                "priority": "medium",
                "title": "Reduce organic bounce rate",
                "description": f"Current bounce rate {bounce_rate:.1f}% exceeds benchmark 55%",
                "kpis": {"bounce_rate": {"current": bounce_rate, "benchmark": 55}},
                "projected_impact": f"Bounce rate reduction to 55% would improve session duration and conversions",
                "action": "Improve page load speed, enhance internal linking, create engaging content"
            })

    # GSC CTR check
    if gsc_data:
        queries = gsc_data.get("queries", [])
        low_ctr_keywords = [q for q in queries if q.get("ctr", 0) < 0.03 and q.get("impressions", 0) > 100]

        if low_ctr_keywords:
            top_keyword = low_ctr_keywords[0]
            recommendations.append({
                "type": "organic_ctr",
                "priority": "medium",
                "title": "Improve CTR for top-ranking keywords",
                "description": f"Keyword '{top_keyword.get('query', '')}' has low CTR ({top_keyword.get('ctr', 0) * 100:.1f}%) despite ranking",
                "kpis": {"gsc_ctr": {"current": top_keyword.get('ctr', 0) * 100, "benchmark": 3}},
                "projected_impact": f"CTR improvement to 3%+ would increase organic clicks by {((0.03 - top_keyword.get('ctr', 0)) / top_keyword.get('ctr', 0.01) * 100):.0f}%",
                "action": "Optimize meta descriptions, test title tags, improve URL structure"
            })

    return recommendations


def analyze_content_gaps(gsc_data, ga4_data):
    """Identify content opportunities from data."""
    recommendations = []

    if not gsc_data:
        return recommendations

    queries = gsc_data.get("queries", [])

    # Find keywords with high impressions but low ranking
    opportunities = []
    for q in queries:
        impressions = q.get("impressions", 0)
        position = q.get("position", 100)

        if impressions > 100 and position > 10 and position < 30:
            opportunities.append(q)

    opportunities.sort(key=lambda x: x.get("impressions", 0), reverse=True)

    if opportunities:
        top = opportunities[0]
        recommendations.append({
            "type": "content_opportunity",
            "priority": "high",
            "title": f"Create content for '{top.get('query', '')}'",
            "description": f"This keyword has {int(top.get('impressions', 0))} impressions but ranks at position {top.get('position', 0):.1f}",
            "kpis": {"position": {"current": top.get('position', 0), "target": 5}},
            "projected_impact": f"Targeting position 1-3 could drive {int(top.get('impressions', 0) * 0.1)} additional clicks/month",
            "action": "Create dedicated landing page or blog post optimized for this keyword"
        })

    return recommendations


def analyze_competitive(ga4_data):
    """Analyze competitive position and generate recommendations."""
    recommendations = []

    # Check if we're losing traffic to competitors
    if ga4_data:
        traffic_sources = ga4_data.get("traffic_sources", [])
        direct_traffic = next((s for s in traffic_sources if s.get("source") == "Direct"), None)
        organic_traffic = next((s for s in traffic_sources if s.get("source") == "Organic Search"), None)

        if organic_traffic and direct_traffic:
            org_pct = organic_traffic.get("sessions", 0)
            dir_pct = direct_traffic.get("sessions", 0)

            if org_pct > dir_pct * 2:
                recommendations.append({
                    "type": "brand_awareness",
                    "priority": "medium",
                    "title": "Increase direct traffic / brand awareness",
                    "description": f"Organic ({org_pct}) heavily outweighs direct ({dir_pct}) - suggests brand awareness opportunity",
                    "kpis": {"direct_sessions": dir_pct, "organic_sessions": org_pct},
                    "projected_impact": "Improving brand recognition would increase direct traffic and reduce paid media dependency",
                    "action": "Increase brand campaigns, influencer partnerships, community events"
                })

    return recommendations


def generate_recommendations(limit=None, format="markdown"):
    """Generate all recommendations from current data."""
    # Load all data
    ga4_data = load_json(STATE_DIR / "ga4-data.json")
    gsc_data = load_json(STATE_DIR / "gsc-data.json")
    ads_data = load_json(STATE_DIR / "google-ads-data.json")

    all_recommendations = []

    # Analyze all channels
    all_recommendations.extend(analyze_meta_ads(ads_data))
    all_recommendations.extend(analyze_google_ads(ads_data))
    all_recommendations.extend(analyze_organic(ga4_data, gsc_data))
    all_recommendations.extend(analyze_content_gaps(gsc_data, ga4_data))
    all_recommendations.extend(analyze_competitive(ga4_data))

    # Sort by priority: high first, then medium
    priority_order = {"high": 0, "medium": 1, "low": 2}
    all_recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "medium"), 1))

    # Apply limit if specified
    if limit:
        all_recommendations = all_recommendations[:limit]

    return all_recommendations


def format_markdown(recommendations):
    """Format recommendations as markdown for meeting."""
    date = datetime.now().strftime("%Y-%m-%d")

    md = f"""# Pre-Meeting Recommendations — {date}

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Total Recommendations:** {len(recommendations)}

---

## Executive Summary

This document contains {len(recommendations)} actionable recommendations generated from current performance data across Meta Ads, Google Ads, and organic search channels.

**KPI Benchmarks Used:**
- Meta Ads: CPM <$12, CPC <$1.50, CPL <$25
- Google Ads: CTR >4%, CPC <$3, Conv Rate >5%
- Organic: Bounce Rate <55%, GSC CTR >3%

---

## Recommendations

"""

    for i, rec in enumerate(recommendations, 1):
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(rec.get("priority", "medium"), "🟡")

        md += f"""
### {i}. {priority_emoji} {rec.get('title', 'Untitled')}

**Priority:** {rec.get('priority', 'medium').upper()}
**Type:** {rec.get('type', 'general').replace('_', ' ').title()}

**Description:**
{rec.get('description', 'No description available')}

**Current KPIs:**
"""
        kpis = rec.get("kpis", {})
        for kpi_name, kpi_data in kpis.items():
            current = kpi_data.get("current", "N/A")
            benchmark = kpi_data.get("benchmark", "N/A")
            md += f"- {kpi_name.upper()}: {current} (benchmark: {benchmark})\n"

        md += f"""
**Projected Impact:**
{rec.get('projected_impact', 'Impact not specified')}

**Recommended Action:**
{rec.get('action', 'No action specified')}

---

"""

    md += """
## Next Steps

1. Review recommendations before meeting
2. Select 3-5 priority recommendations for discussion
3. At meeting: decide which to approve for execution
4. Approved items will be tracked as actions with assigned owners

---

*This document was auto-generated by CB247 Marketing Intelligence*
"""

    return md


def format_json(recommendations):
    """Format recommendations as JSON."""
    return json.dumps({
        "generated_at": datetime.now().isoformat(),
        "total_count": len(recommendations),
        "recommendations": recommendations
    }, indent=2)


def main():
    parser = ArgumentParser(description="Generate pre-meeting recommendations")
    parser.add_argument("--limit", type=int, help="Limit to top N recommendations")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    parser.add_argument("--save", action="store_true", help="Save to outputs/meetings/")
    args = parser.parse_args()

    print(f"CB247 Recommendation Engine — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    recommendations = generate_recommendations(limit=args.limit)

    print(f"Generated {len(recommendations)} recommendations")
    print(f"High priority: {len([r for r in recommendations if r.get('priority') == 'high'])}")
    print(f"Medium priority: {len([r for r in recommendations if r.get('priority') == 'medium'])}")

    if args.format == "markdown":
        output = format_markdown(recommendations)
    else:
        output = format_json(recommendations)

    if args.save:
        date = datetime.now().strftime("%Y-%m-%d")
        filename = f"recommendations-{date}.md"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / filename
        output_path.write_text(output)
        print(f"\nSaved to: {output_path}")
    else:
        print("\n" + "="*60)
        print("RECOMMENDATIONS OUTPUT")
        print("="*60)
        print(output)


if __name__ == "__main__":
    main()