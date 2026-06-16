// dataFilters.js — applies the active filter selection to every dataset
// used by the views, so charts/KPIs ONLY show rows that match.
//
// Input shape (from FilterMenu.onApply):
//   { basket:    string[]  // product codes;  null = all · [] = none
//   , flags:     string[]  // quality flags;   null = all · [] = none
//   , states:    string[]  // UF codes;        null = all · [] = none
//   , munis:     string[]  // município codes (cascade); narrows topMunis
//   , muniNames: string[]  // selected município NAMES — the data keys topMunis
//                          //   by city name, so the engine matches on these
//   , nations, regions     // cascade parents; their effect reaches the data
//                          //   through `states` (deselecting prunes states)
//   , startDate, endDate   // 'YYYY-MM-01'
//   , valueMin, valueMax   // row-level value filter (banco base currency)
//   }
//
// Output: { ts, productTS, ufData, regionData, topMunis, topProducts,
//           qualityFlags, qualityTs, selectedProducts, yearStart, yearEnd,
//           notFilteredByBasket, _shares }

(function () {
  const yearOf = (iso) => iso ? parseInt(iso.slice(0, 4), 10) : null;

  // Heuristic share of rows that pass the row-level value filter.
  // Used only to scale the "Linhas" provenance counter; not data display.
  // The thresholds + shares come from the shared window.VALUE_PRESETS
  // (filtersSchema.js). There is no real backend COUNT for a value threshold yet,
  // so rather than assert a fabricated filtered count we leave the "Linhas" counter
  // at the unfiltered total (share 1.00) for every value-threshold — presets AND a
  // custom range alike — until a real /api count exists.
  function valueShareForRange(min, max) {
    if (min == null && max == null) return 1.00;
    if (min === 0 && max == null)   return 1.00;
    const preset = (window.VALUE_PRESETS || []).find(p => p.min === min && p.max === max);
    if (preset) return preset.rowShare;
    return 1.00; // custom range — no fabricated share (was 0.66)
  }

  window.applyFilters = function (summary, bancoId) {
    summary = summary || {};

    // ── Resolve the in-memory snapshot for the active banco ────────────
    // Banco-aware seam: when a bancoId is given and its snapshot is loaded,
    // read from it; otherwise fall back to the PEVS globals so EVERY existing
    // call site — applyFilters(summary) with no bancoId — behaves EXACTLY as
    // before (zero regression). This is the single function the backend
    // generalizes: in Dash/Python it becomes apply_filters(banco_id, summary)
    // reading dataset_for(banco_id). Missing dimensions degrade to empty.
    const fromStore = (bancoId && window.dataStore && window.dataStore.get)
      ? window.dataStore.get(bancoId) : null;
    // If the banco isn't loaded into the store yet, fall back to its OWN
    // synthetic snapshot (banco-aware) — never silently to PEVS. Only when no
    // bancoId / no snapshot exists do we use the PEVS globals (the live mock).
    const fromSynth = (!fromStore && bancoId && window.snapshotFor)
      ? window.snapshotFor(bancoId) : null;
    const snap = fromStore || fromSynth || {
      products:   window.PRODUCTS,
      productTS:  window.PRODUCT_TS,
      overviewTS: window.OVERVIEW_TS,
      ufData:     window.UF_DATA,
      quality:    window.QUALITY_FLAGS,
      qualityTs:  window.QUALITY_TS,
      topMunis:   window.TOP_MUNICIPIOS,
      regions:    window.REGIONS,
      qualityByProduct: window.QUALITY_BY_PRODUCT,
      qualityByUf:      window.QUALITY_BY_UF,
    };
    const PRODUCTS_T   = snap.products   || [];
    const PRODUCT_TS_T = snap.productTS  || {};
    const OVERVIEW_T   = snap.overviewTS || [];
    const UF_DATA_T    = snap.ufData     || [];
    const QUALITY_T    = snap.quality    || [];
    const QUALITY_TS_T = snap.qualityTs  || [];
    const TOP_MUNIS_T  = snap.topMunis   || [];
    const REGIONS_T    = snap.regions    || window.REGIONS || [];

    const allProducts = PRODUCTS_T.map(p => p.code);
    // Distinguish "no product filter applied" (basket == null → all) from
    // "explicitly cleared" (basket == [] → none). Zero always means none.
    const basket = summary.basket == null ? allProducts : summary.basket;
    const selectedProducts = basket.filter(c => allProducts.includes(c));

    const yearStart = yearOf(summary.startDate) || (OVERVIEW_T[0] && OVERVIEW_T[0].y) || 1986;
    const yearEnd   = yearOf(summary.endDate)   || (OVERVIEW_T[OVERVIEW_T.length - 1] && OVERVIEW_T[OVERVIEW_T.length - 1].y) || 2024;

    // Same null-vs-empty rule as the basket: undefined/null = "no filter"
    // (all); an explicit empty array = "none selected" (zero rows). An empty
    // Set is truthy, so the `!set ||` / `set ?` guards downstream correctly
    // resolve null→all and empty-Set→none.
    const flagSet  = summary.flags  == null ? null : new Set(summary.flags);
    const stateSet = summary.states == null ? null : new Set(summary.states);

    // ── Geography-aware aggregation (product × UF × year) ──────────────
    // The national per-product series (PRODUCT_TS_T) can honour a product basket
    // and a year window, but NOT a state filter (it has no UF grain). The snapshot's
    // ufYearly carries (UF × year) but is ALL-products (so it can honour state + year
    // but not a basket). To make VALOR TOTAL / the choropleth / the series respect
    // state + product + period TOGETHER, we pull a basket-scoped (UF × year) cube on
    // demand (window.geoYearly → /api/geo-yearly) and aggregate it client-side.
    const hasGeoData = UF_DATA_T.length > 0;
    const ufYearlyAll = Array.isArray(snap.ufYearly) ? snap.ufYearly : [];
    // A basket genuinely narrows products only when a proper, non-empty subset is
    // selected (null = all; [] = none → handled by the empty-series path below).
    const basketActive =
      hasGeoData && summary.basket != null &&
      selectedProducts.length > 0 && selectedProducts.length < allProducts.length;
    // A state filter genuinely narrows only below the canonical 27-UF universe (the
    // all-selected default is NOT a narrowing). Summing the (UF × year) grid over a
    // proper subset is the only case where it diverges from the national series.
    const _ufUniverse = (window.UF_DATA || []).length || 27;
    const stateNarrowing =
      hasGeoData && stateSet != null &&
      (stateSet.size === 0 || stateSet.size < _ufUniverse);
    // The basket-scoped cube (null until the fetch lands, or for a non-geo banco).
    // Only fetched when a basket is active — a state-only narrowing reads the
    // all-products ufYearly already in the snapshot (no extra round-trip).
    const geoCube = (basketActive && window.geoYearly)
      ? window.geoYearly(bancoId, summary) : null;
    const useCube = !!(geoCube && geoCube.length);
    // The (UF × year) source for the geo-derived series/map: the basket cube when
    // ready, else the snapshot's all-products grid (for the state-only case).
    const geoSource = useCube ? geoCube : ufYearlyAll;
    // When narrowing states, restrict to the selected UFs; with no narrowing sum the
    // WHOLE grid (incl. COMEX non-state pseudo-origins) so the national total matches
    // PRODUCT_TS_T exactly (those pseudo-origins are not selectable UFs).
    const sumStates = (rows, y) => {
      let v = 0, qMass = 0, qVol = 0;
      for (const r of rows) {
        if (r.year !== y) continue;
        if (stateNarrowing && !stateSet.has(r.uf)) continue;
        v += (r.value || 0) / 1000;     // ufYearly value is mi → ts.v is bi
        qMass += (r.q_mass || 0);        // already mil t
        qVol  += (r.q_vol  || 0);        // already mi m³
      }
      return { v, q_mass: qMass, q_vol: qVol };
    };
    // Engage the geo-derived series only when it adds correctness the national series
    // can't: a real state narrowing, OR a basket whose territorial cube has loaded —
    // and only when the (UF × year) grid actually carries rows (a snapshot without
    // ufYearly falls back to the national series rather than zeroing it out).
    const geoDerivedTs = hasGeoData && geoSource.length > 0 && (stateNarrowing || useCube);

    // ── Aggregated time series ────────────────────────────────────────
    const allYears = OVERVIEW_T.map(d => d.y).filter(y => y >= yearStart && y <= yearEnd);
    const ts = allYears.map(y => {
      if (geoDerivedTs) {
        const g = sumStates(geoSource, y);
        return { y, v: g.v, q: g.q_mass, q_mass: g.q_mass, q_vol: g.q_vol };
      }
      // National path (no state narrowing): per-product series, basket + year aware.
      let v = 0, qMass = 0, qVol = 0;
      selectedProducts.forEach(code => {
        const series = PRODUCT_TS_T[code];
        if (!series) return;
        const pt = series.find(p => p.y === y);
        if (!pt) return;
        v += pt.v / 1000;                    // productTS.v is mi → ts.v is bi
        if (pt.family === 'mass')   qMass += pt.q;
        if (pt.family === 'volume') qVol  += pt.q;
      });
      return { y, v, q: qMass, q_mass: qMass, q_vol: qVol };
    });

    // ── Per-product time series, restricted to basket + window ───────
    const productTS = {};
    selectedProducts.forEach(code => {
      const series = PRODUCT_TS_T[code];
      if (!series) return;
      productTS[code] = series.filter(d => d.y >= yearStart && d.y <= yearEnd);
    });

    // ── UF / region / municipio data ─────────────────────────────────────
    // Per-UF rows for the choropleth + ranking, restricted by the state filter and —
    // when the basket's (UF × year) cube has loaded (useCube) — by the product basket
    // too, so the map reflects the SELECTED products. Until that cube lands (or when
    // no basket is active) the map shows the snapshot's latest-year per-UF totals
    // (all products), narrowed by state. State filtering is always exact.
    // `notFilteredByBasket` stays true ONLY while a basket is active but its cube has
    // not loaded — the geo views render an honest pt-BR note for that transient. The
    // old code faked a basket × UF split by scaling every UF uniformly by selected/all
    // (fabricated geography); the cube is the REAL product × UF × year grain instead.
    const notFilteredByBasket = hasGeoData && basketActive && !useCube;
    // The ONE combination the client cannot aggregate faithfully: BOTH a product
    // basket AND a UF subset, before the product×UF×year cube has loaded. The
    // national per-product series has no UF grain; the all-products UF grid has no
    // basket grain — so the geo-derived `ts` here would sum ALL products over the
    // selected UFs, SILENTLY dropping the basket from VALOR TOTAL / YoY / acumulada.
    // We refuse to show that wrong number: flag it so the view holds the value at a
    // loading state until the cube resolves (then it computes the exact selection),
    // instead of reporting a figure that disregards the user's product filter.
    const geoComboPending = hasGeoData && basketActive && stateNarrowing && !useCube;

    // Tile-grid (col/row) join for cube-derived UF rows: the snapshot's ufData is
    // already decorated (decorate.js), but cube rows come straight from the serializer,
    // so attach col/row/name/region from the UF registry (mirrors decorateUfRows).
    const _ufTiles = {};
    (window.UF_DATA || []).forEach(u => { _ufTiles[u.uf] = u; });
    const _normRegion = window.normalizeRegion || ((api, tile) => api || tile);
    const _decorateUf = (rows) => rows.map(r => {
      const t = _ufTiles[r.uf] || {};
      // Normalize region to the canonical CODE — same as decorateUfRows — so the
      // cube-derived ufData matches the regionData groupBy (`u.region === r.id`).
      return { ...r, col: r.col ?? t.col, row: r.row ?? t.row,
               region: _normRegion(r.region, t.region), name: r.name || t.name };
    });

    // The per-(UF, year) grid backing the map + its TRUE data year: the basket cube
    // when loaded, else the snapshot's all-products grid. The map's data year is the
    // max reference_year present IN the window (NOT yearEnd) — if the endDate runs past
    // the last year with UF rows (future/partial trade year), labelling with yearEnd
    // would lie. Falls back to yearEnd when the grid is empty (synthetic/older payloads).
    const ufYearly = geoSource;
    const ufYearsInWindow = ufYearly
      .map(r => r.year)
      .filter(y => typeof y === 'number' && y >= yearStart && y <= yearEnd);
    const ufLatestYear = ufYearsInWindow.length ? Math.max(...ufYearsInWindow) : yearEnd;
    const ufData = useCube
      ? _decorateUf(
          geoCube
            .filter(r => r.year === ufLatestYear)
            .filter(u => !stateSet || stateSet.has(u.uf))
            .map(r => ({ uf: r.uf, name: r.name, region: r.region,
                         value: r.value, q_mass: r.q_mass, q_vol: r.q_vol })),
        )
      : UF_DATA_T
          .filter(u => !stateSet || stateSet.has(u.uf))
          .map(u => ({ ...u }));
    // The map year is "partial" when it falls SHORT of the requested window end — the
    // researcher asked through yearEnd but the latest UF data stops earlier (newer year
    // not yet in Gold, or an in-progress year). Lets the geo views annotate honestly.
    const ufYearPartial = hasGeoData && ufLatestYear < yearEnd;

    // The "UFs cobertas" denominator (ViewOverview/MainScreen) must be the banco's
    // ALL-TIME UF universe, not just the latest year's UFs. ufData is latest-year-
    // scoped (see above), so using it as the denominator would, on a SPARSE trade
    // year (fewer states reporting), under-count the universe. ufYearly spans every
    // covered year, so its distinct UF set IS the all-time universe — first row per
    // UF carries name/region/real for the real-UF tally. Fall back to the latest-year
    // ufData when ufYearly is absent (synthetic / older payloads). Counts are capped
    // at 27 downstream, so this only ever CORRECTS an under-count, never inflates.
    // Always derived from the ALL-products grid (ufYearlyAll), never the basket cube —
    // the denominator is the banco's FULL territorial universe, so it stays "/27"
    // rather than shrinking to the subset of UFs that happen to grow the basket.
    const ufUniverse = (() => {
      if (!ufYearlyAll.length) return UF_DATA_T;
      const seen = new Map();
      ufYearlyAll.forEach(r => { if (!seen.has(r.uf)) seen.set(r.uf, r); });
      return Array.from(seen.values());
    })();

    // productShare is NO LONGER used to scale displayed UF/region/heatmap values
    // (that fabricated geography — see above). It survives only as an ESTIMATED
    // multiplier for the hero "Linhas" provenance counter (MainScreen), where an
    // approximate row count is acceptable and clearly labelled as a selection size.
    const productShare = allProducts.length ? (selectedProducts.length / allProducts.length) : 0;

    // region totals derived from the REAL (state-filtered) ufData
    const regionData = REGIONS_T.map(r => {
      const ufs = ufData.filter(u => u.region === r.id);
      return {
        ...r,
        value:  ufs.reduce((s, u) => s + u.value,  0),
        q_mass: ufs.reduce((s, u) => s + u.q_mass, 0),
        q_vol:  ufs.reduce((s, u) => s + u.q_vol,  0),
        ufs:    ufs.length,
      };
    }).filter(r => r.ufs > 0);

    // top municipios — keep ones whose product is in basket AND uf is in stateSet
    // AND that survive the município selection. The município picker is an
    // explicit PARTIAL list of leaders, so matching is by city name (the data
    // has no município code): a city the picker can address passes only when
    // selected; a city outside the picker's universe is governed by the UF
    // filter alone. munis == null (or muniNames absent) ⇒ no município filter.
    const productNamesInBasket = new Set(
      selectedProducts.map(c => (PRODUCTS_T.find(p => p.code === c) || {}).name).filter(Boolean)
    );
    const muniNameSet = summary.muniNames == null ? null : new Set(summary.muniNames);
    const muniUniverse = window.MUNI_PICKER_NAMES || new Set();
    const topMunis = TOP_MUNIS_T
      .filter(m => productNamesInBasket.has(m.product))
      .filter(m => !stateSet || stateSet.has(m.uf))
      .filter(m => {
        if (!muniNameSet) return true;            // no município filter → all
        if (!muniUniverse.has(m.city)) return true; // unlisted leader → UF-governed
        return muniNameSet.has(m.city);           // listed → must be selected
      })
      .map(m => ({ ...m })); // values already at municipality level

    // ── Top products composition (donut / share) ─────────────────────
    // Take last endpoint from per-product TS, keep only basket products.
    const compositionRaw = selectedProducts
      .map(code => {
        const prod = PRODUCTS_T.find(p => p.code === code);
        const series = PRODUCT_TS_T[code];
        if (!prod || !series) return null;
        const lastInWindow = series.filter(d => d.y >= yearStart && d.y <= yearEnd).slice(-1)[0];
        if (!lastInWindow) return null;
        return { name: prod.name, value: lastInWindow.v };
      })
      .filter(Boolean)
      .sort((a, b) => b.value - a.value);
    const compTotal = compositionRaw.reduce((s, p) => s + p.value, 0) || 1;
    const COLORS = [...window.VIZ_SCALE, 'var(--pres-gray-300)', 'var(--pres-gray-400)'];
    let topProducts;
    if (compositionRaw.length <= 7) {
      topProducts = compositionRaw.map((p, i) => ({
        ...p, share: p.value / compTotal, color: COLORS[i % COLORS.length],
      }));
    } else {
      const head = compositionRaw.slice(0, 6);
      const tail = compositionRaw.slice(6);
      const tailVal = tail.reduce((s, p) => s + p.value, 0);
      topProducts = [
        ...head.map((p, i) => ({ ...p, share: p.value / compTotal, color: COLORS[i] })),
        { name: 'Outros', value: tailVal, share: tailVal / compTotal,
          color: 'var(--pres-gray-200)', muted: true },
      ];
    }

    // ── Quality flag distribution ─────────────────────────────────────
    const qualityFlagsAll = QUALITY_T;
    const filteredFlags = flagSet
      ? qualityFlagsAll.filter(f => flagSet.has(f.id))
      : qualityFlagsAll;
    // re-normalize shares to selected flags' world
    const flagTotal = filteredFlags.reduce((s, f) => s + f.count, 0) || 1;
    const qualityFlags = filteredFlags.map(f => ({ ...f, share: f.count / flagTotal }));

    // quality time series — pass-through, optionally trim to window
    const qualityTs = QUALITY_TS_T.filter(d => d.y >= yearStart && d.y <= yearEnd);

    // ── Row counter (for hero "SELEÇÃO ATIVA · Linhas") ────────────────
    const valueShare = valueShareForRange(summary.valueMin, summary.valueMax);
    const flagShare  = flagSet
      ? filteredFlags.reduce((s, f) => s + f.share, 0)
      : 1;
    const yearShare = (yearEnd - yearStart + 1) / ((OVERVIEW_T && OVERVIEW_T.length) || 39);
    const stateShare = stateSet ? (stateSet.size / ((UF_DATA_T && UF_DATA_T.length) || 27)) : 1;

    return {
      ts, productTS, ufData, regionData, topMunis, topProducts,
      qualityFlags, qualityTs, selectedProducts,
      yearStart, yearEnd,
      // The choropleth/tile map's TRUE data year (max UF year within the window),
      // and whether it stops short of the requested yearEnd. The geo views label the
      // map with `ufLatestYear` (not `yearEnd`) and annotate `ufYearPartial` so the
      // year shown always matches the data plotted (FINDING #1).
      ufLatestYear, ufYearPartial,
      // Banco-aware metadata so product/quality views read the ACTIVE banco's
      // dimensions instead of reaching into the PEVS globals (window.PRODUCTS …):
      products:        PRODUCTS_T,                 // active banco product list
      productsTotal:   allProducts.length,
      allProductTS:    PRODUCT_TS_T,               // full (unfiltered) per-product series
      // The banco's ALL-TIME UF universe (distinct UFs across every covered year),
      // not just the latest year's — so the "UFs cobertas" denominator never under-
      // counts on a sparse trade year. Falls back to the latest-year UF list when
      // ufYearly is absent. [] when the banco has no geography.
      ufDataFull:      ufUniverse,
      qualityByProduct: snap.qualityByProduct || [],
      qualityByUf:     snap.qualityByUf || [],
      // Honest flag for the geo views: true when a product basket is active but
      // the per-UF/region/heatmap totals are NOT narrowed by it (no per-product ×
      // UF grain in the snapshot). The views render a pt-BR note instead of
      // silently showing all-products territorial figures under a basket chip.
      notFilteredByBasket,
      // True while VALOR TOTAL/YoY/série cannot honour basket × UF simultaneously
      // (the product×UF cube is still loading) — the view shows a loading state
      // instead of a basket-dropped value. See geoComboPending above.
      geoComboPending,
      _shares: { productShare, valueShare, flagShare, yearShare, stateShare },
    };
  };
})();
