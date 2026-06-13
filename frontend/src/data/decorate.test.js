// decorate.test.js — the registry joins the /api/snapshot deliberately omits.
// Pure function; we stub the proto registries on window and assert the merge,
// including the "API value wins, registry fills the gap" precedence.

import { beforeEach, describe, expect, it } from 'vitest';

import { decorateSnapshot, isCanonicalUf } from './decorate.js';

describe('decorateSnapshot', () => {
  beforeEach(() => {
    window.UF_DATA = [{ uf: 'PA', col: 7, row: 2, region: 'Norte', name: 'Pará' }];
    window.QUALITY_FLAGS = [{ id: 'OK', label: 'Sem ressalvas', color: 'var(--ok)' }];
    window.REGIONS = [{ id: 'N', name: 'Norte' }];
  });

  it('joins UF tile coords + region/name from the registry', () => {
    const out = decorateSnapshot({ ufData: [{ uf: 'PA', value: 1.5 }] });
    expect(out.ufData[0]).toMatchObject({
      uf: 'PA',
      value: 1.5,
      col: 7,
      row: 2,
      region: 'Norte',
      name: 'Pará',
    });
  });

  it('keeps values the API already provided, fills only the gaps', () => {
    const out = decorateSnapshot({ ufData: [{ uf: 'PA', value: 1, col: 99, region: 'X' }] });
    expect(out.ufData[0].col).toBe(99); // API col wins (?? keeps 99)
    expect(out.ufData[0].region).toBe('X'); // API region wins (|| keeps 'X')
    expect(out.ufData[0].name).toBe('Pará'); // missing → filled from the registry
  });

  it('joins quality flag label + color, falling back when the id is unknown', () => {
    const out = decorateSnapshot({ quality: [{ id: 'OK', count: 5 }, { id: 'WEIRD', count: 1 }] });
    expect(out.quality[0]).toMatchObject({ label: 'Sem ressalvas', color: 'var(--ok)' });
    expect(out.quality[1].label).toBe('WEIRD'); // unknown id → id as its own label
    expect(out.quality[1].color).toBe('var(--pres-gray-400)'); // fallback color
  });

  it('defaults regions and is null/empty-safe', () => {
    expect(decorateSnapshot(null)).toBe(null);
    const out = decorateSnapshot({});
    expect(out.regions).toEqual([{ id: 'N', name: 'Norte' }]);
    expect(out.ufData).toBeUndefined(); // no ufData key → left untouched
  });

  it('decorates in place (same object ref) and leaves empty arrays untouched', () => {
    const snap = { ufData: [], quality: [] };
    const out = decorateSnapshot(snap);
    expect(out).toBe(snap); // in-place contract — the views hold this same ref
    expect(out.ufData).toEqual([]); // empty arrays skip the map, stay []
    expect(out.quality).toEqual([]);
  });
});

describe('isCanonicalUf (FINDING #4)', () => {
  beforeEach(() => {
    window.UF_DATA = [
      { uf: 'PA', name: 'Pará' },
      { uf: 'SP', name: 'São Paulo' },
    ];
  });

  it('accepts a registered Brazilian UF and rejects COMEX trade pseudo-codes', () => {
    expect(isCanonicalUf('PA')).toBe(true);
    expect(isCanonicalUf('SP')).toBe(true);
    // ND/EX/ZN/CB/RE/MC… are trade-origin pseudo-codes, NOT states — they must
    // not count toward the "UFs cobertas / 27" tally.
    expect(isCanonicalUf('ND')).toBe(false);
    expect(isCanonicalUf('EX')).toBe(false);
    expect(isCanonicalUf('ZN')).toBe(false);
  });

  it('is null/empty-safe and exposed on window for the reused views', () => {
    expect(isCanonicalUf(null)).toBe(false);
    expect(isCanonicalUf('')).toBe(false);
    expect(window.isCanonicalUf).toBe(isCanonicalUf);
  });
});
