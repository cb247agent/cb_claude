#!/usr/bin/env python3
"""
kpi_calculator.py — Calculate KPI performance for executed CB247 actions

Compares projected vs actual KPIs for completed actions and generates
impact reports for the KPI ledger.

Usage:
    python kpi_calculator.py                    # Show all pending reviews
    python kpi_calculator.py --action ACT-001  # Calculate KPIs for specific action
    python kpi_calculator.py --overdue         # Show actions past 14-day review window

KPI Benchmarks:
    Meta Ads: CPM <$12, CPC <$1.50, CPL <$25
    Google Ads: CTR >4%, CPC <$3, Conv Rate >5%
    Organic: Bounce Rate <55%, GSC CTR >3%
    General: ROAS >3x
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from argparse import ArgumentParser

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"


def load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return None


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def get_benchmarks():
    """Return KPI benchmarks."""
    return {
        "meta": {"cpm": 12, "cpc": 1.50, "cpl": 25},
        "google": {"ctr": 4, "cpc": 3, "conv_rate": 5},
        "organic": {"bounce_rate": 55, "gsc_ctr": 3},
        "general": {"roas": 3}
    }


def calculate_cpl(ads_data, campaign_name=None):
    """Calculate CPL from ads data."""
    if not ads_data:
        return None

    campaigns = ads_data.get("campaigns", [])
    total_spend = 0
    total_leads = 0

    for campaign in campaigns:
        if campaign_name and campaign.get("name") != campaign_name:
            continue
        metrics = campaign.get("metrics", {})
        spend = metrics.get("spend", 0)
        leads = metrics.get("leads", 0)
        if spend and leads:
            total_spend += spend
            total_leads += leads

    if total_leads > 0:
        return total_spend / total_leads
    return None


def calculate_roas(ads_data, campaign_name=None):
    """Calculate ROAS from ads data."""
    if not ads_data:
        return None

    campaigns = ads_data.get("campaigns", [])
    total_revenue = 0
    total_spend = 0

    for campaign in campaigns:
        if campaign_name and campaign.get("name") != campaign_name:
            continue
        metrics = campaign.get("metrics", {})
        spend = metrics.get("spend", 0)
        revenue = metrics.get("revenue", 0)
        if spend and revenue:
            total_spend += spend
            total_revenue += revenue

    if total_spend > 0:
        return total_revenue / total_spend
    return None


def calculate_cpm(ads_data, campaign_name=None):
    """Calculate CPM from ads data."""
    if not ads_data:
        return None

    campaigns = ads_data.get("campaigns", [])
    total_spend = 0
    total_impressions = 0

    for campaign in campaigns:
        if campaign_name and campaign.get("name") != campaign_name:
            continue
        metrics = campaign.get("metrics", {})
        spend = metrics.get("spend", 0)
        impressions = metrics.get("impressions", 0)
        if spend and impressions:
            total_spend += spend
            total_impressions += impressions

    if total_impressions > 0:
        return (total_spend / total_impressions) * 1000
    return None


def calculate_cpc(ads_data, campaign_name=None):
    """Calculate CPC from ads data."""
    if not ads_data:
        return None

    campaigns = ads_data.get("campaigns", [])
    total_spend = 0
    total_clicks = 0

    for campaign in campaigns:
        if campaign_name and campaign.get("name") != campaign_name:
            continue
        metrics = campaign.get("metrics", {})
        spend = metrics.get("spend", 0)
        clicks = metrics.get("clicks", 0)
        if spend and clicks:
            total_spend += spend
            total_clicks += clicks

    if total_clicks > 0:
        return total_spend / total_clicks
    return None


def calculate_ctr(ads_data, campaign_name=None):
    """Calculate CTR from ads data."""
    if not ads_data:
        return None

    campaigns = ads_data.get("campaigns", [])
    total_clicks = 0
    total_impressions = 0

    for campaign in campaigns:
        if campaign_name and campaign.get("name") != campaign_name:
            continue
        metrics = campaign.get("metrics", {})
        clicks = metrics.get("clicks", 0)
        impressions = metrics.get("impressions", 0)
        if clicks and impressions:
            total_clicks += clicks
            total_impressions += impressions

    if total_impressions > 0:
        return (total_clicks / total_impressions) * 100
    return None


def get_action(action_id):
    """Get action by ID from actions.json."""
    actions_data = load_json(STATE_DIR / "actions.json")
    if not actions_data:
        return None

    for action in actions_data.get("actions", []):
        if action.get("id") == action_id:
            return action
    return None


def get_actions_pending_review():
    """Get all actions that need 14-day review."""
    actions_data = load_json(STATE_DIR / "actions.json")
    if not actions_data:
        return []

    pending = []
    for action in actions_data.get("actions", []):
        if action.get("status") == "completed" and not action.get("actual_impact"):
            completion_date = action.get("completion_date")
            if completion_date:
                completion = datetime.strptime(completion_date, "%Y-%m-%d")
                review_date = completion + timedelta(days=14)
                pending.append({
                    **action,
                    "review_date": review_date.strftime("%Y-%m-%d"),
                    "days_since_completion": (datetime.now() - completion).days
                })
    return pending


def get_overdue_reviews():
    """Get actions past their 14-day review window."""
    pending = get_actions_pending_review()
    return [a for a in pending if a.get("days_since_completion", 0) >= 14]


def calculate_action_kpis(action):
    """Calculate actual KPIs for an action."""
    ads_data = load_json(STATE_DIR / "google-ads-data.json")

    selected_kpis = action.get("selected_kpis", [])
    actual_kpis = {}

    for kpi in selected_kpis:
        if kpi == "cpl":
            actual_kpis["cpl"] = calculate_cpl(ads_data)
        elif kpi == "cpm":
            actual_kpis["cpm"] = calculate_cpm(ads_data)
        elif kpi == "cpc":
            actual_kpis["cpc"] = calculate_cpc(ads_data)
        elif kpi == "roas":
            actual_kpis["roas"] = calculate_roas(ads_data)
        elif kpi == "ctr":
            actual_kpis["ctr"] = calculate_ctr(ads_data)

    return actual_kpis


def rate_kpi(kpi_name, actual, projected, benchmark):
    """Rate a single KPI."""
    if actual is None or projected is None:
        return "unknown"

    direction = "higher_is_better" if kpi_name in ["ctr", "roas", "conv_rate", "gsc_ctr"] else "lower_is_better"

    if direction == "higher_is_better":
        if actual >= projected * 1.1:
            return "exceeds"
        elif actual >= projected:
            return "meets"
        elif actual >= projected * 0.8:
            return "below"
        else:
            return "misses"
    else:
        if actual <= projected * 0.9:
            return "exceeds"
        elif actual <= projected:
            return "meets"
        elif actual <= projected * 1.2:
            return "below"
        else:
            return "misses"


def generate_impact_report(action_id):
    """Generate an impact report for an action."""
    action = get_action(action_id)
    if not action:
        return {"error": f"Action {action_id} not found"}

    if action.get("status") != "completed":
        return {"error": f"Action {action_id} is not completed yet"}

    actual_kpis = calculate_action_kpis(action)
    projected_impact = action.get("projected_impact", {})
    benchmarks = get_benchmarks()

    kpi_results = {}
    ratings = []

    for kpi_name, actual_value in actual_kpis.items():
        projected = projected_impact.get(kpi_name, {}).get("to")
        benchmark = benchmarks.get("meta", {}).get(kpi_name) or benchmarks.get("google", {}).get(kpi_name) or benchmarks.get("general", {}).get(kpi_name)

        rating = "unknown"
        delta = None
        delta_percent = None

        if actual_value is not None and projected:
            delta = actual_value - projected
            delta_percent = (delta / projected) * 100 if projected != 0 else 0
            rating = rate_kpi(kpi_name, actual_value, projected, benchmark)

        kpi_results[kpi_name] = {
            "projected": projected,
            "actual": actual_value,
            "benchmark": benchmark,
            "delta": delta,
            "delta_percent": delta_percent,
            "rating": rating
        }

        if rating != "unknown":
            ratings.append(rating)

    # Overall rating
    if ratings:
        if all(r == "exceeds" for r in ratings):
            overall = "exceeds"
        elif all(r in ["exceeds", "meets"] for r in ratings):
            overall = "meets"
        elif all(r in ["meets", "below"] for r in ratings):
            overall = "below"
        else:
            overall = "misses"
    else:
        overall = "unknown"

    report = {
        "action_id": action_id,
        "action_description": action.get("description"),
        "completed_date": action.get("completion_date"),
        "review_date": datetime.now().strftime("%Y-%m-%d"),
        "kpis": kpi_results,
        "overall_rating": overall,
        "notes": ""
    }

    return report


def update_kpi_ledger(action_id, report):
    """Save KPI report to the ledger."""
    ledger_data = load_json(STATE_DIR / "kpi_ledger.json")
    if not ledger_data:
        ledger_data = {"schema_version": "1.0", "entries": []}

    # Check if entry already exists
    existing_idx = None
    for idx, entry in enumerate(ledger_data.get("entries", [])):
        if entry.get("action_id") == action_id:
            existing_idx = idx
            break

    # Create entry
    entry = {
        "action_id": report.get("action_id"),
        "action_description": report.get("action_description"),
        "completed_date": report.get("completed_date"),
        "review_date": report.get("review_date"),
        "kpis": report.get("kpis", {}),
        "overall_rating": report.get("overall_rating"),
        "notes": report.get("notes", "")
    }

    if existing_idx is not None:
        ledger_data["entries"][existing_idx] = entry
    else:
        ledger_data["entries"].append(entry)

    ledger_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    save_json(STATE_DIR / "kpi_ledger.json", ledger_data)


def update_action_actual_impact(action_id, report):
    """Update actions.json with actual impact from report."""
    actions_data = load_json(STATE_DIR / "actions.json")
    if not actions_data:
        return

    for action in actions_data.get("actions", []):
        if action.get("id") == action_id:
            action["actual_impact"] = report.get("kpis", {})
            break

    actions_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    save_json(STATE_DIR / "actions.json", actions_data)


def format_report_markdown(report):
    """Format impact report as markdown."""
    kpis = report.get("kpis", {})

    md = f"""# KPI Impact Report — {report.get('action_id')}

**Action:** {report.get('action_description')}
**Completed:** {report.get('completed_date')}
**Reviewed:** {report.get('review_date')}
**Overall Rating:** {report.get('overall_rating', 'unknown').upper()}

---

## KPI Performance

| KPI | Projected | Actual | Benchmark | Delta | Rating |
|-----|-----------|--------|-----------|-------|--------|
"""

    for kpi_name, kpi_data in kpis.items():
        projected = kpi_data.get("projected", "N/A")
        actual = kpi_data.get("actual", "N/A")
        benchmark = kpi_data.get("benchmark", "N/A")
        delta = kpi_data.get("delta")
        delta_pct = kpi_data.get("delta_percent")
        rating = kpi_data.get("rating", "unknown")

        if isinstance(projected, (int, float)):
            projected = f"{projected:.2f}"
        if isinstance(actual, (int, float)):
            actual = f"{actual:.2f}"
        if isinstance(benchmark, (int, float)):
            benchmark = f"{benchmark:.2f}"

        if delta is not None:
            delta_str = f"{delta:+.2f} ({delta_pct:+.1f}%)" if delta_pct is not None else f"{delta:+.2f}"
        else:
            delta_str = "N/A"

        rating_emoji = {"exceeds": "🟢", "meets": "🟡", "below": "🟠", "misses": "🔴", "unknown": "⚪"}.get(rating, "⚪")

        md += f"| {kpi_name.upper()} | {projected} | {actual} | {benchmark} | {delta_str} | {rating_emoji} {rating.upper()} |\n"

    md += f"""
---

## Summary

**Overall Performance:** {report.get('overall_rating', 'unknown').upper()}

"""
    if report.get("overall_rating") == "exceeds":
        md += "This action exceeded all projected KPIs. Excellent execution!\n"
    elif report.get("overall_rating") == "meets":
        md += "This action met projected KPIs. Solid performance.\n"
    elif report.get("overall_rating") == "below":
        md += "This action was below projected KPIs but within acceptable range.\n"
    elif report.get("overall_rating") == "misses":
        md += "This action significantly underperformed projections. Review recommended.\n"

    md += f"""
## Notes

_{report.get('notes', 'No notes added yet.')}_

---

*Report generated by CB247 KPI Calculator*
"""
    return md


def main():
    parser = ArgumentParser(description="Calculate KPI performance for CB247 actions")
    parser.add_argument("--action", type=str, help="Action ID to calculate KPIs for")
    parser.add_argument("--list", action="store_true", help="List all actions pending review")
    parser.add_argument("--overdue", action="store_true", help="List actions past 14-day review window")
    parser.add_argument("--save", action="store_true", help="Save report to outputs/meetings/")
    args = parser.parse_args()

    if args.overdue:
        print("CB247 KPI Calculator — Overdue Reviews")
        print("="*60)
        overdue = get_overdue_reviews()
        if not overdue:
            print("No overdue reviews.")
        else:
            for action in overdue:
                print(f"\n{action['id']}: {action['description']}")
                print(f"  Completed: {action['completion_date']}")
                print(f"  Days since completion: {action['days_since_completion']}")
                print(f"  Review date: {action['review_date']}")
        return

    if args.list:
        print("CB247 KPI Calculator — Pending Reviews")
        print("="*60)
        pending = get_actions_pending_review()
        if not pending:
            print("No actions pending review.")
        else:
            for action in pending:
                print(f"\n{action['id']}: {action['description']}")
                print(f"  Due for review: {action['review_date']} ({action['days_since_completion']} days)")
        return

    if args.action:
        print(f"Calculating KPIs for {args.action}...")
        report = generate_impact_report(args.action)

        if "error" in report:
            print(f"Error: {report['error']}")
            return

        print("\n" + "="*60)
        print("IMPACT REPORT")
        print("="*60)
        print(format_report_markdown(report))

        if args.save:
            from pathlib import Path
            OUTPUT_DIR = BASE_DIR / "outputs" / "meetings"
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            filename = f"impact-{args.action}-{datetime.now().strftime('%Y-%m-%d')}.md"
            (OUTPUT_DIR / filename).write_text(format_report_markdown(report))
            print(f"\nSaved to: {OUTPUT_DIR / filename}")

            # Also update the ledger
            update_kpi_ledger(args.action, report)
            update_action_actual_impact(args.action, report)
            print("Updated: state/kpi_ledger.json and state/actions.json")
        return

    # No arguments: show help
    parser.print_help()


if __name__ == "__main__":
    main()