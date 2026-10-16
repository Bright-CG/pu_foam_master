#!/usr/bin/env bash
# Upload code to VPS (does NOT overwrite server .env secrets).
# Usage: ./rsync_from_mac.sh happifoam@SERVER_IP
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 happifoam@host" >&2
  echo "Optional env: REMOTE_PATH=/home/happifoam/olderp SSH_PORT=2222" >&2
  exit 1
fi

REMOTE="${1}"
REMOTE_PATH="${REMOTE_PATH:-/home/happifoam/olderp}"
SSH_PORT="${SSH_PORT:-2222}"
LOCAL="$(cd "$(dirname "$0")/.." && pwd)"

RSYNC_SSH="ssh -p ${SSH_PORT}"

rsync -avz --progress -e "${RSYNC_SSH}" \
  --exclude 'scraper/.venv' \
  --exclude 'venv' \
  --exclude 'scraper/.env' \
  --exclude 'laravel_archive/.env' \
  --exclude 'laravel_archive/vendor' \
  --exclude 'laravel_archive/node_modules' \
  --exclude 'laravel_archive/storage/framework/sessions' \
  --exclude 'laravel_archive/storage/logs' \
  --exclude 'data/happifoam.db-wal' \
  --exclude 'data/happifoam.db-shm' \
  --exclude '.DS_Store' \
  "${LOCAL}/" "${REMOTE}:${REMOTE_PATH}/"

echo ""
echo "Synced to ${REMOTE}:${REMOTE_PATH} (port ${SSH_PORT})"
echo "On VPS: bash deploy/install_scraper.sh && bash deploy/install_laravel.sh"
