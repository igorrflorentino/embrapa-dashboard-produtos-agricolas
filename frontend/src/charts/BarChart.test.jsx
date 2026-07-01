// BarChart.test.jsx — the bar-tip value label format. Compact magnitude by default
// ("2,9 bi") for monetary/aggregate values that would otherwise overflow the card;
// raw pt-BR ("3.500") when compact=false for UNIT metrics like kg/ha yield, where the
// magnitude word ("3,5 mil") misleads (audit CORR-1). plotlyBundle is mocked so we
// capture the traces BarChart hands to Plot and read the computed `text` array.

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

import BarChart from './BarChart.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => { cleanup(); reactState.lastTraces = null; });

const labels = () => reactState.lastTraces?.[0]?.text ?? [];

describe('BarChart value labels', () => {
  const data = [{ uf: 'PA', value: 2_900_918_362 }, { uf: 'MT', value: 3500 }];

  it('uses COMPACT magnitude labels by default (monetary / aggregate values)', () => {
    render(<BarChart data={data} valueKey="value" />);
    expect(labels()[0]).toBe('2,9 bi');
    expect(labels()[1]).toBe('3,5 mil');
  });

  it('compact={false} keeps the exact pt-BR integer (unit metrics like kg/ha) — audit CORR-1', () => {
    render(<BarChart data={data} valueKey="value" compact={false} />);
    expect(labels()[0]).toBe('2.900.918.362');
    expect(labels()[1]).toBe('3.500'); // NOT "3,5 mil" — a yield reads as the exact figure
  });

  it('renders an empty label for a null value in either mode', () => {
    render(<BarChart data={[{ uf: 'XX', value: null }]} valueKey="value" compact={false} />);
    expect(labels()[0]).toBe('');
  });
});
