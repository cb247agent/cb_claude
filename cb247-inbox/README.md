# CB247 Inbox

Drop files here weekly before the Monday 2am AWST cron job runs.

## Files expected

| Filename | Source | Frequency | Used by |
|---|---|---|---|
| `metricool.pdf` | Metricool weekly report PDF (export from Metricool dashboard) | Every Monday morning before 1:55am AWST | `scripts/parse_metricool_pdf.py` → `state/metricool-data.json` → Organic Social page |

## Metricool PDF — how to export

1. Sign in to Metricool
2. Select the CB247 brand
3. Go to **Reports** → **Weekly Report**
4. Set date range: **last completed Saturday → Friday**
5. Click **Export PDF**
6. Save to this folder as `metricool.pdf` (overwrite the existing file)

The parser reads the date range from inside the PDF, so filename can be simple.
Failed parses gracefully fall back to the previous week's data — no panic.

## Run manually

```bash
.venv/bin/python3.13 scripts/parse_metricool_pdf.py
.venv/bin/python3.13 scripts/inject-social-block.py
```

## Notes

- `metricool.pdf` is in `.gitignore` (contains private analytics data)
- If you forget to drop the PDF, the dashboard falls back to the previous parsed week
- The parser is forgiving — if Metricool tweaks their PDF layout slightly, individual fields may go missing but the rest still works
