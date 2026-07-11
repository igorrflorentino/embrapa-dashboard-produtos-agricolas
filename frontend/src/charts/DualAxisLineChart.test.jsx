// DualAxisLineChart.test.jsx — up to two Y axes, one per distinct `unit` (first
// unit → left/y, second → right/y2). Locks the axis-assignment rule and the
// opt-out Plotly legend (`showLegend`) so ViewCrossSource / ViewSeasonality —
// which draw their own xs-legend / pc-legend — don't render two legends. We
// capture the traces + layout handed to Plotly; plotlyBundle is mocked.

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

import DualAxisLineChart from './DualAxisLineChart.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
});

afterEach(() => { cleanup(); reactState.traces = null; reactState.layout = null; });

const SERIES = [
  { label: 'Volume', unit: 'mil t', data: [{ y: 2020, v: 3 }, { y: 2021, v: 4 }] },
  { label: 'Capital', unit: 'US$', data: [{ y: 2020, v: 30 }, { y: 2021, v: 40 }] },
];

describe('DualAxisLineChart', () => {
  it('renders no traces for empty series', () => {
    render(<DualAxisLineChart series={[]} />);
    expect(reactState.traces).toEqual([]);
  });

  it('puts the first unit on the left axis (y) and the second on the right (y2)', () => {
    render(<DualAxisLineChart series={SERIES} />);
    const t = reactState.traces;
    expect(t).toHaveLength(2);
    expect(t[0].yaxis).toBe('y');   // first distinct unit → left
    expect(t[1].yaxis).toBe('y2');  // second distinct unit → right
    expect(reactState.layout.yaxis2).toBeTruthy();
    expect(reactState.layout.yaxis2.side).toBe('right');
  });

  it('appends bancoShort to the trace name when present', () => {
    render(<DualAxisLineChart series={[{ label: 'Preço', unit: 'US$', bancoShort: 'COMEX', data: [{ y: 2020, v: 1 }] }]} />);
    expect(reactState.traces[0].name).toBe('Preço (COMEX)');
  });

  it('shows the Plotly legend by default and hides it when showLegend=false', () => {
    render(<DualAxisLineChart series={SERIES} />);
    expect(reactState.layout.showlegend).toBe(true);
    cleanup();
    // ViewCrossSource (xs-legend) / ViewSeasonality (pc-legend) opt out.
    render(<DualAxisLineChart series={SERIES} showLegend={false} />);
    expect(reactState.layout.showlegend).toBe(false);
  });
});
