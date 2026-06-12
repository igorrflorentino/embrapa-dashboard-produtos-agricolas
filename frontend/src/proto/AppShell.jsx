// AppShell — institutional chrome: header band, sidebar, breadcrumb, footer tríade.
//
// Two-axis navigation:
//   • sidebar  → selects the data source ("Banco de dados") + info pages
//   • topnav   → selects the analytical view (perspective) of the active banco

function AppShell({
  children,
  view, setView,
  database, setDatabase,
  infoPage, setInfoPage,
  summary,
  conventions,
  crossState,
  mode = 'single', setMode,
}) {
  const [citeOpen, setCiteOpen] = React.useState(false);
  const [shared,   setShared]   = React.useState(false);
  const [navOpen,  setNavOpen]  = React.useState(false);

  const groups = window.VIEW_GROUPS || [];
  const activeView = window.viewById ? window.viewById(view) : null;
  const activeGroup = activeView?.group;

  const isMulti = mode === 'multi';
  // A view belongs to the multi-fonte mode iff it operates across bancos.
  const inMode = (v) => isMulti ? !!v.crossBanco : !v.crossBanco;
  // Topnav lists only the perspectives that belong to the active mode.
  const visibleGroups = groups
    .map(g => ({ ...g, views: g.views.filter(inMode) }))
    .filter(g => g.views.length);
  // Which bancos are "in play" for the active multi-fonte perspective —
  // the picker view reflects the chosen series; the analytical views
  // declare fixed `sources`. The sidebar uses this as an indicator.
  const crossSeries = (crossState && crossState.series) || [];
  const onCrossPicker = activeView?.id === 'cross_source';
  const includedBancos = new Set(
    onCrossPicker ? crossSeries.map(s => s.b) : (activeView?.sources || [])
  );
  const seriesCountByBanco = onCrossPicker
    ? crossSeries.reduce((m, s) => { m[s.b] = (m[s.b] || 0) + 1; return m; }, {})
    : {};

  const bancos = window.visibleBancos ? window.visibleBancos() : (window.BANCOS || []);
  const bancoMeta = window.bancoById ? window.bancoById(database) : null;

  const pickView = (id) => {
    setView(id);
    if (setInfoPage) setInfoPage(null);
    setNavOpen(false);
  };

  const onBanco = (id) => {
    setDatabase(id);
    if (setInfoPage) setInfoPage(null);
  };
  const onInfo = (id) => {
    if (setInfoPage) setInfoPage(id);
  };

  const onInfoPage = !!infoPage;

  // ── Citation + share helpers ─────────────────────────────────────────
  const VIEW_LABEL = window.viewLabel
    ? Object.fromEntries((window.VIEW_GROUPS || []).flatMap(g => g.views.map(v => [v.id, v.label])))
    : {};
  const activeBanco = (window.bancoById && window.bancoById(database)) || null;
  const bancoCiteLabel = activeBanco
    ? `${activeBanco.short} · ${activeBanco.label.replace(/^[^·]+·\s*/, '')}`
    : database;
  const today = new Date();
  const accessedOn = today.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' });
  // Recorte temporal: the ACTIVE banco's LIVE coverage \u2014 its snapshot overviewTS
  // span first (window.dataStore.get), then the /api/source-meta coverage
  // (meta().coverage), then '\u2014'. NEVER window.OVERVIEW_TS, which is the synthetic
  // seed frozen identically for every banco (audit #23).
  const _ovTs = (window.dataStore && window.dataStore.get && window.dataStore.get(database)?.overviewTS) || [];
  const _cov = (window.dataStore && window.dataStore.meta && window.dataStore.meta(database)?.coverage) || null;
  const _yStart = _ovTs[0]?.y ?? _cov?.yearStart ?? '\u2014';
  const _yEnd   = _ovTs[_ovTs.length - 1]?.y ?? _cov?.yearEnd ?? '\u2014';
  const period = summary && (summary.startDate || summary.endDate)
    ? `${String(summary.startDate || _yStart).slice(0,4)}\u2013${String(summary.endDate || _yEnd).slice(0,4)}`
    : `${_yStart}\u2013${_yEnd}`;
  const convLabel = conventions
    ? `${conventions.currency} \u00b7 ${conventions.correction} \u00b7 ${conventions.units?.mass} \u00b7 ${conventions.units?.volume}`
    : 'BRL \u00b7 IPCA \u00b7 t \u00b7 m\u00b3';

  const activeView2 = window.viewById ? window.viewById(view) : null;
  const isCrossView = !!(activeView2 && activeView2.crossBanco);

  // Human label for the cross-source selection (used in citation + chips).
  const crossLabel = () => {
    const ser = (crossState && crossState.series) || [];
    const parts = ser.map(r => {
      const b = window.bancoById ? window.bancoById(r.b) : null;
      const m = window.metricById ? window.metricById(r.b, r.m) : null;
      return b && m ? `${m.label} (${b.short})` : `${r.b}:${r.m}`;
    });
    return parts.join(' × ');
  };
  // The analytical cross perspectives have fixed sources; only the picker
  // view ('cross_source') is described by the chosen series.
  const isPickerCite = activeView2?.id === 'cross_source';
  const crossSourcesLabel = (activeView2?.sources || [])
    .map(id => window.bancoById ? window.bancoById(id)?.short : id).filter(Boolean).join(' · ');

  const citation = isCrossView
    ? (isPickerCite
        ? `EMPRESA BRASILEIRA DE PESQUISA AGROPECU\u00c1RIA (EMBRAPA). ` +
          `Dashboard de An\u00e1lise Hist\u00f3rica de Commodities \u2014 Cruzamento entre fontes \u2014 ` +
          `${crossLabel()}. Recorte: ${period}. ` +
          `Bras\u00edlia: Embrapa, 2026. Acesso em: ${accessedOn}.`
        : `EMPRESA BRASILEIRA DE PESQUISA AGROPECU\u00c1RIA (EMBRAPA). ` +
          `Dashboard de An\u00e1lise Hist\u00f3rica de Commodities \u2014 An\u00e1lise cruzada \u2014 ` +
          `${VIEW_LABEL[view] || view}${crossSourcesLabel ? ` (fontes: ${crossSourcesLabel})` : ''}. ` +
          `Recorte: ${period}. Bras\u00edlia: Embrapa, 2026. Acesso em: ${accessedOn}.`)
    : `EMPRESA BRASILEIRA DE PESQUISA AGROPECU\u00c1RIA (EMBRAPA). ` +
      `Dashboard de An\u00e1lise Hist\u00f3rica de Commodities \u2014 ` +
      `${bancoCiteLabel} \u2014 ${VIEW_LABEL[view] || view}. ` +
      `Recorte: ${period}. Conven\u00e7\u00f5es m\u00e9tricas: ${convLabel}. ` +
      `Bras\u00edlia: Embrapa, 2026. Acesso em: ${accessedOn}.`;

  const onCite = () => setCiteOpen(true);
  const onShare = async () => {
    // Encode the current state in a query string researchers can paste.
    // Keys + array sentinel rules come from the shared codec (urlState.js) —
    // the same module the decoder (Dashboard.readStateFromURL) reads — so the
    // two halves can't drift on the wire format.
    // Guard the codec globals (same as main.jsx's URL write-back) so a Share
    // click before urlState.js has loaded degrades to a no-op instead of a
    // "urlEncodeArr is not a function" throw.
    if (!window.urlEncodeState) return;
    const arrParam = window.urlEncodeArr || (() => '');
    const state = {
      v: view, b: database, ip: infoPage,
      cur: conventions?.currency, corr: conventions?.correction,
      mu: conventions?.units?.mass, vu: conventions?.units?.volume, as: conventions?.autoScale ? 1 : 0,
      pb: arrParam(summary?.basket),
      fl: arrParam(summary?.flags),
      st: arrParam(summary?.states),
      vmn: summary?.valueMin ?? '', vmx: summary?.valueMax ?? '',
      sd: summary?.startDate || '', ed: summary?.endDate || '',
      // Cross-source selection: series as "banco:metric|banco:metric",
      // plus visualization mode and the comparable year window.
      xs: isCrossView && crossState?.series ? crossState.series.map(r => `${r.b}:${r.m}`).join('|') : '',
      xm: isCrossView ? (crossState?.mode || '') : '',
      xy0: isCrossView && crossState?.y0 ? crossState.y0 : '',
      xy1: isCrossView && crossState?.y1 ? crossState.y1 : '',
    };
    const qs = window.urlEncodeState(state);
    const url = `${location.origin}${location.pathname}?${qs}`;
    try { await navigator.clipboard.writeText(url); } catch (e) {}
    setShared(true);
    setTimeout(() => setShared(false), 1800);
  };
  const onCopyCite = async () => {
    try { await navigator.clipboard.writeText(citation); } catch (e) {}
  };

  return (
    <div className="shell">
      <header className="topbar">
        <button className="brand brand-btn" onClick={() => { if (setInfoPage) setInfoPage('about'); }} title="Voltar para Sobre o dashboard">
          <img src="assets/logo-embrapa-white-cropped.png" alt="Embrapa" className="brand-logo"/>
        </button>
        <div className="sep"></div>
        <div className="product-name">Análise histórica de commodities</div>

        <div className="mode-switch" role="tablist" aria-label="Modo de análise">
          <button role="tab" aria-selected={!isMulti}
            className={'mode-opt ' + (!isMulti ? 'on' : '')}
            onClick={() => setMode && setMode('single')}
            title="Analisar um banco de dados por vez">
            <window.Icon name="database" size={15}/>
            <span>Banco único</span>
          </button>
          <button role="tab" aria-selected={isMulti}
            className={'mode-opt ' + (isMulti ? 'on' : '')}
            onClick={() => setMode && setMode('multi')}
            title="Cruzar séries de bancos diferentes no mesmo eixo de tempo">
            <window.Icon name="hub" size={15}/>
            <span>Multi-fonte</span>
          </button>
        </div>

        <nav className="topnav">
          <button
            className={'topnav-trigger ' + (navOpen ? 'open' : '') + (onInfoPage ? '' : ' has-active')}
            onClick={() => setNavOpen(o => !o)}
            aria-haspopup="true"
            aria-expanded={navOpen}>
            <span className="topnav-trigger-l">
              {onInfoPage ? (
                <span className="topnav-trigger-view">Selecionar perspectiva</span>
              ) : (
                <>
                  <span className="topnav-trigger-grp">{activeGroup?.label || 'Perspectiva'}</span>
                  <span className="topnav-trigger-view">{activeView?.label || 'Visão geral'}</span>
                </>
              )}
            </span>
            <window.Icon name="expand_more" size={18}/>
          </button>

          {navOpen && (
            <>
              <div className="topnav-scrim" onClick={() => setNavOpen(false)}></div>
              <div className={'topnav-menu' + (isMulti ? ' narrow' : '')} role="menu">
                <div className="topnav-menu-bar">
                  <span className="topnav-menu-scope">
                    {isMulti
                      ? <>Perspectivas <strong>multi-fonte</strong> · entre bancos</>
                      : <>Perspectivas para <strong>{bancoMeta ? bancoMeta.short : 'banco'}</strong></>}
                  </span>
                  <span className="topnav-menu-legend">
                    <span className="tnl-item"><span className="tnl-dot ok"></span>Disponível</span>
                    {!isMulti && <span className="tnl-item"><span className="tnl-dot soon"></span>Em breve</span>}
                    {!isMulti && <span className="tnl-item"><span className="tnl-dot na"></span>Não se aplica</span>}
                  </span>
                </div>
                <div className="topnav-menu-grid">
                  {visibleGroups.map(g => (
                    <div key={g.id} className="topnav-grp">
                      <div className="topnav-grp-head">
                        <span className="topnav-grp-label">{g.label}</span>
                        <span className="topnav-grp-hint">{g.hint}</span>
                      </div>
                      {g.views.map(v => {
                        const compat = window.viewAppliesTo
                          ? window.viewAppliesTo(v.id, database)
                          : { applies: true, missing: [] };
                        const applies = compat.applies;
                        const supporters = !applies && window.bancosSupporting
                          ? window.bancosSupporting(v.id)
                          : [];
                        const state = !applies ? 'na' : (v.status === 'soon' ? 'soon' : 'ok');
                        return (
                          <button
                            key={v.id}
                            className={'topnav-opt state-' + state + (!onInfoPage && view === v.id ? ' active' : '')}
                            onClick={() => pickView(v.id)}
                            role="menuitem"
                            title={!applies ? `Requer ${window.missingCapsLabel(compat.missing)} — não disponível em ${bancoMeta?.short || 'este banco'}` : v.desc}>
                            <span className="topnav-opt-top">
                              <span className={'topnav-opt-dot ' + state}></span>
                              <span className="topnav-opt-label">{v.label}</span>
                              {v.crossBanco && <span className="topnav-opt-tag cross">multi-fonte</span>}
                              {state === 'soon' && <span className="topnav-opt-tag soon">Em breve</span>}
                              {state === 'na'   && <span className="topnav-opt-tag na">Não se aplica</span>}
                            </span>
                            {!applies && supporters.length > 0 && (
                              <span className="topnav-opt-supporters">
                                disponível em {supporters.map(b => b.short).join(' · ')}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </nav>

        <div className="util">
          <button className="util-action" onClick={onCite} title="Citar este painel no estado atual">
            <window.Icon name="format_quote" size={16}/>
            <span>Citar painel</span>
          </button>
          <button className="util-action" onClick={onShare} title="Copiar URL com o estado atual (filtros, view, convenções)">
            <window.Icon name="link" size={16}/>
            <span>{shared ? 'URL copiada' : 'Compartilhar'}</span>
          </button>
        </div>
      </header>

      <div className="body">
        <aside className="sidebar">
          <div className="side-section">{isMulti ? 'Fontes no cruzamento' : 'Banco de dados'}</div>
          {isMulti ? (
            <>
              <div className="side-hint">
                {onCrossPicker
                  ? <>Reflete as séries montadas no painel. Edite as fontes em <strong>Montagem do cruzamento</strong>.</>
                  : <>Fontes combinadas por esta perspectiva.</>}
              </div>
              <div className="side-srclist" role="list">
                {bancos.map(b => {
                  const incl = includedBancos.has(b.id);
                  return (
                    <div key={b.id} role="listitem"
                         className={'side-src ' + (incl ? 'incl' : 'excl')}
                         title={incl
                           ? `${seriesCountByBanco[b.id] || ''} ${b.short} no cruzamento`.trim()
                           : `${b.short} fora do cruzamento atual`}>
                      <span className="side-src-dot"></span>
                      <span className="side-src-name">{b.short}</span>
                      {incl
                        ? (seriesCountByBanco[b.id]
                            ? <span className="side-src-count tnum" title={`${seriesCountByBanco[b.id]} série(s)`}>{seriesCountByBanco[b.id]}</span>
                            : <span className="side-src-in">incluída</span>)
                        : <window.MaturityTag banco={b} size="sm" />}
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            bancos.map(b => {
              const active = database === b.id;
              return (
              <div key={b.id}
                   className={'side-item ' + (active ? (onInfoPage ? 'selected' : 'active') : '')}
                   onClick={() => onBanco(b.id)}
                   title={b.label}>
                <window.UsageDot active={active} />
                <span className="side-item-l">{b.short}</span>
                <window.MaturityTag banco={b} size="sm" />
              </div>
              );
            })
          )}

          <div className="side-section">Curadoria</div>
          <div className={'side-item ' + (infoPage === 'curation' ? 'active' : '')}
               onClick={() => onInfo('curation')}>
            <window.Icon name="fact_check"/>Enriquecimento
          </div>

          <div className="side-section">Informações</div>
          <div className={'side-item ' + (infoPage === 'about' ? 'active' : '')}
               onClick={() => onInfo('about')}>
            <window.Icon name="info"/>Sobre o dashboard
          </div>
          <div className={'side-item ' + (infoPage === 'glossary' ? 'active' : '')}
               onClick={() => onInfo('glossary')}>
            <window.Icon name="menu_book"/>Glossário global
          </div>
          <div className={'side-item ' + (infoPage === 'health' ? 'active' : '')}
               onClick={() => onInfo('health')}>
            <window.Icon name="pulse"/>Saúde do sistema
          </div>
        </aside>

        <main className="content">
          {children}
        </main>
      </div>

      {citeOpen && (
        <div className="cite-backdrop" onClick={() => setCiteOpen(false)}>
          <div className="cite-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-labelledby="cite-title">
            <header className="cite-head">
              <div>
                <div className="overline">Citação acadêmica</div>
                <h2 id="cite-title">Citar painel · ABNT NBR 6023</h2>
                <p className="caption">
                  Citação do estado atual (banco, view, recorte temporal e convenções métricas).
                </p>
              </div>
              <button className="fm-close" onClick={() => setCiteOpen(false)} aria-label="Fechar">
                <window.Icon name="close" size={18}/>
              </button>
            </header>
            <div className="cite-body">
              <pre className="cite-text">{citation}</pre>
              <div className="cite-actions">
                <button className="btn-secondary" onClick={() => setCiteOpen(false)}>Fechar</button>
                <button className="btn-primary" onClick={onCopyCite}>
                  <window.Icon name="content_copy" size={14}/> Copiar citação
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <footer className="footer">
        <img src="assets/triade-horizontal-black.png" alt="Embrapa · Ministério da Agricultura e Pecuária · Governo do Brasil" className="triade"/>
        <div className="foot-meta">
          <div>© Empresa Brasileira de Pesquisa Agropecuária</div>
          <div className="caption">Ministério da Agricultura e Pecuária · Pipeline Bronze → Silver → Gold · BigQuery + Looker Studio</div>
          <div className="caption"><a href="#">www.embrapa.br</a> &nbsp;·&nbsp; <a href="#">Serviço de Atendimento ao Cidadão (SAC)</a></div>
        </div>
      </footer>
    </div>
  );
}

window.AppShell = AppShell;
