// ViewProductivity.cov.test.jsx — coverage smoke + branch tests for the
// agricultural yield/area view (ViewProductivity.jsx, PAM-only). It is a
// self-data view: it reads window.productivityData(database, crop, summary), so we
// stub that producer plus the window.* formatters/widgets and drive:
//   - the no-data empty state (EmptyCard) — banco without the 'yield' capability,
//   - a full render: crop selector, the 4 KPIs (rendimento/área/produção/CAGR), the
//     national yield+area LineCharts, the per-UF tile map + ranking BarChart,
//   - the NotApplicableNote (basket-active) branch,
//   - the fmtArea/fmtProd magnitude branches (>= 1e6 → "mi", else "mil").

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';

function stubGlobals(prodData) {
  window.productivityData = () => prodData;
  window.numBR = (v, d) => Number(v).toFixed(d == null ? 0 : d).replace('.', ',');
  window.fmtSigned = (v) => `${v >= 0 ? '+' : ''}${v}%`;
  // Widgets → readable DOM.
  window.EmptyCard = ({ children }) => <div className="empty-card">{children}</div>;
  window.NotApplicableNote = ({ note }) =>
    note ? <div className="na-note">{note.basket || note.states || ''}</div> : null;
  window.KpiCardSpark = ({ label, value }) => (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
    </div>
  );
  window.SectionHeader = ({ title, overline }) => (
    <div className="sh">
      <span className="sh-overline">{overline}</span>
      <span className="sh-title">{title}</span>
    </div>
  );
  window.UnitFamilyTag = () => <span className="uf-tag" />;
  window.LineChart = (props) => <div className="line-chart" data-points={(props.data || []).length} />;
  window.BarChart = (props) => <div className="bar-chart" data-points={(props.data || []).length} />;
  window.BrazilTileMap = (props) => <div className="tile-map" data-points={(props.data || []).length} />;
}

// A representative productivityData payload (PAM-shaped). Area/prod are in the
// >= 1e6 band so the "mi ha" / "mi t" formatting branch is exercised.
function makeData(overrides = {}) {
  return {
    crop: { code: 'C1', name: 'Soja' },
    crops: [
      { code: 'C1', name: 'Soja' },
      { code: 'C2', name: 'Milho' },
    ],
    yieldUnit: 'kg/ha',
    areaUnit: 'ha',
    series: [
      { y: 2019, yieldKgHa: 3000, areaHa: 2_000_000, prodT: 6_000_000 },
      { y: 2020, yieldKgHa: 3300, areaHa: 2_100_000, prodT: 6_930_000 },
    ],
    national: { yieldCagr: 4.2 },
    byUF: [
      { uf: 'MT', name: 'Mato Grosso', yieldKgHa: 3500.6 },
      { uf: 'PR', name: 'Paraná', yieldKgHa: 3400.2 },
    ],
    notApplicable: undefined,
    ...overrides,
  };
}

let ViewProductivity;

beforeEach(async () => {
  await import('./ViewProductivity.jsx'); // registers window.ViewProductivity
  ViewProductivity = window.ViewProductivity;
});

afterEach(() => cleanup());

describe('ViewProductivity — empty state', () => {
  it('renders the EmptyCard when the producer returns null (no yield capability)', () => {
    stubGlobals(null);
    const { container } = render(
      <ViewProductivity summary={{}} conventions={{}} database="ibge_pevs" />
    );
    expect(container.querySelector('.empty-card')).toBeTruthy();
    expect(container.textContent).toContain('não expõe rendimento agrícola');
  });
});

describe('ViewProductivity — full render (PAM)', () => {
  it('renders the crop selector, the four KPIs, the trajectory charts and the UF geography', () => {
    stubGlobals(makeData());
    const { container } = render(
      <ViewProductivity summary={{}} conventions={{ currency: 'BRL' }} database="ibge_pam" />
    );

    // Crop selector with both crops; the active one (C1/Soja) carries the 'on' class.
    expect(container.textContent).toContain('Lavoura em análise');
    const chips = [...container.querySelectorAll('.pp-chip')];
    expect(chips.map((c) => c.textContent.trim())).toEqual(['Soja', 'Milho']);
    expect(chips[0].className).toContain('on');

    // KPI strip — four cards.
    const kpiLabels = [...container.querySelectorAll('.kpi-label')].map((e) => e.textContent);
    expect(kpiLabels.some((l) => l.includes('Rendimento nacional'))).toBe(true);
    expect(kpiLabels).toContain('Área colhida');
    expect(kpiLabels).toContain('Produção');
    expect(kpiLabels).toContain('CAGR do rendimento');

    // fmtArea/fmtProd hit the >= 1e6 branch → "mi ha" / "mi t".
    const kpiValues = [...container.querySelectorAll('.kpi-value')].map((e) => e.textContent);
    expect(kpiValues.some((v) => v.includes('mi ha'))).toBe(true);
    expect(kpiValues.some((v) => v.includes('mi t'))).toBe(true);

    // Two national trajectory LineCharts + the per-UF tile map + the ranking BarChart.
    expect(container.querySelectorAll('.line-chart').length).toBe(2);
    expect(container.querySelector('.tile-map')).toBeTruthy();
    expect(container.querySelector('.bar-chart')).toBeTruthy();

    // No basket note when notApplicable is undefined.
    expect(container.querySelector('.na-note')).toBeNull();
  });

  it('surfaces the basket NotApplicableNote when the producer flags it', () => {
    stubGlobals(
      makeData({
        notApplicable: { basket: 'A cesta de produtos não se aplica aqui.' },
      })
    );
    const { container } = render(
      <ViewProductivity summary={{ basket: ['C1'] }} conventions={{}} database="ibge_pam" />
    );
    expect(container.querySelector('.na-note')).toBeTruthy();
    expect(container.textContent).toContain('A cesta de produtos não se aplica aqui.');
  });

  it('falls into the "mil ha"/"mil t" formatting branch for sub-million area/production', () => {
    stubGlobals(
      makeData({
        series: [
          { y: 2019, yieldKgHa: 2000, areaHa: 30_000, prodT: 60_000 },
          { y: 2020, yieldKgHa: 2100, areaHa: 32_000, prodT: 67_200 },
        ],
      })
    );
    const { container } = render(
      <ViewProductivity summary={{}} conventions={{}} database="ibge_pam" />
    );
    const kpiValues = [...container.querySelectorAll('.kpi-value')].map((e) => e.textContent);
    expect(kpiValues.some((v) => v.includes('mil ha'))).toBe(true);
    expect(kpiValues.some((v) => v.includes('mil t'))).toBe(true);
  });

  it('guards the empty-series loading frame without crashing', () => {
    // series: [] → last/prev/first fall back to the zero guard; deltas are 0.
    stubGlobals(makeData({ series: [], byUF: [] }));
    const { container } = render(
      <ViewProductivity summary={{}} conventions={{}} database="ibge_pam" />
    );
    // Still renders the selector + KPI strip (no throw on the empty series).
    expect(container.textContent).toContain('Lavoura em análise');
    expect(container.querySelectorAll('.kpi').length).toBe(4);
  });
});
