// ViewCuration.jsx — the researcher ENRICHMENT surface. TWO editors over the shared
// institutional store (enrichment.js):
//   • ViewEnrichmentIndustrialization — the "Nível de industrialização" codes table.
//   • ViewEnrichmentMarketNature       — the "Tipo de Mercado" regime × flow matrix
//     (reverted from the comtrade_market_nature seed, v1.9.0).
// Edits persist + notify so analyses react, and "Aplicar à base" commits the pending draft
// (append-only SCD2 logs, gated by the `enable_curation` dbt var). No per-row provenance in
// v1 (per the brief) — just the values. A lingering ?ip=curation deep link resolves to the
// industrialization screen.

// Re-render this subtree whenever the shared enrichment store notifies (edit,
// commit start/end). Each screen uses it so its KPIs / apply bar stay live.
function useEnrichmentTick() {
  const [, force] = React.useState(0);
  React.useEffect(() => window.enrichment.subscribe(() => force(n => n + 1)), []);
}

const _bancoShort = (id) => (window.bancoById ? window.bancoById(id)?.short : id) || id;

// ── fast hover tooltip (replaces the native `title`, whose ~1s browser delay made
// the matrix hints feel "broken"). A single body-level, fixed-position bubble is
// reused for every hint — fixed position escapes the table's overflow clipping,
// and a short 90 ms delay makes it feel instant. Shared by the matrix headers and
// regime rows; any element can opt in via the <CurHint> wrapper below.
let _tipEl = null;
let _tipTimer = null;
let _tipXY = { x: 0, y: 0 };
function _tipLayer() {
  if (_tipEl) return _tipEl;
  _tipEl = document.createElement('div');
  _tipEl.className = 'cur-tip-pop';
  _tipEl.setAttribute('role', 'tooltip');
  document.body.appendChild(_tipEl);
  // A scroll anywhere should drop the bubble (the anchor moved under it).
  window.addEventListener('scroll', () => _hideTip(), true);
  return _tipEl;
}
function _placeTip(el) {
  const pad = 12;
  const r = el.getBoundingClientRect();
  let left = _tipXY.x + 14;
  let top = _tipXY.y + 18;
  if (left + r.width + pad > window.innerWidth) left = window.innerWidth - r.width - pad;
  if (top + r.height + pad > window.innerHeight) top = _tipXY.y - r.height - 14;
  if (top < pad) top = pad;
  if (left < pad) left = pad;
  el.style.left = left + 'px';
  el.style.top = top + 'px';
}
function _showTip(text) {
  const el = _tipLayer();
  el.textContent = text;
  el.classList.add('on');
  _placeTip(el);
}
function _hideTip() {
  if (_tipTimer) {
    clearTimeout(_tipTimer);
    _tipTimer = null;
  }
  if (_tipEl) _tipEl.classList.remove('on');
}
// Wrap any element to give it a fast custom tooltip. `tag` picks the host element
// (th / div), `tip` is the text; remaining props (className, key…) pass through.
function CurHint({ tag = 'div', tip, children, ...rest }) {
  const Tag = tag;
  const onEnter = (e) => {
    _tipXY = { x: e.clientX, y: e.clientY };
    if (_tipTimer) clearTimeout(_tipTimer);
    _tipTimer = setTimeout(() => _showTip(tip), 90);
  };
  const onMove = (e) => {
    _tipXY = { x: e.clientX, y: e.clientY };
    if (_tipEl && _tipEl.classList.contains('on')) _placeTip(_tipEl);
  };
  return (
    <Tag onMouseEnter={onEnter} onMouseMove={onMove} onMouseLeave={_hideTip} {...rest}>
      {children}
    </Tag>
  );
}

// One code row in the industrialization worklist (the LEFT JOIN result).
function EnrichmentCodeRow(c, nested) {
  const todo = !c.level;
  return (
    <tr key={c.id} className={(nested ? 'cur-coderow-nested' : '') + (todo ? ' cur-coderow-todo' : '')}>
      <td className="cur-cell-src">{nested ? null : <span className="cur-src">{_bancoShort(c.source)}</span>}</td>
      <td className="tnum cur-cell-code" data-label="Código">{c.code}</td>
      <td className="cur-cell-desc" data-label="Descrição">{c.desc}{todo && <span className="cur-todo-pill">a classificar</span>}</td>
      <td className="cur-cell-level" data-label="Nível de industrialização">
        <select className={'xs-select cur-level' + (todo ? ' cur-level-empty' : '')} value={c.level || ''}
                title={c.level ? window.enrichment.levelDesc(c.level) : 'Selecione o nível de industrialização'}
                onChange={(e) => window.enrichment.setCode(c.id, { level: e.target.value })}>
          <option value="">— a classificar —</option>
          {window.ENRICH_LEVELS.map(l => <option key={l.id} value={l.id} title={l.description}>{l.label}</option>)}
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

// Reference legend of the 8 industrialization levels + their definitions (the researcher-
// facing taxonomy, from window.ENRICH_LEVELS). Shown atop the classifier so the meaning of
// each option is visible while classifying — the "Industrialização × Descrição" reference.
function EnrichmentLevelLegend() {
  const [open, setOpen] = React.useState(true);
  return (
    <div className="card">
      <window.SectionHeader
        overline="Escala de industrialização · do bruto ao manufaturado"
        title="O que significa cada nível"
        action={<button className="btn-secondary" onClick={() => setOpen(o => !o)}>{open ? 'Ocultar' : 'Mostrar'}</button>}
      />
      {open && (
        <div className="pc-table-wrap">
          <table className="pc-table">
            <thead><tr><th style={{ width: 220 }}>Industrialização</th><th>Descrição</th></tr></thead>
            <tbody>
              {window.ENRICH_LEVELS.map(l => (
                <tr key={l.id}>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: 600, whiteSpace: 'nowrap' }}>
                      <span style={{ width: 10, height: 10, borderRadius: 3, background: l.color, flexShrink: 0 }}></span>
                      {l.label}
                    </span>
                  </td>
                  <td style={{ color: 'var(--fg-2)', lineHeight: 1.5 }}>{l.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
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
        <window.KpiCardSpark label="Classificados" value={stats.codesTotal - stats.unclassified} sub="com nível definido" />
        <window.KpiCardSpark label="Níveis usados" value={Object.values(stats.byLevel).filter(n => n > 0).length} sub={`de ${window.ENRICH_LEVELS.length} na escala`} />
      </div>

      <EnrichmentLevelLegend />

      <div className="card">
        <window.SectionHeader
          overline="Códigos entre fontes · nível de industrialização"
          title="Classifique cada código pelo nível de industrialização"
          action={
            <div className="cur-group-by">
              <span className="cur-group-label">Agrupar por</span>
              <div className="seg cur-codes-seg">
                <button className={'seg-opt ' + (codesView === 'commodity' ? 'on' : '')} onClick={() => setCodesView('commodity')}>
                  <window.Icon name="eco" size={14} /> Agrupamento
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

// ── Tool 2: Tipo de Mercado (regime × flow matrix) ────────────────────────────
function ViewEnrichmentMarketNature() {
  useEnrichmentTick();
  const stats = window.enrichment.stats();

  return (
    <>
      <EnrichmentApplyBar note={
        <>
          O que você marca aqui é <strong>compartilhado</strong>: vale para toda a equipe e
          alimenta a análise de tipo de mercado (<strong>consumo</strong> × <strong>processamento</strong>).
          A finalidade depende da <strong>combinação</strong> entre regime aduaneiro e fluxo — não de
          cada um isolado. Nada é salvo até você clicar em <strong>Aplicar à base</strong>.
        </>
      } />

      <div className="kpi-row">
        <window.KpiCardSpark label="Combinações classificadas" value={`${stats.flowsClassified} / ${stats.flowsTotal}`} sub="regime × fluxo" />
        <window.KpiCardSpark label="Regimes aduaneiros" value={window.enrichment.regimes().length} sub="linhas da matriz" />
        <window.KpiCardSpark label="Fluxos comerciais" value={window.enrichment.flowTypes().length} sub="colunas da matriz" />
      </div>

      <div className="card">
        <window.SectionHeader
          overline="Regime aduaneiro × fluxo · finalidade econômica"
          title="A finalidade depende da combinação regime + fluxo"
          action={
            <span className="cur-legend">
              {window.ENRICH_MARKETS.map(m => (
                <span key={m.id} className="cur-legend-item"><span className="cur-legend-dot" style={{ background: m.color }}></span>{m.short}</span>
              ))}
            </span>
          } />
        <p className="caption" style={{ padding: '0 4px 8px' }}>
          Cada <strong>linha</strong> é um regime aduaneiro (a forma da operação no comércio
          exterior) e cada <strong>coluna</strong> é um fluxo (importação, exportação…), ordenados
          pelos que mais movimentam valor. O número sob cada combinação é o valor em dólar
          efetivamente negociado — comece pelas combinações de maior valor.
        </p>
        <div className="pc-table-wrap">
          <table className="pc-table cur-table cur-matrix">
            <thead>
              <tr>
                <th className="cur-corner">
                  <span className="cur-corner-col">Fluxo comercial →</span>
                  <span className="cur-corner-row">Regime aduaneiro ↓</span>
                </th>
                {window.enrichment.flowTypes().map(f => <CurHint key={f.id} tag="th" className="cur-c" tip={f.label + ' — ' + f.hint}><span className="cur-hashint">{f.term}</span></CurHint>)}
              </tr>
            </thead>
            <tbody>
              {window.enrichment.regimes().map(r => (
                <tr key={r.id}>
                  <CurHint tag="td" tip={r.label + ' — ' + r.hint}>
                    <div className="cur-regime cur-hashint">{r.term}</div>
                  </CurHint>
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
// The old combined entry (?ip=curation) routes straight to the industrialization screen in
// MainScreen.
