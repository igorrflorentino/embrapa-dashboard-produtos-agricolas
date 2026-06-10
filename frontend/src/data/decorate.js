// decorate.js — join the client-side registries the /api/snapshot deliberately
// omits onto the API rows (see PLANS/react_migration_contract_map.md §0.3).
//
// The API returns the keys to join on (uf, quality-flag id); the presentation
// metadata — UF tile coordinates (col/row) and quality-flag label/color — lives
// in the prototype's registries (window.UF_DATA, window.QUALITY_FLAGS), which the
// views also use directly. Joining them server-side would duplicate the
// registries and invite drift, so we decorate here, in the data layer.

/** uf → { col, row, region, name } from the UF tile-grid registry. */
function ufTiles() {
  const idx = {};
  (window.UF_DATA || []).forEach((u) => {
    idx[u.uf] = u;
  });
  return idx;
}

/** quality-flag id → { label, color } from the shared taxonomy. */
function qualityTaxonomy() {
  const idx = {};
  (window.QUALITY_FLAGS || []).forEach((f) => {
    idx[f.id] = f;
  });
  return idx;
}

export function decorateSnapshot(snap) {
  if (!snap || typeof snap !== 'object') return snap;

  if (Array.isArray(snap.ufData) && snap.ufData.length) {
    const tiles = ufTiles();
    snap.ufData = snap.ufData.map((r) => {
      const t = tiles[r.uf] || {};
      return {
        ...r,
        col: r.col ?? t.col,
        row: r.row ?? t.row,
        region: r.region || t.region,
        name: r.name || t.name,
      };
    });
  }

  if (Array.isArray(snap.quality) && snap.quality.length) {
    const tax = qualityTaxonomy();
    snap.quality = snap.quality.map((q) => {
      const f = tax[q.id] || {};
      return { ...q, label: f.label || q.id, color: f.color || 'var(--pres-gray-400)' };
    });
  }

  // applyFilters reads snap.regions (falls back to window.REGIONS anyway, but be
  // explicit). qualityTs + qualityByProduct now ARRIVE in the snapshot; qualityByUf
  // / topMunis stay optional and default to [] in applyFilters (no endpoint yet).
  snap.regions = snap.regions || window.REGIONS || [];
  return snap;
}
