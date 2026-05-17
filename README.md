# Embrapa Commodities Dashboard

Pipeline Medalhão (**Bronze → Silver → Gold → Looker Studio**) para análise histórica de produção extrativa vegetal brasileira (IBGE PEVS), enriquecida com câmbio (USD, EUR, CNY) e inflação (IPCA, IGP-M, IGP-DI) do Banco Central do Brasil.

```
IBGE PEVS API ─┐
BCB Inflation ─┼─► Python (src/embrapa_commodities) ─► GCS Bronze (Parquet)
BCB Currency  ─┘                                              │
                                                              ▼
                              dbt-bigquery ──► Silver (tipada + IPCA encadeado)
                                                              │
                                                              ▼
                                             gold_commodity_matrix (tabela física)
                                                              │
                                                              ▼
                                                       Looker Studio
```

## Stack

| Camada | Tecnologia |
|---|---|
| Versão Python | `pyenv` + `3.12.11` (arquivo `.python-version`) |
| Gerenciamento de pacotes | `uv` |
| Ingestão | Python puro (`requests`, `tenacity`, `pandas`, `pyarrow`) |
| Data Lake | GCS (Parquet em `gs://${GCS_BUCKET}/${GCS_LANDING_PREFIX}/...`) |
| Warehouse | BigQuery (datasets configuráveis via `.env`) |
| Transformações | `dbt-core` + `dbt-bigquery` |
| Dashboard | Looker Studio (conectar direto na tabela física `${gold}.gold_commodity_matrix`) |

## Tudo é configurável via `.env`

Buckets, prefixos, datasets, tabelas, códigos de produtos do IBGE e séries do BCB ficam em `.env`. Veja [.env.example](.env.example).

Buckets e datasets são **criados automaticamente** na primeira execução de `embrapa ingest *`.

## Quickstart

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
| `valnominal*` | Valor da época, convertido por **FX médio do mesmo ano**. Pré-1994 vem em moeda da época (Cruzeiros etc.) — útil só para auditoria histórica. | FX do ano indisponível (ex.: EUR < 1999). |
| `valrealipca*` | Valor projetado para hoje pela **cadeia IPCA** (absorve inflação + reformas monetárias) e convertido para FX corrente. **Use esta coluna para comparações entre anos.** | IPCA do ano-base indisponível. |
| `valrealigpm*` | Idem, usando IGP-M. | IGP-M do ano-base indisponível. |

> A série IPCA do BCB (SGS 433) é variação mensal. A camada Silver encadeia esse percentual em um número-índice de base 100, tornando matematicamente válido o produto `valor_em_cruzeiros * (IPCA_atual / IPCA_ano)` para chegar a Reais atuais — sem necessidade de tabela de conversão histórica de moedas.

## `dataquality_flag`

| Valor | Significado |
|---|---|
| `OK` | linha tem quantidade (em qualquer unidade) **e** valor |
| `MISSING_VALUE` | quantidade reportada mas valor monetário ausente |
| `MISSING_QUANTITY` | valor monetário reportado mas quantidade ausente |
| `INCOMPLETE` | ambos ausentes |

Placeholders do IBGE (`-`, `...`, `..`, `*`, `X`) são convertidos para `NULL` na Silver pelo macro `safe_numeric`.

## Saída final — `gold.gold_commodity_matrix`

22 colunas, uma linha por `(reference_year, state_acronym, city_name, product_code)`:

`reference_year`, `state_acronym`, `city_name`, `product_description`, `product_code`,
`quantitykg`, `quantitytons`, `quantitym3`, `quantityliters`,
`valnominalbrl`, `valnominalusd`, `valnominaleur`, `valnominalcny`,
`valrealipcabrl`, `valrealipcausd`, `valrealipcaeur`, `valrealipcacny`,
`valrealigpmbrl`, `valrealigpmusd`, `valrealigpmeur`, `valrealigpmcny`,
`dataquality_flag`.

## Looker Studio — recomendações

- Conectar **diretamente** na tabela `${BQ_GOLD_DATASET}.gold_commodity_matrix` (não em views nem em "custom query").
- Habilite **BI Engine** com 1–2 GB cobrindo o dataset Gold — corta latência e custos de queries repetitivas.
- Filtro padrão sugerido para o dashboard executivo: `dataquality_flag = 'OK'`.

## Estrutura

```
src/embrapa_commodities/    # ingestão (Python puro)
  ├── config.py             # pydantic-settings + .env
  ├── discover.py           # helpers auxiliares (não usados no pipeline)
  ├── cli.py                # entrypoint typer (`embrapa`)
  ├── gcp/                  # ADC + BigQuery + GCS
  ├── ibge/                 # SIDRA client + Bronze pipeline
  └── bcb/                  # SGS client + Bronze pipelines
dbt/                        # transformações Silver + Gold
tests/                      # pytest (clientes HTTP mockados)
docs/ownership_transfer.md  # checklist para migrar para a empresa
```

## Transferência futura para a empresa

Veja [docs/ownership_transfer.md](docs/ownership_transfer.md). Nada está hardcoded — basta um novo `.env` e a primeira execução de `uv run embrapa ingest all` recria toda a infraestrutura (bucket, datasets, tabelas) no novo projeto GCP.
