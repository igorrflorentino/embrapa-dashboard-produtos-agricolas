# Fonte UN COMTRADE — `gold_comtrade_flows`

> **Status:** planejado. Gate de acesso **validado ao vivo** (2026-05-31): a API
> pública responde sem chave (HTTP 200, shape ok), mas corta em **500
> registros/request** (cap. 44 global estoura). Com a **chave gratuita** o limite
> sobe p/ ~100k registros/chamada + uma **cota diária** — então a estratégia é
> **ingestão incremental em fatias (chunked), resumível pela zona raw**.
> Bloqueado só pela chave: o usuário a coloca em `COMTRADE_API_KEY` no `.env`.

## Contexto

O COMEX dá a ótica **do Brasil** (alfândega do MDIC). O **UN Comtrade** dá o
comércio do **mundo inteiro** (todo país que reporta, bilateral por HS), em US$.
Para a Embrapa, adiciona o **contexto competitivo e de mercado global**: tamanho
do mercado mundial de castanha/madeira, ranking de concorrentes (no gate já
apareceu: castanha 080121 2022 — Brasil #1 US$12,9M, Bolívia #2, Nigéria #3),
preços mundiais, e validação-espelho do COMEX.

É a primeira fonte `flows` **global**. Nomenclatura `gold_comtrade_flows` (os
docs já a antecipam).

## Escopo (decidido com o usuário)

- **Produtos:** espelham o COMEX — HS `0801` (castanha) + capítulo `44`
  (madeira/carvão). `COMTRADE_CMD_CODES`.
- **Reporters:** todos (`all`) — visão global.
- **Parceiros:** bilateral (`partnerCode=all`) — a matriz origem→destino completa
  (de quem cada país compra/vende). É o análogo global completo do COMEX.
- **Fluxos:** export (`X`) + import (`M`).
- **Frequência:** anual (`A`) — série completa/autoritativa do Comtrade.
- **Janela:** `COMTRADE_START_YEAR..END_YEAR` (default 2000→corrente).
- Deflação US$→BRL reaproveitando `silver_currency` (BCB USD/EUR ∪ ECB CNY).
- Quantidade no modelo de **família de unidade (#44)**: `qty`+`qtyUnitCode` →
  `family`/`qty_native`/`qty_base`/`base_unit`; `netWgt` como massa-kg paralela.

## Acesso & estratégia incremental (o ponto-chave)

- **Endpoint keyed:** `GET {COMTRADE_API_BASE_URL}/C/A/HS` com header
  `Ocp-Apim-Subscription-Key: <COMTRADE_API_KEY>` + params `reporterCode`,
  `period`, `partnerCode`, `cmdCode`, `flowCode`.
- **Limites (a confirmar ao vivo com a chave):** ~100k registros/chamada + cota
  diária de chamadas (~500/dia no free) + ~1 req/s.
- **Chunking:** unidade = `(ano, fluxo, grupo-de-commodity)`. Castanha (0801,
  poucos HS6) cabe numa chamada; cap. 44 (muitos HS6 × all-reporters ×
  all-partners) pode passar de 100k → split por HS6 ou por reporter.
- **Resumível pela zona raw** (o que torna a cota diária um não-problema): cada
  chunk → arquiva o JSON no `raw/comtrade/.../<chunk>.parquet` → carrega Bronze.
  Se a cota do dia acabar, **para e retoma amanhã** os chunks ainda não
  arquivados (`raw_provenance`/`list_raw` sabem o que já veio — igual ao
  ETag-skip do COMEX e à trilha do BCB). Bronze append + dedup do Silver = o
  "juntar tudo no BigQuery".

## Design técnico (segue os 11 passos do guia, pacote `comtrade/`)

1. **`client.py`** — GET keyed (chave da config, **nunca** logada), retry
   compartilhado (`core/http`), parse JSON → DataFrame (colunas `data[*]`).
   Helper de chunking + (opcional) honra `count`/paginação se um chunk passar do
   limite.
2. **`pipeline.py`** — two-phase: Fase 1 `sync_raw` por chunk (extrai→`land_raw`),
   resumível; Fase 2 `bronze_one` (lê raw→filtra/molda→Bronze). `run(full,
   from_raw)`. Comando `ingest comtrade` multi-chunk (eventos por chunk no
   monitor; continue-on-failure; respeita a cota — para limpo ao bater limite).
3. **`config.py`/`.env`** — `COMTRADE_*` (já wired) + `COMTRADE_API_KEY` (segredo).
4. **Registries** — `cli.INGESTS`, `doctor.SOURCE_CHECKS` (`_check_comtrade`:
   avisa se a chave falta), `doctor.BRONZE_TARGETS`.
5–7. **dbt** — `_sources.yml` (`bronze_comtrade`); `silver_comtrade_flows`
   (dedup por chave natural reporter×partner×cmd×year×flow; `safe_numeric`);
   `gold_comtrade_flows` (grão reporter×partner×cmd×year×flow; deflação via
   `silver_currency`; família via `unit_family_conversions`/`product_unit_factors`).
8. **Seeds** — das tabelas de referência do Comtrade (JSON sem chave em
   `comtradeapi.un.org/files/v1/app/reference/`): `comtrade_country` (M49→ISO/
   nome, p/ reporter **e** partner), `comtrade_unit` (qtyUnitCode→label+família),
   `comtrade_hs` (HS→descrição, filtrado p/ 0801+44).
9. **Testes** — `test_comtrade_client.py` (fixture JSON, sem rede), 
   `test_comtrade_pipeline.py` (chunk/resumível + mocks GCP).
10. **Segredo** — `COMTRADE_API_KEY` no `.env` (gitignored) + GitHub secret no CI.
11. **Docs** — README/ARCHITECTURE/CONTRIBUTING/CHANGELOG.

## Reaproveita / é novo

- **Reaproveita:** zona raw two-phase + resumível; deflação US$ via
  `silver_currency`; família de unidade (#44); padrão `gold_<fonte>_flows`;
  retry HTTP compartilhado; seeds de dimensão (mesmo padrão do COMEX).
- **Novo:** uma **API key** (1º segredo de fonte do projeto); o chunking
  resumível guiado por cota; tabelas de referência próprias do Comtrade.

## Tarefas / PRs

- [x] Gate de acesso (keyless funciona, 500-cap; keyed sobe limite). Config
      `COMTRADE_*` + `.env.example` wired.
- [ ] **Usuário:** colocar `COMTRADE_API_KEY` no `.env`.
- [ ] Validar ao vivo (pela app) os limites reais da chave + shape keyed.
- [ ] **PR-1 (Bronze):** client + pipeline chunked/resumível + config + 3
      registries + testes. `embrapa ingest comtrade` funcional.
- [ ] **PR-2 (dbt):** Silver + Gold + seeds de referência + testes.
- [ ] **PR-3 (docs).**

## Riscos

- **Cota diária** → o backfill global completo leva alguns dias (resumível por
  design; sem perda). Mitigação: chunk fino + `--from-raw` p/ re-derivar sem
  re-chamar a API.
- **Volume do cap. 44 bilateral global** — muitos HS6 × ~200 reporters × ~200
  partners × anos. Mitigação: split por HS6/reporter; Bronze clusterizado;
  considerar incremental no Silver.
- **Espelho ≠ COMEX** — Comtrade usa dados reportados (revisões, "não
  especificados", re-exports); documentar que é a base global reportada, não a
  alfândega-Brasil.
