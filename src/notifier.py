"""
src/notifier.py  —  Email sender via Resend API

Sends two types of emails:
  1. Daily digest  — price protection drops + watchlist sales (one email per day)
  2. Scraper alert — if >50% of SKUs failed to scrape

Usage (test):
    RESEND_API_KEY=re_xxx NOTIFY_EMAIL=you@gmail.com python src/notifier.py --test
"""

import argparse
import os
from datetime import date

import resend
from dotenv import load_dotenv

load_dotenv()

SENDER = "Costco Agent <onboarding@resend.dev>"


def _format_currency(val: float) -> str:
    return f"${val:.2f}"


def _offer_date_str(offer_end_date: str | None) -> str:
    if not offer_end_date:
        return "—"
    return offer_end_date


def build_digest_html(
    price_alerts: list[dict],
    watchlist_hits: list[dict],
) -> str:
    today = date.today().strftime("%b %d, %Y")

    sections = []

    # ── Price Protection section ──────────────────────────────────────────────
    if price_alerts:
        rows = ""
        for item in price_alerts:
            deadline_str = f'<span style="color:#dc2626;">⚠️ Offer valid until: {_offer_date_str(item.get("deadline"))}</span><br>' if item.get('deadline') else ''
            rows += f"""
            <tr>
              <td style="padding:12px 0; border-bottom:1px solid #f0f0f0;">
                <strong>{item['item_name']}</strong><br>
                <span style="color:#888;">You paid: {_format_currency(item.get('purchase_price', item['old_price']))}
                  on {item.get('purchase_date','—')}</span><br>
                Sameday pricing: <span style="text-decoration:line-through; color:#888;">{_format_currency(item['old_price'])}</span>
                → <strong style="color:#16a34a;">{_format_currency(item['new_price'])}</strong>
                <span style="color:#16a34a;">(↓ {_format_currency(item['savings'])} off)</span><br>
                {deadline_str}
                <a href="{item['product_url']}" style="color:#0070cc;">→ View on Costco.com</a>
              </td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#0070cc; border-bottom:2px solid #0070cc; padding-bottom:6px;">
          💰 Price Protection ({len(price_alerts)} item{'s' if len(price_alerts)!=1 else ''})
        </h2>
        <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        """)

    # ── Watchlist section ─────────────────────────────────────────────────────
    if watchlist_hits:
        rows = ""
        for item in watchlist_hits:
            rows += f"""
            <tr>
              <td style="padding:12px 0; border-bottom:1px solid #f0f0f0;">
                <strong>{item['item_name']}</strong><br>
                Regular: <span style="text-decoration:line-through; color:#888;">
                  {_format_currency(item['regular_price'])}</span>
                → Today: <strong style="color:#16a34a;">{_format_currency(item['sale_price'])}</strong>
                <span style="color:#16a34a;">(↓ {_format_currency(item['savings'])} off)</span><br>
                {"<span style='color:#dc2626;'>⚠️ Offer valid until: " + _offer_date_str(item.get('offer_end_date')) + "</span><br>" if item.get('offer_end_date') else ""}
                <a href="{item['product_url']}" style="color:#0070cc;">→ View on Costco.com</a>
              </td>
            </tr>"""

        sections.append(f"""
        <h2 style="color:#ea580c; border-bottom:2px solid #ea580c; padding-bottom:6px;">
          🛒 Watchlist Sales ({len(watchlist_hits)} item{'s' if len(watchlist_hits)!=1 else ''})
        </h2>
        <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        """)

    # ── No-alerts section ─────────────────────────────────────────────────────
    if not sections:
        sections.append("""
        <div style="text-align:center; padding:32px 0;">
          <span style="font-size:48px;">✅</span>
          <h2 style="color:#16a34a; margin:12px 0 4px;">All clear today!</h2>
          <p style="color:#888; margin:0;">No price drops or watchlist sales found.<br>
          The agent ran successfully and is monitoring your items.</p>
        </div>
        """)

    body = "\n".join(sections)

    return f"""
    <html><body style="font-family:Arial,sans-serif; max-width:600px; margin:auto; color:#333;">
      <div style="background:#0070cc; color:#fff; padding:16px 24px; border-radius:8px 8px 0 0;">
        <h1 style="margin:0; font-size:20px;">🛍️ Costco Daily Alert — {today}</h1>
      </div>
      <div style="padding:24px; background:#fff; border:1px solid #e5e5e5; border-top:none; border-radius:0 0 8px 8px;">
        {body}
        <p style="margin-top:24px; font-size:12px; color:#aaa;">
          This email was sent by your Costco Price Protection Agent.<br>
          Newark (#1660) warehouse · 30-day price adjustments must be claimed in-store.
        </p>
      </div>
    </html></body>
    """


def send_daily_digest(
    price_alerts: list[dict],
    watchlist_hits: list[dict],
    dry_run: bool = False,
) -> None:
    n_drops = len(price_alerts)
    n_sales = len(watchlist_hits)
    today = date.today().strftime("%b %d")

    if not price_alerts and not watchlist_hits:
        subject = f"✅ Costco Daily Check-in — All clear ({today})"
    else:
        subject = f"🛒 Costco Daily Alert — {n_drops} price drop{'s' if n_drops!=1 else ''}, {n_sales} watchlist sale{'s' if n_sales!=1 else ''} ({today})"

    html = build_digest_html(price_alerts, watchlist_hits)

    if dry_run:
        print(f"\n[DRY RUN] Would send digest:\n  Subject: {subject}")
        return

    _send(subject, html)
    print(f"✅ Digest sent: {subject}")


def send_scraper_failure_alert(
    failed_count: int,
    total_count: int,
    dry_run: bool = False,
) -> None:
    today = date.today().strftime("%b %d, %Y")
    subject = f"⚠️ Costco Agent: Scraper failed on {today}"
    html = f"""
    <html><body style="font-family:Arial,sans-serif; max-width:600px; margin:auto; color:#333;">
      <div style="background:#dc2626; color:#fff; padding:16px 24px; border-radius:8px 8px 0 0;">
        <h1 style="margin:0; font-size:20px;">⚠️ Scraper Failure — {today}</h1>
      </div>
      <div style="padding:24px; background:#fff; border:1px solid #e5e5e5; border-top:none; border-radius:0 0 8px 8px;">
        <p>The daily price check could not fetch prices for most items today.</p>
        <p><strong>Failed SKUs: {failed_count} / {total_count}</strong></p>
        <p>Likely cause: Costco rate-limiting or a change in page structure.</p>
        <p>Check the <strong>GitHub Actions logs</strong> for details.</p>
        <p style="margin-top:24px; font-size:12px; color:#aaa;">Costco Price Protection Agent · Newark (#1660)</p>
      </div>
    </html></body>
    """

    if dry_run:
        print(f"\n[DRY RUN] Would send scraper alert:\n  Subject: {subject}")
        return

    _send(subject, html)
    print(f"✅ Scraper failure alert sent.")


def _send(subject: str, html: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    to_email = os.environ.get("NOTIFY_EMAIL")

    if not api_key or not to_email:
        raise EnvironmentError("RESEND_API_KEY and NOTIFY_EMAIL must be set in environment.")

    resend.api_key = api_key
    resend.Emails.send({
        "from":    SENDER,
        "to":      [to_email],
        "subject": subject,
        "html":    html,
    })


def _test_email() -> None:
    """Send a sample digest email with dummy data for testing."""
    test_price_alerts = [
        {
            "item_name":    "Organic Avocado Hass Variety, 6-count",
            "purchase_price": 6.99,
            "old_price":    7.99,
            "new_price":    5.99,
            "savings":      2.00,
            "purchase_date": "Jan 31, 2026",
            "deadline":     "Apr 15",
            "product_url":  "https://www.costco.com/s?keyword=796993",
        }
    ]
    test_watchlist_hits = [
        {
            "item_name":    "Kirkland Signature Free-Range Organic Eggs, 24-count",
            "regular_price": 7.69,
            "sale_price":   5.99,
            "savings":      1.70,
            "offer_end_date": "Apr 15",
            "product_url":  "https://www.costco.com/s?keyword=1068083",
        }
    ]
    send_daily_digest(test_price_alerts, test_watchlist_hits)


def main() -> None:
    parser = argparse.ArgumentParser(description="Costco email notifier")
    parser.add_argument("--test", action="store_true", help="Send a test digest email")
    args = parser.parse_args()
    if args.test:
        _test_email()


if __name__ == "__main__":
    main()
