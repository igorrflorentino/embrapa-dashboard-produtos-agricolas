# Arquitetura Raw Zone — ingestão two-phase para TODAS as fontes

> **Status:** em construção (branch `feat/raw-zone-architecture`, sobre
> `feat/comex-flows`/PR #38). Decisão do usuário (2026-05-30): padronizar o
> modelo two-phase em IBGE PEVS, BCB e COMEX para um pipeline homogêneo.

## Princípio

Toda fonte segue **duas fases** explícitas:

1. **Extract → Raw.** Busca o extrato *verbatim* da fonte e o arquiva no GCS em
   `raw/<source>/<dataset>/<basename>.parquet`, com **metadata de proveniência**
   (URL de origem, ETag/Last-Modified quando houver, `fetched_at`, `rows`).
2. **Raw → Bronze.** Lê o Parquet raw de volta do GCS, aplica o
   filtro/moldagem específico da fonte e carrega a tabela BigQuery **Bronze**.

A partir daí o medalhão (Silver → Gold, dbt) é **inalterado**.

**Por quê.** Desacoplar *fetch* de *load*: re-filtrar, mudar regras ou
re-derivar o Bronze nunca re-bate na fonte — só uma revisão real do dado
(detectada via proveniência, ex. ETag HTTP) dispara um re-fetch. Ganhos:
homogeneidade entre fontes, manutenção simples, adicionar produto/regra fica
barato (re-roda só a Fase 2, lendo do GCS, sem internet), resiliência a
indisponibilidade da fonte, e linhagem/reprodutibilidade científica.

## Layout GCS

```
gs://<bucket>/raw/<source>/<dataset>/<basename>.parquet   (verbatim + metadata)
```

- O prefixo `landing/` filtrado atual é **aposentado** — havia 2 artefatos
  (parquet filtrado no GCS + Bronze no BQ); agora há 1 (raw no GCS) e o Bronze
  BQ deriva dele via `load_table_from_dataframe`.
- Lifecycle: `raw/` ganha as mesmas regras de `landing/` (Nearline@30 →
  Coldline@90 → Archive@365, nunca deleta — trilha de auditoria).

## Contrato compartilhado — `core/raw.py`

| Função | Papel |
|---|---|
| `raw_object_name(settings, source, dataset, basename)` | caminho canônico |
| `land_raw(df, *, settings, storage_client, source, dataset, basename, provenance)` | Fase 1: escreve parquet verbatim + metadata; retorna gs URI |
| `read_raw(storage_client, *, settings, source, dataset, basename)` | Fase 2: lê o parquet raw → DataFrame |
| `raw_provenance(storage_client, *, settings, source, dataset, basename)` | metadata de proveniência (None se ausente) — base p/ checagem de freshness |

A cauda BQ (Fase 2) usa o `gcp/bigquery.load_dataframe` existente. O antigo
`core/bronze.land_and_load` (que acoplava GCS-filtrado + BQ) é
removido/aposentado conforme as fontes migram.

## Mapa por fonte

| Fonte | Fase 1 (raw) | Fase 2 (bronze) | Freshness |
|---|---|---|---|
| **COMEX** | download CSV → Parquet **completo** (todos NCM) → raw | lê raw → filtra NCM/capítulo → Bronze | **ETag/Last-Modified** por arquivo (HEAD) — re-extrai só se mudou; pega revisões de qualquer ano |
| **IBGE PEVS** | SIDRA fetch (já filtrada pela query) → Parquet → raw | lê raw → (typed STRING) → Bronze | re-extrai a janela/chunks por run (POST sem ETag) |
| **BCB** (infl/câmbio) | SGS fetch por série/janela → Parquet → raw | lê raw → projeção de colunas → Bronze | delta por `max(reference_date)` (overlap), como hoje |

## CLI

- `embrapa ingest <source>` → F1 + F2 (extract→raw→bronze).
- `embrapa ingest <source> --from-raw` → só F2 (reprocessa Bronze do raw, **sem
  internet**) — para re-filtrar / aplicar novas regras / mudar produtos.
- `embrapa ingest <source> --raw-only` → só F1 (atualiza o arquivo bruto).

## Ordem de implementação (testes verdes a cada passo)

1. `core/raw.py` + testes + lifecycle `raw/` + `gcs_raw_prefix` no config. **(ref.)**
2. **COMEX** migrado (referência) — client separa extract-raw de filtro;
   pipeline em 2 fases; ETag; CLI; testes.
3. **IBGE** migrado.
4. **BCB** (`series.py` + inflation/currency) migrado.
5. doctor (checagem raw opcional), docs (README/ARCHITECTURE/CHANGELOG).

dbt inalterado (as tabelas/sources Bronze seguem idênticas).

## Riscos & notas

- **Memória no COMEX:** o raw completo é por (fluxo, ano) (~7 MB Parquet cada),
  então a Fase 2 lê um arquivo por vez e filtra — sem carregar 1 GB de uma vez.
- **Assimetria com a forma antiga:** IBGE/BCB já filtram via parâmetros da API,
  então o raw deles == o que era o landing filtrado (conteúdo ~igual); o ganho
  estrutural é a homogeneidade + reprocesso sem re-fetch.
- **Migração de buckets existentes:** dados antigos em `landing/` permanecem
  (lifecycle mantido); o novo fluxo escreve em `raw/`. Sem migração destrutiva.
