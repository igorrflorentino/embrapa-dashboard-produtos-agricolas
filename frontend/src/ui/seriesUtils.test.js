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
});
