#!/usr/bin/env bash
# Happifoam legacy archive only — port 8090 (ERPNext uses 8000 in Docker).
set -euo pipefail
cd "$(dirname "$0")"
PORT="${ARCHIVE_PORT:-8090}"
echo "Legacy ERP archive: http://127.0.0.1:${PORT}/login"
echo "(PU Foam ERPNext stays on http://localhost:8000)"
exec php artisan serve --host=127.0.0.1 --port="${PORT}"
