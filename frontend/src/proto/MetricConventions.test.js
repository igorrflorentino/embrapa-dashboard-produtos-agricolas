// MetricConventions.test.js — base-aware currency scaling (cross-contract #5).
//
// convFactor is base-UNAWARE (assumes BRL-canonical values); convFactorFor adds
// the banco's own base currency so a USD-native trade banco (COMEX/Comtrade)
// converts correctly when the display switches away from its default. These
// tests pin the byte-identical defaults AND the previously-broken BRL switch.
//
// Importing the proto module for side effects installs window.convFactor/
// convFactorFor/CURRENCY_FX under jsdom (the module only assigns on window).

import { beforeAll, describe, expect, it } from 'vitest';

import './MetricConventions.jsx';

describe('convFactorFor (base-aware value multiplier)', () => {
  beforeAll(() => {
    // Guard against drift: these rates are the values the helper pivots through.
    expect(window.CURRENCY_FX.USD.rate).toBe(0.205);
    expect(window.CURRENCY_FX.EUR.rate).toBe(0.187);
  });

  // ---- Defaults must be byte-identical to the pre-fix convFactor path -------
  it('BRL base delegates to convFactor verbatim (PEVS/SEFAZ path unchanged)', () => {
    for (const currency of ['BRL', 'USD', 'EUR']) {
      const conv = { currency };
      expect(window.convFactorFor('BRL', conv)).toBe(window.convFactor(conv));
    }
  });

  it('USD-native default display (USD) is identity — same as today (factor 1)', () => {
    expect(window.convFactorFor('USD', { currency: 'USD' })).toBe(1);
    expect(window.convFactor({ currency: 'USD' })).toBe(1); // pre-fix default path
  });

  it('missing base defaults to BRL (back-compat)', () => {
    expect(window.convFactorFor(undefined, { currency: 'BRL' })).toBe(1);
    expect(window.convFactorFor(null, { currency: 'USD' })).toBe(1); // server-native USD col
  });

  // ---- The bug: USD-native banco switched to a non-default display ----------
  it('USD base → BRL display converts USD→BRL (the previously-broken case)', () => {
    // Pre-fix this was convFactor("BRL") = 1, leaving a US$ magnitude under R$.
    const f = window.convFactorFor('USD', { currency: 'BRL' });
    expect(f).toBeCloseTo(1 / 0.205, 10);
    // A US$100 UF value renders as ~R$487.80 instead of the wrong R$100.
    expect(100 * f).toBeCloseTo(487.804878, 4);
  });

  it('USD base → EUR display converts USD→EUR via the BRL pivot', () => {
    const f = window.convFactorFor('USD', { currency: 'EUR' });
    expect(f).toBeCloseTo(0.187 / 0.205, 10);
  });

  it('USD base → USD display stays exactly 1 (no rounding drift)', () => {
    expect(window.convFactorFor('USD', { currency: 'USD' })).toBe(1);
  });
});
