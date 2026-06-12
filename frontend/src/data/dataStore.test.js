// dataStore.test.js — the pushdown query boundary the views load through.
// Covers the fetch → decorate → cache path, the per-convention cache key
// (currency/correction pick the deflated column server-side, so a change must
// re-fetch), and that an HTTP failure becomes status='error' with a message.

import { describe, expect, it, vi } from 'vitest';

function jsonRes(body, { ok = true, status = 200 } = {}) {
  return Promise.resolve({ ok, status, json: () => Promise.resolve(body) });
}

// load() also fires a /api/source-meta fetch (live provenance) alongside the
// snapshot; these tests assert on the SNAPSHOT query cadence, so count only those.
const snapCalls = (f) => f.mock.calls.filter((c) => String(c[0]).includes('/snapshot')).length;
const metaCalls = (f) => f.mock.calls.filter((c) => String(c[0]).includes('/source-meta')).length;

// A contract-complete BancoSnapshot (the shape assertSnapshotShape requires).
function validSnap(over = {}) {
  return { products: [], productTS: {}, overviewTS: [], ufData: [], quality: [], ...over };
}

async function loadStore(fetchImpl) {
  globalThis.fetch = fetchImpl;
  vi.resetModules();
  window.UF_DATA = [{ uf: 'PA', col: 7, row: 2, region: 'Norte', name: 'Pará' }];
  window.QUALITY_FLAGS = [{ id: 'OK', label: 'Sem ressalvas', color: 'var(--ok)' }];
  window.REGIONS = [{ id: 'N' }];
  await import('./dataStore.js');
  return window.dataStore;
}

describe('dataStore', () => {
  it('loads, decorates, and caches a snapshot', async () => {
    const snap = validSnap({ ufData: [{ uf: 'PA', value: 1 }], quality: [{ id: 'OK', count: 3 }] });
    const f = vi.fn(() => jsonRes(snap));
    const ds = await loadStore(f);

    expect(ds.status('ibge_pevs')).toBe('idle');
    const res = await ds.load('ibge_pevs');
    expect(res.status).toBe('ready');
    expect(ds.status('ibge_pevs')).toBe('ready');

    const data = ds.get('ibge_pevs');
    expect(data.table).toBe('gold_pevs_production'); // stamped from the table map
    expect(data.ufData[0]).toMatchObject({ col: 7, region: 'Norte', name: 'Pará' }); // decorated
    expect(data.quality[0]).toMatchObject({ label: 'Sem ressalvas', color: 'var(--ok)' });

    await ds.load('ibge_pevs'); // same banco + convention → served from cache
    expect(snapCalls(f)).toBe(1);
  });

  it('surfaces an HTTP error as status=error with a message', async () => {
    const f = vi.fn(() => jsonRes({}, { ok: false, status: 500 }));
    const ds = await loadStore(f);

    const res = await ds.load('ibge_pevs');
    expect(res.status).toBe('error');
    expect(ds.error('ibge_pevs')).toMatch(/500/);
    expect(ds.get('ibge_pevs')).toBe(null);
  });

  it('re-fetches under a different convention (currency drives the cache key)', async () => {
    const f = vi.fn(() => jsonRes(validSnap()));
    const ds = await loadStore(f);

    await ds.load('ibge_pevs'); // BRL|IPCA
    ds.setConventions({ currency: 'USD', correction: 'IPCA' });
    await ds.load('ibge_pevs'); // USD|IPCA → new key → fetch again

    expect(snapCalls(f)).toBe(2);
    const lastUrl = f.mock.calls
      .map((c) => String(c[0]))
      .filter((u) => u.includes('/snapshot'))
      .pop();
    expect(lastUrl).toContain('currency=USD');
  });

  it('rejects a drifted snapshot shape as status=error (no silent empty view)', async () => {
    // products is fine but productTS arrived as an array (a contract drift) —
    // every producer would read it and render blank; instead, fail loudly.
    const f = vi.fn(() => jsonRes(validSnap({ productTS: [] })));
    const ds = await loadStore(f);

    const res = await ds.load('ibge_pevs');
    expect(res.status).toBe('error');
    expect(ds.error('ibge_pevs')).toMatch(/contrato.*productTS/i);
    expect(ds.get('ibge_pevs')).toBe(null);
  });

  it('rejects a non-object snapshot payload (e.g. null / an error string)', async () => {
    const f = vi.fn(() => jsonRes(null));
    const ds = await loadStore(f);

    const res = await ds.load('ibge_pevs');
    expect(res.status).toBe('error');
    expect(ds.error('ibge_pevs')).toMatch(/inesperada/i);
  });

  it('loadMeta fetches /source-meta once and overlays it onto meta() (deduped)', async () => {
    // The freshness/about info-pages reach loadMeta directly (no snapshot load),
    // so it must fetch provenance on its own and never double-fetch a resolved one.
    const sm = {
      table: 'gold_pevs_production',
      yearStart: 1986,
      yearEnd: 2024,
      totalRows: 94771,
      lastRefreshLabel: '11 jun 2026 · 05:02 BRT',
    };
    const f = vi.fn((url) => jsonRes(String(url).includes('/source-meta') ? sm : validSnap()));
    const ds = await loadStore(f);
    window.bancoById = () => ({ prov: { refresh: 'fallback' } }); // registry fallback

    await ds.loadMeta('ibge_pevs');
    expect(metaCalls(f)).toBe(1);
    const m = ds.meta('ibge_pevs');
    expect(m.refresh).toBe('11 jun 2026 · 05:02 BRT'); // overlaid, not the fallback
    expect(m.coverage).toMatchObject({ yearEnd: 2024, totalRows: 94771 });

    await ds.loadMeta('ibge_pevs'); // already resolved → no second fetch
    expect(metaCalls(f)).toBe(1);
  });
});
