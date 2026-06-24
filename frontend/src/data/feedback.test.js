// feedback.test.js — the data layer for the "Reportar problema" channel.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

function jsonRes(body, { ok = true, status = 200 } = {}) {
  return Promise.resolve({ ok, status, json: () => Promise.resolve(body) });
}

beforeEach(() => {
  vi.resetModules(); // re-run feedback.js so it re-assigns window.postFeedback
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe('postFeedback', () => {
  it('POSTs the payload to /api/feedback and returns the echoed row', async () => {
    const f = vi.fn(() => jsonRes({ feedback_id: 'abc', submitted_by: 'user@embrapa.br', category: 'bug' }));
    globalThis.fetch = f;
    await import('./feedback.js');

    const result = await window.postFeedback({ category: 'bug', message: 'oi' });

    expect(result.submitted_by).toBe('user@embrapa.br');
    expect(f).toHaveBeenCalledWith('/api/feedback', expect.objectContaining({ method: 'POST' }));
    const sent = JSON.parse(f.mock.calls[0][1].body);
    expect(sent).toMatchObject({ category: 'bug', message: 'oi' });
  });

  it('rejects with the server error message on a non-ok response', async () => {
    globalThis.fetch = vi.fn(() => jsonRes({ error: 'message is required' }, { ok: false, status: 400 }));
    await import('./feedback.js');

    await expect(window.postFeedback({ message: '' })).rejects.toThrow('message is required');
  });
});
