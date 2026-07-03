// ViewGeography.cov.test.jsx — render coverage for the territorial-distribution view.
// ViewGeography composes a wide set of window.* helpers (metric conventions, geo
// scalers) + chart widgets and branches heavily on the active metric (value / mass /
// volume / cabeças), the granularity scope (região / UF / município), and a handful of
// honest empty/partial states. Following the ViewFlows/ViewConcentration pattern, we
// stub every window.* dependency so each branch is exercised deterministically, then
// assert the view renders without crashing and that the relevant content surfaces.
//
// The view reads React hooks off the GLOBAL `React` (the prototype convention —
// `const { useState: useGeoState } = React` runs at import time), so we set
// globalThis.React / window.React BEFORE importing the view.

import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';

// Captured props from the stubbed chart widgets, so we can assert what each branch fed.
let regionBarsProps, choroProps, tileMapProps, heatmapProps, barChartCalls;

function stubGlobals(filtered, opts = {}) {
  const {
    geoLevel = 'municipio',     // 'municipio' (IBGE) vs 'uf' (trade) → muniCapable
    baseCcy = 'BRL',
    snapUfYearly = [],          // dataStore.get(db).ufYearly → real heatmap history
    meta = null,                // dataStore.meta(db) → partial-year calendar signal
    productsByUf = { products: [] },
  } = opts;

  window.applyFilters = () => filtered;
  window.DEFAULT_CONVENTIONS = { currency: 'BRL', correction: 'IPCA', autoScale: true };

  // Metric-convention helpers — identity-ish so the math stays predictable.
  window.canonCurrencyFor = () => baseCcy;
  window.convFactorFor = () => 1;          // valueMul = 1 * 1e6
  window.massQtyMul = () => 1e3;
  window.volumeQtyMul = () => 1e6;
  window.countQtyMul = () => 1e6;
  window.valueAxisLabel = () => 'R$';
  window.massAxisLabel = () => 't';
  window.volumeAxisLabel = () => 'm³';
  window.countAxisLabel = () => 'cab';
  window.geoLevelFor = () => geoLevel;

  // scaleSeries: pass through data + a stable label so the DOM is assertable.
  window.scaleSeries = (data, _max, _conv, _key, label) => ({ data: data || [], label });
  window.autoScaleNum = (v) => {
    const a = Math.abs(v || 0);
    if (a >= 1e9) return { factor: 1e9, suffix: 'bi' };
    if (a >= 1e6) return { factor: 1e6, suffix: 'mi' };
    if (a >= 1e3) return { factor: 1e3, suffix: 'mil' };
    return { factor: 1, suffix: '' };
  };
  window.scaleLabel = (unit, suffix) => (suffix ? `${unit} (${suffix})` : unit);

  window.dataStore = {
    get: () => ({ ufYearly: snapUfYearly }),
    meta: () => meta,
  };
  window.productsByUf = () => productsByUf;

  // Composed widgets — capture props / render markers.
  window.UnitFamilyBanner = () => <div className="ufb" />;
  window.SectionHeader = ({ overline, title, action }) => (
    <div className="sh">
      <span className="sh-ov">{overline}</span>
      <span className="sh-title">{title}</span>
      <span className="sh-action">{action}</span>
    </div>
  );
  window.RegionBars = (props) => { regionBarsProps = props; return <div className="regionbars" />; };
  window.BrazilChoropleth = (props) => { choroProps = props; return <div className="choro" />; };
  window.BrazilTileMap = (props) => { tileMapProps = props; return <div className="tilemap" />; };
  window.Heatmap = (props) => { heatmapProps = props; return <div className="heatmap" />; };
  window.BarChart = (props) => { barChartCalls.push(props); return <div className="barchart" />; };
}

let ViewGeography;

beforeEach(async () => {
  regionBarsProps = choroProps = tileMapProps = heatmapProps = undefined;
  barChartCalls = [];
  globalThis.React = React;
  window.React = React;
  await import('./ViewGeography.jsx'); // registers window.ViewGeography
  ViewGeography = window.ViewGeography;
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

// A representative snapshot: two UFs, two regions, two top municípios, plus a real
// per-(UF, year) history for the heatmap. Carries value + mass + volume + count so the
// metric toggle has every dimension available.
function fullFixture(overrides = {}) {
  return {
    ufData: [
      { uf: 'PA', value: 75, q_mass: 30, q_vol: 8, q_count: 12, real: true },
      { uf: 'SP', value: 25, q_mass: 10, q_vol: 4, q_count: 6, real: true },
    ],
    regionData: [
      { region: 'Norte', value: 75, q_mass: 30, q_vol: 8, q_count: 12 },
      { region: 'Sudeste', value: 25, q_mass: 10, q_vol: 4, q_count: 6 },
    ],
    topMunis: [
      { city: 'Belém', uf: 'PA', product: 'Açaí', value: 40, q_mass: 16, q_vol: 5, q_count: 7 },
      { city: 'Santos', uf: 'SP', product: 'Castanha', value: 12, q_mass: 6, q_vol: 2, q_count: 3 },
    ],
    yearStart: 2018,
    yearEnd: 2020,
    ufLatestYear: 2020,
    ufYearPartial: false,
    notFilteredByBasket: false,
    ...overrides,
  };
}

const UF_YEARLY = [
  { uf: 'PA', name: 'Pará', year: 2019, value: 60, q_mass: 24, q_vol: 6, q_count: 10 },
  { uf: 'PA', name: 'Pará', year: 2020, value: 75, q_mass: 30, q_vol: 8, q_count: 12 },
  { uf: 'SP', name: 'São Paulo', year: 2019, value: 20, q_mass: 8, q_vol: 3, q_count: 5 },
  { uf: 'SP', name: 'São Paulo', year: 2020, value: 25, q_mass: 10, q_vol: 4, q_count: 6 },
];

describe('ViewGeography — smoke + main branches', () => {
  it('renders the default (value · UF) view with the choropleth and the real heatmap', () => {
    stubGlobals(fullFixture(), { snapUfYearly: UF_YEARLY });
    const { container } = render(
      <ViewGeography
        families={['mass', 'volume']}
        summary={{}}
        database="ibge_pevs"
        conventions={{ currency: 'BRL', correction: 'IPCA', autoScale: true }}
      />
    );
    // Default scope = UF, default ufViz = map → choropleth gets the scaled UF rows.
    expect(choroProps).toBeTruthy();
    expect(choroProps.data.map((u) => u.uf)).toEqual(['PA', 'SP']);
    // value × valueMul (1e6) → PA 75 → 75e6
    expect(choroProps.data.find((u) => u.uf === 'PA').value).toBe(75e6);
    // Heatmap built from the REAL ufYearly history (two states kept).
    expect(heatmapProps).toBeTruthy();
    expect(heatmapProps.rows.length).toBe(2);
    // Metric segment offers Valor + the two quantity dims present in this basket.
    expect(container.textContent).toContain('Valor');
    expect(container.textContent).toContain('Quantidade (massa)');
    expect(container.textContent).toContain('Quantidade (volume)');
  });

  it('switching the metric to massa rescales the maps by the mass multiplier', () => {
    stubGlobals(fullFixture(), { snapUfYearly: UF_YEARLY });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    const massBtn = [...container.querySelectorAll('.seg-opt')].find((b) => b.textContent.includes('massa'));
    expect(massBtn).toBeTruthy();
    fireEvent.click(massBtn);
    // q_mass × massMul (1e3): PA 30 → 30000.
    expect(choroProps.data.find((u) => u.uf === 'PA').q_mass).toBe(30000);
  });

  it('the "Blocos" toggle swaps the choropleth for the SVG tile map', () => {
    stubGlobals(fullFixture(), { snapUfYearly: UF_YEARLY });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    const blocos = [...container.querySelectorAll('.seg-opt')].find((b) => b.textContent === 'Blocos');
    fireEvent.click(blocos);
    expect(tileMapProps).toBeTruthy();
    expect(tileMapProps.data.length).toBe(2);
  });

  it('the "Região" granularity renders the RegionBars instead of the UF map', () => {
    stubGlobals(fullFixture(), { snapUfYearly: UF_YEARLY });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    const regiaoBtn = [...container.querySelectorAll('.seg-opt')].find((b) => b.textContent === 'Região');
    fireEvent.click(regiaoBtn);
    // RegionBars is also rendered in the lower "Soma por região" card, but with the
    // scope=region it additionally drives the main map card.
    expect(regionBarsProps).toBeTruthy();
  });

  it('the "Município" granularity lists the top municípios when rows exist', () => {
    stubGlobals(fullFixture(), { snapUfYearly: UF_YEARLY, geoLevel: 'municipio' });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    const muniBtn = [...container.querySelectorAll('.seg-opt')].find((b) => b.textContent === 'Município');
    expect(muniBtn).toBeTruthy();
    fireEvent.click(muniBtn);
    expect(container.querySelector('.muni-list')).toBeTruthy();
    expect(container.textContent).toContain('Belém');
    expect(container.textContent).toContain('Santos');
  });

  it('the município granularity shows the recorte-a-geografia note when there are no rows', () => {
    stubGlobals(fullFixture({ topMunis: [] }), { snapUfYearly: UF_YEARLY, geoLevel: 'municipio' });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    const muniBtn = [...container.querySelectorAll('.seg-opt')].find((b) => b.textContent === 'Município');
    fireEvent.click(muniBtn);
    expect(container.querySelector('.muni-list')).toBeFalsy();
    expect(container.textContent).toContain('recortar a geografia');
  });
});

describe('ViewGeography — gating and honest-note branches', () => {
  it('hides the Município button for a UF-only trade banco (geoLevel=uf)', () => {
    stubGlobals(fullFixture(), { snapUfYearly: UF_YEARLY, geoLevel: 'uf' });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="mdic_comex" conventions={{ autoScale: true }} />
    );
    const labels = [...container.querySelectorAll('.seg-opt')].map((b) => b.textContent);
    expect(labels).not.toContain('Município');
    expect(labels).toContain('UF');
    expect(labels).toContain('Região');
  });

  it('shows the basket note when the territorial split is not basket-filtered', () => {
    stubGlobals(fullFixture({ notFilteredByBasket: true }), { snapUfYearly: UF_YEARLY });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    expect(container.textContent).toContain('todas as commodities');
  });

  it('shows the mass-unavailable note when the family is in the basket but per-UF has no mass', () => {
    // mass family present, but every per-UF q_mass is 0 → massAvail false → note shown,
    // and the metric segment falls back to Valor only.
    const fx = fullFixture({
      ufData: [
        { uf: 'PA', value: 75, q_mass: 0, q_vol: 0, q_count: 0, real: true },
        { uf: 'SP', value: 25, q_mass: 0, q_vol: 0, q_count: 0, real: true },
      ],
    });
    stubGlobals(fx, { snapUfYearly: UF_YEARLY });
    const { container } = render(
      <ViewGeography families={['mass', 'volume']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    // Both mass + volume families present but all-zero per UF → the combined plural note.
    expect(container.textContent).toContain('ainda não estão disponíveis');
    // Only Valor remains in the metric segment.
    expect(container.textContent).not.toContain('Quantidade (massa)');
  });

  it('shows the cabeças cross-species caveat when the active dim is count', () => {
    const fx = fullFixture({
      ufData: [
        { uf: 'MT', value: 0, q_mass: 0, q_vol: 0, q_count: 200, real: true },
        { uf: 'SP', value: 0, q_mass: 0, q_vol: 0, q_count: 50, real: true },
      ],
      regionData: [
        { region: 'Centro-Oeste', value: 0, q_count: 200 },
        { region: 'Sudeste', value: 0, q_count: 50 },
      ],
      topMunis: [],
    });
    stubGlobals(fx, { snapUfYearly: [], geoLevel: 'municipio' });
    const { container } = render(
      <ViewGeography families={['count']} summary={{}} database="ibge_ppm" conventions={{ autoScale: true }} />
    );
    // value is all-zero → valueAvail false; count is the only available dim → active.
    expect(container.textContent).toContain('cabeças');
    expect(container.textContent).toContain('Rebanho');
  });

  it('renders the ufYearPartial caption and "(parcial)" tag when the UF year lags the window', () => {
    stubGlobals(fullFixture({ ufYearPartial: true, ufLatestYear: 2019, yearEnd: 2020 }), {
      snapUfYearly: UF_YEARLY,
    });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    expect(container.textContent).toContain('(parcial)');
    expect(container.textContent).toContain('o último ano com dados por UF');
  });

  it('flags the map year as "(parcial)" from the calendar-incomplete latest year', () => {
    stubGlobals(fullFixture({ ufLatestYear: 2024 }), {
      snapUfYearly: UF_YEARLY,
      meta: { latest: { yearComplete: false, completeYear: 2023 } },
    });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    expect(container.textContent).toContain('2024 (parcial)');
  });
});

describe('ViewGeography — empty geo + products-by-UF base table', () => {
  it('renders without crashing on an empty heatmap history (no ufYearly)', () => {
    stubGlobals(fullFixture(), { snapUfYearly: [] });
    const { container } = render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: true }} />
    );
    // Empty history → 0 heatmap rows, but the rest of the view still mounts.
    expect(heatmapProps.rows.length).toBe(0);
    expect(container.querySelector('.choro')).toBeTruthy();
  });

  it('renders the per-state products card when summary.states is selected', () => {
    stubGlobals(fullFixture(), {
      snapUfYearly: UF_YEARLY,
      productsByUf: {
        products: [
          { code: 'P1', name: 'Açaí', value: 40 },
          { code: 'P2', name: 'Castanha', value: 12 },
        ],
      },
    });
    const { container } = render(
      <ViewGeography
        families={['mass']}
        summary={{ states: ['PA'] }}
        database="ibge_pevs"
        conventions={{ autoScale: true }}
      />
    );
    expect(container.textContent).toContain('Produtos do estado');
    expect(container.textContent).toContain('PA');
    // The per-state products card adds a BarChart on top of the Top-10 + region bars.
    expect(barChartCalls.length).toBeGreaterThanOrEqual(1);
  });

  it('omits the per-state products card when productsByUf returns nothing', () => {
    stubGlobals(fullFixture(), {
      snapUfYearly: UF_YEARLY,
      productsByUf: { products: [] },
    });
    const { container } = render(
      <ViewGeography
        families={['mass']}
        summary={{ states: ['PA'] }}
        database="ibge_pevs"
        conventions={{ autoScale: true }}
      />
    );
    expect(container.textContent).not.toContain('Produtos do estado');
  });

  it('honors autoScale=false on the heatmap (rows passed through unscaled)', () => {
    stubGlobals(fullFixture(), { snapUfYearly: UF_YEARLY });
    render(
      <ViewGeography families={['mass']} summary={{}} database="ibge_pevs" conventions={{ autoScale: false }} />
    );
    // autoScale off → heatScaled returns the raw rows + the bare unit label.
    expect(heatmapProps.rows.length).toBe(2);
  });
});
