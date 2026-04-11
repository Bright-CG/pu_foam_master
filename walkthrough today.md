# Restoration Walkthrough: ERPNext v15 Docker Environment

We have successfully performed a permanent restoration of the production-aligned ERPNext v15 environment, moving away from the unstable v16.11.0 image and removing the "fake gunicorn" hack.

## Key Accomplishments

### 1. Custom Docker Image Build
- **Base Image**: Switched to `frappe/erpnext:v15` (stable v15 with Python 3.11).
- **Baked-in Apps**: Included `hrms` (v15.49.2) and the custom `happifoam_manufacturing` app directly into the image.
- **Dependency Fix**: Verified `orjson` is natively available, allowing the real `gunicorn` to start without errors.

### 2. Orchestration Stabilization
- **Version Lock**: Updated `/Users/devoption/erpnext-docker/frappe_docker/pwd.yml` to point all 8 services to `happifoam-erpnext:v15` instead of the floating v16 tag.
- **Hack Removal**: Confirmed `/home/frappe/frappe-bench/env/bin/gunicorn` is now the authentic binary, not a shell script.

### 3. Site Migration & App Configuration
- **Database Migration**: Successfully ran `bench migrate` to align the schema with v15 requirements.
- **App Installation**: Confirmed `happifoam_manufacturing` is registered in `apps.txt` and the database.
- **Workspace Deployment**: Executed the `create_workspace` script to ensure the **Happifoam Manufacturing** Desk sidebar is visible.

## Verification Results

### Container Status
```bash
$ docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
NAMES                          STATUS             IMAGE
frappe_docker-frontend-1       Up 15 minutes      happifoam-erpnext:v15
frappe_docker-backend-1        Up 15 minutes      happifoam-erpnext:v15
...
```

### Connectivity Test
The site is reachable and serving the ERPNext login page:
```bash
$ curl -I http://localhost:8080
HTTP/1.1 200 OK
X-Page-Name: login
```

### Workspace Persistence
The `Happifoam Manufacturing` workspace is confirmed in the database and should survive container restarts.

> [!IMPORTANT]
> The environment is now version-locked to **v15**. To upgrade to v16 in the future, you should update the `Containerfile` base image and rebuild, rather than changing the `pwd.yml` tag directly.

> [!TIP]
> Use `docker compose -f pwd.yml logs -f backend` to monitor for any application-level warnings during normal operation.
