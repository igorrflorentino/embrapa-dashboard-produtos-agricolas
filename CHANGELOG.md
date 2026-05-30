# Changelog

Todas as mudanças notáveis do projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

### Added
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
