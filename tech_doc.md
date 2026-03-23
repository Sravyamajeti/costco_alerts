# Costco Price Protection & Watchlist Agent — Technical Documentation

## 1. Overview

This agent automates two things defined in the PRD:

1. **Price Protection** — Monitors items you bought within the last 30 days. If any prices drop, all affected items are bundled into **one daily digest email** with savings amounts and claim deadlines.
2. **Watchlist** — Monitors recurring staple items (e.g., Kirkland Coffee, Organic Eggs) and alerts you whenever they go on sale.

**Scope:** Newark, CA Costco warehouse (#1660) only. Online purchases and other warehouses are excluded.

**Cost:** $0. Everything runs on free tiers (GitHub Actions, SQLite, Resend API).

---

## 2. Tech Stack

| Layer | Tool | Why / Cost |
|---|---|---|
| Language | Python 3.11 | Stdlib-heavy; minimal dependencies |
| Database | SQLite (`data/costco.db`) | File-based, zero cost, no server needed |
| Scheduling | GitHub Actions cron | Free (2,000 min/month) |
| Web Scraping | `requests` + `BeautifulSoup4` | Parse Costco.com product pages |
| Email | Resend API (free tier) | 3,000 emails/month free |
| Data Parsing | Python stdlib `csv`, `sqlite3` | No pandas needed |

---

## 3. Project Structure

```
costco/
├── prd.md                        # Product requirements
├── past_data.csv                 # Initial Costco order export (and future ones)
├── watchlist.json                # User-managed staple items to monitor
├── requirements.txt
├── .env.example                  # Template for local secrets
├── data/
│   └── costco.db                 # SQLite DB (gitignored, rebuilt on every run)
├── src/
│   ├── ingest.py                 # CSV → DB loader
│   ├── price_check.py            # Scrapes Costco.com for current prices
│   ├── watchlist.py              # Compares today's prices against normal_price
│   ├── notifier.py               # Sends HTML emails via Resend API
│   └── agent.py                  # Orchestrator — runs all daily jobs
└── .github/
    └── workflows/
        └── daily_check.yml       # GitHub Actions cron schedule
```

---

## 4. Database Schema (SQLite)

**File:** `data/costco.db` — gitignored. Rebuilt fresh on every GitHub Actions run from committed CSVs.

### `purchases`

```sql
CREATE TABLE purchases (
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
    UNIQUE(raw_receipt_hash, item_sku)  -- one line per item per receipt
);
CREATE INDEX idx_sku_date ON purchases(item_sku, transaction_date);
```

### `price_history`

```sql
CREATE TABLE price_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    item_sku       TEXT NOT NULL,
    checked_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    regular_price  REAL,   -- Costco's listed regular/non-sale price (strikethrough on page)
    current_price  REAL,   -- Costco's current offer/member price
    offer_end_date DATE,   -- Costco's listed "offer valid" end date, scraped from product page
    product_url    TEXT
);
CREATE INDEX idx_ph_sku ON price_history(item_sku);
```

### `watchlist` *(optional — JSON file is the primary source)*

```sql
CREATE TABLE watchlist (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    item_sku  TEXT UNIQUE NOT NULL,
    item_name TEXT,
    added_at  DATE DEFAULT CURRENT_DATE
);
```

---

## 5. Data Flow

```
past_data.csv  ──►  ingest.py  ──►  purchases table
                                          │
                        ┌─────────────────┘
                        ▼
                  price_check.py  ──►  Costco.com (scrape)  ──►  price_history table
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
     Price Protection          watchlist.py  ◄──  watchlist.json
     Logic (agent.py)          Sale Logic
             │                     │
             └──────────┬──────────┘
                        ▼
                   notifier.py
                        │
                        ▼
                  Your Email Inbox
```

---

## 6. Component Details

### 6.1 CSV Ingestion (`src/ingest.py`)

**Input:** Any `.csv` file in the repo root (Costco order export format).

**Filter rules applied during ingestion:**
- `receipt_type == "warehouse"` — exclude gas station purchases
- `warehouse_info` contains `NEWARK` — Newark #1660 only
- `item_sku` is non-empty and non-negative — skip refund/adjustment rows
- `raw_receipt_hash` not already in DB — dedup across multiple CSV imports

**CSV column → DB column mapping:**

| CSV Column | DB Column | Notes |
|---|---|---|
| `item_sku` | `item_sku` | Primary identifier for scraping |
| `item_actual_name` | `item_full_name` | Full display name |
| `item_name` | `item_name` | Short name |
| `unit_price` | `unit_price` | Price paid at checkout |
| `transaction_date` | `transaction_date` | Used for 30-day window |
| `warehouse_info` | `warehouse` | Filtered to NEWARK (#1660) |
| `instant_savings` | `instant_savings` | Discount applied at checkout |
| `raw_receipt_hash` | `raw_receipt_hash` | Dedup key per receipt line |

**CLI usage:**
```bash
python src/ingest.py --csv past_data.csv
# Output: "Inserted 52 rows, skipped 0 duplicates"
```

---

### 6.2 Price Scraping (`src/price_check.py`)

**Scope:** Only SKUs from `purchases` where `transaction_date >= today - 30 days`.

**Strategy:** Use the item SKU directly in Costco's search URL:
```
https://www.costco.com/s?keyword=<SKU>
```
Example: SKU `796993` → `https://www.costco.com/s?keyword=796993` → resolves to the correct product page.

Parse both prices from the product page:
```python
# Current offer/member price (always present)
current_price = soup.find("span", {"automation-id": "unitPrice"})

# Regular price — only present when item is on sale (shown as strikethrough)
regular_price = soup.find("div", class_="price-was")  # or similar strikethrough element
```

Both `current_price` and `regular_price` (if found) are stored in `price_history`. When `regular_price` is present and `current_price < regular_price`, Costco is actively running a sale on that item.

**Rate limiting mitigation:**
- 30-second fixed delay between each request (`time.sleep(30)`)
- Rotate `User-Agent` headers (Chrome/Firefox strings)
- At most ~50 unique SKUs per day (typical 30-day window)

**Failure handling:**
- HTTP 429, 404, or parse error → skip SKU, log warning
- Price of `0` or `None` → treated as "unable to fetch", skipped
- If **all** SKU fetches fail (total scraper blockage), or if failures exceed a threshold (e.g., >50% of SKUs fail), `notifier.py` sends a separate **scraper failure alert email**:

```
Subject: ⚠️ Costco Agent: Scraper failed on [Date]

The daily price check could not fetch prices today.
Failed SKUs: 42 / 50
Likely cause: Costco rate-limiting or page structure change.
Check GitHub Actions logs for details.
```

---

### 6.3 Price Protection Logic (`src/agent.py`)

```python
for sku in recent_purchases:  # last 30 days
    purchase_price = db.get_min_price_paid(sku)
    current_price  = price_history.get_latest(sku)
    if current_price and current_price < purchase_price:
        alerts.append({
            "item_name":   sku.item_full_name,
            "old_price":   purchase_price,
            "new_price":   current_price,
            "savings":     purchase_price - current_price,
            "deadline":    price_history.offer_end_date,  # scraped from Costco's listed offer valid date
            "product_url": price_history.product_url
        })
```

---

### 6.4 Watchlist (`watchlist.json` + `src/watchlist.py`)

User-maintained JSON file in the repo root — **only SKU and name, no prices**:
```json
[
  { "sku": "1068083", "name": "Kirkland Organic Eggs 24-ct" },
  { "sku": "796993",  "name": "Organic Avocado 6-ct" },
  { "sku": "1001368", "name": "KS Organic Quinoa 4.5 lb" }
]
```

**Sale detection logic in `watchlist.py`:**
```python
for item in watchlist:
    ph = price_history.get_latest(item["sku"])
    # Costco shows a strikethrough regular_price alongside a lower current_price when on sale
    if ph.regular_price and ph.current_price and ph.current_price < ph.regular_price:
        hits.append({
            "item_name":    item["name"],
            "regular_price": ph.regular_price,
            "sale_price":    ph.current_price,
            "savings":       ph.regular_price - ph.current_price,
            "offer_end_date": ph.offer_end_date,
            "product_url":   ph.product_url
        })
```

No user-maintained prices needed — Costco's own page is the source of truth.

To add a new item to the watchlist: edit `watchlist.json` with the SKU (from the Costco product URL) and commit.

---

### 6.5 Email Notifier (`src/notifier.py`)

Sends **one consolidated daily digest email** via the **Resend API** (free tier: 3,000 emails/month).

> [!NOTE]
> Only **one email per day** is sent, regardless of how many items have price drops or watchlist hits. All findings are bundled together into a single digest. If there are no price drops and no watchlist sales that day, no email is sent.

**Daily Digest Email:**
```
Subject: 🛒 Costco Daily Alert — [N] price drops, [M] watchlist sales (Mar 22)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 PRICE PROTECTION (N items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Kirkland Signature Olive Oil 2L
  You paid: $19.99 on Mar 5
  Now: $14.99  (↓ $5.00 off)
  ⚠️ Offer valid until: Apr 15
  → View on Costco.com

Organic Avocados 6-ct
  You paid: $7.99 on Mar 10
  Now: $5.99  (↓ $2.00 off)
  ⚠️ Offer valid until: Apr 15
  → View on Costco.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛒 WATCHLIST SALES (M items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Kirkland Organic Eggs 24-ct
  Normal: $7.69 → Today: $5.99  (↓ $1.70 off)
  → View on Costco.com
```

**Sending logic in `agent.py`:**
```python
price_alerts   = get_price_protection_alerts()   # list of all drops
watchlist_hits = get_watchlist_sales()            # list of all sale items

if price_alerts or watchlist_hits:
    notifier.send_daily_digest(price_alerts, watchlist_hits)
# → exactly one email, or zero if nothing found
```

---

## 7. Environment Setup

### Local Development

Create a `.env` file (not committed to git):
```bash
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
NOTIFY_EMAIL=your.email@gmail.com
```

> [!IMPORTANT]
> **How to get a free Resend API key:**
> 1. Go to [resend.com](https://resend.com) → Sign up (free)
> 2. Go to **API Keys** → Create API Key → copy it
> 3. For the sender address, use Resend's shared test domain (`onboarding@resend.dev`) — no domain setup required for personal use

### GitHub Actions Secrets

In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret Name | Value |
|---|---|
| `RESEND_API_KEY` | Your Resend API key |
| `NOTIFY_EMAIL` | Email address to receive alerts |

---

## 8. GitHub Actions Workflow

**File:** `.github/workflows/daily_check.yml`

```yaml
name: Daily Price Check

on:
  schedule:
    - cron: '0 14 * * *'   # 7 AM PST (UTC-7) every day
  workflow_dispatch:         # allows manual trigger from GitHub UI

jobs:
  price-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Ingest all CSVs
        run: |
          for csv in *.csv; do
            python src/ingest.py --csv "$csv"
          done

      - name: Run agent
        env:
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          NOTIFY_EMAIL: ${{ secrets.NOTIFY_EMAIL }}
        run: python src/agent.py
```

**Resource usage:** Each run takes ~25–30 min (30s delay × ~50 SKUs) → ~900 min/month → within 2,000 min/month free limit.

---

## 9. Adding a New Purchase

When you make a new Costco trip:
1. Go to **Costco.com → Orders & Purchases** → export the receipt as CSV.
2. Save the CSV to `/Users/sravya/costco/` (any filename, e.g., `march_2026.csv`).
3. Commit and push to GitHub.
4. GitHub Actions will automatically ingest it on the next run. Dedup logic ensures no double-counting.

---

## 10. Dependencies (`requirements.txt`)

```
requests==2.31.0
beautifulsoup4==4.12.3
python-dotenv==1.0.1
resend==2.0.0
```

Only 4 external packages. `sqlite3`, `csv`, `json`, `datetime`, `smtplib` are all Python stdlib.

---

## 11. Verification Steps

**1. Local ingestion test**
```bash
cd /Users/sravya/costco
pip install -r requirements.txt
python src/ingest.py --csv past_data.csv
sqlite3 data/costco.db "SELECT COUNT(*) FROM purchases;"
# Expected: count of Newark warehouse rows in the CSV
```

**2. Price check dry run (single SKU)**
```bash
python src/price_check.py --sku 796993 --dry-run
# Expected: prints current Costco price for Organic Avocados
```

**3. Notifier test**
```bash
RESEND_API_KEY=re_xxx NOTIFY_EMAIL=you@gmail.com python src/notifier.py --test
# Expected: sends a test email with dummy price-drop data
```

**4. Full agent dry run**
```bash
python src/agent.py --dry-run
# Expected: prints what emails WOULD be sent without actually sending them
```

**5. GitHub Actions manual trigger**
- Push code to GitHub → go to **Actions** tab → `Daily Price Check` → `Run workflow`.
- Verify green checkmark and no errors in logs.

---

## 12. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Costco may block scrapers | Price check may fail | Email alert sent if scraper fails; retries next day |
| No official Costco price API | HTML structure can change | Monitor parse errors in GH Actions logs |
| GitHub Actions DB is ephemeral | DB rebuilt on every run | CSVs are the source of truth; DB is derived |
| Newark warehouse only | No cross-store price comparison | By design per PRD |
| Email only (no SMS/push) | Requires checking inbox | Resend is reliable; emails sent daily |
| 30-day claim must be done in-store | Manual action required | Email contains exact deadline date |
