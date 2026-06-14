// ViewCuration.jsx — the researcher ENRICHMENT surface, split into ONE SCREEN
// PER TOOL so each enrichment can be done on its own:
//   • ViewEnrichmentIndustrialization — "Nível de industrialização" (codes table)
//   • ViewEnrichmentMarketNature      — "Tipo de Mercado" (regime × flow matrix)
// Both edit the SAME shared institutional store (enrichment.js): edits persist +
// notify, so analyses react live, and "Aplicar à base" commits the whole pending
// draft (one append-only SCD2 log) regardless of which screen you apply from.
// No per-row provenance in v1 (per the brief) — just the values.
//
// Any lingering ?ip=curation deep link still resolves: MainScreen routes that legacy
// value straight to the industrialization screen.

// Re-render this subtree whenever the shared enrichment store notifies (edit,
// commit start/end). Each screen uses it so its KPIs / apply bar stay live.
function useEnrichmentTick() {
  const [, force] = React.useState(0);
  React.useEffect(() => window.enrichment.subscribe(() => force(n => n + 1)), []);
}

const _bancoShort = (id) => (window.bancoById ? window.bancoById(id)?.short : id) || id;

// One code row in the industrialization worklist (the LEFT JOIN result).
function EnrichmentCodeRow(c, nested) {
  const todo = !c.level;
  return (
    <tr key={c.id} className={(nested ? 'cur-coderow-nested' : '') + (todo ? ' cur-coderow-todo' : '')}>
      <td>{nested ? null : <span className="cur-src">{_bancoShort(c.source)}</span>}</td>
      <td className="tnum">{c.code}</td>
      <td>{c.desc}{todo && <span className="cur-todo-pill">a classificar</span>}</td>
      <td>
        <select className={'xs-select cur-level' + (todo ? ' cur-level-empty' : '')} value={c.level || ''}
                onChange={(e) => window.enrichment.setCode(c.id, { level: e.target.value })}>
          <option value="">— a classificar —</option>
          {window.ENRICH_LEVELS.map(l => <option key={l.id} value={l.id}>{l.label}</option>)}
        </select>
      </td>
    </tr>
  );
}

// Shared "intro note + Aplicar à base bar + write-error" block, rendered atop each
// enrichment screen. `note` is the screen-specific explanatory text. The apply bar
// reflects the GLOBAL pending draft (the store commits atomically) — applying from
// either screen writes every pending classification to the shared log.
function EnrichmentApplyBar({ note }) {
  const [justApplied, setJustApplied] = React.useState(false);
  const committing = window.enrichment.isCommitting();
  const pending = window.enrichment.pendingCount();
  const writeError = window.enrichment.lastError ? window.enrichment.lastError() : null;
  const onApply = () => {
    window.enrichment.apply(() => {
      setJustApplied(true);
      setTimeout(() => setJustApplied(false), 2800);
    });
  };

  return (
    <>
      <div className="cur-note">
        <window.Icon name="info" size={16} />
        <span>{note}</span>
      </div>

      <div className={'cur-apply ' + (committing ? 'committing' : (pending > 0 ? 'dirty' : (justApplied ? 'done' : '')))}>
        <span className="cur-apply-status">
          {committing
            ? <><span className="cur-spinner"></span> Gravando no log de classificação (SCD2) e refazendo o JOIN ao vivo…</>
            : pending > 0
              ? <><span className="cur-apply-dot"></span><strong>{pending}</strong>&nbsp;{pending > 1 ? 'alterações não aplicadas' : 'alteração não aplicada'} à base</>
              : justApplied
                ? <><window.Icon name="fact_check" size={15} /> Aplicado à base — análises re-sincronizadas</>
                : <><window.Icon name="fact_check" size={15} /> Curadoria aplicada — a dimensão está em sincronia com a base</>}
        </span>
        <div className="cur-apply-actions">
          {pending > 0 && !committing && <button className="btn-secondary" onClick={() => window.enrichment.discard()}>Descartar</button>}
          <button className="btn-primary" disabled={pending === 0 || committing} onClick={onApply}>
            {committing ? <><span className="cur-spinner cur-spinner-btn"></span> Aplicando…</> : 'Aplicar à base'}
          </button>
        </div>
      </div>

      {writeError && !committing && (
        <div className="cur-write-error" role="alert"
             style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0',
                      padding: '10px 14px', borderRadius: 8, fontSize: 13,
                      background: 'var(--pres-red-50, #fdecea)', color: 'var(--pres-red-700, #b3261e)',
                      border: '1px solid var(--pres-red-200, #f4c7c3)' }}>
          <window.Icon name="warning" size={16} />
          <span>
            Falha ao gravar a curadoria (<strong>{writeError}</strong>). As alterações foram
            <strong> mantidas</strong> — verifique o acesso (autor IAP) e clique em <strong>Aplicar</strong> novamente.
          </span>
        </div>
      )}
    </>
  );
}

// ── Tool 1: Nível de industrialização ─────────────────────────────────────────
function ViewEnrichmentIndustrialization() {
  useEnrichmentTick();
  const [codesView, setCodesView] = React.useState('commodity');
  const stats = window.enrichment.stats();

  return (
    <>
      <EnrichmentApplyBar note={
        <>
          Curadoria <strong>institucional compartilhada</strong>: o conhecimento adicionado aqui
          vale para todos os pesquisadores e alimenta as análises curadas. A worklist é um
          <strong> LEFT JOIN</strong> entre os códigos da Gold e o log de classificação — códigos
          sem classificação aparecem como <strong>a classificar</strong>. As alterações só entram
          na base ao clicar em <strong>Aplicar</strong>.
        </>
      } />

      <div className="kpi-row">
        <window.KpiCardSpark label="Códigos na worklist" value={stats.codesTotal} sub="Gold DISTINCT ⟕ log" />
        <window.KpiCardSpark label="A classificar" value={stats.unclassified} sub="sem linha no log (NULL)" />
        <window.KpiCardSpark label="Bruta" value={stats.byLevel.bruta} sub="códigos classificados" />
        <window.KpiCardSpark label="Processada" value={stats.byLevel.processada} sub="códigos classificados" />
      </div>

      <div className="card">
        <window.SectionHeader
          overline="Códigos entre fontes · nível de industrialização"
          title="Classifique cada código como bruto ou processado"
          action={
            <div className="cur-group-by">
              <span className="cur-group-label">Agrupar por</span>
              <div className="seg cur-codes-seg">
                <button className={'seg-opt ' + (codesView === 'commodity' ? 'on' : '')} onClick={() => setCodesView('commodity')}>
                  <window.Icon name="eco" size={14} /> Commodity
                </button>
                <button className={'seg-opt ' + (codesView === 'banco' ? 'on' : '')} onClick={() => setCodesView('banco')}>
                  <window.Icon name="database" size={14} /> Banco
                </button>
              </div>
            </div>
          } />
        <div className="pc-table-wrap">
          <table className="pc-table cur-table">
            <thead>
              <tr>
                <th>Fonte</th><th>Código</th><th>Descrição</th>
                <th>Nível de industrialização</th>
              </tr>
            </thead>
            <tbody>
              {codesView === 'commodity'
                ? (window.ENRICH_GROUPS).map(g => {
                    const rows = window.enrichment.codes().filter(c => c.group === g.id);
                    if (!rows.length) return null;
                    return (
                      <React.Fragment key={g.id}>
                        <tr className="cur-grouprow"><td colSpan={4}>{g.label}</td></tr>
                        {rows.map(c => EnrichmentCodeRow(c))}
                      </React.Fragment>
                    );
                  })
                : [...new Set(window.enrichment.codes().map(c => c.source))].map(src => {
                    const srcCodes = window.enrichment.codes().filter(c => c.source === src);
                    const chapters = [...new Set(srcCodes.map(c => window.enrichment.chapterOf(src, c.code)))];
                    return (
                      <React.Fragment key={src}>
                        <tr className="cur-bancorow"><td colSpan={4}><window.Icon name="database" size={13} /> {_bancoShort(src)}</td></tr>
                        {chapters.map(ch => (
                          <React.Fragment key={src + ':' + ch}>
                            <tr className="cur-chaprow"><td colSpan={4}>{ch}</td></tr>
                            {srcCodes.filter(c => window.enrichment.chapterOf(src, c.code) === ch).map(c => EnrichmentCodeRow(c, true))}
                          </React.Fragment>
                        ))}
                      </React.Fragment>
                    );
                  })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// ── Tool 2: Tipo de Mercado (finalidade econômica) ────────────────────────────
function ViewEnrichmentMarketNature() {
  useEnrichmentTick();
  const stats = window.enrichment.stats();

  return (
    <>
      <EnrichmentApplyBar note={
        <>
          Curadoria <strong>institucional compartilhada</strong>: a finalidade econômica de cada
          par <strong>procedimento aduaneiro × fluxo</strong> vale para todos os pesquisadores e
          alimenta a análise de <strong>tipo de mercado</strong> (consumo vs. processamento). As
          alterações só entram na base ao clicar em <strong>Aplicar</strong>.
        </>
      } />

      <div className="kpi-row">
        <window.KpiCardSpark label="Pares classificados" value={`${stats.flowsClassified} / ${stats.flowsTotal}`} sub="regime × fluxo" />
        <window.KpiCardSpark label="Procedimentos aduaneiros" value={window.enrichment.regimes().length} sub="regimes (linhas)" />
        <window.KpiCardSpark label="Fluxos comerciais" value={window.enrichment.flowTypes().length} sub="direções (colunas)" />
      </div>

      <div className="card">
        <window.SectionHeader
          overline="Procedimento aduaneiro × fluxo · finalidade econômica"
          title="A finalidade depende do par procedimento + fluxo"
          action={
            <span className="cur-legend">
              {window.ENRICH_MARKETS.map(m => (
                <span key={m.id} className="cur-legend-item"><span className="cur-legend-dot" style={{ background: m.color }}></span>{m.short}</span>
              ))}
            </span>
          } />
        <p className="caption" style={{ padding: '0 4px 8px' }}>
          Linhas = códigos <strong>reais</strong> de procedimento aduaneiro do COMTRADE (<code>customsCode</code>),
          ordenados por valor transacionado; colunas = fluxos (<code>flowCode</code>). O valor sob cada par é o
          US$ efetivamente movimentado — classifique primeiro os pares materiais.
        </p>
        <div className="pc-table-wrap">
          <table className="pc-table cur-table cur-matrix">
            <thead>
              <tr>
                <th className="cur-corner">
                  <span className="cur-corner-col">Fluxo comercial →</span>
                  <span className="cur-corner-row">Regime aduaneiro ↓</span>
                </th>
                {window.enrichment.flowTypes().map(f => <th key={f.id} className="cur-c" title={f.label + ' — ' + f.hint}><span className="cur-hashint">{f.term}</span></th>)}
              </tr>
            </thead>
            <tbody>
              {window.enrichment.regimes().map(r => (
                <tr key={r.id}>
                  <td title={r.label + ' — ' + r.hint}>
                    <div className="cur-regime cur-hashint">{r.term}</div>
                  </td>
                  {window.enrichment.flowTypes().map(f => {
                    const v = window.enrichment.pairMarket(r.id, f.id);
                    // Real COMTRADE value for this pair — shown so the researcher
                    // curates by materiality (opaque codes + their magnitude).
                    const val = window.enrichment.pairValueLabel
                      ? window.enrichment.pairValueLabel(r.id, f.id) : '';
                    return (
                      <td key={f.id} className="cur-c">
                        <select className={'cur-cell ' + (v ? 'mk-' + v : 'cur-cell-empty')} value={v || ''}
                                onChange={(e) => window.enrichment.setPair(r.id, f.id, e.target.value || null)}>
                          <option value="">—</option>
                          {window.ENRICH_MARKETS.map(m => <option key={m.id} value={m.id}>{m.short}</option>)}
                        </select>
                        <span className="cur-cell-val" style={{ display: 'block', fontSize: 10, color: 'var(--fg-3)', textAlign: 'center', marginTop: 2 }}>{val || '·'}</span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

window.ViewEnrichmentIndustrialization = ViewEnrichmentIndustrialization;
window.ViewEnrichmentMarketNature = ViewEnrichmentMarketNature;
// Back-compat for the old combined entry (?ip=curation) is handled in MainScreen,
// which routes that legacy value straight to the industrialization screen — so no
// window.ViewCuration alias is needed here.
