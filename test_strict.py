import sqlite3
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
import price_check

# Mock the get_skus_to_check to only return our tricky tests
def mock_get_skus(*args, **kwargs):
    return [
        {"sku": "4296", "item_name": "Kirkland Signature Organic Extra Virgin Olive Oil, 2 L", "source": "watchlist"},
        {"sku": "512515", "item_name": "Kirkland Signature Flushable Wipes, 632-count", "source": "watchlist"},
        {"sku": "2619", "item_name": "Kirkland Signature Bath Tissue, 2-Ply, 425 sheets, 30 rolls", "source": "watchlist"},
    ]

price_check.get_skus_to_check = mock_get_skus

print("Running strict matching test on known bad SKUs")
res = price_check.run(dry_run=True)
print("Test completed. Failed SKUs:", res['failed_skus'])
