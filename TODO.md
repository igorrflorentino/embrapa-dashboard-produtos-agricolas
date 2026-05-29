# TODO — Embrapa Commodities Dashboard

> Lista macro de tarefas pendentes e concluídas do projeto.
> Atualizada manualmente conforme o progresso do desenvolvimento.

---

## ✅ Concluídas

### Backend (pipeline de dados)
- [x] Pipeline Medallion completo (Bronze → Silver → Gold)
- [x] Ingestão IBGE PEVS via API SIDRA
- [x] Ingestão BCB (inflação IPCA/IGP-M/IGP-DI + câmbio USD/EUR/CNY)
- [x] Delta ingestion para pipelines BCB (apenas novos dados)
- [x] Ingestão IBGE em chunks (`ibge-batch --chunk-years`)
- [x] Cadeia IPCA chain index (Silver) para deflação histórica
- [x] Seed `historical_currency_factors` para reformas monetárias
- [x] Separação dev/prod nos schemas dbt (`dbt_dev_*` vs `silver`/`gold`)
- [x] Auto-expiração de tabelas dev (7 dias via `apply_dev_ttl`)
- [x] CLI unificado com Typer (`embrapa ingest|discover|dbt|doctor|backup-gold|monitor`)
- [x] Service Account Impersonation (OAuth, sem keyfiles)
- [x] Pre-commit hooks (gitleaks + ruff + file-hygiene)
- [x] CI/CD GitHub Actions (lint + test + dbt parse)
- [x] Backup Gold → GCS (`embrapa backup-gold`, introspectivo por prefixo)
- [x] `embrapa doctor` para diagnóstico de saúde
- [x] Observabilidade JSONL + `embrapa monitor` (IBGE e BCB)
- [x] Setup automatizado cross-platform (`setup.sh`, `setup.bat`, `setup.ps1`)
- [x] Documentação de setup, IAM, cost safety, ownership transfer
- [x] Convenção Gold `gold_<fonte>_<forma>` + uma tabela comprehensiva por fonte
- [x] Terreno pronto para multi-fonte (registries `cli.INGESTS` / `doctor.*`, `core/`, guia `adding_a_data_source.md`)

### Camada de visualização

> A UI Dash + Plotly e o deploy Cloud Run **foram entregues na v0.1.0 e removidos
> em 2026-05-29** para reconstrução no Claude Design System (ver [`CHANGELOG.md`](CHANGELOG.md)).
> Não são "pendências" nem "concluídas" — são um caminho de consumo **em
> reconstrução**. O backend já alimenta os **dois caminhos paralelos** de
> consumo (Looker Studio + dashboard Dash/Cloud Run); ver [`ARCHITECTURE.md`](ARCHITECTURE.md) § Consumo.

- [x] Consumo via **Looker Studio** (conexão direta na Gold) — disponível
- [ ] **Dashboard dedicado (HTML/CSS + Dash) no Cloud Run** — em reconstrução (Claude Design System); reintroduz Dockerfile + deploy Cloud Run + SA read-only

---

## 🔲 Pendentes

Tarefas pendentes estão priorizadas por horizonte temporal no [`ROADMAP.md`](ROADMAP.md).

Para o registro histórico de features entregues por versão, veja o [`CHANGELOG.md`](CHANGELOG.md).

---

> 💡 Para detalhes de features complexas, consulte o diretório [`PLANS/`](PLANS/).

