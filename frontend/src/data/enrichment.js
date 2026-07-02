// enrichment.js — the researcher ENRICHMENT store (Engenharia de Atributos), API-backed.
//
// ONE institutional axis remains editable: CODE-level industrialization — an 8-level
// ordinal scale from a raw commodity (Commodity Pura) to a specialized manufactured good
// (Manufaturado Especializado). The worklist is /api/curation/worklist (Gold DISTINCT
// codes ⟕ the append-only SCD2 classification log); it drives window.valueAddedAnalysis
// (→ /api/cross/value-added, exports charted per level). Edits stage in a local draft and
// commit via POST on "Aplicar à base" (the append-only writer, author captured from IAP),
// gated downstream by the `enable_curation` dbt var.
//
// (The OTHER axis — tipo de mercado / market nature — is no longer editable here: it is the
// static comtrade_market_nature seed carried as serving_comtrade_annual.market_nature, and
// surfaces only as the "Finalidade econômica" analysis + the "Tipo de mercado" filter.)

import { ensure, get, invalidate, subscribe as subscribeResource } from './resource';

const API = '/api';
const WL_KEY = 'curation:worklist'; // code-level industrialization worklist

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
// The economic-purpose markets (consumo/processamento) the seed classifies — consumed by
// the "Finalidade econômica" analysis (ViewCuratedAnalyses).
window.ENRICH_MARKETS = [
  { id: 'consumo', label: 'Consumo', short: 'Consumo', color: 'var(--viz-1)' },
  { id: 'processamento', label: 'Processamento', short: 'Processamento', color: 'var(--viz-9)' },
];
// Derived from the live code worklist rows (commodity → name) at read time.
window.ENRICH_GROUPS = [];

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
subscribeResource(notify); // re-notify when the worklist resource resolves

// ── code-level worklist (API ⟕ draft) ─────────────────────────────────────────
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

window.enrichment = {
  codes: () => worklist(),
  worklist: () => worklist(),

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

  pendingCount: () => draft.size,
  isDirty() {
    return draft.size > 0;
  },
  isCommitting: () => committing,
  // The last write failure (e.g. "HTTP 401" when no IAP author), or null. The editor
  // renders this so a failed commit is visible — not silently swallowed.
  lastError: () => lastError,

  // Commit the draft → POST each staged edit to the append-only writer, then re-fetch the
  // worklist (now reflecting the writes). Locks while committing so a double-click can't
  // write duplicate revisions. Uses allSettled so a partial failure DROPS only the edits
  // that actually landed (the SCD2 log is append-only — re-POSTing a succeeded edit would
  // write a redundant revision); the failures stay staged and lastError is surfaced.
  apply(onDone) {
    if (committing || draft.size === 0) return;
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
    // One task per staged edit, tagged so a landed edit can be dropped individually (and a
    // retry re-POSTs only the failures).
    const tasks = [...draft.entries()].map(([id, level]) => {
      const [source, code] = id.split(':');
      const change_id = draftCid.get(id);
      return { key: id, run: () => post('/curation/code-level', { source, code, level, change_id }) };
    });
    Promise.allSettled(tasks.map((t) => t.run())).then((results) => {
      let failed = 0;
      results.forEach((res, i) => {
        if (res.status === 'fulfilled') {
          draft.delete(tasks[i].key); // landed → drop so a retry won't re-POST it
          draftCid.delete(tasks[i].key); // and drop its idempotency key
        } else {
          failed += 1;
          lastError = (res.reason && res.reason.message) || 'Falha ao gravar a curadoria';
        }
      });
      invalidate(WL_KEY); // reflect whatever landed (full OR partial)
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
    return {
      codesTotal: wl.length,
      byLevel,
      unclassified: wl.filter((c) => !c.level).length,
    };
  },
};
