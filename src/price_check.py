"""
src/price_check.py  —  Scrape Costco.com for current prices

Usage:
    python src/price_check.py                  # scrape all relevant SKUs
    python src/price_check.py --sku 796993     # scrape one SKU
    python src/price_check.py --dry-run        # print results, don't write to DB
"""

import argparse
import json
import random
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

from bs4 import BeautifulSoup
import undetected_chromedriver as uc

DB_PATH = Path(__file__).parent.parent / "data" / "costco.db"
WATCHLIST_PATH = Path(__file__).parent.parent / "watchlist.json"

RATE_LIMIT_SLEEP = 30  # seconds between requests
FAILURE_THRESHOLD = 0.5  # flag if >50% of SKUs fail

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def get_skus_to_check(conn: sqlite3.Connection, single_sku: str | None = None) -> list[dict]:
    """
    Returns a unified, deduplicated list of SKUs to scrape.
    Includes:
      1. Purchase SKUs within the last 30 days (price protection window).
      2. All watchlist SKUs.
    """
    skus: dict[str, dict] = {}

    if single_sku:
        skus[single_sku] = {"sku": single_sku, "item_name": single_sku, "source": "manual"}
        return list(skus.values())

    # 1. Recent purchases (30-day window)
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    rows = conn.execute(
        """
        SELECT item_sku, item_full_name AS item_name
        FROM purchases
        WHERE transaction_date >= ?
        GROUP BY item_sku
        """,
        (cutoff,),
    ).fetchall()
    for sku, name in rows:
        skus[sku] = {"sku": sku, "item_name": name or sku, "source": "purchase"}

    # 2. Watchlist
    if WATCHLIST_PATH.exists():
        with open(WATCHLIST_PATH) as f:
            watchlist = json.load(f)
        for item in watchlist:
            sku = str(item["sku"])
            if sku not in skus:
                skus[sku] = {"sku": sku, "item_name": item.get("name", sku), "source": "watchlist"}

    return list(skus.values())


def scrape_sku(sku: str, driver: uc.Chrome) -> dict | None:
    """
    Fetch Costco.com search results for a SKU using undetected-chromedriver.
    Returns a dict with current_price, regular_price, offer_end_date, product_url.
    Returns None on failure.
    """
    url = f"https://www.costco.com/s?keyword={sku}"
    
    try:
        driver.get(url)
        time.sleep(4)  # Wait for page to fully render/bots to clear
    except Exception as e:
        print(f"  ⚠️  [{sku}] Browser failed: {e}")
        return None

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # --- Current (offer/member) price ---
    current_price = None
    price_el = (
        soup.find("span", {"automation-id": "unitPrice"})
        or soup.find("span", class_="price")
        or soup.find("div", class_="price")
    )
    if price_el:
        try:
            current_price = float(price_el.get_text(strip=True).replace("$", "").replace(",", ""))
        except ValueError:
            pass

    if not current_price:
        print(f"  ⚠️  [{sku}] Could not parse current price")
        return None

    # --- Regular (non-sale) price — only present when item is on sale ---
    regular_price = None
    was_el = (
        soup.find("div", class_="price-was")
        or soup.find("span", class_="price-was")
        or soup.find("s", class_="price")          # strikethrough
        or soup.find("del")                         # generic strikethrough
    )
    if was_el:
        try:
            regular_price = float(was_el.get_text(strip=True).replace("$", "").replace(",", ""))
        except ValueError:
            pass

    # --- Offer end date ---
    offer_end_date = None
    date_el = (
        soup.find("span", {"automation-id": "offerEndDate"})
        or soup.find("div", class_="offer-end-date")
        or soup.find("span", class_="valid-thru")
    )
    if date_el:
        # Store as raw text; agent.py normalises to YYYY-MM-DD
        offer_end_date = date_el.get_text(strip=True)

    return {
        "current_price":  current_price,
        "regular_price":  regular_price,
        "offer_end_date": offer_end_date,
        "product_url":    url,
    }


def store_result(conn: sqlite3.Connection, sku: str, result: dict) -> None:
    conn.execute(
        """
        INSERT INTO price_history (item_sku, regular_price, current_price, offer_end_date, product_url)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            sku,
            result["regular_price"],
            result["current_price"],
            result["offer_end_date"],
            result["product_url"],
        ),
    )
    conn.commit()


def run(single_sku: str | None = None, dry_run: bool = False) -> dict:
    """
    Main entry point. Returns a summary dict:
        {
            "results":        [{sku, item_name, current_price, regular_price, ...}],
            "failed_skus":    [sku, ...],
            "failure_ratio":  float,
        }
    """
    conn = get_connection()
    items = get_skus_to_check(conn, single_sku)

    if not items:
        print("No SKUs to check.")
        conn.close()
        return {"results": [], "failed_skus": [], "failure_ratio": 0.0}

    print(f"🔍 Checking {len(items)} SKU(s)...")

    # Start the undetected browser
    options = uc.ChromeOptions()
    options.headless = True
    driver = uc.Chrome(options=options)

    results = []
    failed = []

    try:
        for i, item in enumerate(items):
            sku = item["sku"]
            print(f"  [{i+1}/{len(items)}] SKU {sku} — {item['item_name']}")
            result = scrape_sku(sku, driver)

            if result is None:
                failed.append(sku)
            else:
                result["sku"] = sku
                result["item_name"] = item["item_name"]
                results.append(result)
                print(
                    f"       current=${result['current_price']:.2f}"
                    + (f"  regular=${result['regular_price']:.2f}" if result["regular_price"] else "")
                    + (f"  valid till {result['offer_end_date']}" if result["offer_end_date"] else "")
                )
                if not dry_run:
                    store_result(conn, sku, result)

            # Rate-limit between requests (skip sleep on last item or in dry-run)
            if i < len(items) - 1 and not dry_run:
                time.sleep(RATE_LIMIT_SLEEP)
    finally:
        driver.quit()
        conn.close()

    failure_ratio = len(failed) / len(items) if items else 0.0
    if failed:
        print(f"\n⚠️  Failed SKUs ({len(failed)}): {', '.join(failed)}")
    if failure_ratio > FAILURE_THRESHOLD:
        print(f"🚨 Failure ratio {failure_ratio:.0%} exceeds threshold — scraper alert will be sent.")

    return {
        "results":       results,
        "failed_skus":   failed,
        "failure_ratio": failure_ratio,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Costco prices for relevant SKUs.")
    parser.add_argument("--sku",     help="Scrape a single SKU only")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to DB")
    args = parser.parse_args()
    run(single_sku=args.sku, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
