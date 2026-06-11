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

  const [dim, setDim]     = useGeoState('value');
  const [scope, setScope] = useGeoState('uf');
  const [ufViz, setUfViz] = useGeoState('map'); // 'map' = maplibre choropleth, 'tiles' = SVG tile-grid

  const massFamily = families.includes('mass');
  const volFamily  = families.includes('volume');

  // Dimensions with active unit label
  const dims = [
    { id: 'value',  label: 'Valor',              key: 'value',  unit: valueUnitLabel, mul: valueMul, available: true },
    { id: 'mass',   label: 'Quantidade (massa)', key: 'q_mass', unit: massUnitLabel,  mul: massMul,  available: massFamily },
    { id: 'volume', label: 'Quantidade (volume)',key: 'q_vol',  unit: volUnitLabel,   mul: volMul,   available: volFamily },
  ].filter(d => d.available);

  // If the active dimension is no longer available (e.g. the basket changed
  // from a mixed cesta to mass-only), reset to the first available one.
  // Done in an effect — never call setState during render.
  useGeoEffect(() => {
    if (!dims.find(d => d.id === dim)) setDim(dims[0].id);
  }, [dim, massFamily, volFamily]);
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

  // Heatmap: year × UF
  const heatRows = useGeoMemo(() => {
    const ts = filtered.ts;
    if (!ts.length) return [];
    const tsMax = Math.max(...ts.map(d => d.v), 1);
    return scaledUFs
      .slice()
      .sort((a, b) => b[valueKey] - a[valueKey])
      .slice(0, 12)
      .map(u => ({
        id: u.uf,
        label: `${u.uf} · ${u.name}`,
        values: ts.map(t => ({ y: t.y, v: Math.round(u[valueKey] * (t.v / tsMax) * 100) / 100 })),
      }));
  }, [valueKey, scaledUFs]);

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
    const CURRENCY_SYMS = ['R$', 'US$', '€', '¥'];
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
          overline={`Mapa de calor · ${activeDim.label} · ${displayUnit} · ${filtered.yearEnd}`}
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
            title={`Maiores estados produtores · ${filtered.yearEnd}`}
            action={<span className="caption">{activeDim.label} ({top10Scaled.label})</span>}
          />
          <window.BarChart data={top10Scaled.data} valueKey={valueKey} color="var(--viz-2)" height={320} />
        </div>
        <div className="card">
          <window.SectionHeader
            overline={`${activeDim.label} · ${filtered.yearEnd}`}
            title="Soma por região"
            action={<span className="caption">{regScaled.data.length} macrorregiões · {regScaled.label}</span>}
          />
          <window.RegionBars data={regScaled.data} valueKey={valueKey} label={regScaled.label} height={320} />
        </div>
      </div>
    </>
  );
}

window.ViewGeography = ViewGeography;
