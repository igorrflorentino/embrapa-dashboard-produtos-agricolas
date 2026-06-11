// choroplethScale.test.js — the pure color logic behind the UF choropleth
// (maplibre itself needs WebGL, so it's verified in the browser, not here).

import { describe, expect, it } from 'vitest';

import { NODATA, RAMP, fillColorExpression, ufColorScale } from './choroplethScale';

describe('ufColorScale', () => {
  it('buckets values 0..max into the ramp; max → darkest, zero → no-data', () => {
    const { byUf, max } = ufColorScale(
      [{ uf: 'SP', v: 100 }, { uf: 'PA', v: 50 }, { uf: 'AC', v: 0 }],
      'v',
    );
    expect(max).toBe(100);
    expect(byUf.SP).toBe(RAMP[RAMP.length - 1]); // the maximum gets the darkest bucket
    expect(byUf.AC).toBe(NODATA); // zero → neutral "no data" gray
    expect(RAMP).toContain(byUf.PA); // a mid value lands on some ramp bucket
    expect(byUf.PA).not.toBe(NODATA);
  });

  it('is safe on empty / null / uf-less data', () => {
    expect(ufColorScale([], 'v').byUf).toEqual({});
    expect(ufColorScale(null, 'v').max).toBe(1); // max floored at 1 (no divide-by-zero)
    expect(ufColorScale([{ v: 5 }], 'v').byUf).toEqual({}); // rows with no uf are skipped
  });
});

describe('fillColorExpression', () => {
  it('builds a maplibre match expression on the uf property, fallback last', () => {
    const expr = fillColorExpression({ SP: '#aaa', PA: '#bbb' }, '#fff');
    expect(expr[0]).toBe('match');
    expect(expr[1]).toEqual(['get', 'uf']);
    expect(expr).toContain('SP');
    expect(expr).toContain('#aaa');
    expect(expr[expr.length - 1]).toBe('#fff');
  });

  it('returns the constant fallback when there is nothing to color', () => {
    expect(fillColorExpression({}, '#fff')).toBe('#fff');
  });
});
