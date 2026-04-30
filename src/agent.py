"""
src/agent.py  —  Daily orchestrator

Runs all daily jobs in order:
  1. Ingest all CSVs in the repo root
  2. Scrape prices for all relevant SKUs
  3. Compute price protection alerts
  4. Compute watchlist sale alerts
  5. Send daily digest email (if any alerts)
  6. Send scraper failure alert (if failure ratio > threshold)

Usage:
    python src/agent.py              # full run
    python src/agent.py --dry-run   # print alerts without sending emails
"""

import argparse
import glob
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import ingest as ingest_module
import notifier
import price_check as price_check_module
import watchlist as watchlist_module

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "data" / "costco.db"


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def compute_price_protection_alerts(conn: sqlite3.Connection) -> list[dict]:
    """
    For each SKU bought in the last 30 days, check if it is currently on sale
    on Costco Sameday by comparing regular_price and current_price.
    Since Sameday base prices are marked up, we calculate the explicit discount
    amount instead of comparing against the warehouse purchase_price.
    """
    cutoff = (date.today() - timedelta(days=30)).isoformat()

    rows = conn.execute(
        """
        SELECT
            p.item_sku,
            p.item_full_name,
            MIN(p.unit_price)      AS purchase_price,
            MAX(p.transaction_date) AS purchase_date,
            ph.current_price,
            ph.regular_price,
            ph.offer_end_date,
            ph.product_url
        FROM purchases p
        JOIN (
            SELECT item_sku, current_price, regular_price, offer_end_date, product_url
            FROM price_history
            WHERE (item_sku, checked_at) IN (
                SELECT item_sku, MAX(checked_at)
                FROM price_history
                GROUP BY item_sku
            )
            AND checked_at >= datetime('now', '-2 days')
        ) ph ON ph.item_sku = p.item_sku
        WHERE p.transaction_date >= ?
        GROUP BY p.item_sku
        HAVING ph.regular_price IS NOT NULL
           AND ph.current_price < ph.regular_price
        """,
        (cutoff,),
    ).fetchall()

    alerts = []
    for sku, name, purchase_price, purchase_date, current_price, regular_price, offer_end_date, product_url in rows:
        savings = round(regular_price - current_price, 2)
        alerts.append({
            "sku":           sku,
            "item_name":     name or sku,
            "purchase_price": purchase_price,
            "old_price":     regular_price,
            "new_price":     current_price,
            "savings":       savings,
            "purchase_date": purchase_date,
            "deadline":      offer_end_date,
            "product_url":   product_url,
        })

    return alerts


def run(dry_run: bool = False) -> None:
    today = date.today().isoformat()
    print(f"\n{'='*50}")
    print(f"🛒 Costco Agent — {today}")
    print(f"{'='*50}\n")

    # ── Step 1: Ingest all CSVs ───────────────────────────────────────────────
    csv_files = glob.glob(str(REPO_ROOT / "*.csv"))
    if not csv_files:
        print("⚠️  No CSV files found in repo root.")
    else:
        conn = ingest_module.get_connection()
        ingest_module.init_db(conn)
        for csv_path in csv_files:
            inserted, skipped = ingest_module.ingest_csv(csv_path, conn)
            print(f"  📥 '{csv_path}': inserted {inserted}, skipped {skipped}")
        conn.close()

    # ── Step 2: Scrape prices ─────────────────────────────────────────────────
    print("\n📡 Scraping prices...")
    scrape_summary = price_check_module.run(dry_run=dry_run)
    total_checked = len(scrape_summary["results"]) + len(scrape_summary["failed_skus"])
    failed_count  = len(scrape_summary["failed_skus"])
    failure_ratio = scrape_summary["failure_ratio"]

    # ── Step 3: Price protection alerts ──────────────────────────────────────
    print("\n🔎 Computing price protection alerts...")
    conn = get_connection()
    price_alerts = compute_price_protection_alerts(conn)
    if price_alerts:
        for a in price_alerts:
            print(f"  💰 {a['item_name']}: ${a['old_price']:.2f} → ${a['new_price']:.2f} (save ${a['savings']:.2f})")
    else:
        print("  No price drops found.")

    # ── Step 4: Watchlist sale alerts ────────────────────────────────────────
    print("\n🛒 Checking watchlist...")
    watchlist_hits = watchlist_module.get_watchlist_sales(conn)
    conn.close()

    is_failure = failure_ratio > price_check_module.FAILURE_THRESHOLD

    # ── Step 5: Send daily digest ─────────────────────────────────────────────
    print("\n📧 Sending notifications...")
    if not is_failure:
        notifier.send_daily_digest(price_alerts, watchlist_hits, dry_run=dry_run)
    else:
        print("  Skipping daily digest because scraper failed (preventing stale deals from sending).")

    # ── Step 6: Send scraper failure alert ───────────────────────────────────
    if is_failure:
        notifier.send_scraper_failure_alert(failed_count, total_checked, dry_run=dry_run)

    print(f"\n✅ Done. {len(price_alerts)} price drop(s), {len(watchlist_hits)} watchlist sale(s).\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Costco Price Protection Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without scraping or sending emails",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
