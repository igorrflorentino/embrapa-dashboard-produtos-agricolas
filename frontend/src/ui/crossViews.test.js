// crossViews.test.js — the multi-fonte usability gate (window.crossViewApplies),
// which lets the perspective picker show ONLY the cross perspectives the user can
// actually use. Three axes: data-blocked (authored), source-availability, and the
// ≥2-comparable-series rule for the free-form comparator.

import { describe, expect, it } from 'vitest';

import './bancos.js';
import './views.js';

describe('crossViewApplies — multi-fonte perspective usability', () => {
  it('data-blocked perspectives are not usable (state=preview)', () => {
    for (const id of ['cross_chain', 'cross_lag']) {
      const r = window.crossViewApplies(id);
      expect(r.usable).toBe(false);
      expect(r.state).toBe('preview');
      expect(r.reason).toMatch(/[Dd]emonstra/);
    }
  });

  it('working cross perspectives are usable (live sources)', () => {
    for (const id of ['cross_export_coef', 'cross_market_share', 'cross_price_spread', 'cross_mirror']) {
      expect(window.crossViewApplies(id).usable).toBe(true);
    }
  });

  it('the free-form comparator (cross_source) is usable while ≥2 comparable series exist', () => {
    // allMetricRefs spans PEVS(3)+COMEX(4)+COMTRADE(3) — well over 2.
    expect(window.allMetricRefs().length).toBeGreaterThanOrEqual(2);
    expect(window.crossViewApplies('cross_source').usable).toBe(true);
  });

  it('curated perspectives are NOT gated here (needs-activation is a separate state)', () => {
    expect(window.crossViewApplies('curated_value_added').usable).toBe(true);
    expect(window.crossViewApplies('curated_market_nature').usable).toBe(true);
  });

  it('a non-cross view short-circuits to usable (this gate is cross-only)', () => {
    expect(window.crossViewApplies('overview').usable).toBe(true);
  });

  it('source-availability: a cross view becomes Indisponível when a source has no data', () => {
    // Temporarily mark a live source as a no-data maturity stage and confirm the
    // perspective that depends on it flips to state=na. Restore afterward.
    const comtrade = window.bancoById('un_comtrade');
    const prev = comtrade.maturity;
    try {
      comtrade.maturity = 'planejado'; // MATURITY.planejado.hasData === false
      const r = window.crossViewApplies('cross_market_share'); // sources: comex + comtrade
      expect(r.usable).toBe(false);
      expect(r.state).toBe('na');
      expect(r.reason).toMatch(/Fonte indispon/);
    } finally {
      comtrade.maturity = prev;
    }
  });
});
