#!/usr/bin/env bash
# Run as user happifoam from /home/happifoam/olderp
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ROOT}/venv"

python3 -m venv "${VENV}"
"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install -r "${ROOT}/scraper/requirements.txt"
"${VENV}/bin/python" "${ROOT}/scraper/db.py"

if [[ ! -f "${ROOT}/scraper/.env" ]]; then
  cp "${ROOT}/scraper/.env.example" "${ROOT}/scraper/.env"
  chmod 640 "${ROOT}/scraper/.env"
  echo "Created ${ROOT}/scraper/.env — edit ERP credentials before scraping."
fi

mkdir -p "${ROOT}/data/logs" "${ROOT}/data/exports"
echo "Scraper venv ready: ${VENV}"
