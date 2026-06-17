// StackedArea.test.jsx — products as stacked layers over time. Two properties
// worth locking: (1) every trace shares the SAME stackgroup so Plotly actually
// stacks them, and (2) the value axis is sized to the per-year STACK SUM, not any
// single series' peak — otherwise the top layer would clip out of frame. We capture
// the traces + layout the chart hands Plotly; plotlyBundle is mocked.

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

import StackedArea from './StackedArea.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
});

afterEach(() => { cleanup(); reactState.traces = null; reactState.layout = null; });

describe('StackedArea', () => {
  it('renders no traces for empty series (never throws)', () => {
    render(<StackedArea series={[]} />);
    expect(reactState.traces).toEqual([]);
  });

  it('puts every series in the same stackgroup and maps data to x=year / y=value', () => {
    const series = [
      { name: 'Açaí', data: [{ y: 2020, v: 3 }, { y: 2021, v: 4 }] },
      { name: 'Babaçu', data: [{ y: 2020, v: 2 }, { y: 2021, v: 1 }] },
    ];
    render(<StackedArea series={series} />);
    const t = reactState.traces;
    expect(t).toHaveLength(2);
    expect(t.every((tr) => tr.stackgroup === 'one')).toBe(true);
    expect(t[0].x).toEqual([2020, 2021]);
    expect(t[0].y).toEqual([3, 4]);
  });

  it('sizes the y axis to the per-year STACK SUM, not a single series peak', () => {
    // Five series each peaking at 10 in the same year → stacked sum 50. A bug that
    // used the single-series max (10) could never produce a top tick ≥ 50.
    const series = Array.from({ length: 5 }, (_, i) => ({
      name: `S${i}`,
      data: [{ y: 2020, v: 10 }, { y: 2021, v: 1 }],
    }));
    render(<StackedArea series={series} />);
    const tickvals = reactState.layout.yaxis.tickvals;
    expect(Array.isArray(tickvals)).toBe(true); // positive max → fixed pt-BR array ticks
    expect(Math.max(...tickvals)).toBeGreaterThanOrEqual(50);
  });

  it('falls back to the palette colour and a default name when a series omits them', () => {
    const series = [{ data: [{ y: 2020, v: 5 }] }]; // no name, no color
    render(<StackedArea series={series} />);
    const tr = reactState.traces[0];
    expect(tr.line.color).toBeTruthy(); // palette fallback resolved to a colour
    expect(tr.fillcolor).toBeTruthy();
    expect(tr.name).toBe('Série 1'); // name || code || `Série ${i+1}`
  });

  it('prefers name, then code, for the trace label', () => {
    render(<StackedArea series={[{ code: '0801', data: [] }]} />);
    expect(reactState.traces[0].name).toBe('0801');
  });
});
