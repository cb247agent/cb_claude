"""
schema.py — WorkQueueAction dataclass + validation.

Strict, typed schema. Every action must declare at least one KPI projection.
Validation is manual (no Pydantic dependency) to keep the package stdlib-only.

INTENTIONAL OMISSION — stage / kanban_stage
    WorkQueueAction does NOT carry a `stage` field. Kanban stage is owned
    by the Supabase `planner_status` table (one row per item, synced
    realtime to every open dashboard — see db/schema.sql).

    The JSON snapshot at state/work-queue.json is just the emitter output;
    stage is layered on by the dashboard's cbState.workQueue.fetchStages()
    at render time. This split lets multiple users move kanban cards in
    realtime without conflicting with the weekly strategist re-emit.

    Auditor note (13 Jun 2026): if you see "stage: MISSING" across all 82
    actions in a JSON dump, that's expected behaviour, NOT a bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional


# ── Enumerations (kept as constants — easier than Literal for runtime checks) ──

VALID_METRICS = {
    "gsc_position",
    "gsc_clicks_weekly",
    "gsc_impressions_weekly",
    "gsc_ctr",
    "ahrefs_domain_rating",
    "meta_ctr",
    "meta_cpa",
    "meta_cpm",
    "meta_cpc",
    "meta_results_weekly",
    "meta_ad_clicks_weekly",
    "meta_ad_reach_weekly",
    "google_ads_cpa",
    "google_ads_cpc",
    "google_ads_conversions_weekly",
    "google_ads_clicks_weekly",
    "google_ads_spend_weekly",
    "google_ads_ctr",
    "gbp_review_response_rate",
    "gbp_reviews_count",
    "gbp_photos_count",
    "gbp_posts_per_week",
    "gbp_rating",
    "ig_engagement_rate",
    "ig_followers",
    "membership_signups_weekly",
    "membership_cancellations_weekly",
    "membership_addon_active_count",
    "membership_future_cancellations",
    # MWCC-specific (childcare metrics)
    "mwcc_occupancy_pct",
    "mwcc_wage_ratio_pct",
    "mwcc_enrolments_weekly",
    "mwcc_enquiries_weekly",
    # ROI / paid→organic switch tracking (added 09 Jun 2026)
    "ads_spend_saved_monthly",          # per-keyword: $ saved by pausing paid in favour of organic
    "cumulative_ads_savings_monthly",   # aggregate: $ saved across all switches this month
    # Technical-SEO ops metrics (added 11 Jun 2026, SEO Strategist Option C)
    # The LLM strategist proposes ops actions like "fix 3 broken URLs" or
    # "add LocalBusiness schema" that are measurable as counts → 0. Without
    # these here the normaliser drops them.
    "pages_4xx",                        # count of URLs returning 4xx (target: 0)
    "schema_implemented",               # 0/1 — has the page got LocalBusiness JSON-LD yet
    "duplicate_metas",                  # count of pages sharing the same meta description (target: 0)
    "qualitative_assessment",
}

VALID_SOURCE_PAGES = {
    "seo-organic",
    "meta-ads",
    "google-ads",
    "organic-social",
    "gbp",
    "membership",
    "enrolment",     # MWCC-specific (childcare equivalent of membership)
    "opportunity",   # paid→organic switch + ROI tracking (added 09 Jun 2026)
    "overview",
}

VALID_PRIORITY = {"P1", "P2", "P3"}
VALID_DATA_QUALITY = {"high", "medium", "low"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_VERDICT = {"winner", "partial_win", "no_change", "underperforming", "pending"}
VALID_KPI_STATUS = {"winner", "partial_win", "no_change", "underperforming", "pending"}


# ── Records ──────────────────────────────────────────────────────────────────


@dataclass
class ProjectedKPI:
    """One measurable prediction. The MUST-HAVE on every action."""

    metric: str                                  # one of VALID_METRICS
    measurement_window_days: int                 # 1, 7, 14, 28 typical
    keyword: Optional[str] = None                # specific keyword (gsc, ahrefs)
    keyword_pattern: Optional[str] = None        # regex for cluster metrics
    baseline: Optional[float] = None             # current value
    target: Optional[float] = None               # specific target value
    delta_min: Optional[float] = None            # for ranged targets
    delta_max: Optional[float] = None
    confidence: Optional[str] = None             # high / medium / low

    def validate(self) -> List[str]:
        errors = []
        if not self.metric:
            errors.append("metric is required")
        elif self.metric not in VALID_METRICS:
            errors.append(f"metric '{self.metric}' not in VALID_METRICS")
        if self.measurement_window_days is None or self.measurement_window_days < 1:
            errors.append("measurement_window_days must be >= 1")
        if self.confidence is not None and self.confidence not in VALID_CONFIDENCE:
            errors.append(f"confidence must be one of {VALID_CONFIDENCE}")
        # Need either target OR (delta_min + delta_max)
        has_target = self.target is not None
        has_range = self.delta_min is not None and self.delta_max is not None
        if not (has_target or has_range):
            errors.append("must declare target OR (delta_min + delta_max)")
        return errors


@dataclass
class ActualKPI:
    """Measurement result, filled in by the +N-day verdict job."""

    metric: str
    keyword: Optional[str] = None
    keyword_pattern: Optional[str] = None
    baseline: Optional[float] = None
    target: Optional[float] = None
    actual: Optional[float] = None
    delta: Optional[float] = None
    target_hit: Optional[bool] = None
    status: Optional[str] = None              # one of VALID_KPI_STATUS

    def validate(self) -> List[str]:
        errors = []
        if self.status is not None and self.status not in VALID_KPI_STATUS:
            errors.append(f"status '{self.status}' not in VALID_KPI_STATUS")
        return errors


@dataclass
class WorkQueueAction:
    """One atomic action recommended by a performance page."""

    # Identity
    id: str                                   # e.g. seo-act-2026w23-001
    source_page: str                          # one of VALID_SOURCE_PAGES
    source_run_at: str                        # ISO timestamp

    # Display
    title: str
    description: str
    owner: str                                # team member name (e.g. "John")
    owner_role: str
    priority: str                             # P1 / P2 / P3
    effort_hours: float
    category: str                             # seo / meta / gbp / etc. (UI badge)
    data_quality: str                         # high / medium / low

    # Required: at least one KPI
    projected_kpis: List[ProjectedKPI]

    # Optional
    urgent: bool = False                      # uses shorter measurement window
    related_actions: List[str] = field(default_factory=list)
    # Agent Action Contract (07 Jun 2026) — when an action comes from an LLM
    # agent (not a rule-based emitter), source_agent identifies which agent
    # proposed it. Used for per-agent hit-rate tracking.
    # Examples: "strategist" · "seo-agent" · "competitor-spy" · "mwcc-strategist"
    source_agent: Optional[str] = None

    # Wave 5 (10 Jun 2026) — Promo Pipeline linkage. When an action is a child
    # of a parent promo concept (e.g. a reel for "Don't Quit Winter"), this
    # holds the promo ID. The dashboard uses it to:
    #   1. Render "Awaiting Assets" badge on In Progress cards whose parent
    #      promo has no gdrive_folder_url yet
    #   2. Cascade promo stage changes to child items (future)
    parent_promo_id: Optional[str] = None

    # Measurement-time (filled later)
    actual_kpis: Optional[List[ActualKPI]] = None
    overall_verdict: Optional[str] = None     # one of VALID_VERDICT
    measured_at: Optional[str] = None
    notes_human: str = ""

    def validate(self) -> List[str]:
        errors = []
        if not self.id:
            errors.append("id is required")
        if not self.title:
            errors.append("title is required")
        if not self.description:
            errors.append("description is required")
        if not self.owner:
            errors.append("owner is required")
        if self.priority not in VALID_PRIORITY:
            errors.append(f"priority must be one of {VALID_PRIORITY}, got '{self.priority}'")
        if self.data_quality not in VALID_DATA_QUALITY:
            errors.append(f"data_quality must be one of {VALID_DATA_QUALITY}, got '{self.data_quality}'")
        if self.source_page not in VALID_SOURCE_PAGES:
            errors.append(f"source_page '{self.source_page}' not in VALID_SOURCE_PAGES")
        if self.effort_hours is None or self.effort_hours <= 0:
            errors.append("effort_hours must be > 0")
        if not self.projected_kpis:
            errors.append("at least one projected_kpi is required (strict-schema rule)")
        else:
            for i, kpi in enumerate(self.projected_kpis):
                for err in kpi.validate():
                    errors.append(f"projected_kpis[{i}]: {err}")
        if self.overall_verdict is not None and self.overall_verdict not in VALID_VERDICT:
            errors.append(f"overall_verdict '{self.overall_verdict}' not in VALID_VERDICT")
        if self.actual_kpis:
            for i, ak in enumerate(self.actual_kpis):
                for err in ak.validate():
                    errors.append(f"actual_kpis[{i}]: {err}")
        return errors


@dataclass
class WorkQueue:
    """Top-level container with metadata + actions."""

    generated_at: str
    generator_version: str
    actions: List[WorkQueueAction]

    def validate(self) -> List[str]:
        errors = []
        ids_seen = set()
        for i, a in enumerate(self.actions):
            for err in a.validate():
                errors.append(f"actions[{i}] ({a.id or '<no-id>'}): {err}")
            if a.id in ids_seen:
                errors.append(f"duplicate id: {a.id}")
            ids_seen.add(a.id)
        return errors


# ── Helpers ──────────────────────────────────────────────────────────────────


def now_iso() -> str:
    """Current UTC time as ISO 8601."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def week_iso(date: Optional[datetime] = None) -> str:
    """ISO week format YYYYwWW, e.g. 2026w23."""
    d = date or datetime.now(timezone.utc)
    year, week, _ = d.isocalendar()
    return f"{year}w{week:02d}"


def make_action_id(source_prefix: str, week: Optional[str] = None, serial: int = 1) -> str:
    """e.g. make_action_id('seo', '2026w23', 1) → 'seo-act-2026w23-001'"""
    wk = week or week_iso()
    return f"{source_prefix}-act-{wk}-{serial:03d}"


# Closed-loop safety net (12 Jun 2026): every action MUST be attributable
# to a source agent for per-agent hit-rate tracking. The 6 rule emitters
# historically forgot to set source_agent; this mapping derives it from
# the id prefix so we never end up with None/?/orphan rows again. Any new
# emitter adding a new id prefix MUST extend this map.
_ID_PREFIX_TO_SOURCE_AGENT = {
    "gbp-act":  "gbp-emitter",
    "mem-act":  "membership-emitter",
    "soc-act":  "social-emitter",
    "seo-act":  "seo-emitter",            # legacy (now LLM strategist)
    "gads-act": "google-ads-emitter",     # legacy (now LLM strategist)
    "meta-act": "meta-emitter",           # legacy (now LLM strategist)
    "opp-act":  "opportunity-emitter",
    "attr-act": "attribution-emitter",
    "prop":     "promo-concept-emitter",  # 'prop-<source>-<week>-<hash>'
}


def derive_source_agent(action_id: str) -> Optional[str]:
    """Infer source_agent from an action id's prefix when the field is empty.

    e.g. 'gbp-act-2026w23-001' → 'gbp-emitter'.
         'prop-seo-organic-2026w23-1a2b' → 'promo-concept-emitter'.
         'seo-strategist-act-2026w24-007' → None  (must be set explicitly
         by the agent extractor, since 'seo-strategist' shares the
         'seo-' prefix but isn't a rule emitter)
    """
    if not action_id:
        return None
    if action_id.startswith("prop-"):
        return _ID_PREFIX_TO_SOURCE_AGENT["prop"]
    # 'seo-strategist-act-*' must NOT match 'seo-act' — check more specific
    # prefixes first
    aid = action_id
    parts = aid.split("-")
    if len(parts) >= 2:
        head_2 = "-".join(parts[:2])    # e.g. "gbp-act", "seo-act"
        if head_2 in _ID_PREFIX_TO_SOURCE_AGENT:
            return _ID_PREFIX_TO_SOURCE_AGENT[head_2]
    return None


def to_jsonable(action: WorkQueueAction) -> dict:
    """Convert dataclass to JSON-serializable dict.

    Safety net (12 Jun 2026): if source_agent is unset, derive it from
    the id prefix. Keeps existing emitters working without per-emitter
    edits while preventing new orphans.
    """
    d = asdict(action)
    if not d.get("source_agent"):
        derived = derive_source_agent(d.get("id", ""))
        if derived:
            d["source_agent"] = derived
    return d
