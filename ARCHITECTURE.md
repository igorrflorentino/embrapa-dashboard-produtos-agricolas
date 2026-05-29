# Arquitetura — Embrapa Commodities Dashboard

> Documento técnico de "capô aberto": estrutura de pastas, decisões de stack, fluxo de dados e diagramas.

> ⚠️ **Frontend em reconstrução com Claude Design System.** A camada de visualização Dash + Plotly (Cloud Run) foi removida em 2026-05-29. O backend descrito abaixo está intacto e operacional. O próximo handoff trará o novo frontend; até lá, o consumo do Gold se dá via Looker Studio ou queries diretas no BigQuery.

---

## Visão Geral do Pipeline

O projeto implementa uma **arquitetura Medallion** (Bronze → Silver → Gold) para análise histórica de produção extrativa vegetal brasileira (IBGE PEVS), enriquecida com câmbio (USD, EUR, CNY) e inflação (IPCA, IGP-M, IGP-DI) do Banco Central do Brasil.

```
 ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
 │  IBGE SIDRA  │   │  BCB SGS     │   │  BCB SGS     │
 │  (PEVS)      │   │  (Inflação)  │   │  (Câmbio)    │
 └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
        │                  │                   │
        └──────────┬───────┴───────────────────┘
                   ▼
 ┌─────────────────────────────────────────────────────┐
 │  Python  (src/embrapa_commodities)                  │
 │  fetch → Parquet → GCS → BigQuery Bronze            │
 └───────────────────────┬─────────────────────────────┘
                         ▼
 ┌─────────────────────────────────────────────────────┐
 │  dbt-bigquery  (dbt/)                               │
 │  Silver: tipagem, dedup, IPCA chain index           │
 │  Gold:   denormalização, FX, deflação real           │
 └───────────────────────┬─────────────────────────────┘
                         ▼
 ┌─────────────────────────────────────────────────────┐
 │  Consumo                                            │
 │  • Looker Studio (direto na tabela Gold)             │
 │  • (frontend dedicado em reconstrução)               │
 └─────────────────────────────────────────────────────┘
```

---

## Stack de Tecnologias

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Linguagem | Python 3.12 (`pyenv` + `.python-version`) | Ecossistema de dados maduro, type hints modernos |
| Gerenciamento de pacotes | `uv` + `uv.lock` | Resolução determinística, 10–100× mais rápido que pip |
| Build system | `hatchling` | PEP 517 nativo, zero config para wheel |
| Ingestão | `requests`, `tenacity`, `pandas`, `pyarrow` | HTTP resiliente com retry, Parquet columnar nativo |
| Data Lake | Google Cloud Storage (Parquet) | Armazenamento object-store, particionado por fonte/data |
| Data Warehouse | BigQuery | Serverless, SQL padrão, integração nativa com Looker |
| Transformações | `dbt-core` + `dbt-bigquery` | Transformações versionadas, testáveis, incrementais |
| CI/CD | GitHub Actions | Lint + test + dbt parse em cada PR |
| Lint / Format | Ruff | Substitui flake8 + isort + black; extremamente rápido |
| SQL Lint | SQLFluff | Validação de estilo SQL nos modelos dbt |
| Pre-commit | gitleaks, ruff, file-hygiene hooks | Segurança de credenciais + qualidade de código |
| Testes | pytest, responses, pytest-cov | Mocks HTTP, cobertura, markers customizados |
| Configuração | pydantic-settings + `.env` | Validação tipada, zero hardcode |

> A camada de **visualização** (anteriormente Dash + Plotly + Gunicorn em Cloud Run) está sendo refeita no Claude Design System em um fluxo separado. Quando o novo frontend chegar via handoff, a tabela acima será atualizada com a nova stack de UI/deploy.

---

## Estrutura de Pastas

```
embrapa-dashboard-commodities/
│
├── src/embrapa_commodities/          # Pacote Python principal
│   ├── __init__.py
│   ├── cli.py                        # Entrypoint Typer (`embrapa`)
│   ├── config.py                     # pydantic-settings — lê .env
│   ├── discover.py                   # Helpers auxiliares (não usados no pipeline)
│   ├── doctor.py                     # Diagnóstico de saúde (embrapa doctor)
│   ├── backup.py                     # Snapshot Gold → GCS
│   ├── monitor.py                    # Monitoramento de métricas
│   ├── observability.py              # Logging estruturado
│   │
│   ├── gcp/                          # Clientes GCP
│   │   ├── bigquery.py               # Load Parquet → BQ, auto-create datasets
│   │   └── storage.py                # Upload → GCS, auto-create bucket
│   │
│   ├── ibge/                         # Pipeline IBGE PEVS
│   │   ├── client.py                 # HTTP client SIDRA API
│   │   └── pipeline.py               # Orquestração Bronze
│   │
│   └── bcb/                          # Pipelines Banco Central
│       ├── client.py                 # HTTP client SGS API
│       ├── inflation.py              # Pipeline IPCA/IGP-M/IGP-DI
│       └── currency.py               # Pipeline USD/EUR/CNY
│
├── dbt/                              # Transformações dbt (Silver + Gold)
│   ├── dbt_project.yml               # Configuração do projeto dbt
│   ├── packages.yml                  # Dependências (dbt_utils)
│   ├── profiles.yml.example          # Template de perfil (nunca commitado real)
│   ├── models/
│   │   ├── _sources.yml              # Declaração de fontes Bronze
│   │   ├── silver/
│   │   │   ├── _silver.yml           # Schema + testes Silver
│   │   │   ├── silver_ibge_pevs.sql  # PEVS tipado + dedup (incremental)
│   │   │   ├── silver_bcb_inflation.sql  # IPCA chain index
│   │   │   └── silver_bcb_currency.sql   # Câmbio limpo
│   │   └── gold/
│   │       ├── _gold.yml             # Schema + testes Gold
│   │       ├── gold_commodity_matrix.sql            # Tabela principal (município × produto × ano)
│   │       ├── gold_commodity_state_year.sql        # Agregação por estado × produto × ano
│   │       ├── gold_commodity_year_product.sql      # Agregação nacional por produto × ano
│   │       └── gold_commodity_state_total_year.sql  # Agregação geográfica pura (UF × ano)
│   ├── macros/
│   │   ├── generate_schema_name.sql  # Dev/prod schema separation
│   │   ├── safe_numeric.sql          # Conversão segura (placeholders IBGE → NULL)
│   │   ├── data_quality_flag.sql     # Flag OK/MISSING_VALUE/etc.
│   │   ├── state_dimensions.sql      # Região/UF lookup
│   │   └── apply_dev_ttl.sql         # Auto-expiração de tabelas dev (7 dias)
│   ├── seeds/
│   │   ├── _seeds.yml                # Schema dos seeds
│   │   └── historical_currency_factors.csv  # Fatores de reforma monetária
│   └── tests/                        # Testes dbt customizados
│
├── tests/                            # Testes Python (pytest)
│   ├── test_cli.py                   # Testes do CLI
│   ├── test_config.py                # Testes de configuração
│   ├── test_ibge_client.py           # Testes do client IBGE (HTTP mockado)
│   ├── test_ibge_pipeline.py         # Testes do pipeline IBGE
│   ├── test_bcb_client.py            # Testes do client BCB
│   ├── test_bcb_inflation_pipeline.py
│   ├── test_bcb_currency_pipeline.py
│   ├── test_bcb_pipeline.py
│   ├── test_gcp_bigquery.py
│   ├── test_gcp_storage.py
│   ├── test_backup.py
│   ├── test_doctor.py
│   ├── test_monitor.py
│   └── test_observability.py
│
├── scripts/                          # Tooling auxiliar
│   ├── README.md                     # Documentação dos scripts
│   ├── setup_dev_env.py              # Setup unificado cross-platform
│   ├── test_setup.py                 # Testes do setup
│   ├── grant-sa-iam-roles.ps1        # IAM roles
│   └── setup-claude-code-web-sa.sh   # SA para Claude Code Web
│
├── docs/                             # Documentação detalhada
│   ├── architecture.md               # Arquitetura de autenticação (Cadeia de Confiança)
│   ├── cost_safety.md                # Budget alert + custom quota
│   ├── iam_setup.md                  # Setup de IAM e Service Accounts
│   ├── looker_studio_setup.md        # Conexão Looker Studio → Gold
│   ├── migration_history.md          # Notas de migração histórica
│   ├── ownership_transfer.md         # Checklist de transferência para empresa
│   ├── setup.md                      # Guia completo de setup
│   └── testing.md                    # Estratégia e guia de testes
│
├── .github/workflows/                # CI/CD
│   ├── ci.yml                        # PR gate: lint + test + dbt parse
│   └── dbt-build-prod.yml            # Build prod automatizado em push para main
│
├── .claude/                          # Configuração Claude Code
│   ├── settings.json
│   └── skills/                       # Skills para Claude Code (backend)
│
├── CLAUDE.md                         # Guia para assistentes de IA
├── README.md                         # Documentação principal
├── ARCHITECTURE.md                   # ← Este arquivo
├── pyproject.toml                    # Manifest Python (deps, scripts, tools)
├── uv.lock                           # Lockfile determinístico
├── Makefile                          # Atalhos de desenvolvimento
├── LICENSE                           # Apache License 2.0
├── .env.example                      # Template de variáveis de ambiente
├── .pre-commit-config.yaml           # Hooks de pré-commit
├── .python-version                   # Pin do Python (3.12.11)
├── .gitignore                        # Exclusões do Git
├── setup.sh / setup.bat / setup.ps1  # Setup automatizado por plataforma
├── test.sh / test.bat                # Atalhos para testes
└── init_dev_env.sh                   # Inicialização para sandboxes
```

> Apagados em 2026-05-29 junto com a UI: `src/embrapa_commodities/dashboard/`, `Dockerfile`, `scripts/dashboard*`, `scripts/check_dashboard_size.py`, `tests/test_dashboard_*`, `.github/workflows/dashboard-smoke.yml`, `docs/auth.md`, e os skills do Claude Code `run-dashboard` / `dash-page-scaffold` / `new-chart-component` / `deploy-cloud-run`. Caminhos legados que ainda existem mas só faziam sentido para a UI antiga: `deploy/`, `artifacts/`, `.dockerignore`, `.gcloudignore` — podem ser removidos com segurança quando conveniente.

---

## Fluxo de Dados Detalhado

### 1. Bronze (Python → GCS → BigQuery)

- **Append-only**: cada ingestão adiciona registros; nunca sobrescreve.
- Todas as colunas são `STRING` exceto `ingestion_timestamp` — tipagem acontece no Silver.
- BCB é **delta por padrão**: consulta `max(reference_date_str)` no Bronze e só busca overlap de 12 meses (inflação) ou 30 dias (câmbio).
- Auto-criação: bucket GCS e datasets BigQuery são criados automaticamente na primeira execução.

### 2. Silver (dbt, `materialized=table` / `incremental`)

- `silver_ibge_pevs`: **incremental** (`insert_overwrite` por `reference_year`). Dedup via `qualify row_number() ... order by ingestion_timestamp desc`.
- `silver_bcb_inflation`: **table** (precisa de janela completa para calcular o chain index IPCA).
- `silver_bcb_currency`: **table** (tabela pequena).
- **Seed `historical_currency_factors`**: fator multiplicador que absorve reformas monetárias brasileiras (Cz$ → NCz$ → Cr$ → CR$ → R$). Sem ele, valores pré-1994 ficam 10⁶–10⁹× inflados.

### 3. Gold (dbt, `materialized=table`)

- Tabela principal: `gold_commodity_matrix` — uma linha por `(reference_year, state_acronym, city_name, product_code)`.
- Tabelas agregadas (siblings, todas derivadas direto da matrix): `gold_commodity_state_year` (UF × produto × ano), `gold_commodity_year_product` (produto × ano nacional), `gold_commodity_state_total_year` (UF × ano sem produto).
- Quatro convenções monetárias:
  - `val_yearfx_*` — valor nominal convertido pelo FX médio do ano. NULL para moedas estrangeiras pré-1994.
  - `val_real_{ipca,igpm,igpdi}_*` — valor deflacionado pela cadeia IPCA / IGP-M / IGP-DI, projetado para hoje. **Use esta coluna para comparações entre anos.**

### 4. Consumo

- **Looker Studio**: conexão direta na tabela `gold.gold_commodity_matrix`.
- **Frontend dedicado**: em reconstrução com Claude Design System. Até lá, o novo agente do handoff vai reintroduzir a camada de UI consumindo as mesmas tabelas Gold.

---

## Separação Dev / Prod

O macro `generate_schema_name.sql` garante:

| Target | Silver Dataset | Gold Dataset |
|---|---|---|
| `dev` (padrão) | `dbt_dev_silver` | `dbt_dev_gold` |
| `prod` | `silver` | `gold` |

Tabelas dev auto-expiram em **7 dias** (macro `apply_dev_ttl`).

---

## Modelo de Configuração

**Nada é hardcoded.** Todos os parâmetros fluem via `.env` → `pydantic-settings` (`config.py`):

- Bucket GCS, prefixos, nomes de datasets
- Códigos de produtos IBGE, séries BCB
- Projeto GCP, localização BQ
- Método de autenticação (impersonation vs. keyfile)

Transferência para outro projeto GCP = copiar `.env.example`, ajustar e rodar `embrapa ingest all`.

---

## Segurança e Autenticação

Modelo de **Service Account Impersonation** (OAuth 2.0) sem keyfiles distribuídos:

- **`sa-secret-reader-prod`**: target de impersonação para desenvolvedores (dbt + queries)
- **`sa-data-pipeline-prod`**: pipelines de ingestão (write GCS + BQ)
- **`sa-ai-agent-admin-prod`**: agentes de IA (BQ editor + GCS)

> A SA `sa-web-dashboard-prod` (read-only para o Cloud Run anterior) foi descomissionada junto com a remoção da UI Dash. Quando o novo frontend chegar, uma nova SA será documentada aqui.

Detalhes completos em [`docs/architecture.md`](docs/architecture.md) e [`docs/iam_setup.md`](docs/iam_setup.md).

---

## CI/CD

### GitHub Actions (`ci.yml`)

Executa em cada PR para `main`:
1. `make lint` — Ruff check + format
2. `make test` — pytest (sem credenciais GCP)
3. `dbt deps` + `dbt parse` — validação Jinja + ref/source sem warehouse

### dbt build prod (`dbt-build-prod.yml`)

Push para `main` que toque `dbt/**` ou `config.py` dispara um build do Silver/Gold em prod via Workload Identity Federation. Snapshots Gold seguem manuais (`make dbt-build-prod-with-backup` localmente, antes de release boundaries).

---

## Documentação Relacionada

Índice completo de toda a documentação do projeto (root + `docs/`) disponível no [`README.md`](README.md#-documentação).
