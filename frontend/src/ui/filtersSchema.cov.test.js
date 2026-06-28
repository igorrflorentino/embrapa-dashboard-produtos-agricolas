// filtersSchema.cov.test.js — pushes filtersSchema.js to high coverage by driving
// the remaining branches the contract test (filtersSchema.test.js) leaves: the
// auditFilterSchemaCoverage drift detector (an unknown `requires` capability and a
// serverParam-without-FLOW_OPTIONS both reach the warn path), the once-per-run guard,
// and the document.readyState 'complete' immediate-run branch at module load.
//
// Side-effect modules populate window.* in dependency order (bancos → views →
// filtersSchema), exactly like filtersSchema.test.js.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import './bancos.js';
import './views.js';
import './filtersSchema.js';

describe('auditFilterSchemaCoverage — drift detector (warn path)', () => {
  let realSchemas;
  let realFlow;
  beforeEach(() => {
    realSchemas = window.FILTER_SCHEMAS;
    realFlow = window.FLOW_OPTIONS;
    window.__filterSchemaAudited = false; // reset the once-per-run guard
  });
  afterEach(() => {
    window.FILTER_SCHEMAS = realSchemas;
    window.FLOW_OPTIONS = realFlow;
    window.__filterSchemaAudited = false;
    vi.restoreAllMocks();
  });

  it('warns when a dim requires an unknown capability token (line 308)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    window.FILTER_SCHEMAS = {
      bogus_banco: {
        table: 't',
        dims: [{ id: 'mystery', requires: 'no_such_capability', backed: true }],
      },
    };
    window.auditFilterSchemaCoverage();
    expect(warn).toHaveBeenCalledTimes(1);
    const msg = warn.mock.calls[0][0];
    expect(msg).toContain('coverage drift detected');
    expect(msg).toContain("requires 'no_such_capability' is not a known capability");
  });

  it('warns when a serverParam:flow dim has no FLOW_OPTIONS for its banco (line 311)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    // A known capability (so line 308 is skipped) but no FLOW_OPTIONS entry for the banco.
    window.FILTER_SCHEMAS = {
      banco_without_flow_options: {
        table: 't',
        dims: [{ id: 'fluxo', requires: 'flow', backed: true, serverParam: 'flow' }],
      },
    };
    window.FLOW_OPTIONS = {}; // no entry → flowOptionsFor(...) returns null
    window.auditFilterSchemaCoverage();
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toContain("serverParam 'flow' but no FLOW_OPTIONS");
  });

  it('is a no-op on a second call (once-per-run guard short-circuits)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    window.FILTER_SCHEMAS = {
      bad: { table: 't', dims: [{ id: 'x', requires: 'unknown_cap', backed: true }] },
    };
    window.auditFilterSchemaCoverage(); // sets the guard + warns once
    expect(warn).toHaveBeenCalledTimes(1);
    window.auditFilterSchemaCoverage(); // guard true → early return, no second warn
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it('a dim with no requires never trips the capability check', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    window.FILTER_SCHEMAS = {
      ok_banco: { table: 't', dims: [{ id: 'periodo', requires: null, backed: true }] },
    };
    window.auditFilterSchemaCoverage();
    expect(warn).not.toHaveBeenCalled();
  });
});

describe('module-load immediate-run branch (document.readyState complete)', () => {
  afterEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
  });

  it('runs auditFilterSchemaCoverage immediately when the document is already complete', async () => {
    // jsdom default readyState is 'complete', so a FRESH import of the module (after
    // resetModules) takes the `if (document.readyState === 'complete')` branch (line 327)
    // and runs the audit synchronously, instead of registering the 'load' listener.
    vi.resetModules();
    expect(document.readyState).toBe('complete');
    const auditSpy = vi.fn();
    // Pre-seed the global the fresh module will assign over; spy via a getter trap is
    // brittle, so instead assert the module DID run by checking the audited guard flips.
    window.__filterSchemaAudited = false;
    await import('./bancos.js');
    await import('./views.js');
    await import('./filtersSchema.js');
    // The immediate run set the once-per-run guard true.
    expect(window.__filterSchemaAudited).toBe(true);
    expect(auditSpy).not.toHaveBeenCalled(); // (sanity: our local spy was never wired in)
  });
});
