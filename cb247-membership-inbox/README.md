# CB247 Membership Inbox

Drop the 3 weekly XLSX exports here **before Monday 1:55am AWST** so the
Monday 10am cron picks them up.

## Files expected

| Filename (exact) | Source | Where to export |
|---|---|---|
| `PGM_ContractsSummary.xlsx` | Perfect Gym → Reports → Contracts Summary | Weekly report covering last completed Sat–Fri |
| `PGM_AllContracts.xlsx`     | Perfect Gym → Reports → All Contracts     | Full snapshot as at Sunday night |
| `Cleverwaiver.xlsx`         | CleverWaiver dashboard export             | Cancellation surveys for the report week |

**Filenames must match exactly** — the parser looks them up by name.

If Cleverwaiver has no responses some weeks, drop an empty file or skip it.
The parser skips gracefully — the rest of the membership dashboard still works.

## What runs

1. **Monday 10am AWST** — cron triggers `weekly-report.sh`
2. `parse_membership_data.py` reads the 3 XLSX files → `state/membership-data.json`
3. `inject-membership-data.py` updates the dashboard's `window.MEMBERSHIP_DATA` block
4. Deploys via git push to GitHub Pages
5. **By 10:30am** — fresh numbers live on CB247 → Clubs → Membership Statistics

## Run manually

```bash
cd ~/Documents/ChasingBetter/CB_Marketing
./.venv/bin/python3.13 scripts/parse_membership_data.py
./.venv/bin/python3.13 scripts/inject-membership-data.py
git add docs/index.html
git commit -m "data: weekly membership refresh"
git push
```

## What's extracted

**From PGM Contracts Summary (weekly aggregate):**
- Per-club totals: New, Ended, Suspended, Future Cancellations, Projected
- Base unique people (excludes add-ons + Kids Hub + Employee Free + Fitness Passport, dedupes by user)
- Cancel reason histogram (from Ended contracts tab)

**From PGM AllContracts (master list):**
- Total active base members per club (Status = "Live")
- Active add-ons by category: Recovery (Sauna/Ice Bath) · Reformer Pilates · Neon (Group Fitness) · ChasinRX · Sauna Only

**From Cleverwaiver (cancellation surveys):**
- Reason breakdown (with per-club split)
- "Would you return?" Yes/Unsure/No
- "What would have helped you stay?" — top 10 themes

## Notes

- Files in this folder are **git-ignored** (private member data)
- The parser keeps the last 12 weeks of history in `state/membership-history.json` for WoW comparison
- If you forget to drop one week, the previous parse stays live — no panic
