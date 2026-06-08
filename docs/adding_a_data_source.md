# Adicionando uma nova fonte de dados

Guia passo-a-passo para integrar uma fonte nova ao pipeline (Bronze → Silver → Gold) sem precisar fazer engenharia reversa dos padrões existentes.

**Quando usar:** ao adicionar MDIC COMEX, UN COMTRADE, SEFAZ NFe, ou qualquer outra fonte futura. O projeto já está preparado — as fricções estruturais foram resolvidas no PR de prep que introduziu o pacote [`core/`](../src/embrapa_commodities/core/), o registry `cli.INGESTS`, o registry `doctor.SOURCE_CHECKS`, e a introspecção do `backup.py`.

**Premissa arquitetural (importante):** **Gold é por fonte — UMA tabela comprehensiva por fonte**, nomeada `gold_<fonte>_<forma>`. O `<forma>` é o grão semântico: `production` (medição de saída produtiva, sem origem→destino; só o PEVS → `gold_pevs_production`) ou `flows` (fluxo origem→destino; bancos de comércio → `gold_comex_flows`, `gold_comtrade_flows`, `gold_nfe_flows`). Agregações ad-hoc saem do Gold em tempo de query via `GROUP BY`; marts pré-agregados (para o Pushdown Computing do dashboard) ficam na camada `serving/`, derivando do Gold — não crie siblings pré-agregadas no dataset Gold. E não tente forçar COMEX (mensal × país × HS code) ou NFe (evento × UF) dentro de `gold_pevs_production` — os grãos são incompatíveis. As Silver de deflação e câmbio (`silver_bcb_inflation`, `silver_bcb_currency`) ficam compartilhadas via `ref()`.

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

A mixin com `SourceTransientError` permite que o decorator compartilhado em [`core/http.py`](../src/embrapa_commodities/core/http.py) (`http_retry_policy`) pegue todas as transientes sem listar cada classe nominalmente.

**Retry padrão + drain slow-byte** (5 tentativas, exponencial 2-30s, timeout `(10, 30)`, `Connection: close`, defesa contra slow-byte via `iter_content` sob deadline wall-clock): use os primitivos compartilhados de `core/http.py`:

```python
from embrapa_commodities.core import http as core_http

@core_http.http_retry_policy(
    transient_exc=<Fonte>TransientError,
    deadline_s=PER_REQUEST_DEADLINE_S,   # source-specific (180s no IBGE, 120s no BCB)
    before_sleep=_emit_retry,            # opcional — para observabilidade (ver IBGE)
)
def _http_get(url: str) -> requests.Response:
    response = core_http.get_drained(
        url,
        total_deadline_s=REQUEST_TOTAL_DEADLINE_S,  # source-specific (75s IBGE, 60s BCB)
        transient_exc=<Fonte>TransientError,
        context=...,                                 # string para a mensagem de erro
    )
    try:
        # status-code handling source-specific
        ...
    except BaseException:
        response.close()
        raise
```

`http_retry_policy` aceita `transient_exc`, `deadline_s`, `max_attempts=5` e `before_sleep=None`. `get_drained` retorna a `Response` já com body em `_content` — preserva `.json()` / `.text`. Veja [`ibge/client.py:_http_get`](../src/embrapa_commodities/ibge/client.py) e [`bcb/client.py:_fetch_window`](../src/embrapa_commodities/bcb/client.py) para os dois call-sites de referência. Constantes de deadline ficam no client (são source-specific).

**Lógica que NÃO deve ir para `core/`** (caso a API apresente): period-halving recursivo (como `SidraLimitExceeded` no IBGE), chunking por ano (como o `MAX_YEARS_PER_REQUEST` do BCB), paralelismo por entidade — código hard-won que merece ficar no client da fonte.

### 2. Pipeline (two-phase: extract→raw→bronze)

Local: `src/embrapa_commodities/<fonte>/pipeline.py`

**Modelo two-phase (obrigatório, todas as fontes).** O pipeline tem duas fases:

1. **Fase 1 — extract→raw:** busque o extrato *verbatim* e arquive-o no GCS via
   [`core.land_raw(df, ...)`](../src/embrapa_commodities/core/raw.py) (ou
   `land_raw_file(path, ...)` para extratos grandes demais p/ memória). Passe
   `provenance` (URL, ETag/Last-Modified, params da query) — vira metadata do
   objeto e base da checagem de freshness.
2. **Fase 2 — raw→bronze:** leia o raw de volta (`read_raw` / `download_raw +
   iter_batches`), filtre/molde, **stamp `ingestion_timestamp`** e carregue o
   Bronze via [`gcp/bigquery.load_dataframe()`](../src/embrapa_commodities/gcp/bigquery.py)
   (schema explícito + `clustering_fields`).

```python
def run(settings: Settings, *, full: bool = False, from_raw: bool = False) -> str:
    """Extract→raw (Fase 1) então raw→Bronze (Fase 2). Retorna destination, ou ''.

    from_raw pula a Fase 1 e reconstrói o Bronze do raw já arquivado (re-filtrar
    sem re-bater na fonte). Veja PLANS/raw_zone_architecture.md e os 3 exemplos:
    comex/pipeline.py, ibge/pipeline.py, bcb/series.py.
    """
```

`ensure_dataset` fica com você, *antes* do extract (o lookup delta consulta o
Bronze). Curto-circuite a fetch vazia (retornando `""`). Exponha `--from-raw` no
comando CLI. **Freshness** é source-specific na Fase 1: ETag (COMEX, via
`raw_provenance` vs HEAD), `max(reference_date)` (BCB), ou re-extração por run
(IBGE). Para re-derivar a partir da trilha completa, use
[`core.list_raw()`](../src/embrapa_commodities/core/raw.py).

**Delta-aware?** Reaproveite [`latest_reference_date()`](../src/embrapa_commodities/gcp/bigquery.py) para computar o start de re-fetch na Fase 1.

- **Se a fonte é uma série SGS do BCB** (shape `data`/`valor`, chave natural `reference_date_str`, lookup delta por série), você não escreve pipeline: defina um [`BcbSeriesSpec`](../src/embrapa_commodities/bcb/series.py) e delegue para `bcb.series.run`. As variantes inflation/currency são exatamente isso — diferem só no `label_column`, no schema e numa única função `overlap_start_year(last) -> int` (mensal rebobina sempre 1 ano; diária só em janeiro). Veja [`bcb/inflation.py`](../src/embrapa_commodities/bcb/inflation.py) e [`bcb/currency.py`](../src/embrapa_commodities/bcb/currency.py).
- **Se a fonte tem shape genuinamente diferente** (API não-SGS, granularidade de evento/timestamp como NFe, outra chave natural), escreva o seu próprio `run()` em vez de forçar um spec sobre `bcb.series` — use `latest_reference_date` com `date_format` custom e a janela de overlap apropriada (pode ser horas). Não tente generalizar `bcb.series` para cobrir formas heterogêneas; o custo de legibilidade não compensa.

**Schema explícito.** O loader [`gcp/bigquery.load_dataframe()`](../src/embrapa_commodities/gcp/bigquery.py) exige `list[SchemaField]` — não use autodetect.

**Aterrissagem.** A Fase 1 grava o raw com `core.land_raw`/`land_raw_file`; a
Fase 2 carrega o Bronze com `gcp/bigquery.load_dataframe` (não há mais um único
primitivo land+load — o GCS guarda o raw verbatim, o BQ guarda o Bronze
derivado). `ensure_bucket` é chamado dentro do `land_raw`; `ensure_dataset` fica
com você antes do extract.

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

E escreva o `@ingest_app.command("<fonte>")` manuscrito no `cli.py` — o `ingest all` usa o registry, mas cada comando individual é escrito à mão (mensagens próprias). Para a **visibilidade no `embrapa monitor`**, envolva o trabalho no context manager `pipeline_run` de [`core/observability_helpers.py`](../src/embrapa_commodities/core/observability_helpers.py):

```python
from embrapa_commodities.core import pipeline_run

@ingest_app.command("<fonte>")
def ingest_<fonte>(full: bool = typer.Option(False, "--full")) -> None:
    settings = get_settings()
    with pipeline_run("<fonte>", params={"full": full}) as (_run_id, log_path):
        console.print(f"[dim]event log:[/dim] {log_path}")
        destination = <fonte>_pipeline.run(settings, full=full)
    if destination:
        console.print(f"[green]✓[/green] <Fonte> bronze loaded → {destination}")
    else:
        console.print("[dim]<fonte>: nothing new since last ingest.[/dim]")
```

- **Single-shot** (uma varredura, como IBGE/BCB): use `pipeline_run` como acima. Ele emite a sequência `pipeline_start → chunk_start → chunk_end/chunk_error → pipeline_end` e a fonte aparece no monitor.
- **Multi-chunk** (progresso por estado/série/mês, como `ingest ibge-batch`): NÃO use `pipeline_run`; copie a estrutura manuscrita de `ingest_ibge_batch` em [`cli.py`](../src/embrapa_commodities/cli.py), que emite `chunk_start`/`chunk_end`/`chunk_error` por chunk e `state_*` por unidade.

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

### 7. dbt Gold (linhagem própria, UMA tabela por fonte)

Local: `dbt/models/gold/gold_<fonte>_<forma>.sql` — ex.: `gold_comex_flows.sql`, `gold_comtrade_flows.sql`, `gold_nfe_flows.sql`. `<forma>` = `production` (medição de saída, como PEVS) ou `flows` (fluxo origem→destino, bancos de comércio).

**Uma tabela comprehensiva por fonte** — agregação ad-hoc em tempo de query via `GROUP BY`; marts pré-agregados (Pushdown do dashboard) ficam na camada `serving/`, não no dataset Gold. E **não** junte a fonte dentro de `gold_pevs_production`: grãos e geografias incompatíveis.

Para deflação monetária: reaproveite as Silver compartilhadas via `ref()`:

```sql
inflation_year_end as (
  -- ver os CTEs de deflação em gold_pevs_production.sql
  select ... from {{ ref('silver_bcb_inflation') }} ...
),

fx_year as (
  -- ver os CTEs de FX em gold_pevs_production.sql
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

- ❌ **Forçar a fonte em `gold_pevs_production`.** Cria join impossível ou aglutina grãos incompatíveis. Crie a linhagem própria `gold_<fonte>_<forma>`.
- ❌ **Criar tabelas pré-agregadas no dataset Gold.** O Gold é UMA tabela comprehensiva por fonte (agregação ad-hoc em query-time). Marts pré-agregados existem — mas na camada `serving/` (Pushdown do dashboard), derivando do Gold, não como siblings no dataset Gold.
- ❌ **Hardcodar listas que devem ser registries.** Se você editar `backup.py` ou `doctor.py` em vez de só acrescentar entry em registry, está fora do padrão.
- ❌ **Pular `SourceTransientError`.** Sem o mixin, retry compartilhado futuro não funcionará.
- ❌ **Reescrever slow-byte / period-halving copy-pasted do IBGE para outra fonte.** Esse código é caro de manter; só replique se a sua API realmente apresenta o mesmo patológico.
- ❌ **Commitar credenciais em `.env`.** Use `.env.example` como template; o real `.env` está no `.gitignore`.
- ❌ **Esquecer de adicionar Bronze TABLE_TABLE config em `BRONZE_TARGETS`.** O `embrapa doctor` não vai checar e o operador descobre só quando a tabela não materializa.
