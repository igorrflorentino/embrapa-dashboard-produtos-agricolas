// MultiLineChart.test.jsx — one line per series on a shared axis (comparison
// views). Locks the per-series mapping (data → x/y), the configurable valueKey, and
// the palette colour fallback that keeps colour-less series visually distinct. We
// capture the traces the chart hands Plotly; plotlyBundle is mocked.

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const { reactState } = vi.hoisted(() => ({ reactState: { traces: null, layout: null } }));

vi.mock('./plotlyBundle', () => ({
  default: {
    react: (_el, traces, layout) => { reactState.traces = traces; reactState.layout = layout; },
    purge: () => {},
    Plots: { resize: () => {} },
  },
}));

import MultiLineChart from './MultiLineChart.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
});

afterEach(() => { cleanup(); reactState.traces = null; reactState.layout = null; });

describe('MultiLineChart', () => {
  it('renders no traces for empty series', () => {
    render(<MultiLineChart series={[]} />);
    expect(reactState.traces).toEqual([]);
  });

  it('emits one line trace per series, mapping data to x=year / y=value', () => {
    const series = [
      { name: 'PEVS', data: [{ y: 2020, v: 3 }, { y: 2021, v: 4 }] },
      { name: 'COMEX', data: [{ y: 2020, v: 9 }, { y: 2021, v: 8 }] },
    ];
    render(<MultiLineChart series={series} />);
    const t = reactState.traces;
    expect(t).toHaveLength(2);
    expect(t.map((tr) => tr.name)).toEqual(['PEVS', 'COMEX']);
    expect(t[0].x).toEqual([2020, 2021]);
    expect(t[1].y).toEqual([9, 8]);
    expect(t.every((tr) => tr.mode === 'lines')).toBe(true);
  });

  it('honours a custom valueKey', () => {
    const series = [{ name: 'Preço', data: [{ y: 2020, price: 1.5 }, { y: 2021, price: 2.0 }] }];
    render(<MultiLineChart series={series} valueKey="price" />);
    expect(reactState.traces[0].y).toEqual([1.5, 2.0]);
  });

  it('respects an explicit series colour and falls back to the palette otherwise', () => {
    // jsdom has no stylesheet, so CSS-var colours all resolve to the same fallback;
    // a LITERAL colour passes through resolveColor untouched. This pins the branch:
    // an explicit colour is used as-is, a colour-less series gets the (resolved)
    // palette default — so a series that sets its colour is never overridden.
    const series = [
      { name: 'A', color: '#aa0000', data: [{ y: 2020, v: 1 }] },
      { name: 'B', data: [{ y: 2020, v: 2 }] }, // no colour → palette fallback
    ];
    render(<MultiLineChart series={series} />);
    const [a, b] = reactState.traces;
    expect(a.line.color).toBe('#aa0000'); // explicit colour respected
    expect(b.line.color).toBeTruthy(); // fallback colour applied
    expect(b.line.color).not.toBe('#aa0000');
  });

  it('shows the Plotly legend by default and hides it when showLegend=false', () => {
    // Default keeps the native legend (e.g. ViewRebanho / the ratio card rely on it).
    render(<MultiLineChart series={[{ name: 'A', data: [{ y: 2020, v: 1 }] }]} />);
    expect(reactState.layout.showlegend).toBe(true);
    cleanup();
    // Comparison views with their own pc-legend/xs-legend opt out to avoid a duplicate.
    render(<MultiLineChart series={[{ name: 'A', data: [{ y: 2020, v: 1 }] }]} showLegend={false} />);
    expect(reactState.layout.showlegend).toBe(false);
  });
});
