# Arquitetura — Embrapa Commodities Dashboard

> Documento técnico de "capô aberto": estrutura de pastas, decisões de stack, fluxo de dados e diagramas.

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
 │  • Dash web app (Cloud Run)                         │
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
| Dashboard (web) | Dash + Plotly + Gunicorn | Python full-stack, gráficos interativos, deploy Cloud Run |
| Containerização | Docker (multi-stage) | Imagem slim, non-root, cache de layers |
| Deploy | Google Cloud Run | Serverless, auto-scaling, IAM nativo |
| CI/CD | GitHub Actions | Lint + test + dbt parse em cada PR |
| Lint / Format | Ruff | Substitui flake8 + isort + black; extremamente rápido |
| SQL Lint | SQLFluff | Validação de estilo SQL nos modelos dbt |
| Pre-commit | gitleaks, ruff, file-hygiene hooks | Segurança de credenciais + qualidade de código |
| Testes | pytest, responses, pytest-cov | Mocks HTTP, cobertura, markers customizados |
| Configuração | pydantic-settings + `.env` | Validação tipada, zero hardcode |

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
│   ├── bcb/                          # Pipelines Banco Central
│   │   ├── client.py                 # HTTP client SGS API
│   │   ├── inflation.py              # Pipeline IPCA/IGP-M/IGP-DI
│   │   └── currency.py               # Pipeline USD/EUR/CNY
│   │
│   └── dashboard/                    # Dash web application
│       ├── app.py                    # Servidor Dash + layout
│       ├── config.py                 # Configuração do dashboard
│       ├── data.py                   # Camada de dados (BQ → DataFrame)
│       ├── data_sources.py           # Fontes de dados abstraídas
│       ├── formatting.py             # Formatação de números/moedas
│       ├── health.py                 # Health check endpoint
│       ├── theme.py                  # Design tokens / tema visual
│       ├── assets/                   # CSS, favicons, imagens estáticas
│       ├── components/               # Componentes Dash reutilizáveis
│       └── pages/                    # Páginas do dashboard (multi-page)
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
│   │       ├── gold_commodity_matrix.sql          # Tabela principal (22 cols)
│   │       ├── gold_commodity_state_year.sql      # Agregação por estado/ano
│   │       └── gold_commodity_year_product.sql    # Agregação por produto/ano
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
│   ├── test_observability.py
│   └── test_dashboard_smoke.py       # Smoke test (requer GCP, marker `smoke`)
│
├── scripts/                          # Tooling auxiliar
│   ├── README.md                     # Documentação dos scripts
│   ├── setup_dev_env.py              # Setup unificado cross-platform
│   ├── test_setup.py                 # Testes do setup
│   ├── dashboard_smoke.py            # Smoke test do dashboard
│   ├── dashboard_visual_check.py     # Visual check com Playwright
│   ├── check_dashboard_size.py       # Soft 500-LOC ceiling
│   ├── dashboard-*.ps1               # Scripts PowerShell (Windows)
│   ├── grant-sa-iam-roles.ps1        # IAM roles
│   └── setup-claude-code-web-sa.sh   # SA para Claude Code Web
│
├── docs/                             # Documentação detalhada
│   ├── architecture.md               # Arquitetura de autenticação (Cadeia de Confiança)
│   ├── auth.md                       # Guia de autenticação do dashboard
│   ├── cost_safety.md                # Budget alert + custom quota
│   ├── iam_setup.md                  # Setup de IAM e Service Accounts
│   ├── looker_studio_setup.md        # Conexão Looker Studio → Gold
│   ├── migration_history.md          # Notas de migração histórica
│   ├── ownership_transfer.md         # Checklist de transferência para empresa
│   ├── setup.md                      # Guia completo de setup
│   └── testing.md                    # Estratégia e guia de testes
│
├── deploy/                           # Artefatos de deploy
│   └── README.md                     # Instruções de deploy
│
├── design system/                    # Design system do dashboard
│   └── embrapa-commodities-design-system/
│
├── .github/workflows/                # CI/CD
│   ├── ci.yml                        # PR gate: lint + test + dbt parse
│   └── dashboard-smoke.yml           # Smoke test do dashboard
│
├── .claude/                          # Configuração Claude Code
│   ├── settings.json
│   └── skills/                       # Skills para Claude Code
│
├── CLAUDE.md                         # Guia para assistentes de IA
├── README.md                         # Documentação principal
├── ARCHITECTURE.md                   # ← Este arquivo
├── pyproject.toml                    # Manifest Python (deps, scripts, tools)
├── uv.lock                           # Lockfile determinístico
├── Makefile                          # Atalhos de desenvolvimento
├── Dockerfile                        # Imagem Docker multi-stage
├── LICENSE                           # Apache License 2.0
├── .env.example                      # Template de variáveis de ambiente
├── .pre-commit-config.yaml           # Hooks de pré-commit
├── .python-version                   # Pin do Python (3.12.11)
├── .gitignore                        # Exclusões do Git
├── .dockerignore                     # Exclusões do Docker build
├── .gcloudignore                     # Exclusões do gcloud deploy
├── setup.sh / setup.bat / setup.ps1  # Setup automatizado por plataforma
├── test.sh / test.bat                # Atalhos para testes
└── init_dev_env.sh                   # Inicialização para sandboxes
```

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
- Tabelas agregadas: `gold_commodity_state_year`, `gold_commodity_year_product`.
- Duas convenções monetárias:
  - `val_yearfx_*` — valor nominal convertido pelo FX médio do ano. NULL para moedas estrangeiras pré-1994.
  - `val_real_{ipca,igpm}_*` — valor deflacionado pela cadeia IPCA/IGP-M, projetado para hoje. **Use esta coluna para comparações entre anos.**

### 4. Consumo

- **Looker Studio**: conexão direta na tabela `gold.gold_commodity_matrix`.
- **Dash web app**: aplicação Python (Dash + Plotly) servida via Gunicorn no Cloud Run.

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
- **`sa-web-dashboard-prod`**: dashboard read-only (BQ viewer)
- **`sa-ai-agent-admin-prod`**: agentes de IA (BQ editor + GCS)

Detalhes completos em [`docs/architecture.md`](docs/architecture.md) e [`docs/iam_setup.md`](docs/iam_setup.md).

---

## CI/CD

### GitHub Actions (`ci.yml`)

Executa em cada PR para `main`:
1. `make lint` — Ruff check + format
2. `make test` — pytest (sem credenciais GCP)
3. Dashboard module size ceiling (soft 500 LOC)
4. `dbt deps` + `dbt parse` — validação Jinja + ref/source sem warehouse

### Dashboard Smoke (`dashboard-smoke.yml`)

Smoke test que requer credenciais GCP (execução separada).

---

## Documentação Relacionada

Índice completo de toda a documentação do projeto (root + `docs/`) disponível no [`README.md`](README.md#-documentação).

