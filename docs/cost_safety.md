# Cost Safety — Budget Alerts and Quotas on GCP

Even running manually, **one misbehaving query** (a loop in a dashboard, a full-scan
without partition, an accidental full-refresh in prod) can generate an unexpected bill
within hours. This document lists the 2 cost guardrails that need to be
configured **once** in the Cloud Console — they are not code.

---

## 1. Monthly budget with alerts (3 minutes)

1. **Cloud Console → Billing → Budgets & alerts**
2. **Create budget**:
   - Name: `embrapa-commodities-monthly`
   - Projects: select `embrapa-dashboard-commodities`
   - Services: leave blank (covers everything in the project)
3. **Budget amount**:
   - Type: **Specified amount**
   - Target amount: **R$ 100/month** (suggested for academic use — the real
     pipeline costs cents per run; the headroom is protection against a bug)
4. **Threshold rules** (automatic emails):
   - **50%** of budget — initial alert
   - **90%** — serious concern
   - **100%** — turn off the terminal and investigate
5. **Notifications**:
   - Check **Email alerts to billing admins and users**
   - (Optional) Connect a Pub/Sub topic + Cloud Function if you want an
     **automatic kill-switch** that disables billing when it exceeds
     100% — overkill for the academic case.

> Budget alerts are **warnings**, not blocks. For a hard limit, see §2.

---

## 2. Custom quota: hard cap on BigQuery bytes (5 minutes)

Even with BI Engine active, queries that escape the cache (custom queries in
Looker, new joins) can scan several GB. Set a daily ceiling.

1. **Cloud Console → IAM & Admin → Quotas & System Limits**
2. Filter by: `bigquery.googleapis.com` + `Query usage per day per user`
3. **Edit quota**:
   - Set to: **100 GB / day** (suggested — a full Silver+Gold build
     scans ~400 MB in the current state, so 100 GB covers ~250 builds/day)
4. **Submit**

When the limit is reached, BigQuery starts rejecting new queries until midnight
UTC with `quotaExceeded`. **No billing surprise.**

---

## 3. (Optional) Authorized View for external readers

If the dashboard is shared with third parties who should **not** incur
project costs:

1. Create a `gold_readonly` dataset in a separate project (`embrapa-readers`).
2. **Create authorized view** pointing to `gold.gold_pevs_production`.
3. Share that separate project with the readers.

The readers consume from their own project; yours stays isolated.

---

## 4. Quick check of current spend

```bash
gcloud billing accounts list
gcloud billing projects describe embrapa-dashboard-commodities
```

Or via the Console: **Billing → Reports** — cost-by-SKU chart for the last
30 days. Under normal conditions the project should stay < R$ 5/month (BigQuery
storage + BI Engine + GCS Standard ⇒ Coldline).
