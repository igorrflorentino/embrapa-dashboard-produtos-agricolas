// ViewPartners.cov.test.jsx — render coverage for the trading-partner ranking view
// (country/UF, COMEX/COMTRADE). ViewPartners branches on the active ranking metric:
// Capital (value — exp/imp split bars + top-3 concentration), Volume (weight —
// additive single bar), and Preço médio (price — a non-additive ratio → "faixa de
// preço" range KPI). The metric is a window.React.useState toggle that recomputes
// the ranking server-side, so we set window.React BEFORE importing the view (the
// prototype hooks-off-global convention) and stub every window.* dependency.

import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';

// partnerData captures the metric it was asked for so we can prove the toggle
// drives a server-side recompute (a new partnerData call per metric).
let partnerDataCalls;

function stubGlobals(byMetric) {
  window.React = React;
  globalThis.React = React;
  window.partnerData = (db, summary, metric) => {
    partnerDataCalls.push(metric);
    return byMetric[metric] || byMetric.value;
  };
  window.bancoById = () => ({ scope: 'País', domain: 'Comércio exterior' });
  window.fmtPct = (x) => `${Math.round((x || 0) * 100)}%`;
  window.NotApplicableNote = ({ note }) => (note ? <div className="na">{note}</div> : null);
  window.SectionHeader = ({ overline, title, action }) => (
    <div className="sh">
      <span className="sh-ov">{overline}</span>
      <span className="sh-title">{title}</span>
      <span className="sh-action">{action}</span>
    </div>
  );
  window.KpiCardSpark = ({ label, value, sub }) => (
    <div className="kpi" data-label={label}>
      <span className="kpi-value">{String(value)}</span>
      <span className="kpi-sub">{sub}</span>
    </div>
  );
}

let ViewPartners;

beforeEach(async () => {
  partnerDataCalls = [];
  window.React = React;
  globalThis.React = React;
  await import('./ViewPartners.jsx'); // registers window.ViewPartners
  ViewPartners = window.ViewPartners;
});

afterEach(() => cleanup());

// Three partner rankings keyed by metric. Value carries exp/imp split bars; weight is
// a plain additive measure; price is a non-additive US$/kg ratio.
const BY_METRIC = {
  value: {
    unit: 'US$',
    flowLabel: 'destino',
    notApplicable: 'Origem-UF não se aplica a um banco país-origem.',
    partners: [
      { name: 'China', value: 6000, exp: 5000, imp: 1000 }, // bi-scale (>=1000) → "bi"
      { name: 'EUA',   value: 3000, exp: 2500, imp: 500 },
      { name: 'Peru',  value: 1000, exp: 800,  imp: 200 },
      { name: 'Chile', value: 50,   exp: 50,   imp: 0 },     // <10 → 2-decimal "mi"
    ],
  },
  weight: {
    unit: 'US$',
    flowLabel: 'destino',
    notApplicable: null,
    partners: [
      { name: 'China', weight: 12.5 },
      { name: 'EUA',   weight: 8 },
      { name: 'Peru',  weight: 3 },
    ],
  },
  price: {
    unit: 'US$',
    flowLabel: 'destino',
    notApplicable: null,
    partners: [
      { name: 'Suíça',  price: 42.5 },
      { name: 'Japão',  price: 18 },
      { name: 'França', price: 6.25 },
      { name: 'Outro',  price: null }, // null price → '—' / filtered from range
    ],
  },
};

describe('ViewPartners — smoke + metric-toggle branches', () => {
  it('renders the default Capital ranking with exp/imp bars + top-3 concentration', () => {
    stubGlobals(BY_METRIC);
    const { container } = render(
      <ViewPartners summary={{}} conventions={{}} database="mdic_comex" />
    );
    // Honest country-origin note.
    expect(container.textContent).toContain('Origem-UF não se aplica');
    // Largest destino = China, formatted bi-scale (6000 → 6,0 bi).
    const top = container.querySelector('.kpi[data-label="Maior destino"] .kpi-value');
    expect(top.textContent).toBe('China');
    // Partners mapped = 4.
    const mapped = container.querySelector('.kpi[data-label="Parceiros mapeados"] .kpi-value');
    expect(mapped.textContent).toBe('4');
    // Additive metric → top-3 concentration KPI.
    expect(container.querySelector('.kpi[data-label="Concentração top-3"]')).toBeTruthy();
    expect(container.querySelector('.kpi[data-label="Faixa de preço"]')).toBeFalsy();
    // Value metric → exp + imp split bars + the legend.
    expect(container.querySelectorAll('.ptn-bar.exp').length).toBe(4);
    expect(container.querySelectorAll('.ptn-bar.imp').length).toBe(4);
    expect(container.querySelector('.ptn-legend')).toBeTruthy();
    // Four ranked rows, numbered #1..#4.
    expect(container.querySelectorAll('.ptn-row').length).toBe(4);
    expect(container.querySelector('.ptn-rank').textContent).toBe('#1');
  });

  it('switching to Volume recomputes server-side and renders a single additive bar', () => {
    stubGlobals(BY_METRIC);
    const { container } = render(
      <ViewPartners summary={{}} conventions={{}} database="mdic_comex" />
    );
    const volBtn = [...container.querySelectorAll('.seg-opt')].find((b) => b.textContent === 'Volume');
    expect(volBtn).toBeTruthy();
    fireEvent.click(volBtn);
    // The toggle triggered a fresh partnerData('weight') call (server-side re-sort).
    expect(partnerDataCalls).toContain('weight');
    // Volume is additive → still the top-3 concentration KPI, sub now "volume total".
    const kpi3 = container.querySelector('.kpi[data-label="Concentração top-3"]');
    expect(kpi3).toBeTruthy();
    expect(kpi3.querySelector('.kpi-sub').textContent).toContain('volume');
    // Weight metric → single (non-exp/imp) bars, no exp/imp split, no value legend.
    expect(container.querySelectorAll('.ptn-bar.imp').length).toBe(0);
    expect(container.querySelector('.ptn-legend')).toBeFalsy();
    // 3 partners in the weight ranking.
    expect(container.querySelectorAll('.ptn-row').length).toBe(3);
  });

  it('switching to Preço médio shows the non-additive faixa-de-preço range KPI', () => {
    stubGlobals(BY_METRIC);
    const { container } = render(
      <ViewPartners summary={{}} conventions={{}} database="mdic_comex" />
    );
    const priceBtn = [...container.querySelectorAll('.seg-opt')].find((b) => b.textContent === 'Preço médio');
    fireEvent.click(priceBtn);
    expect(partnerDataCalls).toContain('price');
    // Non-additive → faixa de preço KPI, not top-3 concentration.
    expect(container.querySelector('.kpi[data-label="Faixa de preço"]')).toBeTruthy();
    expect(container.querySelector('.kpi[data-label="Concentração top-3"]')).toBeFalsy();
    // Range value spans min–max over the positive prices: 6,25–42,50/kg.
    const faixa = container.querySelector('.kpi[data-label="Faixa de preço"] .kpi-value');
    expect(faixa.textContent).toContain('6,25');
    expect(faixa.textContent).toContain('42,50');
    // The null-price partner renders '—' for its measure.
    const vals = [...container.querySelectorAll('.ptn-val')].map((e) => e.textContent);
    expect(vals).toContain('—');
  });

  it('renders the empty faixa-de-preço KPI gracefully when there are no partners', () => {
    stubGlobals({
      ...BY_METRIC,
      price: { unit: 'US$', flowLabel: 'destino', notApplicable: null, partners: [] },
    });
    const { container } = render(
      <ViewPartners summary={{}} conventions={{}} database="comtrade" />
    );
    const priceBtn = [...container.querySelectorAll('.seg-opt')].find((b) => b.textContent === 'Preço médio');
    fireEvent.click(priceBtn);
    // No partners → faixa value falls back to '—', "Maior destino" is '—', no rows.
    const faixa = container.querySelector('.kpi[data-label="Faixa de preço"] .kpi-value');
    expect(faixa.textContent).toBe('—');
    const top = container.querySelector('.kpi[data-label="Maior destino"] .kpi-value');
    expect(top.textContent).toBe('—');
    expect(container.querySelectorAll('.ptn-row').length).toBe(0);
  });
});
