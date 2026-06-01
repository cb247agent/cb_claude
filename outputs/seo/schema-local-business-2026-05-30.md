# LocalBusiness Schema Markup — ChasingBetter247
Generated: 2026-05-30
Issue: 40 pages have no structured data. LocalBusiness + GymOrHealthClub schema
boosts local pack rankings and enables rich results in Google Search.

## Why Schema Markup Matters
Schema tells Google exactly what your business is, where it is, and what it offers.
For local gyms, this directly influences:
- Google Maps / Local Pack rankings
- "Near me" search visibility
- Star ratings appearing in search results
- FAQ rich results (click-through rate booster)

---

## SCHEMA 1 — Malaga Location
**Add to: `/` (homepage) and any Malaga-specific pages**
**How:** Paste inside `<head>` or as a `<script>` block before `</body>`

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": ["GymOrHealthClub", "LocalBusiness"],
  "name": "ChasingBetter247 — Malaga",
  "url": "https://www.chasingbetter247.com.au",
  "logo": "https://www.chasingbetter247.com.au/logo.png",
  "image": "https://www.chasingbetter247.com.au/gym-malaga.jpg",
  "description": "24/7 gym in Malaga, Perth. Reformer Pilates, Kids Hub, Sauna & Ice Bath, ChasingRX, Group Fitness, Personal Training. From $11.95/week, no lock-in contract.",
  "telephone": "+61 8 XXXX XXXX",
  "email": "reception@chasingbetter247.com.au",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "[INSERT MALAGA STREET ADDRESS]",
    "addressLocality": "Malaga",
    "addressRegion": "WA",
    "postalCode": "6090",
    "addressCountry": "AU"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": -31.8478,
    "longitude": 115.8780
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
      "opens": "00:00",
      "closes": "23:59"
    }
  ],
  "priceRange": "$$",
  "currenciesAccepted": "AUD",
  "paymentAccepted": "Credit Card, Debit Card, Direct Debit",
  "amenityFeature": [
    {"@type": "LocationFeatureSpecification", "name": "24/7 Access", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Kids Hub / Childminding", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Sauna", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Ice Bath", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Reformer Pilates", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Group Fitness Classes", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Personal Training", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Massage", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Free Parking", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "No Lock-in Contract", "value": true}
  ],
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "Memberships",
    "itemListElement": [
      {
        "@type": "Offer",
        "name": "Standard Membership",
        "price": "11.95",
        "priceCurrency": "AUD",
        "priceSpecification": {
          "@type": "RecurringCharge",
          "billingPeriod": "P1W"
        },
        "description": "Full gym access, 24/7, no lock-in contract"
      }
    ]
  },
  "sameAs": [
    "https://www.instagram.com/chasingbetter247",
    "https://www.facebook.com/chasingbetter247"
  ]
}
</script>
```

---

## SCHEMA 2 — Ellenbrook Location
**Add to: `/ellenbrook` page (once created) and Ellenbrook-specific pages**

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": ["GymOrHealthClub", "LocalBusiness"],
  "name": "ChasingBetter247 — Ellenbrook",
  "url": "https://www.chasingbetter247.com.au/ellenbrook",
  "logo": "https://www.chasingbetter247.com.au/logo.png",
  "image": "https://www.chasingbetter247.com.au/gym-ellenbrook.jpg",
  "description": "24/7 gym in Ellenbrook, Perth. Group Fitness, Kids Hub, ChasingRX, Personal Training. Family-friendly gym from $11.95/week — no lock-in contract.",
  "telephone": "+61 8 XXXX XXXX",
  "email": "reception@chasingbetter247.com.au",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "[INSERT ELLENBROOK STREET ADDRESS]",
    "addressLocality": "Ellenbrook",
    "addressRegion": "WA",
    "postalCode": "6069",
    "addressCountry": "AU"
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
      "opens": "00:00",
      "closes": "23:59"
    }
  ],
  "priceRange": "$$",
  "amenityFeature": [
    {"@type": "LocationFeatureSpecification", "name": "24/7 Access", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Kids Hub / Childminding", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Group Fitness Classes", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Personal Training", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "No Lock-in Contract", "value": true},
    {"@type": "LocationFeatureSpecification", "name": "Free Parking", "value": true}
  ],
  "sameAs": [
    "https://www.instagram.com/chasingbetter247",
    "https://www.facebook.com/chasingbetter247"
  ]
}
</script>
```

---

## SCHEMA 3 — FAQ Schema (Homepage + FAQ page)
**Add to: `/` (homepage) and `/faqs`**
FAQ schema generates rich results — the question/answer appears directly in Google search results, dramatically increasing click-through rates.

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "How much does a gym membership cost at ChasingBetter247?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "ChasingBetter247 membership starts from $11.95 per week with no lock-in contract. You can cancel anytime."
      }
    },
    {
      "@type": "Question",
      "name": "Is ChasingBetter247 open 24 hours?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes — ChasingBetter247 is open 24 hours a day, 7 days a week at both Malaga and Ellenbrook locations."
      }
    },
    {
      "@type": "Question",
      "name": "Does ChasingBetter247 have a kids area?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes — we have Kids Hub childminding available during staffed hours at both Malaga and Ellenbrook. Kids are supervised so you can train without distraction."
      }
    },
    {
      "@type": "Question",
      "name": "Does ChasingBetter247 have a sauna?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes — ChasingBetter247 Malaga has a sauna and ice bath (Bath House) available to members. Recovery facilities are included with membership."
      }
    },
    {
      "@type": "Question",
      "name": "Can I get a casual gym pass at ChasingBetter247?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes — casual passes are available at ChasingBetter247. Visit the casual passes page on our website or ask at reception."
      }
    },
    {
      "@type": "Question",
      "name": "Does ChasingBetter247 have Reformer Pilates?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes — ChasingBetter247 Malaga offers Reformer Pilates classes as part of the membership. Check the group fitness timetable for session times."
      }
    }
  ]
}
</script>
```

---

## Implementation Guide

**Webflow:**
Project Settings → Custom Code → `<head>` section → Paste Schema 1 + Schema 3
For Ellenbrook page specifically: Page Settings → Custom Code → Head → Paste Schema 2

**WordPress:**
Use "Schema Pro" plugin OR add directly to `functions.php`:
```php
add_action('wp_head', function() { ?>
  [paste schema here]
<?php });
```

**Validate after adding:**
→ https://search.google.com/test/rich-results
Paste your URL — it will confirm Google can read the schema correctly.
