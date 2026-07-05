// enrichment.js — the researcher ENRICHMENT store (Engenharia de Atributos), API-backed.
//
// TWO institutional axes are editable:
//   (1) CODE-level industrialization — an 8-level ordinal scale from a raw commodity
//       (Commodity Pura) to a specialized manufactured good (Manufaturado Especializado).
//       Worklist: /api/attributes/worklist (Gold DISTINCT codes ⟕ the append-only SCD2
//       classification log); drives window.valueAddedAnalysis (→ /api/cross/value-added).
//   (2) MARKET NATURE — the REAL COMTRADE customs procedure (customsCode) × flow grid from
//       /api/attributes/flow-worklist, carrying each pair's USD value so the researcher
//       classifies by materiality; drives window.marketNatureAnalysis (→ /api/cross/market-nature).
//       Reverted from the comtrade_market_nature seed (v1.9.0) back to the editable matrix.
//
// Edits stage in local drafts and commit via POST on "Aplicar à base" (the append-only
// writers, author captured from IAP), gated downstream by the `enable_curation` dbt var.
// The matrix editor reflects an edit instantly (the live SCD2 view); the "Tipo de mercado"
// filter + "Finalidade econômica" analysis reflect it after the next dbt build (the mart
// column is materialized). The customs code is mapped to human pt-BR labels via CUSTOMS_DESC
// below (authoritative source: UN Comtrade CustomsCodes.json); the flow via FLOW_DESC, keyed
// by the NORMALIZED flow token (export/import/…, matching the mart's flow column).

import { ensure, get, invalidate, subscribe as subscribeResource } from './resource';

const API = '/api';
const WL_KEY = 'curation:worklist'; // code-level industrialization worklist
const FW_KEY = 'curation:flow-worklist'; // customsCode × flow market matrix

// ── static registries (industrialization levels + the economic-purpose markets) ──
// The 8 industrialization levels, ORDERED least→most processed (the ordinal drives the
// value-added gradient chart + the most-vs-least "prêmio de processamento"). `id` is the
// stored slug (open-vocabulary in the backend); `description` is the researcher-facing
// definition shown in the editor + reference legend.
window.ENRICH_LEVELS = [
  { id: 'commodity_pura', label: 'Commodity Pura', color: 'var(--viz-3)',
    description: 'Produto em estado original, sem nenhuma modificação pós-colheita ou extração.' },
  { id: 'commodity_higienizada', label: 'Commodity Higienizada', color: 'var(--viz-5)',
    description: 'Produto passou por algumas etapas simples de limpeza, como tratamento contra microorganismos e remoção de elementos indesejáveis (sujeira, parasitas, terra e afins).' },
  { id: 'commodity_acondicionada', label: 'Commodity Acondicionada', color: 'var(--viz-2)',
    description: 'Produto passou por algumas etapas simples de aperfeiçoamento, como remoção de cascas e excessos e compartimentalização em tamanhos e recipientes específicos (cortes, sacas, perfilamento e afins).' },
  { id: 'commodity_consumivel', label: 'Commodity Consumível', color: 'var(--viz-4)',
    description: 'Produto passou por todas as etapas necessárias para poder ser usado como insumo em uma nova cadeia industrial (transformado, combinado e afins) ou ser consumido diretamente como produto fim.' },
  { id: 'commodity_subproduto', label: 'Commodity Subproduto', color: 'var(--viz-8)',
    description: 'Produto que sobrou de alguma etapa anterior de processamento e ainda pode ser usado ou reaproveitado em alguma cadeia produtiva ou ser consumido diretamente.' },
  { id: 'manufaturado_artesanal', label: 'Manufaturado Artesanal', color: 'var(--viz-6)',
    description: 'Produto que passou por um processamento de diferenciação de forma manual, sem processo ou etapas de construção definidos ou padronizados.' },
  { id: 'manufaturado_industrial', label: 'Manufaturado Industrial', color: 'var(--viz-1)',
    description: 'Produto que passou por um processamento de diferenciação de forma industrial, com um processo ou etapas de construção bem definidos e padronizados.' },
  { id: 'manufaturado_especializado', label: 'Manufaturado Especializado', color: 'var(--viz-9)',
    description: 'Produto que passou por um processamento de diferenciação com exclusividade intelectual, em geral envolvendo camadas de propriedade intelectual como inovações e patentes.' },
];
// The economic-purpose markets (consumo/processamento) the matrix classifies — consumed by
// the "Finalidade econômica" analysis (ViewCuratedAnalyses) + the matrix cells.
window.ENRICH_MARKETS = [
  { id: 'consumo', label: 'Consumo', short: 'Consumo', color: 'var(--viz-1)' },
  { id: 'processamento', label: 'Processamento', short: 'Processamento', color: 'var(--viz-9)' },
];
// Derived from the live code worklist rows (commodity → name) at read time.
window.ENRICH_GROUPS = [];

// ── customs-procedure code → human pt-BR label + researcher tooltip (matrix rows) ──
// The matrix rows are UN Comtrade `customsCode` values (WCO customs procedures, prefix C).
// Authoritative meanings: UN Comtrade CustomsCodes.json reference (NOT the EU/UK CDS
// C-series, a different classification). The `hint` is a plain sentence for an agricultural
// researcher; regimes() appends the traded value.
const CUSTOMS_DESC = {
  C01: { label: 'Despacho para consumo',         hint: 'Importação nacionalizada: mercadoria estrangeira liberada para circular e ser consumida no país após o recolhimento dos tributos — destino típico de abastecimento do mercado interno.' },
  C02: { label: 'Reimportação no mesmo estado',  hint: 'Retorno ao país de um bem que havia sido exportado, sem transformação no exterior (ex.: devolução) — não representa nova produção nem agregação de valor.' },
  C03: { label: 'Exportação definitiva',         hint: 'Saída definitiva de mercadoria nacional para o exterior, sem previsão de retorno — a exportação comum, que escoa a produção do país.' },
  C04: { label: 'Entreposto aduaneiro',          hint: 'Mercadoria armazenada sob controle aduaneiro, com tributos suspensos, antes de definir o destino (consumo, reexportação ou industrialização) — ponto de espera logístico, não destino final.' },
  C05: { label: 'Zona franca',                   hint: 'Área com incentivos fiscais e aduaneiros (ex.: Zona Franca de Manaus); a mercadoria entra com tributação reduzida, em geral para transformação industrial.' },
  C06: { label: 'Aperfeiçoamento ativo',         hint: 'Importação temporária de insumos, com suspensão de tributos, para industrialização no país e posterior reexportação — sinaliza uso industrial, não consumo final.' },
  C07: { label: 'Aperfeiçoamento passivo',       hint: 'Exportação temporária de um bem para beneficiamento ou reparo no exterior, com retorno ao país — o valor é agregado fora do território nacional.' },
  C08: { label: 'Drawback',                      hint: 'Regime de incentivo à exportação que suspende ou restitui os tributos dos insumos importados usados na fabricação de um produto a ser exportado — produção voltada ao mercado externo.' },
  C09: { label: 'Transformação para consumo interno', hint: 'Industrialização da mercadoria importada sob controle aduaneiro, com os tributos incidindo sobre o produto já transformado, destinado ao mercado interno — uso industrial voltado ao consumo nacional.' },
  C10: { label: 'Cabotagem',                      hint: 'Transporte de mercadoria entre pontos do próprio país por via marítima ou fluvial — movimentação interna, não comércio com o exterior.' },
  C11: { label: 'Infrações aduaneiras',          hint: 'Operações associadas a apreensões ou irregularidades aduaneiras — não refletem fluxo comercial regular; interprete com cautela.' },
  C12: { label: 'Viajantes',                      hint: 'Bens trazidos ou levados por viajantes (bagagem) — volumes pequenos e de uso pessoal, sem caráter de mercado.' },
  C13: { label: 'Tráfego postal',                hint: 'Mercadorias movimentadas pelo correio (remessas postais) — em geral de pequeno porte.' },
  C14: { label: 'Provisões de bordo',            hint: 'Combustíveis, alimentos e suprimentos embarcados em navios e aeronaves para consumo durante a viagem — não é mercadoria destinada a um mercado.' },
  C15: { label: 'Remessas de socorro',           hint: 'Doações e ajuda humanitária — fluxo de natureza não comercial.' },
  C20: { label: 'Procedimento não especificado', hint: 'Operação aduaneira não enquadrada nas demais categorias — agrupa registros sem classificação própria; interprete com cautela.' },
};

// ── flow token → pt-BR label + tooltip (matrix columns) ───────────────────────
// Keyed by the NORMALIZED flow token (serving_comtrade_annual.flow / the log's flow_code),
// NOT the raw UN code (X/M/RX). Authoritative names from the UN Comtrade "trade regimes"
// reference (comtradeapi.un.org/files/v1/app/reference/tradeRegimes.json — exactly 10 codes).
// `label` is the column header (the backend _FLOW_LABELS overrides it when the flow is present
// in the data); flowTypes() appends the token in parentheses. Only export/import/re-export/
// re-import occur in the current data; the rest are shown for completeness.
const FLOW_DESC = {
  import:                    { label: 'Importação',                              hint: 'Entrada de mercadoria estrangeira no território nacional, qualquer que seja o destino (consumo, estoque ou industrialização).' },
  export:                    { label: 'Exportação',                              hint: 'Saída de mercadoria do país para o exterior; pode englobar produção nacional e reexportações, conforme o detalhamento da fonte.' },
  'national-export':         { label: 'Exportação nacional',                     hint: 'Exportação de mercadoria efetivamente produzida no país (domestic export), distinta da simples reexportação.' },
  'foreign-import':          { label: 'Importação estrangeira',                  hint: 'Importação de mercadoria de origem estrangeira (foreign import) — contrapartida da exportação nacional do país parceiro.' },
  'import-inward-processing':  { label: 'Importação para aperfeiçoamento ativo',   hint: 'Importação temporária de mercadoria que entra no país para ser industrializada ou beneficiada e depois reexportada (regime de aperfeiçoamento ativo).' },
  'import-outward-processing': { label: 'Importação após aperfeiçoamento passivo', hint: 'Retorno ao país de mercadoria nacional que havia sido exportada temporariamente para beneficiamento no exterior (regime de aperfeiçoamento passivo).' },
  're-import':               { label: 'Reimportação',                            hint: 'Reentrada de mercadoria que havia sido exportada, sem transformação no exterior (ex.: devoluções) — não caracteriza nova importação para consumo.' },
  're-export':               { label: 'Reexportação',                            hint: 'Reexportação de mercadoria antes importada, sem ter sido transformada no país — indica papel de entreposto/intermediação, não de produção própria.' },
  'export-inward-processing':  { label: 'Exportação após aperfeiçoamento ativo',   hint: 'Saída do país de mercadoria já industrializada ou beneficiada internamente a partir de insumos importados em regime de aperfeiçoamento ativo.' },
  'export-outward-processing': { label: 'Exportação para aperfeiçoamento passivo', hint: 'Exportação temporária de mercadoria nacional enviada ao exterior para beneficiamento, com previsão de retorno (regime de aperfeiçoamento passivo).' },
};
// Canonical orders for the COMPLETE matrix — every known regime (rows) × every known flow
// (columns) is shown, so the table holds ALL combinations and is ready for any data
// granularity, even before a given pair appears in the data. Flow order mirrors the UN
// Comtrade reference (import side, then export side).
const FLOW_ORDER = [
  'import', 'export', 'national-export', 'foreign-import', 'import-inward-processing',
  'import-outward-processing', 're-import', 're-export', 'export-inward-processing',
  'export-outward-processing',
];
const CUSTOMS_ORDER = Object.keys(CUSTOMS_DESC);

// ── USD formatter (compact, for the matrix cell + row hints) ──────────────────
const fmtUsdShort = (v) => {
  const n = Number(v || 0);
  if (n >= 1e9) return 'US$ ' + (n / 1e9).toFixed(n >= 1e10 ? 0 : 1) + ' bi';
  if (n >= 1e6) return 'US$ ' + (n / 1e6).toFixed(0) + ' mi';
  if (n >= 1e3) return 'US$ ' + (n / 1e3).toFixed(0) + ' mil';
  return 'US$ ' + n.toFixed(0);
};

// A fresh idempotency key (change_id) per staged edit. The backend dedupes a retried POST
// carrying the SAME change_id (e.g. a network timeout that actually landed server-side →
// re-POST is a no-op instead of a duplicate revision). We mint one when the edit is STAGED,
// not per-POST, so retries reuse it but a fresh user action always gets a new key.
const newChangeId = () =>
  globalThis.crypto && globalThis.crypto.randomUUID
    ? globalThis.crypto.randomUUID()
    : 'cid-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);

// ── subscriber fan-out (editor re-renders on draft + resource changes) ─────────
const subs = new Set();
const notify = () => {
  for (const fn of subs) {
    try {
      fn();
    } catch {
      /* keep other subscribers alive */
    }
  }
};
subscribeResource(notify); // re-notify when either worklist resource resolves

// ── (1) code-level worklist (API ⟕ draft) ─────────────────────────────────────
const draft = new Map(); // id -> level (a staged change vs the API level)
const draftCid = new Map(); // id -> change_id (idempotency key, stable across retries)
let committing = false;
let lastError = null; // last write failure (HTTP status / message), surfaced in the editor

const apiRows = () => {
  const wl = get(WL_KEY);
  return (wl && wl.rows) || [];
};
const rowId = (r) => `${r.source}:${r.code}`;

function worklist() {
  ensure(WL_KEY, () => `${API}/attributes/worklist`);
  const groupLabels = {};
  const rows = apiRows().map((r) => {
    const id = rowId(r);
    const apiLevel = r.level || null;
    const level = draft.has(id) ? draft.get(id) : apiLevel;
    if (r.commodity) groupLabels[r.commodity] = r.agrupamento_nome || r.commodity;
    return {
      id,
      group: r.commodity || '_sem_grupo',
      source: r.source,
      code: r.code,
      desc: r.name || r.code,
      level,
      status: level ? 'classificado' : 'a-classificar',
    };
  });
  window.ENRICH_GROUPS = Object.entries(groupLabels).map(([id, label]) => ({ id, label }));
  return rows;
}

// ── (2) flow-market matrix (real COMTRADE customsCode × flow ⟕ draft) ──────────
const flowDraft = new Map(); // `${customs}:${flow}` -> market ('' clears)
const flowDraftCid = new Map(); // `${customs}:${flow}` -> change_id (idempotency key)

function flowWorklist() {
  ensure(FW_KEY, () => `${API}/attributes/flow-worklist`);
  return get(FW_KEY) || { customs: [], flows: [], cells: [], classified: 0, total: 0 };
}
// `${customs}:${flow}` -> cell {customs_code, flow_code, value_usd, market}.
function cellMap() {
  const m = new Map();
  flowWorklist().cells.forEach((c) => m.set(`${c.customs_code}:${c.flow_code}`, c));
  return m;
}
// Effective market for a pair = staged draft if any, else the persisted value. Pass a
// pre-built `map` (from cellMap()) when calling in a loop so the cell Map isn't rebuilt on
// every invocation; single calls omit it.
function effMarket(customs, flow, map) {
  const k = `${customs}:${flow}`;
  if (flowDraft.has(k)) return flowDraft.get(k) || null;
  const cell = (map || cellMap()).get(k);
  return (cell && cell.market) || null;
}

window.enrichment = {
  codes: () => worklist(),
  worklist: () => worklist(),

  // Matrix ROWS = the COMPLETE set of customs-procedure codes: every canonical regime
  // (CUSTOMS_ORDER) unioned with any extra code present in the data, so the table holds ALL
  // regimes and is ready for any data granularity. Ordered by total traded value desc
  // (material regimes on top), then by canonical order for the zero-value tail. Each code
  // maps to a human pt-BR name + tooltip via CUSTOMS_DESC; the traded value is appended to
  // the tooltip (or a "no records yet" note when it is zero).
  regimes() {
    const wl = flowWorklist();
    const totals = {};
    wl.cells.forEach((c) => {
      totals[c.customs_code] = (totals[c.customs_code] || 0) + (c.value_usd || 0);
    });
    const all = Array.from(new Set([...CUSTOMS_ORDER, ...wl.customs]));
    const orderIdx = (code) => {
      const i = CUSTOMS_ORDER.indexOf(code);
      return i === -1 ? CUSTOMS_ORDER.length : i;
    };
    return all
      .sort((a, b) => (totals[b] || 0) - (totals[a] || 0) || orderIdx(a) - orderIdx(b))
      .map((code) => {
        const d = CUSTOMS_DESC[code];
        const name = d ? `${d.label} (${code})` : `Regime aduaneiro ${code}`;
        const meaning = d
          ? d.hint
          : `Regime aduaneiro ${code} do comércio exterior (código UN Comtrade), sem descrição cadastrada.`;
        const value = totals[code] || 0;
        const valueNote = value
          ? `Total transacionado: ${fmtUsdShort(value)}.`
          : 'Ainda sem registros nos dados atuais.';
        return { id: code, term: name, label: name, hint: `${meaning} ${valueNote}` };
      });
  },
  // Matrix COLUMNS = the COMPLETE set of flow tokens: every canonical flow (FLOW_ORDER)
  // unioned with any extra token present in the data. The pt-BR label comes from the backend
  // when the flow is present, otherwise from FLOW_DESC; the tooltip is the direction's meaning.
  flowTypes() {
    const present = flowWorklist().flows;
    const labelOf = {};
    present.forEach((f) => {
      labelOf[f.code] = f.label;
    });
    const all = Array.from(new Set([...FLOW_ORDER, ...present.map((f) => f.code)]));
    const orderIdx = (code) => {
      const i = FLOW_ORDER.indexOf(code);
      return i === -1 ? FLOW_ORDER.length : i;
    };
    return all
      .sort((a, b) => orderIdx(a) - orderIdx(b))
      .map((code) => {
        const d = FLOW_DESC[code];
        const base = labelOf[code] || (d && d.label) || `Fluxo ${code}`;
        const name = `${base} (${code})`; // keep the token, like the customs rows
        const meaning = (d && d.hint) || `Fluxo comercial ${code} (UN Comtrade).`;
        return { id: code, term: name, label: name, hint: meaning };
      });
  },
  pairMarket: (customs, flow) => effMarket(customs, flow),
  // The per-cell traded value (formatted) — empty when the pair has no COMTRADE rows.
  // Shown in the matrix so the researcher classifies what actually matters.
  pairValueLabel(customs, flow) {
    const cell = cellMap().get(`${customs}:${flow}`);
    if (!cell || !cell.value_usd) return '';
    return fmtUsdShort(cell.value_usd);
  },

  levelLabel: (id) => (window.ENRICH_LEVELS.find((l) => l.id === id) || {}).label || id,
  levelColor: (id) => (window.ENRICH_LEVELS.find((l) => l.id === id) || {}).color || 'var(--fg-3)',
  levelDesc: (id) => (window.ENRICH_LEVELS.find((l) => l.id === id) || {}).description || '',
  groupLabel: (id) => (window.ENRICH_GROUPS.find((g) => g.id === id) || {}).label || id,

  // Chapter derived from the code prefix (NCM/HS by leading 2 digits; PEVS by group).
  chapterOf(source, code) {
    if (source === 'ibge_pevs') {
      const s = String(code).split('.')[0];
      return { 1: 'Produtos alimentícios', 2: 'Produtos madeireiros' }[s] || `Grupo ${s}`;
    }
    const ch = String(code).slice(0, 2);
    return (
      { '08': '08 · Frutas e castanhas', 44: '44 · Madeira e carvão', 20: '20 · Preparações de frutas' }[ch] ||
      `${ch} · Outros`
    );
  },

  // Stage a level edit relative to the API state (matching the API level unstages).
  setCode(id, patch) {
    if (!patch || !('level' in patch) || !patch.level) return;
    const r = apiRows().find((x) => rowId(x) === id);
    const apiLevel = (r && r.level) || null;
    if (patch.level === apiLevel) {
      draft.delete(id);
      draftCid.delete(id);
    } else {
      draft.set(id, patch.level);
      draftCid.set(id, newChangeId()); // fresh idempotency key for this staging
    }
    lastError = null; // a fresh edit clears the stale write error
    notify();
  },
  // Stage a (customs, flow) → market edit. Matching the persisted value unstages; an empty
  // market stages a CLEAR (the writer records market='' = "a classificar").
  setPair(customs, flow, market) {
    const k = `${customs}:${flow}`;
    const cell = cellMap().get(k);
    const apiMarket = (cell && cell.market) || null;
    const next = market || null;
    if (next === apiMarket) {
      flowDraft.delete(k);
      flowDraftCid.delete(k);
    } else {
      flowDraft.set(k, market || '');
      flowDraftCid.set(k, newChangeId()); // fresh idempotency key for this staging
    }
    lastError = null; // a fresh edit clears the stale write error
    notify();
  },

  pendingCount: () => draft.size + flowDraft.size,
  isDirty() {
    return draft.size > 0 || flowDraft.size > 0;
  },
  isCommitting: () => committing,
  // The last write failure (e.g. "HTTP 401" when no IAP author), or null. The editor
  // renders this so a failed commit is visible — not silently swallowed.
  lastError: () => lastError,

  // Commit BOTH drafts → POST each staged edit to its append-only writer, then re-fetch the
  // worklists (now reflecting the writes). Locks while committing so a double-click can't
  // write duplicate revisions. Uses allSettled so a partial failure DROPS only the edits that
  // actually landed (the SCD2 logs are append-only — re-POSTing a succeeded edit would write
  // a redundant revision); the failures stay staged and lastError is surfaced.
  apply(onDone) {
    if (committing || (draft.size === 0 && flowDraft.size === 0)) return;
    committing = true;
    lastError = null; // clear any prior failure before a new attempt
    notify();
    const post = (path, body) =>
      fetch(`${API}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      });
    // One task per staged edit, tagged with the draft it came from so a landed edit can be
    // dropped individually (and a retry re-POSTs only the failures).
    const tasks = [
      ...[...draft.entries()].map(([id, level]) => {
        const [source, code] = id.split(':');
        const change_id = draftCid.get(id);
        return {
          store: draft,
          cidStore: draftCid,
          key: id,
          run: () => post('/attributes/code-level', { source, code, level, change_id }),
        };
      }),
      ...[...flowDraft.entries()].map(([k, market]) => {
        const [customs_code, flow_code] = k.split(':');
        const change_id = flowDraftCid.get(k);
        return {
          store: flowDraft,
          cidStore: flowDraftCid,
          key: k,
          run: () => post('/attributes/flow-market', { customs_code, flow_code, market, change_id }),
        };
      }),
    ];
    Promise.allSettled(tasks.map((t) => t.run())).then((results) => {
      let failed = 0;
      results.forEach((res, i) => {
        if (res.status === 'fulfilled') {
          tasks[i].store.delete(tasks[i].key); // landed → drop so a retry won't re-POST it
          tasks[i].cidStore.delete(tasks[i].key); // and drop its idempotency key
        } else {
          failed += 1;
          lastError = (res.reason && res.reason.message) || 'Falha ao gravar a curadoria';
        }
      });
      invalidate(WL_KEY); // reflect whatever landed (full OR partial)
      invalidate(FW_KEY);
      committing = false;
      notify();
      if (failed === 0 && typeof onDone === 'function') {
        try {
          onDone();
        } catch {
          /* ignore callback error */
        }
      }
    });
  },
  discard() {
    if (committing) return;
    draft.clear();
    draftCid.clear();
    flowDraft.clear();
    flowDraftCid.clear();
    lastError = null;
    notify();
  },
  subscribe(fn) {
    subs.add(fn);
    return () => subs.delete(fn);
  },

  stats() {
    const wl = worklist();
    const byLevel = {};
    window.ENRICH_LEVELS.forEach((l) => {
      byLevel[l.id] = wl.filter((c) => c.level === l.id).length;
    });
    // Count over the COMPLETE matrix (all regimes × all flows), matching what the editor
    // renders, so "classificadas / total" reflects the full grid.
    const regimes = this.regimes();
    const flows = this.flowTypes();
    const cm = cellMap(); // build the cell Map ONCE, not per (regime × flow) cell
    let flowsClassified = 0;
    regimes.forEach((r) => flows.forEach((f) => effMarket(r.id, f.id, cm) && flowsClassified++));
    return {
      codesTotal: wl.length,
      byLevel,
      unclassified: wl.filter((c) => !c.level).length,
      flowsTotal: regimes.length * flows.length,
      flowsClassified,
    };
  },
};
