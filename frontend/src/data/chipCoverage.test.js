// chipCoverage.test.js — the filter-chip coverage resolution (FINDING #2).
// On first load / banco switch, before the active banco's snapshot lands,
// applyFilters returns the PEVS synthetic globals (12 products, 1986–2024). The
// chips must instead show the ACTIVE banco's real product count + data range.

import { describe, expect, it } from 'vitest';

import { resolveChipCoverage } from './chipCoverage.js';

// applyFilters fallback shape when the snapshot is cold (PEVS synthetic globals).
const PEVS_FALLBACK = { productsTotal: 12, yearStart: 1986, yearEnd: 2024 };

describe('resolveChipCoverage', () => {
  it('uses the LIVE source-meta coverage when the snapshot is not loaded yet', () => {
    // COMEX: real catalog = 5 products, range 1997–2026. The chip must NOT show the
    // PEVS default the cold applyFilters returned.
    const out = resolveChipCoverage({
      snapLoaded: false,
      applied: PEVS_FALLBACK,
      meta: { coverage: { productsTotal: 5, yearStart: 1997, yearEnd: 2026 } },
      hasDateSel: false,
    });
    expect(out).toEqual({ total: 5, yearStart: 1997, yearEnd: 2026 });
  });

  it('falls back to the banco registry prov when source-meta has not resolved', () => {
    const out = resolveChipCoverage({
      snapLoaded: false,
      applied: PEVS_FALLBACK,
      meta: { coverage: null, prov: { productsTotal: 5, yearStart: 1997, yearEnd: 2024 } },
      hasDateSel: false,
    });
    expect(out).toEqual({ total: 5, yearStart: 1997, yearEnd: 2024 });
  });

  it('prefers source-meta coverage over the registry prov when both exist', () => {
    const out = resolveChipCoverage({
      snapLoaded: false,
      applied: PEVS_FALLBACK,
      meta: {
        coverage: { productsTotal: 5, yearStart: 1997, yearEnd: 2026 }, // live Gold
        prov: { productsTotal: 5, yearStart: 1997, yearEnd: 2024 }, // frozen registry
      },
      hasDateSel: false,
    });
    expect(out.yearEnd).toBe(2026); // the live value, not the registry 2024
  });

  it('trusts applyFilters once the snapshot IS loaded (real banco values)', () => {
    // Snapshot present → applyFilters already reflects the banco; meta is ignored.
    const out = resolveChipCoverage({
      snapLoaded: true,
      applied: { productsTotal: 3, yearStart: 1986, yearEnd: 2024 }, // real PEVS
      meta: { coverage: { productsTotal: 999, yearStart: 1, yearEnd: 2 } },
      hasDateSel: false,
    });
    expect(out).toEqual({ total: 3, yearStart: 1986, yearEnd: 2024 });
  });

  it('keeps an explicit date selection (deep link) instead of the banco span', () => {
    // hasDateSel → applyFilters already carries the user window; do not override it.
    const out = resolveChipCoverage({
      snapLoaded: false,
      applied: { productsTotal: 12, yearStart: 2000, yearEnd: 2010 }, // user window
      meta: { coverage: { productsTotal: 5, yearStart: 1997, yearEnd: 2026 } },
      hasDateSel: true,
    });
    expect(out.yearStart).toBe(2000); // selection preserved
    expect(out.yearEnd).toBe(2010);
    expect(out.total).toBe(5); // product total still corrected to the banco's
  });

  it('degrades to the applied values when no banco metadata is available', () => {
    const out = resolveChipCoverage({
      snapLoaded: false,
      applied: PEVS_FALLBACK,
      meta: null,
      hasDateSel: false,
    });
    expect(out).toEqual({ total: 12, yearStart: 1986, yearEnd: 2024 });
  });
});
