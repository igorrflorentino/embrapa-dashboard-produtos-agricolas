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
6. **Primeira carga** — `uv run embrapa ingest all` cria automaticamente o bucket e os datasets `bronze_ibge` / `bronze_bcb` / `bronze_comex` no novo projeto (COMTRADE fica de fora do `all` — é key-gated; rode `uv run embrapa ingest comtrade` à parte).
7. **Primeira transformação** — `make dbt-build` materializa Silver e Gold.
8. **Looker Studio** — duplique o relatório existente e reaponte a fonte de dados para `embrapa-commodities-prod.gold.gold_pevs_production`.

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

## Backup cold-storage do Gold (responsabilidade do operador)

O comando `embrapa backup-gold` exporta todas as tabelas Gold (introspecta o
dataset por prefixo `gold_`; hoje quatro) para
`gs://${GCS_BUCKET}/backups/run=<timestamp>/...` em Parquet. Ele **não**
roda automaticamente após `make dbt-build-prod` — isso é intencional, para
que builds experimentais em prod não inflem o bucket de snapshots.

**Caminho recomendado:** use `make dbt-build-prod-with-backup` em vez de
`make dbt-build-prod` puro sempre que o resultado for digno de preservação
(release de schema, novo código de produto, qualquer coisa em que você
queira poder fazer roll-back). Plain `make dbt-build-prod` continua
disponível para iterações descartáveis.

**Cadência recomendada:** no mínimo **uma vez por fronteira de release** —
ou seja, sempre que algo no comportamento ou no schema do Gold mudar de
forma observável pelo Looker Studio / pelo dashboard. Em projetos com
ingestão semanal, o padrão prático é rodar o caminho `-with-backup` na
sexta-feira final de cada sprint.

**Retenção automática:** o ciclo de vida do GCS aplicado ao prefixo
`backups/` faz:

| Idade | Ação |
|---|---|
| 30 dias | Transição para `NEARLINE` |
| 90 dias | Transição para `COLDLINE` |
| 365 dias | `DELETE` |

(Configurado em `src/embrapa_commodities/gcp/storage.py` e aplicado na
criação do bucket — o prefixo `landing/` segue um ciclo separado que
termina em `ARCHIVE`, sem delete.)

**Monitoramento:** `uv run embrapa doctor` inclui uma checagem
`Gold backup freshness` que emite warning se o snapshot mais recente
estiver com mais de `BACKUP_STALENESS_DAYS` (padrão 14) dias, e falha
explicitamente quando nenhum snapshot existe.
