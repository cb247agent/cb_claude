#!/usr/bin/env python3
"""
seo_blog_scheduler.py — Weekly SEO blog generation scheduler

This script determines the current week in the topic rotation,
pulls latest GSC/GA4 data, and generates a blog draft.

Usage:
    python seo_blog_scheduler.py              # Generate this week's blog
    python seo_blog_scheduler.py --dry-run    # Show what would be generated
    python seo_blog_scheduler.py --force      # Force regenerate even if recently generated

Topic Rotation:
    Week 1 (Mon): Fitness Tips
    Week 2 (Tue): Local Community
    Week 3 (Wed): Competitor Comparison
    Week 4 (Thu): Data-Driven (based on GSC/GA4 insights)

Week numbers align with ISO week - so this always produces the right topic
regardless of month boundaries.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from argparse import ArgumentParser

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
OUTPUTS_BLOG_DIR = BASE_DIR / "outputs" / "blogs"


def load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return None


def get_topic_for_week():
    """Determine topic based on ISO week number."""
    current_week = datetime.now().isocalendar()[1]
    week_type = current_week % 4  # 0-3 cycling

    topics = {
        0: {
            "theme": "fitness_tips",
            "name": "Fitness Tips",
            "description": "Educational workout guidance and training advice",
            "examples": [
                "5 exercises for FIFO workers between shifts",
                "How to start working out at 40 (and stick with it)",
                "The beginner's guide to reformer pilates in Perth",
                "Why sauna sessions supercharge your recovery"
            ]
        },
        1: {
            "theme": "local_community",
            "name": "Local Community",
            "description": "Malaga and Ellenbrook community events and partnerships",
            "examples": [
                "Best parks near Ellenbrook for outdoor training",
                "How the Kids Hub lets parents train guilt-free",
                "Community partnerships: training with Malaga fitness groups"
            ]
        },
        2: {
            "theme": "competitor_comparison",
            "name": "Competitor Comparison",
            "description": "Why CB247 beats the competition on value",
            "examples": [
                "Revo vs CB247: Why members make the switch",
                "Why $11.95/week at CB247 beats Anytime Fitness",
                "Why we're the only 24/7 gym with sauna AND ice bath in Perth"
            ]
        },
        3: {
            "theme": "data_driven",
            "name": "Data-Driven Insights",
            "description": "Based on GSC/GA4 data - high-opportunity keywords",
            "examples": [
                "Topic will be determined by keyword analysis"
            ]
        }
    }

    return topics[week_type]


def find_data_driven_topic(gsc_data, ga4_data):
    """Find high-opportunity keyword from GSC data for Week 4."""
    opportunities = []

    # Look at GSC data for high impressions, low position (easy wins)
    if gsc_data:
        for query in gsc_data.get("queries", []):
            impressions = query.get("impressions", 0)
            position = query.get("position", 100)
            ctr = query.get("ctr", 0)

            # High impressions but position > 10 = ranking opportunity
            if impressions > 100 and position > 10 and position < 30:
                opportunities.append({
                    "keyword": query.get("query", ""),
                    "impressions": impressions,
                    "position": position,
                    "ctr": ctr
                })

    # Sort by opportunity score (impressions * (30 - position))
    opportunities.sort(
        key=lambda x: x["impressions"] * (30 - min(x["position"], 30)),
        reverse=True
    )

    if opportunities:
        top = opportunities[0]
        return {
            "theme": "data_driven",
            "name": "Data-Driven Insights",
            "description": f"Based on GSC data: '{top['keyword']}' has {int(top['impressions'])} impressions but ranks at position {top['position']:.1f}",
            "suggested_topic": f"Why '{top['keyword']}' matters for fitness in Perth",
            "opportunity_keyword": top["keyword"]
        }

    # Fallback if no opportunities found
    return {
        "theme": "data_driven",
        "name": "Data-Driven Insights",
        "description": "Based on GSC/GA4 data analysis",
        "suggested_topic": "How to choose the right gym for your fitness goals"
    }


def get_recent_blog_date():
    """Get the date of the most recent blog if it exists."""
    if not OUTPUTS_BLOG_DIR.exists():
        return None

    blogs = list(OUTPUTS_BLOG_DIR.glob("seo-blog-*.md"))
    if not blogs:
        return None

    # Sort by date in filename
    blogs.sort(reverse=True)
    latest = blogs[0].stem  # e.g., "seo-blog-2026-06-01"
    return latest.replace("seo-blog-", "")


def should_skip_generation(force=False):
    """Check if we should skip blog generation (already generated this week)."""
    if force:
        return False

    recent = get_recent_blog_date()
    if not recent:
        return False

    # Check if most recent blog is from this week
    recent_date = datetime.strptime(recent, "%Y-%m-%d")
    current_date = datetime.now()
    current_week = current_date.isocalendar()[1]
    recent_week = recent_date.isocalendar()[1]

    # If same week, skip (already generated)
    if current_week == recent_week and recent_date.year == current_date.year:
        return True

    return False


def generate_blog_metadata(topic, gsc_data=None, ga4_data=None):
    """Generate the YAML front matter for the blog."""
    date = datetime.now().strftime("%Y-%m-%d")

    # Determine target keyword based on topic
    keyword_map = {
        "fitness_tips": "gym tips perth",
        "local_community": "gym malaga",
        "competitor_comparison": "best gym perth value",
        "data_driven": "fitness perth"
    }

    target_keyword = keyword_map.get(topic["theme"], "gym perth")

    # Enhance with GSC data if data-driven week
    if topic["theme"] == "data_driven" and gsc_data:
        data_topic = find_data_driven_topic(gsc_data, ga4_data)
        if "opportunity_keyword" in data_topic:
            target_keyword = data_topic["opportunity_keyword"]

    featured_prompt = {
        "fitness_tips": "Professional fitness photography, fitness training tips and workout guidance, teal (#3FA69A) and white color scheme, CB247 gym branding, diverse group of athletes training, modern gym equipment visible, motivational mood, natural lighting, high resolution",
        "local_community": f"Community fitness event at CB247 gym, teal and white branding, Malaga or Ellenbrook location setting, families and individuals working out together, Kids Hub visible in background, welcoming atmosphere, warm natural lighting, high resolution",
        "competitor_comparison": "Competitive comparison marketing, CB247 gym vs competitors side by side, teal (#3FA69A) premium equipment, value comparison visual, professional photography, modern clean gym aesthetic, high resolution, marketing material",
        "data_driven": "Data analytics and fitness insights, CB247 gym data visualization, teal (#3FA69A) charts and graphs, fitness performance metrics, professional infographic style, modern clean design, high resolution"
    }

    return {
        "date": date,
        "topic": topic,
        "target_keyword": target_keyword,
        "featured_image_prompt": featured_prompt.get(topic["theme"], featured_prompt["fitness_tips"])
    }


def create_blog_draft_prompt(metadata, gsc_data=None, ga4_data=None):
    """Generate the prompt text for the blog draft."""
    topic = metadata["topic"]
    date = metadata["date"]

    prompt = f"""Generate this week's CB247 SEO blog post.

**Date:** {date}
**Topic Theme:** {topic['name']} ({topic['theme']})
**Description:** {topic['description']}

**Target Keyword:** {metadata['target_keyword']}

"""

    if topic['theme'] == 'data_driven' and 'suggested_topic' in topic:
        prompt += f"**Suggested Focus:** {topic['suggested_topic']}\n"

    prompt += """
**Task:**
Generate a complete blog post following the seo-blog-generator skill guidelines.
Save the output to: outputs/blogs/seo-blog-{date}.md

The blog should:
1. Use the topic description as the theme
2. Follow the PAS (Problem-Agitate-Solution) framework
3. Target the specified ICP (infer from topic)
4. Include YAML front matter with all required fields
5. Include the featured image prompt
6. Follow all SEO requirements from the skill file

Use data insights from GSC/GA4 where relevant.
"""

    return prompt


def main():
    parser = ArgumentParser(description="Weekly SEO blog scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    parser.add_argument("--force", action="store_true", help="Force regenerate even if recent")
    parser.add_argument("--week", type=int, help="Override week type (0=fitness, 1=local, 2=competitor, 3=data)")
    args = parser.parse_args()

    print(f"CB247 SEO Blog Scheduler — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Check if we should skip
    if should_skip_generation(args.force):
        print("Blog already generated this week. Use --force to regenerate.")
        sys.exit(0)

    # Load data
    gsc_data = load_json(STATE_DIR / "gsc-data.json")
    ga4_data = load_json(STATE_DIR / "ga4-data.json")

    # Get topic
    if args.week is not None:
        week_type = args.week % 4
        topic = {
            0: {"theme": "fitness_tips", "name": "Fitness Tips", "description": "Fitness tips and training guidance"},
            1: {"theme": "local_community", "name": "Local Community", "description": "Malaga/Ellenbrook community content"},
            2: {"theme": "competitor_comparison", "name": "Competitor Comparison", "description": "Value proposition vs competitors"},
            3: {"theme": "data_driven", "name": "Data-Driven Insights", "description": "Based on GSC/GA4 analysis"}
        }[week_type]
    else:
        topic = get_topic_for_week()
        if topic["theme"] == "data_driven":
            topic = find_data_driven_topic(gsc_data, ga4_data)

    print(f"Topic: {topic['name']}")
    print(f"Theme: {topic['theme']}")
    print(f"Description: {topic['description']}")

    if args.dry_run:
        print("\n[Dry run] Would generate blog with above topic.")
        print("Run without --dry-run to generate.")
        sys.exit(0)

    # Generate metadata
    metadata = generate_blog_metadata(topic, gsc_data, ga4_data)
    print(f"Target Keyword: {metadata['target_keyword']}")

    # Create the prompt for the AI to generate the blog
    prompt = create_blog_draft_prompt(metadata, gsc_data, ga4_data)

    print("\n" + "="*60)
    print("GENERATION PROMPT (copy to clipboard or use with Claude Code)")
    print("="*60)
    print(prompt)
    print("="*60)

    print(f"\nOutput file: outputs/blogs/seo-blog-{metadata['date']}.md")
    print("\nNote: This script generates the prompt. Run with Claude Code to execute.")


if __name__ == "__main__":
    main()