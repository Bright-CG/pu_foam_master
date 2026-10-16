#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="${ROOT}/data/happifoam.db"
LOG="${ROOT}/data/logs/vps_scrape.log"

if [[ ! -f "${DB}" ]]; then
  echo "No database at ${DB}" >&2
  exit 1
fi

echo "=== Archive scrape progress ==="
sqlite3 "${DB}" "
SELECT 'Customers (master)' AS metric, COUNT(*) FROM customers;
SELECT 'Customer statement lines', COUNT(*) FROM customer_statement_lines;
SELECT 'Suppliers (master)', COUNT(*) FROM suppliers;
SELECT 'Supplier statement lines', COUNT(*) FROM supplier_statement_lines;
SELECT 'GL accounts complete (62 periods)', COUNT(*) FROM (
  SELECT account_code FROM gl_account_inquiry_periods
  GROUP BY account_code HAVING COUNT(*) >= 62
);
SELECT 'GL inquiry lines', COUNT(*) FROM gl_account_inquiry_lines;
SELECT 'Scrape errors (scrape_log)', COUNT(*) FROM scrape_log WHERE status = 'error';
"

if [[ -f "${LOG}" ]]; then
  echo ""
  echo "=== Last lines of vps_scrape.log ==="
  tail -8 "${LOG}"
fi
