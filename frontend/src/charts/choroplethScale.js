// choroplethScale.js — the pure color logic behind BrazilChoropleth, split out so
// it can be unit-tested without importing maplibre-gl (WebGL, no jsdom).

// Sequential light->dark green ramp (quantized buckets); zero / no-data UFs get a
// neutral gray so "absent" reads differently from "low".
export const RAMP = ['#e8f3ec', '#bfe0cb', '#8fcaa6', '#5bb381', '#2f9460', '#16713f'];
export const NODATA = '#eef0ef';

/** {uf -> bucket color} for the data, on a 0..max linear scale quantized into
 *  `ramp`. Zero / missing values map to `nodata`. Returns { byUf, max }. */
export function ufColorScale(data, valueKey, ramp = RAMP, nodata = NODATA) {
  const rows = Array.isArray(data) ? data : [];
  const max = Math.max(1, ...rows.map((d) => Number(d[valueKey]) || 0));
  const byUf = {};
  for (const d of rows) {
    if (!d.uf) continue;
    const v = Number(d[valueKey]) || 0;
    if (v <= 0) {
      byUf[d.uf] = nodata;
      continue;
    }
    const t = Math.min(1, v / max); // linear share of the max
    const idx = Math.min(ramp.length - 1, Math.floor(t * (ramp.length - 1) + 1e-9));
    byUf[d.uf] = ramp[idx];
  }
  return { byUf, max };
}

/** A maplibre data-driven `match` expression on the `uf` feature property, or a
 *  constant fallback color when there's nothing to color.
 *
 *  Hardened (FINDING #5): only well-formed [string uf → string color] pairs are
 *  emitted. A `null`/`undefined`/non-string label or color injected into a
 *  maplibre `match` makes the expression compiler dereference `.length` on a
 *  missing operand and throw "Cannot read properties of undefined (reading
 *  'length')" — which blanks the map without tripping the WebGL fallback. Any
 *  bad pair is dropped; if nothing valid remains we return the constant fallback
 *  so maplibre always receives a valid paint value. */
export function fillColorExpression(byUf, fallback = NODATA) {
  const pairs = [];
  for (const [uf, color] of Object.entries(byUf || {})) {
    if (typeof uf === 'string' && uf && typeof color === 'string' && color) {
      pairs.push(uf, color);
    }
  }
  if (!pairs.length) return fallback;
  return ['match', ['get', 'uf'], ...pairs, fallback];
}
