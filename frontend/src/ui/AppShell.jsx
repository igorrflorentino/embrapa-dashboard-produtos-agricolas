// AppShell — institutional chrome: header band, sidebar, breadcrumb, footer tríade.
//
// Two-axis navigation:
//   • sidebar  → selects the data source ("Banco de dados") + info pages
//   • topnav   → selects the analytical view (perspective) of the active banco

// Restore the user's saved sidebar width BEFORE first paint (sets the
// --sidebar-w custom property the .body grid reads). Runs once at import.
try {
  const _savedSbW = localStorage.getItem('embrapa:sidebarW');
  if (_savedSbW) document.documentElement.style.setProperty('--sidebar-w', _savedSbW);
} catch { /* localStorage unavailable — keep the CSS default (260px) */ }

// Draggable handle on the sidebar's right edge: lets the researcher widen/narrow
// the sidebar within a sensible range (no fixed width). Persists to localStorage;
// double-click resets to the default. Drives the same --sidebar-w the grid reads.
const SIDEBAR_MIN_W = 200;
const SIDEBAR_MAX_W = 460;
const SIDEBAR_DEFAULT_W = '260px';
function SidebarResizer() {
  const beginResize = (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const root = document.documentElement;
    const startW = parseInt(getComputedStyle(root).getPropertyValue('--sidebar-w'), 10) || 260;
    document.body.classList.add('sb-resizing');
    const onMove = (ev) => {
      const w = Math.min(SIDEBAR_MAX_W, Math.max(SIDEBAR_MIN_W, startW + (ev.clientX - startX)));
      root.style.setProperty('--sidebar-w', w + 'px');
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      document.body.classList.remove('sb-resizing');
      try {
        localStorage.setItem('embrapa:sidebarW',
          getComputedStyle(document.documentElement).getPropertyValue('--sidebar-w').trim());
      } catch { /* ignore persistence failure */ }
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };
  const reset = () => {
    document.documentElement.style.setProperty('--sidebar-w', SIDEBAR_DEFAULT_W);
    try { localStorage.setItem('embrapa:sidebarW', SIDEBAR_DEFAULT_W); } catch { /* ignore */ }
  };
  return (
    <div className="sidebar-resizer" role="separator" aria-orientation="vertical"
         title="Arraste para ajustar a largura · duplo clique para o padrão"
         onPointerDown={beginResize} onDoubleClick={reset} />
  );
}

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
  // ABNT NBR 6023:2025 access date: "13 jun. 2026" (abbreviated month + period;
  // "maio" is NOT abbreviated). toLocaleDateString's "13 de junho de 2026" is
  // non-compliant, so build it explicitly.
  const _mesAbnt = ['jan.', 'fev.', 'mar.', 'abr.', 'maio', 'jun.', 'jul.', 'ago.', 'set.', 'out.', 'nov.', 'dez.'];
  const accessedOn = `${today.getDate()} ${_mesAbnt[today.getMonth()]} ${today.getFullYear()}`;
  // Editora year — derive from the current date so the reference never rots.
  const editoraYear = today.getFullYear();
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

  // Permalink that reproduces the EXACT panel state \u2014 the ABNT "Dispon\u00edvel em:".
  // Same codec as onShare (urlState.js); extracted so the citation and the Share
  // button can't drift. Returns null before the codec has loaded (degrade clean).
  const buildPermalink = () => {
    if (!window.urlEncodeState) return null;
    const arrParam = window.urlEncodeArr || (() => '');
    const state = {
      v: view, b: database, ip: infoPage,
      cur: conventions?.currency, corr: conventions?.correction,
      mu: conventions?.units?.mass, vu: conventions?.units?.volume, as: conventions?.autoScale ? 1 : 0,
      pb: arrParam(summary?.basket), fl: arrParam(summary?.flags), st: arrParam(summary?.states),
      vmn: summary?.valueMin ?? '', vmx: summary?.valueMax ?? '',
      sd: summary?.startDate || '', ed: summary?.endDate || '',
      xs: isCrossView && crossState?.series ? crossState.series.map(r => `${r.b}:${r.m}`).join('|') : '',
      xm: isCrossView ? (crossState?.mode || '') : '',
      xy0: isCrossView && crossState?.y0 ? crossState.y0 : '',
      xy1: isCrossView && crossState?.y1 ? crossState.y1 : '',
    };
    return `${location.origin}${location.pathname}?${window.urlEncodeState(state)}`;
  };
  const _permalink = buildPermalink();
  const dispoStr = _permalink ? `Dispon\u00edvel em: ${_permalink}. ` : '';

  // Data-scope fragments for the single-banco cite \u2014 so the reference names EXACTLY
  // what is on screen (products, UFs, quality, value range) and never over-claims a
  // filtered panel as if it were the full dataset. The chip strings are already
  // computed by the shell (withChips); restricted-only dims (quality/value) are
  // included only when an actual filter is set.
  const scopeBits = [];
  if (summary?.products) scopeBits.push(`Produtos: ${summary.products}`);
  if (summary?.geo) scopeBits.push(`UFs: ${summary.geo}`);
  if (summary?.flags && summary.flags.length && summary.quality) scopeBits.push(`Qualidade: ${summary.quality}`);
  if ((summary?.valueMin != null || summary?.valueMax != null) && summary.valueRange) scopeBits.push(`Faixa de valor: ${summary.valueRange}`);
  const scopeStr = scopeBits.length ? `${scopeBits.join('. ')}. ` : '';

  const citation = isCrossView
    ? (isPickerCite
        ? `EMPRESA BRASILEIRA DE PESQUISA AGROPECU\u00c1RIA (EMBRAPA). ` +
          `Dashboard de An\u00e1lise Hist\u00f3rica de Commodities \u2014 Cruzamento entre fontes \u2014 ` +
          `${crossLabel()}. Recorte: ${period}. Conven\u00e7\u00f5es m\u00e9tricas: ${convLabel}. ` +
          `Bras\u00edlia, DF: Embrapa, ${editoraYear}. ${dispoStr}Acesso em: ${accessedOn}.`
        : `EMPRESA BRASILEIRA DE PESQUISA AGROPECU\u00c1RIA (EMBRAPA). ` +
          `Dashboard de An\u00e1lise Hist\u00f3rica de Commodities \u2014 An\u00e1lise cruzada \u2014 ` +
          `${VIEW_LABEL[view] || view}${crossSourcesLabel ? ` (fontes: ${crossSourcesLabel})` : ''}. ` +
          `Recorte: ${period}. Conven\u00e7\u00f5es m\u00e9tricas: ${convLabel}. ` +
          `Bras\u00edlia, DF: Embrapa, ${editoraYear}. ${dispoStr}Acesso em: ${accessedOn}.`)
    : `EMPRESA BRASILEIRA DE PESQUISA AGROPECU\u00c1RIA (EMBRAPA). ` +
      `Dashboard de An\u00e1lise Hist\u00f3rica de Commodities \u2014 ` +
      `${bancoCiteLabel} \u2014 ${VIEW_LABEL[view] || view}. ` +
      `Recorte: ${period}. ${scopeStr}Conven\u00e7\u00f5es m\u00e9tricas: ${convLabel}. ` +
      `Bras\u00edlia, DF: Embrapa, ${editoraYear}. ${dispoStr}Acesso em: ${accessedOn}.`;

  // ABNT NBR 10520:2023 in-text citation (chamada autor-data) \u2014 what you insert in
  // the running text. The 2023 revision renders the author in the parenthetical
  // with only an initial capital (e.g. "(Embrapa, 2026)"), UNLIKE the reference
  // body above, which keeps the entity in ALL CAPS per NBR 6023:2025. The two
  // norms are complementary: 10520 = the in-text call; 6023 = the full reference.
  const inTextCite = `(Embrapa, ${editoraYear})`;

  const onCite = () => setCiteOpen(true);
  const onShare = async () => {
    // Reuse the SAME permalink builder the citation uses (buildPermalink, above) —
    // one codec path, so the Share URL and the cite's "Disponível em:" can't drift.
    // Degrades to a no-op before urlState.js has loaded (buildPermalink → null).
    const url = buildPermalink();
    if (!url) return;
    try { await navigator.clipboard.writeText(url); } catch (e) {}
    setShared(true);
    setTimeout(() => setShared(false), 1800);
  };
  const onCopyCite = async () => {
    try { await navigator.clipboard.writeText(citation); } catch (e) {}
  };
  const onCopyInText = async () => {
    try { await navigator.clipboard.writeText(inTextCite); } catch (e) {}
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

          <div className="side-section">Engenharia de atributos</div>
          <div className={'side-item ' + (infoPage === 'enrich_industrial' || infoPage === 'curation' ? 'active' : '')}
               onClick={() => onInfo('enrich_industrial')}>
            <window.Icon name="factory"/>Nível de industrialização
          </div>
          <div className={'side-item ' + (infoPage === 'enrich_market' ? 'active' : '')}
               onClick={() => onInfo('enrich_market')}>
            <window.Icon name="trending_up"/>Tipo de Mercado
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
          <SidebarResizer />
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
                <h2 id="cite-title">Citar painel</h2>
                <p className="caption">
                  Do painel exatamente como exibido — banco, perspectiva, recorte temporal,
                  produtos, UFs, filtros e convenções métricas — com o link permanente que
                  reproduz a seleção. A <strong>citação no texto</strong> segue a ABNT NBR
                  10520:2023; a <strong>referência</strong> completa segue a ABNT NBR 6023:2025.
                </p>
              </div>
              <button className="fm-close" onClick={() => setCiteOpen(false)} aria-label="Fechar">
                <window.Icon name="close" size={18}/>
              </button>
            </header>
            <div className="cite-body">
              <div className="cite-block">
                <div className="cite-block-head">
                  <span className="overline">Citação no texto · ABNT NBR 10520:2023</span>
                  <button className="cite-copy-mini" onClick={onCopyInText} aria-label="Copiar citação no texto">
                    <window.Icon name="content_copy" size={13}/> Copiar
                  </button>
                </div>
                <pre className="cite-text cite-text-inline">{inTextCite}</pre>
                <p className="caption cite-hint">Formato autor-data, para inserir no corpo do texto.</p>
              </div>
              <div className="cite-block">
                <div className="cite-block-head">
                  <span className="overline">Referência · ABNT NBR 6023:2025</span>
                  <button className="cite-copy-mini" onClick={onCopyCite} aria-label="Copiar referência">
                    <window.Icon name="content_copy" size={13}/> Copiar
                  </button>
                </div>
                <pre className="cite-text">{citation}</pre>
                <p className="caption cite-hint">Para a lista de referências ao final do trabalho.</p>
              </div>
              <div className="cite-actions">
                <button className="btn-secondary" onClick={() => setCiteOpen(false)}>Fechar</button>
                <button className="btn-primary" onClick={onCopyCite}>
                  <window.Icon name="content_copy" size={14}/> Copiar referência
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
          <div className="caption">Ministério da Agricultura e Pecuária</div>
          <div className="caption"><a href="#">www.embrapa.br</a> &nbsp;·&nbsp; <a href="#">Serviço de Atendimento ao Cidadão (SAC)</a></div>
        </div>
      </footer>
    </div>
  );
}

window.AppShell = AppShell;
