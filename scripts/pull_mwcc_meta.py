"""
pull_mwcc_meta.py — Pull Meta Ads data for My World Childcare via Graph API.
Account: MWCC_META_AD_ACCOUNT_ID (act_2835637326727066)
Token:   META_ACCESS_TOKEN (same long-lived token as CB247)

Saves to state/mwcc-meta.json:
  - Account-level weekly summary (spend, impressions, clicks, CTR, CPC, CPM)
  - Campaign breakdown (MW Traffic, MWCC Engagement, etc.)
  - Ad set breakdown by centre (Armadale, Midvale, Rockingham, Seville Grove, Waikiki)
  - Top 10 ads by CTR (for creative performance section)
  - Audience location breakdown (monitors Perth% vs non-target international %)

Centre mapping — ad set names contain centre keywords:
  armadale / midvale / rockingham / seville grove / sg / waikiki
  Unmapped ad sets labelled "Other" (not hidden).

Date range: last completed Sat–Fri week (matches GA4 + Google Ads).
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR    = Path(__file__).resolve().parent.parent
STATE_DIR   = BASE_DIR / "state"
OUTPUT_FILE = STATE_DIR / "mwcc-meta.json"
load_dotenv(BASE_DIR / ".env")

ACCESS_TOKEN  = os.getenv("META_ACCESS_TOKEN", "").strip()
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")
GRAPH_BASE    = f"https://graph.facebook.com/{GRAPH_VERSION}"

# MWCC ad account — hardcoded with env-var override for safety
_env_acct = os.getenv("MWCC_META_AD_ACCOUNT_ID", "").strip()
MWCC_ACCOUNT = _env_acct if _env_acct else "act_2835637326727066"
if not MWCC_ACCOUNT.startswith("act_"):
    MWCC_ACCOUNT = f"act_{MWCC_ACCOUNT}"

# MWCC centre names — used to map ad set names → centre
CENTRES = ["Armadale", "Midvale", "Rockingham", "Seville Grove", "Waikiki"]

HISTORY_CAP = 8  # weeks of rolling history to keep


# ─────────────────────────────────────────────
# Graph API helper
# ─────────────────────────────────────────────
def _graph(path, params):
    params = dict(params or {})
    params["access_token"] = ACCESS_TOKEN
    url = f"{GRAPH_BASE}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=45) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try:
            msg = json.loads(body).get("error", {}).get("message", body[:300])
        except Exception:
            msg = body[:300]
        return {"_error": msg}
    except Exception as e:
        return {"_error": str(e)}


def _token_ok():
    """Validate token and print expiry warning if within 14 days."""
    if not ACCESS_TOKEN or len(ACCESS_TOKEN) < 20:
        print("[MWCC Meta] META_ACCESS_TOKEN not set in .env — skipping.")
        return False
    me = _graph("me", {"fields": "id,name"})
    if me.get("_error"):
        print(f"[MWCC Meta] Token invalid/expired: {me['_error']}")
        print("  → Refresh at: https://developers.facebook.com/tools/explorer/")
        return False
    print(f"[MWCC Meta] Authenticated as: {me.get('name', me.get('id'))}")

    # Expiry check
    res = _graph("debug_token", {"input_token": ACCESS_TOKEN})
    expires_at = res.get("data", {}).get("expires_at", 0)
    if expires_at:
        try:
            expiry    = datetime.fromtimestamp(int(expires_at), tz=timezone.utc)
            days_left = (expiry - datetime.now(tz=timezone.utc)).days
            expiry_str = expiry.strftime("%Y-%m-%d")
            if days_left <= 0:
                print(f"[MWCC Meta] ❌ TOKEN EXPIRED on {expiry_str}")
            elif days_left <= 14:
                print(f"[MWCC Meta] ⚠️  Token expires in {days_left} days ({expiry_str}) — renew soon!")
            else:
                print(f"[MWCC Meta] Token valid until {expiry_str} ({days_left} days)")
        except Exception:
            pass
    return True


# ─────────────────────────────────────────────
# Centre mapping from ad set / campaign name
# ─────────────────────────────────────────────
def _centre_from_name(name: str) -> str:
    """Map ad set or campaign name to a centre name."""
    low = (name or "").lower()
    if "armadale" in low:
        return "Armadale"
    if "midvale" in low:
        return "Midvale"
    if "rockingham" in low:
        return "Rockingham"
    if "seville grove" in low or " sg " in low or low.endswith(" sg") or low.startswith("sg "):
        return "Seville Grove"
    if "waikiki" in low:
        return "Waikiki"
    return "Other"


# ─────────────────────────────────────────────
# Metrics helpers
# ─────────────────────────────────────────────
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _safe_metrics(spend, impr, clicks, reach, lpv=None):
    m = {
        "spend":  round(spend, 2),
        "impr":   int(impr),
        "clicks": int(clicks),
        "reach":  int(reach),
        "ctr":    round(clicks / impr * 100, 2) if impr else 0,
        "cpm":    round(spend / impr * 1000, 2) if impr else 0,
        "cpc":    round(spend / clicks, 2) if clicks else 0,
    }
    if lpv is not None:
        m["lpv"]          = int(lpv)
        m["cost_per_lpv"] = round(spend / lpv, 2) if lpv else 0
    return m


def _get_actions_value(actions_list, action_type):
    """Extract a specific action type value from the actions array."""
    for a in (actions_list or []):
        if a.get("action_type") == action_type:
            return _num(a.get("value", 0))
    return 0.0


# ─────────────────────────────────────────────
# Date range (Sat–Fri, matches GA4 + Google Ads)
# ─────────────────────────────────────────────
def _sat_fri_range():
    today = date.today()
    days_since_friday = (today.weekday() - 4) % 7
    end   = today - timedelta(days=days_since_friday)   # last Friday
    start = end - timedelta(days=6)                     # preceding Saturday
    return start.isoformat(), end.isoformat()


def _week_label(since, until):
    try:
        s = datetime.strptime(since, "%Y-%m-%d")
        e = datetime.strptime(until, "%Y-%m-%d")
        return f"{s.strftime('%d%b%y')}-{e.strftime('%d%b%y')}"
    except Exception:
        return f"{since}_{until}"


# ─────────────────────────────────────────────
# Insights fetchers
# ─────────────────────────────────────────────
def _insights(node_id, level, fields, since, until, breakdowns=None):
    params = {
        "level":      level,
        "time_range": json.dumps({"since": since, "until": until}),
        "fields":     fields,
        "limit":      500,
    }
    if breakdowns:
        params["breakdowns"] = breakdowns
    res = _graph(f"{node_id}/insights", params)
    if res.get("_error"):
        print(f"[MWCC Meta]   insights error [{node_id} {level}]: {res['_error']}", file=sys.stderr)
        return []
    return res.get("data", []) or []


# ─────────────────────────────────────────────
# Main pull
# ─────────────────────────────────────────────
def pull_mwcc_meta():
    print("[MWCC Meta] Pulling Meta Ads data...")
    if not _token_ok():
        _write_empty("Token missing or invalid")
        return None

    since, until = _sat_fri_range()
    print(f"[MWCC Meta] Period: {since} to {until}")
    print(f"[MWCC Meta] Account: {MWCC_ACCOUNT}")

    # ── 1. Account-level summary ──────────────────────────────────────────
    acct_fields = "spend,impressions,reach,clicks,inline_link_clicks,actions,ctr,cpm,cpp"
    acct_rows   = _insights(MWCC_ACCOUNT, "account", acct_fields, since, until)
    if not acct_rows:
        print("[MWCC Meta] No account data returned — check account ID and token permissions.")
        _write_empty("No account data returned from Meta API")
        return None

    a = acct_rows[0]
    acct_spend  = _num(a.get("spend"))
    acct_impr   = _num(a.get("impressions"))
    acct_reach  = _num(a.get("reach"))
    acct_clicks = _num(a.get("inline_link_clicks") or a.get("clicks"))
    acct_lpv    = _get_actions_value(a.get("actions"), "landing_page_view")
    acct_results = _get_actions_value(a.get("actions"), "link_click") or acct_clicks
    summary = _safe_metrics(acct_spend, acct_impr, acct_clicks, acct_reach, lpv=acct_lpv)
    summary["results"]          = int(acct_results)
    summary["cost_per_result"]  = round(acct_spend / acct_results, 2) if acct_results else 0

    # ── 2. Campaign-level breakdown ───────────────────────────────────────
    camp_fields = "campaign_name,spend,impressions,reach,clicks,inline_link_clicks,actions"
    camp_rows   = _insights(MWCC_ACCOUNT, "campaign", camp_fields, since, until)
    campaigns   = []
    for c in camp_rows:
        sp  = _num(c.get("spend"))
        im  = _num(c.get("impressions"))
        cl  = _num(c.get("inline_link_clicks") or c.get("clicks"))
        re  = _num(c.get("reach"))
        lpv = _get_actions_value(c.get("actions"), "landing_page_view")
        campaigns.append({
            "name":           c.get("campaign_name", ""),
            **_safe_metrics(sp, im, cl, re, lpv=lpv),
        })
    campaigns.sort(key=lambda x: x["spend"], reverse=True)

    # ── 3. Ad set-level breakdown (centre attribution) ────────────────────
    adset_fields = "adset_name,campaign_name,spend,impressions,reach,clicks,inline_link_clicks,actions,frequency"
    adset_rows   = _insights(MWCC_ACCOUNT, "adset", adset_fields, since, until)
    ad_sets      = []
    centre_totals = {c: {"spend": 0, "impr": 0, "clicks": 0, "reach": 0, "lpv": 0} for c in CENTRES + ["Other"]}

    for s in adset_rows:
        sp   = _num(s.get("spend"))
        im   = _num(s.get("impressions"))
        cl   = _num(s.get("inline_link_clicks") or s.get("clicks"))
        re   = _num(s.get("reach"))
        lpv  = _get_actions_value(s.get("actions"), "landing_page_view")
        freq = _num(s.get("frequency"))
        centre = _centre_from_name(s.get("adset_name", ""))

        ad_sets.append({
            "adset_name":    s.get("adset_name", ""),
            "campaign_name": s.get("campaign_name", ""),
            "centre":        centre,
            "frequency":     round(freq, 2),
            **_safe_metrics(sp, im, cl, re, lpv=lpv),
        })

        if centre in centre_totals:
            centre_totals[centre]["spend"]  += sp
            centre_totals[centre]["impr"]   += im
            centre_totals[centre]["clicks"] += cl
            centre_totals[centre]["reach"]  += re
            centre_totals[centre]["lpv"]    += lpv

    ad_sets.sort(key=lambda x: x["spend"], reverse=True)

    # Build per-centre summary
    by_centre = {}
    for centre, t in centre_totals.items():
        if t["spend"] > 0 or t["impr"] > 0:
            by_centre[centre] = _safe_metrics(
                t["spend"], t["impr"], t["clicks"], t["reach"], lpv=t["lpv"]
            )

    # ── 4. Top ads by CTR ─────────────────────────────────────────────────
    ad_fields = "ad_name,adset_name,spend,impressions,reach,clicks,inline_link_clicks,actions"
    ad_rows   = _insights(MWCC_ACCOUNT, "ad", ad_fields, since, until)
    top_ads   = []
    for ad in ad_rows:
        sp  = _num(ad.get("spend"))
        im  = _num(ad.get("impressions"))
        cl  = _num(ad.get("inline_link_clicks") or ad.get("clicks"))
        re  = _num(ad.get("reach"))
        lpv = _get_actions_value(ad.get("actions"), "landing_page_view")
        if im == 0:
            continue
        top_ads.append({
            "name":    ad.get("ad_name", ""),
            "centre":  _centre_from_name(ad.get("adset_name", "")),
            "spend":   round(sp, 2),
            "impr":    int(im),
            "reach":   int(re),
            "clicks":  int(cl),
            "ctr":     round(cl / im * 100, 2),
            "cpc":     round(sp / cl, 2) if cl else 0,
            "lpv":     int(lpv),
        })
    # Sort by CTR (minimum $1 spend to avoid noise from micro-tests)
    top_ads = [ad for ad in top_ads if ad["spend"] >= 1.0]
    top_ads.sort(key=lambda x: x["ctr"], reverse=True)
    top_ads = top_ads[:10]

    # ── 5. Audience location breakdown (region, monitors Perth% vs non-target) ──
    location_rows = _insights(
        MWCC_ACCOUNT, "ad", "spend,impressions,reach",
        since, until, breakdowns="region"
    )
    locations = []
    total_reach_for_loc = sum(_num(r.get("reach")) for r in location_rows)
    for row in location_rows:
        re = _num(row.get("reach"))
        if total_reach_for_loc > 0 and re > 0:
            locations.append({
                "region": row.get("region", "Unknown"),
                "reach":  int(re),
                "share":  round(re / total_reach_for_loc * 100, 2),
            })
    locations.sort(key=lambda x: x["reach"], reverse=True)
    locations = locations[:15]

    # ── Assemble output ───────────────────────────────────────────────────
    output = {
        "generated_at":  datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":         "mwcc",
        "date_range":    {"start": since, "end": until},
        "account_id":    MWCC_ACCOUNT,
        "summary":       summary,
        "campaigns":     campaigns,
        "ad_sets":       ad_sets,
        "by_centre":     by_centre,
        "top_ads":       top_ads,
        "locations":     locations,
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))

    # Update rolling history
    _update_history(output, since, until)

    print(f"[MWCC Meta] Saved → {OUTPUT_FILE}")
    print(f"[MWCC Meta] Spend      : ${acct_spend:,.2f}  |  Impressions: {int(acct_impr):,}")
    print(f"[MWCC Meta] Clicks     : {int(acct_clicks):,}  |  CTR: {summary['ctr']:.2f}%  |  CPC: ${summary['cpc']:.2f}")
    print(f"[MWCC Meta] CPM        : ${summary['cpm']:.2f}  |  LPVs: {int(acct_lpv):,}")
    print(f"[MWCC Meta] Campaigns  : {len(campaigns)}  |  Ad Sets: {len(ad_sets)}  |  Top Ads: {len(top_ads)}")
    print(f"[MWCC Meta] By centre  :")
    for centre, m in sorted(by_centre.items(), key=lambda x: x[1]["spend"], reverse=True):
        print(f"[MWCC Meta]   {centre:<15} ${m['spend']:>8,.2f}  CTR {m['ctr']:.2f}%  CPC ${m['cpc']:.2f}")
    return output


def _update_history(output, since, until):
    """Append current week to mwcc-meta-history.json (keeps last 8 weeks)."""
    HIST_FILE = STATE_DIR / "mwcc-meta-history.json"
    week_label = _week_label(since, until)
    entry = {
        "week_label": week_label,
        "date_start": since,
        "date_end":   until,
        "summary":    output["summary"],
        "by_centre":  output["by_centre"],
    }
    history = []
    if HIST_FILE.exists():
        try:
            history = json.loads(HIST_FILE.read_text())
        except Exception:
            history = []
    history = [w for w in history if w.get("week_label") != week_label]
    history = [entry] + history[:HISTORY_CAP - 1]
    HIST_FILE.write_text(json.dumps(history, indent=2))
    print(f"[MWCC Meta] History updated → {HIST_FILE.name} ({len(history)} weeks)")


def _write_empty(reason):
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "brand":        "mwcc",
        "available":    False,
        "skip_reason":  reason,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    pull_mwcc_meta()
