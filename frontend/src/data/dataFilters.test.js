// dataFilters.test.js — applyFilters (proto/dataFilters.js) is the single seam
// the geo/value views read filtered datasets through. These lock the F1.5 fix:
// a product basket must NOT fabricate the per-UF / per-region territorial split
// by scaling every state uniformly by selected/all (there is no per-product × UF
// grain in the snapshot). The real state totals must pass through unchanged and
// the honest `notFilteredByBasket` flag must be raised so the views can say so.

import { beforeEach, describe, expect, it, vi } from 'vitest';

// applyFilters reads the active banco's snapshot from window.dataStore.get and a
// few registry globals. Stub the minimum so the IIFE runs in isolation (no full
// proto boot). Each test reloads the module so the IIFE re-binds window.applyFilters.
const SNAP = {
  products: [
    { code: 'A', name: 'Açaí', unit: 't', family: 'mass' },
    { code: 'B', name: 'Babaçu', unit: 't', family: 'mass' },
    { code: 'C', name: 'Carnaúba', unit: 't', family: 'mass' },
  ],
  productTS: {
    A: [{ y: 2020, v: 30, q: 3, family: 'mass' }, { y: 2021, v: 33, q: 3.3, family: 'mass' }],
    B: [{ y: 2020, v: 20, q: 2, family: 'mass' }, { y: 2021, v: 22, q: 2.2, family: 'mass' }],
    C: [{ y: 2020, v: 10, q: 1, family: 'mass' }, { y: 2021, v: 11, q: 1.1, family: 'mass' }],
  },
  overviewTS: [{ y: 2020, v: 0.06 }, { y: 2021, v: 0.066 }],
  ufData: [
    { uf: 'PA', name: 'Pará', region: 'N', value: 100, q_mass: 50, q_vol: 0 },
    { uf: 'RS', name: 'Rio Grande do Sul', region: 'S', value: 40, q_mass: 20, q_vol: 0 },
  ],
  // Per-(UF, year) history backing the heatmap AND the map's true-year derivation.
  // ufData above is the latest-year scope (2021 here); ufYearly carries both years.
  ufYearly: [
    { year: 2020, uf: 'PA', name: 'Pará', region: 'N', value: 90, q_mass: 45, q_vol: 0 },
    { year: 2021, uf: 'PA', name: 'Pará', region: 'N', value: 100, q_mass: 50, q_vol: 0 },
    { year: 2020, uf: 'RS', name: 'Rio Grande do Sul', region: 'S', value: 36, q_mass: 18, q_vol: 0 },
    { year: 2021, uf: 'RS', name: 'Rio Grande do Sul', region: 'S', value: 40, q_mass: 20, q_vol: 0 },
  ],
  quality: [{ id: 'OK', count: 9 }],
  qualityTs: [],
  topMunis: [],
  regions: [{ id: 'N' }, { id: 'S' }],
};

async function loadApplyFilters() {
  vi.resetModules();
  window.dataStore = { get: () => SNAP };
  window.REGIONS = SNAP.regions;
  window.VIZ_SCALE = ['var(--viz-1)'];
  window.VALUE_PRESETS = [];
  window.MUNI_PICKER_NAMES = new Set();
  window.snapshotFor = () => null;
  await import('../proto/dataFilters.js');
  return window.applyFilters;
}

describe('applyFilters — no fabricated geographic split under a basket (F1.5)', () => {
  beforeEach(() => {
    // clean any prior window.applyFilters binding
    delete window.applyFilters;
  });

  it('serves the REAL per-UF totals unchanged when a basket narrows products', async () => {
    const applyFilters = await loadApplyFilters();
    // 1 of 3 products selected — the OLD code scaled every UF by 1/3.
    const f = applyFilters({ basket: ['A'] }, 'ibge_pevs');

    const pa = f.ufData.find((u) => u.uf === 'PA');
    // value/q_mass are the REAL state totals, NOT 100/3 ≈ 33.3.
    expect(pa.value).toBe(100);
    expect(pa.q_mass).toBe(50);
    expect(f.notFilteredByBasket).toBe(true); // honest flag raised
  });

  it('does NOT raise the flag when all products are selected (no narrowing)', async () => {
    const applyFilters = await loadApplyFilters();
    const f = applyFilters({ basket: ['A', 'B', 'C'] }, 'ibge_pevs');
    expect(f.notFilteredByBasket).toBe(false);
    expect(f.ufData.find((u) => u.uf === 'PA').value).toBe(100);
  });

  it('does NOT raise the flag when no basket filter is applied', async () => {
    const applyFilters = await loadApplyFilters();
    const f = applyFilters({}, 'ibge_pevs');
    expect(f.notFilteredByBasket).toBe(false);
  });

  it('still applies the exact STATE filter (real narrowing) on ufData', async () => {
    const applyFilters = await loadApplyFilters();
    const f = applyFilters({ states: ['PA'] }, 'ibge_pevs');
    expect(f.ufData.map((u) => u.uf)).toEqual(['PA']); // RS dropped
    expect(f.ufData[0].value).toBe(100); // unscaled
  });

  it('region totals derive from the REAL (unscaled) ufData', async () => {
    const applyFilters = await loadApplyFilters();
    const f = applyFilters({ basket: ['A'] }, 'ibge_pevs');
    const north = f.regionData.find((r) => r.id === 'N');
    expect(north.value).toBe(100); // = PA total, not PA/3
  });
});

describe('applyFilters — map year follows the DATA, not yearEnd (FINDING #1)', () => {
  beforeEach(() => { delete window.applyFilters; });

  it('derives ufLatestYear from the max UF year IN the window (not yearEnd)', async () => {
    const applyFilters = await loadApplyFilters();
    // endDate runs to 2025 but the latest UF rows stop at 2021 → the map's year is
    // the DATA year (2021), flagged partial because it falls short of yearEnd.
    const f = applyFilters({ startDate: '2020-01-01', endDate: '2025-01-01' }, 'ibge_pevs');
    expect(f.ufLatestYear).toBe(2021);
    expect(f.ufYearPartial).toBe(true);
    expect(f.yearEnd).toBe(2025); // yearEnd is untouched — only the MAP label changes
  });

  it('is not partial when the window end coincides with the latest UF year', async () => {
    const applyFilters = await loadApplyFilters();
    const f = applyFilters({ startDate: '2020-01-01', endDate: '2021-12-01' }, 'ibge_pevs');
    expect(f.ufLatestYear).toBe(2021);
    expect(f.ufYearPartial).toBe(false);
  });

  it('respects the window: a window ending in 2020 yields the 2020 map year', async () => {
    const applyFilters = await loadApplyFilters();
    const f = applyFilters({ startDate: '2020-01-01', endDate: '2020-12-01' }, 'ibge_pevs');
    expect(f.ufLatestYear).toBe(2020);
    expect(f.ufYearPartial).toBe(false);
  });

  it('falls back to yearEnd (never partial) when ufYearly is absent', async () => {
    vi.resetModules();
    delete window.applyFilters;
    // A snapshot without ufYearly (synthetic / older payload).
    const noYearly = { ...SNAP };
    delete noYearly.ufYearly;
    window.dataStore = { get: () => noYearly };
    window.REGIONS = SNAP.regions;
    window.VIZ_SCALE = ['var(--viz-1)'];
    window.VALUE_PRESETS = [];
    window.MUNI_PICKER_NAMES = new Set();
    window.snapshotFor = () => null;
    await import('../proto/dataFilters.js');
    const f = window.applyFilters({ startDate: '2020-01-01', endDate: '2025-01-01' }, 'ibge_pevs');
    expect(f.ufLatestYear).toBe(f.yearEnd); // 2025
    expect(f.ufYearPartial).toBe(false); // no data to prove a shortfall → don't cry partial
  });
});

describe('applyFilters — ufDataFull is the ALL-TIME UF universe (heads-up #1)', () => {
  beforeEach(() => { delete window.applyFilters; });

  it('counts every UF seen across years, not just the latest year', async () => {
    vi.resetModules();
    delete window.applyFilters;
    // A sparse-trade scenario: the LATEST year (2021, = ufData scope) has ONE UF,
    // but an earlier year had a second. The denominator must reflect both.
    const sparse = {
      ...SNAP,
      ufData: [{ uf: 'PA', name: 'Pará', region: 'N', value: 100, q_mass: 50, q_vol: 0 }],
      ufYearly: [
        { year: 2020, uf: 'PA', name: 'Pará', region: 'N', value: 90, q_mass: 45, q_vol: 0 },
        { year: 2020, uf: 'RS', name: 'Rio Grande do Sul', region: 'S', value: 36, q_mass: 18, q_vol: 0 },
        { year: 2021, uf: 'PA', name: 'Pará', region: 'N', value: 100, q_mass: 50, q_vol: 0 },
      ],
    };
    window.dataStore = { get: () => sparse };
    window.REGIONS = SNAP.regions;
    window.VIZ_SCALE = ['var(--viz-1)'];
    window.VALUE_PRESETS = [];
    window.MUNI_PICKER_NAMES = new Set();
    window.snapshotFor = () => null;
    await import('../proto/dataFilters.js');
    const f = window.applyFilters({ startDate: '2020-01-01', endDate: '2021-12-01' }, 'ibge_pevs');
    // ufData (latest year) has 1 UF, but the all-time universe has 2 (PA + RS).
    expect(f.ufData.length).toBe(1);
    expect(f.ufDataFull.map((u) => u.uf).sort()).toEqual(['PA', 'RS']);
  });

  it('falls back to the latest-year UF list when ufYearly is absent', async () => {
    const applyFilters = await loadApplyFilters();
    const noYearly = { ...SNAP };
    delete noYearly.ufYearly;
    window.dataStore = { get: () => noYearly };
    const f = applyFilters({}, 'ibge_pevs');
    expect(f.ufDataFull.map((u) => u.uf).sort()).toEqual(['PA', 'RS']);
  });
});
