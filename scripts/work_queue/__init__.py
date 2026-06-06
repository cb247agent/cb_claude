"""
CB247 Work Queue — structured action emission + measurement pipeline.

Each performance page (SEO, Meta, Google Ads, GBP, Social, Membership) emits
WorkQueueAction records to state/work-queue.json weekly. A sync script pushes
them to Supabase for the dashboard. After items reach 'Done' status, a
measurement job fetches actual KPIs and computes verdicts.

Architecture doc: CB_Brain/wiki/Work-Queue-Architecture.md
Session 1 scope: schema.py + baselines.py + seo_emitter.py
"""
