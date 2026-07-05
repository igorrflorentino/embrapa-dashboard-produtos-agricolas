// enrichment.test.js — the curation store's write path for BOTH editable axes (the
// highest-risk seam: it POSTs to the append-only writers). Covers the API⟕draft worklist
// join, the stage/unstage logic for code-level AND the customs×flow market matrix, the
// apply() → POST → invalidate lifecycle, and the regression guard that a failed write
// surfaces lastError() and KEEPS the draft.
//
// Strategy: mock global fetch (the real ./resource uses it), and vi.resetModules
// + re-import enrichment.js per test so each gets a fresh cache + draft.

import { describe, expect, it, vi } from 'vitest';

const WORKLIST = {
  rows: [
    { source: 'ibge_pevs', code: '1.1', name: 'Mandioca', commodity: 'mandioca', agrupamento_nome: 'Mandioca', level: null },
    { source: 'mdic_comex', code: '4407', name: 'Madeira serrada', commodity: 'madeira', agrupamento_nome: 'Madeira', level: 'processada' },
  ],
};

// Flow-market matrix payload — flow_code is the NORMALIZED token (export/import/…),
// matching serving_comtrade_annual.flow (NOT the raw UN code X/M).
const FLOW_WL = {
  customs: ['C03', 'C04'],
  flows: [{ code: 'import', label: 'Importação' }, { code: 'export', label: 'Exportação' }],
  cells: [
    { customs_code: 'C03', flow_code: 'export', value_usd: 3e9, market: null },
    { customs_code: 'C04', flow_code: 'import', value_usd: 1e9, market: 'consumo' },
  ],
  classified: 1,
  total: 2,
};

function jsonRes(body, { ok = true, status = 200 } = {}) {
  return Promise.resolve({ ok, status, json: () => Promise.resolve(body) });
}

// Load a fresh enrichment store wired to the given fetch implementation.
async function load(fetchImpl) {
  globalThis.fetch = fetchImpl;
  vi.resetModules();
  await import('./enrichment.js');
  return window.enrichment;
}

// GET-only fetch that serves the code worklist; everything else 404s.
function worklistFetch() {
  return vi.fn((url) => {
    if (url.includes('/attributes/worklist')) return jsonRes(WORKLIST);
    return jsonRes({}, { ok: false, status: 404 });
  });
}

// GET-only fetch that serves BOTH worklists (code + flow matrix); everything else 404s.
function bothWorklistsFetch() {
  return vi.fn((url) => {
    if (url.includes('/attributes/flow-worklist')) return jsonRes(FLOW_WL);
    if (url.includes('/attributes/worklist')) return jsonRes(WORKLIST);
    return jsonRes({}, { ok: false, status: 404 });
  });
}

describe('enrichment — code-level worklist', () => {
  it('joins the Gold code universe with the classification log', async () => {
    const e = await load(worklistFetch());
    expect(e.worklist()).toEqual([]); // cold: the fetch was just kicked (sync-over-async)
    await vi.waitFor(() => expect(e.worklist().length).toBe(2));

    const rows = e.worklist();
    expect(rows.find((r) => r.id === 'ibge_pevs:1.1')).toMatchObject({
      group: 'mandioca', desc: 'Mandioca', level: null, status: 'a-classificar',
    });
    expect(rows.find((r) => r.id === 'mdic_comex:4407')).toMatchObject({
      level: 'processada', status: 'classificado',
    });
  });

  it('stages a level edit and unstages when it returns to the API level', async () => {
    const e = await load(worklistFetch());
    await vi.waitFor(() => expect(e.worklist().length).toBe(2));

    e.setCode('mdic_comex:4407', { level: 'bruta' }); // API level is 'processada'
    expect(e.pendingCount()).toBe(1);
    expect(e.worklist().find((r) => r.id === 'mdic_comex:4407').level).toBe('bruta');

    e.setCode('mdic_comex:4407', { level: 'processada' }); // back to API → unstaged
    expect(e.pendingCount()).toBe(0);

    e.setCode('ibge_pevs:1.1', { level: '' }); // empty level is ignored by the guard
    expect(e.pendingCount()).toBe(0);
  });
});

describe('enrichment — flow-market matrix', () => {
  it('exposes the COMPLETE customs×flow grid (material regimes first) and stages pair edits', async () => {
    const e = await load(bothWorklistsFetch());
    // The complete matrix is available immediately — ALL 16 canonical regimes and ALL ten
    // official flow tokens — so it is ready for any granularity before the fetch resolves.
    // regimes() kicks the flow-worklist fetch.
    expect(e.regimes().length).toBe(16);
    expect(e.flowTypes().map((f) => f.id)).toEqual([
      'import', 'export', 'national-export', 'foreign-import', 'import-inward-processing',
      'import-outward-processing', 're-import', 're-export', 'export-inward-processing',
      'export-outward-processing',
    ]);
    expect(e.flowTypes().find((f) => f.id === 'import').term).toBe('Importação (import)');

    await vi.waitFor(() => expect(e.pairMarket('C04', 'import')).toBe('consumo')); // data loaded
    // Regimes that move value sort to the top; the zero-value canonical tail follows.
    expect(e.regimes().slice(0, 2).map((r) => r.id)).toEqual(['C03', 'C04']); // C03 ($3bi) > C04 ($1bi)
    expect(e.regimes().length).toBe(16); // still complete after the data lands
    expect(e.pairMarket('C03', 'export')).toBe(null);
    expect(e.pairValueLabel('C03', 'export')).toBe('US$ 3.0 bi'); // materiality shown per cell

    // stage a pair edit, then unstage by matching the persisted value
    e.setPair('C03', 'export', 'processamento');
    expect(e.pendingCount()).toBe(1);
    expect(e.pairMarket('C03', 'export')).toBe('processamento');
    e.setPair('C04', 'import', 'consumo'); // matches the persisted market → no stage
    expect(e.pendingCount()).toBe(1);

    // stats count over the FULL grid (16×10) and the classified pairs
    const s = e.stats();
    expect(s.flowsTotal).toBe(160);
    expect(s.flowsClassified).toBe(2); // C04×import persisted + C03×export staged
  });
});

describe('enrichment — apply() commit lifecycle', () => {
  it('POSTs BOTH a code-level and a flow-market edit with distinct change_ids', async () => {
    const posts = [];
    const fetchImpl = vi.fn((url, opts) => {
      if (url.includes('/attributes/flow-worklist')) return jsonRes(FLOW_WL);
      if (url.includes('/attributes/worklist')) return jsonRes(WORKLIST);
      if (opts && opts.method === 'POST') {
        posts.push({ url, body: JSON.parse(opts.body) });
        return jsonRes({});
      }
      return jsonRes({}, { ok: false, status: 404 });
    });
    const e = await load(fetchImpl);
    await vi.waitFor(() => expect(e.worklist().length).toBe(2));
    await vi.waitFor(() => expect(e.pairMarket('C04', 'import')).toBe('consumo'));

    e.setCode('ibge_pevs:1.1', { level: 'bruta' });
    e.setPair('C03', 'export', 'processamento');
    expect(e.pendingCount()).toBe(2);

    e.apply();
    await vi.waitFor(() => expect(e.pendingCount()).toBe(0));

    const codePost = posts.find((p) => p.url.includes('/attributes/code-level')).body;
    const flowPost = posts.find((p) => p.url.includes('/attributes/flow-market')).body;
    expect(codePost).toMatchObject({ source: 'ibge_pevs', code: '1.1', level: 'bruta' });
    expect(flowPost).toMatchObject({ customs_code: 'C03', flow_code: 'export', market: 'processamento' });
    expect(codePost.change_id).not.toBe(flowPost.change_id); // independent idempotency keys
  });


  it('POSTs each staged edit, clears the draft, and invalidates → refetch', async () => {
    const posts = [];
    let worklistGets = 0;
    let worklistPayload = WORKLIST;
    const fetchImpl = vi.fn((url, opts) => {
      if (url.includes('/attributes/worklist')) {
        worklistGets += 1;
        return jsonRes(worklistPayload);
      }
      if (opts && opts.method === 'POST') {
        posts.push({ url, body: JSON.parse(opts.body) });
        return jsonRes({});
      }
      return jsonRes({}, { ok: false, status: 404 });
    });
    const e = await load(fetchImpl);
    await vi.waitFor(() => expect(e.worklist().length).toBe(2));
    expect(worklistGets).toBe(1);

    e.setCode('ibge_pevs:1.1', { level: 'bruta' });
    expect(e.pendingCount()).toBe(1);

    // the server now reports the code as classified (proves the refetch is live)
    worklistPayload = { rows: WORKLIST.rows.map((r) => (r.code === '1.1' ? { ...r, level: 'bruta' } : r)) };

    let done = false;
    e.apply(() => { done = true; });
    await vi.waitFor(() => expect(e.pendingCount()).toBe(0));

    expect(done).toBe(true);
    expect(e.lastError()).toBe(null);
    const codePost = posts.find((p) => p.url.includes('/attributes/code-level')).body;
    expect(codePost).toMatchObject({ source: 'ibge_pevs', code: '1.1', level: 'bruta' });
    // the staged edit carries an idempotency key (a string)
    expect(typeof codePost.change_id).toBe('string');

    // invalidate → the next worklist() re-fetches and reflects the new server state
    await vi.waitFor(() => {
      const row = e.worklist().find((r) => r.id === 'ibge_pevs:1.1');
      expect(row && row.level).toBe('bruta');
    });
    expect(worklistGets).toBe(2);
  });

  it('surfaces a write failure and KEEPS the draft, then discard() clears it (the silent-401 regression)', async () => {
    const fetchImpl = vi.fn((url, opts) => {
      if (url.includes('/attributes/worklist')) return jsonRes(WORKLIST);
      if (opts && opts.method === 'POST') return jsonRes({}, { ok: false, status: 401 });
      return jsonRes({}, { ok: false, status: 404 });
    });
    const e = await load(fetchImpl);
    await vi.waitFor(() => expect(e.worklist().length).toBe(2));

    e.setCode('ibge_pevs:1.1', { level: 'bruta' });
    e.apply();
    await vi.waitFor(() => expect(e.isCommitting()).toBe(false));

    expect(e.pendingCount()).toBe(1); // draft retained so the user can retry
    expect(e.lastError()).toBe('HTTP 401'); // surfaced, not swallowed

    e.discard(); // clears both the draft AND the surfaced error
    expect(e.lastError()).toBe(null);
    expect(e.pendingCount()).toBe(0);
  });

  it('reuses the change_id across a retry but mints a fresh one per staging', async () => {
    const posts = [];
    let postCalls = 0;
    const fetchImpl = vi.fn((url, opts) => {
      if (url.includes('/attributes/worklist')) return jsonRes(WORKLIST);
      if (opts && opts.method === 'POST') {
        postCalls += 1;
        posts.push(JSON.parse(opts.body));
        // first attempt fails (a timeout that may have landed); the retry succeeds
        return postCalls === 1 ? jsonRes({}, { ok: false, status: 503 }) : jsonRes({});
      }
      return jsonRes({}, { ok: false, status: 404 });
    });
    const e = await load(fetchImpl);
    await vi.waitFor(() => expect(e.worklist().length).toBe(2));

    e.setCode('ibge_pevs:1.1', { level: 'bruta' });
    e.apply();
    await vi.waitFor(() => expect(e.isCommitting()).toBe(false));
    expect(e.pendingCount()).toBe(1); // failed → draft kept for retry

    e.apply(); // retry the SAME staged edit
    await vi.waitFor(() => expect(e.pendingCount()).toBe(0)); // now lands

    expect(posts).toHaveLength(2);
    expect(posts[0].change_id).toBeTruthy();
    expect(posts[1].change_id).toBe(posts[0].change_id); // retry reuses the key → backend can dedupe
    const priorKey = posts[0].change_id;

    // a fresh staging of the same row is a NEW logical edit → a new key (always lands)
    e.setCode('ibge_pevs:1.1', { level: 'bruta' });
    e.apply();
    await vi.waitFor(() => expect(e.pendingCount()).toBe(0));
    expect(posts).toHaveLength(3);
    expect(posts[2].change_id).not.toBe(priorKey);
  });
});
