// geoSanitize.js — strip degenerate sub-geometries from a GeoJSON FeatureCollection
// before handing it to maplibre-gl. The bundled brazilUfGeo carries EMPTY polygon
// entries (`[]`, a polygon with no rings) inside its MultiPolygons — an artifact of
// the shape-simplification that produced it (143 of them across the 27 UFs). On an
// empty sub-polygon, maplibre-gl 4.x's geojson-vt worker throws "Cannot read
// properties of undefined (reading 'length')" and drops the ENTIRE feature, so the
// choropleth renders 0 features and the map is blank (FINDING #5 — confirmed live in
// production, not a headless artifact). Removing the empty polygons (and any ring
// with < 4 positions, which cannot enclose an area) yields valid GeoJSON that
// renders. Pure + side-effect-free so it is unit-tested without maplibre/WebGL.

// A polygon is an array of linear rings; keep only rings with enough positions to
// enclose an area (>= 4, since a closed ring repeats its first vertex).
function cleanPolygon(poly) {
  return Array.isArray(poly) ? poly.filter((ring) => Array.isArray(ring) && ring.length >= 4) : [];
}

function sanitizeFeature(f) {
  const g = f && f.geometry;
  if (!g) return f;
  if (g.type === 'MultiPolygon') {
    const coordinates = (g.coordinates || []).map(cleanPolygon).filter((poly) => poly.length > 0);
    return { ...f, geometry: { ...g, coordinates } };
  }
  if (g.type === 'Polygon') {
    return { ...f, geometry: { ...g, coordinates: cleanPolygon(g.coordinates || []) } };
  }
  return f;
}

/** Return a copy of a GeoJSON FeatureCollection with empty polygons and degenerate
 *  rings removed from every (Multi)Polygon feature. Non-polygon features pass
 *  through untouched. Safe on malformed input (returns it as-is when not a FC). */
export function sanitizeFeatureCollection(fc) {
  if (!fc || !Array.isArray(fc.features)) return fc;
  return { ...fc, features: fc.features.map(sanitizeFeature) };
}
