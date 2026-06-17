// chipFmt.js — shared formatters for the filter trigger-bar "chips".
//
// The chip labels (products / value range / quality) were implemented THREE
// times with identical rules: FilterMenu.buildChipSummary (operates on Sets),
// Dashboard.chipsFromRestoredSummary and Dashboard.defaultChipsFor (operate on
// arrays). A divergence there means a shared URL shows different chips than the
// FilterMenu would. Centralised here as pure functions over primitives so all
// three call ONE implementation. Loaded with the other data-layer scripts.

// Compact monetary label (sym-aware): "R$ 1,2 bi" / "US$ 340 mil".
// Replaces the per-file copies (FilterMenu.formatBRLcompact + Dashboard.compactBRL).
// Negative-safe so an inverted range still reads correctly.
window.fmtCompactValue = (v, sym = 'R$') => {
  if (v == null) return '—';
  const a = Math.abs(v), sign = v < 0 ? '-' : '';
  const f = (div, dp, suf) => `${sign}${sym} ` + (a / div).toFixed(dp).replace('.', ',') + suf;
  if (a >= 1e9) return f(1e9, 1, ' bi');
  if (a >= 1e6) return f(1e6, 1, ' mi');
  if (a >= 1e3) return f(1e3, 0, ' mil');
  return `${sign}${sym} ` + a.toLocaleString('pt-BR');
};

window.chipFmt = {
  // Product basket → chip. count = selected, total = catalogue size,
  // firstName = name to show when exactly one is selected.
  products(count, total, firstName) {
    if (count == null)            return `Todos (${total})`;   // null = no filter = all
    if (count === 0)              return 'Nenhum';
    if (count === total)          return `Todos (${total})`;
    if (count === 1)              return firstName || `1 de ${total}`;
    return `${count} de ${total}`;
  },

  // Year range → chip ("1986–2024").
  period(startYear, endYear) {
    return `${startYear}\u2013${endYear}`;
  },

  // Value range → chip. sym is the active currency symbol.
  valueRange(min, max, sym = 'R$') {
    const f = (v) => window.fmtCompactValue(v, sym);
    if (min == null && max == null) return 'Sem limite';
    if (min != null && max != null) return `${f(min)} \u2013 ${f(max)}`;
    if (min != null)                return `\u2265 ${f(min)}`;
    return `\u2264 ${f(max)}`;
  },

  // Quality flags → chip. count null = no filter = all; labelOf maps id→label.
  quality(ids, total, labelOf) {
    if (ids == null)          return `Todas (${total})`;
    if (ids.length === 0)     return 'Nenhuma';
    if (ids.length === total) return `Todas (${total})`;
    const head = ids.slice(0, 2).map(labelOf).join(' \u00b7 ');
    return head + (ids.length > 2 ? ` +${ids.length - 2}` : '');
  },

  // States-only geography → chip (Dashboard's banco-aware default & restore).
  // hasGeo false = the banco has no geographic dimension.
  geoStates(stateCount, ufTotal, hasGeo) {
    if (!hasGeo) return 'Não se aplica';
    if (!stateCount || stateCount === ufTotal) return `Brasil \u00b7 ${ufTotal} UFs`;
    return `${stateCount} ${stateCount === 1 ? 'UF' : 'UFs'}`;
  },
};
