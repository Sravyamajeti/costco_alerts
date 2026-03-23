"""
src/ingest.py  —  CSV → SQLite loader

Usage:
    python src/ingest.py --csv past_data.csv
    python src/ingest.py --csv march_2026.csv

Filters applied:
  - receipt_type == "warehouse"
  - warehouse_info contains "NEWARK" (case-insensitive)
  - item_sku non-empty and castable to positive integer
  - raw_receipt_hash not already in DB (dedup)
"""

import argparse
import csv
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "costco.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS purchases (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number     TEXT,
            receipt_id       TEXT,
            transaction_date DATE NOT NULL,
            warehouse        TEXT,
            item_sku         TEXT NOT NULL,
            item_name        TEXT,
            item_full_name   TEXT,
            unit_price       REAL NOT NULL,
            quantity         INTEGER DEFAULT 1,
            instant_savings  REAL DEFAULT 0,
            raw_receipt_hash TEXT,
            UNIQUE(raw_receipt_hash, item_sku)  -- dedup: one line per item per receipt
        );

        CREATE INDEX IF NOT EXISTS idx_sku_date
            ON purchases(item_sku, transaction_date);

        CREATE TABLE IF NOT EXISTS price_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            item_sku       TEXT NOT NULL,
            checked_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            regular_price  REAL,
            current_price  REAL,
            offer_end_date DATE,
            product_url    TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ph_sku
            ON price_history(item_sku);

        CREATE TABLE IF NOT EXISTS watchlist (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            item_sku  TEXT UNIQUE NOT NULL,
            item_name TEXT,
            added_at  DATE DEFAULT CURRENT_DATE
        );
    """)
    conn.commit()


def is_valid_sku(sku: str) -> bool:
    """SKU must be a non-empty string that looks like a positive number."""
    try:
        return sku.strip() != "" and int(sku.strip()) > 0
    except ValueError:
        return False


def ingest_csv(csv_path: str, conn: sqlite3.Connection) -> tuple[int, int]:
    inserted = 0
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # --- Filter 1: warehouse receipts only ---
            if row.get("receipt_type", "").strip().lower() != "warehouse":
                skipped += 1
                continue

            # --- Filter 2: Newark warehouse only ---
            warehouse = row.get("warehouse_info", "")
            if "NEWARK" not in warehouse.upper():
                skipped += 1
                continue

            # --- Filter 3: valid SKU ---
            sku = row.get("item_sku", "").strip()
            if not is_valid_sku(sku):
                skipped += 1
                continue

            # --- Filter 4: dedup via raw_receipt_hash ---
            raw_hash = row.get("raw_receipt_hash", "").strip()

            # Parse numeric fields safely
            def safe_float(val: str, default: float = 0.0) -> float:
                try:
                    return float(val.strip()) if val.strip() else default
                except ValueError:
                    return default

            def safe_int(val: str, default: int = 1) -> int:
                try:
                    return int(float(val.strip())) if val.strip() else default
                except ValueError:
                    return default

            unit_price = safe_float(row.get("unit_price", ""))
            quantity   = safe_int(row.get("quantity", ""))
            instant_savings = safe_float(row.get("instant_savings", ""))

            try:
                conn.execute(
                    """
                    INSERT INTO purchases
                        (order_number, receipt_id, transaction_date, warehouse,
                         item_sku, item_name, item_full_name,
                         unit_price, quantity, instant_savings, raw_receipt_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("order_number", "").strip(),
                        row.get("receipt_id", "").strip(),
                        row.get("transaction_date", "").strip(),
                        warehouse.strip(),
                        sku,
                        row.get("item_name", "").strip(),
                        row.get("item_actual_name", "").strip(),
                        unit_price,
                        quantity,
                        instant_savings,
                        raw_hash or None,
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # raw_receipt_hash already exists → duplicate row
                skipped += 1

    conn.commit()
    return inserted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a Costco CSV into the SQLite DB.")
    parser.add_argument("--csv", required=True, help="Path to the Costco order CSV file")
    args = parser.parse_args()

    csv_path = args.csv
    if not os.path.exists(csv_path):
        print(f"ERROR: File not found: {csv_path}")
        raise SystemExit(1)

    conn = get_connection()
    init_db(conn)

    inserted, skipped = ingest_csv(csv_path, conn)
    conn.close()

    print(f"✅ Ingested '{csv_path}': inserted {inserted} rows, skipped {skipped} rows.")


if __name__ == "__main__":
    main()
