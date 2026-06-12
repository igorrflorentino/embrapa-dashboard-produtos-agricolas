// ViewProductivity — agricultural AREA × YIELD perspective. Meaningful only
// for bancos that provide the 'yield' capability (IBGE PAM). Pick a crop and
// see its national yield/area trajectory plus the per-UF productivity geography.
//
// Self-data view: it reads its own synthetic adapter (window.productivityData),
// exactly like ViewFlows/ViewSeasonality. To go live, swap that adapter's body
// for a real query against the PAM Gold table — this component does not change.
// The beta caveat banner is rendered globally by MainScreen (window.MaturityBanner),
// so it is intentionally NOT repeated here.

const { useState: useProdState } = React;

function ViewProductivity({ summary, conventions, database }) {
  const banco = window.bancoById(database);
  const [crop, setCrop] = useProdState(null);
  const data = window.productivityData(database, crop, summary);

  if (!data) {
    return (
      <div className="card subtle">
        <p className="caption" style={{ padding: '20px 4px', textAlign: 'center' }}>
          Esta fonte não expõe rendimento agrícola. Selecione um banco com a dimensão de produtividade.
        </p>
      </div>
    );
  }

  const activeCrop = data.crop.code;
  const yUnit = data.yieldUnit;

  const fmtY    = (v) => window.numBR(Math.round(v), 0) + ' ' + yUnit;
  const fmtArea = (v) => v >= 1e6 ? window.numBR(v / 1e6, 1) + ' mi ha' : window.numBR(v / 1e3, 0) + ' mil ha';
  const fmtProd = (v) => v >= 1e6 ? window.numBR(v / 1e6, 1) + ' mi t'  : window.numBR(v / 1e3, 0) + ' mil t';

  const series = data.series;
  const last = series[series.length - 1] || { y: 0, yieldKgHa: 0, areaHa: 0, prodT: 0 };
  const prev = series[series.length - 2] || last;
  const first = series[0] || last; // guard the empty loading frame (series resolves async)
  const yDelta = prev.yieldKgHa ? ((last.yieldKgHa - prev.yieldKgHa) / prev.yieldKgHa) * 100 : 0;
  const aDelta = prev.areaHa ? ((last.areaHa - prev.areaHa) / prev.areaHa) * 100 : 0;

  const mapData = data.byUF.map(u => ({ ...u, yieldKgHa: Math.round(u.yieldKgHa) }));
  const byUFTop = data.byUF.slice()
    .sort((a, b) => b.yieldKgHa - a.yieldKgHa)
    .slice(0, 12)
    .map(u => ({ uf: u.uf, name: u.name, yieldKgHa: Math.round(u.yieldKgHa) }));

  return (
    <>
      {/* Crop selector */}
      <div className="pp-selector">
        <span className="pp-selector-label">Lavoura em análise</span>
        <div className="pp-chips">
          {data.crops.map(c => (
            <button key={c.code}
                    className={'pp-chip ' + (c.code === activeCrop ? 'on' : '')}
                    onClick={() => setCrop(c.code)}>
              {c.name}
            </button>
          ))}
        </div>
      </div>

      {/* KPI strip */}
      <div className="kpi-row">
        <window.KpiCardSpark
          label={<>Rendimento nacional · <window.UnitFamilyTag family="rendimento" conv={conventions}/></>}
          value={fmtY(last.yieldKgHa)}
          delta={window.fmtSigned(yDelta)}
          deltaPositive={yDelta >= 0}
          sub={`${last.y} vs. ${prev.y}`}
          spark={series.slice(-12).map(d => ({ y: d.y, v: d.yieldKgHa }))}
          sparkKey="v"
          sparkColor="var(--viz-6)"
        />
        <window.KpiCardSpark
          label="Área colhida"
          value={fmtArea(last.areaHa)}
          delta={window.fmtSigned(aDelta)}
          deltaPositive={aDelta >= 0}
          sub={`safra ${last.y}`}
          spark={series.slice(-12).map(d => ({ y: d.y, v: d.areaHa }))}
          sparkKey="v"
          sparkColor="var(--viz-10)"
        />
        <window.KpiCardSpark
          label="Produção"
          value={fmtProd(last.prodT)}
          sub={`rendimento × área · ${last.y}`}
          spark={series.slice(-12).map(d => ({ y: d.y, v: d.prodT }))}
          sparkKey="v"
          sparkColor="var(--viz-2)"
        />
        <window.KpiCardSpark
          label="CAGR do rendimento"
          value={window.fmtSigned(data.national.yieldCagr)}
          sub={`ganho de produtividade · ${first.y}–${last.y}`}
          spark={series.slice(-12).map(d => ({ y: d.y, v: d.yieldKgHa }))}
          sparkKey="v"
          sparkColor="var(--viz-7)"
        />
      </div>

      {/* National yield + area trajectories */}
      <div className="grid-2">
        <div className="card">
          <window.SectionHeader
            overline={`Rendimento médio · ${yUnit}`}
            title={`${data.crop.name} · produtividade nacional`}
          />
          <window.LineChart
            data={series.map(d => ({ y: d.y, v: Math.round(d.yieldKgHa) }))}
            label={yUnit} valueKey="v" color="var(--viz-6)" height={230} />
        </div>
        <div className="card">
          <window.SectionHeader
            overline={`Área colhida · ${data.areaUnit}`}
            title={`${data.crop.name} · área colhida`}
          />
          <window.LineChart
            data={series.map(d => ({ y: d.y, v: Math.round(d.areaHa) }))}
            label={data.areaUnit} valueKey="v" color="var(--viz-10)" height={230} />
        </div>
      </div>

      {/* Per-UF productivity geography */}
      <div className="grid-2">
        <div className="card">
          <window.SectionHeader
            overline={`Produtividade por UF · ${last.y}`}
            title={`Onde ${data.crop.name} rende mais`}
            action={<span className="caption">{yUnit}</span>}
          />
          <window.BrazilTileMap data={mapData} valueKey="yieldKgHa" label={yUnit} height={420} />
        </div>
        <div className="card">
          <window.SectionHeader
            overline={`Ranking de rendimento · ${last.y}`}
            title="UFs mais produtivas"
            action={<span className="caption">Top 12 · {yUnit}</span>}
          />
          <window.BarChart data={byUFTop} valueKey="yieldKgHa" color="var(--viz-6)" height={360} />
        </div>
      </div>
    </>
  );
}

window.ViewProductivity = ViewProductivity;
