import sqlite3
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
import price_check

def mock_get_skus(*args, **kwargs):
    return [
        {"sku": "1001368", "item_name": "Kirkland Signature, Organic Quinoa, 4.5 lbs", "source": "watchlist"}
    ]

price_check.get_skus_to_check = mock_get_skus

print("Running strict matching test on known GOOD SKUs")
res = price_check.run(dry_run=True)
print("Test completed. Failed SKUs:", res['failed_skus'])
