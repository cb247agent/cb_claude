# MWCC Data Inbox

**Drop your two OWNA exports here every Monday before 2:00 PM.**

The automated pipeline reads these files at 2pm Monday and generates the weekly report.

---

## Files to drop each week

| File | Where to export from | Replace or rename to |
|------|---------------------|----------------------|
| `MYWORLD_REPORT.xlsx` | OWNA → Reports → Weekly Wage Monitor | Keep as `MYWORLD_REPORT.xlsx` |
| `utilisation.xlsx` | OWNA → Reports → Utilisation | Keep as `utilisation.xlsx` |

> You can also keep the date in the filename (e.g. `utilisation-25May26-31May26.xlsx`) —
> the script will find it automatically.

---

## What each file provides

**MYWORLD_REPORT.xlsx**
- Revenue per centre
- Wage % (exc. leave) — alerts if above 42% threshold
- Enquiries, exits, enrolments per centre
- Overall occupancy % per centre

**utilisation.xlsx**
- Per-room daily occupancy (Monday–Friday)
- Calculates weekly average per room
- Flags rooms over 100% capacity (compliance risk)

---

## Troubleshooting

If the report shows "awaiting ops data", one of the files is missing or misnamed.

Check the log: `logs/mwcc-weekly-report.log`

Run manually to test:
```bash
cd CB_Marketing
python scripts/parse_mwcc_ops.py
```

---

## Do not commit these files

xlsx files are excluded from git (they may contain sensitive operational data).
