# Changelog

Todas as mudanças notáveis do projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

### Added
<!-- Novas features que ainda não foram lançadas -->

### Changed
<!-- Mudanças em features existentes -->

### Fixed
<!-- Correções de bugs -->

### Removed
<!-- Features ou código removido -->

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
