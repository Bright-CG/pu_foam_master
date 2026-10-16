#!/usr/bin/env bash
# Full archive scrape pipeline. Logs to data/logs/vps_scrape.log (tee keeps console output too).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${ROOT}/venv/bin/python"
LOG_DIR="${ROOT}/data/logs"
MAIN_LOG="${LOG_DIR}/vps_scrape.log"

mkdir -p "${LOG_DIR}"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing ${PYTHON} — run deploy/install_scraper.sh" >&2
  exit 1
fi

if [[ ! -f "${ROOT}/scraper/.env" ]]; then
  echo "Missing ${ROOT}/scraper/.env — copy scraper/.env.example and set ERP_PASSWORD" >&2
  exit 1
fi

export SCRAPER_ENV_FILE="${ROOT}/scraper/.env"

cd "${ROOT}/scraper"
exec "${PYTHON}" -u run_vps_scrape.py "$@" 2>&1 | tee -a "${MAIN_LOG}"
