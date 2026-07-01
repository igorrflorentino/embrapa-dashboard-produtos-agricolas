// views_bancos.cov.test.js — coverage for the two registry/capability modules:
//   views.js  — VIEW_GROUPS registry + viewById/viewLabel/isViewLive,
//               viewComponent (lazy resolve + dev warn), crossPreviewBanco,
//               the capability system (viewAppliesTo / bancosSupporting /
//               missingCapsLabel) and crossViewApplies.
//   bancos.js — BANCOS registry + MATURITY, maturityMeta/bancoAvailability,
//               bancoById/canonCurrencyFor/isMonetaryBanco/bancoDim/geoLevelFor,
//               isBancoVisible/visibleBancos, bancoTable/bancoMeta, the derived
//               `status` getter, metricById/allMetricRefs and auditBancoCoverage.
//
// Both are side-effect modules that populate window.*; import in dependency order
// (bancos → views) so the cross-module lookups (crossPreviewBanco → bancoById,
// crossViewApplies → maturityMeta) resolve. Mirrors crossViews.test.js.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import './bancos.js';
import './views.js';

// ── bancos.js — MATURITY registry + derived helpers ─────────────────────────

describe('bancos.js — MATURITY registry shape', () => {
  it('exposes the 7 lifecycle stages in ascending order, with the no-data ones flagged', () => {
    const stages = ['planejado', 'desenvolvimento', 'ingestao', 'beta', 'estavel', 'manutencao', 'descontinuado'];
    stages.forEach((id) => {
      expect(window.MATURITY[id]).toBeTruthy();
      expect(window.MATURITY[id].id).toBe(id);
    });
    const orders = stages.map((id) => window.MATURITY[id].order);
    expect(orders).toEqual([...orders].sort((a, b) => a - b)); // strictly ascending
    // hasData split: only planejado + ingestao lack data.
    expect(window.MATURITY.planejado.hasData).toBe(false);
    expect(window.MATURITY.ingestao.hasData).toBe(false);
    expect(window.MATURITY.estavel.hasData).toBe(true);
    expect(window.MATURITY.descontinuado.hasData).toBe(true);
    // The caveat/sunset stages.
    expect(window.MATURITY.beta.caveat).toBe(true);
    expect(window.MATURITY.descontinuado.sunset).toBe(true);
  });
});

describe('maturityMeta — neutral LOADING until backend overlays a stage', () => {
  it('returns the LOADING stage for a banco with no maturity', () => {
    expect(window.maturityMeta({ id: 'x' }).id).toBe('loading');
    expect(window.maturityMeta(null).id).toBe('loading');
    expect(window.maturityMeta(undefined).id).toBe('loading');
  });

  it('resolves a known maturity to its MATURITY entry', () => {
    expect(window.maturityMeta({ maturity: 'estavel' }).id).toBe('estavel');
  });

  it('falls back to planejado for an unknown maturity string', () => {
    expect(window.maturityMeta({ maturity: 'totally_made_up' }).id).toBe('planejado');
  });
});

describe('bancoAvailability — short label derived from maturity', () => {
  it('reads Disponível once hasData, Em breve for ingestao, Sem previsão otherwise', () => {
    expect(window.bancoAvailability({ maturity: 'estavel' })).toBe('Disponível');
    expect(window.bancoAvailability({ maturity: 'desenvolvimento' })).toBe('Disponível');
    expect(window.bancoAvailability({ maturity: 'ingestao' })).toBe('Em breve');
    expect(window.bancoAvailability({ maturity: 'planejado' })).toBe('Sem previsão');
    expect(window.bancoAvailability(null)).toBe('Sem previsão'); // loading → no data → no ETA
  });
});

// ── bancos.js — BANCOS registry + lookups ───────────────────────────────────

describe('bancos.js — BANCOS registry shape', () => {
  it('registers the 6 expected bancos, each with id/short/table/provides/baseCurrency', () => {
    const ids = window.BANCOS.map((b) => b.id);
    expect(ids).toEqual([
      'ibge_pevs', 'ibge_pam', 'ibge_ppm', 'mdic_comex', 'un_comtrade', 'sefaz_nf',
    ]);
    window.BANCOS.forEach((b) => {
      expect(typeof b.short).toBe('string');
      expect(typeof b.table).toBe('string');
      expect(Array.isArray(b.provides)).toBe(true);
      expect(typeof b.baseCurrency).toBe('string');
    });
  });
});

describe('bancoById', () => {
  it('resolves a known id', () => {
    expect(window.bancoById('mdic_comex').id).toBe('mdic_comex');
  });
  it('falls back to the FIRST banco for an unknown id (never null)', () => {
    expect(window.bancoById('nope').id).toBe('ibge_pevs');
  });
});

describe('canonCurrencyFor — default display currency', () => {
  it('BRL for IBGE production bancos, USD for the trade bancos', () => {
    expect(window.canonCurrencyFor('ibge_pevs')).toBe('BRL');
    expect(window.canonCurrencyFor('ibge_ppm')).toBe('BRL');
    expect(window.canonCurrencyFor('mdic_comex')).toBe('USD');
    expect(window.canonCurrencyFor('un_comtrade')).toBe('USD');
  });
  it('falls back to BRL via the bancoById fallback for an unknown id', () => {
    // unknown id → bancoById returns ibge_pevs (BRL).
    expect(window.canonCurrencyFor('unknown')).toBe('BRL');
  });
});

describe('isMonetaryBanco — currency/correction conventions gate', () => {
  it('true for every current banco (all carry a baseCurrency)', () => {
    window.BANCOS.forEach((b) => expect(window.isMonetaryBanco(b)).toBe(true));
  });
  it('accepts a banco id string as well as an object', () => {
    expect(window.isMonetaryBanco('un_comtrade')).toBe(true);
  });
  it('true via a currency-family metric even without a baseCurrency', () => {
    expect(window.isMonetaryBanco({ id: 'x', metrics: [{ family: 'currency' }] })).toBe(true);
  });
  it('false for a physical-only banco (no baseCurrency, no currency metric)', () => {
    expect(window.isMonetaryBanco({ id: 'x', metrics: [{ family: 'mass' }] })).toBe(false);
  });
  it('false for a null/unresolvable banco', () => {
    expect(window.isMonetaryBanco(null)).toBe(false);
  });
});

describe('bancoDim — per-banco dimension descriptor', () => {
  it('reads the declared label + kind for a dimension', () => {
    expect(window.bancoDim('mdic_comex', 'dest')).toEqual({ label: 'país parceiro', kind: 'country' });
    expect(window.bancoDim('ibge_pevs', 'product').codeLabel).toBe('Código PEVS');
  });
  it('returns an empty object for an undeclared dimension', () => {
    expect(window.bancoDim('ibge_pevs', 'nonexistent')).toEqual({});
  });
});

describe('geoLevelFor — finest geographic granularity', () => {
  it('reads the explicit geoLevel where declared', () => {
    expect(window.geoLevelFor('ibge_pevs')).toBe('municipio');
    expect(window.geoLevelFor('mdic_comex')).toBe('uf');
    expect(window.geoLevelFor('un_comtrade')).toBe(null); // country-only
  });
  it('falls back to municipio when geoLevel is undefined but geo is provided', () => {
    // unknown id → bancoById returns ibge_pevs (geoLevel municipio).
    expect(window.geoLevelFor('ibge_pevs')).toBe('municipio');
    // craft a banco with geo capability but no explicit geoLevel.
    const stub = { provides: ['geo'] };
    window.BANCOS.push({ id: '__tmp_geo', ...stub });
    try {
      expect(window.geoLevelFor('__tmp_geo')).toBe('municipio');
    } finally {
      window.BANCOS.pop();
    }
  });
  it('null when no geo capability and no explicit geoLevel', () => {
    window.BANCOS.push({ id: '__tmp_nogeo', provides: ['product'] });
    try {
      expect(window.geoLevelFor('__tmp_nogeo')).toBe(null);
    } finally {
      window.BANCOS.pop();
    }
  });
});

describe('visibility axis — isBancoVisible / visibleBancos', () => {
  it('all 6 bancos are visible by default', () => {
    window.BANCOS.forEach((b) => expect(window.isBancoVisible(b)).toBe(true));
    expect(window.visibleBancos().length).toBe(window.BANCOS.length);
  });
  it('accepts an id string', () => {
    expect(window.isBancoVisible('ibge_pevs')).toBe(true);
  });
  it('a banco flagged visible:false is hidden from the enumeration', () => {
    const banco = window.bancoById('un_comtrade');
    banco.visible = false;
    try {
      expect(window.isBancoVisible(banco)).toBe(false);
      expect(window.visibleBancos().map((b) => b.id)).not.toContain('un_comtrade');
    } finally {
      delete banco.visible;
    }
  });
  it('false for an unresolvable banco', () => {
    expect(window.isBancoVisible({ id: undefined })).toBe(true); // visible !== false → true
  });
});

describe('bancoTable — backend-name-preferring resolver', () => {
  afterEach(() => { delete window.dataStore; });
  it('falls back to the registry table literal with no backend', () => {
    delete window.dataStore;
    expect(window.bancoTable('ibge_pevs')).toBe('gold_pevs_production');
  });
  it('prefers the backend-reported table name when present', () => {
    window.dataStore = { table: (id) => (id === 'ibge_pevs' ? 'gold_pevs_v2' : null) };
    expect(window.bancoTable('ibge_pevs')).toBe('gold_pevs_v2');
  });
  it('falls back to the registry literal when the backend returns null', () => {
    window.dataStore = { table: () => null };
    expect(window.bancoTable('mdic_comex')).toBe('gold_comex_flows');
  });
});

describe('bancoMeta — registry overlaid with backend meta (non-null wins)', () => {
  afterEach(() => { delete window.dataStore; });
  it('returns the bare registry banco with no backend', () => {
    delete window.dataStore;
    expect(window.bancoMeta('ibge_pevs').id).toBe('ibge_pevs');
  });
  it('overlays only the non-null backend fields', () => {
    window.dataStore = { meta: () => ({ rowsTotal: 999, ufsTotal: null }) };
    const meta = window.bancoMeta('ibge_pevs');
    expect(meta.rowsTotal).toBe(999);
    // null backend field must NOT clobber / appear.
    expect(meta.ufsTotal).toBeUndefined();
    expect(meta.id).toBe('ibge_pevs'); // registry field preserved
  });
});

describe('derived `status` getter — live iff maturity.hasData', () => {
  it("reads 'soon' until a maturity is overlaid, then 'live' for a hasData stage", () => {
    const banco = window.bancoById('ibge_pevs');
    const prev = banco.maturity;
    try {
      delete banco.maturity;
      expect(banco.status).toBe('soon');
      banco.maturity = 'estavel';
      expect(banco.status).toBe('live');
      banco.maturity = 'ingestao'; // hasData false
      expect(banco.status).toBe('soon');
    } finally {
      if (prev === undefined) delete banco.maturity; else banco.maturity = prev;
    }
  });
});

describe('metricById / allMetricRefs — cross-source series enumeration', () => {
  it('resolves a single (banco, metric) pair', () => {
    expect(window.metricById('ibge_pevs', 'prod_value').family).toBe('currency');
    expect(window.metricById('ibge_pevs', 'nope')).toBe(null);
    expect(window.metricById('ibge_pam', 'anything')).toBe(null); // PAM has [] metrics
  });
  it('enumerates every (banco, metric) ref across the metric-bearing bancos', () => {
    const refs = window.allMetricRefs();
    // PEVS(3) + COMEX(4) + COMTRADE(3) + SEFAZ(3) = 13; PAM/PPM contribute 0.
    expect(refs.length).toBeGreaterThanOrEqual(2);
    expect(refs.every((r) => r.banco && r.metric && r.bancoMeta && r.metricMeta)).toBe(true);
    expect(refs.some((r) => r.banco === 'ibge_pevs' && r.metric === 'prod_value')).toBe(true);
    expect(refs.some((r) => r.banco === 'ibge_pam')).toBe(false); // no metrics
  });
  it('METRIC_FAMILIES carries the display labels', () => {
    expect(window.METRIC_FAMILIES.currency.label).toBe('valor monetário');
    expect(window.METRIC_FAMILIES.mass.label).toBe('massa');
  });
});

describe('auditBancoCoverage — once-per-map dev lint', () => {
  beforeEach(() => { window.__bancoCoverageWarned = {}; });
  afterEach(() => { window.__bancoCoverageWarned = {}; });

  it('does NOT warn when every visible banco has an entry', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    window.auditBancoCoverage('full_map', () => true);
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it('warns listing the bancos with no entry', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    window.auditBancoCoverage('gappy_map', (b) => b.id !== 'un_comtrade');
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain('un_comtrade');
    warn.mockRestore();
  });

  it('treats a hasEntry that throws as "missing", and counts it', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    window.auditBancoCoverage('throwing_map', () => { throw new Error('boom'); });
    expect(warn).toHaveBeenCalledTimes(1);
    warn.mockRestore();
  });

  it('warns only ONCE per map label (the guard short-circuits a repeat)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    window.auditBancoCoverage('dup_map', () => false);
    window.auditBancoCoverage('dup_map', () => false); // guard → no second warn
    expect(warn).toHaveBeenCalledTimes(1);
    warn.mockRestore();
  });

  it('honours onlyLive: a no-data (soon) banco is skipped', () => {
    const banco = window.bancoById('ibge_pevs');
    const prev = banco.maturity;
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      delete banco.maturity; // status → 'soon'
      // hasEntry returns false ONLY for the now-soon pevs; onlyLive must skip it.
      window.auditBancoCoverage('onlylive_map', (b) => b.id !== 'ibge_pevs', { onlyLive: true });
      expect(warn).not.toHaveBeenCalled();
    } finally {
      if (prev === undefined) delete banco.maturity; else banco.maturity = prev;
      warn.mockRestore();
    }
  });
});

// ── views.js — registry + lookups ───────────────────────────────────────────

describe('views.js — VIEW_GROUPS registry shape', () => {
  it('every group has an id/label and a non-empty views array; each view has id/label/status', () => {
    expect(Array.isArray(window.VIEW_GROUPS)).toBe(true);
    expect(window.VIEW_GROUPS.length).toBeGreaterThan(0);
    window.VIEW_GROUPS.forEach((g) => {
      expect(typeof g.id).toBe('string');
      expect(typeof g.label).toBe('string');
      expect(g.views.length).toBeGreaterThan(0);
      g.views.forEach((v) => {
        expect(typeof v.id).toBe('string');
        expect(typeof v.label).toBe('string');
        expect(v.status).toBe('live');
      });
    });
  });

  it('VIEW_BY_ID flattens every view and attaches its group', () => {
    expect(window.VIEW_BY_ID.overview.group.id).toBe('aggregate');
    expect(window.VIEW_BY_ID.cross_source.group.id).toBe('crosssource');
    // The "curated" group (Análises curadas) is now live → its views are flattened.
    expect(window.VIEW_BY_ID.curated_value_added.group.id).toBe('curated');
    expect(window.VIEW_BY_ID.curated_market_nature.group.id).toBe('curated');
  });
});

describe('viewById / viewLabel / isViewLive', () => {
  it('viewById resolves a known view and returns null for an unknown one', () => {
    expect(window.viewById('overview').id).toBe('overview');
    expect(window.viewById('nope')).toBe(null);
  });
  it('viewLabel returns the label, or echoes the id when unknown', () => {
    expect(window.viewLabel('overview')).toBe('Visão geral');
    expect(window.viewLabel('mystery_id')).toBe('mystery_id');
  });
  it('isViewLive is true for a registered view, false/falsey for an unknown one', () => {
    expect(window.isViewLive('quality')).toBe(true);
    expect(window.isViewLive('mystery_id')).toBeFalsy();
  });
});

describe('viewComponent — lazy global resolution + dev warn', () => {
  afterEach(() => { delete window.ViewOverview; delete window.ViewDados; });

  it('resolves the mapped global when it exists', () => {
    const stub = () => null;
    window.ViewOverview = stub;
    expect(window.viewComponent('overview')).toBe(stub);
  });

  it('returns a falsey component AND warns for a LIVE view whose global is missing', () => {
    // viewComponent returns `window[name]` directly (undefined when the global is
    // not yet defined) — it does NOT coerce to null; the warn is the contract.
    delete window.ViewOverview;
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(window.viewComponent('overview')).toBeFalsy();
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain('overview');
    warn.mockRestore();
  });

  it('returns null WITHOUT warning for an unmapped/unknown id (not a live view)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(window.viewComponent('totally_unknown')).toBe(null);
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe('crossPreviewBanco — least-mature source gates a cross view into preview', () => {
  it('returns null for a non-cross view (no `sources`)', () => {
    expect(window.crossPreviewBanco('overview')).toBe(null);
  });
  it('picks a source banco for a cross view with declared sources', () => {
    // cross_market_share sources: mdic_comex + un_comtrade. Both resolve; the
    // helper returns whichever the gating selects (a real banco object).
    const b = window.crossPreviewBanco('cross_market_share');
    expect(b).toBeTruthy();
    expect(['mdic_comex', 'un_comtrade']).toContain(b.id);
  });
  it('ties prefer the later (downstream) source index', () => {
    // With both COMEX and COMTRADE at the SAME maturity order, the <= tie rule
    // picks the LAST in the sources array → un_comtrade.
    const comex = window.bancoById('mdic_comex');
    const comtrade = window.bancoById('un_comtrade');
    const pc = comex.maturity, pt = comtrade.maturity;
    try {
      comex.maturity = 'estavel';
      comtrade.maturity = 'estavel';
      expect(window.crossPreviewBanco('cross_market_share').id).toBe('un_comtrade');
    } finally {
      if (pc === undefined) delete comex.maturity; else comex.maturity = pc;
      if (pt === undefined) delete comtrade.maturity; else comtrade.maturity = pt;
    }
  });
});

// ── views.js — capability system ────────────────────────────────────────────

describe('CAPABILITIES registry', () => {
  it('carries a label for each declared capability token', () => {
    ['product', 'geo', 'flow', 'partner', 'monthly', 'quality', 'area', 'yield', 'herd', 'monetary']
      .forEach((c) => expect(typeof window.CAPABILITIES[c].label).toBe('string'));
  });
});

describe('viewAppliesTo — requires × provides crossing', () => {
  it('a no-requires view applies to every banco', () => {
    expect(window.viewAppliesTo('overview', 'ibge_pevs')).toEqual({ applies: true, missing: [] });
    expect(window.viewAppliesTo('concentration', 'un_comtrade')).toEqual({ applies: true, missing: [] });
  });

  it('a geo view does not apply to a country-only banco — reports the missing cap', () => {
    const r = window.viewAppliesTo('geo', 'un_comtrade'); // requires ['geo']; comtrade has none
    expect(r.applies).toBe(false);
    expect(r.missing).toContain('geo');
  });

  it('a yield view applies only to a banco that provides yield (PAM), not PEVS', () => {
    expect(window.viewAppliesTo('productivity', 'ibge_pam').applies).toBe(true);
    expect(window.viewAppliesTo('productivity', 'ibge_pevs').applies).toBe(false);
  });

  it('a herd view applies only to PPM', () => {
    expect(window.viewAppliesTo('rebanho', 'ibge_ppm').applies).toBe(true);
    expect(window.viewAppliesTo('rebanho', 'ibge_pevs').applies).toBe(false);
  });

  it('a crossBanco view short-circuits to applies:true regardless of banco', () => {
    expect(window.viewAppliesTo('cross_source', 'ibge_pevs')).toEqual({ applies: true, missing: [] });
    expect(window.viewAppliesTo('cross_export_coef', 'un_comtrade')).toEqual({ applies: true, missing: [] });
  });

  it('an unknown view or banco short-circuits to applies:true (permissive default)', () => {
    expect(window.viewAppliesTo('nope', 'ibge_pevs')).toEqual({ applies: true, missing: [] });
    // unknown banco id → bancoById falls back to ibge_pevs, so still resolves.
    expect(window.viewAppliesTo('overview', 'unknown_banco').applies).toBe(true);
  });
});

describe('bancosSupporting — inverse indicator', () => {
  it('returns [] for an unknown view', () => {
    expect(window.bancosSupporting('nope')).toEqual([]);
  });
  it('a no-requires view is supported by every visible banco', () => {
    expect(window.bancosSupporting('overview').length).toBe(window.visibleBancos().length);
  });
  it('a flow view is supported only by trade bancos', () => {
    const ids = window.bancosSupporting('flows_territorial').map((b) => b.id); // requires ['flow']
    expect(ids).toContain('mdic_comex');
    expect(ids).toContain('un_comtrade');
    expect(ids).not.toContain('ibge_pevs');
  });
  it('a yield view is supported only by PAM', () => {
    expect(window.bancosSupporting('productivity').map((b) => b.id)).toEqual(['ibge_pam']);
  });
});

describe('missingCapsLabel — human phrase for missing caps', () => {
  it('joins known capability labels with a middot', () => {
    expect(window.missingCapsLabel(['flow', 'geo'])).toBe(
      'fluxo origem → destino · dimensão geográfica (UF/município)',
    );
  });
  it('echoes an unknown token verbatim and handles empty/undefined', () => {
    expect(window.missingCapsLabel(['mystery'])).toBe('mystery');
    expect(window.missingCapsLabel([])).toBe('');
    expect(window.missingCapsLabel(undefined)).toBe('');
  });
});

// ── views.js — crossViewApplies (multi-fonte usability) ─────────────────────

describe('crossViewApplies — multi-fonte usability gate', () => {
  it('a non-cross view short-circuits to usable/ok', () => {
    expect(window.crossViewApplies('overview')).toEqual({ usable: true, state: 'ok', reason: '' });
    expect(window.crossViewApplies('nope')).toEqual({ usable: true, state: 'ok', reason: '' });
  });

  it('data-blocked cross views are not usable (state=preview)', () => {
    ['cross_chain', 'cross_lag'].forEach((id) => {
      const r = window.crossViewApplies(id);
      expect(r.usable).toBe(false);
      expect(r.state).toBe('preview');
      expect(r.reason).toMatch(/[Dd]emonstra/);
    });
  });

  it('a working cross view with live sources is usable', () => {
    // maturityMeta returns LOADING (id !== loading is false) → treated as available,
    // so the source-availability axis does not hide it on first paint.
    expect(window.crossViewApplies('cross_export_coef').usable).toBe(true);
  });

  it('source-availability: a no-data source flips the dependent view to state=na', () => {
    const comtrade = window.bancoById('un_comtrade');
    const prev = comtrade.maturity;
    try {
      comtrade.maturity = 'planejado'; // hasData false
      const r = window.crossViewApplies('cross_market_share'); // sources: comex + comtrade
      expect(r.usable).toBe(false);
      expect(r.state).toBe('na');
      expect(r.reason).toMatch(/Fonte indispon/);
    } finally {
      if (prev === undefined) delete comtrade.maturity; else comtrade.maturity = prev;
    }
  });

  it('source-availability: a hidden source flips the dependent view to state=na', () => {
    const comex = window.bancoById('mdic_comex');
    try {
      comex.visible = false;
      const r = window.crossViewApplies('cross_export_coef'); // sources: pevs + comex
      expect(r.usable).toBe(false);
      expect(r.state).toBe('na');
    } finally {
      delete comex.visible;
    }
  });

  it('the free-form comparator (cross_source, no sources) is usable while ≥2 series exist', () => {
    expect(window.allMetricRefs().length).toBeGreaterThanOrEqual(2);
    expect(window.crossViewApplies('cross_source').usable).toBe(true);
  });
});
