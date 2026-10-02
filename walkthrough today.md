# Restoration Walkthrough: ERPNext v15 Docker Environment

Historical notes from restoring a production-aligned ERPNext v15 environment (moved away from an unstable v16 image and removed a temporary gunicorn workaround).

## Key Accomplishments

### 1. Custom Docker Image Build
- **Base Image**: Switched to `frappe/erpnext:v15` (stable v15 with Python 3.11).
- **Baked-in Apps**: Included `hrms` (v15.49.2) and the custom `pu_foam_master` app.
- **Dependency Fix**: Verified `orjson` is natively available, allowing the real `gunicorn` to start without errors.

### 2. Orchestration Stabilization
- **Version Lock**: Updated the external `frappe_docker` compose file to point services at a pinned ERPNext v15 image instead of a floating v16 tag.
- **Hack Removal**: Confirmed `/home/frappe/frappe-bench/env/bin/gunicorn` is the authentic binary, not a shell script.

### 3. Site Migration & App Configuration
- **Database Migration**: Successfully ran `bench migrate` to align the schema with v15 requirements.
- **App Installation**: Confirmed `pu_foam_master` is registered in `apps.txt` and the database.
- **Workspace Deployment**: Executed the workspace setup so the **PU Foam Master** Desk sidebar is visible.

## Verification Results

### Container Status
```bash
$ docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
```

### Connectivity Test
The site should serve the ERPNext login page on the published port (for example `http://localhost:8000` or `http://localhost:8080` depending on compose).

### Workspace Persistence
The **PU Foam Master** workspace is created by `pu_foam_master.setup_workspace.create_workspace` on install/migrate. An older Desk workspace label is deleted on migrate if it still exists.

> [!IMPORTANT]
> The operational target described here is **ERPNext v15**. Upgrading to v16 should be planned as a deliberate image/base upgrade, not a casual tag bump.

> [!TIP]
> Use your compose logs for the backend/web service to monitor application-level warnings during normal operation.
