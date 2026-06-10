"""
send_cb247_management_report.py — Email the weekly CB247 management report.

Mirrors send_mwcc_management_report.py but sends to TIA ONLY by default.
Uses CB247_MANAGEMENT_RECIPIENTS env var if set; otherwise falls back to
WEEKLY_REPORT_RECIPIENT (Tia's address). Per Tia's explicit request:
"please send to tia only" — the script enforces single-recipient safety.

Env vars expected:
    SMTP_HOST                       (e.g. smtp.gmail.com)
    SMTP_PORT                       (default 587)
    SMTP_USER                       (sender email)
    SMTP_PASS                       (app password)
    CB247_MANAGEMENT_RECIPIENTS     (comma-separated — preferred when set)
    WEEKLY_REPORT_RECIPIENT         (fallback — Tia's email)

Run:
    python scripts/send_cb247_management_report.py
"""

from __future__ import annotations

import datetime as _dt
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs" / "reports"


def _load_dotenv():
    """Best-effort .env loader (no third-party dep)."""
    env = BASE_DIR / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _recipients() -> list[str]:
    """Resolve recipient list. Tia-only by default.

    Per Tia's instruction (09 Jun 2026): "please send to tia only".
    CB247_MANAGEMENT_RECIPIENTS exists as an env override for later when
    Tia wants to add Angela, Mark, or other managers — but for now the
    safe default is single-recipient.
    """
    raw = os.getenv("CB247_MANAGEMENT_RECIPIENTS", "").strip()
    if raw:
        addrs = [e.strip() for e in raw.split(",") if e.strip()]
        if addrs:
            return addrs
    fb = os.getenv("WEEKLY_REPORT_RECIPIENT", "").strip()
    if fb:
        return [fb]
    print("[cb247-mgmt-email] No recipients configured. Set CB247_MANAGEMENT_RECIPIENTS or WEEKLY_REPORT_RECIPIENT in .env.")
    return []


def _find_latest_report() -> Path | None:
    today = _dt.date.today().strftime("%Y-%m-%d")
    candidate = OUTPUTS_DIR / f"cb247-management-report-{today}.html"
    if candidate.exists():
        return candidate
    reports = sorted(OUTPUTS_DIR.glob("cb247-management-report-*.html"), reverse=True)
    return reports[0] if reports else None


def main() -> int:
    _load_dotenv()

    report = _find_latest_report()
    if not report:
        print("[cb247-mgmt-email] No cb247-management-report-*.html found in outputs/reports/ — run bake_cb247_management_report.py first.")
        return 1

    recipients = _recipients()
    if not recipients:
        return 1

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    if not all([host, user, pwd]):
        print("[cb247-mgmt-email] SMTP_HOST/USER/PASS missing in .env — cannot send.")
        return 1

    html_body = report.read_text(encoding="utf-8")

    today_str = _dt.date.today().strftime("%a %d %b %Y")
    subject = f"CB247 Management Report — {today_str}"

    msg = EmailMessage()
    msg["From"]    = user
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(
        f"CB247 Management Report — {today_str}\n\n"
        f"This week's CB247 management report is included below as HTML.\n\n"
        f"External revenue dashboards (live):\n"
        f"  Malaga:     https://cb247-weekly-revenue-malaga.netlify.app\n"
        f"  Ellenbrook: https://cb247-weekly-revenue-ellenbrook.netlify.app\n\n"
        f"If your client blocks HTML, the same report is saved at:\n"
        f"  {report.relative_to(BASE_DIR)}\n\n"
        f"— CB247 Marketing Ops"
    )
    msg.add_alternative(html_body, subtype="html")

    print(f"[cb247-mgmt-email] Sending '{subject}' to {len(recipients)} recipient(s)")
    for r in recipients:
        print(f"  → {r}")

    try:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        print(f"[cb247-mgmt-email] ✅ Sent")
        return 0
    except Exception as e:
        print(f"[cb247-mgmt-email] ⚠️  Send failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
