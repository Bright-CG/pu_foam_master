#!/usr/bin/env bash
# Run as user happifoam. Requires PHP 8.3+ and Composer on PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${ROOT}/laravel_archive"

if [[ ! -f "${APP}/.env" ]]; then
  echo "Create ${APP}/.env from deploy/env.laravel.example first." >&2
  exit 1
fi

cd "${APP}"
composer install --no-dev --optimize-autoloader
php artisan key:generate --force
php artisan config:cache
php artisan route:cache
php artisan view:cache

chmod -R ug+rwx storage bootstrap/cache

# Nginx web root: /home/happifoam/olderp/public
ln -sfn "${APP}/public" "${ROOT}/public"

echo "Laravel ready. Nginx root: ${ROOT}/public"
