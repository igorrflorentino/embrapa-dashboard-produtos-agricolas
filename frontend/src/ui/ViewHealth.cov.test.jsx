// ViewHealth.cov.test.jsx — coverage smoke + branch tests for the institutional
// "Saúde do sistema" page (ViewHealth.jsx). The component reads everything off the
// live backend seam (window.dataStore) and the banco registry helpers, so we stub
// those as plain globals and drive the main branches: the KPI strip, the per-banco
// table, the Gold-provenance card, the freshness/sources card, the quality-history
// LineChart (present vs loading empty-state), and crucially the alert builder — both
// the factual "info" coverage note and the derived "warn" integrity alert
// (latest year's non-OK share materially above the recent baseline → "fora de
// Normais"). No dependency on data.js: every global the view touches is stubbed here.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

// A controllable fake of the dataStore seam the page subscribes to + queries.
function makeStore({ snapshots = {}, metas = {}, statuses = {}, errors = {} } = {}) {
  return {
    subscribe: () => () => {}, // returns an unsubscribe fn (used in a cleanup effect)
    loadMeta: vi.fn(),
    load: vi.fn(),
    get: (id) => snapshots[id] || null,
    meta: (id) => metas[id] || {},
    status: (id) => statuses[id] || 'idle',
    error: (id) => errors[id] || null,
  };
}

// The banco registry the page iterates. Two live bancos + one planned, so the table
// + freshness rows + KPI denominators all have rows to render.
const BANCOS = [
  { id: 'ibge_pevs', short: 'IBGE PEVS', status: 'live', maturity: 'estavel', source: 'IBGE' },
  { id: 'comex', short: 'COMEX', status: 'live', maturity: 'beta', source: 'SECEX' },
  { id: 'sefaz', short: 'SEFAZ', status: 'soon', maturity: 'ingestao', source: 'SEFAZ' },
];

function stubWidgets() {
  // Render KPI cards as readable DOM so the strip is assertable. `value` may be a
  // React node (the status pill), so render it through children.
  window.KpiCardSpark = ({ label, value, sub }) => (
    <div className="kpi" data-label={label}>
      <span className="kpi-value">{value}</span>
      <span className="kpi-sub">{sub}</span>
    </div>
  );
  window.SectionHeader = ({ title, overline, action }) => (
    <div className="sh">
      <span className="sh-overline">{overline}</span>
      <span className="sh-title">{title}</span>
      <span className="sh-action">{action}</span>
    </div>
  );
  window.MaturityTag = ({ banco }) => <span className="mat-tag">{banco?.maturity || '…'}</span>;
  window.MaturityLegend = () => <div className="mat-legend" />;
  window.LineChart = (props) => <div className="line-chart" data-points={(props.data || []).length} />;
  window.Icon = ({ name }) => <i className="icon" data-icon={name} />;
}

function stubHelpers(store) {
  window.dataStore = store;
  window.BANCOS = BANCOS;
  window.visibleBancos = () => BANCOS;
  window.maturityMeta = (b) => {
    if (b && (b.maturity === 'estavel' || b.maturity === 'beta')) {
      return { id: b.maturity, hasData: true };
    }
    return { id: b ? b.maturity : 'planejado', hasData: false };
  };
  window.bancoTable = (id) => `gold_${id}`;
  window.fmtRows = (n) => (n == null ? '—' : `${n}`);
  window.fmtPct = (x) => `${Math.round((x || 0) * 100)}%`;
  window.auditBancoCoverage = vi.fn();
}

let ViewHealth;

beforeEach(async () => {
  await import('./ViewHealth.jsx'); // registers window.ViewHealth
  ViewHealth = window.ViewHealth;
});

afterEach(() => cleanup());

describe('ViewHealth — render smoke + main sections', () => {
  it('renders the KPI strip, provenance card, per-banco table and sources card', () => {
    const store = makeStore({
      metas: { ibge_pevs: { refresh: '2026-06-20', prov: {} } },
      statuses: { ibge_pevs: 'ready', comex: 'ready' },
    });
    stubWidgets();
    stubHelpers(store);

    const { container } = render(<ViewHealth summary={{}} />);

    // KPI strip — four cards by label.
    const labels = [...container.querySelectorAll('.kpi')].map((e) => e.dataset.label);
    expect(labels).toContain('Status geral do sistema');
    expect(labels).toContain('Bancos saudáveis (em produção)');
    expect(labels).toContain('Última atualização da Gold · IBGE PEVS');
    expect(labels).toContain('Alertas ativos');

    // The per-banco table renders a row per banco (short label appears).
    expect(container.textContent).toContain('IBGE PEVS');
    expect(container.textContent).toContain('COMEX');
    expect(container.textContent).toContain('SEFAZ');

    // Provenance card note + the "not monitored" run-history empty state.
    expect(container.textContent).toContain('proveniência da Gold');
    expect(container.textContent).toContain('não monitorado');

    // The mount effects fire the seam loaders for every banco / live banco.
    expect(store.loadMeta).toHaveBeenCalled();
    expect(store.load).toHaveBeenCalled();
  });

  it('drives the live refresh value into the scoped KPI when meta resolves', () => {
    const store = makeStore({
      metas: { ibge_pevs: { refresh: '2026-06-20', prov: {} } },
      statuses: { ibge_pevs: 'ready' },
    });
    stubWidgets();
    stubHelpers(store);

    const { container } = render(<ViewHealth summary={{}} />);
    const kpi = container.querySelector('.kpi[data-label="Última atualização da Gold · IBGE PEVS"] .kpi-value');
    expect(kpi?.textContent).toBe('2026-06-20');
  });
});

describe('ViewHealth — alert builder branches', () => {
  it('emits the factual "info" coverage note when a lastCrop edition is known', () => {
    const store = makeStore({
      metas: { ibge_pevs: { refresh: '2026-06-20', prov: { lastCrop: 'PEVS 2024' } } },
      statuses: { ibge_pevs: 'ready' },
    });
    stubWidgets();
    stubHelpers(store);

    const { container } = render(<ViewHealth summary={{}} />);
    expect(container.textContent).toContain('Última safra na Gold: PEVS 2024');
    // An info note IS an alert row (so the empty-state is gone), but it is NOT
    // counted as an open aviso — the header reads "0 aviso(s) em aberto".
    expect(container.textContent).not.toContain('Nenhum alerta ativo no momento.');
    expect(container.textContent).toContain('0 aviso(s) em aberto');
    expect(container.textContent).toContain('Informativo');
  });

  it('raises the "fora de Normais" warn alert when the latest issue share spikes', () => {
    // 6 years of OK shares; the baseline (years before the last) is ~98% OK
    // (issue ≈ 0.02), the latest drops to 90% OK (issue 0.10): 0.10 > 0.02×1.5 AND
    // 0.10 − 0.02 ≥ 0.02 → warn fires.
    const qualityTs = [
      { y: 2019, ok: 0.98 },
      { y: 2020, ok: 0.98 },
      { y: 2021, ok: 0.98 },
      { y: 2022, ok: 0.98 },
      { y: 2023, ok: 0.98 },
      { y: 2024, ok: 0.90 },
    ];
    const store = makeStore({
      snapshots: { ibge_pevs: { qualityTs } },
      metas: { ibge_pevs: { refresh: '2026-06-20', prov: { lastCrop: 'PEVS 2024' } } },
      statuses: { ibge_pevs: 'ready' },
    });
    stubWidgets();
    stubHelpers(store);

    const { container } = render(<ViewHealth summary={{}} />);
    // The warn alert title + its "fora de Normais" wording.
    expect(container.textContent).toContain('Integridade abaixo do padrão recente · 2024');
    expect(container.textContent).toContain('fora de "Normais"');
    // It bumps the overall status to "Em atenção" and the active-alerts KPI to 1.
    expect(container.textContent).toContain('Em atenção');
    const alertsKpi = container.querySelector('.kpi[data-label="Alertas ativos"] .kpi-value');
    expect(alertsKpi?.textContent).toBe('1');
  });

  it('does NOT raise a warn alert when the latest share is within the baseline', () => {
    // Flat ~98% OK every year → no jump → no warn alert.
    const qualityTs = [
      { y: 2019, ok: 0.98 }, { y: 2020, ok: 0.98 }, { y: 2021, ok: 0.98 },
      { y: 2022, ok: 0.98 }, { y: 2023, ok: 0.98 }, { y: 2024, ok: 0.98 },
    ];
    const store = makeStore({
      snapshots: { ibge_pevs: { qualityTs } },
      metas: { ibge_pevs: { refresh: '2026-06-20', prov: {} } },
      statuses: { ibge_pevs: 'ready' },
    });
    stubWidgets();
    stubHelpers(store);

    const { container } = render(<ViewHealth summary={{}} />);
    expect(container.textContent).not.toContain('Integridade abaixo do padrão recente');
    // No open avisos → the alerts list shows the honest empty state.
    expect(container.textContent).toContain('Nenhum alerta ativo no momento.');
  });
});

describe('ViewHealth — operational status + quality-history card', () => {
  it('reports "Falha" overall when a live banco query errored', () => {
    const store = makeStore({
      metas: { ibge_pevs: { refresh: '2026-06-20', prov: {} } },
      statuses: { ibge_pevs: 'error', comex: 'ready' },
      errors: { ibge_pevs: 'boom' },
    });
    stubWidgets();
    stubHelpers(store);

    const { container } = render(<ViewHealth summary={{}} />);
    expect(container.textContent).toContain('Falha');
  });

  it('renders the quality-history LineChart when a snapshot qualityTs is present', () => {
    const store = makeStore({
      snapshots: { ibge_pevs: { qualityTs: [{ y: 2023, ok: 0.97 }, { y: 2024, ok: 0.98 }] } },
      metas: { ibge_pevs: { refresh: '2026-06-20', prov: {} } },
      statuses: { ibge_pevs: 'ready' },
    });
    stubWidgets();
    stubHelpers(store);

    const { container } = render(<ViewHealth summary={{}} />);
    const chart = container.querySelector('.line-chart');
    expect(chart).toBeTruthy();
    expect(chart.dataset.points).toBe('2');
  });

  it('shows the quality-history loading empty-state when no snapshot exists yet', () => {
    const store = makeStore({
      metas: { ibge_pevs: { refresh: '—', prov: {} } },
      statuses: {},
    });
    stubWidgets();
    stubHelpers(store);

    const { container } = render(<ViewHealth summary={{}} />);
    expect(container.querySelector('.line-chart')).toBeNull();
    expect(container.textContent).toContain('Carregando a série de qualidade da Gold');
    // No live banco responded "ready" → overall is "Verificando…".
    expect(container.textContent).toContain('Verificando…');
  });
});
