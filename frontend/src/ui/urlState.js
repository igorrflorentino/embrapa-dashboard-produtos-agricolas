// urlState.js — the shared deep-link codec contract.
//
// The app state travels in the share URL. The ENCODER lives in
// AppShell.onShare and the DECODER in Dashboard.readStateFromURL — two halves
// of the same wire format. The param-key list and the array sentinel rules
// were duplicated as literals on both sides; a typo on one half silently
// breaks shared links. This module is the single source of truth for the keys
// and the array encode/decode, so the two halves can't drift.

// Every query param the dashboard owns. Used by the encoder (to know what to
// emit) and by the decoder (to detect whether a URL carries OUR state at all,
// so unrelated params like ?t=… stay inert).
window.URL_STATE_KEYS = [
  'v', 'b', 'ip', 'cur', 'corr', 'mu', 'vu', 'as',
  'pb', 'fl', 'st', 'vmn', 'vmx', 'sd', 'ed', 'fx',
  // Sub-UF / município geography (v1.5.2): mesorregião (me), microrregião (mc),
  // região intermediária (it), região imediata (im), município (mn). null="all"
  // (omitted), so a non-narrowing selection never bloats the URL — only an actual
  // sub-UF/município narrowing travels (and the município subset stays small, the
  // 414-safe counterpart to the POST /api/municipio-yearly query path).
  'me', 'mc', 'it', 'im', 'mn',
  'xs', 'xm', 'xy0', 'xy1',
];

// Array dimension → param. null = "no filter" (omitted → all on restore); an
// explicit empty selection travels as the sentinel "-" so "Nenhum"/"Nenhuma"
// survives the round-trip instead of silently restoring as "all".
window.urlEncodeArr = (a) => (a == null ? '' : (a.length ? a.join(',') : '-'));

// Inverse of urlEncodeArr, reading from a URLSearchParams.
//   absent/'' → null (no filter, all) · '-' → [] (explicit none) · csv → array
window.urlDecodeArr = (q, key) => {
  const v = q.get(key);
  if (v === null || v === '') return null;
  if (v === '-') return [];
  return v.split(',').filter(Boolean);
};

// Numeric param: absent/'' → null, else a FINITE number. A malformed value
// (?vmn=abc) decodes to null rather than NaN, so a hand-edited/garbage share URL
// can't propagate NaN into value-range filters or the cross-view year bounds.
window.urlDecodeNum = (q, key) => {
  const v = q.get(key);
  if (v === null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

// Does this query string carry any of OUR keys? (Decoder gate.)
window.urlHasOwnState = (q) => window.URL_STATE_KEYS.some(k => q.has(k));

// Build the share query string from the flat state object the encoder
// assembles (keys = URL_STATE_KEYS). Drops empty/undefined/null values.
window.urlEncodeState = (state) =>
  Object.entries(state)
    .filter(([, v]) => v !== '' && v !== undefined && v !== null)
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join('&');
