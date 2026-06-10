// enrichment.js — curation layer, API-backed. Two institutional axes, both
// append-only SCD2 logs joined to the Gold/Bronze universe at read time:
//
//   1. CODE-level industrialization (bruta/processada/misturado) — the worklist
//      is /api/curation/worklist (Gold DISTINCT codes ⟕ classification log); it
//      drives window.valueAddedAnalysis (→ /api/cross/value-added).
//
//   2. FLOW-MARKET economic purpose (consumo/processamento) — the matrix is the
//      REAL COMTRADE customs procedure (customsCode) × flow (flowCode) grid from
//      /api/curation/flow-worklist, carrying each pair's USD value so the
//      researcher classifies what is materially relevant. It drives
//      window.marketNatureAnalysis (→ /api/cross/market-nature).
//
// Both edit a local draft and commit via POST on "Aplicar à base" (the
// append-only writers, author captured from IAP). The flow-market codes are the
// raw UN Comtrade procedure codes (opaque on purpose — their meaning is NOT
// hardcoded; the researcher curates from the code + its value, not a guess).

import { ensure, get, invalidate, subscribe as subscribeResource } from './resource';

const API = '/api';
const WL_KEY = 'curation:worklist'; // code-level industrialization worklist
const FW_KEY = 'curation:flow-worklist'; // customsCode × flowCode market matrix

// ── static registries (the two market purposes + industrialization levels) ────
window.ENRICH_LEVELS = [
  { id: 'bruta', label: 'Bruta', color: 'var(--viz-3)' },
  { id: 'processada', label: 'Processada', color: 'var(--viz-2)' },
  { id: 'misturado', label: 'Misturado', color: 'var(--pres-gray-300)' },
];
window.ENRICH_MARKETS = [
  { id: 'consumo', label: 'Consumo', short: 'Consumo', color: 'var(--viz-1)' },
  { id: 'processamento', label: 'Processamento', short: 'Processamento', color: 'var(--viz-9)' },
];
// Derived from the live code worklist rows (commodity → name) at read time.
window.ENRICH_GROUPS = [];

// ── USD formatters (compact, for the matrix cell + row hints) ─────────────────
const fmtUsdShort = (v) => {
  const n = Number(v || 0);
  if (n >= 1e9) return 'US$ ' + (n / 1e9).toFixed(n >= 1e10 ? 0 : 1) + ' bi';
  if (n >= 1e6) return 'US$ ' + (n / 1e6).toFixed(0) + ' mi';
  if (n >= 1e3) return 'US$ ' + (n / 1e3).toFixed(0) + ' mil';
  return 'US$ ' + n.toFixed(0);
};

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
let committing = false;

const apiRows = () => {
  const wl = get(WL_KEY);
  return (wl && wl.rows) || [];
};
const rowId = (r) => `${r.source}:${r.code}`;

function worklist() {
  ensure(WL_KEY, () => `${API}/curation/worklist`);
  const groupLabels = {};
  const rows = apiRows().map((r) => {
    const id = rowId(r);
    const apiLevel = r.level || null;
    const level = draft.has(id) ? draft.get(id) : apiLevel;
    if (r.commodity) groupLabels[r.commodity] = r.commodity_name || r.commodity;
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

// ── (2) flow-market matrix (real COMTRADE customsCode × flowCode ⟕ draft) ──────
const flowDraft = new Map(); // `${customs}:${flow}` -> market ('' clears)

function flowWorklist() {
  ensure(FW_KEY, () => `${API}/curation/flow-worklist`);
  return get(FW_KEY) || { customs: [], flows: [], cells: [], classified: 0, total: 0 };
}
// `${customs}:${flow}` -> cell {customs_code, flow_code, value_usd, market}.
function cellMap() {
  const m = new Map();
  flowWorklist().cells.forEach((c) => m.set(`${c.customs_code}:${c.flow_code}`, c));
  return m;
}
// Effective market for a pair = staged draft if any, else the persisted value.
function effMarket(customs, flow) {
  const k = `${customs}:${flow}`;
  if (flowDraft.has(k)) return flowDraft.get(k) || null;
  const cell = cellMap().get(k);
  return (cell && cell.market) || null;
}

window.enrichment = {
  codes: () => worklist(),
  worklist: () => worklist(),

  // Matrix ROWS = real customs procedure codes, sorted by total traded value so
  // the material procedures sit at the top. Codes are opaque (UN Comtrade CPC) —
  // we surface the code + its value, never a guessed meaning.
  regimes() {
    const wl = flowWorklist();
    const totals = {};
    wl.cells.forEach((c) => {
      totals[c.customs_code] = (totals[c.customs_code] || 0) + (c.value_usd || 0);
    });
    return wl.customs
      .slice()
      .sort((a, b) => (totals[b] || 0) - (totals[a] || 0))
      .map((code) => ({
        id: code,
        term: code,
        label: `Procedimento aduaneiro ${code}`,
        hint: `Código de procedimento aduaneiro (UN Comtrade customsCode) ${code} — total transacionado ${fmtUsdShort(totals[code] || 0)}. Classifique a finalidade econômica de cada fluxo deste procedimento.`,
      }));
  },
  // Matrix COLUMNS = real flow codes (M, X, RM, RX, …) with pt-BR labels.
  flowTypes() {
    return flowWorklist().flows.map((f) => ({
      id: f.code,
      term: f.label,
      label: f.label,
      hint: `Fluxo comercial ${f.code} — ${f.label}.`,
    }));
  },
  pairMarket: (customs, flow) => effMarket(customs, flow),
  // The per-cell traded value (formatted) — empty when the pair has no COMTRADE
  // rows. Shown in the matrix so the researcher classifies what actually matters.
  pairValueLabel(customs, flow) {
    const cell = cellMap().get(`${customs}:${flow}`);
    if (!cell || !cell.value_usd) return '';
    return fmtUsdShort(cell.value_usd);
  },

  levelLabel: (id) => (window.ENRICH_LEVELS.find((l) => l.id === id) || {}).label || id,
  levelColor: (id) => (window.ENRICH_LEVELS.find((l) => l.id === id) || {}).color || 'var(--fg-3)',
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
    if (patch.level === apiLevel) draft.delete(id);
    else draft.set(id, patch.level);
    notify();
  },
  // Stage a (customs, flow) → market edit. Matching the persisted value unstages;
  // an empty market stages a CLEAR (the writer records market='' = "a classificar").
  setPair(customs, flow, market) {
    const k = `${customs}:${flow}`;
    const cell = cellMap().get(k);
    const apiMarket = (cell && cell.market) || null;
    const next = market || null;
    if (next === apiMarket) flowDraft.delete(k);
    else flowDraft.set(k, market || '');
    notify();
  },

  pendingCount: () => draft.size + flowDraft.size,
  isDirty() {
    return draft.size > 0 || flowDraft.size > 0;
  },
  isCommitting: () => committing,

  // Commit BOTH drafts → POST each staged edit to its append-only writer, then
  // re-fetch the worklists (now reflecting the writes). Locks while committing so
  // a double-click can't write duplicate revisions.
  apply(onDone) {
    if (committing || (draft.size === 0 && flowDraft.size === 0)) return;
    committing = true;
    notify();
    const post = (path, body) =>
      fetch(`${API}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      });
    const codeEdits = [...draft.entries()].map(([id, level]) => {
      const [source, code] = id.split(':');
      return post('/curation/code-level', { source, code, level });
    });
    const flowEdits = [...flowDraft.entries()].map(([k, market]) => {
      const [customs_code, flow_code] = k.split(':');
      return post('/curation/flow-market', { customs_code, flow_code, market });
    });
    Promise.all([...codeEdits, ...flowEdits])
      .then(() => {
        draft.clear();
        flowDraft.clear();
        invalidate(WL_KEY); // next worklist() re-fetches
        invalidate(FW_KEY); // next flowWorklist() re-fetches
        committing = false;
        notify();
        if (typeof onDone === 'function') {
          try {
            onDone();
          } catch {
            /* ignore callback error */
          }
        }
      })
      .catch(() => {
        committing = false;
        notify(); // keep the drafts so the user can retry
      });
  },
  discard() {
    if (committing) return;
    draft.clear();
    flowDraft.clear();
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
    const fw = flowWorklist();
    let flowsClassified = 0;
    fw.customs.forEach((c) => fw.flows.forEach((f) => effMarket(c, f.code) && flowsClassified++));
    return {
      codesTotal: wl.length,
      byLevel,
      unclassified: wl.filter((c) => !c.level).length,
      flowsTotal: fw.customs.length * fw.flows.length,
      flowsClassified,
    };
  },
};
