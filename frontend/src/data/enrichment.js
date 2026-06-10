// enrichment.js — curation layer (per-code industrialization), API-backed.
//
// The editor classifies each Gold CODE (per source) as bruta/processada/
// misturado. The worklist is the LEFT JOIN of the Gold code universe ⟕ the
// current classification log, served by /api/curation/worklist; edits stage in a
// local draft and commit via POST /api/curation/code-level (the append-only SCD2
// writer, author captured from IAP). Persistence needs the prod SCD2 view
// (`enable_curation`) — the worklist + editor work regardless (all codes read
// "a classificar" before activation). The CODE-level curation drives the REAL
// value-added analysis (window.valueAddedAnalysis → /api/cross/value-added).
//
// The regime×flow → market-nature axis is DATA-BLOCKED (the customs-procedure
// dimension is summed away in Silver), so its matrix renders the real customs
// regimes/flows for reference but the pairings are inert (pairMarket/setPair are
// no-ops; window.marketNatureAnalysis is an honest placeholder).

import { ensure, get, invalidate, subscribe as subscribeResource } from './resource';

const API = '/api';
const WL_KEY = 'curation:worklist';

// ── static registries (ported from the prototype) ─────────────────────────────
window.ENRICH_LEVELS = [
  { id: 'bruta', label: 'Bruta', color: 'var(--viz-3)' },
  { id: 'processada', label: 'Processada', color: 'var(--viz-2)' },
  { id: 'misturado', label: 'Misturado', color: 'var(--pres-gray-300)' },
];
window.ENRICH_MARKETS = [
  { id: 'consumo', label: 'Consumo', short: 'Consumo', color: 'var(--viz-1)' },
  { id: 'processamento', label: 'Processamento', short: 'Processamento', color: 'var(--viz-9)' },
];
// Derived from the live worklist rows (commodity → name) at read time.
window.ENRICH_GROUPS = [];
// Customs regimes (rows) × flow types (columns) — reference data for the
// (data-blocked) market-nature matrix.
window.ENRICH_REGIMES = [
  { id: 'desp-consumo', label: 'Despacho para consumo', term: 'Clearance for home use', hint: 'Importação nacionalizada: a mercadoria estrangeira é liberada para circular e ser consumida livremente no país após o recolhimento de todos os tributos.' },
  { id: 'reimport-same', label: 'Reimportação no mesmo estado', term: 'Reimportation in the same state', hint: 'Retorno ao país de um bem que havia sido exportado, sem ter sofrido transformação no exterior. Não representa nova produção nem agregação de valor.' },
  { id: 'exp-definitiva', label: 'Exportação definitiva', term: 'Outright exportation', hint: 'Saída definitiva da mercadoria nacional para o exterior, sem previsão de retorno. É a exportação comum.' },
  { id: 'entreposto', label: 'Entreposto aduaneiro', term: 'Customs warehouses', hint: 'Mercadoria armazenada sob controle aduaneiro com tributos suspensos, antes de definir seu destino. Ponto de espera logístico, não destino final.' },
  { id: 'zona-franca', label: 'Zona Franca', term: 'Free zone', hint: 'Área com incentivos fiscais e aduaneiros para atrair indústria e comércio (ex.: Zona Franca de Manaus), em geral para transformação industrial.' },
  { id: 'aperf-ativo', label: 'Aperfeiçoamento ativo', term: 'Inward processing', hint: 'Importação temporária de insumos com suspensão de tributos para serem industrializados no país e depois reexportados. Uso industrial, não consumo final.' },
  { id: 'aperf-passivo', label: 'Aperfeiçoamento passivo', term: 'Outward processing', hint: 'Exportação temporária de um bem para ser beneficiado no exterior, com retorno ao país. O valor é agregado fora do território nacional.' },
  { id: 'drawback', label: 'Drawback', term: 'Drawback', hint: 'Regime de incentivo à exportação que suspende/restitui tributos dos insumos importados usados na fabricação de um produto exportado.' },
  { id: 'transformacao', label: 'Transformação sob controle aduaneiro', term: 'Processing of goods for home use', hint: 'Transformação industrial sob controle aduaneiro, com o produto destinado ao mercado interno.' },
  { id: 'cabotagem', label: 'Cabotagem', term: 'Carriage of goods coastwise', hint: 'Transporte de mercadorias por via aquaviária entre portos do próprio país. Movimentação interna, não comércio exterior.' },
  { id: 'infracoes', label: 'Infrações aduaneiras', term: 'Customs offences', hint: 'Operações vinculadas a infrações, apreensões ou penalidades. Não representam fluxo comercial regular.' },
  { id: 'viajantes', label: 'Viajantes', term: 'Travellers', hint: 'Bens na bagagem de viajantes. Em geral de uso pessoal, com volume e valor pequenos.' },
  { id: 'postal', label: 'Tráfego postal', term: 'Postal traffic', hint: 'Mercadorias movimentadas pela via postal e remessas internacionais (correios). E-commerce transfronteiriço de pequeno porte.' },
  { id: 'provisoes', label: 'Provisões de bordo', term: 'Stores', hint: 'Combustíveis, alimentos e suprimentos embarcados em navios e aeronaves para consumo durante a viagem.' },
  { id: 'socorro', label: 'Remessas de socorro', term: 'Relief consignments', hint: 'Remessas de ajuda humanitária e socorro, normalmente isentas e fora da lógica comercial.' },
  { id: 'cpc-nes', label: 'CPC não especificado', term: 'CPC N.E.S.', hint: 'Procedimento aduaneiro não especificado nas demais categorias. Interprete com cautela.' },
  { id: 'total-cpc', label: 'Total CPC', term: 'TOTAL CPC', hint: 'Linha de agregação que soma todos os procedimentos. Evita-se somá-la às categorias específicas para não duplicar valores.' },
];
window.ENRICH_FLOWS = [
  { id: 'imports', label: 'Importações', term: 'Imports', hint: 'Entrada de mercadorias estrangeiras no território nacional, qualquer que seja o destino.' },
  { id: 'exports', label: 'Exportações', term: 'Exports', hint: 'Saída de mercadorias do país para o exterior. Pode englobar produção nacional e reexportações.' },
  { id: 'dom-export', label: 'Exportação nacional', term: 'Domestic Export', hint: 'Exportação de mercadoria efetivamente produzida no país (origem nacional). Mede a competitividade da produção interna.' },
  { id: 'for-import', label: 'Importação estrangeira', term: 'Foreign Import', hint: 'Importação de mercadoria de origem estrangeira — a contrapartida da exportação nacional do país parceiro.' },
  { id: 'imp-inward', label: 'Import. p/ aperfeiç. ativo', term: 'Import for inward processing', hint: 'Importação de insumos para industrialização interna e posterior reexportação. Demanda industrial, não consumo.' },
  { id: 'imp-after-outward', label: 'Import. após aperfeiç. passivo', term: 'Import after outward processing', hint: 'Reentrada da mercadoria enviada ao exterior para beneficiamento. O ganho de valor ocorreu fora do país.' },
  { id: 'reimport', label: 'Reimportação', term: 'Re-import', hint: 'Reentrada de mercadoria exportada, sem transformação no exterior (devoluções).' },
  { id: 'reexport', label: 'Reexportação', term: 'Re-export', hint: 'Reexportação de mercadoria importada, sem transformação no país. Papel de entreposto/intermediação.' },
  { id: 'exp-after-inward', label: 'Export. após aperfeiç. ativo', term: 'Export after inward processing', hint: 'Exportação do produto de insumos importados e beneficiados internamente. Exportação com valor agregado pela indústria nacional.' },
  { id: 'exp-for-outward', label: 'Export. p/ aperfeiç. passivo', term: 'Export for outward processing', hint: 'Exportação temporária de um bem para beneficiamento no exterior, com retorno.' },
];

// ── worklist (API ⟕ draft) ─────────────────────────────────────────────────────
const draft = new Map(); // id -> level (a staged change vs the API level)
let committing = false;
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
  regimes: () => window.ENRICH_REGIMES,
  flowTypes: () => window.ENRICH_FLOWS,
  pairMarket: () => null, // data-blocked
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
  setPair() {
    /* data-blocked: the regime×flow market-nature axis has no real source */
  },

  pendingCount: () => draft.size,
  isDirty() {
    return draft.size > 0;
  },
  isCommitting: () => committing,

  // Commit the draft → POST each staged edit to the append-only writer, then
  // re-fetch the worklist (now reflecting the writes). Locks while committing so
  // a double-click can't write duplicate revisions.
  apply(onDone) {
    if (committing || draft.size === 0) return;
    committing = true;
    notify();
    const edits = [...draft.entries()];
    Promise.all(
      edits.map(([id, level]) => {
        const [source, code] = id.split(':');
        return fetch(`${API}/curation/code-level`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source, code, level }),
        }).then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
        });
      }),
    )
      .then(() => {
        draft.clear();
        invalidate(WL_KEY); // next worklist() re-fetches
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
        notify(); // keep the draft so the user can retry
      });
  },
  discard() {
    if (committing) return;
    draft.clear();
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
      flowsTotal: window.ENRICH_REGIMES.length * window.ENRICH_FLOWS.length,
      flowsClassified: 0, // data-blocked
    };
  },
};
