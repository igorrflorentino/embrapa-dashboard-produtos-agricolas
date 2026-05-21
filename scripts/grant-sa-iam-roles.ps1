$PROJECT = "embrapa-dashboard-commodities"
$SA = "serviceAccount:sa-secret-reader-prod@embrapa-dashboard-commodities.iam.gserviceaccount.com"

gcloud config set account igorlopesc@gmail.com

gcloud projects add-iam-policy-binding $PROJECT --member=$SA --role="roles/bigquery.user"
gcloud projects add-iam-policy-binding $PROJECT --member=$SA --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding $PROJECT --member=$SA --role="roles/storage.objectViewer"
# serviceUsageConsumer grants serviceusage.services.use, required for GCS API calls.
# bigquery.user already includes this, but storage.objectViewer does not.
gcloud projects add-iam-policy-binding $PROJECT --member=$SA --role="roles/serviceusage.serviceUsageConsumer"

Write-Host "Done."
