// enrichment.test.js — the curation store's write paths (the highest-risk seam:
// it POSTs to the append-only writers). Covers the API⟕draft worklist join, the
// stage/unstage logic for BOTH axes (code-level + flow-market), the apply() →
// POST → invalidate lifecycle, and — the regression guard for the bug this PR
// fixes — that a failed write surfaces lastError() and KEEPS the draft.
//
// Strategy: mock global fetch (the real ./resource uses it), and vi.resetModules
// + re-import enrichment.js per test so each gets a fresh cache + draft.

import { describe, expect, it, vi } from 'vitest';

const WORKLIST = {
  rows: [
    { source: 'ibge_pevs', code: '1.1', name: 'Mandioca', commodity: 'mandioca', commodity_name: 'Mandioca', level: null },
    { source: 'mdic_comex', code: '4407', name: 'Madeira serrada', commodity: 'madeira', commodity_name: 'Madeira', level: 'processada' },
  ],
};

const FLOW_WL = {
  customs: ['C03', 'C04'],
  flows: [{ code: 'M', label: 'Importação' }, { code: 'X', label: 'Exportação' }],
  cells: [
    { customs_code: 'C03', flow_code: 'X', value_usd: 3e9, market: null },
    { customs_code: 'C04', flow_code: 'M', value_usd: 1e9, market: 'consumo' },
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

// GET-only fetch that serves the two worklists; everything else 404s.
function worklistFetch() {
  return vi.fn((url) => {
    if (url.includes('/curation/flow-worklist')) return jsonRes(FLOW_WL);
    if (url.includes('/curation/worklist')) return jsonRes(WORKLIST);
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
    const e = await load(worklistFetch());
    // The complete matrix is available immediately — ALL canonical regimes (16) and
    // ALL ten official UN Comtrade flow codes, so it is ready for any data
    // granularity even before the flow-worklist resolves. regimes() kicks the fetch.
    expect(e.regimes().length).toBe(16);
    expect(e.flowTypes().map((f) => f.id)).toEqual(['M', 'X', 'DX', 'FM', 'MIP', 'MOP', 'RM', 'RX', 'XIP', 'XOP']);
    // Headers carry the code in parentheses, like the customs rows.
    expect(e.flowTypes().find((f) => f.id === 'M').term).toBe('Importação (M)');
    expect(e.flowTypes().find((f) => f.id === 'MIP').term).toBe('Importação para aperfeiçoamento ativo (MIP)');
    await vi.waitFor(() => expect(e.pairMarket('C04', 'M')).toBe('consumo')); // data loaded

    // Regimes that move value sort to the top; the zero-value canonical tail follows.
    expect(e.regimes().slice(0, 2).map((r) => r.id)).toEqual(['C03', 'C04']); // C03 ($3bi) > C04 ($1bi)
    expect(e.regimes().length).toBe(16); // still complete after the data lands
    expect(e.pairMarket('C03', 'X')).toBe(null);
    expect(e.pairValueLabel('C03', 'X')).toBe('US$ 3.0 bi');

    e.setPair('C03', 'X', 'processamento');
    expect(e.pendingCount()).toBe(1);
    expect(e.pairMarket('C03', 'X')).toBe('processamento');

    e.setPair('C04', 'M', 'consumo'); // matches the persisted market → no stage
    expect(e.pendingCount()).toBe(1);
  });
});

describe('enrichment — apply() commit lifecycle', () => {
  it('POSTs each staged edit, clears the drafts, and invalidates → refetch', async () => {
    const posts = [];
    let worklistGets = 0;
    let worklistPayload = WORKLIST;
    const fetchImpl = vi.fn((url, opts) => {
      if (url.includes('/curation/flow-worklist')) return jsonRes(FLOW_WL);
      if (url.includes('/curation/worklist')) {
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
    await vi.waitFor(() => expect(e.pairMarket('C04', 'M')).toBe('consumo')); // flow-worklist loaded
    expect(worklistGets).toBe(1);

    e.setCode('ibge_pevs:1.1', { level: 'bruta' });
    e.setPair('C03', 'X', 'processamento');
    expect(e.pendingCount()).toBe(2);

    // the server now reports the code as classified (proves the refetch is live)
    worklistPayload = { rows: WORKLIST.rows.map((r) => (r.code === '1.1' ? { ...r, level: 'bruta' } : r)) };

    let done = false;
    e.apply(() => { done = true; });
    await vi.waitFor(() => expect(e.pendingCount()).toBe(0));

    expect(done).toBe(true);
    expect(e.lastError()).toBe(null);
    const codePost = posts.find((p) => p.url.includes('/curation/code-level')).body;
    const flowPost = posts.find((p) => p.url.includes('/curation/flow-market')).body;
    expect(codePost).toMatchObject({ source: 'ibge_pevs', code: '1.1', level: 'bruta' });
    expect(flowPost).toMatchObject({ customs_code: 'C03', flow_code: 'X', market: 'processamento' });
    // each staged edit carries an idempotency key (a string), distinct per edit
    expect(typeof codePost.change_id).toBe('string');
    expect(codePost.change_id).not.toBe(flowPost.change_id);

    // invalidate → the next worklist() re-fetches and reflects the new server state
    await vi.waitFor(() => {
      const row = e.worklist().find((r) => r.id === 'ibge_pevs:1.1');
      expect(row && row.level).toBe('bruta');
    });
    expect(worklistGets).toBe(2);
  });

  it('surfaces a write failure and KEEPS the draft, then discard() clears it (the silent-401 regression)', async () => {
    const fetchImpl = vi.fn((url, opts) => {
      if (url.includes('/curation/worklist')) return jsonRes(WORKLIST);
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

  it('on partial failure drops only the landed edit and keeps the failed one', async () => {
    // code-level POST lands; flow-market POST 401s.
    const fetchImpl = vi.fn((url, opts) => {
      if (url.includes('/curation/flow-worklist')) return jsonRes(FLOW_WL);
      if (url.includes('/curation/worklist')) return jsonRes(WORKLIST);
      if (opts && opts.method === 'POST') {
        return url.includes('/curation/flow-market')
          ? jsonRes({}, { ok: false, status: 401 })
          : jsonRes({});
      }
      return jsonRes({}, { ok: false, status: 404 });
    });
    const e = await load(fetchImpl);
    await vi.waitFor(() => expect(e.worklist().length).toBe(2));
    await vi.waitFor(() => expect(e.pairMarket('C04', 'M')).toBe('consumo')); // flow-worklist loaded

    e.setCode('ibge_pevs:1.1', { level: 'bruta' }); // will land
    e.setPair('C03', 'X', 'processamento'); // will 401
    expect(e.pendingCount()).toBe(2);

    e.apply();
    await vi.waitFor(() => expect(e.isCommitting()).toBe(false));

    expect(e.lastError()).toBe('HTTP 401');
    expect(e.pendingCount()).toBe(1); // only the failed flow edit remains staged
    expect(e.pairMarket('C03', 'X')).toBe('processamento'); // flow draft kept for retry

    e.setPair('C03', 'X', 'consumo'); // a fresh edit clears the surfaced error
    expect(e.lastError()).toBe(null);
  });

  it('reuses the change_id across a retry but mints a fresh one per staging', async () => {
    const posts = [];
    let postCalls = 0;
    const fetchImpl = vi.fn((url, opts) => {
      if (url.includes('/curation/flow-worklist')) return jsonRes(FLOW_WL);
      if (url.includes('/curation/worklist')) return jsonRes(WORKLIST);
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
