// LorenzCurve.test.jsx — the concentration curve carries real math (cumulative
// share of units vs cumulative share of value), so we capture the trace it hands
// Plotly and assert the curve points. plotlyBundle is mocked (no real WebGL/DOM
// plot); the data-shaping is the part worth locking.

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const { reactState } = vi.hoisted(() => ({ reactState: { traces: null } }));

vi.mock('./plotlyBundle', () => ({
  default: {
    react: (_el, traces) => { reactState.traces = traces; },
    purge: () => {},
    Plots: { resize: () => {} },
  },
}));

import LorenzCurve from './LorenzCurve.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
});

afterEach(() => { cleanup(); reactState.traces = null; });

// The first trace is always the 45° equality line; the Lorenz curve (when present)
// is the second.
const equality = () => reactState.traces?.[0];
const lorenz = () => reactState.traces?.[1];

describe('LorenzCurve', () => {
  it('draws ONLY the equality line on empty input (the frame still reads as a chart)', () => {
    render(<LorenzCurve values={[]} />);
    expect(reactState.traces).toHaveLength(1);
    expect(equality().x).toEqual([0, 1]);
    expect(equality().y).toEqual([0, 1]);
    expect(equality().line.dash).toBe('dash');
  });

  it('a perfectly equal distribution traces (near) the 45° line', () => {
    render(<LorenzCurve values={[10, 10, 10, 10]} />);
    const l = lorenz();
    // Cumulative-unit share (x) and cumulative-value share (y) coincide: each step
    // adds 1/4 of the units AND 1/4 of the value.
    expect(l.x).toEqual([0, 0.25, 0.5, 0.75, 1]);
    expect(l.y).toEqual([0, 0.25, 0.5, 0.75, 1]);
  });

  it('a concentrated distribution bows BELOW the equality line', () => {
    // Three tiny holders + one dominant: the curve stays under y=x until the last
    // (richest) unit, where it snaps to 1.
    render(<LorenzCurve values={[1, 1, 1, 97]} />);
    const l = lorenz();
    expect(l.x).toEqual([0, 0.25, 0.5, 0.75, 1]);
    // y at each x is the cumulative VALUE share: 1/100, 2/100, 3/100, then 1.
    expect(l.y[1]).toBeCloseTo(0.01);
    expect(l.y[2]).toBeCloseTo(0.02);
    expect(l.y[3]).toBeCloseTo(0.03);
    expect(l.y[4]).toBe(1);
    // Below the diagonal everywhere but the endpoints (Lorenz dominance).
    for (let i = 1; i < l.x.length - 1; i++) expect(l.y[i]).toBeLessThan(l.x[i]);
  });

  it('ignores non-positive values (zeros/negatives do not count as units)', () => {
    // Only the two positives (10, 30) define the curve → n=2, total=40.
    render(<LorenzCurve values={[0, -5, 10, 30]} />);
    const l = lorenz();
    expect(l.x).toEqual([0, 0.5, 1]); // two units
    expect(l.y).toEqual([0, 0.25, 1]); // 10/40 then 40/40
  });

  it('always ends at (1, 1)', () => {
    render(<LorenzCurve values={[3, 7, 2, 19, 5]} />);
    const l = lorenz();
    expect(l.x[l.x.length - 1]).toBe(1);
    expect(l.y[l.y.length - 1]).toBe(1);
  });
});
