#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="${ROOT}/data/happifoam.db"
LOG="${ROOT}/data/gl_inquiry_run.log"

if [[ ! -f "${DB}" ]]; then
  echo "No database at ${DB}" >&2
  exit 1
fi

echo "=== GL account inquiry progress ==="
sqlite3 "${DB}" "
SELECT 'Accounts with all 62 periods' AS metric,
       COUNT(*) AS value
FROM (
  SELECT account_code
  FROM gl_account_inquiry_periods
  GROUP BY account_code
  HAVING COUNT(*) >= 62
);
SELECT 'Total GL inquiry lines' AS metric, COUNT(*) AS value FROM gl_account_inquiry_lines;
SELECT 'Partial accounts (top 10)' AS '';
SELECT account_code, COUNT(*) AS periods_done
FROM gl_account_inquiry_periods
GROUP BY account_code
HAVING COUNT(*) < 62
ORDER BY periods_done DESC
LIMIT 10;
"

if [[ -f "${LOG}" ]]; then
  echo ""
  echo "=== Last log lines ==="
  tail -5 "${LOG}"
fi

echo ""
echo "CSV backups: $(find "${ROOT}/data/gl_inquiry" -name '*.csv' 2>/dev/null | wc -l | tr -d ' ') files in data/gl_inquiry/"
