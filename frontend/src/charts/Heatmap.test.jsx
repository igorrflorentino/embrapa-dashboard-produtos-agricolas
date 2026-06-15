// Heatmap.test.jsx — column alignment for RAGGED per-row series. The matrix x
// axis must be the UNION of every row's years (sorted), and each row's values
// indexed into that shared axis with null for gaps. Building x from rows[0] alone
// shifted a sparse row's cells onto the wrong year. plotlyBundle is mocked so we
// capture the (x, y, z) trace Heatmap hands to Plot.

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const { reactState } = vi.hoisted(() => ({ reactState: { lastTraces: null } }));

vi.mock('./plotlyBundle', () => ({
  default: {
    react: (_el, traces) => { reactState.lastTraces = traces; },
    purge: () => {},
    Plots: { resize: () => {} },
  },
}));

import Heatmap from './Heatmap.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => { cleanup(); reactState.lastTraces = null; });

const trace = () => reactState.lastTraces?.[0];

describe('Heatmap ragged-row column alignment', () => {
  it('builds x from the UNION of years and indexes each row, gaps → null', () => {
    // Row B is missing 2019 → its 5 must land under 2020, NOT shift onto 2019.
    render(
      <Heatmap
        rows={[
          { id: 'PA', label: 'PA', values: [{ y: 2019, v: 1 }, { y: 2020, v: 2 }] },
          { id: 'SP', label: 'SP', values: [{ y: 2020, v: 5 }] },
        ]}
      />,
    );
    const t = trace();
    expect(t.x).toEqual([2019, 2020]);
    expect(t.y).toEqual(['PA', 'SP']);
    expect(t.z[0]).toEqual([1, 2]);
    expect(t.z[1]).toEqual([null, 5]); // 2019 gap → null; 5 stays under 2020
  });

  it('sorts the union axis chronologically regardless of row/value order', () => {
    render(
      <Heatmap
        rows={[
          { id: 'A', label: 'A', values: [{ y: 2021, v: 9 }, { y: 2019, v: 7 }] },
          { id: 'B', label: 'B', values: [{ y: 2020, v: 8 }] },
        ]}
      />,
    );
    const t = trace();
    expect(t.x).toEqual([2019, 2020, 2021]);
    expect(t.z[0]).toEqual([7, null, 9]); // A: 2019 & 2021 present, 2020 gap
    expect(t.z[1]).toEqual([null, 8, null]); // B: only 2020
  });

  it('renders an empty plot (no trace) when no row carries any year', () => {
    render(<Heatmap rows={[{ id: 'A', label: 'A', values: [] }]} />);
    expect(reactState.lastTraces).toEqual([]);
  });
});
