# Looker Studio — Setup do Dashboard

## Pré-requisito: rode `make dbt-build-prod`

O Looker Studio deve apontar para os datasets **de produção** (`silver`, `gold`),
não para os de dev (`dbt_dev_silver`, `dbt_dev_gold`). Certifique-se de ter rodado:

```bash
make dbt-build-prod
```

Isso cria `embrapa-dashboard-commodities.gold.gold_pevs_production` com os dados completos.

---

## 1. Habilitar BI Engine (opcional)

O BI Engine é uma tecnologia de cache para acelerar consultas ao BigQuery.

Looker Studio disponibiliza 1Gb de BI Engine gratuitamente. Para o projeto em questão não será necessário, mas pode ser útil em casos de uso futuro.

Ele melhora o desempenho do dashboard, especialmente se você tiver consultas complexas ou grandes volumes de dados. Ele também pode ajudar a reduzir custos, pois as consultas que usam o BI Engine não são cobradas por bytes escaneados.

1. Acesse: **BigQuery → BI Engine → Reservations** no console GCP
2. Clique em **Create Reservation**
3. Configurações:
   - **Project**: `embrapa-dashboard-commodities`
   - **Location**: `us-central1` (mesmo da sua BQ_LOCATION)
   - **Capacity**: `[defina a capacidade, ex: 1Gb]`
4. Clique em **Create**

Custo estimado: ~U$ 30/mês/Gb.

> Antes de habilitar BI Engine, configure o budget e a quota em
> [cost_safety.md](cost_safety.md) — assim qualquer custo inesperado dispara
> alerta automático.

---

## 2. Criar o relatório no Looker Studio

### 2a. Acessar o Looker Studio

1. Vá para [lookerstudio.google.com](https://lookerstudio.google.com)
2. Clique em **+ Criar → Relatório**

### 2b. Conectar à tabela Gold

Há **uma única Gold física por fonte** — para o IBGE PEVS é
`gold_pevs_production` (~95 mil linhas, uma por ano × UF × município × produto).
As agregações por estado/ano ou Brasil-total são derivadas no próprio Looker
Studio (campos calculados / GROUP BY na fonte), em vez de tabelas
pré-agregadas separadas. Simplicidade de manutenção sobre eficiência de query.

| Tabela | Linhas (aprox.) | Grão |
|---|---|---|
| `gold_pevs_production` | ~95 mil | ano × UF × município × produto (drill-down completo) |

Conecte:

1. Em "Adicionar dados ao relatório", selecione **BigQuery**
2. Faça login com a conta que tem acesso ao projeto
3. Navegue: **Meus projetos → embrapa-dashboard-commodities → gold → gold_pevs_production**
4. Clique em **Adicionar** → **Adicionar ao relatório**

> **Importante:** conecte diretamente à tabela, não via "Custom Query".
> BI Engine só acelera conexões diretas à tabela física.

### 2c. Configurar campos padrão

Na tela de configuração da fonte de dados, ajuste:

| Campo | Tipo sugerido | Agregação padrão |
|---|---|---|
| `reference_year` | Número (ano) | — |
| `reference_date` | Data (YYYY-MM-DD) | — |
| `state_acronym` | Texto | — |
| `state_name` | Texto | — |
| `region` | Texto | — |
| `city_code` | Texto / Geo → "Brazilian Municipality" | — |
| `city_name` | Texto | — |
| `product_code` | Texto | — |
| `product_description` | Texto | — |
| `quantity_tons` | Número | Soma |
| `quantity_m3` | Número | Soma |
| `val_yearfx_brl` | Número (moeda BRL) | Soma |
| `val_yearfx_usd` | Número (moeda USD) | Soma |
| `val_yearfx_eur` | Número (moeda EUR) | Soma |
| `val_yearfx_cny` | Número (moeda CNY) | Soma |
| `val_real_ipca_brl` | Número (moeda BRL) | Soma |
| `val_real_ipca_usd` | Número (moeda USD) | Soma |
| `val_real_ipca_eur` | Número (moeda EUR) | Soma |
| `val_real_ipca_cny` | Número (moeda CNY) | Soma |
| `val_real_igpm_brl` | Número (moeda BRL) | Soma |
| `val_real_igpm_usd` | Número (moeda USD) | Soma |
| `val_real_igpm_eur` | Número (moeda EUR) | Soma |
| `val_real_igpm_cny` | Número (moeda CNY) | Soma |
| `data_quality_flag` | Texto | — |
| `last_refresh` | Data e hora | Máximo |

---

## 3. Filtro padrão recomendado

Adicione um **filtro de relatório** para o dashboard executivo:

- Campo: `data_quality_flag`
- Condição: **Igual a** `OK`

Isso exclui linhas onde o IBGE não publicou valor monetário (ex.: Pinheiro brasileiro).

---

## 4. Estrutura de páginas sugerida

### Página 1 — Visão geral

| Gráfico | Configuração |
|---|---|
| Scorecard — Valor Real IPCA Total (BRL) | `val_real_ipca_brl` Soma |
| Scorecard — Volume Total (Toneladas) | `quantity_tons` Soma |
| Scorecard — Volume Total (m³) | `quantity_m3` Soma |
| Gráfico de linhas — Série histórica | Dimensão: `reference_year` · Métrica: `val_real_ipca_brl` |
| Gráfico de barras — Por produto | Dimensão: `product_description` · Métrica: `val_real_ipca_brl` |
| Filtro — Ano | Controle deslizante em `reference_year` |
| Filtro — Estado | Seletor em `state_acronym` |
| Filtro — Produto | Seletor em `product_description` |

### Página 2 — Análise geográfica

| Gráfico | Configuração |
|---|---|
| Mapa coroplético (Brasil) | Geo: `state_acronym` · Cor: `val_real_ipca_brl` |
| Tabela detalhada — Top municípios | Dimensões: `city_name`, `state_acronym` · Métricas: `quantity_tons`, `val_yearfx_brl`, `val_real_ipca_brl` |

### Página 3 — Análise monetária comparada

| Gráfico | Configuração |
|---|---|
| Gráfico de linhas — Valores nominais vs reais | Série 1: `val_yearfx_brl` · Série 2: `val_real_ipca_brl` · Série 3: `val_real_igpm_brl` |
| Gráfico de barras — Por moeda | Métricas: `val_real_ipca_usd`, `val_real_ipca_eur`, `val_real_ipca_cny` |

---

## 5. Atualização automática dos dados

O dashboard reflete a tabela Gold no momento da consulta. Para atualizar:

```bash
# Ingestão incremental (só novos dados)
uv run embrapa ingest all

# Reconstruir transformações
make dbt-build-prod
```

Configure um cron ou GitHub Actions para rodar isso anualmente (PEVS é publicado 1× ao ano).

---

## 6. Transferência para a empresa

Ao mover o projeto para a empresa:
1. Transfira o relatório: **Compartilhar → Transferir propriedade** no Looker Studio.
2. Atualize a fonte de dados para apontar para o novo `GCP_PROJECT_ID`.
3. Não há hardcode de projeto no relatório — só a fonte de dados precisa ser atualizada.
