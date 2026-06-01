# Broken Page Redirect Map — ChasingBetter247
Generated: 2026-05-30
Source: Screaming Frog audit (3 × 4xx errors detected)

## Why This Matters
Broken pages waste Google's crawl budget and kill any existing link equity. 
Each 301 redirect passes ~99% of ranking signals to the destination page.

---

## Redirects to Implement

| Broken URL (404) | Redirect To (301) | Reason |
|---|---|---|
| `/2026free` | `/join` or `/membership` | Old promo URL — redirect to current join/membership page |
| `/personal-training/nhung-dam` | `/personal-training` | Trainer profile no longer exists — redirect to PT overview |
| `/personal-training/briana-peterson` | `/personal-training` | Trainer profile no longer exists — redirect to PT overview |

---

## How to Implement (Webflow / WordPress / any CMS)

### Option A — CMS Redirect Manager (recommended)
Most website builders have a built-in 301 redirect tool:
- **Webflow:** Dashboard → SEO → 301 Redirects → Add Rule
- **WordPress:** Use "Redirection" plugin → Add New Redirect
- **Squarespace:** Pages → Not Linked → URL Redirects

Set each row as: `[Old Path]` → `[New Destination]` → Type: 301

### Option B — .htaccess (Apache servers)
Add to the root `.htaccess` file:
```
Redirect 301 /2026free https://www.chasingbetter247.com.au/join
Redirect 301 /personal-training/nhung-dam https://www.chasingbetter247.com.au/personal-training
Redirect 301 /personal-training/briana-peterson https://www.chasingbetter247.com.au/personal-training
```

### Option C — Nginx
Add to server config:
```nginx
rewrite ^/2026free$ https://www.chasingbetter247.com.au/join permanent;
rewrite ^/personal-training/nhung-dam$ https://www.chasingbetter247.com.au/personal-training permanent;
rewrite ^/personal-training/briana-peterson$ https://www.chasingbetter247.com.au/personal-training permanent;
```

---

## Verify After Implementation
Run in terminal:
```bash
curl -I https://www.chasingbetter247.com.au/2026free
curl -I https://www.chasingbetter247.com.au/personal-training/nhung-dam
curl -I https://www.chasingbetter247.com.au/personal-training/briana-peterson
```
Each should return `HTTP/2 301` with `location:` pointing to the new URL.

Then go to Google Search Console → Coverage → Excluded → "Not found (404)" 
and use the URL Inspection tool to confirm pages are no longer indexed as errors.
