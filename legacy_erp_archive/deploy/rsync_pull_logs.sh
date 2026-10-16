#!/usr/bin/env bash
# Pull scrape logs and ERPNext export CSVs from VPS to your Mac.
# Usage: ./rsync_pull_logs.sh happifoam@SERVER_IP
set -euo pipefail

REMOTE="${1:?Usage: $0 happifoam@host}"
REMOTE_PATH="${REMOTE_PATH:-/home/happifoam/olderp}"
SSH_PORT="${SSH_PORT:-2222}"
LOCAL="$(cd "$(dirname "$0")/.." && pwd)"
RSYNC_SSH="ssh -p ${SSH_PORT}"

mkdir -p "${LOCAL}/data/logs" "${LOCAL}/data/exports"

rsync -avz --progress -e "${RSYNC_SSH}" \
  "${REMOTE}:${REMOTE_PATH}/data/logs/" "${LOCAL}/data/logs/"

rsync -avz --progress -e "${RSYNC_SSH}" \
  "${REMOTE}:${REMOTE_PATH}/data/exports/" "${LOCAL}/data/exports/" || true

rsync -avz --progress -e "${RSYNC_SSH}" \
  "${REMOTE}:${REMOTE_PATH}/data/gl_inquiry_run.log" "${LOCAL}/data/" 2>/dev/null || true

echo "Pulled logs to ${LOCAL}/data/logs/"
