# Changelog

Todas as mudanças notáveis do projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

### Changed
- **Quantidades por família de unidade física (quebra de schema, sem
  retrocompat).** O formato fixo `[kg, t, m³, L]` foi removido. Toda linha de
  quantidade na Gold passa a expor `family` (`massa`|`volume`|`energia`|
  `contagem`|`area`|`desconhecida`), `unit_native` (rótulo da fonte), `qty_native`
  (valor nativo), `qty_base` (convertido para a unidade-base da família) e
  `base_unit` (`t`/`m³`/`MWh`/`un`/`ha`). A conversão acontece no **Silver**
  (Gold já entrega no formato final). **`gold_pevs_production`** troca
  `quantity_tons`/`quantity_m3` por essas colunas; **`gold_comex_flows`** troca
  `stat_unit`/`stat_unit_symbol`/`statistical_quantity` por
  `unit_native`/`unit_native_symbol`/`qty_native`+`qty_base`+`family`+`base_unit`
  (a resolução da unidade estatística migrou do Gold para o Silver;
  `net_weight_kg` segue como massa-kg paralela). **Regra:** nunca somar
  `qty_base` entre famílias — toda agregação exige `GROUP BY family` (monte
  `q_by_family = {massa:Σt, volume:Σm³, …}` em tempo de consulta). Valor
  monetário continua família-agnóstico e somável.
  - Novos seeds versionados: **`unit_family_conversions`** (unidade →
    família + `to_base`, fonte única — sem fator hard-coded em query) e
    **`product_unit_factors`** (crosswalk produto→fator para unidades de
    commodity como saca/@/bushel/barril, que sobrepõe o seed genérico; sem
    linha → `qty_base` nulo, marcado para curadoria — nunca conversão inventada).
  - `data_quality_flag` reassinado para `(qty, val_brl)`. Novo teste de
    curadoria (warn) `assert_unconvertible_quantities_for_curation` e um
    **dbt unit test** com um caso por família + override do crosswalk.
  - ⚠️ **Operacional:** `silver_ibge_pevs` é incremental — rode
    `dbt build --select silver_ibge_pevs+ --full-refresh` (dev **e** prod) ao
    aplicar esta mudança, senão as partições antigas ficam com as colunas novas
    nulas.

### Fixed
- **Séries de câmbio do BCB corrigidas (afetava PEVS e COMEX).** As séries
  configuradas estavam erradas: `3694` (USD) é **anual** — insuficiente para a
  deflação mensal do COMEX (só preenchia janeiros); `4393` (EUR) retornava
  ~127 e `20542` (CNY) ~4 milhões — **não são cotações BRL/unidade**. Trocadas
  por PTAX **venda diária**: `1`=USD, `21619`=EUR (a Gold faz a média por ano/
  mês). A **CNY foi removida** — o BCB não publica BRL/CNY (nem USD/CNY) no SGS
  ou PTAX; uma coluna de iuan exigiria fonte externa (follow-up). Isso conserta
  `val_yearfx_{brl,usd,eur}` e `val_real_*_{brl,usd,eur}` em
  `gold_pevs_production` **e** `gold_comex_flows`.
- **`bcb/client`: HTTP 404 do SGS tratado como janela sem dado**, não erro —
  séries têm datas de início diferentes (USD 1984, EUR 1999), então o
  year-chunking do `--full` consulta janelas que antecedem algumas séries.
  Antes, um `--full` de `BCB_START_YEAR` quebrava com 404 na primeira janela
  vazia.

### Added
- **Dimensões de referência do COMEX — rótulos legíveis na `gold_comex_flows`.**
  Três seeds das tabelas auxiliares do MDIC (`bd/tabelas/`): `comex_unit`
  (`NCM_UNIDADE.csv` → unidade estatística, ex. `16`=METRO CUBICO, `10`=
  QUILOGRAMA LIQUIDO), `comex_country` (`PAIS.csv` → ISO-3 + nome PT) e
  `comex_ncm` (`NCM.csv`, filtrado p/ castanha `0801*` + cap. 44 → descrição PT).
  A `gold_comex_flows` ganha colunas legíveis via `ref()`: `ncm_description`,
  `country_name`/`country_iso_a3`, `stat_unit`/`stat_unit_symbol` — 100% de
  cobertura dos dados atuais. Esclarece a semântica de quantidade: `net_weight_kg`
  é sempre kg (comparável entre produtos); `statistical_quantity` é na unidade do
  NCM (m³ p/ a maioria da madeira, kg p/ castanha) — não somar entre unidades
  diferentes.

### Changed
- **Ingestão two-phase com zona `raw/` — padronizada em TODAS as fontes.**
  Toda fonte agora segue **extract→raw→bronze**: a Fase 1 arquiva o extrato
  *verbatim* no GCS (`raw/<source>/<dataset>/<basename>.parquet`, com metadata de
  proveniência — URL, ETag/Last-Modified, `fetched_at`, `rows`); a Fase 2 lê o
  raw de volta, filtra/molda e carrega o Bronze. Re-filtrar, mudar produtos/regras
  ou re-derivar o Bronze **não re-bate na fonte** — só uma revisão real do dado
  dispara re-fetch. Novo primitivo `core/raw.py` (`land_raw`/`land_raw_file`/
  `read_raw`/`download_raw`/`list_raw`/`raw_provenance`) + `GCS_RAW_PREFIX`.
  - **COMEX:** Fase 1 baixa o CSV→Parquet completo (todos NCM) e re-baixa **só
    quando o ETag mudou** (pega revisões de qualquer ano, não só o corrente);
    Fase 2 filtra o raw via `iter_batches`. `--from-raw` re-filtra sem internet.
  - **IBGE:** Fase 1 arquiva a resposta SIDRA; Fase 2 carrega o Bronze.
  - **BCB:** cada janela delta vira um objeto raw carimbado por run (trilha
    append-only); `--from-raw` reconstrói o Bronze relendo a trilha.
  - Todo `embrapa ingest <source>` ganha `--from-raw`. O primitivo morto
    `core/bronze.land_and_load` foi removido (todas as fontes usam o novo fluxo).
    Plano: `PLANS/raw_zone_architecture.md`. dbt/Silver/Gold inalterados.

### Added
- **Fonte COMEX (MDIC Comex Stat) — pipeline Bronze→Silver→Gold completo.**
  Nova fonte de *comércio exterior* (a primeira da forma `flows` —
  origem→destino), cruzando produção × comércio × câmbio × inflação do mesmo
  produto. Escopo: export **e** import, castanha-do-brasil (NCM `08012100`/
  `08012200`) + capítulo 44 inteiro (madeira/carvão), no grão mês×NCM×país×UF.
  - **Bronze (`src/embrapa_commodities/comex/`):** `client.py` baixa os CSVs
    anuais em massa do Comex Stat (`EXP_<ano>.csv`/`IMP_<ano>.csv`; `;`/latin-1)
    — *stream para disco* (arquivos de 100+ MB), parse pandas em chunks, filtro
    coluna-preciso em `CO_NCM`/`CO_NCM[:2]`. EXP (11 col) e IMP (13 col: +
    `VL_FRETE`/`VL_SEGURO`) unificados em schema-union (export grava NULL nas
    duas). **NÃO** usa a API JSON (retornava o total Brasil agregado em filtro
    malformado, HTTP 200). `pipeline.py` tem `run()` próprio com delta por
    `(fluxo, ano)` (re-busca o ano corrente, pula anos já em Bronze). Comando
    `embrapa ingest comex` multi-chunk (eventos por `(fluxo, ano)` no monitor);
    registrado em `cli.INGESTS`, `doctor.SOURCE_CHECKS` (`_check_comex`) e
    `doctor.BRONZE_TARGETS`. Config `COMEX_*` em `config.py`/`.env.example`.
  - **TLS:** o host `balanca.economia.gov.br` omite a CA intermediária do
    handshake (`requests`/certifi falha; curl passa via AIA). A intermediária
    pública (Sectigo R36) está vendorizada em `comex/_ca.py` e anexada ao bundle
    do certifi em runtime — **sem desabilitar verificação**.
  - **Silver/Gold (dbt):** `silver_comex_flows` (dedup no grão-fonte completo);
    `gold_comex_flows` (UMA tabela comprehensiva `flows`, grão
    flow×mês×NCM×país×UF, agregação por `GROUP BY` em query). Aplica as 4
    convenções monetárias sobre `VL_FOB` (US$): `val_yearfx_*` no FX do mês e
    `val_real_{ipca,igpm,igpdi}_*` (US$→BRL no FX do mês → índice BCB → hoje).
  - Cobertura: `tests/test_comex_client.py` + `tests/test_comex_pipeline.py`;
    testes de schema em `_silver.yml`/`_gold.yml`. Plano em
    `PLANS/comex_flows.md`.
- **`core/bronze.py` — primitivo de aterrissagem Bronze compartilhado (D4).**
  Nova função `land_and_load(df, *, settings, storage_client, bq_client, source,
  table, object_basename, destination, schema, clustering_fields, ...)`
  encapsula a cauda idêntica dos três pipelines Bronze: `ensure_bucket` → upload
  Parquet em `landing/<fonte>/<tabela>/run=<ts>/<basename>.parquet` →
  `load_dataframe` (com partition/cluster keys). IBGE, `bcb/inflation` e
  `bcb/currency` agora delegam — cada `run()` mantém só o que é específico da
  fonte (construção de clients, `ensure_dataset` antes do extract, o
  short-circuit de fetch vazia, e o `observability.emit` do IBGE). `run_id` é
  parametrizável para o IBGE compartilhar o instante entre a coluna
  `ingestion_timestamp` e o caminho `run=`. Análogo ao D1 (`core/http.py`):
  primitivo source-agnostic, composto pelas fontes; `ensure_dataset` fica de
  fora porque o BCB precisa do dataset *antes* do extract (lookup delta).
  Comportamento observável preservado. Cobertura: 5 testes novos em
  `tests/test_core_bronze.py`; os testes de pipeline existentes seguem verdes
  após reapontar os patch targets de `upload`/`load`/`ensure_bucket` para
  `core.bronze`.
- **`core/http.py` — primitivos HTTP compartilhados (D1).** Nova fábrica
  `http_retry_policy(transient_exc, deadline_s, max_attempts=5, before_sleep=None)`
  e helper `get_drained(url, *, total_deadline_s, transient_exc, context, ...)`
  encapsulam a política de retry tenacity e o drain manual do body sob deadline
  wall-clock (defesa slow-byte) que antes estavam duplicados nos clients IBGE e
  BCB. Constantes compartilhadas: `DEFAULT_TIMEOUT`, `DEFAULT_HEADERS`,
  `RETRYABLE_STATUS_CODES`. Comportamento observável preservado byte-a-byte —
  deadlines source-specific (75s/180s no IBGE, 60s/120s no BCB) permanecem nos
  clients; lógica defensiva única (period-halving do IBGE, year-chunking do
  BCB) também não migrou. Cobertura: 11 testes novos em
  `tests/test_core_http.py` (inclui o slow-byte deadline test migrado de
  `test_ibge_client.py`) + 2 "delegate" tests assertando os kwargs passados ao
  `get_drained` em cada client.
- **Observabilidade de retry no client BCB (D1.1).** O `_fetch_window` agora
  cabeia um hook `before_sleep=_emit_retry` na política tenacity, simétrico ao
  IBGE — os retries de séries SGS passam a emitir um evento `retry`
  (`series`, `window`, `attempt`, `reason`) que aparece no `embrapa monitor`.
  Diferente do IBGE (que usa contextvar porque a UF vive um frame acima), o
  contexto `(code, window)` vem direto de `retry_state.args`, já que a própria
  `_fetch_window` é a função retried. Cobertura: teste da lógica do hook +
  guard de regressão da fiação (`before_sleep`).

### Changed
- **Pipelines BCB inflation/currency colapsados em `bcb/series.py`.** Os dois
  pipelines eram ~90% idênticos (`_extract`, `_effective_start_year`, `run`);
  agora compartilham um pipeline genérico de série SGS parametrizado por um
  `BcbSeriesSpec` (`kind`, `label_column`, `series_map`, `table`, `schema`, e a
  única linha genuinamente source-specific — `overlap_start_year(last) -> int`).
  `bcb/inflation.py` e `bcb/currency.py` viraram shims finos definindo seu spec
  e delegando. Entry points públicos (`inflation.run`/`currency.run`),
  constantes (`DELTA_OVERLAP_MONTHS`, `BRONZE_SCHEMA`) e o comportamento
  observável preservados. **Reverte deliberadamente** a antiga nota de
  `docs/adding_a_data_source.md` ("não extraia `_effective_start_year`"):
  vista de perto, a diferença era uma linha, hoje um knob `Callable`. O doc foi
  atualizado para orientar séries SGS a usar o spec, e fontes de shape
  diferente a escreverem o próprio `run()`. Testes consolidados: a duplicação
  dos dois arquivos de teste virou um `tests/test_bcb_series.py` parametrizado
  sobre os dois specs + dois arquivos por-variante finos (contrato do spec).
- **Gold renomeada `gold_commodity_matrix` → `gold_pevs_production`**, adotando a
  convenção `gold_<fonte>_<forma>` (`production` para medição de saída como PEVS;
  `flows` para fluxo origem→destino dos bancos de comércio futuros). Reforça a
  regra de **uma tabela Gold comprehensiva por fonte** (sem siblings
  pré-agregadas; agregação em tempo de query — simplicidade sobre eficiência).
  **Ação externa necessária:** reapontar a fonte do Looker Studio para
  `gold.gold_pevs_production` e dropar a tabela órfã `gold.gold_commodity_matrix`
  no prod após o próximo `make dbt-build-prod` (ver `docs/migration_history.md`).

### Fixed
<!-- Correções de bugs -->

### Removed
- **Camada de UI Dash + Plotly removida (2026-05-29).** O frontend está sendo
  reconstruído com o Claude Design System em fluxo separado. Foram apagados:
  o pacote `src/embrapa_commodities/dashboard/`, os testes
  `tests/test_dashboard_*`, os scripts `scripts/dashboard_*` /
  `scripts/check_dashboard_size.py` / `scripts/dashboard-*.ps1`, o
  `Dockerfile`, o workflow `.github/workflows/dashboard-smoke.yml`, o
  `docs/auth.md` e os skills do Claude Code `run-dashboard`,
  `dash-page-scaffold`, `new-chart-component`, `deploy-cloud-run`. Os extras
  `dashboard` e `visual` em `pyproject.toml`, o hook `check-dashboard-size`
  em `.pre-commit-config.yaml`, o `--extra dashboard` em `ci.yml` e os
  alvos `dashboard-*` / `test-smoke` no `Makefile` também foram retirados.
  Backend (pipeline Medallion + dbt + CLI `embrapa`) permanece 100%
  funcional. O próximo handoff fará a junção do novo design system com
  este backend.

---

## [0.1.0] — 2026-05-26

> Release inicial — pipeline Medallion funcional end-to-end.

### Added

- **Pipeline de ingestão IBGE PEVS** via API SIDRA com suporte a múltiplos produtos e períodos.
- **Pipeline de ingestão BCB** (inflação IPCA/IGP-M/IGP-DI + câmbio USD/EUR/CNY) via API SGS.
- **Delta ingestion** para BCB — apenas dados novos são buscados por padrão.
- **Ingestão em chunks** (`ibge-batch --chunk-years`) para janelas históricas grandes.
- **Camada Silver (dbt)**: tipagem, dedup, cadeia IPCA chain index.
- **Seed `historical_currency_factors`**: absorve reformas monetárias brasileiras (1942–1994).
- **Camada Gold (dbt)**: tabela `gold_commodity_matrix` com 22 colunas denormalizadas.
- **Tabelas Gold agregadas**: `gold_commodity_state_year`, `gold_commodity_year_product`.
- **CLI unificado** com Typer: `embrapa ingest|discover|dbt|doctor|backup-gold`.
- **Dashboard web** com Dash + Plotly (multi-page), deploy via Cloud Run.
- **Dockerfile multi-stage** com imagem slim, non-root, Gunicorn.
- **Service Account Impersonation** (OAuth 2.0) — sem keyfiles distribuídos.
- **Quatro Service Accounts** com separação de responsabilidades (reader, pipeline, dashboard, AI).
- **Backup Gold → GCS** (`embrapa backup-gold`, `make dbt-build-prod-with-backup`).
- **`embrapa doctor`**: diagnóstico de saúde do ambiente.
- **Separação dev/prod** nos schemas dbt com auto-expiração de tabelas dev (7 dias).
- **CI/CD**: GitHub Actions com lint (Ruff), test (pytest), dbt parse.
- **Pre-commit hooks**: gitleaks, ruff, file-hygiene, dashboard size ceiling (500 LOC).
- **Smoke test** do dashboard com BQ real.
- **Visual check** com Playwright (headless screenshots → `artifacts/`).
- **Setup automatizado** cross-platform: `setup.sh`, `setup.bat`, `setup.ps1`.
- **Documentação completa**: setup, IAM, auth, cost safety, ownership transfer, testing.

---

<!-- Template para novas versões:

## [X.Y.Z] — YYYY-MM-DD

### Added
### Changed
### Fixed
### Removed
### Security
### Deprecated

-->
