# Adicionando uma nova fonte de dados

Guia passo-a-passo para integrar uma fonte nova ao pipeline (Bronze → Silver → Gold) sem precisar fazer engenharia reversa dos padrões existentes.

**Quando usar:** ao adicionar MDIC COMEX, UN COMTRADE, SEFAZ NFe, ou qualquer outra fonte futura. O projeto já está preparado — as fricções estruturais foram resolvidas no PR de prep que introduziu o pacote [`core/`](../src/embrapa_commodities/core/), o registry `cli.INGESTS`, o registry `doctor.SOURCE_CHECKS`, e a introspecção do `backup.py`.

**Premissa arquitetural (importante):** **Gold é por fonte.** Cada nova fonte ganha sua própria linhagem `gold_<fonte>_*`. Não tente forçar COMEX (mensal × país × HS code) ou NFe (evento × UF) dentro de `gold_commodity_matrix` — os grãos são incompatíveis. As Silver de deflação e câmbio (`silver_bcb_inflation`, `silver_bcb_currency`) ficam compartilhadas via `ref()`.

---

## Checklist (11 passos)

### 1. Cliente HTTP

Local: `src/embrapa_commodities/<fonte>/client.py`

Padrão mínimo:

```python
from embrapa_commodities.core import SourceTransientError


class <Fonte>RequestError(Exception):
    """Non-200 response from the <Fonte> API (base class)."""


class <Fonte>TransientError(<Fonte>RequestError, SourceTransientError):
    """Retryable error (5xx, 408, 429, …)."""
```

A mixin com `SourceTransientError` permite que decorators futuros em `core/http.py` peguem todas as transientes sem listar cada classe nominalmente.

**Retry padrão** (5 tentativas + exponencial 2-30s + timeout `(10, 30)`): por enquanto inline com tenacity, espelhando o decorator `@retry(...)` em [`bcb/client.py`](../src/embrapa_commodities/bcb/client.py) (procure por `@retry`).

**Defesa contra slow-byte / period-halving** (caso a API apresente): modele a função `_http_get` + a recursão de `SidraLimitExceeded` em [`ibge/client.py`](../src/embrapa_commodities/ibge/client.py) — esse código é hard-won e **não** deve ser compartilhado via `core/`.

### 2. Pipeline (Bronze writer)

Local: `src/embrapa_commodities/<fonte>/pipeline.py`

Assinatura:

```python
def run(settings: Settings, *, full: bool = False) -> str:
    """Retorna o GCS URI do Parquet aterrissado, ou string vazia se nada novo."""
```

**Delta-aware?** Reaproveite [`latest_reference_date()`](../src/embrapa_commodities/gcp/bigquery.py) e escreva um `_effective_start_year` local no seu pipeline. Templates:

- Granularidade mensal/anual (overlap = N meses): ver [`bcb/inflation.py:32-45`](../src/embrapa_commodities/bcb/inflation.py).
- Granularidade diária/anual (overlap depende do mês do último registro): ver [`bcb/currency.py:28-39`](../src/embrapa_commodities/bcb/currency.py).
- Evento/timestamp (NFe): use `latest_reference_date` com `date_format` custom; a janela de overlap pode ser horas em vez de meses.

Não tente extrair `_effective_start_year` para um helper compartilhado — as formas são genuinamente diferentes e a abstração custaria legibilidade.

**Schema explícito.** O loader [`gcp/bigquery.load_dataframe()`](../src/embrapa_commodities/gcp/bigquery.py) exige `list[SchemaField]` — não use autodetect.

### 3. Configuração

Local: [`.env.example`](../.env.example) e [`src/embrapa_commodities/config.py`](../src/embrapa_commodities/config.py).

Padrão (espelhe `IBGE_*` / `BCB_*`):

```bash
# ─── <Fonte> ──────────────────────────────────────────────────────────────────
BQ_BRONZE_<FONTE>_DATASET=bronze_<fonte>
BQ_BRONZE_<FONTE>_<TABELA>_TABLE=<tabela>_raw

<FONTE>_API_BASE_URL=https://...
<FONTE>_START_DATE=2010-01
<FONTE>_END_DATE=2026-12
# ... séries / códigos específicos
```

No `Settings`:

```python
bq_bronze_<fonte>_dataset: str = Field(default="bronze_<fonte>")
bq_bronze_<fonte>_<tabela>_table: str = Field(default="<tabela>_raw")
<fonte>_api_base_url: str = Field(default="https://...")
# ...
```

### 4. Registrar nos três registries (CLI + Doctor)

| Registry | Arquivo | O que acrescentar |
|---|---|---|
| `cli.INGESTS` | [`cli.py`](../src/embrapa_commodities/cli.py) (logo após declaração de `discover_app`) | `IngestSpec("<fonte>", <fonte>_pipeline, accepts_full=True/False, label="…")` |
| `doctor.SOURCE_CHECKS` | [`doctor.py`](../src/embrapa_commodities/doctor.py) (fim do arquivo) | `("<fonte>", _check_<fonte>)` |
| `doctor.BRONZE_TARGETS` | [`doctor.py`](../src/embrapa_commodities/doctor.py) | `("bq_bronze_<fonte>_dataset", "bq_bronze_<fonte>_<tabela>_table")` |

E escreva o `@ingest_app.command("<fonte>")` manuscrito no `cli.py` — observabilidade não é compartilhada via registry (cada fonte emite eventos próprios). Use as commands existentes como template:

- Fonte com chunks parciais e progresso por unidade (estado/série/mês): copie [`ingest_ibge_batch`](../src/embrapa_commodities/cli.py) (linhas 135-277).
- Fonte single-shot delta: copie [`ingest_bcb_inflation`](../src/embrapa_commodities/cli.py) (linhas 103-116).

Para fontes sem API pública (NFe via XML em lote), o `_check_<fonte>` pode ser um stub: `return CheckResult("<fonte>", True, "sem probe público (ingestão por lote)")`.

### 5. dbt Bronze source

Local: [`dbt/models/_sources.yml`](../dbt/models/_sources.yml).

Acrescente um bloco `bronze_<fonte>` espelhando os existentes (linhas 4-29):

```yaml
- name: bronze_<fonte>
  description: "Raw <Fonte> payloads ingested by `embrapa ingest <fonte>`."
  database: "{{ target.project }}"
  schema: "{{ env_var('BQ_BRONZE_<FONTE>_DATASET', 'bronze_<fonte>') }}"
  tables:
    - name: <tabela>_raw
      identifier: "{{ env_var('BQ_BRONZE_<FONTE>_<TABELA>_TABLE', '<tabela>_raw') }}"
      description: "..."
      config:
        loaded_at_field: ingestion_timestamp
```

### 6. dbt Silver

Local: `dbt/models/silver/silver_<fonte>_<tabela>.sql`.

Copie [`silver_ibge_pevs.sql`](../dbt/models/silver/silver_ibge_pevs.sql) como template. Padrão:

1. **Dedup** via `qualify row_number() over (partition by <natural_key> order by ingestion_timestamp desc) = 1`.
2. **Tipagem** com [`safe_numeric()`](../dbt/macros/safe_numeric.sql) para colunas STRING → NUMERIC com placeholders (`-`, `...`, `..`, `*`, `X`) → NULL.
3. **Enriquecimento** com seeds e CTEs específicos da fonte.

Adicione testes em `dbt/models/silver/_silver.yml` no mesmo padrão dos existentes — `unique_combination_of_columns`, `not_null`, `accepted_values` para domínios fechados.

### 7. dbt Gold (linhagem própria)

Local: `dbt/models/gold/gold_<fonte>_<grão>.sql` — ex.: `gold_comex_monthly.sql`, `gold_nfe_transactions.sql`.

**Não** tente juntar dentro de `gold_commodity_matrix`. Grãos e geografias incompatíveis.

Para deflação monetária: reaproveite as Silver compartilhadas via `ref()`:

```sql
inflation_year_end as (
  -- mesmo CTE de gold_commodity_matrix.sql:67-83
  select ... from {{ ref('silver_bcb_inflation') }} ...
),

fx_year as (
  -- mesmo CTE de gold_commodity_matrix.sql:105-114
  select ... from {{ ref('silver_bcb_currency') }} ...
)
```

Aplique as quatro convenções monetárias do projeto (`val_yearfx_*`, `val_real_ipca_*`, `val_real_igpm_*`, `val_real_igpdi_*`) se a fonte tiver valores monetários.

**Importante:** depois do `dbt build` em prod, a tabela aparece automaticamente em `make backup-gold` (introspecção via `list_tables` + prefixo `gold_`). Sem manutenção manual de listas.

### 8. Seeds de referência (se aplicável)

Local: `dbt/seeds/`.

Tabelas de mapeamento típicas:
- **HS codes** (COMEX, COMTRADE): `hs_code_<ano>.csv` com colunas `code`, `name`, `parent_code`.
- **Países ISO** (COMTRADE): `country_iso.csv` com `iso2`, `iso3`, `name`, `region`.
- **NCM** (NFe): `ncm_to_hs.csv` para harmonizar com COMEX.

Padrão YAML em [`dbt/seeds/_seeds.yml`](../dbt/seeds/_seeds.yml) — declare `column_types` explícitos e testes (`not_null`, `unique`).

### 9. Testes Python

Locais: `tests/test_<fonte>_client.py` + `tests/test_<fonte>_pipeline.py`.

Templates:
- Cliente HTTP mockado: copie [`tests/test_bcb_client.py`](../tests/test_bcb_client.py) (usa `responses`).
- Pipeline com delta + mocks de GCP: copie [`tests/test_bcb_inflation_pipeline.py`](../tests/test_bcb_inflation_pipeline.py). **Patch `latest_reference_date`** no namespace da sua fonte, não `_effective_start_year`.

Cobertura mínima:
- Schema correto no Bronze (assertion sobre `load_dataframe` kwargs).
- Delta computa corretamente para casos: (a) Bronze vazio → `configured_start`; (b) Bronze com dados → overlap aplicado; (c) `--full` ignora delta.
- HTTP transient (5xx) é retornado como `<Fonte>TransientError`.

### 10. Segredo (decisão por fonte)

- **API pública sem auth** (COMEX, hoje): nada a fazer. Espelha IBGE/BCB.
- **API key não-sensível** (COMTRADE, hoje): use env var em `.env` (`COMTRADE_API_KEY=...`) + GitHub Actions secret no CI. Adicione ao [`.gitignore`](../.gitignore) se nunca foi commitado.
- **Credencial sensível** (cert A1/A3 da SEFAZ NFe; OAuth de longa duração): **abra a decisão de Secret Manager**. O projeto descartou Secret Manager em [`docs/iam_setup.md:70-73`](iam_setup.md) — para esses casos vale revisitar conscientemente. Documente a decisão e o caminho aqui depois.

### 11. Documentação leve

- Acrescente a fonte ao diagrama de pipeline em [`README.md`](../README.md) e [`ARCHITECTURE.md`](../ARCHITECTURE.md) (atualizar as caixas Bronze e Consumo).
- Acrescente o escopo da fonte (`comex`, `comtrade`, `nfe`) à lista em [`CONTRIBUTING.md`](../CONTRIBUTING.md) → Escopos comuns (linha 90).
- Acrescente uma entrada em `CHANGELOG.md` em `[Unreleased] / Added`.

---

## Verificação end-to-end

Antes de declarar a fonte pronta para PR:

```powershell
# 1. Suíte de testes (incluir os novos test_<fonte>_*.py)
uv run pytest

# 2. Lint
uv run ruff check .
uv run ruff format --check .

# 3. CLI smoke — nova fonte aparece nos help e nos registries
uv run python -m embrapa_commodities.cli ingest --help        # deve listar <fonte>
uv run python -m embrapa_commodities.cli doctor                # deve incluir check <fonte>

# 4. Ingestão dev (precisa ADC + .env válido)
uv run python -m embrapa_commodities.cli ingest <fonte>

# 5. dbt parse + build em dev
Set-Location dbt
uv run python -m dbt.cli.main deps
uv run python -m dbt.cli.main parse
uv run python -m dbt.cli.main build --select silver_<fonte>_+ gold_<fonte>_+
Set-Location ..

# 6. Backup-gold introspectiva inclui automaticamente
uv run python -m embrapa_commodities.cli backup-gold           # nova tabela aparece
```

Se cada passo retorna verde e a nova `gold_<fonte>_*` é citada no log do `backup-gold`, a fonte está integrada.

---

## Anti-padrões a evitar

- ❌ **Forçar a fonte em `gold_commodity_matrix`.** Cria join impossível ou aglutina grãos incompatíveis. Use uma sibling.
- ❌ **Hardcodar listas que devem ser registries.** Se você editar `backup.py` ou `doctor.py` em vez de só acrescentar entry em registry, está fora do padrão.
- ❌ **Pular `SourceTransientError`.** Sem o mixin, retry compartilhado futuro não funcionará.
- ❌ **Reescrever slow-byte / period-halving copy-pasted do IBGE para outra fonte.** Esse código é caro de manter; só replique se a sua API realmente apresenta o mesmo patológico.
- ❌ **Commitar credenciais em `.env`.** Use `.env.example` como template; o real `.env` está no `.gitignore`.
- ❌ **Esquecer de adicionar Bronze TABLE_TABLE config em `BRONZE_TARGETS`.** O `embrapa doctor` não vai checar e o operador descobre só quando a tabela não materializa.
