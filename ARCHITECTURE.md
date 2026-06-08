# Arquitetura — Embrapa Commodities Dashboard

> Documento técnico de "capô aberto": estrutura de pastas, decisões de stack, fluxo de dados e diagramas.

> 📊 **Ferramenta de análise histórica e científica** (pesquisadores da Embrapa) — não é um produto de métricas de negócio nem de tempo real; os dados são processados em lote. O Gold é consumido por **dois caminhos paralelos e de primeira classe**: (1) **Looker Studio** direto na tabela Gold, disponível agora; (2) **dashboard dedicado Dash + HTML/CSS com deploy no Cloud Run**, atualmente em reconstrução com o Claude Design System (a UI Dash anterior foi removida em 2026-05-29 para um handoff limpo). O backend descrito abaixo é independente da visualização e já alimenta ambos.

---

## Visão Geral do Pipeline

O projeto implementa uma **arquitetura Medallion** (Bronze → Silver → Gold) para análise histórica de produção extrativa vegetal brasileira (IBGE PEVS), enriquecida com câmbio (USD, EUR, CNY) e inflação (IPCA, IGP-M, IGP-DI) do Banco Central do Brasil.

```
 ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐
 │ IBGE SIDRA │ │  BCB SGS   │ │  BCB SGS   │ │ MDIC COMEX │ │ UN Comtrade  │
 │  (PEVS)    │ │ (Inflação) │ │  (Câmbio)  │ │ (CSV massa)│ │ (API keyed)  │
 └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └──────┬───────┘
       │              │              │              │               │
       └──────┬───────┴──────────────┴──────────────┴───────────────┘
              ▼
 ┌─────────────────────────────────────────────────────┐
 │  Python  (src/embrapa_commodities) — two-phase      │
 │  Fase 1  extract → raw/ (Parquet verbatim no GCS)   │
 │  Fase 2  raw/ → filtra/molda → BigQuery Bronze      │
 └───────────────────────┬─────────────────────────────┘
                         ▼
 ┌─────────────────────────────────────────────────────┐
 │  dbt-bigquery  (dbt/)                               │
 │  Silver:  tipagem, dedup, IPCA chain index          │
 │  Gold:    denormalização, FX, deflação real          │
 │  core:    dim_date, dim_geo_br (conformadas)        │
 │  serving: marts pré-agregados (Pushdown Computing)  │
 └───────────────────────┬─────────────────────────────┘
                         ▼
 ┌─────────────────────────────────────────────────────┐
 │  Consumo (dois caminhos paralelos)                  │
 │  • Looker Studio (direto na tabela Gold)             │
 │  • Dashboard Dash @ Cloud Run — stateless           │
 │    filtros → SQL @param no serving + flask-caching  │
 │    curadoria: log append-only + SCD Tipo 2          │
 │    (UI em reconstrução · Claude Design System)       │
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
| Consumo / Visualização | Looker Studio · Dash @ Cloud Run | Dois caminhos paralelos sobre as mesmas tabelas Gold (ver seção Consumo) |
| Dashboard data access | `google-cloud-bigquery` + `flask-caching` | Pushdown Computing: filtros da UI → SQL `@param` no `serving`, resultados cacheados |

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
│   ├── serving/                      # ⭐ Data-access layer do dashboard (Pushdown)
│   │   ├── sql.py                    # SQL parametrizado (@param) + allowlist anti-injeção
│   │   ├── gateway.py                # fetch_* cacheados (flask-caching) sobre os marts
│   │   ├── cache.py                  # Instância flask-caching (SimpleCache/Redis)
│   │   ├── iap.py                    # Autor via header IAP → edited_by
│   │   └── curation.py               # Escritor append-only SCD2 + invalidação de cache
│   │
│   ├── ibge/                         # Pipeline IBGE PEVS
│   │   ├── client.py                 # HTTP client SIDRA API
│   │   └── pipeline.py               # Orquestração Bronze
│   │
│   ├── bcb/                          # Pipelines Banco Central
│   │   ├── client.py                 # HTTP client SGS API
│   │   ├── series.py                 # Pipeline SGS genérico (inflation/currency)
│   │   ├── inflation.py              # Spec IPCA/IGP-M/IGP-DI
│   │   └── currency.py               # Spec USD/EUR (CNY vem de fonte externa, não-BCB)
│   │
│   ├── comex/                        # Pipeline MDIC Comex Stat (CSV em massa)
│   │   ├── client.py                 # Downloader CSV (stream p/ disco + filtro)
│   │   ├── pipeline.py               # Orquestração Bronze (delta por fluxo×ano)
│   │   └── _ca.py                    # CA intermediária TLS vendorizada
│   │
│   └── comtrade/                     # Pipeline UN Comtrade (API JSON keyed, global)
│       ├── client.py                 # GET keyed; chave só no header; enumera reporters
│       └── pipeline.py               # Bronze chunked/resumível por (ano, batch de reporters)
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
│   │   │   ├── silver_bcb_currency.sql   # Câmbio BCB (USD/EUR diário PTAX)
│   │   │   ├── silver_extfx_currency.sql # Câmbio externo (CNY via ECB/seed)
│   │   │   ├── silver_currency.sql       # UNION BCB ∪ externo (lido pela Gold)
│   │   │   ├── silver_comex_flows.sql    # COMEX tipado + dedup (grão-fonte)
│   │   │   └── silver_comtrade_flows.sql # COMTRADE HS6, 4 regimes; só registro agregado (anti-dupla-contagem)
│   │   ├── gold/
│   │   │   ├── _gold.yml             # Schema + testes Gold
│   │   │   ├── gold_pevs_production.sql  # Gold IBGE PEVS (forma: production)
│   │   │   ├── gold_comex_flows.sql      # Gold COMEX (forma: flows, Brasil)
│   │   │   ├── gold_comtrade_flows.sql   # Gold COMTRADE (forma: flows, global bilateral)
│   │   │   ├── gold_commodity_crosswalk.sql  # Ponte cross-source (source,code)→commodity
│   │   │   └── gold_source_metadata.sql  # Proveniência por fonte (view; seam dataStore.meta)
│   │   │                                 # Novas fontes: gold_<fonte>_<forma>
│   │   ├── core/                     # ⭐ Dimensões conformadas (Pushdown Computing)
│   │   │   ├── _core.yml
│   │   │   ├── dim_date.sql          # Calendário (grão mês, rótulos pt-BR)
│   │   │   ├── dim_geo_br.sql        # 27 UFs → nome/região/abrev (N·NE·CO·SE·S)
│   │   │   └── dim_commodity_scd2.sql  # SCD Tipo 2 da curadoria (view; gated)
│   │   └── serving/                  # ⭐ Marts pré-agregados p/ o dashboard Dash
│   │       ├── _serving.yml
│   │       ├── serving_pevs_annual.sql
│   │       ├── serving_comex_annual.sql
│   │       ├── serving_comex_seasonality.sql
│   │       ├── serving_comtrade_annual.sql
│   │       └── serving_quality_by_source.sql
│   ├── macros/
│   │   ├── generate_schema_name.sql  # Dev/prod schema separation
│   │   ├── safe_numeric.sql          # Conversão segura (placeholders IBGE → NULL)
│   │   ├── data_quality_flag.sql     # Flag OK/MISSING_VALUE/etc.
│   │   ├── state_dimensions.sql      # Região/UF lookup
│   │   └── apply_dev_ttl.sql         # Auto-expiração de tabelas dev (7 dias)
│   ├── seeds/
│   │   ├── _seeds.yml                # Schema dos seeds
│   │   ├── historical_currency_factors.csv  # Fatores de reforma monetária
│   │   ├── comex_unit.csv            # Dimensão de unidade estatística (CO_UNID)
│   │   ├── comex_country.csv         # Dimensão de país (CO_PAIS → ISO/nome)
│   │   ├── comex_ncm.csv             # Dimensão de NCM (descrição PT, cap. 08+44)
│   │   ├── comex_via.csv             # Dimensão de modal de transporte (CO_VIA → PT)
│   │   ├── comtrade_country.csv      # Dimensão M49 → ISO3/nome (partnerAreas.json)
│   │   ├── comtrade_unit.csv         # Dimensão qtyUnitCode → label + família
│   │   ├── comtrade_hs.csv           # Dimensão HS (0801 + cap. 44; HS.json)
│   │   ├── commodity_crosswalk.csv   # Ponte cross-source (commodity ↔ pevs/ncm/hs6)
│   │   ├── product_unit_factors.csv  # Fator unidade-estatística → base (massa/volume) por NCM
│   │   ├── unit_family_conversions.csv  # Famílias de unidade e conversões (massa/volume)
│   │   └── extfx_cny_brl.csv         # BRL/CNY mensal (ECB; scripts/refresh_cny_seed.py)
│   └── tests/                        # Testes dbt customizados
│
├── tests/                            # Testes Python (pytest)
│   ├── test_cli.py                   # Testes do CLI
│   ├── test_config.py                # Testes de configuração
│   ├── test_ibge_client.py           # Testes do client IBGE (HTTP mockado)
│   ├── test_ibge_pipeline.py         # Testes do pipeline IBGE
│   ├── test_bcb_client.py            # Testes do client BCB
│   ├── test_bcb_series.py            # Testes do pipeline SGS genérico
│   ├── test_bcb_inflation_pipeline.py
│   ├── test_bcb_currency_pipeline.py
│   ├── test_bcb_pipeline.py
│   ├── test_comex_client.py          # Testes do downloader COMEX
│   ├── test_comex_pipeline.py        # Testes do pipeline COMEX (two-phase)
│   ├── test_comtrade_client.py       # Testes do client UN Comtrade
│   ├── test_comtrade_pipeline.py     # Testes do pipeline COMTRADE (chunked/resumível)
│   ├── test_core_http.py             # Testes dos primitivos HTTP compartilhados
│   ├── test_core_raw.py              # Testes da zona raw (land/read/provenance/marker)
│   ├── test_gcp_bigquery.py
│   ├── test_gcp_storage.py
│   ├── test_backup.py
│   ├── test_doctor.py
│   ├── test_monitor.py
│   ├── test_observability.py
│   └── test_observability_helpers.py
│
├── scripts/                          # Tooling auxiliar
│   ├── README.md                     # Documentação dos scripts
│   ├── setup_dev_env.py              # Setup unificado cross-platform
│   ├── test_setup.py                 # Testes do setup
│   ├── refresh_cny_seed.py           # Atualiza o seed extfx_cny_brl.csv (ECB)
│   ├── refresh_comtrade_country_seed.py  # Atualiza o seed comtrade_country.csv (M49)
│   ├── grant-sa-iam-roles.ps1        # IAM roles
│   ├── setup-claude-code-web-sa.sh   # SA para Claude Code Web
│   └── claude-hooks/                 # Hooks de segurança (block-dangerous-commands, protect-secrets)
│
├── docs/                             # Documentação detalhada
│   ├── adding_a_data_source.md       # Guia de extensão: adicionar uma nova fonte
│   ├── auth_architecture.md          # Arquitetura de autenticação (Cadeia de Confiança)
│   ├── cost_safety.md                # Budget alert + custom quota
│   ├── frontend_data_contract.md     # Contrato de dados Gold → frontend
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
- `silver_comex_flows`: **table** (dedup no grão-fonte completo via `qualify`, incl. modal `CO_VIA`; `safe_numeric` em VL_FOB/KG/QT/frete/seguro). Candidata a incremental se o volume do cap. 44 ao longo das décadas crescer.
- `silver_comtrade_flows`: **table**. Produtos no nível **HS6**; **4 regimes** (X/M/RX/RM → export/import/re-export/re-import). Mantém **só o registro totalmente agregado** (`motCode=0`/`customsCode=C00`/`partner2Code=0`/`mosCode=0`) — os breakdowns por modal/aduana/2º parceiro **somam no agregado**, então re-somá-los dupla-contaria (~2,5×). Dropa o partner World (`0`); sentinela de quantidade `0.0` → NULL.
- **Seed `historical_currency_factors`**: fator multiplicador que absorve reformas monetárias brasileiras (Cz$ → NCz$ → Cr$ → CR$ → R$). Sem ele, valores pré-1994 ficam 10⁶–10⁹× inflados.

### 3. Gold (dbt, `materialized=table`)

- Tabela do IBGE PEVS: `gold_pevs_production` — uma linha por `(reference_year, state_acronym, city_name, product_code)`.
- Tabela do MDIC COMEX: `gold_comex_flows` — uma linha por `(flow, reference_year, reference_month, ncm_code, country_code, state_acronym, transport_route_code)` (o modal `via` faz parte do grão; `via_name` via seed `comex_via`). As 4 convenções monetárias são aplicadas sobre `VL_FOB` (US$): `val_yearfx_*` no FX do mês de registro e `val_real_*` convertendo US$→BRL no FX do mês, deflacionando pela cadeia BCB e reconvertendo no FX atual (deflação **mensal**, não anual, por o grão ser mensal).
- Tabela da UN Comtrade: `gold_comtrade_flows` — comércio **global** bilateral, uma linha por `(flow, reference_year, reporter_code, partner_code, cmd_code)`. Mesmas 4 convenções sobre `primaryValue` (US$), mas deflação **anual** (FX médio do ano, índice de inflação fim-de-ano — como o PEVS) por o grão ser anual. Geografia bilateral: `reporter` + `partner` (ambos M49 → nome/ISO3). Sem dupla-contagem (World dropado no Silver), então `SUM` sobre partners é total bilateral verdadeiro.
- **Dimensão cross-source** (exceção ao "uma tabela por fonte"): `gold_commodity_crosswalk` — `(source, code) → commodity_id`, resolvido do seed `commodity_crosswalk` (vínculos por prefixo) contra os códigos reais das Gold. Liga a mesma commodity entre PEVS/COMEX/COMTRADE para as análises cross.
- **Metadados por fonte** (view): `gold_source_metadata` — uma linha por fonte com proveniência derivada do Gold (tabela, cadência, cobertura, contadores, `last_refresh`). Alimenta o seam `dataStore.meta(id)` do frontend; `implStatus`/`visible` são config de runtime (ver [docs/frontend_data_contract.md](docs/frontend_data_contract.md)).
- **Gold é por fonte, UMA tabela comprehensiva por fonte.** Nomenclatura: `gold_<fonte>_<forma>`, onde `<forma>` é o grão semântico — `production` (medição de saída produtiva, sem origem→destino; só o PEVS) ou `flows` (fluxo origem→destino; os bancos de comércio: COMEX, COMTRADE, NFe). Cada fonte tem sua própria linhagem consumindo as mesmas Silver de deflação/FX. O Gold é o **grão analítico comprehensivo** por fonte; agregações ad-hoc (Looker, exploração) saem dele via `GROUP BY` em tempo de query. **Para viabilizar o Pushdown Computing do dashboard Dash sem explodir custo e latência no BigQuery**, uma camada **`serving/`** materializa marts pré-agregados nos grãos exatos dos gráficos (ver [§ Camada Serving](#camada-serving--pushdown-computing-dashboard-dash)) — ela **deriva** do Gold, não o substitui. Grãos incompatíveis (mensal × país × HS code para COMEX, evento × UF para NFe) também justificam linhagens separadas — ver [docs/adding_a_data_source.md](docs/adding_a_data_source.md).
- Quatro convenções monetárias (aplicáveis a qualquer Gold monetária):
  - `val_yearfx_*` — valor nominal convertido pelo FX médio do ano. NULL para moedas estrangeiras pré-1994.
  - `val_real_{ipca,igpm,igpdi}_*` — valor deflacionado pela cadeia IPCA / IGP-M / IGP-DI, projetado para hoje. **Use esta coluna para comparações entre anos.**

### 4. Consumo

Dois caminhos paralelos, ambos lendo as mesmas tabelas Gold — não são exclusivos e podem coexistir:

- **Looker Studio** (no-code): conexão direta nas tabelas Gold (`gold.gold_pevs_production`, `gold.gold_comex_flows`). Bom para relatórios padronizados e exploração rápida sem deploy. Disponível agora.
- **Dashboard dedicado (Dash) no Cloud Run — stateless, Pushdown Computing**: frontend sob medida para os pesquisadores (UI em reconstrução com o Claude Design System). **Não** carrega tabelas Gold em memória (Pandas) atrás de um lock global — esse desenho foi descartado por risco de OOM e concorrência. Traduz cada filtro da UI em **SQL parametrizado** (`@param`) sobre a camada **`serving`** (marts pré-agregados), com **flask-caching** nos resultados; a curadoria usa um **log append-only + SCD Tipo 2** (ver §§ [Camada Serving](#camada-serving--pushdown-computing-dashboard-dash) e [Curadoria dinâmica](#curadoria-dinâmica--log-append-only--scd-tipo-2)). A data-access layer (BFF) já vive em [`src/embrapa_commodities/serving/`](../src/embrapa_commodities/serving/); o Dockerfile/Cloud Run e os componentes de UI chegam com o handoff do Design System.

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

## Camada Serving — Pushdown Computing (dashboard Dash)

> **Pivô arquitetural (2026-06).** O dashboard Dash **não** carrega tabelas Gold
> inteiras em memória (Pandas) atrás de um `threading.Lock()` global — desenho
> descartado por risco de OOM e falhas de concorrência. O Cloud Run é
> **stateless**: a UI traduz cada filtro em **SQL parametrizado** (`@param`)
> executado pelo BigQuery, e o resultado (pequeno) é cacheado por `flask-caching`.

**Por que uma camada `serving/`.** Pushdown ingênuo direto no Gold varreria
gigabytes a cada filtro. Para viabilizar custo e latência, `dbt/models/serving/`
materializa **marts pré-agregados nos grãos exatos dos gráficos** (mapeados em
[`docs/frontend_data_contract.md`](docs/frontend_data_contract.md)), reduzindo o
scan de **GB → MB**. São **tabelas**, não views: uma view sobre o Gold
re-varreria o fato inteiro a cada query e não economizaria nada — o ganho vem da
pré-agregação materializada, particionada por ano e clusterizada pelos filtros.

| Mart (`serving`) | Grão | Alimenta |
|---|---|---|
| `serving_pevs_annual` | ano × UF × produto × família | overviewTS · productTS · ufData (PEVS) |
| `serving_comex_annual` | ano × flow × NCM × UF × país | overview · produto · UF · partner · flow (COMEX) |
| `serving_comex_seasonality` | ano × mês × flow × NCM | monthlyData / sazonalidade |
| `serving_comtrade_annual` | ano × flow × cmd × reporter × partner | partner · flow · market-share (COMTRADE) |
| `serving_quality_by_source` | fonte × data_quality_flag | donut de qualidade |

**Dimensões conformadas** (`dbt/models/core/`): `dim_date` (grão mês, rótulos
pt-BR, quarter/semestre) e `dim_geo_br` (27 UFs → nome / região / abreviação
N·NE·CO·SE·S) são a **fonte única** dos joins do serving. Ficam no dataset Gold
(são insumos de *build* assados nos marts, não lidos ao vivo pela UI). Os marts
carregam `commodity_id` (via `gold_commodity_crosswalk`) para o LEFT JOIN ao vivo
com a dimensão de curadoria.

**Dataset próprio + menor privilégio.** Os marts vivem no dataset `serving`
(`BQ_SERVING_DATASET`), separado do Gold, para que a SA do dashboard
(`sa-web-dashboard-prod`) seja escopada **apenas** à superfície de serving.

**Camada de acesso a dados (Python).** [`src/embrapa_commodities/serving/`](../src/embrapa_commodities/serving/)
é o BFF **UI-agnóstico** que o Dash importa — **sem páginas/charts** (esses chegam
no handoff do Design System):

- `sql.py` — construtores de SQL **parametrizado** (`@param`); a coluna de medida
  (que não pode ser bind param) passa por uma **allowlist** contra injeção.
- `gateway.py` — funções `fetch_*` **cacheadas** (`@cache.memoize()`) que rodam os
  marts. Sem DataFrame Pandas global, sem lock — o estado mora no BigQuery.
- `cache.py` — instância `flask-caching`. ⚠️ **Multi-instância:** `SimpleCache` é
  por processo; para a invalidação de curadoria propagar entre instâncias no
  Cloud Run, use `CACHE_TYPE=RedisCache` (Memorystore).
- `iap.py` — extrai o autor do header **IAP** (`edited_by`).
- `curation.py` — escritor append-only da curadoria (abaixo).

**Política de cache.** Marts mudam **só** no rebuild dbt noturno → cache por
**TTL** (`CACHE_DEFAULT_TIMEOUT`). A classificação da curadoria **pode** mudar
entre rebuilds → cache **explicitamente invalidado** na escrita.

---

## Curadoria dinâmica — log append-only + SCD Tipo 2

Pesquisadores reclassificam commodities (estágio de processamento: `in_natura`,
`beneficiado`, `semi_processado`, `industrializado`, …) pelo painel de curadoria.
O fluxo **nunca sobrescreve o Gold**:

1. **Escrita (botão "Salvar").** `serving.curation.record_processing_stage` anexa
   **uma linha imutável** a `research_inputs.commodity_processing_stage_log` (DML
   `INSERT` parametrizado — consistente para leitura imediata). O autor vem do
   header **IAP** `X-Goog-Authenticated-User-Email` na coluna `edited_by` — toda
   edição é atribuível a uma pessoa, nunca à Service Account. Em seguida o cache
   da classificação é invalidado. A tabela é **auto-criada**
   (`ensure_curation_log_table`, padrão da casa).
2. **Histórico (SCD Tipo 2).** A view `dim_commodity_scd2` (`dbt/models/core/`)
   deriva, por commodity, `valid_from` / `valid_to` / `is_current` via
   `lead(edited_at)` sobre o log. É uma **view**, não tabela: um `INSERT` novo
   aparece para a UI **na hora**, sem rebuild dbt. Fica gated por
   `--vars 'enable_curation: true'` (ative quando o log existir, para o build
   default permanecer verde até lá).
3. **Leitura (UI).** O dashboard faz **LEFT JOIN ao vivo** entre a **Serving View
   estática** (mart pré-agregado, pesado, com `commodity_id`) e a
   `dim_commodity_scd2` **viva** (leve), filtrando `is_current` para "agora" — ou
   `valid_from <= as_of < valid_to` para reconstruir como a commodity estava
   classificada em uma data passada (rastreabilidade).

```
"Salvar" ─► INSERT append-only ─► research_inputs.commodity_processing_stage_log
                                              │  (lead() → valid_from/valid_to/is_current)
                                              ▼
   Serving mart (estático)  ──LEFT JOIN ao vivo──►  dim_commodity_scd2 (view)
   por commodity_id                                  is_current = true
```

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

> A SA `sa-web-dashboard-prod` é a **runtime do dashboard stateless no Cloud Run**. Com o Pushdown Computing ela é escopada a **menor privilégio**: `roles/bigquery.dataViewer` **apenas no dataset `serving`** (marts + `dim_commodity_scd2`) — não no Gold inteiro — mais `roles/bigquery.jobUser` para executar as queries, e `roles/bigquery.dataEditor` no dataset `research_inputs` para o `INSERT` append-only da curadoria. O dashboard fica **atrás do IAP**, que injeta `X-Goog-Authenticated-User-Email` (origem do `edited_by` auditável). Está dormente enquanto a UI é reconstruída no Claude Design System. O **Looker Studio não usa esta SA** — consome a Gold via OAuth do usuário final (caminho de consumo independente).

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

## Orquestração da ingestão (Cloud Run Job + Cloud Scheduler)

O CLI `embrapa ingest all` é empacotado como um **Cloud Run Job** — **não** um
Service. A distinção é deliberada:

| | **Job** (ingestão) | **Service** (dashboard Dash) |
|---|---|---|
| Natureza | batch, efêmero — roda até concluir e encerra | stateless, sempre-on, escala a zero |
| Porta HTTP | não | sim (Gunicorn) |
| Disparo | **Cloud Scheduler** (cron) | requisição do usuário (atrás de IAP) |

Um **Cloud Scheduler** dispara o Job **nas madrugadas** (ex.: cron diário em
horário de baixa contenção, fora da janela de análise). A execução
não-supervisionada é segura porque a resiliência atual já absorve as falhas
típicas de uma fonte pública:

- **`tenacity`** via `core.http.http_retry_policy` (`stop_after_attempt(5)` +
  `wait_exponential` + drain sob deadline wall-clock) reabsorve transitórias
  (HTTP 5xx, timeouts, slow-byte).
- **BCB é delta por padrão** (janela de overlap) — absorve revisões sem re-puxar
  o histórico; COMEX re-baixa só quando o ETag muda; COMTRADE é resumível por
  cota diária. Reexecutar o Job é idempotente o suficiente para um cron cego.
- Falha total emite evento (base para a notificação de falha do ROADMAP).

> **Artefatos** em [`deploy/ingestion/`](deploy/ingestion/): `Dockerfile` (imagem
> do Job — distinta do Dockerfile do dashboard *Service*), `cloudbuild.yaml`,
> `deploy.sh` (build + cria/atualiza o Job lendo o `.env`) e `schedule.sh` (cria/
> atualiza o trigger do Scheduler). Atalhos: `make ingest-job-deploy` e
> `make ingest-job-schedule`. O deploy efetivo (rodar os scripts no projeto GCP) é
> passo do operador — o backend que eles invocam (`embrapa ingest all`) já está
> pronto e é o mesmo caminho testado localmente.

---

## Documentação Relacionada

Índice completo de toda a documentação do projeto (root + `docs/`) disponível no [`README.md`](README.md#-documentação).
