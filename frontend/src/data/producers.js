// producers.js — API-backed replacements for the prototype's synthetic data
// producers, keeping identical window.* names/signatures. The per-banco snapshot
// path lives in dataStore.js (gated by DataBoundary); this file covers the
// cross-source / analytics / curation producers + the data-blocked placeholders.
//
// Sync-over-async (contract map §3.1): the cross producers are SYNC for the
// reused views — they read the resource cache (get) and, if cold, kick off the
// fetch (ensure) + return a safe pending placeholder. A CrossBoundary (main.jsx)
// subscribes to resource changes and re-renders, so the view's next sync call
// gets real data. Trade adapters (flow/partner/monthly) have no endpoint yet;
// chain/lag/market-nature are data-blocked — all return honest preview shells.

import { decorateUfRows } from './decorate';
import { ensure, get } from './resource';

const API = '/api';
const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v != null)).toString();

// pt-BR month labels — was defined in the synthetic previewData.js (not imported);
// the seasonality view + MonthYearHeatmap read window.MONTH_LABELS.
window.MONTH_LABELS = window.MONTH_LABELS || [
  'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez',
];

// ── per-banco snapshot fallback (dataStore is the primary path) ───────────────
window.snapshotFor = function snapshotFor() {
  // Every live banco loads through dataStore.load → /api/snapshot. This fallback
  // (used by applyFilters only if the store isn't populated) returns null so the
  // caller degrades gracefully rather than fabricating data.
  return null;
};

// ── cross-source comparable series ────────────────────────────────────────────
window.crossSeries = function crossSeries(bancoId, metricId, opts = {}) {
  const { y0, y1 } = opts;
  const key = `cross:series:${bancoId}:${metricId}:${y0 ?? ''}:${y1 ?? ''}`;
  ensure(key, () => `${API}/cross/series?${qs({ banco: bancoId, metric: metricId, y0, y1 })}`);
  // bancoMeta/metricMeta are registry objects (bancos.js) joined client-side —
  // the contract (SeriesResult) carries them, and the view reads bancoMeta.short.
  const bancoMeta = window.bancoById ? window.bancoById(bancoId) : null;
  const metricMeta = window.metricById ? window.metricById(bancoId, metricId) : null;
  const data = get(key);
  if (data) return { ...data, bancoMeta, metricMeta };
  return {
    banco: bancoId,
    metric: metricId,
    key: `${bancoId}:${metricId}`,
    bancoMeta,
    metricMeta,
    label: (metricMeta && metricMeta.label) || '',
    unit: '',
    family: (metricMeta && metricMeta.family) || '',
    preview: false, // real data, just loading — not a demo (no PreviewBanner)
    coverage: (metricMeta && metricMeta.years) || [0, 0],
    points: [],
  };
};

// Comparable window = intersection of the selected metrics' native coverage
// (read client-side from the banco registry — no fetch needed).
window.crossCommonWindow = function crossCommonWindow(refs = []) {
  const covs = refs
    .map((r) => {
      const b = window.bancoById && window.bancoById(r.b || r.banco);
      const m = b && (b.metrics || []).find((x) => x.id === (r.m || r.metric));
      return m && m.years;
    })
    .filter(Boolean);
  if (!covs.length) return { y0: 1997, y1: 2024, union: [1997, 2024] };
  const y0 = Math.max(...covs.map((c) => c[0]));
  const y1 = Math.min(...covs.map((c) => c[1]));
  const union = [Math.min(...covs.map((c) => c[0])), Math.max(...covs.map((c) => c[1]))];
  return y0 <= y1 ? { y0, y1, union } : { y0: union[0], y1: union[1], union };
};

// ── crosswalk commodity catalog (the multi-source pickers' option universe) ───
// The cross/* analytics are keyed by the crosswalk commodity_id SLUG (not a PEVS
// product code), so their commodity picker must offer slugs. /api/catalog returns
// { commodity_id -> {id, name, pevs[], comex[], comtrade[]} }; we flatten it to a
// sorted [{ code: <slug>, name }] list (sync-over-async like the analytics below —
// reads the cache, kicks the fetch on a miss, returns [] until it lands).
window.crossCatalog = function crossCatalog() {
  const key = 'cross:catalog';
  ensure(key, () => `${API}/catalog`);
  const data = get(key);
  if (!data) return [];
  return Object.values(data)
    .map((c) => ({ code: c.id, name: c.name }))
    .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));
};

// ── cross-source analytics (crosswalk-joined) ─────────────────────────────────
const crossAnalytic = (name, path, shell) =>
  function (commodityId) {
    const key = `cross:${name}:${commodityId || '*'}`;
    ensure(key, () => `${API}/cross/${path}?${qs({ commodity: commodityId })}`);
    return get(key) || shell;
  };

// Loading shells use preview:false — the data IS real, just not arrived yet (so
// no "demonstração" banner flashes). Empty arrays render empty charts until the
// resource resolves and the gate re-renders with real data.
window.exportCoefficient = crossAnalytic('export-coef', 'export-coef', {
  preview: false, unit: 'mil t', byUf: [], national: {}, timeseries: [],
});
window.marketShare = crossAnalytic('market-share', 'market-share', {
  preview: false, unit: 'US$ bi', series: [], byProduct: [],
});
window.priceSpread = crossAnalytic('price-spread', 'price-spread', {
  preview: false, unit: 'US$/kg', series: [],
});
window.tradeMirror = crossAnalytic('mirror', 'mirror', {
  preview: false, unit: 'US$ bi', series: [], discrepancy: [],
});
window.valueAddedAnalysis = crossAnalytic('value-added', 'value-added', {
  preview: false, years: [], byLevel: { bruta: [], processada: [] }, series: [], nCodes: 0,
});

// ── data-blocked producers (no upstream source — honest preview shells) ───────
// chainBalance needs SEFAZ inter-UF flows; harvestShipmentLag needs MONTHLY PEVS
// (annual-only). The views render their blocked-source banner.
window.chainBalance = function chainBalance(_code, year) {
  return {
    preview: true, unit: 'mil t', year: year || 2024, produced: 0, exported: 0, internal: 0,
    domestic: 0, expFrac: 0, intFrac: 0, domFrac: 0, worldShare: 0, worldTotal: 0, exportUsd: 0,
    sankey: { nodes: [], links: [] },
  };
};
window.harvestShipmentLag = function harvestShipmentLag() {
  return {
    preview: true, months: [], production: [], shipments: [], peakHarvest: 0, peakShip: 0,
    lagMonths: 0, corrAtLag: 0, lagProfile: [],
  };
};
// market-nature is now CURATED-REAL: COMTRADE value summed by the economic
// purpose (consumo/processamento) the researcher assigns to each customsCode×
// flowCode pair in Curadoria. Empty series until pairs are classified — the view
// guards that with an honest "classify first" state (no synthetic fallback).
window.marketNatureAnalysis = crossAnalytic('market-nature', 'market-nature', {
  preview: false, years: [], series: [], latest: {},
});

// ── trade adapters (flow / partner / monthly) — resource-backed, COMEX/COMTRADE ─
// The banco's dimension labels (originLabel/destLabel/flowLabel) come from the
// registry (bancoDim) client-side; the API supplies the data.
window.flowData = function flowData(bancoId) {
  const key = `trade:flow:${bancoId}`;
  ensure(key, () => `${API}/flow?${qs({ banco: bancoId })}`);
  const data = get(key);
  const dim = (d) => (window.bancoDim ? window.bancoDim(bancoId, d) : {});
  const labels = {
    originLabel: dim('origin').label || 'Origem',
    destLabel: dim('dest').label || 'Destino',
  };
  return data
    ? { ...data, ...labels }
    : { preview: false, unit: 'US$', ...labels, nodes: [], links: [] };
};
window.partnerData = function partnerData(bancoId) {
  const key = `trade:partners:${bancoId}`;
  ensure(key, () => `${API}/partners?${qs({ banco: bancoId })}`);
  const data = get(key);
  const flowLabel = (window.bancoDim && window.bancoDim(bancoId, 'partner').label) || 'Parceiro';
  return data ? { ...data, flowLabel } : { preview: false, flowLabel, unit: 'US$', partners: [] };
};
window.monthlyData = function monthlyData(bancoId) {
  const key = `trade:monthly:${bancoId}`;
  ensure(key, () => `${API}/monthly?${qs({ banco: bancoId })}`);
  return (
    get(key) || {
      preview: false,
      unit: 'US$',
      years: [],
      months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
      matrix: {},
      // 12 zeros (not []) so the view's peak/low/amplitude math survives the
      // loading render; real values replace it when the fetch resolves.
      monthlyAvg: new Array(12).fill(0),
      series: [],
    }
  );
};
// PAM área × rendimento (backs ViewProductivity). Resource-backed: fetches the
// real /api/productivity (production ÷ harvested area → yield kg/ha, server-side)
// for the selected crop. The router only renders this view for a yield-capable
// banco (IBGE PAM), so the empty shell below is just the brief loading frame —
// the view renders empty charts until the resource resolves with real data.
window.productivityData = function productivityData(bancoId, crop) {
  const key = `productivity:${bancoId}:${crop || 'default'}`;
  ensure(key, () => `${API}/productivity?${qs({ banco: bancoId, crop: crop || undefined })}`);
  const data = get(key);
  if (!data) {
    return {
      preview: false,
      crop: { code: '', name: '' },
      crops: [],
      yieldUnit: 'kg/ha',
      areaUnit: 'ha',
      series: [],
      national: { yieldCagr: 0 },
      byUF: [],
    };
  }
  // The per-UF tile map needs col/row tile coords the /api omits — decorate from
  // the UF_DATA registry, exactly like the snapshot's ufData (decorate.js).
  return { ...data, byUF: decorateUfRows(data.byUF) };
};
