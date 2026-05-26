# TODO — Embrapa Commodities Dashboard

> Lista macro de tarefas pendentes e concluídas do projeto.
> Atualizada manualmente conforme o progresso do desenvolvimento.

---

## ✅ Concluídas

- [x] Pipeline Medallion completo (Bronze → Silver → Gold)
- [x] Ingestão IBGE PEVS via API SIDRA
- [x] Ingestão BCB (inflação IPCA/IGP-M/IGP-DI + câmbio USD/EUR/CNY)
- [x] Delta ingestion para pipelines BCB (apenas novos dados)
- [x] Ingestão IBGE em chunks (`ibge-batch --chunk-years`)
- [x] Cadeia IPCA chain index (Silver) para deflação histórica
- [x] Seed `historical_currency_factors` para reformas monetárias
- [x] Separação dev/prod nos schemas dbt (`dbt_dev_*` vs `silver`/`gold`)
- [x] Auto-expiração de tabelas dev (7 dias via `apply_dev_ttl`)
- [x] CLI unificado com Typer (`embrapa ingest|discover|dbt|doctor|backup-gold`)
- [x] Dockerfile multi-stage (builder + runtime non-root)
- [x] Deploy Cloud Run com IAM (`--no-allow-unauthenticated`)
- [x] Dashboard Dash + Plotly (multi-page)
- [x] Service Account Impersonation (OAuth, sem keyfiles)
- [x] Pre-commit hooks (gitleaks + ruff + file-hygiene)
- [x] CI/CD GitHub Actions (lint + test + dbt parse)
- [x] Smoke test do dashboard (live BQ)
- [x] Visual check com Playwright (headless screenshots)
- [x] Backup Gold → GCS (`embrapa backup-gold`)
- [x] `embrapa doctor` para diagnóstico de saúde
- [x] Soft 500-LOC ceiling para módulos do dashboard
- [x] Setup automatizado cross-platform (`setup.sh`, `setup.bat`, `setup.ps1`)
- [x] Documentação de setup, IAM, cost safety, auth, ownership transfer

---

## 🔲 Pendentes

Tarefas pendentes estão priorizadas por horizonte temporal no [`ROADMAP.md`](ROADMAP.md).

Para o registro histórico de features entregues por versão, veja o [`CHANGELOG.md`](CHANGELOG.md).

---

> 💡 Para detalhes de features complexas, consulte o diretório [`PLANS/`](PLANS/).

