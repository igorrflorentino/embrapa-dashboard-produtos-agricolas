// producers.test.js — the crosswalk catalog producer that feeds the multi-source
// commodity picker. The cross/* endpoints key on the commodity_id SLUG, so the
// picker must offer slugs (from /api/catalog), not PEVS product codes — this
// guards that mapping + the sync-over-async loading shape (cold → [], hot → list).

import { describe, expect, it, vi } from 'vitest';

const tick = () => new Promise((r) => setTimeout(r, 0));

function jsonRes(body) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
}

// /api/catalog shape: { commodity_id -> {id, name, pevs[], comex[], comtrade[]} }.
const CATALOG = {
  castanha_caju: { id: 'castanha_caju', name: 'Castanha de caju', pevs: ['49101'], comex: ['0801'], comtrade: ['0801'] },
  acai: { id: 'acai', name: 'Açaí', pevs: ['40102'], comex: ['0810'], comtrade: ['0810'] },
};

// Fresh resource+producers modules per load so the module-level resource cache
// (and window.crossCatalog) start clean; fetch is reassigned directly (matches
// the other data-layer suites — restoreMocks doesn't track a direct assignment).
async function loadProducers(fetchImpl) {
  globalThis.fetch = fetchImpl;
  vi.resetModules();
  await import('./producers.js');
  return window.crossCatalog;
}

describe('crossCatalog', () => {
  it('returns [] while cold and kicks off exactly one /api/catalog fetch', async () => {
    const f = vi.fn(() => jsonRes(CATALOG));
    const crossCatalog = await loadProducers(f);

    expect(crossCatalog()).toEqual([]); // cold cache → empty, no crash
    expect(f).toHaveBeenCalledTimes(1);
    expect(f.mock.calls[0][0]).toContain('/api/catalog');

    crossCatalog(); // a re-render before the fetch resolves must not re-fetch
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('maps the catalog to slug-keyed {code,name} options, sorted pt-BR by name', async () => {
    const f = vi.fn(() => jsonRes(CATALOG));
    const crossCatalog = await loadProducers(f);

    crossCatalog(); // kick the fetch
    await tick();
    const opts = crossCatalog(); // cache hot now

    // code is the commodity_id SLUG the cross/* endpoints expect (not a PEVS code).
    expect(opts).toEqual([
      { code: 'acai', name: 'Açaí' },
      { code: 'castanha_caju', name: 'Castanha de caju' },
    ]);
  });
});
