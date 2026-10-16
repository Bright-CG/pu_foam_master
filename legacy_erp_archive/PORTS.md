# Local URLs — do not mix with PU Foam ERPNext

| Application | URL | How to start |
|-------------|-----|--------------|
| **PU Foam ERPNext** (Frappe Desk) | **http://localhost:8000** | Docker: `devcontainer-example-frappe-1` (frappe_docker) |
| **Happifoam legacy archive** (Laravel) | **http://127.0.0.1:8090** | `cd laravel_archive && ./serve.sh` |

**Never run `php artisan serve` on port 8000** — that steals ERPNext on macOS because both bind `localhost:8000`.

Legacy archive login: see `laravel_archive/.env` (`AUTH_ARCHIVE_USER` / `AUTH_ARCHIVE_PASS`).
