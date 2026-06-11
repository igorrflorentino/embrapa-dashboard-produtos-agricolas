// _base.test.jsx — the Plot wrapper's error boundary. A malformed trace must
// degrade to an inline fallback for THAT chart, not throw out of the effect and
// blank the whole perspective (ViewErrorBoundary). plotlyBundle is mocked so we
// drive Plotly.react to succeed or throw on demand; ResizeObserver is stubbed
// (jsdom has none).

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

// vi.hoisted so the mock factory can reach this mutable impl (vi.mock is hoisted
// above imports). Each test swaps reactState.impl to choose success/throw.
const { reactState } = vi.hoisted(() => ({ reactState: { impl: () => {} } }));

vi.mock('./plotlyBundle', () => ({
  default: {
    react: (...args) => reactState.impl(...args),
    purge: () => {},
    Plots: { resize: () => {} },
  },
}));

import { Plot } from './_base.jsx';

beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => cleanup());

const FALLBACK = /Não foi possível renderizar este gráfico/;

describe('Plot error boundary', () => {
  it('renders the chart host and no fallback when Plotly succeeds', () => {
    const ok = vi.fn();
    reactState.impl = ok;

    render(<Plot traces={[{ x: [1, 2], y: [3, 4] }]} />);

    expect(ok).toHaveBeenCalled();
    expect(screen.queryByText(FALLBACK)).toBeNull();
  });

  it('shows an inline fallback when Plotly.react throws (the view survives)', async () => {
    reactState.impl = () => {
      throw new Error('malformed trace');
    };

    render(<Plot traces={[{ bogus: true }]} />);

    // The throw is caught in the effect → fallback rendered, no error propagates.
    expect(await screen.findByText(FALLBACK)).toBeTruthy();
  });
});
