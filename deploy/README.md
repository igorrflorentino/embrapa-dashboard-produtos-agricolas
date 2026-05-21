# Deploying the Embrapa Commodities dashboard to Cloud Run

The dashboard is a Dash Plotly app that loads `gold.gold_commodity_matrix`
into a pandas DataFrame at boot and serves the in-memory snapshot until the
TTL expires (default 6 h) or the container is restarted.

## Prerequisites

- A GCP project that already runs the ingestion / dbt pipeline (so
  `gold.gold_commodity_matrix` exists).
- `gcloud` CLI installed and authenticated against that project.
- A runtime service account for the dashboard with the IAM roles below.

## Runtime IAM

Create a dedicated service account so the dashboard cannot do more than read
the Gold table:

```bash
SA=dashboard-runtime
PROJECT=$GCP_PROJECT_ID
gcloud iam service-accounts create $SA \
  --project=$PROJECT \
  --display-name="Embrapa Commodities Dashboard runtime"

# Grant read on the Gold dataset only (not the whole project).
bq add-iam-policy-binding \
  --member="serviceAccount:${SA}@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer" \
  "${PROJECT}:gold"

# Job-running permission lives at project level.
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA}@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

## Deploy

From the repo root:

```bash
gcloud run deploy embrapa-commodities-dashboard \
  --source . \
  --region us-central1 \
  --service-account dashboard-runtime@$GCP_PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars GCP_PROJECT_ID=$GCP_PROJECT_ID,BQ_GOLD_DATASET=gold,BQ_LOCATION=US \
  --allow-unauthenticated \
  --memory 1Gi --cpu 1 \
  --min-instances 0 --max-instances 5 \
  --port 8080
```

Cloud Run picks up `Dockerfile` automatically when present. The
`Makefile` target `make dashboard-deploy` wraps this command and reads
`GCP_PROJECT_ID` / `BQ_LOCATION` from the environment.

## Verify

```bash
URL=$(gcloud run services describe embrapa-commodities-dashboard \
        --region us-central1 --format='value(status.url)')
curl -fsS "$URL/_health"
open "$URL"
```

The first request will issue one BigQuery query (`SELECT * FROM
gold.gold_commodity_matrix`) — expected to take 1–3 s on a cold container.
Subsequent navigation and filter changes are served from the in-memory
snapshot.

## Local container test

```bash
make dashboard-build
docker run --rm -p 8080:8080 \
  -v ~/.config/gcloud:/root/.config/gcloud \
  -e GCP_PROJECT_ID=$GCP_PROJECT_ID \
  -e BQ_GOLD_DATASET=gold \
  embrapa-dashboard:local
```

Open <http://localhost:8080>. The mounted `gcloud` config provides
Application Default Credentials so BigQuery queries authenticate locally.
