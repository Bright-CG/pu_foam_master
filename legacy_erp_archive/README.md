# Happifoam Legacy ERP Archive

This folder contains the complete toolchain for extracting, archiving, and serving
historical data from the old **LeadingEdge Cloud ERP** (webERP) used by
**Solar Foam and Chemical Industries Nigeria Ltd** before the ERPNext cutover on **18-Oct-2021**.

## Folder Structure

```
legacy_erp_archive/
├── scraper/              # Python extraction scripts (runs against the live ERP)
│   ├── requirements.txt  # Python dependencies
│   ├── login.py          # Shared login session helper
│   ├── scrape_customers.py    # Extract all customer ledgers & transactions
│   ├── scrape_suppliers.py    # Extract all supplier ledgers & transactions
│   ├── scrape_gl.py           # Extract General Ledger accounts & journal entries
│   ├── scrape_inventory.py    # Extract stock items and BOMs
│   └── run_all.py             # Master runner — runs all scrapers in order
│
├── data/                 # Raw extracted data (created by scraper)
│   ├── happifoam.db      # SQLite database (canonical archive)
│   ├── customers/        # Per-customer CSV/JSON backups
│   ├── suppliers/        # Per-supplier CSV/JSON backups
│   ├── gl/               # GL CSV/JSON backups
│   └── inventory/        # Item & BOM CSV/JSON backups
│
└── laravel_archive/      # Self-hosted Laravel PHP archive viewer
    ├── app/
    ├── resources/views/
    ├── database/         # SQLite migrations and seeders
    └── ...
```

## Usage

### Step 1 — Run the scraper
```bash
cd scraper
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python run_all.py
```

If the network drops mid-run, webERP may return **“Error in form verification”** for some
customers. The old scraper treated that as “0 transactions”. Re-run only the failed ones:

```bash
python rescue_customers.py          # all customers logged with 0 transactions
python rescue_customers.py 448      # e.g. Margawa (customer 448)
```

The scraper uses **`requests` with keep-alive**, validates each inquiry page, and retries
with a fresh FormID / re-login when the session is stale.

### Step 2 — Seed the Laravel archive
```bash
cd ../laravel_archive
composer install
cp .env.example .env
php artisan key:generate
php artisan migrate
php artisan db:seed
php artisan serve
```

Visit `http://localhost:8000` and login with:
- **Username**: `admin`
- **Password**: `happifoam2021`

## Data Coverage (Cutover Date: 18-Oct-2021)

| Module | Description |
|---|---|
| Customer Ledger | All invoices, receipts, credit notes, allocations for 1,200+ customers |
| Supplier Ledger | All bills, payments, debit notes for 225 suppliers |
| General Ledger | Chart of Accounts, Journal Entries, Trial Balance, P&L, Balance Sheet |
| Inventory | 1,259 stock items with descriptions, units, and valuations |

---
*This folder is excluded from the main PU Foam repo via `.gitignore` to protect company data.*
