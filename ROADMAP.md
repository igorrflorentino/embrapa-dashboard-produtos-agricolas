# Roadmap — Embrapa Commodities Dashboard

> Visão de futuro do projeto. Metas organizadas por horizonte temporal.
> Este documento é atualizado conforme o projeto evolui.

---

## 🟢 Curto Prazo (1–3 meses)

Foco: **estabilização, observabilidade e automação básica**.

### Pipeline & Dados
- [ ] **Orquestração da ingestão**: empacotar `embrapa ingest all` como **Cloud Run Job** (batch, não Service) disparado por **Cloud Scheduler** nas madrugadas — aproveitando a resiliência atual com `tenacity` (retry/slow-byte) e o modo delta do BCB/COMEX. Ver [ARCHITECTURE § Orquestração da ingestão](ARCHITECTURE.md#orquestração-da-ingestão-cloud-run-job--cloud-scheduler).
- [ ] Notificações de falha de ingestão (email ou Slack webhook)
- [ ] Integrar SQLFluff no CI (atualmente rodado manualmente)
- [ ] Testes de integridade end-to-end (row counts Bronze → Silver → Gold)

### Visualização (dois caminhos paralelos)

> O Gold é consumido por **Looker Studio** (no-code, direto na Gold) **e** por um
> **dashboard dedicado Dash + HTML/CSS no Cloud Run** (em reconstrução no Claude
> Design System). Os itens abaixo aplicam-se ao dashboard dedicado; o Looker cobre
> o caminho no-code em paralelo. Ver [`ARCHITECTURE.md`](ARCHITECTURE.md) § Consumo.

- [x] **Pushdown Computing** — dashboard **stateless**: filtros da UI → SQL `@param` na camada `serving`, com `flask-caching` (TTL) nos resultados. Substitui o desenho in-memory/Pandas (risco de OOM/concorrência). Backend (BFF) já em [`src/embrapa_commodities/serving/`](src/embrapa_commodities/serving/).
- [x] **Curadoria dinâmica (SCD Tipo 2)** — log append-only `commodity_processing_stage_log` + view `dim_commodity_scd2` (`lead()`); LEFT JOIN ao vivo na UI; autor via header IAP. Sem sobrescrever o Gold.
- [ ] Componentes de UI da curadoria + export CSV/Excel (chegam com o handoff do Design System)
- [ ] Melhorias de UX baseadas em feedback de pesquisadores

### Qualidade
- [ ] Aumentar cobertura de testes para ≥ 80%
- [ ] Testes de contrato para APIs externas (IBGE SIDRA, BCB SGS)
- [ ] Runbook de operações / troubleshooting

### Documentação
- [ ] Documentar API do CLI (geração automática via `embrapa --help`)
- [ ] Diagrama ER do modelo de dados Gold
- [ ] Guia de onboarding para novos contribuidores

---

## 🟡 Médio Prazo (3–6 meses)

Foco: **novas fontes de dados, IaC e melhorias de dashboard**.

### Novas Fontes de Dados
- [ ] CONAB — preços e custos de produção
- [ ] CEPEA — indicadores de preços agrícolas
- [ ] FAO — dados internacionais de produção para benchmarking
- [ ] Expandir cobertura de produtos IBGE (além de extrativismo vegetal)

### Infraestrutura
- [ ] Terraform / Pulumi para provisionamento do projeto GCP (IaC)
- [ ] Workload Identity Federation para CI/CD (eliminar secrets)
- [ ] Ambiente de staging separado (entre dev local e prod)
- [ ] Pipeline de deploy automatizado (CI/CD → Cloud Run)

### Dashboard
- [ ] Página de comparação entre produtos
- [ ] Mapas geográficos interativos (choropleth por estado/município)
- [ ] Tema claro/escuro configurável
- [ ] Internacionalização (i18n) — suporte a inglês

### Dados
- [ ] Particionamento otimizado das tabelas Gold (clustering por product_code + state_acronym)
- [x] **Camada `serving/` (Pushdown Computing)** — marts pré-agregados nos grãos exatos dos gráficos + dimensões conformadas (`dim_date`, `dim_geo_br`), reduzindo o scan de **GB → MB** para o dashboard. Substitui a postura anterior de "deliberadamente nunca pré-agregar"; o Gold permanece a fonte comprehensiva por fonte e o `serving` deriva dele (ver [`ARCHITECTURE.md`](ARCHITECTURE.md#camada-serving--pushdown-computing-dashboard-dash) § Camada Serving)
- [ ] Materializações incrementais nos marts de serving **se** o volume crescer (hoje `table` full-refresh no rebuild noturno)
- [ ] Data freshness monitoring (dbt source freshness)

---

## 🔴 Longo Prazo (6–12 meses)

Foco: **escala, inteligência e abertura**.

### Inteligência & Análise
- [ ] Modelos preditivos de produção (séries temporais, sazonalidade)
- [ ] Alertas automáticos de anomalias nos dados (queda/pico inesperado)
- [ ] Integração com Vertex AI para análises avançadas
- [ ] Natural Language Query — perguntas em linguagem natural sobre os dados

### Escala
- [ ] Suporte a múltiplos projetos GCP (multi-tenant)
- [ ] API REST pública para consulta programática dos dados Gold
- [ ] Data sharing via BigQuery Analytics Hub
- [ ] Orquestração com Apache Airflow / Cloud Composer

### Comunidade & Abertura
- [ ] Publicação de dataset público (BigQuery public dataset ou dados.gov.br)
- [ ] Documentação técnica em inglês (internacionalização da docs)
- [ ] Contribuição para pacotes open-source utilizados
- [ ] Apresentação em conferências (PyCon, dbt Coalesce, Google Cloud Next)

### Governança
- [ ] Data catalog (Google Data Catalog ou DataHub)
- [ ] Data lineage visual (integração com dbt docs)
- [ ] SLA formal para atualização dos dados
- [ ] Política de retenção de dados (lifecycle rules no GCS)

---

## 📌 Princípios Guia

1. **Zero hardcode** — tudo configurável via `.env`
2. **Reprodutibilidade** — qualquer pessoa deve conseguir recriar o pipeline do zero
3. **Segurança primeiro** — sem keyfiles, impersonation everywhere
4. **Dados confiáveis** — testes, flags de qualidade, chain index auditável
5. **Simplicidade operacional** — um `make` ou `embrapa` comando para cada tarefa

---

> 💡 Sugestões de features? Abra uma [issue](https://github.com/igorrflorentino/embrapa-dashboard-commodities/issues) ou veja [CONTRIBUTING.md](CONTRIBUTING.md).
