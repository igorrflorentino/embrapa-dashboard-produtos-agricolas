# Cost Safety — Budget Alerts and Quotas on GCP

Even running manually, **one misbehaving query** (a loop in a dashboard, a full-scan
without partition, an accidental full-refresh in prod) can generate an unexpected bill
within hours. This document lists the 2 cost guardrails that need to be
configured **once** in the Cloud Console — they are not code.

---

## 0. Cost posture — scale to zero, ZERO fixed cost

This is an **experimental** project with no expectation of daily use, so the
architecture is **100% scale-to-zero / pay-per-use** — if nobody uses it, it costs
~nothing. There are **no fixed-cost (billed-at-zero-traffic) components**:

- **Cloud Run** runs at **min-instances = 0** (scales to zero) for BOTH the webapi
  Service and the ingestion Job — no warm/provisioned instances, no
  always-allocated CPU.
- **Auth = Cloud Run _direct_ IAP** (free), **NOT** an external HTTPS Load Balancer
  (an LB is a fixed ~US$18+/mo charge even idle). There is no load balancer.
- **BigQuery is on-demand** (per-query bytes, capped — see §2). **No** reserved
  slots / flat-rate capacity commitments, and **no BI Engine reservation** (BI
  Engine is reserved acceleration capacity billed by GB-hour even at zero traffic).
- Batch via **Cloud Run Jobs + Cloud Scheduler** (run-then-stop; pay-per-invocation).
  GCS lifecycle tiers/deletes cold objects; dev BQ datasets auto-expire (7 days).

> **Rule:** never add a fixed-cost component (LB, min-instances>0, reserved BQ
> slots, BI Engine, provisioned concurrency, static IP, Cloud NAT, always-on VM)
> without an explicit instruction. Fixed-cost infra is a *future* concern.

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

BigQuery runs **on-demand** (you pay per query byte scanned), so a single query —
a custom Looker query, a new join, an accidental full scan — can read several GB.
Set a daily ceiling. (The webapi serving path is also capped per-query via
`BQ_MAX_BYTES_BILLED`.)

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
on-demand query + storage + GCS Standard ⇒ Coldline); Cloud Run scales to zero, so
it costs ~nothing when idle, and there is no load balancer or BI Engine fixed cost.
