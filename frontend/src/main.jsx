// main.jsx — application entry. Replaces the prototype's Dashboard.html inline
// boot. Order matters: bootstrap-globals sets window.React FIRST (proto modules
// read React as a bare global at eval time), then the modules side-effect-import
// in dependency order (each assigns window.X). The SYNTHETIC data layer + SVG
// charts are NOT imported from proto/ — they're replaced by src/data/* (API) and
// src/charts/* (Plotly). See PLANS/react_migration_contract_map.md §5.

import './bootstrap-globals'; // window.React/ReactDOM — must be first
import React, { useState, useEffect } from 'react';
import { subscribe as subscribeResource } from './data/resource';

// ── registries + utils (reused verbatim) ──────────────────────────────────────
import './proto/data.js'; // static registries (UF tiles, REGIONS, QUALITY_FLAGS, UNIT_FAMILIES) + formatters (+ unused synthetic globals — harmless)
import './proto/bancos.js';
import './proto/views.js';
import './proto/filtersSchema.js';
import './proto/glossary.js';
import './proto/urlState.js';
import './proto/chipFmt.js';
import './proto/seriesUtils.js';
import './proto/dataFilters.js';
import './proto/csvExport.js';
import './proto/MetricConventions.jsx';

// ── data layer (NEW — API-backed, replaces the synthetic producers) ───────────
import './data/dataStore.js';
import './data/producers.js';
import './data/enrichment.js';

// ── charts (NEW — Plotly for analytical charts; SVG ports for tile-map/donut) ─
import './charts/LineChart.jsx';
import './charts/MultiLineChart.jsx';
import './charts/StackedArea.jsx';
import './charts/BarChart.jsx';
import './charts/YoYBars.jsx';
import './charts/Heatmap.jsx';
import './charts/FlagBars.jsx';
import './charts/RegionBars.jsx';
import './charts/LorenzCurve.jsx';
import './charts/SankeyChart.jsx';
import './charts/MonthYearHeatmap.jsx';
import './charts/DualAxisLineChart.jsx';
import './charts/StackedPanels.jsx';
import './charts/MonthlyOverlay.jsx';
import './charts/LagBars.jsx';
import './charts/Donut.jsx'; // SVG port (categorical share)
import './charts/BrazilTileMap.jsx'; // SVG port (geographic tile grid)
import './charts/BrazilChoropleth.jsx'; // maplibre choropleth (real UF shapes)
import './charts/PreviewBanner.jsx'; // non-chart banner the preview/cross views use

// ── atoms + shell (reused) ────────────────────────────────────────────────────
import './proto/Icon.jsx';
import './proto/Status.jsx';
import './proto/Sparkline.jsx';
import './proto/UnitFamily.jsx';
import './proto/Atoms.jsx';
import './proto/DataBoundary.jsx';
import './proto/Glossary.jsx';
import './proto/FilterMenu.jsx';
import './proto/FilterTriggerBar.jsx';
import './proto/AppShell.jsx';
import './proto/MainScreen.jsx';

// ── views (reused) ────────────────────────────────────────────────────────────
import './proto/ViewOverview.jsx';
import './proto/ViewValueVolume.jsx';
import './proto/ViewGeography.jsx';
import './proto/ViewConcentration.jsx';
import './proto/ViewQuality.jsx';
import './proto/ViewProductProfile.jsx';
import './proto/ViewProductCompare.jsx';
import './proto/ViewProductivity.jsx';
import './proto/ViewSeasonality.jsx';
import './proto/ViewFlows.jsx';
import './proto/ViewPartners.jsx';
import './proto/ViewCrossSource.jsx';
import './proto/ViewsMultiSource.jsx';
import './proto/ViewsChain.jsx';
import './proto/ViewCuration.jsx';
import './proto/ViewCuratedAnalyses.jsx';
import './proto/ViewAbout.jsx';
import './proto/ViewHealth.jsx';
import './proto/ViewComingSoon.jsx';
import './proto/ViewNotApplicable.jsx';
import './proto/ViewPerspectiveSoon.jsx';

// ── deep-link decode (the DECODER half of the urlState.js codec contract) ─────
function readStateFromURL() {
  const q = new URLSearchParams(location.search);
  if (!window.urlHasOwnState || !window.urlHasOwnState(q)) return null;
  const conv = { ...window.DEFAULT_CONVENTIONS };
  if (q.get('cur')) conv.currency = q.get('cur');
  if (q.get('corr')) conv.correction = q.get('corr');
  if (q.get('mu') || q.get('vu')) {
    conv.units = { ...conv.units, mass: q.get('mu') || conv.units?.mass, volume: q.get('vu') || conv.units?.volume };
  }
  if (q.get('as') != null) conv.autoScale = q.get('as') === '1';
  const summary = {
    basket: window.urlDecodeArr(q, 'pb'),
    flags: window.urlDecodeArr(q, 'fl'),
    states: window.urlDecodeArr(q, 'st'),
    valueMin: window.urlDecodeNum(q, 'vmn'),
    valueMax: window.urlDecodeNum(q, 'vmx'),
    startDate: q.get('sd') || null,
    endDate: q.get('ed') || null,
  };
  let crossState = window.DEFAULT_CROSS_STATE;
  const xs = q.get('xs');
  if (xs) {
    crossState = {
      series: xs.split('|').filter(Boolean).map((s) => { const [b, m] = s.split(':'); return { b, m }; }),
      mode: q.get('xm') || 'basic',
      y0: window.urlDecodeNum(q, 'xy0'),
      y1: window.urlDecodeNum(q, 'xy1'),
    };
  }
  const view = q.get('v') || 'overview';
  const isCross = !!(window.viewById && window.viewById(view)?.crossBanco);
  return {
    view,
    database: q.get('b') || 'ibge_pevs',
    infoPage: q.get('ip') || null,
    conventions: conv,
    summary,
    crossState,
    mode: isCross ? 'multi' : 'single',
  };
}

// ── filter chips: the FilterTriggerBar reads display strings (summary.products,
// .period, …). FilterMenu.onApply emits them, but the initial/URL-restored
// summary only has raw arrays — compute the chips from applyFilters + the
// registries (chipFmt is the shared formatter the FilterMenu also uses). ───────
function withChips(summary, database, conventions) {
  const s = summary || {};
  if (s.products && s.period) return s; // already carries chips (from FilterMenu)
  const f = window.applyFilters ? window.applyFilters(s, database) : null;
  if (!f || !window.chipFmt) return s;
  const conv = conventions || window.DEFAULT_CONVENTIONS || {};
  const sym = ((window.CURRENCY_FX || {})[conv.currency] || { symbol: 'R$' }).symbol;
  const flagsAll = window.QUALITY_FLAGS || [];
  const labelOf = (id) => (flagsAll.find((q) => q.id === id) || {}).label || id;
  const total = f.productsTotal || (f.products || []).length;
  const basket = s.basket || null;
  const firstName =
    basket && basket.length === 1
      ? ((f.products || []).find((p) => p.code === basket[0]) || {}).name
      : null;
  const ufTotal = (f.ufDataFull || []).length || 27;
  const hasGeo = (f.ufDataFull || []).length > 0;
  return {
    ...s,
    products: window.chipFmt.products(basket ? basket.length : null, total, firstName),
    period: window.chipFmt.period(f.yearStart, f.yearEnd),
    valueRange: window.chipFmt.valueRange(s.valueMin, s.valueMax, sym),
    geo: window.chipFmt.geoStates(s.states ? s.states.length : null, ufTotal, hasGeo),
    quality: window.chipFmt.quality(s.flags || null, flagsAll.length, labelOf),
  };
}

// ── error boundary: a single view/component throwing must not blank the whole
// app (the prototype had none — real, sparser data exposes edge cases). Shows a
// recoverable message inside the content area; the shell stays usable. ─────────
class ViewErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidUpdate(prev) {
    // Reset the error when navigating to a different view/banco.
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="card subtle" style={{ margin: 24 }}>
          <div className="overline">Erro ao renderizar a perspectiva</div>
          <p className="caption" style={{ padding: '8px 4px' }}>
            {String(this.state.error?.message || this.state.error)}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── DataBoundary gate: load the active banco's snapshot (async) and block the
// per-banco data views on it. Info pages + cross-banco views don't need the
// active snapshot, so they render immediately. ───────────────────────────────
function DataGate({ database, infoPage, view, children }) {
  const d = window.useBancoData(database); // hook (DataBoundary.jsx) — loads + subscribes
  const banco = window.bancoById && window.bancoById(database);
  const vm = window.viewById && window.viewById(view);
  const needsData = !infoPage && !(vm && vm.crossBanco) && banco && banco.status === 'live';

  if (needsData) {
    if (d.status === 'loading' || d.status === 'idle') return <window.DataLoading banco={banco} />;
    if (d.status === 'error') {
      return <window.DataError banco={banco} message={d.error} onRetry={d.reload} />;
    }
  }
  return (
    <>
      {needsData && d.stale && (
        <window.FreshnessBanner banco={banco} latestAt={d.latestAt} onReload={d.reload} />
      )}
      {children}
    </>
  );
}

// ── root: holds the app state the prototype's Dashboard component held ─────────
function Dashboard() {
  const initial = readStateFromURL() || {};
  const [view, setView] = useState(initial.view || 'overview');
  const [database, setDatabase] = useState(initial.database || 'ibge_pevs');
  const [infoPage, setInfoPage] = useState(initial.infoPage ?? null);
  const [summary, setSummary] = useState(initial.summary || {});
  const [conventions, setConventions] = useState(initial.conventions || window.DEFAULT_CONVENTIONS);
  const [crossState, setCrossState] = useState(initial.crossState || window.DEFAULT_CROSS_STATE);
  const [mode, setMode] = useState(initial.mode || 'single');
  const [filterOpen, setFilterOpen] = useState(false);
  const [, forceTick] = useState(0);

  // Conventions → data layer bridge: currency/correction pick the deflated value
  // column server-side, so a change re-fetches the snapshot (contract map §0.2).
  useEffect(() => {
    if (window.dataStore?.setConventions) window.dataStore.setConventions(conventions);
  }, [conventions]);

  // Sync-over-async gate (contract map §3.1): the cross/curation producers are
  // synchronous cache reads that kick off a fetch on a miss. Re-render the tree
  // when any resource resolves so the view's next sync read sees real data.
  useEffect(() => subscribeResource(() => forceTick((t) => t + 1)), []);

  // URL write-back: mirror the app state into the query string (replaceState, no
  // history clutter) so reload + copy-paste preserve view/banco/filters/
  // conventions/cross. Uses the SAME codec (urlState.js) the share button +
  // readStateFromURL use, so the encoder/decoder can't drift on the wire format.
  useEffect(() => {
    if (!window.urlEncodeState) return;
    const arr = window.urlEncodeArr || (() => '');
    const isCross = !!(window.viewById && window.viewById(view)?.crossBanco);
    const qs = window.urlEncodeState({
      v: view,
      b: database,
      ip: infoPage,
      cur: conventions?.currency,
      corr: conventions?.correction,
      mu: conventions?.units?.mass,
      vu: conventions?.units?.volume,
      as: conventions?.autoScale ? 1 : 0,
      pb: arr(summary?.basket),
      fl: arr(summary?.flags),
      st: arr(summary?.states),
      vmn: summary?.valueMin ?? '',
      vmx: summary?.valueMax ?? '',
      sd: summary?.startDate || '',
      ed: summary?.endDate || '',
      xs: isCross && crossState?.series ? crossState.series.map((r) => `${r.b}:${r.m}`).join('|') : '',
      xm: isCross ? crossState?.mode || '' : '',
      xy0: isCross && crossState?.y0 ? crossState.y0 : '',
      xy1: isCross && crossState?.y1 ? crossState.y1 : '',
    });
    window.history.replaceState(null, '', qs ? `${location.pathname}?${qs}` : location.pathname);
  }, [view, database, infoPage, summary, conventions, crossState]);

  // The filter bar/menu apply only to per-banco DATA views (not info pages or
  // the cross-banco perspectives, which have no single-banco filter surface).
  const vm = window.viewById ? window.viewById(view) : null;
  const banco = window.bancoById ? window.bancoById(database) : null;
  const isDataView = !infoPage && !(vm && vm.crossBanco) && !!banco;
  const displaySummary = isDataView ? withChips(summary, database, conventions) : summary;

  return (
    <window.AppShell
      view={view}
      setView={setView}
      database={database}
      setDatabase={setDatabase}
      infoPage={infoPage}
      setInfoPage={setInfoPage}
      summary={displaySummary}
      conventions={conventions}
      crossState={crossState}
      mode={mode}
      setMode={setMode}
    >
      <DataGate database={database} infoPage={infoPage} view={view}>
        {isDataView && window.FilterTriggerBar && (
          <window.FilterTriggerBar
            summary={displaySummary}
            onOpen={() => setFilterOpen(true)}
            onExport={() =>
              window.exportActiveTableCSV &&
              window.exportActiveTableCSV({ view, database, summary, conventions })
            }
            live={banco.status === 'live'}
            banco={banco}
            view={view}
          />
        )}
        <ViewErrorBoundary resetKey={`${view}|${database}|${infoPage}`}>
          <window.MainScreen
            filters={summary}
            view={view}
            database={database}
            infoPage={infoPage}
            basket={summary.basket}
            conventions={conventions}
            setDatabase={setDatabase}
            crossState={crossState}
            setCrossState={setCrossState}
          />
        </ViewErrorBoundary>
      </DataGate>

      {/* Mount only WHEN OPEN: the menu initializes its product set from
          dataStore.get(banco) at mount, so it must mount after the snapshot has
          loaded (else it captures the synthetic fallback codes → applies an empty
          basket). Opening after the view rendered guarantees real data. */}
      {filterOpen && window.FilterMenu && (
        <window.FilterMenu
          open
          banco={database}
          value={summary}
          onClose={() => setFilterOpen(false)}
          onApply={(s) => {
            setSummary(s);
            setFilterOpen(false);
          }}
        />
      )}
    </window.AppShell>
  );
}

// Reuse the root across HMR re-evaluations of this module (calling createRoot
// twice on the same container warns). In prod this simply runs once.
const _container = document.getElementById('root');
window.__embrapaRoot = window.__embrapaRoot || window.ReactDOM.createRoot(_container);
window.__embrapaRoot.render(
  <React.StrictMode>
    <Dashboard />
  </React.StrictMode>
);
