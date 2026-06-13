// chipCoverage.js — pure helper backing the FilterTriggerBar chip summary.
//
// FINDING #2: on first load / banco switch the active banco's per-convention
// snapshot has not arrived yet, so applyFilters falls back to the PEVS synthetic
// globals (12 products, 1986–2024). Building the chips straight from that showed
// the cross-source catalog count + the PEVS year span for EVERY banco (COMEX read
// "Todos (12) · 1986–2024" instead of its real "Todos (5) · 1997–2026").
//
// This resolves the product TOTAL and the PERIOD the chips should show, preferring
// — when the snapshot is NOT yet loaded — the ACTIVE banco's own metadata (the
// live /api/source-meta coverage if it resolved, else the banco-specific registry
// prov), never the PEVS default. Once the snapshot is loaded, applyFilters already
// carries the banco's real values, so we use those.
//
// Pure (no window / no React) so it is unit-testable in isolation.

/**
 * @param {object} args
 * @param {boolean} args.snapLoaded   - true once the banco's snapshot is in the store
 * @param {object|null} args.applied  - applyFilters() result ({ productsTotal, yearStart, yearEnd })
 * @param {object|null} args.meta     - dataStore.meta(banco) ({ coverage, prov })
 * @param {boolean} args.hasDateSel   - true when the summary carries an explicit date window
 * @returns {{ total:number, yearStart:number, yearEnd:number }}
 */
export function resolveChipCoverage({ snapLoaded, applied, meta, hasDateSel }) {
  const f = applied || {};
  const appliedTotal =
    f.productsTotal != null ? f.productsTotal : (f.products || []).length;

  // Snapshot present → applyFilters already reflects the active banco; trust it.
  if (snapLoaded) {
    return { total: appliedTotal, yearStart: f.yearStart, yearEnd: f.yearEnd };
  }

  const cov = (meta && meta.coverage) || null;
  const prov = (meta && meta.prov) || null;
  const pick = (key) => {
    if (cov && cov[key] != null) return cov[key];
    if (prov && prov[key] != null) return prov[key];
    return null;
  };
  const fbTotal = pick('productsTotal');
  const fbY0 = pick('yearStart');
  const fbY1 = pick('yearEnd');

  return {
    total: fbTotal != null ? fbTotal : appliedTotal,
    // An explicit date selection already yields the right window via applyFilters;
    // only the unselected default would otherwise fall back to the PEVS span.
    yearStart: !hasDateSel && fbY0 != null ? fbY0 : f.yearStart,
    yearEnd: !hasDateSel && fbY1 != null ? fbY1 : f.yearEnd,
  };
}
