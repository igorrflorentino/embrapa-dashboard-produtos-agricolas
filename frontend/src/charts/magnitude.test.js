// magnitude.test.js — locks the single bi/mi/mil threshold ladder (DEDUP-7). The chart
// axis (ptBrMagnitude) and the KPI auto-scale (window.autoScaleNum) both derive from this
// kernel, so a regression here is the one place an axis-vs-KPI drift could re-enter.

import { describe, expect, it } from 'vitest';

import { magnitudeParts } from './magnitude.js';

describe('magnitudeParts — the shared pt-BR magnitude ladder', () => {
  it('selects the right factor + bare suffix per threshold', () => {
    expect(magnitudeParts(15e9)).toEqual({ factor: 1e9, suffix: 'bi' });
    expect(magnitudeParts(3.4e6)).toEqual({ factor: 1e6, suffix: 'mi' });
    expect(magnitudeParts(5000)).toEqual({ factor: 1e3, suffix: 'mil' });
    expect(magnitudeParts(150)).toEqual({ factor: 1, suffix: '' });
  });

  it('thresholds on absolute value (so negatives scale symmetrically)', () => {
    expect(magnitudeParts(-2e9)).toEqual({ factor: 1e9, suffix: 'bi' });
    expect(magnitudeParts(-500)).toEqual({ factor: 1, suffix: '' });
  });

  it('is exclusive at the boundary minus one and inclusive at the threshold', () => {
    expect(magnitudeParts(1e9).suffix).toBe('bi');
    expect(magnitudeParts(1e9 - 1).suffix).toBe('mi');
    expect(magnitudeParts(1e3).suffix).toBe('mil');
    expect(magnitudeParts(999).suffix).toBe('');
  });
});
