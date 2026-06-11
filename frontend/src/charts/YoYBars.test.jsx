// YoYBars.test.jsx — the year-over-year % math. The guard must treat ONLY a
// missing prev (null/undefined) or prev===0 as "no base" (→ 0%, avoiding a
// divide-by-zero), while a legit prior value — including a small or negative
// one — still yields a real variation. plotlyBundle is mocked so we capture the
// traces YoYBars hands to Plot and read the computed pct off trace.y.

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

// Capture the last traces passed to Plotly.react (arg index 1).
const { reactState } = vi.hoisted(() => ({ reactState: { lastTraces: null } }));

vi.mock('./plotlyBundle', () => ({
  default: {
    react: (_el, traces) => { reactState.lastTraces = traces; },
    purge: () => {},
    Plots: { resize: () => {} },
  },
}));

import YoYBars from './YoYBars.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => { cleanup(); reactState.lastTraces = null; });

// The chart slices off the first point (no prior year), so trace.y[k] is the
// YoY for input row k+1.
const pcts = () => reactState.lastTraces?.[0]?.y ?? [];

describe('YoYBars year-over-year math', () => {
  it('computes a real % for a normal increase/decrease (not zeroed)', () => {
    render(<YoYBars data={[{ y: 2020, v: 100 }, { y: 2021, v: 50 }, { y: 2022, v: 75 }]} />);
    // 100→50 = -50%, 50→75 = +50%.
    expect(pcts()).toEqual([-50, 50]);
  });

  it('returns 0% when the prior value is exactly 0 (no divide-by-zero)', () => {
    render(<YoYBars data={[{ y: 2020, v: 0 }, { y: 2021, v: 10 }]} />);
    expect(pcts()).toEqual([0]);
  });

  it('returns 0% when the prior value is missing (null/undefined)', () => {
    render(<YoYBars data={[{ y: 2020 }, { y: 2021, v: 10 }]} />);
    expect(pcts()).toEqual([0]);
  });

  it('still computes a % when the prior value is negative', () => {
    render(<YoYBars data={[{ y: 2020, v: -20 }, { y: 2021, v: -10 }]} />);
    // (-10 - -20) / -20 * 100 = -50%. The null/zero-aware guard only treats
    // null/undefined/0 as "no base", so a real negative base still computes.
    expect(pcts()).toEqual([-50]);
  });
});
