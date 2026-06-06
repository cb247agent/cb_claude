"""
schema.py — WorkQueueAction dataclass + validation.

Strict, typed schema. Every action must declare at least one KPI projection.
Validation is manual (no Pydantic dependency) to keep the package stdlib-only.
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
    "qualitative_assessment",
}

VALID_SOURCE_PAGES = {
    "seo-organic",
    "meta-ads",
    "google-ads",
    "organic-social",
    "gbp",
    "membership",
    "overview",
}

VALID_PRIORITY = {"P1", "P2", "P3"}
VALID_DATA_QUALITY = {"high", "medium", "low"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_VERDICT = {"winner", "partial_win", "no_change", "underperforming", "pending"}
VALID_KPI_STATUS = {"winner", "partial_win", "no_change", "underperforming"}


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


def to_jsonable(action: WorkQueueAction) -> dict:
    """Convert dataclass to JSON-serializable dict."""
    return asdict(action)
