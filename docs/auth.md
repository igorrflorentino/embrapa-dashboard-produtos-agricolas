# Dashboard auth — granting access to the Cloud Run URL

The Cloud Run service `embrapa-dashboard-commodities` is deployed with
`--no-allow-unauthenticated`. Hitting the URL with no credentials returns
`403 Forbidden`. To view the dashboard a principal must hold
`roles/run.invoker` on the service.

This is the URL-level access layer. The container's read access to BigQuery
is a separate concern, governed by the `dashboard-runtime` service account
documented in [`deploy/README.md`](../deploy/README.md#runtime-iam) and
[`iam_setup.md`](iam_setup.md).

## Why the service is private

The underlying data (IBGE SIDRA + BCB SGS) is public, but the *URL* is not,
because:

1. **Cost containment.** Every cold request triggers
   `SELECT * FROM gold.gold_commodity_matrix`. Open access invites scraped
   traffic that pins the service warm and racks up BigQuery scan costs
   billed to the project.
2. **Implicit-policy risk.** If an internal-only column (cost basis,
   draft figures, supplier names) ever lands in Gold, an open service
   exposes it on the next deploy with nothing in code review to catch it.
   Gating the URL forces an explicit grant for every viewer.

See [`audit_2026-05.md`](audit_2026-05.md) §1 for the original decision.

## Granting access

### A single user

```bash
PROJECT=$GCP_PROJECT_ID
REGION=us-central1
SERVICE=embrapa-dashboard-commodities
VIEWER_EMAIL=person@example.com

gcloud run services add-iam-policy-binding $SERVICE \
  --project=$PROJECT \
  --region=$REGION \
  --member="user:${VIEWER_EMAIL}" \
  --role="roles/run.invoker"
```

### A Google Group (preferred for teams)

A group binding scales to N viewers with one IAM change and survives staff
turnover — add/remove members in the Google Workspace admin console without
touching IAM.

```bash
gcloud run services add-iam-policy-binding $SERVICE \
  --project=$PROJECT \
  --region=$REGION \
  --member="group:embrapa-dashboard-viewers@example.com" \
  --role="roles/run.invoker"
```

### A service account (programmatic access)

For automated checks (smoke tests, Looker Studio, internal tooling):

```bash
gcloud run services add-iam-policy-binding $SERVICE \
  --project=$PROJECT \
  --region=$REGION \
  --member="serviceAccount:caller@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

## How a granted user actually opens the URL

Cloud Run does not perform a browser login flow itself. Two practical paths:

1. **CLI / curl.** Mint a short-lived identity token and pass it as a
   bearer header. The exact invocation depends on the account type:
   ```bash
   URL=$(gcloud run services describe $SERVICE \
           --project=$PROJECT --region=$REGION --format='value(status.url)')

   # User account (you, authenticated via `gcloud auth login`):
   #   Cloud Run whitelists gcloud's OAuth client ID — no --audiences needed.
   #   In fact, passing --audiences with a user account fails with
   #   "Invalid account type".
   curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" "$URL/_health"

   # Service account (CI, automation):
   #   Cloud Run validates the JWT `aud` strictly, so you MUST mint with the
   #   service URL as the audience.
   curl -H "Authorization: Bearer $(gcloud auth print-identity-token --audiences=$URL)" "$URL/_health"
   ```
   `scripts/dashboard_smoke.py` auto-detects the account type and picks the
   right invocation. Useful for the post-deploy gate from a developer
   machine or from CI.

2. **Browser.** Plain navigation to the `*.run.app` URL won't authenticate
   — gcloud doesn't have a browser session-cookie story for Cloud Run. The
   pragmatic options:
   - Front the service with **IAP** (Identity-Aware Proxy) via a load
     balancer; viewers sign in with Google and IAP forwards the identity.
     Requires provisioning an external HTTPS LB — not done today.
   - Use the [Cloud Run Proxy](https://cloud.google.com/sdk/gcloud/reference/run/services/proxy):
     `gcloud run services proxy $SERVICE --region=$REGION` opens a local
     `http://localhost:8080` tunnel authenticated as the developer.

If browser-shareable links are a hard requirement, plan an IAP rollout
before widening the viewer list.

## Revoking access

```bash
gcloud run services remove-iam-policy-binding $SERVICE \
  --project=$PROJECT \
  --region=$REGION \
  --member="user:${VIEWER_EMAIL}" \
  --role="roles/run.invoker"
```

Group memberships are revoked in Google Workspace; no IAM change needed.

## Auditing

```bash
# Who can currently invoke the service?
gcloud run services get-iam-policy $SERVICE \
  --project=$PROJECT --region=$REGION \
  --format=json | jq '.bindings[] | select(.role=="roles/run.invoker")'
```

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `403 Forbidden` from `curl $URL/_health` | Missing identity token | Add `-H "Authorization: Bearer $(gcloud auth print-identity-token)"` |
| `403` even with token | Caller lacks `roles/run.invoker` | Add the binding (see above) |
| `dashboard_smoke.py --url <prod>` fails after deploy | Smoke runs unauthenticated | Either grant the caller `roles/run.invoker` and inject the token, or run the smoke against the Cloud Run Proxy URL |
| Browser hangs on `*.run.app` | No browser SSO for raw Cloud Run | Use `gcloud run services proxy` or plan an IAP rollout |
