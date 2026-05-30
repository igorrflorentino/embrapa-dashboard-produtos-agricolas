# Fonte COMEX — `gold_comex_flows`

> **Status:** gate de validação ao vivo **CONCLUÍDO** (2026-05-30, Claude Code
> local). Shape do CSV confirmado contra `EXP_*.csv` / `IMP_*.csv` reais
> (headers 1997→2026, linhas de castanha + cap.44). Pronto para PR-1 (Bronze).
> Achado principal: **IMP traz 2 colunas a mais que EXP** (`VL_FRETE`,
> `VL_SEGURO`) — Bronze precisa de schema-union. Ver "Validação ao vivo" abaixo.

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
- Colunas-fonte **CONFIRMADAS ao vivo** (2026-05-30):
  - **EXP (11 col):**
    `CO_ANO;CO_MES;CO_NCM;CO_UNID;CO_PAIS;SG_UF_NCM;CO_VIA;CO_URF;QT_ESTAT;KG_LIQUIDO;VL_FOB`
  - **IMP (13 col):** as 11 do EXP **+ `VL_FRETE;VL_SEGURO`**.
  - Aspas mistas: colunas de texto entre `"`, numéricas (`QT_ESTAT` em diante)
    sem aspas — `pandas(sep=";", quotechar='"', dtype=str)` lê ambos os casos.
  - `CO_NCM` 8 dígitos zero-padded e entre aspas; `CO_MES` 2 dígitos
    zero-padded; `CO_PAIS` é **código numérico** (ex. `160`, `764` — precisa de
    seed `country_iso` p/ nome); `SG_UF_NCM` é a sigla de 2 letras da UF.
  - **Filtro tem de ser coluna-preciso em `CO_NCM`/`CO_NCM[:2]`** — um grep de
    substring `"44` na linha crua casa falsamente com `CO_PAIS=445` etc.

**2. Pipeline (`comex/pipeline.py`) — `run()` próprio** (shape ≠ SGS, então não
usa `bcb.series`):
- **Delta por `(fluxo, ano)`**: re-busca sempre o ano corrente (revisado
  mensalmente pelo MDIC) e pula anos passados já carregados. Mais natural que o
  delta-por-`reference_date` do BCB. Usar `latest_reference_date` ou um lookup
  de anos distintos já em Bronze.
- Cauda land→load via `core.land_and_load` (não reescrever).
- Bronze: todas as colunas STRING + `ingestion_timestamp`; chave natural
  `(flow, CO_ANO, CO_MES, CO_NCM, CO_PAIS, SG_UF_NCM)`.
- **Schema-union EXP+IMP:** o Bronze é UMA tabela com as 13 colunas do IMP;
  linhas de export gravam `VL_FRETE`/`VL_SEGURO` como NULL. O client deve
  reindexar o DataFrame para o superset de colunas antes do load (não confiar
  na ordem/contagem por fluxo). Coluna `flow` (`export`/`import`) adicionada
  pelo pipeline, não vem do CSV.

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

**10. Segredo:** nada — fonte pública sem auth. **Mas:** o host
`balanca.economia.gov.br` serve só o cert folha e **omite a intermediária
TLS** (Sectigo R36) — `requests`/certifi falha com `CERTIFICATE_VERIFY_FAILED`
(o `curl` passa por buscar a intermediária via AIA / trust store do SO). Sem
isso a ingestão real não funciona em lugar nenhum (incl. CI Linux/Cloud Run).
Mitigação **sem desabilitar verificação**: a intermediária pública está
vendorizada em `comex/_ca.py` e o client a anexa ao bundle do `certifi` em
runtime (`verify=`). Re-vendorizar se o host rotacionar a CA (válida até 2036).

**11. Docs:** README/ARCHITECTURE (caixas Bronze+Consumo), CONTRIBUTING (escopo
`comex`), CHANGELOG (`[Unreleased]/Added`).

## Tarefas

- [x] **Validar CSV ao vivo** (local, 2026-05-30): headers de
      `EXP_{1997,2023,2026}` / `IMP_{1997,2023,2026}` confirmados via range
      requests; separador `;` + latin-1 + aspas mistas; linhas de castanha
      (`08012100`/`08012200`) e cap.44 (`44072920`/`44091000`) presentes em
      EXP_2023. **Gate liberado.** Achado: IMP = EXP + `VL_FRETE`/`VL_SEGURO`.
- [x] Revisar/aprovar este plano à luz do shape confirmado.
- [x] **PR-1 (Bronze ponta-a-ponta):** pacote `comex/` (`client.py` stream-para-
      disco + filtro coluna-preciso, `pipeline.py` delta por `(fluxo, ano)`,
      `_ca.py` cadeia TLS), config + properties, 3 registries, comando `ingest
      comex` multi-chunk, `_check_comex` no doctor. `test_comex_client.py` +
      `test_comex_pipeline.py` (274 testes verdes). `embrapa ingest comex`
      funcional — validado ao vivo: EXP_2026 baixado e filtrado (6157 linhas,
      só cap. 08+44, 126 de castanha). **Pendente:** rodar `ingest comex` real
      contra o BQ do usuário (precisa ADC + projeto).
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
