# Fonte COMEX — `gold_comex_flows`

> **Status:** planejado, não iniciado. Bloqueado para validação ao vivo no
> ambiente Claude Code on the web (host dos CSVs em massa fora da allowlist de
> rede); retomar no Claude Code local, com internet liberada.

## Contexto

O backend está preparado para multi-fonte (registries `cli.INGESTS`,
`doctor.SOURCE_CHECKS`/`BRONZE_TARGETS`, primitivos `core/http.py` +
`core/bronze.py`, guia `docs/adding_a_data_source.md`). Hoje só há uma fonte de
*produção* (IBGE PEVS → `gold_pevs_production`) enriquecida por câmbio/inflação
do BCB.

Adicionar **COMEX (comércio exterior, MDIC)** é o maior multiplicador de valor
para a audiência científica da Embrapa: cruza **produção × comércio × câmbio ×
inflação** do mesmo produto, e valida o design `gold_<fonte>_<forma>` (a forma
`flows` — fluxo origem→destino — ainda não existia).

## Escopo

**Incluído (decidido com o usuário):**

- **Fonte de dados:** bulk CSV do Comex Stat — `EXP_<ano>.csv` / `IMP_<ano>.csv`
  em `https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/`
  (`;`-separado, latin-1, um arquivo por ano por fluxo, histórico desde 1997).
  **NÃO usar a API JSON** (ver Riscos).
- **Fluxo:** export **e** import (coluna `flow`).
- **Produtos:** castanha-do-pará/brasil (NCM `08012100` com casca, `08012200`
  sem casca) + **capítulo 44 inteiro** (madeira e carvão vegetal — qualquer NCM
  cujos 2 primeiros dígitos sejam `44`).
- **Grão Gold:** mês × NCM × país × UF → `gold_comex_flows` (forma `flows`).
- Deflação monetária reaproveitando as Silver compartilhadas
  (`silver_bcb_inflation`, `silver_bcb_currency`) via `ref()`, aplicando as 4
  convenções do projeto (`val_yearfx_*`, `val_real_{ipca,igpm,igpdi}_*`) sobre
  `VL_FOB` (US$).

**Excluído:**

- Pré-agregações (estado-ano, nacional): agregar em tempo de query via
  `GROUP BY` — UMA tabela comprehensiva por fonte.
- Forçar COMEX dentro de `gold_pevs_production` (grãos incompatíveis).
- Frontend / Looker (consome a Gold depois, fora deste escopo).

## Design Técnico

Seguindo os 11 passos de `docs/adding_a_data_source.md`. Pacote
`src/embrapa_commodities/comex/`.

**1. Client (`comex/client.py`) — downloader de CSV, não API JSON.**
- Download via **GET** dos arquivos anuais (dezenas/centenas de MB) — **stream
  para disco temporário**, não drain-em-memória (arquivo grande leva minutos
  legitimamente; reavaliar/relaxar o deadline slow-byte do `core/http.py`, que
  foi desenhado para respostas pequenas).
- Erros `ComexRequestError` / `ComexTransientError(SourceTransientError)` para
  herdar o retry compartilhado.
- Parsing com pandas (`sep=";"`, `encoding="latin-1"`, `dtype=str`), filtrando
  localmente: `CO_NCM in ncm_codes OR CO_NCM[:2] in chapter_codes`.
- Colunas-fonte esperadas (CONFIRMAR AO VIVO antes de codar):
  `CO_ANO;CO_MES;CO_NCM;CO_UNID;CO_PAIS;SG_UF_NCM;CO_VIA;CO_URF;QT_ESTAT;KG_LIQUIDO;VL_FOB`.

**2. Pipeline (`comex/pipeline.py`) — `run()` próprio** (shape ≠ SGS, então não
usa `bcb.series`):
- **Delta por `(fluxo, ano)`**: re-busca sempre o ano corrente (revisado
  mensalmente pelo MDIC) e pula anos passados já carregados. Mais natural que o
  delta-por-`reference_date` do BCB. Usar `latest_reference_date` ou um lookup
  de anos distintos já em Bronze.
- Cauda land→load via `core.land_and_load` (não reescrever).
- Bronze: todas as colunas STRING + `ingestion_timestamp`; chave natural
  `(flow, CO_ANO, CO_MES, CO_NCM, CO_PAIS, SG_UF_NCM)`.

**3. Config (`config.py` + `.env.example`):** `BQ_BRONZE_COMEX_DATASET`,
`BQ_BRONZE_COMEX_FLOWS_TABLE`, `COMEX_CSV_BASE_URL`, `COMEX_FLOWS`
(`export,import`), `COMEX_NCM_CODES` (CODE:LABEL), `COMEX_CHAPTER_CODES`
(CODE:LABEL), `COMEX_START_YEAR=1997`, `COMEX_END_YEAR`. Properties espelhando
`*_map` / `*_list` com validação (reusar `_parse_code_label`).

**4. Registries:** `cli.INGESTS` += spec; comando `ingest comex` manuscrito
(multi-chunk por ano → copiar a estrutura de `ingest_ibge_batch`, que emite
`chunk_*` por ano, em vez do `pipeline_run` single-shot); `doctor.SOURCE_CHECKS`
+= `_check_comex`; `doctor.BRONZE_TARGETS` += entry COMEX.

**5–7. dbt:** `_sources.yml` (bloco `bronze_comex`); `silver_comex_flows.sql`
(dedup por `qualify row_number()` na chave natural; `safe_numeric()` em
`VL_FOB`/`KG_LIQUIDO`); `gold_comex_flows.sql` (grão mês×NCM×país×UF + CTEs de
deflação por `ref(silver_bcb_*)`). Testes em `_silver.yml` / `_gold.yml`.

**8. Seeds (opcional):** `hs_ncm.csv` (NCM→label legível) se quisermos nomes em
vez de códigos; `country_iso.csv` para resolver `CO_PAIS`.

**9. Testes Python:** `test_comex_client.py` (CSV fixture local, sem rede —
parsing + filtro cap.44/NCM); `test_comex_pipeline.py` (delta por ano + mocks
GCP, copiar padrão de `test_bcb_series.py`).

**10. Segredo:** nada — fonte pública sem auth.

**11. Docs:** README/ARCHITECTURE (caixas Bronze+Consumo), CONTRIBUTING (escopo
`comex`), CHANGELOG (`[Unreleased]/Added`).

## Tarefas

- [ ] **Validar CSV ao vivo** (local): baixar header de `EXP_2023.csv` /
      `IMP_2023.csv`, confirmar separador/encoding/colunas e o filtro cap.44 +
      2 NCMs de castanha. **Gate — não codar o client antes disto.**
- [ ] Revisar/aprovar este plano à luz do shape confirmado.
- [ ] **PR-1 (Bronze ponta-a-ponta):** client + pipeline + config + 3
      registries + testes Python. `embrapa ingest comex` funcional.
- [ ] **PR-2 (dbt):** Silver + Gold + testes dbt + seeds (se aplicável).
- [ ] **PR-3 (docs):** README/ARCHITECTURE/CONTRIBUTING/CHANGELOG.

## Riscos & Mitigações

- **API JSON descartada por integridade.** A API POST `/general` retornava
  **silenciosamente o total Brasil agregado quando o filtro vinha malformado,
  com HTTP 200** — risco de ingerir dado errado sem erro. Por isso usamos o bulk
  CSV (base bruta autoritativa, filtrada e inspecionada localmente).
- **Host bloqueado no ambiente web.** `balanca.economia.gov.br` falha no proxy
  do Claude Code on the web (`upstream connect error ... CERTIFICATE_VERIFY_FAILED`,
  host fora da allowlist). **Mitigação:** desenvolver no Claude Code local (rede
  liberada). Alternativa: ajustar a network policy do ambiente
  (code.claude.com/docs) + recriar a sessão.
- **Arquivos grandes.** Stream-para-disco + filtro early; reavaliar o deadline
  slow-byte do `core/http.py` (desenhado para payloads pequenos).
- **Volume do capítulo 44 inteiro.** Muitos NCMs × países × UFs × meses ×
  décadas. Mitigação: clustering Bronze por chave natural; particionar por
  `ingestion_timestamp`; considerar incremental no Silver (como
  `silver_ibge_pevs`).

## Critérios de Aceite

- `uv run pytest` verde (inclui `test_comex_*`); `ruff check`/`format` limpos.
- `embrapa ingest comex` aterrissa Bronze; `embrapa doctor` inclui check
  `comex`; `ingest --help` lista o subcomando.
- `dbt build --select silver_comex_flows+ gold_comex_flows+` verde em dev.
- `embrapa backup-gold` cita `gold_comex_flows` automaticamente (introspecção).
- Sanidade de dados: linhas batem mês×NCM×país×UF; `VL_FOB` deflacionado nas 4
  convenções; castanha + cap.44 presentes, demais NCMs ausentes.
