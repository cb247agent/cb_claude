"""
pull_meta.py — Pull Meta (Facebook/Instagram) Ads data via the Graph API and
merge it into state/ads-data.json under the "meta_ads" key.

This is the LIVE-API equivalent of the CSV parser in pull_local_ads.py. It writes
the SAME structure the weekly report + dashboard already consume:

  ads-data.json
    └─ "meta_ads": [                       # newest week first
         {
           "week_label": "12 May – 18 May 2026",
           "start": "2026-05-12", "end": "2026-05-18",
           "combined":   {spend,impr,clicks,reach,ctr,cpm,cpc},
           "malaga":     {spend,impr,clicks,reach,ctr,cpm,cpc},
           "ellenbrook": {spend,impr,clicks,reach,ctr,cpm,cpc},
           "ads": [ {name,spend,impr,clicks,reach,ctr,cpc} ]
         }, ...
       ]

Auth:  META_ACCESS_TOKEN in .env  (MUST be a valid long-lived token)
Config (optional):  metaads/meta-accounts.json mapping ad-account → location:
  { "act_1234567890": "Malaga", "act_9876543210": "Ellenbrook" }
If no mapping, accounts are discovered via /me/adaccounts and each campaign is
assigned a location by name ("malaga"/"ellenbrook" substring).

Graceful: if the token is missing/expired it prints a clear message, leaves any
existing CSV-sourced meta_ads untouched, and returns None.
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

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
META_DIR = BASE_DIR / "metaads"
ADS_DATA_FILE = STATE_DIR / "ads-data.json"
load_dotenv(BASE_DIR / ".env")

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
WEEKS = int(os.getenv("META_WEEKS", "4"))
HISTORY_CAP = 12
ACCOUNTS_CONFIG = META_DIR / "meta-accounts.json"


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


def _check_token_expiry():
    """
    Calls /debug_token to get the token's expiry date.
    Prints a warning if the token expires within 14 days.
    Silent if the debug call fails (non-critical — pull continues).
    """
    res = _graph("debug_token", {"input_token": ACCESS_TOKEN})
    data = res.get("data", {})
    expires_at = data.get("expires_at", 0)
    if not expires_at:
        return  # token is non-expiring or debug call failed — skip
    try:
        expiry = datetime.fromtimestamp(int(expires_at), tz=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        days_left = (expiry - now).days
        expiry_str = expiry.strftime("%Y-%m-%d")
        if days_left <= 0:
            print(f"  ❌ META TOKEN EXPIRED on {expiry_str} — pull will likely fail.")
            print("  → Renew at: https://developers.facebook.com/tools/explorer/")
            print("    Then extend: https://developers.facebook.com/tools/debug/accesstoken/")
        elif days_left <= 14:
            print(f"  ⚠️  META TOKEN EXPIRES IN {days_left} DAYS ({expiry_str}) — renew soon!")
            print("  → Renew at: https://developers.facebook.com/tools/explorer/")
            print("    Then extend: https://developers.facebook.com/tools/debug/accesstoken/")
            print("    Update META_ACCESS_TOKEN in .env after renewing.")
        else:
            print(f"  ✅ Token valid until {expiry_str} ({days_left} days remaining)")
    except Exception:
        pass  # non-critical — don't block the pull


def _token_ok():
    if not ACCESS_TOKEN or len(ACCESS_TOKEN) < 20:
        print("  META_ACCESS_TOKEN not set (or empty) — skipping Meta API pull.")
        print("  → Step 1: Get a short-lived token (Graph API Explorer):")
        print("            https://developers.facebook.com/tools/explorer/")
        print("            Permissions needed: ads_read, ads_management, business_management")
        print("  → Step 2: Exchange for a long-lived token (60-day) via:")
        print("            https://developers.facebook.com/tools/debug/accesstoken/")
        print("  → Step 3: Paste the long-lived token into .env as META_ACCESS_TOKEN=...")
        return False
    me = _graph("me", {"fields": "id,name"})
    if me.get("_error"):
        print("  ❌ Meta token invalid or expired — skipping Meta API pull.")
        print(f"     {me['_error']}")
        print("  → Refresh at: https://developers.facebook.com/tools/explorer/")
        print("    Permissions needed: ads_read, ads_management, business_management")
        print("    Then convert to long-lived: https://developers.facebook.com/tools/debug/accesstoken/")
        return False
    print(f"  ✅ Authenticated as: {me.get('name', me.get('id'))}")
    _check_token_expiry()  # warn if expiry is within 14 days
    return True


# ─────────────────────────────────────────────
# Account discovery + location mapping
# ─────────────────────────────────────────────
def _load_account_map():
    if ACCOUNTS_CONFIG.exists():
        try:
            return json.loads(ACCOUNTS_CONFIG.read_text())
        except Exception:
            pass
    return {}


def _discover_accounts():
    cfg = _load_account_map()
    res = _graph("me/adaccounts", {"fields": "account_id,name,account_status", "limit": 100})
    accounts = []
    for a in res.get("data", []) or []:
        acct_id = f"act_{a.get('account_id')}"
        name = a.get("name", "")
        loc = cfg.get(acct_id) or cfg.get(str(a.get("account_id")))

        # If a config file exists, skip any account not explicitly listed in it.
        # This filters out the authenticating user's personal ad accounts.
        if cfg and not loc:
            continue

        if not loc:
            low = name.lower()
            if "malaga" in low:
                loc = "Malaga"
            elif "ellenbrook" in low:
                loc = "Ellenbrook"
        accounts.append({"id": acct_id, "name": name, "location": loc})
    return accounts


# ─────────────────────────────────────────────
# Week ranges (Mon–Sun, matching CSV reporting weeks)
# ─────────────────────────────────────────────
def _week_ranges(n):
    today = date.today()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    ranges = []
    for i in range(n):
        end = last_sunday - timedelta(days=7 * i)
        start = end - timedelta(days=6)
        ranges.append((start, end))
    return ranges


def _week_label(start, end):
    return f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _location_for_campaign(camp_name, account_loc):
    if account_loc:
        return account_loc
    low = (camp_name or "").lower()
    if "malaga" in low:
        return "Malaga"
    if "ellenbrook" in low:
        return "Ellenbrook"
    return "Other"


def _metrics(spend, impr, clicks, reach):
    return {
        "spend": round(spend, 2),
        "impr": int(impr),
        "clicks": int(clicks),
        "reach": int(reach),
        "ctr": round(clicks / impr * 100, 2) if impr else 0,
        "cpm": round(spend / impr * 1000, 2) if impr else 0,
        "cpc": round(spend / clicks, 2) if clicks else 0,
    }


# ─────────────────────────────────────────────
# Insights
# ─────────────────────────────────────────────
def _insights(acct_id, level, fields, since, until):
    res = _graph(f"{acct_id}/insights", {
        "level": level,
        "time_range": json.dumps({"since": since, "until": until}),
        "fields": fields,
        "limit": 500,
    })
    if res.get("_error"):
        print(f"     insights error [{acct_id} {level}]: {res['_error']}", file=sys.stderr)
        return []
    return res.get("data", []) or []


def _build_week(accounts, start, end, include_ads=False):
    since, until = start.isoformat(), end.isoformat()
    acc = {"Malaga": [0.0, 0, 0, 0], "Ellenbrook": [0.0, 0, 0, 0], "_all": [0.0, 0, 0, 0]}
    ads = []

    for a in accounts:
        for c in _insights(a["id"], "campaign",
                           "campaign_name,spend,impressions,reach,clicks,inline_link_clicks",
                           since, until):
            spend = _num(c.get("spend"))
            impr = _num(c.get("impressions"))
            reach = _num(c.get("reach"))
            clicks = _num(c.get("inline_link_clicks") or c.get("clicks"))
            loc = _location_for_campaign(c.get("campaign_name"), a["location"])
            for bucket in (loc, "_all"):
                if bucket in acc:
                    acc[bucket][0] += spend
                    acc[bucket][1] += impr
                    acc[bucket][2] += clicks
                    acc[bucket][3] += reach

        if include_ads:
            for ad in _insights(a["id"], "ad",
                                "ad_name,spend,impressions,reach,clicks,inline_link_clicks",
                                since, until):
                sp = _num(ad.get("spend"))
                im = _num(ad.get("impressions"))
                cl = _num(ad.get("inline_link_clicks") or ad.get("clicks"))
                re = _num(ad.get("reach"))
                ads.append({
                    "name": ad.get("ad_name", ""),
                    "spend": round(sp, 2), "impr": int(im), "clicks": int(cl), "reach": int(re),
                    "ctr": round(cl / im * 100, 2) if im else 0,
                    "cpc": round(sp / cl, 2) if cl else 0,
                })

    ads.sort(key=lambda x: x["spend"], reverse=True)
    return {
        "week_label": _week_label(start, end),
        "start": since, "end": until,
        "combined":   _metrics(*acc["_all"]),
        "malaga":     _metrics(*acc["Malaga"]),
        "ellenbrook": _metrics(*acc["Ellenbrook"]),
        "ads": ads[:10],
    }


# ─────────────────────────────────────────────
# Merge into ads-data.json (preserve google_ads)
# ─────────────────────────────────────────────
def _merge_into_ads_data(new_weeks):
    data = {}
    if ADS_DATA_FILE.exists():
        try:
            data = json.loads(ADS_DATA_FILE.read_text())
        except Exception:
            data = {}
    existing = data.get("meta_ads") or []
    by_label = {w.get("week_label"): w for w in existing}
    for w in new_weeks:
        by_label[w["week_label"]] = w  # API data overwrites same-week CSV data
    merged = list(by_label.values())

    def _key(w):
        try:
            return datetime.strptime(w.get("end", ""), "%Y-%m-%d")
        except Exception:
            return datetime.min
    merged.sort(key=_key, reverse=True)

    data["meta_ads"] = merged[:HISTORY_CAP]
    data.setdefault("generated", datetime.now(timezone.utc).isoformat())
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ADS_DATA_FILE.write_text(json.dumps(data, indent=2))
    return merged


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def pull_meta():
    print("Pulling Meta Ads data (Graph API)...")
    if not _token_ok():
        return None

    accounts = _discover_accounts()
    if not accounts:
        print("  No ad accounts found for this token — skipping.")
        return None
    print("  Ad accounts: " + ", ".join(
        f"{a['name'] or a['id']}" + (f" → {a['location']}" if a['location'] else " (campaign-mapped)")
        for a in accounts))

    weeks = []
    for idx, (start, end) in enumerate(_week_ranges(WEEKS)):
        label = _week_label(start, end)
        print(f"  → Week {label}")
        weeks.append(_build_week(accounts, start, end, include_ads=(idx == 0)))

    if not any(w["combined"]["spend"] or w["combined"]["impr"] for w in weeks):
        print("  ⚠️ Meta returned no spend/impressions — check ad-account access/date range.")

    merged = _merge_into_ads_data(weeks)
    latest = weeks[0]
    c = latest["combined"]
    print(f"\n  ✅ Latest week ({latest['week_label']}): "
          f"${c['spend']:.2f} | {c['impr']:,} impr | {c['clicks']:,} clicks")
    print(f"     Malaga ${latest['malaga']['spend']:.2f} | Ellenbrook ${latest['ellenbrook']['spend']:.2f}")
    print(f"  Merged into {ADS_DATA_FILE.name} ({len(merged)} weeks of meta_ads)")
    return {"latest": latest, "weeks": merged}


def main():
    return pull_meta()


if __name__ == "__main__":
    main()
