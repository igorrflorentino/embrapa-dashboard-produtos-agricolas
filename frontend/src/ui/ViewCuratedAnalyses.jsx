// ─── FROZEN FEATURE: curated analyses (Curadoria) — postponed to "Versão Futura" ──
// Leadership decision (2026-06): partially built + not yet validated. The two views
// (Valor agregado / Finalidade econômica) are hidden from the topnav (views.js) and
// the app runs fully decoupled. Kept as the scaffold for the real future
// implementation — do not delete. They degrade to an honest empty state when the
// curation data is absent.
//
// ViewCuratedAnalyses.jsx — analyses POWERED BY the enrichment layer. They
// subscribe to the store, so editing the Curadoria re-renders them live.
//   · ViewValueAdded   — exports split by industrialization (bruta × processada)
//   · ViewMarketNature — trade value by curated economic purpose (consumo × processamento)
// Both read real Gold/COMTRADE data; the curated split comes from Engenharia de
// atributos and an empty classification shows an honest "classify first" state.

const { useState: useCaState, useEffect: useCaEffect } = React;

function useEnrichmentTick() {
  const [, force] = useCaState(0);
  useCaEffect(() => window.enrichment.subscribe(() => force(n => n + 1)), []);
}

const caNum = window.numBR, caPct = window.pctBR;

// ── Value added: bruta × processada ───────────────────────────────────
function ViewValueAdded() {
  useEnrichmentTick();
  const [group, setGroup] = useCaState(null);
  // Per-UF scoping ('' = Brasil). The COMEX export side honours it.
  const [uf, setUf] = useCaState('');
  const data = window.valueAddedAnalysis(group, uf ? [uf] : undefined);
  const last = data.series[data.series.length - 1];
  const first = data.series[0];

  const areaSeries = [
    { name: 'Bruta', color: 'var(--viz-3)', data: data.byLevel.bruta },
    { name: 'Processada', color: 'var(--viz-2)', data: data.byLevel.processada },
  ];
  // Volume composition (mil t) — the same bruta×processada split, by weight.
  const areaSeriesW = [
    { name: 'Bruta', color: 'var(--viz-3)', data: (data.byLevelWeight || { bruta: [] }).bruta },
    { name: 'Processada', color: 'var(--viz-2)', data: (data.byLevelWeight || { processada: [] }).processada },
  ];
  // Absolute unit price per level (US$/kg) — not just the premium ratio.
  const priceSeries = [
    { name: 'Bruta', color: 'var(--viz-3)', data: data.series.map(d => ({ y: d.y, v: d.priceBruta })) },
    { name: 'Processada', color: 'var(--viz-2)', data: data.series.map(d => ({ y: d.y, v: d.priceProc })) },
  ];
  const shareTs = data.series.map(d => ({ y: d.y, v: d.procShare }));

  return (
    <>
      <div className="pp-selector">
        <span className="pp-selector-label">Commodity</span>
        <div className="pp-chips">
          <button className={'pp-chip ' + (!group ? 'on' : '')} onClick={() => setGroup(null)}
            style={!group ? { background: 'var(--embrapa-green)', borderColor: 'var(--embrapa-green)', color: '#fff' } : null}>Todas curadas</button>
          {window.ENRICH_GROUPS.map(g => {
            const on = group === g.id;
            return (
              <button key={g.id} className={'pp-chip ' + (on ? 'on' : '')} onClick={() => setGroup(g.id)}
                style={on ? { background: 'var(--embrapa-green)', borderColor: 'var(--embrapa-green)', color: '#fff' } : null}>{g.label}</button>
            );
          })}
        </div>
      </div>

      <window.UfScopePicker value={uf} onChange={setUf} />

      <div className="kpi-row">
        <window.KpiCardSpark label="Exportação processada" value={caPct(last?.procShare)} sub={`${last?.y ?? '—'} · do valor exportado`} />
        <window.KpiCardSpark label="Variação na janela" value={window.fmtSigned((last?.procShare || 0) - (first?.procShare || 0), 1, ' p.p.')} deltaPositive={(last?.procShare || 0) >= (first?.procShare || 0)} sub={`${first?.y ?? '—'}–${last?.y ?? '—'}`} />
        <window.KpiCardSpark label="Prêmio do processado" value={'×' + caNum(last?.premium, 1)} sub="preço processada ÷ bruta" />
        <window.KpiCardSpark label="Códigos na análise" value={data.nCodes} sub="incluídos e classificados" />
      </div>

      <div className="card">
        <window.SectionHeader overline="Valor exportado por nível · US$ bi" title="Quanto sai bruto e quanto sai processado"
          action={<span className="caption">classificação da Curadoria</span>} />
        {data.nCodes < 1 ? (
          <p className="caption" style={{ padding: '24px 4px', textAlign: 'center' }}>
            Nenhum código bruto/processado incluído para esta seleção. Ajuste em <strong>Engenharia de atributos → Nível de industrialização</strong>.
          </p>
        ) : (
          <>
            <window.StackedArea series={areaSeries} valueKey="v" label="US$ bi" height={300} />
            <div className="pc-legend">
              {areaSeries.map(s => (
                <span key={s.name} className="pc-legend-item"><span className="pc-legend-dot" style={{ background: s.color }}></span>{s.name}</span>
              ))}
            </div>
          </>
        )}
      </div>

      {data.nCodes >= 1 && (
        <div className="card">
          <window.SectionHeader overline="Volume exportado por nível · mil t" title="Quanto sai bruto e quanto sai processado (em peso)"
            action={<span className="caption">{caPct(last?.procShareW)} processado em {last?.y ?? '—'}</span>} />
          <window.StackedArea series={areaSeriesW} valueKey="v" label="mil t" height={260} />
          <div className="pc-legend">
            {areaSeriesW.map(s => (
              <span key={s.name} className="pc-legend-item"><span className="pc-legend-dot" style={{ background: s.color }}></span>{s.name}</span>
            ))}
          </div>
        </div>
      )}

      {data.nCodes >= 1 && (
        <div className="card">
          <window.SectionHeader overline="Preço médio por nível · US$/kg" title="Quanto vale o quilo bruto vs. processado"
            action={<span className="caption">prêmio ×{caNum(last?.premium, 1)}</span>} />
          <window.MultiLineChart series={priceSeries} valueKey="v" label="US$/kg" height={260} trend />
          <p className="caption" style={{ padding: '8px 4px 0' }}>
            O prêmio do processado é o quociente destes dois preços — agregar valor é vender o quilo mais caro.
          </p>
        </div>
      )}

      <div className="card">
        <window.SectionHeader overline="Participação do processado no tempo" title="A pauta está agregando mais valor?"
          action={<span className="caption">% · valor processado ÷ total</span>} />
        <window.LineChart data={shareTs} valueKey="v" label="% processado" color="var(--viz-2)" height={240} />
        <p className="caption" style={{ padding: '8px 4px 0' }}>
          Reclassifique um código entre <strong>bruta</strong> e <strong>processada</strong> em <strong>Engenharia de atributos → Nível de industrialização</strong> e esta análise se atualiza —
          é o conhecimento do pesquisador entrando no dado.
        </p>
      </div>
    </>
  );
}

// ── Economic purpose: consume × process ───────────────────────────────
function ViewMarketNature() {
  useEnrichmentTick();
  const [group, setGroup] = useCaState(null);
  window.enrichment.worklist(); // kick the code worklist so ENRICH_GROUPS (the commodity chips) populates
  const data = window.marketNatureAnalysis(group);

  // Scope the analysis to one commodity's COMTRADE codes (or all curated).
  const selector = (
    <div className="pp-selector">
      <span className="pp-selector-label">Commodity</span>
      <div className="pp-chips">
        <button className={'pp-chip ' + (!group ? 'on' : '')} onClick={() => setGroup(null)}
          style={!group ? { background: 'var(--embrapa-green)', borderColor: 'var(--embrapa-green)', color: '#fff' } : null}>Todas curadas</button>
        {window.ENRICH_GROUPS.map(g => {
          const on = group === g.id;
          return (
            <button key={g.id} className={'pp-chip ' + (on ? 'on' : '')} onClick={() => setGroup(g.id)}
              style={on ? { background: 'var(--embrapa-green)', borderColor: 'var(--embrapa-green)', color: '#fff' } : null}>{g.label}</button>
          );
        })}
      </div>
    </div>
  );

  // Curated-real: the series is EMPTY until the researcher classifies customs×flow
  // pairs in Curadoria (or while the fetch is in flight). Guard before reading
  // series[0]/latest — show an honest "classify first" state, never a crash or
  // synthetic chart. (preview only flips true if a trade banco isn't live.)
  if (!data.series || !data.series.length) {
    return (
      <>
        {selector}
        <div className="card subtle">
          <window.SectionHeader overline="Valor por finalidade econômica · US$ bi"
            title="Classifique os pares regime × fluxo para ativar esta análise" />
          <p className="caption" style={{ padding: '24px 4px', textAlign: 'center' }}>
            Nenhum par <strong>regime aduaneiro × fluxo</strong> classificado ainda. Defina a
            finalidade (consumo ou processamento) de cada par em{' '}
            <strong>Engenharia de atributos → Tipo de Mercado</strong> — esta análise passa a somar o
            valor do COMTRADE por finalidade, ao vivo.
          </p>
        </div>
      </>
    );
  }

  const L = data.latest;
  const total = window.ENRICH_MARKETS.reduce((s, m) => s + (L[m.id] || 0), 0) || 1;
  const areaSeries = window.ENRICH_MARKETS.map(m => ({
    name: m.short, color: m.color, data: data.series.map(d => ({ y: d.y, v: d[m.id] })),
  }));
  const donut = window.ENRICH_MARKETS.map(m => ({
    name: m.short, value: L[m.id], share: L[m.id] / total, color: m.color,
  }));

  return (
    <>
      {selector}

      <div className="kpi-row">
        {window.ENRICH_MARKETS.map(m => (
          <window.KpiCardSpark key={m.id} label={m.label}
            value={'US$ ' + caNum(L[m.id], 1) + ' bi'}
            sub={caPct((L[m.id] / total) * 100) + ' do total'} />
        ))}
        <window.KpiCardSpark label="Janela" value={`${data.series[0].y}–${L.y}`} sub="cobertura comparável" />
      </div>

      <div className="card">
        <window.SectionHeader overline="Valor por finalidade econômica · US$ bi" title="Comprando/vendendo para consumir ou para processar"
          action={<span className="caption">classificação da Curadoria</span>} />
        <window.StackedArea series={areaSeries} valueKey="v" label="US$ bi" height={300} />
        <div className="pc-legend">
          {areaSeries.map(s => (
            <span key={s.name} className="pc-legend-item"><span className="pc-legend-dot" style={{ background: s.color }}></span>{s.name}</span>
          ))}
        </div>
      </div>

      <div className="card">
        <window.SectionHeader overline={`Composição · ${L.y}`} title="Quanto vai para consumo vs. processamento" />
        <window.Donut data={donut} valueKey="share" size={170} />
        <p className="caption" style={{ padding: '8px 4px 0' }}>
          A direção (comprar/vender) vem do fluxo; a <strong>finalidade</strong> (consumo ou processamento) vem da Curadoria.
          Reclassifique um par regime × fluxo e esta análise se atualiza.
        </p>
      </div>
    </>
  );
}

Object.assign(window, { ViewValueAdded, ViewMarketNature });
