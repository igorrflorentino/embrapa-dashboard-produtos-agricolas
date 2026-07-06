// chipFmt.test.js — the COMTRADE país reporter/parceiro chip formatters (chipFmt.reporter /
// chipFmt.partner). Pins the Brasil / Mundo / N-países wording so the trigger-bar chip matches
// the menu across BOTH the apply path (Sets → array) and the URL-restore path (raw arrays).

import { describe, expect, it } from 'vitest';

import './chipFmt.js';

describe('chipFmt.reporter — país reporter chip', () => {
  const nameOf = (iso) => ({ BRA: 'Brasil', CHN: 'China' })[iso] || iso;

  it('null (default) → Brasil; "__all__"/full → Mundo; single → name; subset → N países', () => {
    expect(window.chipFmt.reporter(null, 203, nameOf)).toBe('Brasil');
    expect(window.chipFmt.reporter('__all__', 203, nameOf)).toBe('Mundo (203)');
    expect(window.chipFmt.reporter(new Array(203).fill('X'), 203, nameOf)).toBe('Mundo (203)');
    expect(window.chipFmt.reporter(['CHN'], 203, nameOf)).toBe('China');
    expect(window.chipFmt.reporter(['BRA', 'CHN'], 203, nameOf)).toBe('2 países');
  });
});

describe('chipFmt.partner — país parceiro chip', () => {
  const nameOf = (iso) => ({ CHN: 'China' })[iso] || iso;

  it('null/full → Todos; single → name; subset → N de total', () => {
    expect(window.chipFmt.partner(null, 246, nameOf)).toBe('Todos (246)');
    expect(window.chipFmt.partner(new Array(246).fill('X'), 246, nameOf)).toBe('Todos (246)');
    expect(window.chipFmt.partner(['CHN'], 246, nameOf)).toBe('China');
    expect(window.chipFmt.partner(['CHN', 'USA'], 246, nameOf)).toBe('2 de 246');
  });
});
