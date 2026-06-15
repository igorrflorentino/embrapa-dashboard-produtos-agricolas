// filterSummary.js — the pt-BR geographic-scope summary strings for FilterMenu.
//
// FilterMenu builds TWO geo summaries from the same selection: the live header
// line ("todo o território", lowercase) and the apply-time chip ("Todo o
// território", title case, used in the filter chip bar). Their wording differs,
// and so do their *partial* branches — the header keys on whether the banco is
// muni-SLICEABLE (a capability), the chip on whether the muni selection is FULL.
// They were buried in the 1101-line component as two inline ternary chains that
// had already drifted; co-locating them here (with a shared test) makes the
// difference explicit and keeps the two from silently diverging further.
//
// Pure string functions — no React, no window state — so they're unit-tested
// directly (filterSummary.test.js). Behaviour is preserved verbatim from the
// original inline logic.

const filterSummary = {
  // Live header line (FilterMenu.summary.geoTxt). Lowercase prose.
  geoHeaderText({
    hasGeo,
    nationsSize,
    nationsTotal,
    hasOnlyBR,
    regionsSize,
    regionsTotal,
    statesSize,
    statesTotal,
    munisSize,
    munisTotal,
    muniSliceable,
  }) {
    const muniFull = !muniSliceable || munisSize === munisTotal;
    if (!hasGeo) return 'sem recorte geográfico';
    if (
      nationsSize === nationsTotal &&
      regionsSize === regionsTotal &&
      statesSize === statesTotal &&
      muniFull
    )
      return 'todo o território';
    if (hasOnlyBR && statesSize === statesTotal && muniFull) return 'Brasil · todos os estados';
    if (muniSliceable)
      return `${nationsSize} nação(ões), ${statesSize} UF, ${munisSize === munisTotal ? 'todos os' : munisSize} municípios`;
    return `${nationsSize} nação(ões), ${statesSize} UF`;
  },

  // Apply-time chip (FilterMenu.buildChipSummary.geoChip). Title case + counts.
  geoChipText({
    hasGeo,
    nationsSize,
    nationsTotal,
    hasOnlyBR,
    regionsSize,
    regionsTotal,
    statesSize,
    statesTotal,
    munisSize,
    munisTotal,
    muniSliceable,
  }) {
    const muniFull = !muniSliceable || munisSize === munisTotal;
    if (!hasGeo) return 'Não se aplica';
    if (hasOnlyBR && statesSize === statesTotal && muniFull) return `Brasil · ${statesTotal} UFs`;
    if (
      nationsSize === nationsTotal &&
      regionsSize === regionsTotal &&
      statesSize === statesTotal &&
      muniFull
    )
      return 'Todo o território';
    if (!muniFull)
      return `${statesSize} ${statesSize === 1 ? 'UF' : 'UFs'} · ${munisSize} ${munisSize === 1 ? 'município' : 'municípios'}`;
    return `${nationsSize} ${nationsSize === 1 ? 'nação' : 'nações'} · ${statesSize} ${statesSize === 1 ? 'UF' : 'UFs'}`;
  },
};

window.filterSummary = filterSummary;
export default filterSummary;
