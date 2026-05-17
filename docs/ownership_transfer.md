# Transferência de propriedade para a empresa

Este projeto foi desenhado para ser portável: nada no código tem o `GCP_PROJECT_ID` ou o nome do bucket fixos. Tudo flui via `.env`.

## Checklist de migração

1. **GitHub** — transfira o repositório para a organização da empresa em *Settings → Transfer ownership*. Os colaboradores e o histórico permanecem.
2. **Novo projeto GCP** — crie um projeto dentro da org da empresa, por exemplo `embrapa-commodities-prod`. Habilite as APIs: BigQuery, Cloud Storage, IAM.
3. **Permissões locais (dev)** — cada engenheiro roda uma vez: `gcloud auth application-default login`.
4. **`.env` da empresa** — copie `.env.example` e atualize:
   ```
   GCP_PROJECT_ID=embrapa-commodities-prod
   GCS_BUCKET=embrapa-commodities-prod-datalake
   BQ_LOCATION=southamerica-east1   # ou US, conforme política da empresa
   ```
5. **`profiles.yml` da empresa** — copie `dbt/profiles.yml.example` para `~/.dbt/profiles.yml` e troque `project:` pelo novo projeto.
6. **Primeira carga** — `uv run embrapa ingest all` cria automaticamente o bucket e os datasets `bronze_ibge` / `bronze_bcb` no novo projeto.
7. **Primeira transformação** — `make dbt-build` materializa Silver e Gold.
8. **Looker Studio** — duplique o relatório existente e reaponte a fonte de dados para `embrapa-commodities-prod.gold.gold_commodity_matrix`.

## Quando migrar a orquestração para a nuvem

Hoje o MVP roda local. Quando a empresa exigir agendamento, recomendo, em ordem de complexidade:

1. **GitHub Actions + Workload Identity Federation** — gratuito (ou ~$0 para repos privados pequenos). Adicione um workflow em `.github/workflows/ingest.yml` rodando `uv run embrapa ingest all` num cron diário; a auth para o GCP via WIF dispensa service account keys.
2. **Cloud Run Jobs + Cloud Scheduler** — empacote o pacote Python como container e dispare via cron. Tudo dentro do GCP.
3. **Cloud Composer (Airflow)** — só se a empresa já mantém um cluster Composer; o custo fixo (~$300/mês) não compensa para este volume.

Em qualquer caso, o código não muda — apenas o trigger.

## IAM mínimo para a service account de produção

| Papel | Recurso | Justificativa |
|---|---|---|
| `roles/bigquery.dataEditor` | datasets `bronze_*`, `silver`, `gold` | escrita das tabelas |
| `roles/bigquery.jobUser` | projeto | criar jobs de load e query |
| `roles/storage.objectAdmin` | bucket `${project}-datalake` | escrita do Parquet raw |
