# CB_Marketing OS — Complete External Tools Breakdown

*Last Updated: 27 May 2026*

---

## Category 1: AI & Model Gateway

---

### 1. OpenRouter

| Detail | Information |
|--------|-------------|
| **Purpose** | API gateway that provides access to multiple LLM models |
| **Subscription** | $40/month (pay-per-token, estimate based on usage) |
| **Annual Cost** | $480/year |
| **Function** | Powers all 9 marketing agents (strategist, content-agent, seo-agent, etc.) to generate content, analyze data, and provide recommendations |
| **Models Used** | minimax-m2.7 (default), google/gemini-3-flash-preview (subagents) |
| **5-Site Support** | ✅ Unlimited — single API gateway for all locations |
| **Status** | ✅ Active |

---

### 2. Anthropic Claude

| Detail | Information |
|--------|-------------|
| **Purpose** | Backup AI model for complex analysis tasks |
| **Subscription** | $10/month (pay-per-token usage) |
| **Annual Cost** | $120/year |
| **Function** | Handles heavy analysis tasks, report generation, and complex reasoning that requires high-quality outputs |
| **5-Site Support** | ✅ Unlimited |
| **Status** | ✅ Active |

---

### 3. Ollama

| Detail | Information |
|--------|-------------|
| **Purpose** | Local LLM inference engine |
| **Subscription** | Free (self-hosted) |
| **Annual Cost** | $0 |
| **Function** | Runs gemma4:31b-cloud locally for heavy analysis without cloud costs. Processes large datasets and generates complex reports locally |
| **5-Site Support** | ✅ Unlimited — local, no per-site limits |
| **Status** | ✅ Running on localhost:11434 |

---

## Category 2: SEO Tools

---

### 4. Apify

| Detail | Information |
|--------|-------------|
| **Purpose** | Web scraping and automation platform |
| **Subscription** | $49/month (Starter plan) |
| **Annual Cost** | $588/year |
| **Function** | Scrapes competitor websites, tracks Google search results (SERP), monitors Instagram content from competitors, gathers market intelligence automatically |
| **Used By** | `scripts/pull_apify.py`, skills/competitor-ads-scraper, skills/competitor-seo-scraper |
| **5-Site Support** | ✅ 5+ concurrent actors (1 per gym location) |
| **Status** | ✅ Active — API key configured |

---

### 5. Ahrefs Lite

| Detail | Information |
|--------|-------------|
| **Purpose** | SEO analytics and backlink analysis |
| **Subscription** | $129/month |
| **Annual Cost** | $1,548/year |
| **Function** | Tracks backlinks to CB247 websites, monitors keyword rankings and search volume, identifies keyword opportunities, analyzes competitor SEO strategies, provides domain rating scores |
| **Used By** | `scripts/pull_ahrefs.py`, skills/seo-content-strategist |
| **5-Site Support** | ✅ Lite plan includes 5 tracked domains (1 per gym location) |
| **Status** | ❌ Not configured — API key missing in .env |
| **Why Needed** | Without it, we're guessing on keywords and can't track backlink growth |

---

### 6. Screaming Frog SEO Spider

| Detail | Information |
|--------|-------------|
| **Purpose** | Technical SEO site audit tool |
| **Subscription** | $279/year (~$23.25/month) |
| **Annual Cost** | $279/year |
| **Function** | Crawls CB247 websites like Google does, finds broken links, missing meta tags, duplicate content, slow pages, missing alt tags on images. Generates audit reports for developers to fix technical issues before they hurt rankings |
| **Used By** | `scripts/run_screaming_frog.py` |
| **5-Site Support** | ✅ Unlimited — one-time purchase covers all sites |
| **Status** | ✅ Owned — installed at `/Applications/Screaming Frog SEO Spider.app` |
| **Why Needed** | Technical SEO issues kill rankings silently. Finds problems Google penalizes for |

---

## Category 3: Content Generation

---

### 7. Higgsfield.ai

| Detail | Information |
|--------|-------------|
| **Purpose** | AI image and video generation |
| **Subscription** | $49/month (estimate — confirm with sales) |
| **Annual Cost** | $588/year |
| **Function** | Generates on-brand marketing images and videos using AI. Produces featured images for blog posts, social media graphics, ad creatives in CB247 brand colors (#3FA69A teal) |
| **Used By** | `mcp_servers/higgsfield_server.js`, team-commands skill (/creative) |
| **5-Site Support** | ✅ 5 brand accounts (1 per gym location) |
| **Status** | ❌ Not configured — HIGGSFIELD_API_KEY not set |
| **Why Needed** | Cuts image production time from days to minutes without needing a designer for every asset |

---

## Category 4: Team Collaboration

---

### 8. Claude Cowork

| Detail | Information |
|--------|-------------|
| **Purpose** | Team collaboration platform for Claude Code |
| **Subscription** | $20/seat/month |
| **Annual Cost** | $240/seat |
| **Recommended Seats** | 3 seats: 1 Admin, 1 Content Creator, 1 Approver |
| **Total Cost** | $60/month ($720/year for 3 seats) |
| **Function** | Gives non-technical team members access to CB_Marketing via simple slash commands (/blog, /meeting prepare, /status). Enables team collaboration without requiring Claude Code CLI knowledge |
| **5-Site Support** | ✅ 5 seats |
| **Status** | ❌ Not configured |
| **Why Needed** | Without it, only 1 technical person can access the system. With it, any team member can generate content and run reports |

---

### 9. Notion

| Detail | Information |
|--------|-------------|
| **Purpose** | Knowledge base and documentation |
| **Subscription** | $10/seat/month |
| **Annual Cost** | $120/seat |
| **Recommended Seats** | 3 seats |
| **Total Cost** | $30/month ($360/year for 3 seats) |
| **Function** | Stores strategy documents, campaign history, learnings, brand guidelines. Maintains the marketing knowledge base. Replaces scattered Google Docs with organized wiki |
| **5-Site Support** | ✅ Per-seat licensing |
| **Status** | ✅ Active — API key configured |
| **Why Needed** | After every campaign, team updates Notion with what worked/didn't. New members read wiki to understand approach instantly |

---

### 10. Slack

| Detail | Information |
|--------|-------------|
| **Purpose** | Team notifications and communication |
| **Subscription** | Free tier available; $24/seat/month for paid |
| **Annual Cost** | $0 (free tier) or $288/year |
| **Function** | Sends automated alerts for performance anomalies (CPL spiked to $32, organic traffic dropped 20%), delivers weekly report summaries to team channels, notifies when KPIs breach thresholds |
| **5-Site Support** | ✅ Unlimited |
| **Status** | ❌ Not configured — SLACK_BOT_TOKEN placeholder in .env |
| **Why Needed** | Team gets Slack alerts within hours of issues instead of discovering them days later during manual checks |
| **Recommendation** | Start with free tier for notifications; upgrade to paid only if full team communication needed |

---

## Category 5: Google Platform

---

### 11. Google Analytics 4 (GA4)

| Detail | Information |
|--------|-------------|
| **Purpose** | Website analytics and conversion tracking |
| **Subscription** | Free (Standard tier) |
| **Annual Cost** | $0 |
| **Function** | Tracks all website visitors — sessions, users, conversions, traffic sources, top pages, device breakdown. Shows which marketing channels drive memberships |
| **Used By** | `scripts/pull_ga4.py`, skills/analytics-connector, performance-dashboard |
| **Data** | Sessions, users, new users, conversions, bounce rate, top 10 pages, traffic sources, device categories |
| **5-Site Support** | ✅ 5 properties (1 per gym location) |
| **Status** | ✅ Active — GA4_PROPERTY_ID and GA4_MEASUREMENT_ID configured |
| **Why Needed** | Without it, we're blind to whether 'gym malaga' searches from Google actually convert |

---

### 12. Google Search Console (GSC)

| Detail | Information |
|--------|-------------|
| **Purpose** | Organic search performance data |
| **Subscription** | Free |
| **Annual Cost** | $0 |
| **Function** | Shows how CB247 ranks in Google — clicks, impressions, CTR, keyword rankings. Identifies which keywords we're winning and losing on |
| **Used By** | `scripts/pull_gsc.py`, skills/seo-reporting |
| **Data** | Total clicks, impressions, average CTR, average position, top 10 queries, top 10 pages |
| **5-Site Support** | ✅ Separate GSC property per site |
| **Status** | ✅ Active — configured via Google OAuth |
| **Why Needed** | Shows which keywords we rank #1-10 for and which need more content to push higher |

---

### 13. Google Ads API

| Detail | Information |
|--------|-------------|
| **Purpose** | Paid search campaign data |
| **Subscription** | Free (standard access) |
| **Annual Cost** | $0 |
| **Function** | Pulls live campaign data — spend, CPC, CTR, conversions by campaign and location. Enables real-time CPL monitoring and automated bidding rules |
| **Used By** | `scripts/pull_google_ads.py`, skills/google-ads-optimizer |
| **Data** | Campaign spend, impressions, clicks, CPC, CTR, conversions, CPL per campaign |
| **5-Site Support** | ✅ MCC (Manager Account) with 5 sub-accounts |
| **Status** | ⚠️ Partial — requires GOOGLE_ADS_DEVELOPER_TOKEN |
| **Why Needed** | Tracks whether our paid ads actually generate leads. Sets alerts when CPL exceeds target |

---

### 14. Google OAuth

| Detail | Information |
|--------|-------------|
| **Purpose** | Authentication for all Google services |
| **Subscription** | Free |
| **Annual Cost** | $0 |
| **Function** | Centralized authentication flow for GA4, GSC, Google Ads. OAuth credentials stored in secrets/google-oauth.json and secrets/token.json |
| **Used By** | `scripts/google_auth.py` (centralized auth handler) |
| **5-Site Support** | ✅ Single OAuth for all Google services |
| **Status** | ✅ Active |

---

## Category 6: Meta Platform

---

### 15. Meta Business Manager

| Detail | Information |
|--------|-------------|
| **Purpose** | Facebook/Instagram ad account management |
| **Subscription** | Free |
| **Annual Cost** | $0 |
| **Function** | Central platform for managing Meta ad accounts, page access, team permissions for CB247's Facebook and Instagram |
| **5-Site Support** | ✅ 5 ad accounts (1 per gym location) |
| **Status** | ✅ Active |

---

### 16. Meta Ads API

| Detail | Information |
|--------|-------------|
| **Purpose** | Facebook/Instagram ad performance data |
| **Subscription** | Free |
| **Annual Cost** | $0 |
| **Function** | Would provide automated access to ad performance data (impressions, clicks, spend, CPC) instead of manual CSV exports |
| **Used By** | skills/meta-ads-optimizer |
| **Data** | Campaign spend, impressions, clicks, CPC, CPM, engagement |
| **5-Site Support** | ✅ 5 ad accounts |
| **Status** | ⚠️ CSV only — Meta Marketing API not connected |
| **Why Needed** | Currently requires manual CSV export from Ads Manager. API would enable automated real-time data |

---

### 17. Meta Pixel

| Detail | Information |
|--------|-------------|
| **Purpose** | Website conversion tracking from social traffic |
| **Subscription** | Free |
| **Annual Cost** | $0 |
| **Function** | Tracks Instagram/Facebook traffic to CB247 website. Shows which social posts lead to website visits and sign-ups |
| **Used By** | GA4 integration |
| **5-Site Support** | ✅ 1 pixel per gym website |
| **Status** | ⚠️ Partial — enhanced conversion tracking not configured |
| **Why Needed** | Connects social ad spend to actual website conversions and memberships |

---

## Category 7: Visualization & CDN

---

### 18. Chart.js

| Detail | Information |
|--------|-------------|
| **Purpose** | Interactive charts for dashboards |
| **Subscription** | Free (CDN) |
| **Annual Cost** | $0 |
| **Function** | Renders interactive charts in the CB247 command center dashboard — line charts for trends, bar charts for comparisons, pie charts for breakdowns |
| **Used By** | `dashboards/cb247-command-center.html` |
| **5-Site Support** | ✅ Included |
| **Status** | ✅ Included via CDN |

---

### 19. Google Fonts

| Detail | Information |
|--------|-------------|
| **Purpose** | Typography for reports and dashboards |
| **Subscription** | Free (CDN) |
| **Annual Cost** | $0 |
| **Function** | Provides fonts (Roboto, Open Sans) for HTML reports and dashboards. Maintains professional typography across all outputs |
| **Used By** | `scripts/bake-weekly-report.py`, dashboards |
| **5-Site Support** | ✅ Included |
| **Status** | ✅ Included via Google Fonts CDN |

---

## Category 8: Email & Reporting

---

### 20. Gmail/SMTP

| Detail | Information |
|--------|-------------|
| **Purpose** | Automated email delivery |
| **Subscription** | Free (with Google Workspace) |
| **Annual Cost** | $0 |
| **Function** | Sends automated weekly PDF performance reports to stakeholders. Delivers SEO alerts and KPI breach notifications |
| **Used By** | `scripts/send_weekly_report.py`, `scripts/send_seo_report.py` |
| **5-Site Support** | ✅ Unlimited |
| **Status** | ✅ Active — SMTP credentials configured |

---

## Summary Table

| # | Tool | Category | Monthly | Annual | Status |
|---|------|---------|--------|--------|--------|
| 1 | OpenRouter | AI | $40 | $480 | ✅ Active |
| 2 | Anthropic Claude | AI | $10 | $120 | ✅ Active |
| 3 | Ollama | AI | $0 | $0 | ✅ Running |
| 4 | Apify | SEO | $49 | $588 | ✅ Active |
| 5 | Ahrefs Lite | SEO | $129 | $1,548 | ❌ Needed |
| 6 | Screaming Frog | SEO | $23.25 | $279 | ✅ Owned |
| 7 | Higgsfield.ai | Content | $49 | $588 | ❌ Needed |
| 8 | Claude Cowork (3 seats) | Team | $60 | $720 | ❌ Needed |
| 9 | Notion (3 seats) | Team | $30 | $360 | ✅ Active |
| 10 | Slack | Team | $0-24 | $0-288 | ❌ Optional |
| 11 | Google Analytics 4 | Google | $0 | $0 | ✅ Active |
| 12 | Google Search Console | Google | $0 | $0 | ✅ Active |
| 13 | Google Ads API | Google | $0 | $0 | ⚠️ Partial |
| 14 | Google OAuth | Google | $0 | $0 | ✅ Active |
| 15 | Meta Business Manager | Meta | $0 | $0 | ✅ Active |
| 16 | Meta Ads API | Meta | $0 | $0 | ⚠️ CSV only |
| 17 | Meta Pixel | Meta | $0 | $0 | ⚠️ Partial |
| 18 | Chart.js | Viz | $0 | $0 | ✅ Included |
| 19 | Google Fonts | Viz | $0 | $0 | ✅ Included |
| 20 | Gmail/SMTP | Email | $0 | $0 | ✅ Active |
| | **TOTAL** | | **$390.25** | **$4,683** | |

---

## Cost Breakdown by Category

| Category | Monthly | Annual | Tools |
|----------|---------|--------|-------|
| AI & Model Gateway | $50 | $600 | 3 tools |
| SEO Tools | $201.25 | $2,415 | 3 tools |
| Content Generation | $49 | $588 | 1 tool |
| Team Collaboration | $90 | $1,080 | 3 tools |
| Google Platform | $0 | $0 | 4 tools |
| Meta Platform | $0 | $0 | 3 tools |
| Visualization | $0 | $0 | 2 tools |
| Email | $0 | $0 | 1 tool |
| **TOTAL** | **$390.25** | **$4,683** | **20 tools** |

---

## Priority Recommendation

| Priority | Tool | Monthly | Why |
|----------|------|---------|-----|
| **Must Have** | Ahrefs Lite | $129 | Core SEO intelligence |
| **High Value** | Higgsfield.ai | $49 | AI image/video generation |
| **Essential** | Claude Cowork | $60 | Team access for non-technical staff |
| **Nice to Have** | Slack Paid | $24 | Better team notifications |
| **Already Have** | Apify | $49 | Already active |
| **Already Have** | Notion | $30 | Already active |
| **Already Have** | OpenRouter | $40 | Already active |