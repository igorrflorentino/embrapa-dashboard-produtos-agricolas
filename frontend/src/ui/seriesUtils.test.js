// seriesUtils.test.js — locks the year-aware correlation (M2). The cross-source
// ratio + correlation used to pair series BY ARRAY INDEX, which silently misaligns
// the moment one series has an internal year gap. pearsonByYear aligns by point.y.
//
// seriesUtils.js registers its helpers on `window` (window-global style); importing
// it for side-effects under jsdom populates window.pearson / window.pearsonByYear.

import { describe, expect, it } from 'vitest';

import './seriesUtils.js';

describe('pearsonByYear — aligns two series BY YEAR, not by array index (M2)', () => {
  it('perfectly co-moving, gap-free series → +1', () => {
    // VARYING growth (a constant-growth/geometric series has zero growth variance,
    // for which Pearson is undefined → 0 by convention). Identical varying growth → +1.
    const a = [{ y: 2000, v: 10 }, { y: 2001, v: 20 }, { y: 2002, v: 15 }, { y: 2003, v: 30 }];
    const b = [{ y: 2000, v: 100 }, { y: 2001, v: 200 }, { y: 2002, v: 150 }, { y: 2003, v: 300 }];
    expect(window.pearsonByYear(a, b)).toBeCloseTo(1, 6);
  });

  it('equals the legacy index correlation when years are identical & gap-free', () => {
    const a = [{ y: 2010, v: 5 }, { y: 2011, v: 6 }, { y: 2012, v: 4 }, { y: 2013, v: 9 }];
    const b = [{ y: 2010, v: 50 }, { y: 2011, v: 40 }, { y: 2012, v: 55 }, { y: 2013, v: 30 }];
    const legacy = window.pearson(window.seriesGrowth(a), window.seriesGrowth(b));
    expect(window.pearsonByYear(a, b)).toBeCloseTo(legacy, 6);
  });

  it('an internal year gap no longer misaligns the pairing', () => {
    // A is missing 2003 and carries a far-future 2010; B is dense through 2003.
    // The common, calendar-adjacent years are 2000-2002, where the two series move
    // identically → +1. The OLD index path would have paired A[3]=2010 against
    // B[3]=2003 and produced a spurious value.
    const a = [{ y: 2000, v: 10 }, { y: 2001, v: 20 }, { y: 2002, v: 30 }, { y: 2010, v: 5 }];
    const b = [{ y: 2000, v: 10 }, { y: 2001, v: 20 }, { y: 2002, v: 30 }, { y: 2003, v: 99 }];
    expect(window.pearsonByYear(a, b)).toBeCloseTo(1, 6);
    const legacy = window.pearson(window.seriesGrowth(a), window.seriesGrowth(b));
    expect(Math.abs(legacy - 1)).toBeGreaterThan(0.01); // the buggy index path diverges
  });

  it('skips growth across a gap and never crashes on sparse overlap', () => {
    const a = [{ y: 2000, v: 100 }, { y: 2001, v: 110 }, { y: 2003, v: 121 }];
    const b = [{ y: 2000, v: 100 }, { y: 2001, v: 90 }, { y: 2002, v: 80 }, { y: 2003, v: 70 }];
    const r = window.pearsonByYear(a, b);
    expect(Number.isFinite(r)).toBe(true);
    expect(r).toBeGreaterThanOrEqual(-1);
    expect(r).toBeLessThanOrEqual(1);
  });

  it('correlates on a custom key (q for a value-less herd, not v)', () => {
    // ViewProductCompare passes key="q" for an all-herd basket: v=0 for a stock, so the
    // default key="v" would read zero growth (variance 0 → 0). On "q" (cabeças) the same
    // co-moving growth gives +1 — the measure-aware correlation the audit fix added.
    const a = [{ y: 2000, q: 10, v: 0 }, { y: 2001, q: 20, v: 0 }, { y: 2002, q: 15, v: 0 }, { y: 2003, q: 30, v: 0 }];
    const b = [{ y: 2000, q: 100, v: 0 }, { y: 2001, q: 200, v: 0 }, { y: 2002, q: 150, v: 0 }, { y: 2003, q: 300, v: 0 }];
    expect(window.pearsonByYear(a, b, 'q')).toBeCloseTo(1, 6);
    expect(window.pearsonByYear(a, b, 'v')).toBe(0); // all-zero value → no growth variance
  });
});

describe('linearFit — OLS trend line (the "linha de tendência" overlay)', () => {
  it('recovers the slope/intercept of a perfectly linear series', () => {
    // v = 2·y - 4000 over 2000..2003
    const pts = [{ y: 2000, v: 0 }, { y: 2001, v: 2 }, { y: 2002, v: 4 }, { y: 2003, v: 6 }];
    const fit = window.linearFit(pts);
    expect(fit.slope).toBeCloseTo(2, 6);
    expect(fit.predict(2004)).toBeCloseTo(8, 6);
    // line endpoints span the x-range and lie on the fit
    expect(fit.line[0]).toMatchObject({ y: 2000 });
    expect(fit.line[1].y).toBe(2003);
    expect(fit.line[1].v).toBeCloseTo(6, 6);
  });

  it('fits a least-squares slope through noisy points', () => {
    const pts = [{ y: 1, v: 1 }, { y: 2, v: 3 }, { y: 3, v: 2 }, { y: 4, v: 5 }, { y: 5, v: 4 }];
    const fit = window.linearFit(pts);
    expect(fit.slope).toBeCloseTo(0.8, 6); // classic textbook OLS result
  });

  it('returns null on fewer than 2 finite points or zero x-variance', () => {
    expect(window.linearFit([])).toBeNull();
    expect(window.linearFit([{ y: 2000, v: 5 }])).toBeNull();
    expect(window.linearFit([{ y: 2000, v: 1 }, { y: 2000, v: 9 }])).toBeNull(); // all x equal
    expect(window.linearFit([{ y: 2000, v: NaN }, { y: 2001, v: 3 }])).toBeNull();
  });

  it('honours a custom value key', () => {
    const pts = [{ y: 2000, q: 10 }, { y: 2001, q: 20 }];
    const fit = window.linearFit(pts, 'q');
    expect(fit.slope).toBeCloseTo(10, 6);
    expect(fit.line[0].q).toBeDefined();
  });
});
