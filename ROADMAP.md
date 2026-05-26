# Roadmap — Embrapa Commodities Dashboard

> Visão de futuro do projeto. Metas organizadas por horizonte temporal.
> Este documento é atualizado conforme o projeto evolui.

---

## 🟢 Curto Prazo (1–3 meses)

Foco: **estabilização, observabilidade e automação básica**.

### Pipeline & Dados
- [ ] Scheduler automático para ingestão (Cloud Scheduler ou cron job)
- [ ] Notificações de falha de ingestão (email ou Slack webhook)
- [ ] Integrar SQLFluff no CI (atualmente rodado manualmente)
- [ ] Testes de integridade end-to-end (row counts Bronze → Silver → Gold)

### Dashboard
- [ ] Exportação de dados (CSV/Excel) diretamente do dashboard
- [ ] Melhorias de UX baseadas em feedback de usuários
- [ ] Cache layer para queries repetitivas (in-memory ou Redis)

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
- [ ] Materialização de tabelas agregadas para queries frequentes do dashboard
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
