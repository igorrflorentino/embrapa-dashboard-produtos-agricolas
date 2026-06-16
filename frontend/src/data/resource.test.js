import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as resource from './resource.js';

const tick = () => new Promise((r) => setTimeout(r, 0));

describe('resource ensure() retry cap', () => {
  beforeEach(() => {
    resource.invalidate('k');
    resource.invalidate('k2');
    vi.restoreAllMocks();
  });

  it('stops auto-retrying after MAX_ATTEMPTS on a persistent failure', async () => {
    const fetchMock = vi.fn(() => Promise.reject(new Error('network down')));
    vi.stubGlobal('fetch', fetchMock);

    // Each ensure() models one render's synchronous producer call; a failure
    // notify()s → re-render → ensure() again. The cap (3) must bound the storm.
    for (let i = 0; i < 10; i++) {
      resource.ensure('k', () => '/api/x');
      await tick();
    }

    expect(fetchMock).toHaveBeenCalledTimes(3); // capped, not 10
    expect(resource.stateOf('k')).toBe('error');
  });

  it('invalidate() resets the cap so an explicit user retry can fetch again', async () => {
    const fetchMock = vi.fn(() => Promise.reject(new Error('down')));
    vi.stubGlobal('fetch', fetchMock);

    for (let i = 0; i < 5; i++) {
      resource.ensure('k2', () => '/api/y');
      await tick();
    }
    expect(fetchMock).toHaveBeenCalledTimes(3);

    resource.invalidate('k2'); // user-triggered retry resets attempts
    resource.ensure('k2', () => '/api/y');
    await tick();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it('a successful fetch makes the data available and does not retry', async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ v: 1 }) }));
    vi.stubGlobal('fetch', fetchMock);

    resource.invalidate('ok');
    resource.ensure('ok', () => '/api/ok');
    await tick();
    resource.ensure('ok', () => '/api/ok'); // already ready → no-op

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(resource.get('ok')).toEqual({ v: 1 });
  });
});

describe('resource ensure() generation token — no stale overwrite (M8)', () => {
  beforeEach(() => {
    resource.invalidate('g');
    vi.restoreAllMocks();
  });

  // A same-key reload can start a NEWER fetch while an OLDER one is in flight; the
  // older response must NOT clobber the newer one. We make the first fetch resolve
  // LAST so it would win without the generation guard.
  it('an OLDER in-flight response cannot overwrite a NEWER one', async () => {
    let resolveOld;
    const oldP = new Promise((res) => { resolveOld = res; });
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => oldP) // gen 1 — resolves later
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ v: 'new' }) })); // gen 2
    vi.stubGlobal('fetch', fetchMock);

    resource.ensure('g', () => '/api/g'); // gen 1, pending
    resource.invalidate('g'); // user-triggered reload bumps the generation
    resource.ensure('g', () => '/api/g'); // gen 2 — newer fetch
    await tick();
    expect(resource.get('g')).toEqual({ v: 'new' }); // gen 2 landed

    // Now the STALE gen-1 fetch finally resolves — it must be dropped.
    resolveOld({ ok: true, json: () => Promise.resolve({ v: 'old' }) });
    await tick();
    expect(resource.get('g')).toEqual({ v: 'new' }); // still the newer payload, not 'old'
  });

  it('a stale fetch that ERRORS does not clobber a newer ready value', async () => {
    let rejectOld;
    const oldP = new Promise((_res, rej) => { rejectOld = rej; });
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => oldP) // gen 1 — rejects later
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ v: 'fresh' }) }));
    vi.stubGlobal('fetch', fetchMock);

    resource.ensure('g', () => '/api/g'); // gen 1
    resource.invalidate('g');
    resource.ensure('g', () => '/api/g'); // gen 2
    await tick();
    expect(resource.stateOf('g')).toBe('ready');

    rejectOld(new Error('stale boom')); // gen-1 failure arrives late
    await tick();
    expect(resource.stateOf('g')).toBe('ready'); // not flipped to 'error'
    expect(resource.get('g')).toEqual({ v: 'fresh' });
  });
});
