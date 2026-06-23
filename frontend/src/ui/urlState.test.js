// urlState.test.js — the shared deep-link codec contract (urlState.js). Pins the
// encode/decode round-trip so a share/cite link reproduces the exact panel state.
// Regression guard for the RVC-1 audit finding (the v1.5.2 sub-UF/município geo
// dims were silently dropped from share links) and the urlDecodeNum NaN guard.

import { describe, expect, it } from 'vitest';

import './urlState.js';

describe('urlState — array codec', () => {
  it('encodes null→"" (all), []→"-" (explicit none), subset→csv', () => {
    expect(window.urlEncodeArr(null)).toBe('');
    expect(window.urlEncodeArr([])).toBe('-');
    expect(window.urlEncodeArr(['a', 'b'])).toBe('a,b');
  });

  it('decodes absent/""→null, "-"→[], csv→array', () => {
    const q = new URLSearchParams('x=-&y=a,b');
    expect(window.urlDecodeArr(q, 'missing')).toBe(null);
    expect(window.urlDecodeArr(q, 'x')).toEqual([]);
    expect(window.urlDecodeArr(q, 'y')).toEqual(['a', 'b']);
  });

  it('round-trips null / [] / subset through encode→parse→decode', () => {
    for (const original of [null, [], ['3101', '3102']]) {
      const qs = `g=${window.urlEncodeArr(original)}`;
      const q = new URLSearchParams(qs);
      expect(window.urlDecodeArr(q, 'g')).toEqual(original);
    }
  });
});

describe('urlState — numeric codec (NaN guard)', () => {
  it('absent/"" → null, finite → Number, garbage → null (no NaN leak)', () => {
    const q = new URLSearchParams('a=42&b=abc&c=');
    expect(window.urlDecodeNum(q, 'missing')).toBe(null);
    expect(window.urlDecodeNum(q, 'a')).toBe(42);
    expect(window.urlDecodeNum(q, 'c')).toBe(null);
    // The whole point: a hand-edited junk value must NOT become NaN.
    expect(window.urlDecodeNum(q, 'b')).toBe(null);
  });
});

describe('urlState — own-state gate + key registry', () => {
  it('URL_STATE_KEYS carries the v1.5.2 sub-UF geography keys', () => {
    for (const k of ['me', 'mc', 'it', 'im', 'mn']) {
      expect(window.URL_STATE_KEYS).toContain(k);
    }
  });

  it('urlHasOwnState detects our keys and ignores foreign ones', () => {
    expect(window.urlHasOwnState(new URLSearchParams('t=123'))).toBe(false);
    expect(window.urlHasOwnState(new URLSearchParams('mn=3550308'))).toBe(true);
    expect(window.urlHasOwnState(new URLSearchParams('v=overview'))).toBe(true);
  });
});

describe('urlState — full geo share round-trip (RVC-1)', () => {
  it('a sub-UF/município narrowing survives encode→decode; "all" is omitted', () => {
    const summary = {
      mesos: ['3101'],
      micros: null, // all → must be dropped from the URL
      inters: ['3501'],
      imediatas: null,
      munis: ['3550308', '3304557'],
    };
    const state = {
      v: 'geografia',
      me: window.urlEncodeArr(summary.mesos),
      mc: window.urlEncodeArr(summary.micros),
      it: window.urlEncodeArr(summary.inters),
      im: window.urlEncodeArr(summary.imediatas),
      mn: window.urlEncodeArr(summary.munis),
    };
    const qs = window.urlEncodeState(state);
    // "all" (null) dims are dropped entirely — never serialize the full universe.
    expect(qs).not.toMatch(/(^|&)mc=/);
    expect(qs).not.toMatch(/(^|&)im=/);

    const q = new URLSearchParams(qs);
    expect(window.urlDecodeArr(q, 'me')).toEqual(['3101']);
    expect(window.urlDecodeArr(q, 'mc')).toBe(null);
    expect(window.urlDecodeArr(q, 'it')).toEqual(['3501']);
    expect(window.urlDecodeArr(q, 'im')).toBe(null);
    expect(window.urlDecodeArr(q, 'mn')).toEqual(['3550308', '3304557']);
  });
});
