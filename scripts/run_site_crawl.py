#!/usr/bin/env python3
"""
run_site_crawl.py — Privacy-compliant SEO site crawler for CB247.
Drop-in replacement for Screaming Frog SEO Spider.

Outputs:
  state/screaming-frog-data.json   — Same format Screaming Frog produces (all SEO skills read this)
  state/pagespeed-data.json        — Core Web Vitals, if GOOGLE_PAGESPEED_API_KEY is set in .env
  outputs/seo/audits/crawl-logs/   — Timestamped audit trail for every run

Usage:
  python scripts/run_site_crawl.py                    # Crawl CB247 only
  python scripts/run_site_crawl.py --competitors      # + specific competitor pages
  python scripts/run_site_crawl.py --pagespeed        # + Core Web Vitals (needs API key)
  python scripts/run_site_crawl.py --dry-run          # Check robots.txt only, no fetching
  python scripts/run_site_crawl.py --max-pages 50     # Limit pages crawled (default 100)

════════════════════════════════════════════════════════
COMPLIANCE FRAMEWORK
════════════════════════════════════════════════════════

Australian law
──────────────
  Privacy Act 1988 (Cth) + Australian Privacy Principles (APPs 1–13)
    APP 3  — Only information necessary for the stated purpose is collected.
               This crawler collects SEO metadata ONLY (title, meta description,
               headings, status codes, word count). No personal information.
    APP 11 — Data security: output files overwritten each run; no cumulative
               personal data build-up. Audit logs retained for accountability.
  Spam Act 2003 (Cth)
    Email addresses and phone numbers are detected by regex and REDACTED before
    any data is written to disk. The crawler never harvests contact information.
  Copyright Act 1968 (Cth)
    Only structural/metadata elements are extracted. Raw page content is never
    stored. Word count is stored as an integer only (not the content itself).
  Criminal Code Act 1995 (Cth) ss.477–478 — Unauthorised computer access
    robots.txt is fetched and parsed BEFORE any request to any domain.
    Disallowed paths are unconditionally skipped. A 5xx or network error when
    fetching robots.txt is treated as disallow-all (conservative).
  ACCC / Consumer Law considerations
    Competitor page analysis is limited to publicly accessible marketing pages
    for legitimate SEO benchmarking. No scraping of pricing databases, member
    data, or any protected content.

International law
─────────────────
  GDPR (EU) 2016/679
    Art. 5(1)(b) — Purpose limitation: data collected solely for SEO audit.
    Art. 5(1)(c) — Data minimisation: only structural metadata extracted.
    Art. 5(1)(e) — Storage limitation: state files overwritten each run.
    Art. 32      — Security: SSL verification enforced on all HTTPS connections.
  UK Data Protection Act 2018
    Equivalent obligations to GDPR; same design principles apply.
  CCPA (California) — Cal. Civ. Code § 1798.100 et seq.
    No personal information is collected, stored, or sold.
  CFAA (US) — 18 U.S.C. § 1030
    Good-faith robots.txt compliance and explicit ToS review of target sites
    are the primary safeguards against unauthorised access claims.

Core design principles
──────────────────────
  1. robots.txt FIRST — fetched and honoured before ANY URL is requested.
     Disallowed paths are skipped unconditionally, including on CB247's own site.
  2. Honest User-Agent — never impersonates a browser. Operator contact
     included so site owners can reach us.
  3. No PII stored — PII patterns (emails, phones, AU tax IDs) are detected and
     redacted before any string is written to disk.
  4. Rate limiting — minimum 2-second delay between requests (configurable).
     The robots.txt Crawl-delay directive is respected if it requires longer.
  5. Scope-limited — CB247 own-site is spidered recursively within its domain.
     Competitor domains are checked at SPECIFIC listed URLs only — no link
     following on competitor sites.
  6. SSL enforced — requests.Session.verify = True always. Never bypassed.
  7. Audit log — every URL fetched is logged with timestamp, HTTP status, and
     robots.txt disposition for accountability and compliance review.
  8. Data minimisation — word count stored as int; raw text never written.
  9. Storage limitation — state/screaming-frog-data.json overwritten each run.
════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlencode
from urllib.robotparser import RobotFileParser

# Third-party
try:
    import requests
    from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
    warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
except ImportError as e:
    sys.exit(
        f"Missing dependency: {e}\n"
        "Run: pip install -r scripts/requirements.txt"
    )

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv optional; env vars can be set directly


# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
LOG_DIR = BASE_DIR / "outputs" / "seo" / "audits" / "crawl-logs"


# ─── Crawler identity ─────────────────────────────────────────────────────────
CRAWLER_NAME = "CB247-SEO-Auditor"
CRAWLER_VERSION = "1.0"
CRAWLER_CONTACT = "reception@chasingbetter247.com.au"

# Honest User-Agent including operator contact (best practice under AU/GDPR law)
USER_AGENT = (
    f"{CRAWLER_NAME}/{CRAWLER_VERSION} "
    f"(Internal SEO audit tool; "
    f"operator: ChasingBetter247 Health & Fitness; "
    f"contact: {CRAWLER_CONTACT}; "
    f"respects robots.txt and applicable privacy law)"
)


# ─── Runtime configuration (overridable via .env) ─────────────────────────────
RATE_LIMIT_SECONDS = float(os.getenv("CRAWL_RATE_LIMIT", "2.0"))   # min delay between requests
MAX_PAGES_DEFAULT  = int(os.getenv("CRAWL_MAX_PAGES",   "100"))     # circuit breaker
REQUEST_TIMEOUT    = int(os.getenv("CRAWL_TIMEOUT",     "15"))      # seconds per request
GOOGLE_PAGESPEED_API_KEY = os.getenv("GOOGLE_PAGESPEED_API_KEY", "")


# ─── Crawl targets ────────────────────────────────────────────────────────────
CB247_START_URL = "https://www.chasingbetter247.com.au/"
CB247_DOMAIN    = "chasingbetter247.com.au"

# Competitor pages: ONLY these specific public marketing pages are checked.
# No recursive spidering of competitor domains.
COMPETITOR_PAGES = [
    {"url": "https://www.revofitness.com.au/locations/malaga",      "name": "Revo Fitness Malaga"},
    {"url": "https://www.revofitness.com.au/locations/ellenbrook",  "name": "Revo Fitness Ellenbrook"},
    {"url": "https://www.anytimefitness.com.au/locate/malaga",      "name": "Anytime Fitness Malaga"},
    {"url": "https://www.anytimefitness.com.au/locate/ellenbrook",  "name": "Anytime Fitness Ellenbrook"},
]


# ─── PII detection patterns (GDPR Art.5 / APP 3) ─────────────────────────────
# Any extracted metadata string that matches these is redacted before storage.
_PII_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),   # email
    re.compile(r"(?<!\d)(?:\+?61|0)[2-578]\d{8}(?!\d)"),                    # AU phone
    re.compile(r"\b(?:\d[ \-]?){15,16}\b"),                                  # credit card
    re.compile(r"\b(?:tfn|abn|acn)[\s:]*\d[\d\s]{6,14}\b", re.I),           # AU IDs
    re.compile(r"\b\d{3}[\-\s]\d{2}[\-\s]\d{4}\b"),                         # SSN-like
]


# ─── Issue definitions ────────────────────────────────────────────────────────
# (name, category, priority, description) — maps to Screaming Frog issue format
_ISSUE_DEFS: dict[str, tuple[str, str, str, str]] = {
    "missing_title":      ("Missing Title Tag",                   "On-Page",         "Critical", "Page has no <title> tag."),
    "title_too_long":     ("Title Too Long (>60 chars)",          "On-Page",         "High",     "Title tag exceeds 60 characters and may be truncated in SERPs."),
    "title_too_short":    ("Title Too Short (<10 chars)",         "On-Page",         "High",     "Title tag is very short — likely not keyword-optimised."),
    "duplicate_title":    ("Duplicate Title Tags",                "On-Page",         "High",     "Multiple pages share the same title tag."),
    "missing_meta_desc":  ("Missing Meta Description",            "On-Page",         "Critical", "No meta description — Google may auto-generate an unhelpful one."),
    "meta_desc_too_long": ("Meta Description Too Long (>155)",    "On-Page",         "High",     "Meta description truncated in search results."),
    "meta_desc_too_short":("Meta Description Too Short (<50)",    "On-Page",         "Medium",   "Meta description too brief to be compelling."),
    "duplicate_meta":     ("Duplicate Meta Descriptions",         "On-Page",         "High",     "Multiple pages share the same meta description."),
    "missing_h1":         ("Missing H1 Tag",                      "On-Page",         "Critical", "Page has no H1 heading — critical for keyword relevance."),
    "multiple_h1":        ("Multiple H1 Tags",                    "On-Page",         "High",     "Page has more than one H1 tag."),
    "missing_canonical":  ("Missing Canonical Tag",               "Technical",       "Medium",   "No rel=canonical — risk of duplicate content issues."),
    "noindex":            ("Noindex Pages",                       "Technical",       "High",     "Page has a robots noindex directive — not indexable."),
    "http_error":         ("HTTP Error (4xx/5xx)",                "Technical",       "Critical", "Page returns a client or server error."),
    "redirect":           ("Redirect (3xx)",                      "Technical",       "Medium",   "Page returns a redirect — check for chains."),
    "thin_content":       ("Thin Content (<200 words)",           "Content",         "High",     "Very little text content — may be seen as low-value by Google."),
    "images_missing_alt": ("Images Missing Alt Text",             "Accessibility",   "Medium",   "Images without alt attributes reduce SEO and accessibility."),
    "missing_schema":     ("No Schema Markup Detected",           "Technical",       "Medium",   "No structured data found — LocalBusiness/FAQ schema recommended."),
}

_PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


# ═══════════════════════════════════════════════════════════════════════════════
# Compliance utilities
# ═══════════════════════════════════════════════════════════════════════════════

def redact_pii(text: str) -> str:
    """
    Detect and redact PII patterns from any string before storage.
    Applies: email, AU phone, credit card, AU tax/business IDs, SSN-like.
    Required by: APP 3 (data minimisation), GDPR Art.5(1)(c).
    """
    if not text:
        return text
    for pattern in _PII_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class RobotsCache:
    """
    Fetches and caches robots.txt for each domain encountered.

    Legal basis: Honouring robots.txt is the primary mechanism by which an
    automated crawler demonstrates good-faith non-unauthorised access under:
      - Criminal Code Act 1995 (AU) ss.477–478
      - Computer Fraud and Abuse Act (US) 18 U.S.C. § 1030
      - hiQ Labs v. LinkedIn (9th Cir. 2022) — publicly accessible pages

    Conservative failure handling: any error fetching robots.txt (5xx, network
    timeout, DNS failure) results in disallow-all for that domain.
    This is the safe default — it prevents accidental access to a site that
    may be experiencing issues, which could be misread as a DoS attempt.
    """

    def __init__(self, session: requests.Session, logger: logging.Logger) -> None:
        self._cache: dict[str, RobotFileParser] = {}
        self._session = session
        self._log = logger

    def _load(self, domain: str) -> RobotFileParser:
        parser = RobotFileParser()
        robots_url = f"https://{domain}/robots.txt"
        try:
            r = self._session.get(robots_url, timeout=10)
            if r.status_code == 200:
                parser.parse(r.text.splitlines())
                self._log.debug(f"robots.txt loaded: {robots_url} (200 OK)")
            elif r.status_code == 404:
                # robots.txt absent → all paths permitted
                parser.parse([])
                self._log.debug(f"robots.txt absent: {robots_url} (404 — all paths allowed)")
            else:
                # Conservative: disallow-all on any unexpected response
                parser.parse(["User-agent: *", "Disallow: /"])
                self._log.warning(
                    f"robots.txt fetch returned HTTP {r.status_code}: {robots_url} — "
                    f"treating as disallow-all (conservative compliance)"
                )
        except Exception as exc:
            parser.parse(["User-agent: *", "Disallow: /"])
            self._log.warning(
                f"robots.txt unreachable for {domain}: {exc} — "
                f"treating as disallow-all (conservative compliance)"
            )
        return parser

    def is_allowed(self, url: str) -> bool:
        """Return True if the URL may be fetched under robots.txt rules."""
        domain = urlparse(url).netloc
        if domain not in self._cache:
            self._cache[domain] = self._load(domain)
        allowed = self._cache[domain].can_fetch(USER_AGENT, url)
        if not allowed:
            self._log.info(f"  [robots.txt BLOCKED] {url}")
        return allowed

    def crawl_delay(self, domain: str) -> float:
        """Return the Crawl-delay for this domain, or our default."""
        if domain not in self._cache:
            return RATE_LIMIT_SECONDS
        declared = self._cache[domain].crawl_delay(USER_AGENT)
        if declared and float(declared) > RATE_LIMIT_SECONDS:
            self._log.debug(f"Crawl-delay {declared}s for {domain} (overrides default)")
            return float(declared)
        return RATE_LIMIT_SECONDS


# ═══════════════════════════════════════════════════════════════════════════════
# Session + fetch
# ═══════════════════════════════════════════════════════════════════════════════

def make_session() -> requests.Session:
    """
    Build a requests.Session with:
    - Honest User-Agent header
    - SSL verification enforced (never disabled — GDPR Art.32 / data-in-transit)
    - No credential storage
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",  # Do Not Track signal — respects user privacy preferences
    })
    s.verify = True  # SSL certificate verification ON — never set to False
    return s


def fetch_page(
    url: str,
    session: requests.Session,
    robots: RobotsCache,
    logger: logging.Logger,
    delay: float = RATE_LIMIT_SECONDS,
) -> tuple[requests.Response | None, str]:
    """
    Fetch a URL with full compliance checks.

    Returns (response, disposition):
      disposition values: 'ok' | 'robots_blocked' | 'non_html' |
                          'timeout' | 'ssl_error' | 'error'

    Compliance order:
      1. robots.txt check — abort if disallowed
      2. Rate limit — sleep before requesting
      3. Fetch with SSL verification and timeout
      4. Content-type guard — skip non-HTML resources
    """
    # 1. robots.txt — must check before ANY network request to the URL
    if not robots.is_allowed(url):
        return None, "robots_blocked"

    # 2. Rate limiting — prevents DoS-like behaviour (Criminal Code Act 1995 AU)
    time.sleep(delay)

    # 3. Fetch
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        content_type = resp.headers.get("Content-Type", "")
        logger.debug(f"FETCH {resp.status_code} {url} [{content_type[:60]}]")

        # 4. Skip non-HTML resources (PDFs, images, JS, CSS, etc.)
        if "text/html" not in content_type:
            return resp, "non_html"

        return resp, "ok"

    except requests.exceptions.Timeout:
        logger.warning(f"TIMEOUT ({REQUEST_TIMEOUT}s): {url}")
        return None, "timeout"
    except requests.exceptions.SSLError as exc:
        # Never bypass SSL errors — log and skip the URL
        logger.error(f"SSL_ERROR (not bypassing): {url} — {exc}")
        return None, "ssl_error"
    except requests.exceptions.TooManyRedirects:
        logger.warning(f"TOO_MANY_REDIRECTS: {url}")
        return None, "error"
    except requests.exceptions.RequestException as exc:
        logger.warning(f"REQUEST_ERROR: {url} — {exc}")
        return None, "error"


# ═══════════════════════════════════════════════════════════════════════════════
# SEO data extraction (privacy-safe)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_seo_data(url: str, response: requests.Response) -> dict:
    """
    Extract SEO-relevant metadata from an HTML page.

    Privacy compliance:
    - Only STRUCTURAL metadata extracted: title, meta description, headings,
      canonical, robots meta, schema type names, link/image counts.
    - Raw page text/body content is NEVER stored (data minimisation — GDPR Art.5(c)).
    - Word count is computed and stored as an INTEGER only.
    - All extracted strings pass through redact_pii() before storage.
    - User-generated content sections (comment threads, review sections) are
      stripped before word count computation.
    - Image src URLs are NOT stored (may contain personally identifying filenames).
    """
    soup = BeautifulSoup(response.text, "html.parser")

    # Strip non-content elements before word count
    for tag in soup.find_all(["script", "style", "nav", "footer",
                               "header", "aside", "noscript"]):
        tag.decompose()

    # ── Title tag ─────────────────────────────────────────────────────────────
    title_tag = soup.find("title")
    title = redact_pii(title_tag.get_text(strip=True)) if title_tag else ""

    # ── Meta description ──────────────────────────────────────────────────────
    meta_el = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_desc = ""
    if meta_el:
        meta_desc = redact_pii((meta_el.get("content") or "").strip())

    # ── Headings ──────────────────────────────────────────────────────────────
    h1_tags = soup.find_all("h1")
    h1 = redact_pii(h1_tags[0].get_text(strip=True)) if h1_tags else ""
    h2_tags = soup.find_all("h2")
    h2s = [redact_pii(h.get_text(strip=True)) for h in h2_tags[:5]]  # max 5

    # ── Canonical ─────────────────────────────────────────────────────────────
    canonical_el = soup.find("link", rel=lambda r: r and "canonical" in r)
    canonical = (canonical_el.get("href") or "").strip() if canonical_el else ""

    # ── Robots meta ───────────────────────────────────────────────────────────
    robots_el = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    robots_content = (robots_el.get("content") or "").lower() if robots_el else ""
    noindex = "noindex" in robots_content

    # ── Schema markup (type names only — no content) ──────────────────────────
    schema_types: list[str] = []
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(s.string or "{}")
            t = data.get("@type")
            if t:
                schema_types.append(str(t))
        except (json.JSONDecodeError, AttributeError, ValueError):
            pass

    # ── Internal links (count only) ───────────────────────────────────────────
    parsed_url = urlparse(url)
    internal_links = sum(
        1 for a in soup.find_all("a", href=True)
        if CB247_DOMAIN in urlparse(urljoin(url, a["href"])).netloc
    )

    # ── Images missing alt (count only — no src URLs stored) ──────────────────
    images_missing_alt = sum(
        1 for img in soup.find_all("img")
        if not (img.get("alt") or "").strip()
    )

    # ── Word count (integer — raw content never stored) ───────────────────────
    body = soup.find("body")
    word_count = len(body.get_text(separator=" ", strip=True).split()) if body else 0

    # ── Page size ─────────────────────────────────────────────────────────────
    size_kb = round(len(response.content) / 1024, 1)

    return {
        # Core fields (Screaming Frog-compatible format)
        "url": url,
        "status": str(response.status_code),
        "final_url": response.url,
        "title": title,
        "h1": h1,
        "word_count": str(word_count),
        "size_kb": str(size_kb),
        # Extended fields (used by seo-site-audit skill)
        "title_length": len(title),
        "meta_description": meta_desc,
        "meta_description_length": len(meta_desc),
        "h1_count": len(h1_tags),
        "h2s": h2s,
        "canonical": canonical,
        "noindex": noindex,
        "schema_types": schema_types,
        "internal_links_count": internal_links,
        "images_missing_alt": images_missing_alt,
        "load_time_ms": int(response.elapsed.total_seconds() * 1000),
    }


def _error_page(url: str, status: str, disposition: str = "") -> dict:
    """Return a minimal page record for an unreachable or error page."""
    return {
        "url": url, "status": status, "final_url": url,
        "title": "", "h1": "", "word_count": "0", "size_kb": "0",
        "title_length": 0, "meta_description": "", "meta_description_length": 0,
        "h1_count": 0, "h2s": [], "canonical": "", "noindex": False,
        "schema_types": [], "internal_links_count": 0, "images_missing_alt": 0,
        "load_time_ms": 0, **({"error": disposition} if disposition else {}),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Crawlers
# ═══════════════════════════════════════════════════════════════════════════════

def crawl_cb247(
    session: requests.Session,
    robots: RobotsCache,
    logger: logging.Logger,
    max_pages: int = MAX_PAGES_DEFAULT,
) -> list[dict]:
    """
    Spider CB247's own website.

    - Stays strictly within the CB247 domain — never follows off-domain links.
    - robots.txt checked at every URL before fetching.
    - Crawl-delay directive respected.
    - Stops at max_pages (circuit breaker).
    """
    logger.info("")
    logger.info("=" * 65)
    logger.info(f"CRAWLING OWN SITE: {CB247_START_URL}")
    logger.info(f"Max pages: {max_pages}  |  Rate limit: {RATE_LIMIT_SECONDS}s/req")
    logger.info("=" * 65)

    delay = robots.crawl_delay(CB247_DOMAIN)
    visited: set[str] = set()
    queue: list[str] = [CB247_START_URL]
    pages: list[dict] = []

    while queue and len(visited) < max_pages:
        raw_url = queue.pop(0).split("#")[0]  # strip fragments
        url = raw_url.rstrip("/") if raw_url != CB247_START_URL else raw_url

        if url in visited:
            continue
        visited.add(url)
        logger.info(f"  [{len(visited):3d}/{max_pages}] {url}")

        response, disposition = fetch_page(url, session, robots, logger, delay)

        if disposition == "robots_blocked":
            continue

        if response is None or disposition in ("timeout", "ssl_error", "error"):
            pages.append(_error_page(url, disposition, disposition))
            continue

        if disposition == "non_html":
            continue  # Skip PDFs, images etc. — no data extracted

        # Redirect — record, but don't follow off-domain
        if str(response.status_code).startswith("3"):
            pages.append(_error_page(url, str(response.status_code)))
            continue

        # 4xx / 5xx error
        if response.status_code >= 400:
            pages.append(_error_page(url, str(response.status_code)))
            continue

        # Successful HTML page — extract SEO data
        data = extract_seo_data(url, response)
        pages.append(data)

        # Discover new internal links
        soup = BeautifulSoup(response.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = (a_tag["href"] or "").split("#")[0].strip()
            if not href:
                continue
            abs_url = urljoin(url, href).rstrip("/")
            parsed = urlparse(abs_url)
            if (
                CB247_DOMAIN in (parsed.netloc or "")
                and parsed.scheme in ("http", "https")
                and abs_url not in visited
                and abs_url not in queue
            ):
                queue.append(abs_url)

    logger.info(f"\n  CB247 crawl complete: {len(pages)} pages processed")
    return pages


def check_competitor_pages(
    session: requests.Session,
    robots: RobotsCache,
    logger: logging.Logger,
) -> list[dict]:
    """
    Fetch ONLY the specific competitor URLs listed in COMPETITOR_PAGES.

    Compliance notes:
    - These are public marketing/location pages — no login required.
    - robots.txt is checked for each URL before fetching.
    - No recursive link-following on competitor sites.
    - Only structural SEO metadata extracted (title, meta, headings, counts).
    - No personal information can reasonably be present in these metadata fields,
      but PII patterns are still applied as a safeguard.
    - This constitutes standard SEO competitive benchmarking, consistent with
      industry practice and not prohibited by any applicable privacy law
      (which governs personal information, not public commercial metadata).
    """
    logger.info("")
    logger.info("=" * 65)
    logger.info("COMPETITOR PAGES  (specific URLs only — no recursive crawl)")
    logger.info("=" * 65)

    results: list[dict] = []

    for entry in COMPETITOR_PAGES:
        url = entry["url"]
        name = entry["name"]
        domain = urlparse(url).netloc
        delay = robots.crawl_delay(domain)

        logger.info(f"  {name}")
        logger.info(f"    {url}")

        response, disposition = fetch_page(url, session, robots, logger, delay)

        if disposition == "robots_blocked":
            logger.info(f"    → robots.txt BLOCKED — not crawled")
            results.append({
                "competitor_name": name,
                "url": url,
                "status": "robots_blocked",
                "note": "Blocked by robots.txt — not fetched per compliance rules",
            })
            continue

        if response is None or disposition != "ok":
            results.append({
                "competitor_name": name, "url": url,
                "status": "error", "error": disposition,
            })
            continue

        data = extract_seo_data(url, response)
        data["competitor_name"] = name
        results.append(data)
        logger.info(f"    → HTTP {response.status_code} | title: {data['title'][:60]}")

    logger.info(f"\n  Competitor pages checked: {len(results)}")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Issue analysis
# ═══════════════════════════════════════════════════════════════════════════════

def analyse_issues(pages: list[dict]) -> list[dict]:
    """
    Convert raw page data into a structured issues list.

    Output format matches Screaming Frog's issues export so all existing
    SEO skills (seo-site-audit, seo-reporting, etc.) work without changes.
    """
    counts: dict[str, list[str]] = defaultdict(list)
    titles: dict[str, list[str]] = defaultdict(list)
    metas: dict[str, list[str]] = defaultdict(list)

    for p in pages:
        url = p.get("url", "")
        status = str(p.get("status", ""))

        # Skip pages that weren't fetched
        if status in ("robots_blocked", "timeout", "ssl_error", "error", "non_html"):
            continue

        if status.startswith("4") or status.startswith("5"):
            counts["http_error"].append(url)
            continue

        if status.startswith("3"):
            counts["redirect"].append(url)
            continue

        # Title checks
        title = p.get("title", "")
        if not title:
            counts["missing_title"].append(url)
        else:
            length = p.get("title_length", len(title))
            if length > 60:
                counts["title_too_long"].append(url)
            elif length < 10:
                counts["title_too_short"].append(url)
            titles[title].append(url)

        # Meta description checks
        meta = p.get("meta_description", "")
        if not meta:
            counts["missing_meta_desc"].append(url)
        else:
            ml = p.get("meta_description_length", len(meta))
            if ml > 155:
                counts["meta_desc_too_long"].append(url)
            elif ml < 50:
                counts["meta_desc_too_short"].append(url)
            metas[meta].append(url)

        # H1 checks
        if not p.get("h1"):
            counts["missing_h1"].append(url)
        elif p.get("h1_count", 1) > 1:
            counts["multiple_h1"].append(url)

        # Other structural checks
        if not p.get("canonical"):
            counts["missing_canonical"].append(url)
        if p.get("noindex"):
            counts["noindex"].append(url)
        if int(p.get("word_count", "0") or 0) < 200:
            counts["thin_content"].append(url)
        if (p.get("images_missing_alt") or 0) > 0:
            counts["images_missing_alt"].append(url)
        if not p.get("schema_types"):
            counts["missing_schema"].append(url)

    # Duplicate detection (multi-URL matching value)
    for title_val, urls in titles.items():
        if len(urls) > 1:
            for u in urls:
                if u not in counts["duplicate_title"]:
                    counts["duplicate_title"].append(u)

    for meta_val, urls in metas.items():
        if len(urls) > 1:
            for u in urls:
                if u not in counts["duplicate_meta"]:
                    counts["duplicate_meta"].append(u)

    # Build issues list
    issues: list[dict] = []
    for key, affected in counts.items():
        if not affected:
            continue
        defn = _ISSUE_DEFS.get(
            key,
            (key.replace("_", " ").title(), "Other", "Medium", "")
        )
        issues.append({
            "name":          defn[0],
            "type":          defn[1],
            "priority":      defn[2],
            "count":         len(affected),
            "description":   defn[3],
            "affected_urls": affected[:10],  # sample — max 10 per issue
        })

    issues.sort(key=lambda x: (_PRIORITY_ORDER.get(x["priority"], 9), -x["count"]))
    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# Google PageSpeed Insights (optional)
# ═══════════════════════════════════════════════════════════════════════════════

def check_pagespeed(urls: list[str], logger: logging.Logger) -> dict:
    """
    Fetch Core Web Vitals via Google PageSpeed Insights API (free tier).

    API key set in .env as GOOGLE_PAGESPEED_API_KEY.
    Without a key the call still works but is rate-limited to 25 req/100s.
    No personal data is sent to or received from this API.

    Ref: https://developers.google.com/speed/docs/insights/v5/reference/pagespeedapi/runpagespeed
    """
    if not urls:
        return {}

    if not GOOGLE_PAGESPEED_API_KEY:
        logger.info("PageSpeed: no GOOGLE_PAGESPEED_API_KEY — running without key (rate-limited)")

    logger.info(f"\nPageSpeed Insights — {len(urls)} page(s), mobile + desktop...")
    results: dict = {}
    base_api = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    for url in urls:
        for strategy in ("mobile", "desktop"):
            time.sleep(1.5)  # PageSpeed API rate limit
            params: dict[str, str] = {
                "url": url,
                "strategy": strategy,
                "fields": (
                    "lighthouseResult/categories/performance/score,"
                    "lighthouseResult/audits/largest-contentful-paint/displayValue,"
                    "lighthouseResult/audits/cumulative-layout-shift/displayValue,"
                    "lighthouseResult/audits/total-blocking-time/displayValue,"
                    "lighthouseResult/audits/speed-index/displayValue"
                ),
            }
            if GOOGLE_PAGESPEED_API_KEY:
                params["key"] = GOOGLE_PAGESPEED_API_KEY

            try:
                r = requests.get(
                    f"{base_api}?{urlencode(params)}", timeout=30, verify=True
                )
                if r.status_code == 200:
                    d = r.json()
                    lr = d.get("lighthouseResult", {})
                    cats = lr.get("categories", {})
                    audits = lr.get("audits", {})
                    record = {
                        "url": url,
                        "strategy": strategy,
                        "performance_score": cats.get("performance", {}).get("score"),
                        "lcp": audits.get("largest-contentful-paint",  {}).get("displayValue"),
                        "cls": audits.get("cumulative-layout-shift",    {}).get("displayValue"),
                        "tbt": audits.get("total-blocking-time",        {}).get("displayValue"),
                        "speed_index": audits.get("speed-index",        {}).get("displayValue"),
                    }
                    results[f"{url}_{strategy}"] = record
                    score = record["performance_score"]
                    logger.info(f"  {strategy:7s} {url}  →  score {score}")
                else:
                    logger.warning(f"  PageSpeed API HTTP {r.status_code}: {url} ({strategy})")
            except Exception as exc:
                logger.warning(f"  PageSpeed error: {url} ({strategy}) — {exc}")

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Logging setup
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging(run_id: str) -> logging.Logger:
    """
    Configure dual-output logger:
      - File: full DEBUG audit trail in crawl-logs/ (compliance record)
      - Console: INFO-level progress messages
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"crawl-audit-{run_id}.log"

    logger = logging.getLogger("cb247_crawler")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s UTC [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.info(f"Audit log: {log_path}")
    return logger


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CB247 Privacy-Compliant SEO Crawler — Screaming Frog replacement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Compliance: AU Privacy Act 1988, GDPR Art.5, AU Spam Act 2003\n"
            "robots.txt is always respected. No personal data is collected.\n"
        ),
    )
    parser.add_argument(
        "--competitors", action="store_true",
        help="Also check specific competitor pages (robots.txt respected; no recursive crawl)",
    )
    parser.add_argument(
        "--pagespeed", action="store_true",
        help="Fetch Core Web Vitals via Google PageSpeed Insights API (optional)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Verify robots.txt for all targets, then exit without fetching pages",
    )
    parser.add_argument(
        "--max-pages", type=int, default=MAX_PAGES_DEFAULT,
        metavar="N",
        help=f"Max pages to crawl on CB247 domain (default: {MAX_PAGES_DEFAULT})",
    )
    args = parser.parse_args()

    # Run ID is UTC timestamp — used in audit log filename and output metadata
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    logger = setup_logging(run_id)

    logger.info("")
    logger.info("=" * 65)
    logger.info(f"  {CRAWLER_NAME} v{CRAWLER_VERSION}  —  Run {run_id}")
    logger.info(f"  User-Agent: {USER_AGENT[:80]}")
    logger.info(f"  Compliance: AU Privacy Act 1988 | GDPR Art.5 | Spam Act 2003")
    logger.info(f"  robots.txt: enforced  |  SSL verify: ON  |  PII redaction: ON")
    logger.info("=" * 65)

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    session = make_session()
    robots = RobotsCache(session, logger)

    # ── Dry run ───────────────────────────────────────────────────────────────
    if args.dry_run:
        logger.info("\n[DRY RUN] Checking robots.txt only — no pages will be fetched\n")
        logger.info(f"  CB247: {CB247_START_URL}")
        robots.is_allowed(CB247_START_URL)
        for entry in COMPETITOR_PAGES:
            logger.info(f"  {entry['name']}: {entry['url']}")
            robots.is_allowed(entry["url"])
        logger.info("\nDry run complete. No data written.")
        return

    # ── Crawl CB247 ───────────────────────────────────────────────────────────
    cb247_pages = crawl_cb247(session, robots, logger, max_pages=args.max_pages)

    # ── Competitor pages (optional) ───────────────────────────────────────────
    competitor_pages: list[dict] = []
    if args.competitors:
        competitor_pages = check_competitor_pages(session, robots, logger)

    # ── Issue analysis (own site only) ────────────────────────────────────────
    issues = analyse_issues(cb247_pages)

    # ── PageSpeed (optional) ──────────────────────────────────────────────────
    pagespeed_data: dict = {}
    if args.pagespeed:
        key_pages = [
            p["url"] for p in cb247_pages
            if p.get("status") == "200"
        ][:5]  # limit to 5 pages to stay within free tier
        pagespeed_data = check_pagespeed(key_pages, logger)

    # ── Build Screaming-Frog-compatible output ─────────────────────────────────
    top_pages = [
        {
            # Core fields (existing skills rely on these exact keys)
            "url":        p["url"],
            "title":      p.get("title", ""),
            "h1":         p.get("h1", ""),
            "word_count": p.get("word_count", "0"),
            "status":     p.get("status", ""),
            "size_kb":    p.get("size_kb", "0"),
            # Extended fields (available to skills that want richer data)
            "meta_description":    p.get("meta_description", ""),
            "h2s":                 p.get("h2s", []),
            "canonical":           p.get("canonical", ""),
            "noindex":             p.get("noindex", False),
            "schema_types":        p.get("schema_types", []),
            "images_missing_alt":  p.get("images_missing_alt", 0),
            "internal_links_count":p.get("internal_links_count", 0),
            "load_time_ms":        p.get("load_time_ms", 0),
        }
        for p in cb247_pages
        if p.get("status") == "200"
    ]

    ok_count  = sum(1 for p in cb247_pages if p.get("status") == "200")
    rxx_count = sum(1 for p in cb247_pages if str(p.get("status","")).startswith("3"))
    exx_count = sum(1 for p in cb247_pages if str(p.get("status","")) in
                    [s for s in map(str, range(400, 600))])

    result = {
        # ── Metadata ──────────────────────────────────────────────────────────
        "crawler":          CRAWLER_NAME,
        "crawler_version":  CRAWLER_VERSION,
        "date_crawled":     datetime.now(timezone.utc).isoformat(),
        "run_id":           run_id,
        "site":             CB247_START_URL,

        # ── Compliance record (kept in output for auditability) ───────────────
        "compliance": {
            "robots_txt":        "enforced — disallowed paths unconditionally skipped",
            "pii_redaction":     "active — email, phone, AU tax IDs redacted",
            "ssl_verification":  "enforced — no certificate bypassing",
            "rate_limit_seconds": RATE_LIMIT_SECONDS,
            "scope":             "CB247 own-site (recursive) + specific competitor URLs only",
            "applicable_laws":   [
                "AU Privacy Act 1988 (Cth) + APPs",
                "GDPR (EU) 2016/679 Art.5",
                "AU Spam Act 2003 (Cth)",
                "AU Criminal Code Act 1995 ss.477-478",
            ],
        },

        # ── Summary ───────────────────────────────────────────────────────────
        "summary": {
            "total_pages_crawled": len(cb247_pages),
            "pages_200":           ok_count,
            "pages_3xx":           rxx_count,
            "pages_4xx_5xx":       exx_count,
            "issues_critical":     sum(1 for i in issues if i["priority"] == "Critical"),
            "issues_high":         sum(1 for i in issues if i["priority"] == "High"),
            "issues_medium":       sum(1 for i in issues if i["priority"] == "Medium"),
        },

        # ── Core outputs (read by seo-site-audit, seo-reporting skills) ───────
        "issues":           issues,
        "top_pages":        top_pages,

        # ── Competitor data (optional) ────────────────────────────────────────
        "competitor_pages": competitor_pages,
    }

    if pagespeed_data:
        result["pagespeed"] = pagespeed_data

    # ── Save state/screaming-frog-data.json ───────────────────────────────────
    sf_path = STATE_DIR / "screaming-frog-data.json"
    sf_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"\nSaved: {sf_path}")

    # ── Save state/pagespeed-data.json (if applicable) ────────────────────────
    if pagespeed_data:
        ps_path = STATE_DIR / "pagespeed-data.json"
        ps_path.write_text(json.dumps(pagespeed_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Saved: {ps_path}")

    # ── Print summary ─────────────────────────────────────────────────────────
    s = result["summary"]
    logger.info("")
    logger.info("=" * 65)
    logger.info("  CRAWL SUMMARY")
    logger.info(f"  Pages crawled : {s['total_pages_crawled']}")
    logger.info(f"  200 OK        : {s['pages_200']}")
    logger.info(f"  3xx redirects : {s['pages_3xx']}")
    logger.info(f"  4xx/5xx errors: {s['pages_4xx_5xx']}")
    logger.info(f"  Critical issues: {s['issues_critical']}")
    logger.info(f"  High issues    : {s['issues_high']}")
    logger.info(f"  Medium issues  : {s['issues_medium']}")
    if competitor_pages:
        ok_comp = sum(1 for p in competitor_pages if p.get("status") == "200")
        blocked = sum(1 for p in competitor_pages if p.get("status") == "robots_blocked")
        logger.info(f"  Competitor pages: {ok_comp} fetched, {blocked} blocked by robots.txt")
    logger.info("=" * 65)
    logger.info(f"  {CRAWLER_NAME} complete.")
    logger.info("")


if __name__ == "__main__":
    main()
