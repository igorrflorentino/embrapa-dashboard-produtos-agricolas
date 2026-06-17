// StackedPanels.test.jsx — small-multiples: one stacked panel per series, each
// pinned to its OWN x/y subplot pair. Regression lock: binding only the y axis (the
// old bug) left x2…xN undefined → an invalid Plotly layout that threw and blanked
// "Painéis". This captures the traces + layout the chart builds and asserts every
// panel gets a MATCHED x and y axis, plus an independent grid. plotlyBundle mocked.

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

import StackedPanels from './StackedPanels.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
});

afterEach(() => { cleanup(); reactState.traces = null; reactState.layout = null; });

const SERIES = [
  { label: 'PEVS valor', bancoShort: 'IBGE', unit: 'R$ bi', data: [{ y: 2020, v: 3 }, { y: 2021, v: 4 }] },
  { label: 'COMEX FOB', bancoShort: 'MDIC', unit: 'US$ bi', data: [{ y: 2020, v: 9 }, { y: 2021, v: 8 }] },
  { label: 'Comtrade', bancoShort: 'UN', unit: 'US$ bi', data: [{ y: 2020, v: 5 }, { y: 2021, v: 6 }] },
];

describe('StackedPanels', () => {
  it('renders an empty plot for no series (never throws)', () => {
    render(<StackedPanels series={[]} />);
    expect(reactState.traces).toEqual([]);
  });

  it('binds each trace to its OWN matched x AND y axis pair (the regression)', () => {
    render(<StackedPanels series={SERIES} />);
    const t = reactState.traces;
    expect(t).toHaveLength(3);
    expect(t[0]).toMatchObject({ xaxis: 'x', yaxis: 'y' });
    expect(t[1]).toMatchObject({ xaxis: 'x2', yaxis: 'y2' });
    expect(t[2]).toMatchObject({ xaxis: 'x3', yaxis: 'y3' });
    // No trace may omit either axis — that's exactly what blanked the panel before.
    t.forEach((tr) => {
      expect(tr.xaxis).toBeTruthy();
      expect(tr.yaxis).toBeTruthy();
    });
  });

  it('declares an independent grid with one row per series', () => {
    render(<StackedPanels series={SERIES} />);
    expect(reactState.layout.grid).toMatchObject({
      rows: 3,
      columns: 1,
      pattern: 'independent',
    });
    // A matched x AND y axis object exists for every panel.
    expect(reactState.layout.xaxis).toBeTruthy();
    expect(reactState.layout.xaxis2).toBeTruthy();
    expect(reactState.layout.xaxis3).toBeTruthy();
    expect(reactState.layout.yaxis).toBeTruthy();
    expect(reactState.layout.yaxis2).toBeTruthy();
    expect(reactState.layout.yaxis3).toBeTruthy();
  });

  it('locks the stacked panels to a shared year range and only labels the bottom row', () => {
    render(<StackedPanels series={SERIES} />);
    // Secondary panels match the first panel's x range (synchronised zoom/pan).
    expect(reactState.layout.xaxis2.matches).toBe('x');
    expect(reactState.layout.xaxis3.matches).toBe('x');
    // Only the bottom panel (last) shows tick labels, so they read as one axis.
    expect(reactState.layout.xaxis.showticklabels).toBe(false);
    expect(reactState.layout.xaxis3.showticklabels).toBe(true);
  });

  it('maps each series data to x=year / y=value', () => {
    render(<StackedPanels series={SERIES} />);
    expect(reactState.traces[1].x).toEqual([2020, 2021]);
    expect(reactState.traces[1].y).toEqual([9, 8]);
  });
});
