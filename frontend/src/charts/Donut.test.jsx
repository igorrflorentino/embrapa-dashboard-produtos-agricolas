// Donut.test.jsx — the share-ring is pure SVG (no Plotly), so we render it and
// read the legend percentages + slice paths. Locks the M5 coercion: a missing or
// non-numeric valueKey must not produce NaN% legend text or a NaN-coordinate
// (blank) ring — Number(d[valueKey]) || 0 treats it as 0.

import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import Donut from './Donut.jsx';

afterEach(() => cleanup());

const legendPercents = (container) =>
  Array.from(container.querySelectorAll('.donut-legend .lval')).map((n) => n.textContent);

const slicePaths = (container) =>
  Array.from(container.querySelectorAll('svg path')).map((p) => p.getAttribute('d'));

describe('Donut — coerces missing/non-numeric values (M5)', () => {
  it('renders 0% (not NaN%) for a datum missing the valueKey', () => {
    const { container } = render(
      <Donut data={[{ name: 'A', share: 0.75 }, { name: 'B' /* no share */ }]} />,
    );
    const pcts = legendPercents(container);
    expect(pcts).toEqual(['75%', '0%']);
    expect(pcts.join(' ')).not.toMatch(/NaN/);
  });

  it('does not emit NaN coordinates in any slice path', () => {
    const { container } = render(
      <Donut data={[{ name: 'A', share: 0.5 }, { name: 'B', share: undefined }, { name: 'C', share: 0.5 }]} />,
    );
    slicePaths(container).forEach((d) => expect(d).not.toMatch(/NaN/));
  });

  it('treats a non-numeric value as 0', () => {
    const { container } = render(
      <Donut data={[{ name: 'A', share: 0.6 }, { name: 'B', share: 'oops' }]} />,
    );
    const pcts = legendPercents(container);
    expect(pcts).toEqual(['60%', '0%']);
  });

  it('an all-missing dataset yields 0% slices and a blank-safe (NaN-free) ring', () => {
    const { container } = render(<Donut data={[{ name: 'A' }, { name: 'B' }]} />);
    expect(legendPercents(container)).toEqual(['0%', '0%']);
    slicePaths(container).forEach((d) => expect(d).not.toMatch(/NaN/));
  });

  it('still renders correct shares for fully-populated data', () => {
    const { container } = render(
      <Donut data={[{ name: 'A', share: 0.4 }, { name: 'B', share: 0.6 }]} />,
    );
    expect(legendPercents(container)).toEqual(['40%', '60%']);
  });
});
