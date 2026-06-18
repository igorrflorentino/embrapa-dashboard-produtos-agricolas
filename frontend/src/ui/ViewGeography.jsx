// ViewGeography — territorial distribution of production, value and volume.
// All scales come from the global metric conventions (props.conventions).

const { useState: useGeoState, useMemo: useGeoMemo, useEffect: useGeoEffect } = React;

function ViewGeography({ families, conventions, summary, database }) {
  const conv     = conventions || window.DEFAULT_CONVENTIONS;
  // UF_DATA.value is in the banco's OWN base currency (mi) internally — scale by
  // 1e6 to absolute, then convert base→display through the base-aware factor.
  // For a USD-native banco (COMEX/Comtrade) the plain convFactor would leave a
  // US$ magnitude under R$ once the display switches to BRL; base=BRL (PEVS/
  // SEFAZ) routes through convFactor verbatim, so that path is unchanged.
  // UF_DATA.q_mass is in mil t internally; UF_DATA.q_vol is in mi m³.
  const baseCcy  = window.canonCurrencyFor ? window.canonCurrencyFor(database) : 'BRL';
  const valueMul = window.convFactorFor(baseCcy, conv) * 1e6;  // mi → absolute, base-aware
  const massMul  = window.massQtyMul(conv);   // 1e3 (t) or 1e6 (kg)
  const volMul   = window.volumeQtyMul(conv); // 1e6 (m³) or 1e9 (L)
  const valueUnitLabel = window.valueAxisLabel(conv); // "R$" / "US$" / etc.
  const massUnitLabel  = window.massAxisLabel(conv);  // "t" or "kg"
  const volUnitLabel   = window.volumeAxisLabel(conv);// "m³" or "L"

  const filtered = window.applyFilters(summary || {}, database);
  // The per-UF maps/bars are scoped to the latest UF year IN the window, which can
  // fall short of yearEnd (future/partial endDate). Label them with the data's OWN
  // year so the caption never diverges from what's plotted (FINDING #1).
  const mapYear     = filtered.ufLatestYear != null ? filtered.ufLatestYear : filtered.yearEnd;
  // "(parcial)" when the UF data lags the window end (ufYearPartial) OR the map year
  // is the calendar-incomplete latest year (a monthly banco's current year — the same
  // FINDING #3 signal the Overview uses), so the map is as honest as the time series.
  const geoLatest   = (window.dataStore && window.dataStore.meta)
    ? (window.dataStore.meta(database) || {}).latest : null;
  const mapYearCalPartial = !!geoLatest && geoLatest.yearComplete === false &&
    (geoLatest.completeYear == null || mapYear > geoLatest.completeYear);
  const mapPartial  = filtered.ufYearPartial || mapYearCalPartial;
  const mapYearTag  = mapPartial ? `${mapYear} (parcial)` : `${mapYear}`;

  const [dim, setDim]     = useGeoState('value');
  const [scope, setScope] = useGeoState('uf');
  const [ufViz, setUfViz] = useGeoState('map'); // 'map' = maplibre choropleth, 'tiles' = SVG tile-grid

  const massFamily = families.includes('mass');
  const volFamily  = families.includes('volume');

  // A quantity dimension is only offered when the per-UF rows actually CARRY it —
  // gating on the basket family alone (the old behaviour) offered a toggle that
  // rendered an all-zero map for a banco whose per-UF reader returns no quantity.
  // We require both the family AND at least one non-zero per-UF value.
  const hasUfQty = (key) =>
    Array.isArray(filtered.ufData) && filtered.ufData.some(u => (u[key] || 0) > 0);
  const massAvail = massFamily && hasUfQty('q_mass');
  const volAvail  = volFamily  && hasUfQty('q_vol');
  // The family is in the basket but the per-UF grain has no quantity → tell the
  // researcher honestly instead of silently dropping the toggle or showing zeros.
  const massUnavailNote = massFamily && !massAvail;
  const volUnavailNote  = volFamily  && !volAvail;

  // Dimensions with active unit label
  const dims = [
    { id: 'value',  label: 'Valor',              key: 'value',  unit: valueUnitLabel, mul: valueMul, available: true },
    { id: 'mass',   label: 'Quantidade (massa)', key: 'q_mass', unit: massUnitLabel,  mul: massMul,  available: massAvail },
    { id: 'volume', label: 'Quantidade (volume)',key: 'q_vol',  unit: volUnitLabel,   mul: volMul,   available: volAvail },
  ].filter(d => d.available);

  // If the active dimension is no longer available (e.g. the basket changed
  // from a mixed cesta to mass-only), reset to the first available one.
  // Done in an effect — never call setState during render.
  useGeoEffect(() => {
    if (!dims.find(d => d.id === dim)) setDim(dims[0].id);
  }, [dim, massAvail, volAvail]);
  const activeDim = dims.find(d => d.id === dim) || dims[0];
  const valueKey  = activeDim.key;
  const unit      = activeDim.unit;
  const mul       = activeDim.mul;

  // Scale geo datasets according to active dimension's multiplier
  const scaledUFs = useGeoMemo(
    () => filtered.ufData.map(u => ({ ...u, [valueKey]: u[valueKey] * mul })),
    [valueKey, mul, filtered]
  );
  const scaledRegions = useGeoMemo(
    () => filtered.regionData.map(r => ({ ...r, [valueKey]: r[valueKey] * mul })),
    [valueKey, mul, filtered]
  );
  const scaledMunis = useGeoMemo(
    () => filtered.topMunis.map(m => ({ ...m, [valueKey]: (m[valueKey] || 0) * mul })),
    [valueKey, mul, filtered]
  );

  // Heatmap: ano × UF — REAL per-(UF, year) Gold history from the snapshot's
  // ufYearly (the serving marts are at the reference_year × uf grain). The old
  // code FABRICATED each UF's curve as ufTotal × (national year value ÷ max),
  // giving every state the identical national trajectory — invented evolution
  // presented as real history. We now read the real rows, honor the year window +
  // state set (the UFs present in filtered.ufData) and use the ACTIVE dimension's
  // metric/scale. We do NOT re-apply a basket productShare here: there is no per-
  // product × UF×year grain, and uniformly scaling every real cell by selected/all
  // would re-inject the same fabrication F1.5 removed from the maps. When a basket
  // is active the view shows an honest pt-BR note (notFilteredByBasket) that the
  // territorial split reflects all products.
  const heatRows = useGeoMemo(() => {
    const snap = (window.dataStore && window.dataStore.get)
      ? window.dataStore.get(database) : null;
    const yearly = (snap && Array.isArray(snap.ufYearly)) ? snap.ufYearly : [];
    if (!yearly.length) return [];
    // Only the UFs that survived the state filter (filtered.ufData is already
    // state-filtered), ranked by the active dimension's total — keep the top 12.
    const keepUf = new Set(scaledUFs.map(u => u.uf));
    const order = scaledUFs
      .slice()
      .sort((a, b) => b[valueKey] - a[valueKey])
      .slice(0, 12)
      .map(u => u.uf);
    const byUf = {};
    yearly.forEach(r => {
      if (!keepUf.has(r.uf)) return;
      if (r.year < filtered.yearStart || r.year > filtered.yearEnd) return;
      const row = byUf[r.uf] || (byUf[r.uf] = { id: r.uf, name: r.name, values: [] });
      // mul applies the active dimension's display scale (value/mass/vol); the
      // cell value is the REAL per-(UF, year) figure, never basket-rescaled.
      row.values.push({ y: r.year, v: (r[valueKey] || 0) * mul });
    });
    return order
      .filter(uf => byUf[uf])
      .map(uf => ({
        id: uf,
        label: `${uf} · ${byUf[uf].name || uf}`,
        values: byUf[uf].values.slice().sort((a, b) => a.y - b.y),
      }));
  }, [valueKey, mul, scaledUFs, filtered, database]);

  const top10ufs = scaledUFs.slice().sort((a, b) => b[valueKey] - a[valueKey]).slice(0, 10);

  // ---- Auto-scale all geo datasets to a shared factor (when ON) -----
  const sharedMax = Math.max(...scaledUFs.map(u => u[valueKey] || 0));
  const ufScaled    = window.scaleSeries(scaledUFs,    sharedMax, conv, valueKey, unit);
  const regScaled   = window.scaleSeries(scaledRegions, Math.max(...scaledRegions.map(r => r[valueKey] || 0)), conv, valueKey, unit);
  const top10Scaled = window.scaleSeries(top10ufs,     sharedMax, conv, valueKey, unit);
  const muniMax     = Math.max(...scaledMunis.map(m => m[valueKey] || 0));
  const muniScaled  = window.scaleSeries(scaledMunis,  muniMax,   conv, valueKey, unit);
  const heatMax     = Math.max(...heatRows.flatMap(r => r.values.map(v => v.v)));
  const heatScaled  = (() => {
    if (!conv.autoScale) return { rows: heatRows, label: unit };
    const { factor, suffix } = window.autoScaleNum(heatMax);
    if (!suffix) return { rows: heatRows, label: unit };
    const CURRENCY_SYMS = ['R$', 'US$', '€'];
    const label = CURRENCY_SYMS.includes(unit) ? `${unit} ${suffix}` : `${suffix} ${unit}`.trim();
    return {
      rows: heatRows.map(r => ({
        ...r,
        values: r.values.map(v => ({ ...v, v: v.v / factor })),
      })),
      label,
    };
  })();
  const displayUnit = ufScaled.label;

  return (
    <>
      <window.UnitFamilyBanner families={families} />

      {filtered.notFilteredByBasket && (
        <div className="card subtle" style={{ marginBottom: 12 }}>
          <p className="caption" style={{ padding: '10px 12px' }}>
            A distribuição territorial reflete <strong>todos os produtos</strong> do banco —
            a cesta selecionada não recorta o mapa por UF/região (não há grão produto × UF nesta
            agregação). Para a distribuição de um produto específico, use a perspectiva
            <strong> Perfil do produto</strong>.
          </p>
        </div>
      )}
      {(massUnavailNote || volUnavailNote) && (
        <div className="card subtle" style={{ marginBottom: 12 }}>
          <p className="caption" style={{ padding: '10px 12px' }}>
            {massUnavailNote && volUnavailNote
              ? 'As quantidades por UF (massa e volume) ainda não estão disponíveis nesta fonte — apenas o valor é exibido no mapa.'
              : massUnavailNote
                ? 'A quantidade por UF (massa) ainda não está disponível nesta fonte — apenas o valor é exibido no mapa.'
                : 'A quantidade por UF (volume) ainda não está disponível nesta fonte — apenas o valor é exibido no mapa.'}
          </p>
        </div>
      )}

      <div className="geo-controls">
        <div className="geo-control-grp">
          <span className="overline">Métrica</span>
          <div className="seg">
            {dims.map(d => (
              <button key={d.id}
                      className={'seg-opt ' + (dim === d.id ? 'on' : '')}
                      onClick={() => setDim(d.id)}>
                {d.label}
              </button>
            ))}
          </div>
        </div>
        <div className="geo-control-grp">
          <span className="overline">Granularidade</span>
          <div className="seg">
            <button className={'seg-opt ' + (scope === 'region' ? 'on' : '')} onClick={() => setScope('region')}>Região</button>
            <button className={'seg-opt ' + (scope === 'uf' ? 'on' : '')} onClick={() => setScope('uf')}>UF</button>
            <button className={'seg-opt ' + (scope === 'municipio' ? 'on' : '')} onClick={() => setScope('municipio')}>Município</button>
          </div>
        </div>
      </div>

      <div className="card">
        <window.SectionHeader
          overline={`Mapa de calor · ${activeDim.label} · ${displayUnit} · ${mapYearTag}`}
          title={
            scope === 'region' ? 'Distribuição por região' :
            scope === 'uf'     ? 'Distribuição por UF' :
                                 'Distribuição por município (top)'
          }
        />
        {scope === 'region' && <window.RegionBars data={regScaled.data} valueKey={valueKey} label={regScaled.label} height={280} />}
        {scope === 'uf' && (
          <>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
              <div className="seg">
                <button className={'seg-opt ' + (ufViz === 'map' ? 'on' : '')} onClick={() => setUfViz('map')}>Mapa</button>
                <button className={'seg-opt ' + (ufViz === 'tiles' ? 'on' : '')} onClick={() => setUfViz('tiles')}>Blocos</button>
              </div>
            </div>
            {ufViz === 'map'
              ? <window.BrazilChoropleth data={ufScaled.data} valueKey={valueKey} label={displayUnit} />
              : <window.BrazilTileMap data={ufScaled.data} valueKey={valueKey} label={displayUnit} />}
            {filtered.ufYearPartial && (
              <p className="caption" style={{ padding: '8px 4px 0' }}>
                <strong>{mapYear} (parcial):</strong> o último ano com dados por UF disponíveis fica
                antes do fim do período selecionado ({filtered.yearEnd}). O mapa mostra {mapYear},
                o ano mais recente com cobertura territorial.
              </p>
            )}
          </>
        )}
        {scope === 'municipio' && (
          <div className="muni-list">
            {muniScaled.data
              .filter(m => valueKey === 'value' || (m[valueKey] != null && m[valueKey] > 0))
              .map((m, i, arr) => {
                const max = Math.max(...arr.map(x => x[valueKey] || 0));
                const v = m[valueKey] || 0;
                return (
                  <div key={m.city + m.uf} className="muni-row">
                    <span className="muni-rank tnum">#{i + 1}</span>
                    <span className="muni-name">{m.city}</span>
                    <span className="muni-uf">{m.uf}</span>
                    <span className="muni-product">{m.product}</span>
                    <div className="muni-bar"><div style={{ width: ((v / max) * 100).toFixed(1) + '%', background: 'var(--viz-2)' }}></div></div>
                    <span className="muni-val tnum">{v.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} {muniScaled.label}</span>
                  </div>
                );
              })}
          </div>
        )}
      </div>

      <div className="card">
        <window.SectionHeader
          overline={`Evolução temporal · ${activeDim.label} (${heatScaled.label})`}
          title={`Mapa de calor · ano × UF (${heatScaled.rows.length} maiores)`}
        />
        <window.Heatmap rows={heatScaled.rows} valueKey="v" valueLabel={heatScaled.label} />
      </div>

      <div className="grid-2">
        <div className="card">
          <window.SectionHeader
            overline={`Top 10 · ${activeDim.label}`}
            title={`Maiores estados produtores · ${mapYearTag}`}
            action={<span className="caption">{activeDim.label} ({top10Scaled.label})</span>}
          />
          <window.BarChart data={top10Scaled.data} valueKey={valueKey} color="var(--viz-2)" height={320} />
        </div>
        <div className="card">
          <window.SectionHeader
            overline={`${activeDim.label} · ${mapYearTag}`}
            title="Soma por região"
            action={<span className="caption">{regScaled.data.length} macrorregiões · {regScaled.label}</span>}
          />
          <window.RegionBars data={regScaled.data} valueKey={valueKey} label={regScaled.label} height={320} />
        </div>
      </div>

      {/* Base de dados — products ranked WITHIN the selected UF(s). The inverse of
          "onde X é produzido": here a state is fixed and the products are ranked.
          Only shown when a UF is selected (the per-(product × UF) grain the rest of
          this view lacks comes from the dedicated /api/products-by-uf reader). */}
      {summary && Array.isArray(summary.states) && summary.states.length > 0 && (() => {
        const pbu = window.productsByUf(database, summary, conv);
        const rows = (pbu.products || [])
          .map(p => ({ ...p, [valueKey]: (p[valueKey] || 0) * mul }))
          .filter(r => (r[valueKey] || 0) > 0)
          .sort((a, b) => b[valueKey] - a[valueKey])
          .slice(0, 20);
        if (!rows.length) return null;
        const scaled = window.scaleSeries(rows, Math.max(...rows.map(r => r[valueKey] || 0)), conv, valueKey, unit);
        return (
          <div className="card">
            <window.SectionHeader
              overline={`Base de dados · ${activeDim.label} · ${scaled.label}`}
              title={`Produtos do estado (${summary.states.join(', ')})`}
              action={<span className="caption">{rows.length} produtos · ranking por {activeDim.label.toLowerCase()}</span>}
            />
            <window.BarChart data={scaled.data} valueKey={valueKey} color="var(--viz-4)" height={Math.max(240, rows.length * 26)} />
          </div>
        );
      })()}
    </>
  );
}

window.ViewGeography = ViewGeography;
