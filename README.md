# Embrapa Commodities Dashboard

[![CI](https://github.com/igorrflorentino/embrapa-dashboard-commodities/actions/workflows/ci.yml/badge.svg)](https://github.com/igorrflorentino/embrapa-dashboard-commodities/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3121/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-orange.svg)](LICENSE)
[![uv](https://img.shields.io/badge/pkg-uv-blueviolet)](https://docs.astral.sh/uv/)
[![dbt](https://img.shields.io/badge/transform-dbt-FF694B)](https://www.getdbt.com/)

Pipeline Medalhão (**Bronze → Silver → Gold → Looker Studio**) para análise histórica de produção extrativa vegetal brasileira (IBGE PEVS), enriquecida com câmbio (USD, EUR, CNY) e inflação (IPCA, IGP-M, IGP-DI) do Banco Central do Brasil.

> ⚠️ **Frontend em reconstrução** com [Claude Design System](https://claude.ai/). A UI anterior (Dash + Plotly servida via Cloud Run) foi removida em 2026-05-29 para preparar um handoff limpo. O backend (pipeline Medallion + dbt + CLI `embrapa`) está 100% funcional e independente da camada de visualização — Looker Studio segue conectando direto à tabela Gold. O próximo handoff fará a junção do novo design system com este backend.

```
IBGE PEVS API ─┐
BCB Inflation ─┼─► Python (src/embrapa_commodities) ─► GCS Bronze (Parquet)
BCB Currency  ─┘                                              │
                                                              ▼
                              dbt-bigquery ──► Silver (tipada + IPCA encadeado)
                                                              │
                                                              ▼
                                             gold_pevs_production (tabela física)
                                                              │
                                                              ▼
                                                       Looker Studio
```

## Stack

Python 3.12 · `uv` · `dbt-bigquery` · BigQuery · GCS · Looker Studio · GitHub Actions

Tabela completa com justificativas técnicas em [`ARCHITECTURE.md`](ARCHITECTURE.md#stack-de-tecnologias).

## Tudo é configurável via `.env`

Buckets, prefixos, datasets, tabelas, códigos de produtos do IBGE e séries do BCB ficam em `.env`. Veja [.env.example](.env.example).

Buckets e datasets são **criados automaticamente** na primeira execução de `embrapa ingest *`.

## Quickstart

### Caminho automatizado (recomendado para máquinas novas)

```bash
# macOS / Linux
./setup.sh

# Windows (Command Prompt ou PowerShell)
setup.bat
```

Os scripts instalam Python 3.12 e `uv` se faltarem, detectam o melhor modo de
autenticação (impersonação OAuth ou keyfile legado) e geram `.env` +
`~/.dbt/profiles.yml`. Detalhes em [docs/setup.md](docs/setup.md).

Para sandboxes (incluindo Claude Code Web), o `init_dev_env.sh` decodifica um
keyfile passado via `GCP_CREDENTIALS_B64` e dispara o mesmo fluxo de
validação. Veja a seção *Claude Code Web* em [docs/setup.md](docs/setup.md).

### Caminho manual

```bash
# 1. Python + venv
pyenv local 3.12.11
uv sync

# 2. Credenciais GCP (uma vez por máquina)
gcloud auth application-default login

# 3. Configurar variáveis
cp .env.example .env       # ajuste GCP_PROJECT_ID e demais campos

# 4. (Opcional) Descobrir códigos antes de fixar no .env
uv run embrapa discover ibge-periods --table-id 289
uv run embrapa discover ibge-products --keywords castanha,madeira,pinheiro
uv run embrapa discover bcb-series 433

# 5. dbt profile (uma vez)
mkdir -p ~/.dbt
cp dbt/profiles.yml.example ~/.dbt/profiles.yml

# 6. Ingestão Bronze (Python → GCS → BigQuery)
uv run embrapa ingest all

# 7. Transformações Silver + Gold
make dbt-deps
make dbt-build
```

## CLI

```text
embrapa ingest ibge | bcb-inflation | bcb-currency | all
embrapa discover ibge-periods   [--table-id 289]
embrapa discover ibge-products  --keywords castanha,madeira
embrapa discover bcb-series     <code>            # ex: 433
embrapa dbt <args>                                  # ex: dbt run --select gold
```

Os comandos `discover` são **auxiliares e não fazem parte do pipeline em produção**. Use-os para investigar APIs IBGE/BCB e descobrir os códigos exatos que quer colocar no `.env`.

## Convenções monetárias do Gold

| Coluna | Significado | Quando é NULL |
|---|---|---|
| `val_yearfx_*` | `val_raw` (já em numerário R$ atual, sem correção inflacionária) convertido pelo **FX médio do mesmo ano**. Colunas em moeda estrangeira são `NULL` pré-1994 para não misturar Cruzeiros antigos com valores atuais. | FX do ano indisponível (ex.: EUR < 1999); ou `reference_year < 1994` para USD/EUR/CNY. |
| `val_real_ipca_*` | Valor projetado para hoje pela **cadeia IPCA** (absorve inflação + reformas monetárias) e convertido para FX corrente. **Use esta coluna para comparações entre anos.** | IPCA do ano-base indisponível. |
| `val_real_igpm_*` | Idem, usando IGP-M. | IGP-M do ano-base indisponível. |

> A série IPCA do BCB (SGS 433) é variação mensal. A camada Silver encadeia esse percentual em um número-índice de base 100, tornando matematicamente válido o produto `valor_em_cruzeiros * (IPCA_atual / IPCA_ano)` para chegar a Reais atuais — sem necessidade de tabela de conversão histórica de moedas.

## `data_quality_flag`

| Valor | Significado |
|---|---|
| `OK` | linha tem quantidade (em qualquer unidade) **e** valor |
| `MISSING_VALUE` | quantidade reportada mas valor monetário ausente |
| `MISSING_QUANTITY` | valor monetário reportado mas quantidade ausente |
| `INCOMPLETE` | ambos ausentes |

Placeholders do IBGE (`-`, `...`, `..`, `*`, `X`) são convertidos para `NULL` na Silver pelo macro `safe_numeric`.

## Saída final — `gold.gold_pevs_production`

Uma linha por `(reference_year, state_acronym, city_name, product_code)`. Colunas:

**Tempo / geografia / produto**
`reference_year`, `reference_date`, `state_acronym`, `state_name`, `region`, `city_code`, `city_name`, `product_code`, `product_description`.

**Quantidades**
`quantity_tons`, `quantity_m3`.

**Valores por FX do ano (foreign zerado pré-1994)**
`val_yearfx_brl`, `val_yearfx_usd`, `val_yearfx_eur`, `val_yearfx_cny`.

**Valores reais via IPCA**
`val_real_ipca_brl`, `val_real_ipca_usd`, `val_real_ipca_eur`, `val_real_ipca_cny`.

**Valores reais via IGP-M**
`val_real_igpm_brl`, `val_real_igpm_usd`, `val_real_igpm_eur`, `val_real_igpm_cny`.

**Qualidade / proveniência**
`data_quality_flag`, `last_refresh`.

## Looker Studio — recomendações

- Conectar **diretamente** na tabela `${BQ_GOLD_DATASET}.gold_pevs_production` (não em views nem em "custom query").
- Habilite **BI Engine** com 1–2 GB cobrindo o dataset Gold — corta latência e custos de queries repetitivas.
- Filtro padrão sugerido para o dashboard executivo: `data_quality_flag = 'OK'`.

## Estrutura

Estrutura completa de pastas (arquivo-a-arquivo) em [`ARCHITECTURE.md`](ARCHITECTURE.md#estrutura-de-pastas).

> Tooling auxiliar (setup do ambiente, scripts de IAM) está em [`scripts/README.md`](scripts/README.md).

## Transferência futura para a empresa

Veja [docs/ownership_transfer.md](docs/ownership_transfer.md). Nada está hardcoded — basta um novo `.env` e a primeira execução de `uv run embrapa ingest all` recria toda a infraestrutura (bucket, datasets, tabelas) no novo projeto GCP.

## Cost safety

Configurações **uma-vez** no Cloud Console (budget alert + custom quota) que protegem contra cobrança inesperada estão em [docs/cost_safety.md](docs/cost_safety.md). Recomendado fazer **antes** de habilitar BI Engine.

---

## 📚 Documentação

| Documento | Descrição |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Guia para assistentes de IA (comandos, arquitetura, skills) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Arquitetura técnica — stack, estrutura de pastas, fluxo de dados |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Guia de contribuição — commits, branches, PRs |
| [CHANGELOG.md](CHANGELOG.md) | Histórico de versões |
| [TODO.md](TODO.md) | Lista macro de tarefas pendentes e concluídas |
| [ROADMAP.md](ROADMAP.md) | Visão de futuro (curto, médio e longo prazo) |
| [SECURITY.md](SECURITY.md) | Política de segurança e reporte de vulnerabilidades |
| [PLANS/](PLANS/) | Planos detalhados de features complexas |

<details>
<summary>Documentação detalhada (docs/)</summary>

| Documento | Conteúdo |
|---|---|
| [docs/setup.md](docs/setup.md) | Guia completo de setup do ambiente |
| [docs/architecture.md](docs/architecture.md) | Arquitetura de autenticação (Cadeia de Confiança) |
| [docs/iam_setup.md](docs/iam_setup.md) | Setup de IAM e Service Accounts |
| [docs/cost_safety.md](docs/cost_safety.md) | Budget alerts e quotas |
| [docs/testing.md](docs/testing.md) | Estratégia e guia de testes |
| [docs/ownership_transfer.md](docs/ownership_transfer.md) | Checklist de transferência para a empresa |
| [docs/looker_studio_setup.md](docs/looker_studio_setup.md) | Conexão Looker Studio → Gold |
| [docs/migration_history.md](docs/migration_history.md) | Histórico de migrações |
| [scripts/README.md](scripts/README.md) | Documentação dos scripts auxiliares |

</details>

---

## 📄 Licença

Este projeto é licenciado sob a [Apache License 2.0](LICENSE).

Desenvolvido por [Igor Florentino](mailto:igorlopesc@gmail.com).
