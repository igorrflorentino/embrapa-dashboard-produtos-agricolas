// ViewCuratedAnalyses.jsx — analyses POWERED BY the enrichment layer. They
// subscribe to the store, so editing the Curadoria re-renders them live.
//   · ViewValueAdded   — exports split by industrialization (bruta × processada)
//   · ViewMarketNature — trade value by curated economic purpose (consumo × processamento)
// Both render synthetic preview until the trade bancos are live.

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
  const data = window.valueAddedAnalysis(group);
  const banco = window.bancoById('mdic_comex');
  const last = data.series[data.series.length - 1];
  const first = data.series[0];

  const areaSeries = [
    { name: 'Bruta', color: 'var(--viz-3)', data: data.byLevel.bruta },
    { name: 'Processada', color: 'var(--viz-2)', data: data.byLevel.processada },
  ];
  const shareTs = data.series.map(d => ({ y: d.y, v: d.procShare }));

  return (
    <>
      {data.preview && <window.PreviewBanner banco={banco}
        capabilityNote="Exportação por código entra como demonstração até o MDIC ser ligado; a classificação bruta/processada vem da Curadoria e pode ser editada lá." />}

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

      <div className="kpi-row">
        <window.KpiCardSpark label="Exportação processada" value={caPct(last?.procShare)} sub={`${last?.y} · do valor exportado`} />
        <window.KpiCardSpark label="Variação na janela" value={window.fmtSigned((last?.procShare || 0) - (first?.procShare || 0), 1, ' p.p.')} deltaPositive={(last?.procShare || 0) >= (first?.procShare || 0)} sub={`${first?.y}–${last?.y}`} />
        <window.KpiCardSpark label="Prêmio do processado" value={'×' + caNum(last?.premium, 1)} sub="preço processada ÷ bruta" />
        <window.KpiCardSpark label="Códigos na análise" value={data.nCodes} sub="incluídos e classificados" />
      </div>

      <div className="card">
        <window.SectionHeader overline="Valor exportado por nível · US$ bi" title="Quanto sai bruto e quanto sai processado"
          action={<span className="caption">classificação da Curadoria</span>} />
        {data.nCodes < 1 ? (
          <p className="caption" style={{ padding: '24px 4px', textAlign: 'center' }}>
            Nenhum código bruto/processado incluído para esta seleção. Ajuste em <strong>Curadoria</strong>.
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

      <div className="card">
        <window.SectionHeader overline="Participação do processado no tempo" title="A pauta está agregando mais valor?"
          action={<span className="caption">% · valor processado ÷ total</span>} />
        <window.LineChart data={shareTs} valueKey="v" label="% processado" color="var(--viz-2)" height={240} />
        <p className="caption" style={{ padding: '8px 4px 0' }}>
          Reclassifique um código entre <strong>bruta</strong> e <strong>processada</strong> na Curadoria e esta análise se atualiza —
          é o conhecimento do pesquisador entrando no dado.
        </p>
      </div>
    </>
  );
}

// ── Economic purpose: consume × process ───────────────────────────────
function ViewMarketNature() {
  useEnrichmentTick();
  const data = window.marketNatureAnalysis();
  const banco = window.bancoById('mdic_comex');

  // Curated-real: the series is EMPTY until the researcher classifies customs×flow
  // pairs in Curadoria (or while the fetch is in flight). Guard before reading
  // series[0]/latest — show an honest "classify first" state, never a crash or
  // synthetic chart. (preview only flips true if a trade banco isn't live.)
  if (!data.series || !data.series.length) {
    return (
      <>
        {data.preview && <window.PreviewBanner banco={banco}
          capabilityNote="A finalidade (consumo/processamento) de cada par procedimento aduaneiro × fluxo vem da Curadoria." />}
        <div className="card subtle">
          <window.SectionHeader overline="Valor por finalidade econômica · US$ bi"
            title="Classifique os pares aduana × fluxo para ativar esta análise" />
          <p className="caption" style={{ padding: '24px 4px', textAlign: 'center' }}>
            Nenhum par <strong>procedimento aduaneiro × fluxo</strong> classificado ainda. Defina a
            finalidade (consumo ou processamento) de cada par na aba{' '}
            <strong>Curadoria → Aduana &amp; finalidade econômica</strong> — esta análise passa a somar o
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
      {data.preview && <window.PreviewBanner banco={banco}
        capabilityNote="Valores por fluxo entram como demonstração até o MDIC ser ligado; a finalidade (consumo/processamento) de cada par regime × fluxo vem da Curadoria." />}

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
