# Happifoam legacy archive on VPS (`olderp.happifoam.com`)

Isolated Linux user **`happifoam`** (no sudo). Base path **`/home/happifoam/olderp`**.

| Component | Path |
|-----------|------|
| SQLite database | `/home/happifoam/olderp/data/happifoam.db` |
| Scraper secrets | `/home/happifoam/olderp/scraper/.env` (`chmod 640`) |
| Python venv | `/home/happifoam/olderp/venv` |
| Scrape log (pull to Mac) | `/home/happifoam/olderp/data/logs/vps_scrape.log` |
| ERPNext import CSVs | `/home/happifoam/olderp/data/exports/` |
| Laravel web root | `/home/happifoam/olderp/public` → `laravel_archive/public` |

**ERPNext** on the same VPS uses a **different vhost** (e.g. `erp.happifoam.com`). This archive does not bind port 8000.

---

## What gets scraped (VPS fresh run)

`run_vps_scrape.py --fresh` clears scraped tables, then:

1. **Customer master** — roster + profile fields (`scrape_customers.py`)
2. **Customer statements** — `CustomerStatementBalances.php` → `customer_statement_lines`
3. **Supplier statements** — `SupplierStatementBalances.php` → `supplier_statement_lines`
4. **GL account inquiry** — `GLAccountInquiry.php` per account/month → `gl_account_inquiry_*`
5. **ERPNext exports** — `data/exports/erpnext_customers.csv`, `erpnext_suppliers.csv`

The Laravel site reads **`happifoam.db` directly** — no separate “import into archive DB” step.

**Not in the default pipeline:** inventory, trial-balance dashboard, old journal-only GL (`scrape_gl.py`). Those routes are hidden in the UI.

---

## 1. Push code from your Mac

SSH port **2222** (default in scripts):

```bash
chmod +x legacy_erp_archive/deploy/*.sh
SSH_PORT=2222 legacy_erp_archive/deploy/rsync_from_mac.sh happifoam@YOUR_SERVER_IP
```

**Excluded from rsync (never overwritten):** `scraper/.env`, `laravel_archive/.env`.

For a **fresh VPS scrape**, do **not** upload an old `data/happifoam.db` (omit it or delete on server before `--fresh`).

Optional: upload only code first; let the scraper create a new DB.

---

## 2. Setup on VPS (as `happifoam`)

```bash
cd /home/happifoam/olderp
bash deploy/install_scraper.sh
```

Edit LeadingEdge credentials:

```bash
nano scraper/.env   # ERP_USERNAME, ERP_PASSWORD, etc.
chmod 640 scraper/.env
```

Laravel:

```bash
cp deploy/env.laravel.example laravel_archive/.env
nano laravel_archive/.env   # APP_URL, AUTH_ARCHIVE_*, DB_DATABASE
bash deploy/install_laravel.sh
```

**Nginx + TLS** (root/admin once):

```bash
sudo cp /home/happifoam/olderp/deploy/nginx-olderp.conf.example \
  /etc/nginx/sites-available/olderp.happifoam.com
sudo ln -sf /etc/nginx/sites-available/olderp.happifoam.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d olderp.happifoam.com
```

DNS: `olderp.happifoam.com` → VPS IP.

---

## 3. Run scrape (from scratch)

**One-time full wipe + scrape** (recommended on VPS):

```bash
cd /home/happifoam/olderp
bash deploy/run_vps_scrape.sh --fresh
```

**Resume** after outage (no wipe):

```bash
bash deploy/run_vps_scrape.sh
```

**systemd** (admin installs unit; runs as `happifoam`):

```bash
sudo cp /home/happifoam/olderp/deploy/happifoam-scraper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now happifoam-scraper
```

Service uses `EnvironmentFile=/home/happifoam/olderp/scraper/.env` and appends to `data/logs/vps_scrape.log`.

Stop: `sudo systemctl stop happifoam-scraper`

---

## 4. Monitor & pull logs to Mac

On VPS:

```bash
bash deploy/check_scrape_progress.sh
tail -f data/logs/vps_scrape.log
```

From Mac:

```bash
SSH_PORT=2222 legacy_erp_archive/deploy/rsync_pull_logs.sh happifoam@YOUR_SERVER_IP
```

Also inspect `data/scrape_log` table errors via sqlite3 on VPS.

---

## 5. Archive website vs ERPNext data

| Need | Where |
|------|--------|
| View statements & GL | https://olderp.happifoam.com/login (`AUTH_ARCHIVE_*`) |
| Import **customers / suppliers** into ERPNext | `data/exports/erpnext_*.csv` after scrape (map columns in Data Import) |
| GL history in ERPNext | Separate COA mapping project; archive GL is for audit/reference |
| Opening AR/AP in ERPNext | Use closing balances from statement lines + ERPNext opening tools |

---

## 6. Optional: copy finished DB to Mac

```bash
rsync -avz -e "ssh -p 2222" \
  happifoam@YOUR_SERVER_IP:/home/happifoam/olderp/data/happifoam.db \
  legacy_erp_archive/data/
```

---

## Security

- Do not expose `/home/happifoam/olderp/data/` via HTTP (nginx serves only `public/`).
- Rotate LeadingEdge password; keep `scraper/.env` only on VPS.
- Strong `AUTH_ARCHIVE_PASS`; HTTPS only.
