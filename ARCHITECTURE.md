# Arquitetura — Embrapa Commodities Dashboard

> Documento técnico de "capô aberto": estrutura de pastas, decisões de stack, fluxo de dados e diagramas.

> 📊 **Ferramenta de análise histórica e científica** (pesquisadores da Embrapa) — não é um produto de métricas de negócio nem de tempo real; os dados são processados em lote. O Gold é consumido por **dois caminhos paralelos e de primeira classe**: (1) **Looker Studio** direto na tabela Gold, disponível agora; (2) **dashboard dedicado Dash + HTML/CSS com deploy no Cloud Run**, atualmente em reconstrução com o Claude Design System (a UI Dash anterior foi removida em 2026-05-29 para um handoff limpo). O backend descrito abaixo é independente da visualização e já alimenta ambos.

---

## Visão Geral do Pipeline

O projeto implementa uma **arquitetura Medallion** (Bronze → Silver → Gold) para análise histórica de produção extrativa vegetal brasileira (IBGE PEVS), enriquecida com câmbio (USD, EUR, CNY) e inflação (IPCA, IGP-M, IGP-DI) do Banco Central do Brasil.

```
 ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐
 │ IBGE SIDRA │  │  BCB SGS   │  │  BCB SGS   │  │ MDIC COMEX   │
 │  (PEVS)    │  │ (Inflação) │  │  (Câmbio)  │  │ (CSV massa)  │
 └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └──────┬───────┘
       │               │               │                │
       └───────┬───────┴───────────────┴────────────────┘
               ▼
 ┌─────────────────────────────────────────────────────┐
 │  Python  (src/embrapa_commodities) — two-phase      │
 │  Fase 1  extract → raw/ (Parquet verbatim no GCS)   │
 │  Fase 2  raw/ → filtra/molda → BigQuery Bronze      │
 └───────────────────────┬─────────────────────────────┘
                         ▼
 ┌─────────────────────────────────────────────────────┐
 │  dbt-bigquery  (dbt/)                               │
 │  Silver: tipagem, dedup, IPCA chain index           │
 │  Gold:   denormalização, FX, deflação real           │
 └───────────────────────┬─────────────────────────────┘
                         ▼
 ┌─────────────────────────────────────────────────────┐
 │  Consumo (dois caminhos paralelos)                  │
 │  • Looker Studio (direto na tabela Gold)             │
 │  • Dashboard Dash + HTML/CSS @ Cloud Run             │
 │    (em reconstrução · Claude Design System)          │
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
| Consumo / Visualização | Looker Studio · Dash + HTML/CSS @ Cloud Run | Dois caminhos paralelos sobre as mesmas tabelas Gold (ver seção Consumo) |

> A camada de **visualização dedicada** (Dash + HTML/CSS, deploy no Cloud Run via Gunicorn) está sendo refeita no Claude Design System em um fluxo separado — é um alvo real, não abandonado. O Looker Studio é o segundo caminho de consumo e permanece disponível em paralelo. Quando o novo frontend chegar via handoff, a stack de UI/deploy (Dockerfile, Cloud Run, SA read-only) será reintroduzida e esta tabela atualizada.

---

## Estrutura de Pastas

```
embrapa-dashboard-commodities/
│
├── src/embrapa_commodities/          # Pacote Python principal
│   ├── __init__.py
│   ├── cli.py                        # Entrypoint Typer (`embrapa`) + registry INGESTS
│   ├── config.py                     # pydantic-settings — lê .env
│   ├── discover.py                   # Helpers auxiliares (não usados no pipeline)
│   ├── doctor.py                     # Diagnóstico + registry SOURCE_CHECKS / BRONZE_TARGETS
│   ├── backup.py                     # Snapshot Gold → GCS (introspecção via list_tables)
│   ├── monitor/                      # Monitor de progresso ao vivo (`embrapa monitor`)
│   │   ├── state.py                  # Estado + parse de eventos JSONL
│   │   └── render.py                 # Renderização Rich (tabela de progresso)
│   ├── observability.py              # Logging estruturado
│   │
│   ├── core/                         # ⭐ Primitivos compartilhados entre fontes
│   │   ├── exceptions.py             # SourceTransientError (marker p/ retry)
│   │   ├── http.py                   # http_retry_policy + get_drained (HTTP resiliente)
│   │   └── observability_helpers.py  # pipeline_run (eventos p/ embrapa monitor)
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
│   │   ├── series.py                 # Pipeline SGS genérico (inflation/currency)
│   │   ├── inflation.py              # Spec IPCA/IGP-M/IGP-DI
│   │   └── currency.py               # Spec USD/EUR/CNY
│   │
│   └── comex/                        # Pipeline MDIC Comex Stat (CSV em massa)
│       ├── client.py                 # Downloader CSV (stream p/ disco + filtro)
│       ├── pipeline.py               # Orquestração Bronze (delta por fluxo×ano)
│       └── _ca.py                    # CA intermediária TLS vendorizada
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
│   │   │   ├── silver_bcb_currency.sql   # Câmbio limpo
│   │   │   └── silver_comex_flows.sql    # COMEX tipado + dedup (grão-fonte)
│   │   └── gold/
│   │       ├── _gold.yml             # Schema + testes Gold
│   │       ├── gold_pevs_production.sql  # Gold IBGE PEVS (forma: production)
│   │       └── gold_comex_flows.sql      # Gold COMEX (forma: flows)
│   │                                     # Novas fontes: gold_<fonte>_<forma>
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
│   ├── auth_architecture.md          # Arquitetura de autenticação (Cadeia de Confiança)
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

> Apagados em 2026-05-29 junto com a UI: `src/embrapa_commodities/dashboard/`, `Dockerfile`, `scripts/dashboard*`, `scripts/check_dashboard_size.py`, `tests/test_dashboard_*`, `.github/workflows/dashboard-smoke.yml`, `docs/auth.md`, e os skills do Claude Code `run-dashboard` / `dash-page-scaffold` / `new-chart-component` / `deploy-cloud-run`.

---

## Fluxo de Dados Detalhado

### 0. Zona Raw + ingestão two-phase (todas as fontes)

Antes do Bronze, **toda fonte arquiva o extrato verbatim** em
`gs://<bucket>/raw/<source>/<dataset>/<basename>.parquet` (com metadata de
proveniência: URL, ETag/Last-Modified, `fetched_at`, `rows`). O Bronze deriva
desse raw. Assim, re-filtrar / mudar produtos / re-derivar o Bronze **não
re-bate na fonte** — só uma revisão real do dado dispara re-fetch. Cada
`embrapa ingest <source>` tem `--from-raw` (reconstrói o Bronze do raw, sem
internet). Contrato compartilhado em [`core/raw.py`](../src/embrapa_commodities/core/raw.py);
detalhes em [`PLANS/raw_zone_architecture.md`](PLANS/raw_zone_architecture.md).
Por fonte: COMEX re-baixa só quando o ETag muda (filtra na Fase 2 via
`iter_batches`); IBGE arquiva a resposta SIDRA; BCB arquiva cada janela delta
como objeto carimbado por run (trilha append-only).

### 1. Bronze (raw → BigQuery)

- **Append-only**: cada ingestão adiciona registros; nunca sobrescreve.
- Todas as colunas são `STRING` exceto `ingestion_timestamp` — tipagem acontece no Silver.
- BCB é **delta por padrão**: consulta `max(reference_date_str)` no Bronze e só busca overlap de 12 meses (inflação) ou 30 dias (câmbio); a Fase 2 anexa o que a Fase 1 arquivou.
- Auto-criação: bucket GCS e datasets BigQuery são criados automaticamente na primeira execução.

### 2. Silver (dbt, `materialized=table` / `incremental`)

- `silver_ibge_pevs`: **incremental** (`insert_overwrite` por `reference_year`). Dedup via `qualify row_number() ... order by ingestion_timestamp desc`.
- `silver_bcb_inflation`: **table** (precisa de janela completa para calcular o chain index IPCA).
- `silver_bcb_currency`: **table** (tabela pequena).
- `silver_comex_flows`: **table** (dedup no grão-fonte completo via `qualify`; `safe_numeric` em VL_FOB/KG/QT/frete/seguro). Candidata a incremental se o volume do cap. 44 ao longo das décadas crescer.
- **Seed `historical_currency_factors`**: fator multiplicador que absorve reformas monetárias brasileiras (Cz$ → NCz$ → Cr$ → CR$ → R$). Sem ele, valores pré-1994 ficam 10⁶–10⁹× inflados.

### 3. Gold (dbt, `materialized=table`)

- Tabela do IBGE PEVS: `gold_pevs_production` — uma linha por `(reference_year, state_acronym, city_name, product_code)`.
- Tabela do MDIC COMEX: `gold_comex_flows` — uma linha por `(flow, reference_year, reference_month, ncm_code, country_code, state_acronym)`. As 4 convenções monetárias são aplicadas sobre `VL_FOB` (US$): `val_yearfx_*` no FX do mês de registro e `val_real_*` convertendo US$→BRL no FX do mês, deflacionando pela cadeia BCB e reconvertendo no FX atual (deflação **mensal**, não anual, por o grão ser mensal).
- **Gold é por fonte, UMA tabela comprehensiva por fonte.** Nomenclatura: `gold_<fonte>_<forma>`, onde `<forma>` é o grão semântico — `production` (medição de saída produtiva, sem origem→destino; só o PEVS) ou `flows` (fluxo origem→destino; os bancos de comércio: COMEX, COMTRADE, NFe). Cada fonte tem sua própria linhagem consumindo as mesmas Silver de deflação/FX. Qualquer agregação (estado-ano, nacional) é derivada **em tempo de query** via `GROUP BY` — deliberadamente NÃO mantemos tabelas pré-agregadas (simplicidade sobre eficiência por ora). Grãos incompatíveis (mensal × país × HS code para COMEX, evento × UF para NFe) também justificam linhagens separadas — ver [docs/adding_a_data_source.md](docs/adding_a_data_source.md).
- Quatro convenções monetárias (aplicáveis a qualquer Gold monetária):
  - `val_yearfx_*` — valor nominal convertido pelo FX médio do ano. NULL para moedas estrangeiras pré-1994.
  - `val_real_{ipca,igpm,igpdi}_*` — valor deflacionado pela cadeia IPCA / IGP-M / IGP-DI, projetado para hoje. **Use esta coluna para comparações entre anos.**

### 4. Consumo

Dois caminhos paralelos, ambos lendo as mesmas tabelas Gold — não são exclusivos e podem coexistir:

- **Looker Studio** (no-code): conexão direta nas tabelas Gold (`gold.gold_pevs_production`, `gold.gold_comex_flows`). Bom para relatórios padronizados e exploração rápida sem deploy. Disponível agora.
- **Dashboard dedicado (HTML/CSS + Dash) no Cloud Run**: frontend sob medida para os pesquisadores, em reconstrução com o Claude Design System. Consome as mesmas tabelas Gold via BigQuery; deploy no Cloud Run com SA read-only e IAM. É um alvo de primeira classe — quando o handoff chegar, o Dockerfile/Cloud Run e a SA de leitura voltam ao repo.

---

## Camada `core/` — contrato comum entre fontes

`src/embrapa_commodities/core/` concentra os primitivos genuinamente compartilhados, mantendo IBGE/BCB/… enxutas:

- **`SourceTransientError`** (em `core/exceptions.py`): marker para falhas transitórias upstream. `SidraTransientError` e `BcbTransientError` herdam via mixin, e qualquer fonte nova faz o mesmo. Isso permite que o decorator compartilhado `core.http.http_retry_policy` capture todas as transientes sem precisar listar cada classe por nome.
- **`http_retry_policy` + `get_drained`** (em `core/http.py`): a política de retry tenacity (`stop_after_attempt(5) | stop_after_delay(deadline_s)` + `wait_exponential(1, 2, 30)`) e o drain manual do body sob deadline wall-clock (defesa contra slow-byte hangs que burlam o per-read timeout do `requests`). Cada fonte compõe com seus deadlines locais e sua exceção transient. Adotados por `ibge/client._http_get` e `bcb/client._fetch_window`.
- **Zona raw** (em `core/raw.py`): o contrato da ingestão two-phase — `land_raw(df)` / `land_raw_file(path)` arquivam o extrato verbatim em `raw/<source>/<dataset>/<basename>.parquet` com metadata de proveniência; `read_raw` / `download_raw` leem de volta (o `download_raw` + `iter_batches` mantém o filtro de arquivos grandes memory-bounded); `list_raw` enumera a trilha de uma fonte (p/ `--from-raw`); `raw_provenance` lê a metadata (base da checagem de freshness por ETag). A cauda BQ usa o `gcp/bigquery.load_dataframe`. Adotado por todas as fontes.
- **`pipeline_run`** (em `core/observability_helpers.py`): context manager que encapsula a sequência de eventos de um ingest de chunk-único (`pipeline_start → chunk_start → chunk_end/chunk_error → pipeline_end`). Os comandos `ingest ibge`, `ingest bcb-inflation` e `ingest bcb-currency` usam o mesmo caminho, então toda fonte single-shot aparece de forma idêntica no `embrapa monitor`. Fluxos multi-chunk (`ingest ibge-batch`) emitem a sequência por estado/chunk à mão e **não** usam este helper.

Ponto importante: **não migrar** clientes existentes (IBGE/BCB) para abstrações compartilhadas só pelo gosto da DRY — o slow-byte / period-halving do SIDRA é defesa hard-won que está bem onde está. Os primitivos de `core/` são adotados conscientemente, fonte a fonte, conforme convém. Veja a seção "Itens deferidos" do plano de prep.

Não mora em `core/`: lógica source-specific (parallelism por UF do IBGE, chunking de séries do BCB, etc.) — fica em `<fonte>/`.

---

## Pontos de extensão para adicionar fontes

Adicionar uma fonte nova mexe em três registries leves + criar dois arquivos. Tudo está documentado em [docs/adding_a_data_source.md](docs/adding_a_data_source.md). Os registries são:

- `cli.INGESTS` (`src/embrapa_commodities/cli.py`) — registra a fonte em `embrapa ingest all`.
- `doctor.SOURCE_CHECKS` (`src/embrapa_commodities/doctor.py`) — adiciona o probe `embrapa doctor` para a nova API.
- `doctor.BRONZE_TARGETS` (`src/embrapa_commodities/doctor.py`) — faz a checagem de "Bronze table existe?" incluir a nova tabela.

Cada `@ingest_app.command()` continua manuscrito (observabilidade heterogênea entre fontes — IBGE emite eventos de estado, BCB não). Apenas o `ingest all` usa o registry.

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

> A SA `sa-web-dashboard-prod` é a **runtime read-only do dashboard dedicado no Cloud Run** (`roles/bigquery.dataViewer` na Gold). Está dormente enquanto o frontend é reconstruído no Claude Design System e volta a ser usada quando ele for redeployado. O **Looker Studio não usa esta SA** — consome a Gold via OAuth do usuário final (caminho de consumo independente).

Detalhes completos em [`docs/auth_architecture.md`](docs/auth_architecture.md) e [`docs/iam_setup.md`](docs/iam_setup.md).

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
