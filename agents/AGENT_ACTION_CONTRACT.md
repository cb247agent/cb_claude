# Agent Action Contract

**Version: 1.0 · Effective from 07 Jun 2026**

This is a binding contract that every LLM-driven agent in `agents/*.yml` (CB247) and `agents/mwcc/*.yml` (MWCC) MUST follow when writing its markdown output.

## Why this contract exists

Before this contract, agents produced rich strategic narrative markdown — but their recommendations were free-text. Humans had to:
- Read the narrative
- Manually decide what to do
- Manually track which recommendation was actioned
- Manually assess whether it worked

Result: agent recommendations were **un-measurable**. We couldn't compute a hit rate per agent. There was no closed loop.

This contract makes every agent recommendation **measurable** by requiring a structured JSON block at the end of the markdown. The block enters the same Work Queue + Performance Review loop as rule-based emitter actions.

---

## The contract

Every agent's output markdown MUST end with a fenced code block tagged `json proposed_actions`. The block contains a JSON array of zero or more `WorkQueueAction`-shaped objects.

If the agent has no recommendations to make this week, the block is an empty array `[]`. Do not skip the block — its absence will be logged as a contract violation.

### Required JSON shape

```json proposed_actions
[
  {
    "title": "Increase Reformer Pilates page word count from 280 → 800",
    "description": "Page targets 'reformer pilates malaga' — currently 280 words, ranks #11. Top 3 competitors have 1,200+ words. Expanding will lift ranking to top 5.",
    "owner": "John",
    "owner_role": "SEO / Web",
    "priority": "P2",
    "effort_hours": 4,
    "category": "seo-organic",
    "data_quality": "high",
    "projected_kpis": [
      {
        "metric": "gsc_position",
        "keyword": "reformer pilates malaga",
        "baseline": 11,
        "target": 5,
        "measurement_window_days": 21,
        "confidence": "medium"
      }
    ]
  }
]
```

### Required fields

| Field | Type | Notes |
|---|---|---|
| `title` | string | Concise — 80 chars max |
| `description` | string | The "why" + the "how" — 200-400 chars |
| `owner` | string | Real team member name (Tia / Denver / Angela / Mark / John / Joanne / Kelley / Jordan / Shauna) |
| `owner_role` | string | Their role title |
| `priority` | enum | `"P1"` (act this week) · `"P2"` (next 2 weeks) · `"P3"` (backlog) · `"P4"` (someday) |
| `effort_hours` | number | Decimal allowed — `0.5`, `4`, `8` |
| `category` | string | One of: `seo-organic` · `meta-ads` · `google-ads` · `gbp` · `organic-social` · `enrolment` · `membership` |
| `data_quality` | enum | `"high"` · `"medium"` · `"low"` — your confidence in the data this action is based on |
| `projected_kpis` | array | At least one — see below |

### `projected_kpis[]` shape

Each KPI projection makes the action measurable:

```json
{
  "metric": "gsc_position",
  "keyword": "reformer pilates malaga",
  "baseline": 11,
  "target": 5,
  "measurement_window_days": 21,
  "confidence": "medium"
}
```

| Field | Notes |
|---|---|
| `metric` | One of `VALID_METRICS` in `scripts/work_queue/schema.py` |
| `keyword` (optional) | When the metric is keyword-scoped (e.g. GSC position) |
| `baseline` | The metric's current value before the action |
| `target` | The value you expect after the measurement window |
| `measurement_window_days` | 14 for typical SEO/Meta · 21 for content · 28 for backlinks |
| `confidence` | `"high"` · `"medium"` · `"low"` |

### Auto-populated fields

The extractor adds these automatically — agents should NOT include them:

- `id` — auto-generated from agent slug + ISO week + title hash
- `source_run_at` — auto-set to extraction timestamp
- `source_agent` — auto-set from filename slug (e.g. `strategist`, `seo-agent`)
- `source_page` — derived from category if not specified

---

## How extraction works

```
agent produces outputs/research/strategist-2026-06-09.md
       ↓
weekly cron runs: python scripts/extract_agent_actions.py --business cb247
       ↓
Extractor finds the ```json proposed_actions block
       ↓
Validates against WorkQueueAction schema
       ↓
Merges into state/work-queue.json (dedup by id)
       ↓
sync_to_supabase.py upserts → mwcc_work_queue_actions / work_queue_actions
       ↓
Dashboard renders the action in the Work Queue page
       ↓
Team executes through the 6-stage approval flow
       ↓
14/21/28 days later: measurement_runner.py compares projected vs actual
       ↓
Verdict assigned: Winner / Partial Win / No Change / Underperforming
       ↓
Performance Review page shows hit rate per agent
```

---

## Examples by agent type

### Strategist (synthesises everything)

```json proposed_actions
[
  {
    "title": "Reduce Google Ads spend on 'gym malaga' — SEO now ranks #2",
    "description": "Organic position for 'gym malaga' improved from #6 → #2 this week. Per-Performance Agent, organic now offsets paid for this keyword. Pause Google Ads exact-match bid + reallocate $80/week to 'reformer pilates malaga' which is still pos #11.",
    "owner": "Tia",
    "owner_role": "OS Owner / Paid Ads",
    "priority": "P1",
    "effort_hours": 0.5,
    "category": "google-ads",
    "data_quality": "high",
    "projected_kpis": [
      { "metric": "google_ads_spend_weekly", "baseline": 240, "target": 160, "measurement_window_days": 14, "confidence": "high" },
      { "metric": "gsc_position", "keyword": "gym malaga", "baseline": 2, "target": 2, "measurement_window_days": 14, "confidence": "medium" }
    ]
  }
]
```

### SEO Agent

```json proposed_actions
[
  {
    "title": "Build dedicated landing page for 'reformer pilates malaga'",
    "description": "Current: no dedicated page — keyword rolls up to /classes which is too broad. Volume 880/mo, KD 12. Build a 1,500-word page with H1 'Reformer Pilates Classes in Malaga', class schedule, pricing CTA, member testimonial video.",
    "owner": "John",
    "owner_role": "SEO / Web",
    "priority": "P2",
    "effort_hours": 8,
    "category": "seo-organic",
    "data_quality": "high",
    "projected_kpis": [
      { "metric": "gsc_position", "keyword": "reformer pilates malaga", "baseline": 21, "target": 8, "measurement_window_days": 28, "confidence": "medium" },
      { "metric": "gsc_clicks_weekly", "keyword": "reformer pilates malaga", "baseline": 0, "target": 25, "measurement_window_days": 28, "confidence": "low" }
    ]
  }
]
```

### Research Agent (might propose 0 actions — that's valid)

```json proposed_actions
[]
```

(Empty array is allowed — research agents observe markets, they often don't directly propose actions. The narrative still informs other agents.)

---

## Schema reference

Full validation rules in `scripts/work_queue/schema.py` (WorkQueueAction dataclass). The extractor (`scripts/extract_agent_actions.py`) does light validation; strict validation happens at sync time.

If you're an agent author and unsure whether your block is valid, run:

```bash
python scripts/extract_agent_actions.py --business cb247
```

It will print any contract violations.

---

## Backwards compatibility

Agents that haven't been updated to follow the contract continue to work — their markdown is still consumed by humans reading it. But their recommendations are not measurable until the contract is added.

Migration path: as each agent gets its first action block added, run the extractor once to backfill that agent's recommendations into the work queue.

---

## Why this fixes the weakness

Before: agent outputs were "judgement calls" — Tia read them and made decisions, but the decisions weren't tied back to the agent.

After: every recommendation has a baseline, target, and measurement window. After the window closes, `measurement_runner.py` knows whether it worked. Hit rate per agent becomes computable:

```
strategist:   8 winners / 12 measured  = 67% hit rate
seo-agent:    5 winners / 8 measured   = 63% hit rate
paid-ads:    11 winners / 14 measured  = 79% hit rate
```

Underperforming agents become visible. Tia can tune prompts, swap models, or retire agents that don't justify their cost.
