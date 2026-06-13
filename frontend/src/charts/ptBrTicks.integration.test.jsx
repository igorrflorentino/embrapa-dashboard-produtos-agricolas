// ptBrTicks.integration.test.jsx — FINDING #9 regression net across ALL value-axis
// charts. Each chart MUST tick its value axis in pt-BR magnitude words ("15 bi"),
// never d3-format's SI letters ("15G"/"3M") — otherwise the SAME R$ series reads
// "15G" on one card and "15 bi" on another. Originally only LineChart was migrated;
// these tests pin every chart that hosts a value axis so a future absolute-magnitude
// series can never reintroduce the mismatch. We feed each an ABSOLUTE-magnitude
// series (≥1e9), capture the layout it hands Plotly, and assert the value axis uses
// fixed pt-BR array ticks with no SI letter and no `~s` tickformat leaking through.

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

const { reactState } = vi.hoisted(() => ({ reactState: { lastLayout: null } }));

vi.mock('./plotlyBundle', () => ({
  default: {
    react: (_el, _traces, layout) => { reactState.lastLayout = layout; },
    purge: () => {},
    Plots: { resize: () => {} },
  },
}));

import BarChart from './BarChart.jsx';
import DualAxisLineChart from './DualAxisLineChart.jsx';
import LineChart from './LineChart.jsx';
import MonthlyOverlay from './MonthlyOverlay.jsx';
import MultiLineChart from './MultiLineChart.jsx';
import RegionBars from './RegionBars.jsx';
import StackedArea from './StackedArea.jsx';
import StackedPanels from './StackedPanels.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => { cleanup(); reactState.lastLayout = null; });

// An axis is "pt-BR migrated" when it uses fixed array ticks labelled in pt-BR
// magnitude words, with NO SI tickformat and NO SI letter (G/M/k) in any label.
function expectPtBrAxis(axis) {
  expect(axis, 'axis should exist on the layout').toBeTruthy();
  expect(axis.tickmode, 'value axis should use fixed array ticks').toBe('array');
  expect(axis.tickformat, 'no SI `~s` fallback when array ticks apply').toBeUndefined();
  expect(Array.isArray(axis.ticktext)).toBe(true);
  expect(axis.ticktext.join(' '), 'no SI letters leak into the labels').not.toMatch(/[GMk]/);
  // At least one tick is labelled in the pt-BR "bi" magnitude word.
  expect(axis.ticktext.some((s) => /bi$/.test(s))).toBe(true);
}

// Year x absolute-magnitude points (≥1e9) → the SI `~s` would print "15G".
const BIG_PTS = [
  { y: 2020, v: 5e9, value: 5e9 },
  { y: 2021, v: 15e9, value: 15e9 },
  { y: 2022, v: 10e9, value: 10e9 },
];

describe('FINDING #9 — every value-axis chart ticks in pt-BR magnitudes', () => {
  it('LineChart (y axis)', () => {
    render(<LineChart data={BIG_PTS} valueKey="v" />);
    expectPtBrAxis(reactState.lastLayout.yaxis);
  });

  it('BarChart (x axis — horizontal bars)', () => {
    render(<BarChart data={[{ uf: 'PA', value: 15e9 }, { uf: 'AM', value: 5e9 }]} />);
    expectPtBrAxis(reactState.lastLayout.xaxis);
  });

  it('RegionBars (y axis)', () => {
    render(<RegionBars data={[{ label: 'Norte', value: 15e9, ufs: 7 }]} valueKey="value" />);
    expectPtBrAxis(reactState.lastLayout.yaxis);
  });

  it('MultiLineChart (y axis — max over series)', () => {
    render(<MultiLineChart series={[{ name: 'A', data: BIG_PTS }]} valueKey="v" />);
    expectPtBrAxis(reactState.lastLayout.yaxis);
  });

  it('StackedArea (y axis — stacked totals)', () => {
    render(<StackedArea series={[{ name: 'A', data: BIG_PTS }]} valueKey="v" />);
    expectPtBrAxis(reactState.lastLayout.yaxis);
  });

  it('StackedPanels (per-panel y axis)', () => {
    render(<StackedPanels series={[{ label: 'A', unit: 'R$', data: BIG_PTS }]} />);
    expectPtBrAxis(reactState.lastLayout.yaxis);
  });

  it('MonthlyOverlay (y axis)', () => {
    render(<MonthlyOverlay series={[{ name: 'A', data: new Array(12).fill(15e9) }]} months={[]} />);
    expectPtBrAxis(reactState.lastLayout.yaxis);
  });

  it('DualAxisLineChart (both axes tick per-unit magnitude)', () => {
    render(
      <DualAxisLineChart
        series={[
          { label: 'L', unit: 'R$', data: BIG_PTS },
          { label: 'R', unit: 'US$', data: BIG_PTS },
        ]}
      />,
    );
    expectPtBrAxis(reactState.lastLayout.yaxis);
    expectPtBrAxis(reactState.lastLayout.yaxis2);
  });
});
