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

// Stand-in for Plotly's graph-div event API: real Plotly augments the element
// with .on/.removeListener/.emit. The default impl wires a tiny listener
// registry onto the element so click-rebinding can be exercised; tests that
// only care about the error boundary swap reactState.impl to a no-op/throw.
vi.mock('./plotlyBundle', () => ({
  default: {
    react: (...args) => reactState.impl(...args),
    purge: () => {},
    Plots: { resize: () => {} },
  },
}));

// Equip an element with the minimal Plotly event surface used by Plot.
function wirePlotlyEvents(el) {
  if (el.__listeners) return; // idempotent across re-renders
  el.__listeners = {};
  el.on = (evt, fn) => { (el.__listeners[evt] ||= []).push(fn); };
  el.removeListener = (evt, fn) => {
    el.__listeners[evt] = (el.__listeners[evt] || []).filter((f) => f !== fn);
  };
  el.__emit = (evt, payload) => (el.__listeners[evt] || []).forEach((f) => f(payload));
}

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

describe('Plot click handler rebinding', () => {
  // Regression: the plotly_click listener is bound once on mount. It must call
  // the CURRENT onClick (which closes over the current data) — not the stale
  // first-render one — when the parent re-renders with a new handler/data.
  it('invokes the latest onClick after the prop changes, not the first one', () => {
    reactState.impl = (el) => wirePlotlyEvents(el);

    const first = vi.fn();
    const second = vi.fn();
    const { container, rerender } = render(
      <Plot traces={[{ x: [1], y: [1] }]} onClick={first} />,
    );
    // The chart host is the inner div the ref attaches to — it's the element
    // Plotly.react was called with, so it carries the wired .on/.emit surface.
    const host = [...container.querySelectorAll('div')].find((d) => typeof d.__emit === 'function');
    expect(host, 'chart host should have the Plotly event surface wired').toBeTruthy();

    host.__emit('plotly_click', { points: [{ x: 1 }] });
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).not.toHaveBeenCalled();

    // Re-render with a different handler (as a parent would when data changes).
    rerender(<Plot traces={[{ x: [2], y: [2] }]} onClick={second} />);
    host.__emit('plotly_click', { points: [{ x: 2 }] });

    // The latest handler fires; the stale one is NOT called again.
    expect(second).toHaveBeenCalledTimes(1);
    expect(first).toHaveBeenCalledTimes(1);
  });
});
