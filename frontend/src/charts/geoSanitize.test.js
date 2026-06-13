import { describe, expect, it } from 'vitest';

import { sanitizeFeatureCollection } from './geoSanitize';

const ring = (n = 5) => Array.from({ length: n }, (_, i) => [-50 + i * 0.1, -15 + i * 0.1]);

describe('sanitizeFeatureCollection', () => {
  it('drops empty `[]` sub-polygons from a MultiPolygon (FINDING #5 — what blanked the map)', () => {
    const fc = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { uf: 'CE' },
          geometry: { type: 'MultiPolygon', coordinates: [[ring()], []] }, // 2nd polygon empty
        },
      ],
    };
    const out = sanitizeFeatureCollection(fc);
    expect(out.features[0].geometry.coordinates).toHaveLength(1);
    expect(out.features[0].geometry.coordinates[0][0]).toHaveLength(5);
  });

  it('drops degenerate rings (< 4 positions) and polygons left empty after that', () => {
    const fc = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { uf: 'XX' },
          geometry: { type: 'MultiPolygon', coordinates: [[ring()], [[[[-50, -15]]]], [[[-50, -15], [-49, -15]]]] },
        },
      ],
    };
    const out = sanitizeFeatureCollection(fc);
    // only the first polygon (a valid 5-point ring) survives
    expect(out.features[0].geometry.coordinates).toHaveLength(1);
  });

  it('keeps valid single-polygon features untouched', () => {
    const fc = {
      type: 'FeatureCollection',
      features: [{ type: 'Feature', properties: { uf: 'AC' }, geometry: { type: 'MultiPolygon', coordinates: [[ring(10)]] } }],
    };
    const out = sanitizeFeatureCollection(fc);
    expect(out.features[0].geometry.coordinates).toHaveLength(1);
    expect(out.features[0].geometry.coordinates[0][0]).toHaveLength(10);
  });

  it('cleans a Polygon geometry and passes non-polygon features through', () => {
    const fc = {
      type: 'FeatureCollection',
      features: [
        { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [ring(), [[-1, -1]]] } },
        { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [-50, -15] } },
      ],
    };
    const out = sanitizeFeatureCollection(fc);
    expect(out.features[0].geometry.coordinates).toHaveLength(1); // degenerate ring dropped
    expect(out.features[1].geometry.type).toBe('Point'); // untouched
  });

  it('returns malformed input as-is without throwing', () => {
    expect(sanitizeFeatureCollection(null)).toBe(null);
    expect(sanitizeFeatureCollection({ foo: 1 })).toEqual({ foo: 1 });
  });
});
