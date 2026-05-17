# Looker Studio — Setup do Dashboard

## Pré-requisito: rode `make dbt-build-prod`

O Looker Studio deve apontar para os datasets **de produção** (`silver`, `gold`),
não para os de dev (`dbt_dev_silver`, `dbt_dev_gold`). Certifique-se de ter rodado:

```bash
make dbt-build-prod
```

Isso cria `embrapa-dashboard-commodities.gold.gold_commodity_matrix` com os dados completos.

---

## 1. Habilitar BI Engine (recomendado)

Antes de criar o dashboard, ative o BI Engine para evitar cobranças por bytes escaneados e ter respostas em sub-segundo.

1. Acesse: **BigQuery → BI Engine → Reservations** no console GCP
2. Clique em **Create Reservation**
3. Configurações:
   - **Project**: `embrapa-dashboard-commodities`
   - **Location**: `us-central1` (mesmo da sua BQ_LOCATION)
   - **Capacity**: `1 GiB` (suficiente para cobrir a Gold com ~3–30k rows)
4. Clique em **Create**

Custo estimado: ~U$ 25–30/mês. Elimina quase todo billing por query no dashboard.

---

## 2. Criar o relatório no Looker Studio

### 2a. Acessar o Looker Studio

1. Vá para [lookerstudio.google.com](https://lookerstudio.google.com)
2. Clique em **+ Criar → Relatório**

### 2b. Conectar à tabela Gold

1. Em "Adicionar dados ao relatório", selecione **BigQuery**
2. Faça login com a conta que tem acesso ao projeto
3. Navegue: **Meus projetos → embrapa-dashboard-commodities → gold → gold_commodity_matrix**
4. Clique em **Adicionar** → **Adicionar ao relatório**

> **Importante:** conecte diretamente à tabela, não via "Custom Query".
> BI Engine só acelera conexões diretas à tabela física.

### 2c. Configurar campos padrão

Na tela de configuração da fonte de dados, ajuste:

| Campo | Tipo sugerido | Agregação padrão |
|---|---|---|
| `reference_year` | Número (ano) | — |
| `state_acronym` | Texto | — |
| `city_name` | Texto | — |
| `product_code` | Texto | — |
| `product_description` | Texto | — |
| `quantitykg` | Número | Soma |
| `quantitytons` | Número | Soma |
| `quantitym3` | Número | Soma |
| `quantityliters` | Número | Soma |
| `valnominalbrl` | Número (moeda BRL) | Soma |
| `valnominalusd` | Número (moeda USD) | Soma |
| `valnominaleur` | Número (moeda EUR) | Soma |
| `valnominalcny` | Número (moeda CNY) | Soma |
| `valrealipcabrl` | Número (moeda BRL) | Soma |
| `valrealipcausd` | Número (moeda USD) | Soma |
| `valrealipcaeur` | Número (moeda EUR) | Soma |
| `valrealipcacny` | Número (moeda CNY) | Soma |
| `valrealigpmbrl` | Número (moeda BRL) | Soma |
| `valrealigpmusd` | Número (moeda USD) | Soma |
| `valrealigpmeur` | Número (moeda EUR) | Soma |
| `valrealigpmcny` | Número (moeda CNY) | Soma |
| `dataquality_flag` | Texto | — |

---

## 3. Filtro padrão recomendado

Adicione um **filtro de relatório** para o dashboard executivo:

- Campo: `dataquality_flag`
- Condição: **Igual a** `OK`

Isso exclui linhas onde o IBGE não publicou valor monetário (ex.: Pinheiro brasileiro).

---

## 4. Estrutura de páginas sugerida

### Página 1 — Visão geral

| Gráfico | Configuração |
|---|---|
| Scorecard — Valor Real IPCA Total (BRL) | `valrealipcabrl` Soma |
| Scorecard — Volume Total (Toneladas) | `quantitytons` Soma |
| Gráfico de linhas — Série histórica | Dimensão: `reference_year` · Métrica: `valrealipcabrl` |
| Gráfico de barras — Por produto | Dimensão: `product_description` · Métrica: `valrealipcabrl` |
| Filtro — Ano | Controle deslizante em `reference_year` |
| Filtro — Estado | Seletor em `state_acronym` |
| Filtro — Produto | Seletor em `product_description` |

### Página 2 — Análise geográfica

| Gráfico | Configuração |
|---|---|
| Mapa coroplético (Brasil) | Geo: `state_acronym` · Cor: `valrealipcabrl` |
| Tabela detalhada — Top municípios | Dimensões: `city_name`, `state_acronym` · Métricas: `quantitytons`, `valnominalbrl`, `valrealipcabrl` |

### Página 3 — Análise monetária comparada

| Gráfico | Configuração |
|---|---|
| Gráfico de linhas — Valores nominais vs reais | Série 1: `valnominalbrl` · Série 2: `valrealipcabrl` · Série 3: `valrealigpmbrl` |
| Gráfico de barras — Por moeda | Métricas: `valrealipcausd`, `valrealipcaeur`, `valrealipcacny` |

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
