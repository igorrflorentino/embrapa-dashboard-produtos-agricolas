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
