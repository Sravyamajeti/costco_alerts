# Costco Price Protection & Watchlist Agent

Automate the tracking of Costco purchases to claim 30-day price adjustments and monitor a "Watchlist" of recurring items for sales. This project specifically targets the Newark, California Costco warehouse for in-store pricing (not online).

## Features
- **Price Engine**: Daily checking of Costco.com Sameday product pages for price changes.
- **Purchase Tracking**: Ingests your purchase history via CSV and filters for items bought within the last 30 days.
- **Email Notifications**: Alerts you when an item you recently bought or a staple item drops in price, including details like Old Price, New Price, discount amount, and validity dates.

## Setup & Dependencies
To run this project, make sure you have Python installed and install the required dependencies:

```bash
pip install -r requirements.txt
```

### Dependencies Include:
- `seleniumbase`
- `setuptools`
- `beautifulsoup4` (BeautifulSoup)
- `python-dotenv`
- `resend` (for email notifications)

## Usage
1. Configure your `.env` file with necessary credentials (e.g., email id).
2. Ensure your purchase data CSV (e.g., `past_data.csv`) is properly formatted.
3. Run the tracking agent to check prices and dispatch notifications.
