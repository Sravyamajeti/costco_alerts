"""
src/watchlist.py  —  Detect watchlist items currently on sale at Costco

A watchlist item is "on sale" when Costco's product page shows both:
  - regular_price  (the strikethrough non-sale price)
  - current_price  < regular_price  (the active offer/member price)

No user-maintained "normal price" needed — Costco's own page is the source of truth.
"""

import json
import sqlite3
from pathlib import Path

WATCHLIST_PATH = Path(__file__).parent.parent / "watchlist.json"


def get_watchlist_sales(conn: sqlite3.Connection) -> list[dict]:
    """
    Returns a list of watchlist items that are currently on sale.
    Each entry: {item_name, sku, regular_price, sale_price, savings, offer_end_date, product_url}
    """
    if not WATCHLIST_PATH.exists():
        print("watchlist.json not found — skipping watchlist check.")
        return []

    with open(WATCHLIST_PATH) as f:
        watchlist = json.load(f)

    if not watchlist:
        return []

    hits = []
    for item in watchlist:
        sku = str(item["sku"])
        name = item.get("name", sku)

        # Get most recent price_history entry for this SKU
        row = conn.execute(
            """
            SELECT regular_price, current_price, offer_end_date, product_url
            FROM price_history
            WHERE item_sku = ?
            ORDER BY checked_at DESC
            LIMIT 1
            """,
            (sku,),
        ).fetchone()

        if not row:
            print(f"  ℹ️  [{sku}] No price data yet — run price_check.py first")
            continue

        regular_price, current_price, offer_end_date, product_url = row

        # Sale = Costco shows a strikethrough regular_price AND current offer is lower
        if regular_price and current_price and current_price < regular_price:
            savings = round(regular_price - current_price, 2)
            hits.append({
                "sku":           sku,
                "item_name":     name,
                "regular_price": regular_price,
                "sale_price":    current_price,
                "savings":       savings,
                "offer_end_date": offer_end_date,
                "product_url":   product_url,
            })
            print(
                f"  🛒 [{sku}] {name}: ${current_price:.2f} "
                f"(was ${regular_price:.2f}, save ${savings:.2f})"
            )
        else:
            print(f"  —  [{sku}] {name}: ${current_price:.2f} — not on sale")

    return hits
