// ViewCuration.jsx — the researcher ENRICHMENT surface: the "Nível de industrialização"
// editor (ViewEnrichmentIndustrialization — the codes table). It edits the shared
// institutional store (enrichment.js): edits persist + notify so analyses react live, and
// "Aplicar à base" commits the pending draft (one append-only SCD2 log, gated by the
// `enable_curation` dbt var). No per-row provenance in v1 (per the brief) — just the values.
//
// (The "Tipo de Mercado" is no longer editable here — it is the static comtrade_market_nature
// seed. Any lingering ?ip=curation deep link resolves to this industrialization screen.)

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
            ? <><span className="cur-spinner"></span> Salvando suas classificações e atualizando as análises…</>
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
            Não foi possível salvar (<strong>{writeError}</strong>). Suas alterações foram
            <strong> mantidas</strong> — verifique seu acesso de curador e clique em <strong>Aplicar à base</strong> novamente.
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
          O que você marca aqui é <strong>compartilhado</strong>: vale para toda a equipe e
          alimenta as análises de valor agregado. A tabela abaixo reúne todos os produtos das
          fontes; os que ainda não têm nível aparecem como <strong>a classificar</strong>. Nada é
          salvo até você clicar em <strong>Aplicar à base</strong>.
        </>
      } />

      <div className="kpi-row">
        <window.KpiCardSpark label="Total de códigos" value={stats.codesTotal} sub="produtos reunidos das fontes" />
        <window.KpiCardSpark label="A classificar" value={stats.unclassified} sub="ainda sem nível definido" />
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

window.ViewEnrichmentIndustrialization = ViewEnrichmentIndustrialization;
// The old combined entry (?ip=curation) routes straight to the industrialization screen in
// MainScreen. (Tipo de Mercado is seed-driven now — no editor screen.)
