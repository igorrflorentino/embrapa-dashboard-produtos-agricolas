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
| `deploy.sh` | Build via Cloud Build + `gcloud run deploy` (private), env allowlist, prod datasets forced. `WEBAPI_SKIP_BUILD=1` deploys a pre-built image instead of rebuilding |

## Deploy

```bash
make webapi-deploy          # or: bash deploy/webapi/deploy.sh
```

Builds from source (Cloud Build) and deploys. Prereqs: gcloud authenticated;
`run`/`cloudbuild`/`artifactregistry` APIs enabled; the runtime SA provisioned
(`make iam-grant`). The build needs `frontend/package-lock.json` (committed) for `npm ci`.

## Releases — build once (CI), deploy later (no rebuild)

`.github/workflows/release.yml` decouples **build** from **deploy**: it bakes a
versioned, immutable image into Artifact Registry on every release, so a later
deploy is just pointing Cloud Run at that tag — no rebuild.

**Cut a release** (builds + pushes `…/embrapa-dashboard:vX.Y.Z` + `:latest`, then
creates the GitHub Release whose body is the curated `CHANGELOG.md` `## [vX.Y.Z]`
section + the deployable-image ref + an auto-generated PR appendix — so add the
version's CHANGELOG entry before tagging):

```bash
git tag v1.2.3 && git push origin v1.2.3      # or publish a Release in the GitHub UI
```

(`workflow_dispatch` on the "Release image" workflow builds an ad-hoc tag too —
no `:latest`, no Release.)

**Deploy that pre-built image** (skips the build, verifies the tag exists, deploys):

```bash
WEBAPI_SKIP_BUILD=1 WEBAPI_TAG=v1.2.3 bash deploy/webapi/deploy.sh
```

One-time GCP setup (a least-privilege release SA with Artifact Registry write,
bound to the existing WIF pool) is documented in the header of `release.yml`.
It reuses the `GCP_PROJECT_ID` / `GCP_WIF_PROVIDER` repo vars from
`dbt-build-prod.yml` and adds `GCP_RELEASE_SERVICE_ACCOUNT`.

## Notes

- **No dash/plotly** in the image: the `webapi` extra is flask + flask-caching +
  gunicorn. The analytical charts are client-side Plotly.js in the SPA.
- **`SPA_DIST_DIR=/app/frontend/dist`** is baked into the image; Flask serves the
  SPA for non-`/api` routes (client-side deep-links resolve to `index.html`).
- Same Pushdown model: parameterized BigQuery via the serving BFF, memoized by
  flask-caching; `WEB_CONCURRENCY=1` keeps the per-instance SimpleCache coherent.
- The old Dash deploy (`deploy/dashboard/`) is removed once the cutover is verified.
