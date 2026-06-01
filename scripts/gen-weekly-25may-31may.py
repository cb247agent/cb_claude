"""Weekly Report Generator — 25–31 May 2026"""
import csv, json, pathlib
from datetime import datetime

BASE  = pathlib.Path('/Users/tiachasingbetter/Documents/ChasingBetter/CB_Marketing')
STATE = BASE / 'state'
OUT   = BASE / 'outputs/reports'

ga4  = json.loads((STATE/'ga4-data.json').read_text())
gsc  = json.loads((STATE/'gsc-data.json').read_text())
ads  = json.loads((STATE/'ads-data.json').read_text())

def parse_meta_csv(path):
    rows = []
    p = pathlib.Path(path)
    if not p.exists():
        return rows
    with open(p, newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            def sf(k):
                v = r.get(k,'').replace(',','').strip()
                try: return float(v)
                except: return 0.0
            name = r.get('Ad name','').strip()
            if not name: continue
            rows.append({
                'ad': name[:65],
                'spend': sf('Amount spent (AUD)'),
                'impr': int(sf('Impressions')),
                'reach': int(sf('Reach')),
                'clicks': int(sf('Link clicks')),
                'results': sf('Results'),
                'cpr': sf('Cost per result'),
                'ctr': round(sf('CTR (link click-through rate)'), 2),
                'cpm': round(sf('CPM (cost per 1,000 impressions)'), 2),
                'quality':  r.get('Quality ranking',''),
                'eng_rank': r.get('Engagement rate ranking',''),
                'conv_rank':r.get('Conversion rate ranking',''),
            })
    return rows

MDIR = BASE / 'metaads'
mal25 = parse_meta_csv(MDIR/'Malaga/Meta_Malaga-25-May-2026-31-May-2026.csv')
ell25 = parse_meta_csv(MDIR/'Ellenbrook/Meta_Ellenbrook-25-May-2026-31-May-2026.csv')
mal18 = parse_meta_csv(MDIR/'Malaga/Meta_Malaga-18-May-2026-24-May-2026.csv')
ell18 = parse_meta_csv(MDIR/'Ellenbrook/Meta_Ellenbtook_18-May-2026-24-May-2026.csv')

def agg(rows):
    active = [r for r in rows if r['spend'] > 0]
    spend   = sum(r['spend']   for r in active)
    impr    = sum(r['impr']    for r in active)
    reach   = sum(r['reach']   for r in active)
    clicks  = sum(r['clicks']  for r in active)
    results = sum(r['results'] for r in active)
    cpr     = round(spend/results, 2) if results > 0 else 0
    return dict(spend=spend, impr=impr, reach=reach, clicks=clicks,
                results=results, cpr=cpr, active=active, n=len(active))

m25 = agg(mal25); e25 = agg(ell25)
m18 = agg(mal18); e18 = agg(ell18)

gads_w  = (ads.get('google_ads') or [{}])[0]
gads_label = gads_w.get('week_label', '18May26-24May26')
gm = gads_w.get('malaga', {})
ge = gads_w.get('ellenbrook', {})
gm_cpa = round(gm.get('spend',0)/gm.get('conv',1), 2) if gm.get('conv') else 0
ge_cpa = round(ge.get('spend',0)/ge.get('conv',1), 2) if ge.get('conv') else 0

# Metricool 25-31 May from PDF
ig_followers=8982; ig_balance=9; ig_views=105360; ig_views_chg=-9.64
ig_reach_day=4511; ig_reach_chg=15.56; ig_posts=1; ig_reels=5; ig_reels_chg=150.0
ig_likes=93; ig_likes_chg=45.31; ig_stories=67; ig_stories_impr=54680; ig_stories_chg=93.92
ig_story_reach=804; ig_reel_eng=1.28
fb_followers=5280; fb_impr=32710; fb_impr_chg=-41.81; fb_interactions=6; fb_int_chg=-90.0; fb_posts=1
gbp_reach=1040; gbp_reach_chg=-23.02; gbp_web=95; gbp_web_chg=-49.74
gbp_actions=446; gbp_actions_chg=-33.13; gbp_reviews=3; gbp_rating=4.33

ga4c = ga4['current']; ga4p = ga4['previous']
sessions    = int(ga4c['sessions']);   p_sessions  = int(ga4p['sessions'])
users       = int(ga4c['users']);      p_users     = int(ga4p['users'])
new_users   = int(ga4c['new_users']); p_new_users = int(ga4p['new_users'])
convs       = int(ga4c['conversions']);p_convs     = int(ga4p['conversions'])
conv_rate   = round(convs/sessions*100, 1)
p_conv_rate = round(p_convs/p_sessions*100, 1)

def src(name):
    for s in ga4.get('traffic_sources',[]):
        if s['sessionDefaultChannelGroup'] == name:
            return int(s['sessions']), int(s['conversions'])
    return 0, 0

org_s, org_c     = src('Organic Search')
paid_s, paid_c   = src('Paid Social')
direct, dir_c    = src('Direct')
cross, crs_c     = src('Cross-network')
paid_sh, psh_c   = src('Paid Search')
org_soc, ors_c   = src('Organic Social')

def pct(a, b):
    if not b: return '—'
    c = (a-b)/b*100
    return ('▲ ' if c>=0 else '▼ ') + f'{abs(c):.1f}%'

def chg(a, b, inverse=False):
    if not b: return '<span style="color:#9ca3af">—</span>'
    c = (a-b)/b*100
    good = c>=0 if not inverse else c<=0
    col = '#00c4b4' if good else '#ef4444'
    sym = '▲' if c>=0 else '▼'
    return f'<span style="color:{col};font-weight:700">{sym} {abs(c):.1f}%</span>'

meta_total_spend   = round(m25['spend'] + e25['spend'], 2)
meta_total_results = int(m25['results'] + e25['results'])
meta_blended_cpr   = round(meta_total_spend / meta_total_results, 2) if meta_total_results else 0
gads_total_spend   = round(gm.get('spend',0) + ge.get('spend',0), 2)
all_spend          = round(meta_total_spend + gads_total_spend, 0)

gen_time = datetime.now().strftime('%-d %B %Y, %-I:%M %p')

def kpi(label, val, change_html='', sub=''):
    return (
        '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:20px 24px;min-width:0">'
        f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af;margin-bottom:6px">{label}</div>'
        f'<div style="font-size:1.7rem;font-weight:800;color:#111827;line-height:1.1;margin-bottom:4px">{val}</div>'
        f'<div style="font-size:12px;margin-bottom:2px">{change_html}</div>'
        f'<div style="font-size:11px;color:#9ca3af">{sub}</div>'
        '</div>'
    )

def section(title):
    return (
        f'<div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;'
        f'color:#9ca3af;margin:36px 0 16px;padding-bottom:8px;border-bottom:2px solid #f3f4f6">{title}</div>'
    )

def obs(color, label, body):
    border = {'red':'#ef4444','teal':'#00c4b4','amber':'#f59e0b','green':'#22c55e'}.get(color,'#9ca3af')
    bg     = {'red':'#fff5f5','teal':'#f0fdfb','amber':'#fffbeb','green':'#f0fdf4'}.get(color,'#f9fafb')
    return (
        f'<div style="background:{bg};border-left:4px solid {border};border-radius:0 8px 8px 0;padding:16px 18px">'
        f'<div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:{border};margin-bottom:6px">{label}</div>'
        f'<div style="font-size:12px;line-height:1.7;color:#374151">{body}</div>'
        '</div>'
    )

def priority(num, title, body):
    return (
        '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:20px 24px;'
        'margin-bottom:12px;border-left:4px solid #3FA69A">'
        f'<h4 style="font-size:12px;font-weight:700;color:#111827;margin-bottom:8px">{num}. {title}</h4>'
        f'<p style="font-size:12px;color:#374151;line-height:1.7">{body}</p>'
        '</div>'
    )

def qual_badge(v):
    if 'Above' in v: return '<span style="font-size:9px;background:#e8f5f4;color:#00c4b4;padding:1px 5px;border-radius:3px;font-weight:700">Above</span>'
    if 'Below' in v: return '<span style="font-size:9px;background:#fee2e2;color:#ef4444;padding:1px 5px;border-radius:3px;font-weight:700">Below</span>'
    if v: return '<span style="font-size:9px;background:#f3f4f6;color:#6b7280;padding:1px 5px;border-radius:3px">Avg</span>'
    return '<span style="color:#d1d5db;font-size:9px">—</span>'

def tier_label(r):
    abv = sum(1 for x in [r['quality'],r['eng_rank'],r['conv_rank']] if 'Above' in x)
    blw = sum(1 for x in [r['quality'],r['eng_rank'],r['conv_rank']] if 'Below' in x)
    if abv >= 2: return '⭐ Star'
    if blw > 0:  return '⚠ Poor'
    if abv == 1: return '✓ Good'
    return '— Avg'

def tier_bg(r):
    t = tier_label(r)
    if '⭐' in t: return '#f0fdf4'
    if '⚠'  in t: return '#fff5f5'
    return '#ffffff'

def ad_rows(rows, loc):
    out = ''
    for r in sorted([r for r in rows if r['spend']>0], key=lambda x:-x['spend']):
        bg  = tier_bg(r)
        t   = tier_label(r)
        ctr_col = '#ef4444' if r['ctr'] < 1 else '#374151'
        cpr_col = '#ef4444' if (r['results'] > 0 and r['cpr'] > 0.5) else '#374151'
        out += (
            f'<tr style="background:{bg}">'
            f'<td style="font-size:11px;max-width:200px;word-break:break-word;padding:8px 6px">{r["ad"]}</td>'
            f'<td style="font-size:10px;color:#9ca3af;padding:8px 6px">{loc}</td>'
            f'<td style="text-align:right;font-family:monospace;font-size:11px;padding:8px 6px">${r["spend"]:.2f}</td>'
            f'<td style="text-align:right;font-family:monospace;font-size:11px;padding:8px 6px">{r["reach"]:,}</td>'
            f'<td style="text-align:right;font-family:monospace;font-size:11px;padding:8px 6px;color:{ctr_col}">{r["ctr"]}%</td>'
            f'<td style="text-align:right;font-family:monospace;font-size:11px;padding:8px 6px">${r["cpm"]:.2f}</td>'
            f'<td style="text-align:right;font-family:monospace;font-size:11px;padding:8px 6px">{int(r["results"])}</td>'
            f'<td style="text-align:right;font-family:monospace;font-size:11px;padding:8px 6px;color:{cpr_col}">${r["cpr"]:.2f}</td>'
            f'<td style="padding:8px 6px">{qual_badge(r["quality"])}</td>'
            f'<td style="padding:8px 6px">{qual_badge(r["eng_rank"])}</td>'
            f'<td style="padding:8px 6px">{qual_badge(r["conv_rank"])}</td>'
            f'<td style="font-size:10px;padding:8px 6px;font-weight:600">{t}</td>'
            '</tr>'
        )
    return out

def channel_row(name, sess, conv, color):
    pct_val = round(sess/sessions*100, 1)
    conv_col = '#00c4b4' if conv > 0 else '#d1d5db'
    return (
        '<div style="display:flex;align-items:center;gap:12px;padding:7px 0;border-bottom:1px solid #f9fafb">'
        f'<div style="width:140px;font-size:12px;font-weight:500;flex-shrink:0">{name}</div>'
        f'<div style="flex:1;background:#f3f4f6;border-radius:99px;height:6px;overflow:hidden">'
        f'<div style="width:{pct_val}%;height:100%;border-radius:99px;background:{color}"></div></div>'
        f'<div style="width:44px;text-align:right;font-size:11px;font-weight:700;color:#374151;flex-shrink:0">{pct_val}%</div>'
        f'<div style="width:55px;text-align:right;font-size:11px;color:#9ca3af;flex-shrink:0">{sess:,}</div>'
        f'<div style="width:50px;text-align:right;font-size:11px;font-weight:600;color:{conv_col};flex-shrink:0">{conv}</div>'
        '</div>'
    )

# Pre-compute observation bodies (avoids nested f-string issues)
obs_what_worked = (
    "<b>Conversion rate improved WoW:</b> Sessions dropped 22.4% but conversions only fell 3.9% — "
    f"the visitors who came were of higher quality. Conv rate rose from {p_conv_rate}% to {conv_rate:.1f}%.<br><br>"
    f"<b>Organic Search held:</b> {org_s:,} sessions, {org_c} conversions — implied 12.4% conversion rate, "
    "the highest-quality acquisition channel by far.<br><br>"
    f"<b>Ellenbrook Meta improved:</b> CPR fell from $0.35 to $0.32 (&#x2212;8.6%). "
    "Ellenbrook is running cleaner campaigns than Malaga.<br><br>"
    f"<b>Instagram Stories surged:</b> {ig_stories_impr:,} story impressions (+93.9% WoW). "
    f"Avg reach {ig_story_reach} per story — the most underused format in the account."
)

obs_needs_attention = (
    "<b>Sessions down 22.4%:</b> 888 fewer visits vs prior week. "
    "Drop concentrated in New Users (&#x2212;32.4%) — the paid acquisition funnel, not member retention, is underperforming.<br><br>"
    "<b>Malaga Meta efficiency collapsed:</b> Same $281 spend, CPR rose 44% ($0.27&#x2192;$0.39), "
    "clicks fell 29.5% (912&#x2192;643). One Below-average-rated ad is dragging account quality.<br><br>"
    f"<b>GBP all signals down:</b> Website clicks &#x2212;49.7%, search reach &#x2212;23%, "
    f"total actions &#x2212;33.1%. Three independent metrics declining simultaneously.<br><br>"
    f"<b>Facebook organic dead:</b> {fb_interactions} interactions from {fb_impr:,} impressions = 0.02% engagement rate. "
    "Only 1 post published (down 75%)."
)

obs_organic_branded = (
    "95%+ of GSC clicks are branded (\"chasing better malaga\", \"chasingbetter\", etc.) — "
    "people who already know CB247 find it easily. Excellent for retention.<br><br>"
    "But very few <i>new</i> prospects find CB247 via non-branded search. "
    "\"gym ellenbrook\" gets 150 impressions at position 6 with 1.3% CTR. "
    "\"malaga gym\" gets 132 impressions at position 8 with 3.0% CTR. "
    "<b>These two keywords alone represent the clearest 30-minute SEO wins available right now.</b>"
)

obs_nonbranded = (
    "CB247 ranks positions 4&#x2013;10 for 9 non-branded queries:<br><br>"
    "<b>gym ellenbrook</b> &#x2014; pos 6, 150 impr, 1.3% CTR &#x2192; Fix: add to Ellenbrook H1<br>"
    "<b>malaga gym</b> &#x2014; pos 8, 132 impr, 3.0% CTR &#x2192; Fix: title tag update<br>"
    "<b>ellenbrook gym</b> &#x2014; pos 4, 89 impr, 4.5% CTR &#x2192; 1 internal link from homepage<br>"
    "<b>gym near me</b> &#x2014; pos 6.5, 75 impr &#x2192; GBP optimisation moves this<br>"
    "<b>fifo gym membership</b> &#x2014; pos 7.3, 62 impr &#x2192; FIFO landing page = top 3<br>"
    "<b>best gyms perth</b> &#x2014; pos 10.7, 69 impr &#x2192; On edge of page 1"
)

obs_gads_cpa = (
    f"Malaga CPA: ${gm_cpa:.2f} vs Ellenbrook CPA: ${ge_cpa:.2f} ({gads_label}). "
    f"Ellenbrook delivers conversions at 2.8x lower cost for similar spend. "
    "This gap is consistent across 4+ weeks of data.<br><br>"
    "<b>Recommendation:</b> Shift $50/week from Malaga to Ellenbrook budget. "
    "But first: verify the conversion event definitions are equivalent between campaigns. "
    "If Malaga counts contact form fills and Ellenbrook counts phone clicks, the CPA gap may be partly a tracking issue. "
    "Audit conversion events in Google Ads before moving budget."
)

obs_smart_bidding = (
    "All keywords show Max CPC = $0.01 confirming Google Maximise Conversions smart bidding is active. "
    f"Actual avg CPC: Malaga ${gm.get('cpc',0):.2f} &#x2022; Ellenbrook ${ge.get('cpc',0):.2f}.<br><br>"
    "Smart Bidding requires 30+ conversions/month to optimise accurately. "
    f"Ellenbrook ({ge.get('conv',0)} conv in one week) is approaching this threshold. "
    "Do not switch to Target CPA until hitting 30 conv/month consistently."
)

obs_malaga_cpr = (
    "Same $281 spend, 29.5% fewer clicks (912&#x2192;643), CPR worsened $0.27&#x2192;$0.39.<br><br>"
    "<b>Root cause: \"Post: Ready to shake up your routine?\"</b> &#x2014; $22.40 spent, 1 click, "
    "0.09% CTR, rated Below average on both engagement AND conversion. "
    "Meta penalises Below-average ads with worse placement and higher CPMs &#x2014; "
    "this ad is dragging down account-level quality and costing money for near-zero return.<br><br>"
    "<b>Action: Pause this ad immediately.</b> Reallocate its $22/week budget to "
    "\"Deep heat. Deep recovery.\" which is the only Malaga ad with dual Above-average signals."
)

obs_star_creative = (
    "<b>\"Instagram post: Deep heat. Deep recovery.\"</b> &#x2014; $49.49 spend, 114 clicks, 1.37% CTR.<br>"
    "Quality: Average &#x2022; Engagement: <b>Above average</b> &#x2022; Conversion: <b>Above average</b><br><br>"
    "This is the only Star-tier creative in the Malaga account this week. "
    "The recovery/wellness angle maps directly to CB247&#x2019;s sauna + ice bath differentiation &#x2014; "
    "the strongest competitive moat in the Malaga market.<br><br>"
    "<b>Action:</b> Increase to $100/week. Do NOT modify the ad copy, creative, or audience &#x2014; "
    "Meta has already found a winning audience. Changes reset the learning phase. "
    "Create a companion variation: \"Ice bath. Sauna. $11.95/week.\""
)

obs_ellenbrook_meta = (
    f"Ellenbrook CPR improved to $0.32 (from $0.35). Positive direction.<br><br>"
    "\"Push the Tempo (2)\" takes $111.63 (40% of Ellenbrook budget) with all-Average quality scores. "
    "3.06% CTR &#x2014; not poor, but no standout signals.<br><br>"
    "<b>Gap:</b> Ellenbrook has no recovery/wellness creative. "
    "The \"Deep heat. Deep recovery.\" angle is proven in Malaga &#x2014; test a matching version for Ellenbrook. "
    "Ellenbrook members use the same sauna + ice bath facilities."
)

obs_pilates_reel = (
    "\"Pilates Reel\" = largest single ad spend in Malaga ($122.66 = 44% of budget). "
    "All-Average quality signals, 1.75% CTR.<br><br>"
    "<b>Thinking:</b> Reformer Pilates is CB247&#x2019;s second most-visited page (312 sessions this week) &#x2014; "
    "the intent is clearly there. But Pilates reel viewers are often inspiration-seekers, not gym-switchers. "
    "The creative angle may be wrong.<br><br>"
    "<b>Test:</b> Replace \"Pilates Reel\" with a more direct-response version: "
    "\"Reformer Pilates in Malaga &#x2014; from $11.95/week. 24/7. No booking needed.\" "
    "with specific CTA. Run both for one week, pause the lower performer."
)

obs_stories = (
    f"67 Stories &#x2192; {ig_stories_impr:,} impressions (+93.9% WoW), avg reach {ig_story_reach} per story.<br><br>"
    "Stories significantly outperformed both Posts (1 published) and Reels in total reach this week. "
    f"5 Reels drove {ig_likes} likes (+45.3% WoW) &#x2014; excellent engagement &#x2014; "
    "but avg watch time of 4&#x2013;8 seconds vs 15s+ benchmark means the algorithm throttles distribution.<br><br>"
    "<b>Fix:</b> Start every Reel with a bold on-screen text hook in the first 0.5s. "
    "\"The only gym in Malaga with THIS\" or \"$11.95/week &#x2014; here&#x2019;s what that gets you.\""
)

obs_facebook_organic = (
    f"1 post published &#x2192; {fb_impr:,} impressions &#x2192; {fb_interactions} interactions = 0.02% engagement.<br>"
    "Compare: Revo Fitness 49,560 FB followers (9.4&#x00D7; larger), World Gym 51,590.<br><br>"
    "<b>Recommendation:</b> Reduce Facebook organic to maintenance only &#x2014; 1 post/week, "
    "repurposed from Instagram. This is not a channel CB247 can win organically at current scale. "
    "Facebook Paid (FIFO + family targeting) remains valid. Organic does not."
)

obs_gbp = (
    f"Website clicks: {gbp_web} (&#x2212;{abs(gbp_web_chg):.0f}% WoW) &#x2022; "
    f"Search reach: {gbp_reach:,} (&#x2212;{abs(gbp_reach_chg):.0f}%) &#x2022; "
    f"Total actions: {gbp_actions} (&#x2212;{abs(gbp_actions_chg):.0f}%)<br>"
    f"Reviews this week: {gbp_reviews} &#x2022; Avg rating: {gbp_rating}&#x2605;<br><br>"
    "Three independent metrics declining simultaneously = systemic signal drop, not noise. "
    "Likely cause: competitor GBP listings gaining ground while CB247 posting cadence dropped.<br><br>"
    "<b>Action today:</b> Post 1 GBP update (both locations). "
    f"Respond to all {gbp_reviews} reviews including the critical one. Upload 5&#x2013;10 facility photos per location."
)

# Build top pages rows
page_notes = [
    'Homepage — primary landing page',
    'Strong purchase intent — Pilates searchers',
    'High-intent — prospects seeking to join',
    'Member retention — class schedule',
    'Thank-you = conversion confirmation',
    'Recovery content — sauna/ice bath traffic',
    'PT upsell opportunity',
    'Kids Hub — family segment researching',
]
page_rows_html = ''
for i, (pg, note) in enumerate(zip(ga4['top_pages'][:8], page_notes), 1):
    page_rows_html += (
        f'<tr>'
        f'<td style="font-family:monospace;font-size:10px;color:#9ca3af;padding:8px 6px">{i}</td>'
        f'<td style="font-size:11px;padding:8px 6px">{pg["pagePath"]}</td>'
        f'<td style="text-align:right;font-family:monospace;font-size:11px;padding:8px 6px">{int(pg["screenPageViews"]):,}</td>'
        f'<td style="text-align:right;font-family:monospace;font-size:11px;padding:8px 6px">{int(pg["sessions"]):,}</td>'
        f'<td style="font-size:10px;color:#6b7280;padding:8px 6px">{note}</td>'
        '</tr>'
    )

ad_rows_html = ad_rows(mal25, 'Malaga') + ad_rows(ell25, 'Ellenbrook')

channels_html = (
    channel_row('Organic Search', org_s,  org_c,  '#00c4b4') +
    channel_row('Paid Social',    paid_s, paid_c, '#3b82f6') +
    channel_row('Direct',         direct, dir_c,  '#8b5cf6') +
    channel_row('Cross-network',  cross,  crs_c,  '#f59e0b') +
    channel_row('Paid Search',    paid_sh, psh_c, '#ef4444') +
    channel_row('Organic Social', org_soc, ors_c, '#fb923c')
)

# Priority recommendation bodies
p1_body = (
    "<b>Evidence:</b> $22.40 spent, 1 click, 0.09% CTR, Below average engagement + Below average conversion. "
    "Meta penalises Below-average ads with worse delivery and higher CPMs &#x2014; this ad is costing money "
    "while dragging down account-level quality, which raises costs on ALL other Malaga ads.<br><br>"
    "<b>Action:</b> Pause in Meta Ads Manager today. Reallocate the $22/week budget to "
    "\"Instagram post: Deep heat. Deep recovery.\" Expected result: Malaga CPR should begin recovering "
    "toward $0.30 within 3&#x2013;5 days as account quality improves."
)
p2_body = (
    "<b>Evidence:</b> $49.49 spend, 114 clicks, 1.37% CTR. "
    "Engagement: Above average. Conversion: Above average. Only Star-tier creative in Malaga this week. "
    "The recovery/wellness angle maps to CB247&#x2019;s sauna + ice bath &#x2014; "
    "the only feature no local competitor can match.<br><br>"
    "<b>Action:</b> Raise to $100/week total. Do NOT modify the ad copy, creative, or audience settings &#x2014; "
    "Meta has already learnt the winning audience. Any change resets the learning phase. "
    "Create one companion variation: \"Ice bath. Then sauna. $11.95/week.\" and run both."
)
p3_body = (
    "<b>Evidence:</b> \"gym ellenbrook\" at position 6, 150 impressions, 1.3% CTR. "
    "\"malaga gym\" at position 8, 132 impressions, 3.0% CTR. Both have commercial intent. "
    "CB247 already ranks for them &#x2014; the pages just aren&#x2019;t optimised to hold position.<br><br>"
    "<b>Action (30 minutes in WordPress):</b><br>"
    "&#x2460; Update Ellenbrook page title to: \"24/7 Gym Ellenbrook WA &#x2014; ChasingBetter247 | No Lock-In from $11.95\"<br>"
    "&#x2461; Update Malaga page title to: \"Gym Malaga Perth | 24/7 Access from $11.95/wk &#x2014; ChasingBetter247\"<br>"
    "&#x2462; Update each page H1 to include the suburb name<br>"
    "Expected impact: 2&#x2013;4 week ranking improvement; potential to double clicks from each keyword."
)
p4_body = (
    f"<b>Evidence:</b> Ellenbrook CPA = ${ge_cpa:.2f} vs Malaga CPA = ${gm_cpa:.2f} ({gads_label}). "
    "Ellenbrook delivers 2.8&#x00D7; more conversions per dollar. "
    "This gap is consistent across 4+ weeks of data.<br><br>"
    "<b>Important check first:</b> Verify conversion event definitions are identical in both campaigns. "
    "If Malaga counts contact form fills and Ellenbrook counts phone clicks, the gap may partly reflect "
    "a tracking difference, not a true performance difference. Audit in Google Ads before moving budget.<br><br>"
    "<b>Also:</b> Upload 25&#x2013;31 May Google Ads CSVs to get the current week&#x2019;s actual numbers "
    "before making budget decisions."
)
p5_body = (
    f"<b>Evidence:</b> Website clicks &#x2212;49.7%, search reach &#x2212;23%, total actions &#x2212;33.1% WoW. "
    f"{gbp_reviews} reviews received including 1 critical. GBP drives free local traffic &#x2014; "
    "a GBP post costs nothing and has same-day impact on local pack signals.<br><br>"
    "<b>Three actions in order of impact:</b><br>"
    f"&#x2460; <b>Respond to all {gbp_reviews} reviews today</b> &#x2014; especially the critical one. "
    "Template: &#x201C;Thank you for your feedback. We&#x2019;re sorry your experience didn&#x2019;t meet our standards &#x2014; "
    "please contact reception@chasingbetter247.com.au so we can make it right.&#x201D; "
    "A professional reply is visible to every prospective member who reads it.<br>"
    "&#x2461; <b>Post 1 GBP update to both locations</b> &#x2014; "
    "&#x201C;Perth winters were made for the gym. Train 24/7 from $11.95/week, no lock-in.&#x201D; + sauna photo.<br>"
    "&#x2462; <b>Upload 5 facility photos per location</b> &#x2014; sauna, ice bath, gym floor, Kids Hub, reception. "
    "Google weights photo quantity and recency as a direct local pack ranking signal."
)

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f8fafc;color:#111827;line-height:1.5;font-size:13px}
.wrap{max-width:960px;margin:0 auto;padding:32px 20px}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:14px;margin-bottom:24px}
.obs-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:24px}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:22px 24px;margin-bottom:16px}
.card-h{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;margin-bottom:14px}
table{width:100%;border-collapse:collapse}
th{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af;padding:8px 6px;border-bottom:2px solid #f3f4f6;text-align:left}
td{border-bottom:1px solid #f9fafb;color:#374151;vertical-align:top}
@media(max-width:640px){.obs-grid{grid-template-columns:1fr}.kpi-grid{grid-template-columns:1fr 1fr}}
"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CB247 Weekly Report — 25–31 May 2026</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);color:#fff;padding:36px 40px;border-radius:16px;margin-bottom:32px">
  <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:#64748b;margin-bottom:10px">ChasingBetter247 &middot; Malaga + Ellenbrook</div>
  <h1 style="font-size:1.6rem;font-weight:800;margin-bottom:4px">Weekly Marketing Report</h1>
  <div style="font-size:1rem;color:#94a3b8">25&ndash;31 May 2026 &nbsp;&middot;&nbsp; Generated {gen_time}</div>
  <div style="margin-top:22px;display:flex;gap:28px;flex-wrap:wrap">
    <div><div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.08em">Sessions</div>
      <div style="font-size:1.5rem;font-weight:800;color:#fff">{sessions:,}</div>
      <div style="font-size:11px;color:#ef4444">{pct(sessions,p_sessions)} WoW</div></div>
    <div><div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.08em">Conversions</div>
      <div style="font-size:1.5rem;font-weight:800;color:#fff">{convs}</div>
      <div style="font-size:11px;color:#ef4444">{pct(convs,p_convs)} WoW</div></div>
    <div><div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.08em">Conv. Rate</div>
      <div style="font-size:1.5rem;font-weight:800;color:#fff">{conv_rate:.1f}%</div>
      <div style="font-size:11px;color:#00c4b4">{chg(conv_rate, p_conv_rate)} vs prior</div></div>
    <div><div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.08em">Total Ad Spend</div>
      <div style="font-size:1.5rem;font-weight:800;color:#fff">${all_spend:,.0f}</div>
      <div style="font-size:11px;color:#94a3b8">Meta + Google Ads</div></div>
    <div><div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.08em">Meta Results</div>
      <div style="font-size:1.5rem;font-weight:800;color:#fff">{meta_total_results:,}</div>
      <div style="font-size:11px;color:#00c4b4">CPR ${meta_blended_cpr:.2f}</div></div>
    <div><div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.08em">IG Followers</div>
      <div style="font-size:1.5rem;font-weight:800;color:#fff">{ig_followers:,}</div>
      <div style="font-size:11px;color:#00c4b4">+{ig_balance} this week</div></div>
  </div>
</div>

{section("Executive Summary")}
<div class="obs-grid">
{obs("teal", "What Worked This Week", obs_what_worked)}
{obs("red",  "What Needs Immediate Attention", obs_needs_attention)}
</div>

{section("Website Performance — GA4 (24&ndash;31 May 2026)")}
<div class="kpi-grid">
{kpi("Sessions", f"{sessions:,}", chg(sessions,p_sessions,inverse=True), f"Prior week: {p_sessions:,}")}
{kpi("Users", f"{users:,}", chg(users,p_users,inverse=True), f"Prior: {p_users:,}")}
{kpi("New Users", f"{new_users:,}", chg(new_users,p_new_users,inverse=True), f"Prior: {p_new_users:,}")}
{kpi("Conversions", f"{convs}", chg(convs,p_convs,inverse=True), f"Prior: {p_convs}")}
{kpi("Conv. Rate", f"{conv_rate:.1f}%", chg(conv_rate,p_conv_rate), f"Prior: {p_conv_rate:.1f}%")}
{kpi("Organic Search", f"{org_s:,}", "", f"{org_c} convs &middot; {round(org_c/org_s*100,1) if org_s else 0:.1f}% conv rate")}
{kpi("Paid Social", f"{paid_s:,}", "", f"{paid_c} direct conversions via GA4")}
{kpi("Direct", f"{direct:,}", "", f"{dir_c} conversions &middot; 53.5% rate (incl. members)")}
</div>

<div class="card">
  <div class="card-h">Traffic by Channel</div>
  <div style="display:flex;gap:12px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af;padding:4px 0 10px">
    <span style="width:140px">Channel</span><span style="flex:1">Share</span>
    <span style="width:44px;text-align:right">%</span>
    <span style="width:55px;text-align:right">Sessions</span>
    <span style="width:50px;text-align:right">Convs</span>
  </div>
  {channels_html}
  <p style="font-size:11px;color:#9ca3af;margin-top:12px">
    <b>Direct conversion rate (53.5%):</b> Inflated by existing member logins and class bookings.
    True new-lead conversions: Organic Search 12.4%, Paid Search 12.1%.
    Paid Social&#x2019;s 0 GA4 conversions doesn&#x2019;t mean Meta ads don&#x2019;t work &mdash; it means the conversion path is indirect (click ad &#x2192; leave &#x2192; return via Direct &#x2192; convert). Meta&#x2019;s own attribution shows 1,584 results this week.
  </p>
</div>

<div class="card">
  <div class="card-h">Top Pages by Sessions</div>
  <table>
    <thead><tr><th>#</th><th>Page</th><th style="text-align:right">Views</th><th style="text-align:right">Sessions</th><th>Insight</th></tr></thead>
    <tbody>{page_rows_html}</tbody>
  </table>
  <p style="font-size:11px;color:#9ca3af;margin-top:10px">
    Recovery page (/post-workout-recovery) in top 6 confirms wellness content resonates &mdash; aligns with the "Deep heat. Deep recovery." ad performance.
    Kids Hub in top 8 signals family segment actively researching &mdash; no paid ads targeting this audience yet.
  </p>
</div>

{section("Organic Search — Google Search Console (28-day to 31 May)")}
<div class="kpi-grid">
{kpi("Total Clicks", "1,809", "", "28-day period to 31 May")}
{kpi("Impressions", "7,245", "", "Total search appearances")}
{kpi("Avg CTR", "24.97%", "", "High — predominantly branded")}
{kpi("Avg Position", "1.5", "", "Top of page 1")}
</div>
<div class="obs-grid">
{obs("amber", "Branded Search Dominates — Growth Ceiling Risk", obs_organic_branded)}
{obs("teal",  "Non-Branded Quick Wins — 9 Keywords Positions 4&ndash;10", obs_nonbranded)}
</div>

{section(f"Google Ads — {gads_label} (Most Recent Available)")}
<div style="background:#fff8e1;border:1px solid #fbbf24;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:12px;color:#92400e">
  &#9888; <b>Note:</b> Google Ads CSV for 25&ndash;31 May has not been uploaded.
  Figures below are from the prior week ({gads_label}) and serve as reference only.
  Upload the 25&ndash;31 May CSV to get current week data.
</div>
<div class="kpi-grid">
{kpi("Malaga Spend", f"${gm.get('spend',0):.2f}", "", f"{gm.get('clicks',0)} clicks &middot; {gm.get('impr',0):,} impr")}
{kpi("Ellenbrook Spend", f"${ge.get('spend',0):.2f}", "", f"{ge.get('clicks',0)} clicks &middot; {ge.get('impr',0):,} impr")}
{kpi("Malaga CPA", f"${gm_cpa:.2f}", "", f"{gm.get('conv',0)} conversions &middot; ${gm.get('cpc',0):.2f} CPC")}
{kpi("Ellenbrook CPA", f"${ge_cpa:.2f}", "", f"{ge.get('conv',0)} conversions &middot; ${ge.get('cpc',0):.2f} CPC")}
</div>
<div class="obs-grid">
{obs("red",  "Malaga CPA 2.8&times; Higher Than Ellenbrook", obs_gads_cpa)}
{obs("teal", "Smart Bidding Confirmed — Strategy Is Correct", obs_smart_bidding)}
</div>

{section("Meta Ads — 25&ndash;31 May 2026 (Live CSV Data)")}
<div class="kpi-grid">
{kpi("Malaga Spend", f"${m25['spend']:.2f}", chg(m25['spend'],m18['spend'],inverse=True), f"Prev: ${m18['spend']:.2f}")}
{kpi("Malaga CPR", f"${m25['cpr']:.2f}", chg(m25['cpr'],m18['cpr'],inverse=True), "Prev: $0.27 &middot; +44% WoW")}
{kpi("Malaga Clicks", f"{m25['clicks']:,}", chg(m25['clicks'],m18['clicks'],inverse=True), f"Prev: {m18['clicks']:,} &middot; &minus;29.5%")}
{kpi("Ellenbrook Spend", f"${e25['spend']:.2f}", chg(e25['spend'],e18['spend'],inverse=True), f"Prev: ${e18['spend']:.2f}")}
{kpi("Ellenbrook CPR", f"${e25['cpr']:.2f}", chg(e25['cpr'],e18['cpr'],inverse=True), "Prev: $0.35 &middot; &minus;8.6%")}
{kpi("Blended", f"${meta_total_spend:.2f}", "", f"{meta_total_results:,} results &middot; ${meta_blended_cpr:.2f} CPR")}
</div>
<div class="obs-grid">
{obs("red",   "Malaga: Efficiency Collapsing — CPR +44% WoW", obs_malaga_cpr)}
{obs("teal",  "Star Creative: Scale Immediately", obs_star_creative)}
{obs("amber", "Ellenbrook: Improving but Gap in Creative Strategy", obs_ellenbrook_meta)}
{obs("amber", "Pilates Reel: Biggest Budget, Average Return", obs_pilates_reel)}
</div>

<div class="card" style="overflow-x:auto">
  <div class="card-h">All Active Ads — 25&ndash;31 May 2026</div>
  <table>
    <thead><tr>
      <th>Ad Creative</th><th>Loc.</th>
      <th style="text-align:right">Spend</th><th style="text-align:right">Reach</th>
      <th style="text-align:right">CTR</th><th style="text-align:right">CPM</th>
      <th style="text-align:right">Results</th><th style="text-align:right">CPR</th>
      <th>Quality</th><th>Eng.</th><th>Conv.</th><th>Tier</th>
    </tr></thead>
    <tbody>{ad_rows_html}</tbody>
  </table>
  <p style="font-size:10px;color:#9ca3af;margin-top:10px">
    &#x2B50; Star = &ge;2 Above average signals &nbsp;&middot;&nbsp;
    &#x26A0; Poor = any Below average signal &nbsp;&middot;&nbsp;
    Green rows = Star &nbsp;&middot;&nbsp; Red rows = Poor
  </p>
</div>

{section("Organic Social — Metricool (25&ndash;31 May 2026)")}
<div class="kpi-grid">
{kpi("IG Followers", f"{ig_followers:,}", f'<span style="color:#00c4b4">+{ig_balance} this week</span>', "0.10% growth")}
{kpi("FB Followers", f"{fb_followers:,}", "", "0.09% growth")}
{kpi("IG Story Impr", f"{ig_stories_impr:,}", f'<span style="color:#00c4b4">&#x25B2; 93.9% WoW</span>', "67 stories published")}
{kpi("IG Reel Likes", f"{ig_likes}", f'<span style="color:#00c4b4">&#x25B2; 45.3% WoW</span>', "5 Reels published")}
{kpi("IG Reach/Day", f"{ig_reach_day:,}", f'<span style="color:#00c4b4">&#x25B2; 15.6% WoW</span>', "Avg daily reach")}
{kpi("FB Interactions", f"{fb_interactions}", f'<span style="color:#ef4444">&#x25BC; 90.0% WoW</span>', f"From {fb_impr:,} impressions")}
{kpi("GBP Actions", f"{gbp_actions:,}", f'<span style="color:#ef4444">&#x25BC; {abs(gbp_actions_chg):.0f}% WoW</span>', "Clicks+calls+directions")}
{kpi("GBP Web Clicks", f"{gbp_web}", f'<span style="color:#ef4444">&#x25BC; {abs(gbp_web_chg):.0f}% WoW</span>', "Critical signal drop")}
</div>
<div class="obs-grid">
{obs("teal",  "Instagram Stories: Highest-Reach Format This Week", obs_stories)}
{obs("red",   "Facebook Organic: Stop Treating It as a Growth Channel", obs_facebook_organic)}
{obs("red",   "GBP: Three Signals Down — Act Today", obs_gbp)}
{obs("amber", "Reel Watch Time 4&ndash;8s vs 15s+ Benchmark", '<b>All top 5 Reels this week are reposts from other creators</b> &mdash; 0 original CB247 branded Reels in the top 5. Reposts drive vanity metrics but not brand equity or direct sign-ups.<br><br>Avg watch time 4&ndash;8s. Algorithm throttles Reels with &lt;15s retention. Fix: lead every Reel with an on-screen text hook in the first 0.5s. "The only gym in Malaga with THIS" or "$11.95/week &mdash; here&#x2019;s what that gets you." Pattern interrupt in frame 1 = longer retention = more distribution.')}
</div>

{section("5 Priority Recommendations — Week of 1&ndash;7 June 2026")}
{priority("1", "Pause &quot;Ready to Shake Up Your Routine?&quot; — Malaga Meta [Do Today]", p1_body)}
{priority("2", "Scale &quot;Deep Heat. Deep Recovery.&quot; to $100/Week — Malaga Meta [Do Today]", p2_body)}
{priority("3", "Fix Two Title Tags — SEO Quick Win [30 Minutes]", p3_body)}
{priority("4", "Audit Before Shifting Google Ads Budget: Malaga &#x2192; Ellenbrook [This Week]", p4_body)}
{priority("5", "GBP Recovery: Three Actions, One Hour Total [Do Today]", p5_body)}

<div style="margin-top:48px;padding:24px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;text-align:center">
  <div style="font-size:11px;color:#9ca3af">
    <b style="color:#374151">ChasingBetter247 AI Marketing Engine</b> &nbsp;&middot;&nbsp;
    Report generated {gen_time} &nbsp;&middot;&nbsp;
    Data: GA4 (24&ndash;31 May), GSC (28-day to 31 May), Meta CSVs (25&ndash;31 May),
    Google Ads CSVs (18&ndash;24 May &mdash; 25&ndash;31 May not yet uploaded), Metricool PDF (25&ndash;31 May)
  </div>
</div>

</div>
</body>
</html>"""

out_path = OUT / 'cb247-weekly-report-25may-31may-2026.html'
out_path.write_text(html, encoding='utf-8')
print(f"Report saved -> {out_path}")
print(f"  Sessions: {sessions:,} | Convs: {convs} | Conv rate: {conv_rate:.1f}%")
print(f"  Meta Malaga: ${m25['spend']:.2f} / {m25['clicks']} clicks / CPR ${m25['cpr']:.2f}")
print(f"  Meta Ellenbrook: ${e25['spend']:.2f} / {e25['clicks']} clicks / CPR ${e25['cpr']:.2f}")
print(f"  Google Ads ({gads_label}): Malaga ${gm.get('spend',0):.2f} / Ellenbrook ${ge.get('spend',0):.2f}")
