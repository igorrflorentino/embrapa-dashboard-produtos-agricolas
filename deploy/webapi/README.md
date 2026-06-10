# deploy/webapi — React SPA + Flask REST Cloud Run Service

The Dash→React migration's deploy target. Serves the built React SPA **and** the
`/api` JSON endpoints from one origin (one service, one IAP, no CORS) via
gunicorn → `embrapa_commodities.webapi.app:app`.

Replaces the Dash image (`deploy/dashboard/`) **in place** at cutover: the
`deploy.sh` defaults to the same service (`embrapa-dashboard`), the same runtime
SA (`sa-web-dashboard-prod`), and the same PRIVATE + IAP posture. The service URL
and IAP grants are unchanged — only the served app changes.

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | 3-stage build: node (build `frontend/dist`) → uv (`--extra webapi`) → runtime (gunicorn + `SPA_DIST_DIR`) |
| `cloudbuild.yaml` | Cloud Build config (explicit Dockerfile path, repo-root context) |
| `deploy.sh` | Build via Cloud Build + `gcloud run deploy` (private), env allowlist, prod datasets forced |

## Deploy

```bash
make webapi-deploy          # or: bash deploy/webapi/deploy.sh
```

Prereqs: gcloud authenticated; `run`/`cloudbuild`/`artifactregistry` APIs enabled;
the runtime SA provisioned (`make iam-grant`). The build needs `frontend/package-lock.json`
(committed) for `npm ci`.

## Notes

- **No dash/plotly** in the image: the `webapi` extra is flask + flask-caching +
  gunicorn. The analytical charts are client-side Plotly.js in the SPA.
- **`SPA_DIST_DIR=/app/frontend/dist`** is baked into the image; Flask serves the
  SPA for non-`/api` routes (client-side deep-links resolve to `index.html`).
- Same Pushdown model: parameterized BigQuery via the serving BFF, memoized by
  flask-caching; `WEB_CONCURRENCY=1` keeps the per-instance SimpleCache coherent.
- The old Dash deploy (`deploy/dashboard/`) is removed once the cutover is verified.
