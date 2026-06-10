/* @ds-bundle: {"format":3,"namespace":"EmbrapaCommoditiesDesignSystem_67b010","components":[],"sourceHashes":{"AppShell.jsx":"57b84b92746b","Atoms.jsx":"893171249dde","Charts.chain.jsx":"364864818360","Charts.cross.jsx":"db27bd3357f8","Charts.flow.jsx":"8684e4fe6768","Charts.geo.jsx":"f0803030b366","Charts.jsx":"b15c953fcd65","DataBoundary.jsx":"11b49c29502e","FilterMenu.jsx":"612235519884","FilterTriggerBar.jsx":"fff11b3df1f7","Glossary.jsx":"6dde305b1688","Icon.jsx":"76c47dc037d1","MainScreen.jsx":"9493e00c6c57","MetricConventions.jsx":"c03d414ef9af","Sparkline.jsx":"374f618f6608","Status.jsx":"e0344a6c06bb","UnitFamily.jsx":"a433b1329448","ViewAbout.jsx":"b823ff0db1ba","ViewComingSoon.jsx":"dcf6a7467ecc","ViewConcentration.jsx":"4ee7df57808d","ViewCrossSource.jsx":"4df34ccda0ac","ViewCuratedAnalyses.jsx":"738796e68f17","ViewCuration.jsx":"ac9eba973409","ViewFlows.jsx":"8ddd427cb9cb","ViewGeography.jsx":"f23ef76f9ad0","ViewHealth.jsx":"0ca93f96413a","ViewNotApplicable.jsx":"081040e0506b","ViewOverview.jsx":"208cdca577f1","ViewPartners.jsx":"33fd6c076071","ViewPerspectiveSoon.jsx":"fd695fff8626","ViewProductCompare.jsx":"a3c937d81681","ViewProductProfile.jsx":"68398dac3820","ViewProductivity.jsx":"198c6c9f1e23","ViewQuality.jsx":"ac52a5461381","ViewSeasonality.jsx":"3789911eeed5","ViewValueVolume.jsx":"9eacd8705810","ViewsChain.jsx":"a6906b8108a7","ViewsMultiSource.jsx":"8c8a0b62fc8f","bancos.js":"b19dc94c030d","chipFmt.js":"d2a404a847d1","contracts.js":"573c099e2c06","crossAnalytics.js":"284c58654a59","crossChain.js":"f13071b1ede2","crossSource.js":"8ffe30bf8eb9","csvExport.js":"3e993a851675","data.js":"4246eaed3804","dataFilters.js":"c9de4e534e70","dataStore.js":"58f513ed165a","demoFixture.js":"3abf8b0088a8","enrichment.js":"3af97cfc8dfc","filtersSchema.js":"a0be97089a39","glossary.js":"5939bc5e3ab5","previewData.js":"487f4aefef98","seriesUtils.js":"771d843dceba","slides/deck-stage.js":"d8d952171670","slides/image-slot.js":"5ade9426e255","synthUtils.js":"82911133510a","urlState.js":"50c4ae23b1c7","views.js":"a494425f13e9"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.EmbrapaCommoditiesDesignSystem_67b010 = window.EmbrapaCommoditiesDesignSystem_67b010 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// AppShell.jsx
try { (() => {
// AppShell — institutional chrome: header band, sidebar, breadcrumb, footer tríade.
//
// Two-axis navigation:
//   • sidebar  → selects the data source ("Banco de dados") + info pages
//   • topnav   → selects the analytical view (perspective) of the active banco

function AppShell({
  children,
  view,
  setView,
  database,
  setDatabase,
  infoPage,
  setInfoPage,
  summary,
  conventions,
  crossState,
  mode = 'single',
  setMode
}) {
  const [citeOpen, setCiteOpen] = React.useState(false);
  const [shared, setShared] = React.useState(false);
  const [navOpen, setNavOpen] = React.useState(false);
  const groups = window.VIEW_GROUPS || [];
  const activeView = window.viewById ? window.viewById(view) : null;
  const activeGroup = activeView?.group;
  const isMulti = mode === 'multi';
  // A view belongs to the multi-fonte mode iff it operates across bancos.
  const inMode = v => isMulti ? !!v.crossBanco : !v.crossBanco;
  // Topnav lists only the perspectives that belong to the active mode.
  const visibleGroups = groups.map(g => ({
    ...g,
    views: g.views.filter(inMode)
  })).filter(g => g.views.length);
  // Which bancos are "in play" for the active multi-fonte perspective —
  // the picker view reflects the chosen series; the analytical views
  // declare fixed `sources`. The sidebar uses this as an indicator.
  const crossSeries = crossState && crossState.series || [];
  const onCrossPicker = activeView?.id === 'cross_source';
  const includedBancos = new Set(onCrossPicker ? crossSeries.map(s => s.b) : activeView?.sources || []);
  const seriesCountByBanco = onCrossPicker ? crossSeries.reduce((m, s) => {
    m[s.b] = (m[s.b] || 0) + 1;
    return m;
  }, {}) : {};
  const bancos = window.visibleBancos ? window.visibleBancos() : window.BANCOS || [];
  const bancoMeta = window.bancoById ? window.bancoById(database) : null;
  const pickView = id => {
    setView(id);
    if (setInfoPage) setInfoPage(null);
    setNavOpen(false);
  };
  const onBanco = id => {
    setDatabase(id);
    if (setInfoPage) setInfoPage(null);
  };
  const onInfo = id => {
    if (setInfoPage) setInfoPage(id);
  };
  const onInfoPage = !!infoPage;

  // ── Citation + share helpers ─────────────────────────────────────────
  const VIEW_LABEL = window.viewLabel ? Object.fromEntries((window.VIEW_GROUPS || []).flatMap(g => g.views.map(v => [v.id, v.label]))) : {};
  const activeBanco = window.bancoById && window.bancoById(database) || null;
  const bancoCiteLabel = activeBanco ? `${activeBanco.short} · ${activeBanco.label.replace(/^[^·]+·\s*/, '')}` : database;
  const today = new Date();
  const accessedOn = today.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric'
  });
  const _ovTs = window.OVERVIEW_TS || [];
  const _yStart = _ovTs[0]?.y || 1986;
  const _yEnd = _ovTs[_ovTs.length - 1]?.y || 2024;
  const period = summary && (summary.startDate || summary.endDate) ? `${String(summary.startDate || _yStart).slice(0, 4)}\u2013${String(summary.endDate || _yEnd).slice(0, 4)}` : `${_yStart}\u2013${_yEnd}`;
  const convLabel = conventions ? `${conventions.currency} \u00b7 ${conventions.correction} \u00b7 ${conventions.units?.mass} \u00b7 ${conventions.units?.volume}` : 'BRL \u00b7 IPCA \u00b7 t \u00b7 m\u00b3';
  const activeView2 = window.viewById ? window.viewById(view) : null;
  const isCrossView = !!(activeView2 && activeView2.crossBanco);

  // Human label for the cross-source selection (used in citation + chips).
  const crossLabel = () => {
    const ser = crossState && crossState.series || [];
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
  const crossSourcesLabel = (activeView2?.sources || []).map(id => window.bancoById ? window.bancoById(id)?.short : id).filter(Boolean).join(' · ');
  const citation = isCrossView ? isPickerCite ? `EMPRESA BRASILEIRA DE PESQUISA AGROPECU\u00c1RIA (EMBRAPA). ` + `Dashboard de An\u00e1lise Hist\u00f3rica de Commodities \u2014 Cruzamento entre fontes \u2014 ` + `${crossLabel()}. Recorte: ${period}. ` + `Bras\u00edlia: Embrapa, 2026. Acesso em: ${accessedOn}.` : `EMPRESA BRASILEIRA DE PESQUISA AGROPECU\u00c1RIA (EMBRAPA). ` + `Dashboard de An\u00e1lise Hist\u00f3rica de Commodities \u2014 An\u00e1lise cruzada \u2014 ` + `${VIEW_LABEL[view] || view}${crossSourcesLabel ? ` (fontes: ${crossSourcesLabel})` : ''}. ` + `Recorte: ${period}. Bras\u00edlia: Embrapa, 2026. Acesso em: ${accessedOn}.` : `EMPRESA BRASILEIRA DE PESQUISA AGROPECU\u00c1RIA (EMBRAPA). ` + `Dashboard de An\u00e1lise Hist\u00f3rica de Commodities \u2014 ` + `${bancoCiteLabel} \u2014 ${VIEW_LABEL[view] || view}. ` + `Recorte: ${period}. Conven\u00e7\u00f5es m\u00e9tricas: ${convLabel}. ` + `Bras\u00edlia: Embrapa, 2026. Acesso em: ${accessedOn}.`;
  const onCite = () => setCiteOpen(true);
  const onShare = async () => {
    // Encode the current state in a query string researchers can paste.
    // Keys + array sentinel rules come from the shared codec (urlState.js) —
    // the same module the decoder (Dashboard.readStateFromURL) reads — so the
    // two halves can't drift on the wire format.
    const arrParam = window.urlEncodeArr;
    const state = {
      v: view,
      b: database,
      ip: infoPage,
      cur: conventions?.currency,
      corr: conventions?.correction,
      mu: conventions?.units?.mass,
      vu: conventions?.units?.volume,
      as: conventions?.autoScale ? 1 : 0,
      pb: arrParam(summary?.basket),
      fl: arrParam(summary?.flags),
      st: arrParam(summary?.states),
      vmn: summary?.valueMin ?? '',
      vmx: summary?.valueMax ?? '',
      sd: summary?.startDate || '',
      ed: summary?.endDate || '',
      // Cross-source selection: series as "banco:metric|banco:metric",
      // plus visualization mode and the comparable year window.
      xs: isCrossView && crossState?.series ? crossState.series.map(r => `${r.b}:${r.m}`).join('|') : '',
      xm: isCrossView ? crossState?.mode || '' : '',
      xy0: isCrossView && crossState?.y0 ? crossState.y0 : '',
      xy1: isCrossView && crossState?.y1 ? crossState.y1 : ''
    };
    const qs = window.urlEncodeState(state);
    const url = `${location.origin}${location.pathname}?${qs}`;
    try {
      await navigator.clipboard.writeText(url);
    } catch (e) {}
    setShared(true);
    setTimeout(() => setShared(false), 1800);
  };
  const onCopyCite = async () => {
    try {
      await navigator.clipboard.writeText(citation);
    } catch (e) {}
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "shell"
  }, /*#__PURE__*/React.createElement("header", {
    className: "topbar"
  }, /*#__PURE__*/React.createElement("button", {
    className: "brand brand-btn",
    onClick: () => {
      if (setInfoPage) setInfoPage('about');
    },
    title: "Voltar para Sobre o dashboard"
  }, /*#__PURE__*/React.createElement("img", {
    src: "assets/logo-embrapa-white-cropped.png",
    alt: "Embrapa",
    className: "brand-logo"
  })), /*#__PURE__*/React.createElement("div", {
    className: "sep"
  }), /*#__PURE__*/React.createElement("div", {
    className: "product-name"
  }, "An\xE1lise hist\xF3rica de commodities"), /*#__PURE__*/React.createElement("div", {
    className: "mode-switch",
    role: "tablist",
    "aria-label": "Modo de an\xE1lise"
  }, /*#__PURE__*/React.createElement("button", {
    role: "tab",
    "aria-selected": !isMulti,
    className: 'mode-opt ' + (!isMulti ? 'on' : ''),
    onClick: () => setMode && setMode('single'),
    title: "Analisar um banco de dados por vez"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "database",
    size: 15
  }), /*#__PURE__*/React.createElement("span", null, "Banco \xFAnico")), /*#__PURE__*/React.createElement("button", {
    role: "tab",
    "aria-selected": isMulti,
    className: 'mode-opt ' + (isMulti ? 'on' : ''),
    onClick: () => setMode && setMode('multi'),
    title: "Cruzar s\xE9ries de bancos diferentes no mesmo eixo de tempo"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "hub",
    size: 15
  }), /*#__PURE__*/React.createElement("span", null, "Multi-fonte"))), /*#__PURE__*/React.createElement("nav", {
    className: "topnav"
  }, /*#__PURE__*/React.createElement("button", {
    className: 'topnav-trigger ' + (navOpen ? 'open' : '') + (onInfoPage ? '' : ' has-active'),
    onClick: () => setNavOpen(o => !o),
    "aria-haspopup": "true",
    "aria-expanded": navOpen
  }, /*#__PURE__*/React.createElement("span", {
    className: "topnav-trigger-l"
  }, onInfoPage ? /*#__PURE__*/React.createElement("span", {
    className: "topnav-trigger-view"
  }, "Selecionar perspectiva") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: "topnav-trigger-grp"
  }, activeGroup?.label || 'Perspectiva'), /*#__PURE__*/React.createElement("span", {
    className: "topnav-trigger-view"
  }, activeView?.label || 'Visão geral'))), /*#__PURE__*/React.createElement(window.Icon, {
    name: "expand_more",
    size: 18
  })), navOpen && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "topnav-scrim",
    onClick: () => setNavOpen(false)
  }), /*#__PURE__*/React.createElement("div", {
    className: 'topnav-menu' + (isMulti ? ' narrow' : ''),
    role: "menu"
  }, /*#__PURE__*/React.createElement("div", {
    className: "topnav-menu-bar"
  }, /*#__PURE__*/React.createElement("span", {
    className: "topnav-menu-scope"
  }, isMulti ? /*#__PURE__*/React.createElement(React.Fragment, null, "Perspectivas ", /*#__PURE__*/React.createElement("strong", null, "multi-fonte"), " \xB7 entre bancos") : /*#__PURE__*/React.createElement(React.Fragment, null, "Perspectivas para ", /*#__PURE__*/React.createElement("strong", null, bancoMeta ? bancoMeta.short : 'banco'))), /*#__PURE__*/React.createElement("span", {
    className: "topnav-menu-legend"
  }, /*#__PURE__*/React.createElement("span", {
    className: "tnl-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "tnl-dot ok"
  }), "Dispon\xEDvel"), !isMulti && /*#__PURE__*/React.createElement("span", {
    className: "tnl-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "tnl-dot soon"
  }), "Em breve"), !isMulti && /*#__PURE__*/React.createElement("span", {
    className: "tnl-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "tnl-dot na"
  }), "N\xE3o se aplica"))), /*#__PURE__*/React.createElement("div", {
    className: "topnav-menu-grid"
  }, visibleGroups.map(g => /*#__PURE__*/React.createElement("div", {
    key: g.id,
    className: "topnav-grp"
  }, /*#__PURE__*/React.createElement("div", {
    className: "topnav-grp-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "topnav-grp-label"
  }, g.label), /*#__PURE__*/React.createElement("span", {
    className: "topnav-grp-hint"
  }, g.hint)), g.views.map(v => {
    const compat = window.viewAppliesTo ? window.viewAppliesTo(v.id, database) : {
      applies: true,
      missing: []
    };
    const applies = compat.applies;
    const supporters = !applies && window.bancosSupporting ? window.bancosSupporting(v.id) : [];
    const state = !applies ? 'na' : v.status === 'soon' ? 'soon' : 'ok';
    return /*#__PURE__*/React.createElement("button", {
      key: v.id,
      className: 'topnav-opt state-' + state + (!onInfoPage && view === v.id ? ' active' : ''),
      onClick: () => pickView(v.id),
      role: "menuitem",
      title: !applies ? `Requer ${window.missingCapsLabel(compat.missing)} — não disponível em ${bancoMeta?.short || 'este banco'}` : v.desc
    }, /*#__PURE__*/React.createElement("span", {
      className: "topnav-opt-top"
    }, /*#__PURE__*/React.createElement("span", {
      className: 'topnav-opt-dot ' + state
    }), /*#__PURE__*/React.createElement("span", {
      className: "topnav-opt-label"
    }, v.label), v.crossBanco && /*#__PURE__*/React.createElement("span", {
      className: "topnav-opt-tag cross"
    }, "multi-fonte"), state === 'soon' && /*#__PURE__*/React.createElement("span", {
      className: "topnav-opt-tag soon"
    }, "Em breve"), state === 'na' && /*#__PURE__*/React.createElement("span", {
      className: "topnav-opt-tag na"
    }, "N\xE3o se aplica")), !applies && supporters.length > 0 && /*#__PURE__*/React.createElement("span", {
      className: "topnav-opt-supporters"
    }, "dispon\xEDvel em ", supporters.map(b => b.short).join(' · ')));
  }))))))), /*#__PURE__*/React.createElement("div", {
    className: "util"
  }, /*#__PURE__*/React.createElement("button", {
    className: "util-action",
    onClick: onCite,
    title: "Citar este painel no estado atual"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "format_quote",
    size: 16
  }), /*#__PURE__*/React.createElement("span", null, "Citar painel")), /*#__PURE__*/React.createElement("button", {
    className: "util-action",
    onClick: onShare,
    title: "Copiar URL com o estado atual (filtros, view, conven\xE7\xF5es)"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "link",
    size: 16
  }), /*#__PURE__*/React.createElement("span", null, shared ? 'URL copiada' : 'Compartilhar')))), /*#__PURE__*/React.createElement("div", {
    className: "body"
  }, /*#__PURE__*/React.createElement("aside", {
    className: "sidebar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "side-section"
  }, isMulti ? 'Fontes no cruzamento' : 'Banco de dados'), isMulti ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "side-hint"
  }, onCrossPicker ? /*#__PURE__*/React.createElement(React.Fragment, null, "Reflete as s\xE9ries montadas no painel. Edite as fontes em ", /*#__PURE__*/React.createElement("strong", null, "Montagem do cruzamento"), ".") : /*#__PURE__*/React.createElement(React.Fragment, null, "Fontes combinadas por esta perspectiva.")), /*#__PURE__*/React.createElement("div", {
    className: "side-srclist",
    role: "list"
  }, bancos.map(b => {
    const incl = includedBancos.has(b.id);
    return /*#__PURE__*/React.createElement("div", {
      key: b.id,
      role: "listitem",
      className: 'side-src ' + (incl ? 'incl' : 'excl'),
      title: incl ? `${seriesCountByBanco[b.id] || ''} ${b.short} no cruzamento`.trim() : `${b.short} fora do cruzamento atual`
    }, /*#__PURE__*/React.createElement("span", {
      className: "side-src-dot"
    }), /*#__PURE__*/React.createElement("span", {
      className: "side-src-name"
    }, b.short), incl ? seriesCountByBanco[b.id] ? /*#__PURE__*/React.createElement("span", {
      className: "side-src-count tnum",
      title: `${seriesCountByBanco[b.id]} série(s)`
    }, seriesCountByBanco[b.id]) : /*#__PURE__*/React.createElement("span", {
      className: "side-src-in"
    }, "inclu\xEDda") : /*#__PURE__*/React.createElement(window.MaturityTag, {
      banco: b,
      size: "sm"
    }));
  }))) : bancos.map(b => {
    const active = database === b.id;
    return /*#__PURE__*/React.createElement("div", {
      key: b.id,
      className: 'side-item ' + (active ? onInfoPage ? 'selected' : 'active' : ''),
      onClick: () => onBanco(b.id),
      title: b.label
    }, /*#__PURE__*/React.createElement(window.UsageDot, {
      active: active
    }), /*#__PURE__*/React.createElement("span", {
      className: "side-item-l"
    }, b.short), /*#__PURE__*/React.createElement(window.MaturityTag, {
      banco: b,
      size: "sm"
    }));
  }), /*#__PURE__*/React.createElement("div", {
    className: "side-section"
  }, "Curadoria"), /*#__PURE__*/React.createElement("div", {
    className: 'side-item ' + (infoPage === 'curation' ? 'active' : ''),
    onClick: () => onInfo('curation')
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "fact_check"
  }), "Enriquecimento"), /*#__PURE__*/React.createElement("div", {
    className: "side-section"
  }, "Informa\xE7\xF5es"), /*#__PURE__*/React.createElement("div", {
    className: 'side-item ' + (infoPage === 'about' ? 'active' : ''),
    onClick: () => onInfo('about')
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "info"
  }), "Sobre o dashboard"), /*#__PURE__*/React.createElement("div", {
    className: 'side-item ' + (infoPage === 'glossary' ? 'active' : ''),
    onClick: () => onInfo('glossary')
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "menu_book"
  }), "Gloss\xE1rio global"), /*#__PURE__*/React.createElement("div", {
    className: 'side-item ' + (infoPage === 'health' ? 'active' : ''),
    onClick: () => onInfo('health')
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "pulse"
  }), "Sa\xFAde do sistema")), /*#__PURE__*/React.createElement("main", {
    className: "content"
  }, children)), citeOpen && /*#__PURE__*/React.createElement("div", {
    className: "cite-backdrop",
    onClick: () => setCiteOpen(false)
  }, /*#__PURE__*/React.createElement("div", {
    className: "cite-modal",
    onClick: e => e.stopPropagation(),
    role: "dialog",
    "aria-labelledby": "cite-title"
  }, /*#__PURE__*/React.createElement("header", {
    className: "cite-head"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "overline"
  }, "Cita\xE7\xE3o acad\xEAmica"), /*#__PURE__*/React.createElement("h2", {
    id: "cite-title"
  }, "Citar painel \xB7 ABNT NBR 6023"), /*#__PURE__*/React.createElement("p", {
    className: "caption"
  }, "Cita\xE7\xE3o do estado atual (banco, view, recorte temporal e conven\xE7\xF5es m\xE9tricas).")), /*#__PURE__*/React.createElement("button", {
    className: "fm-close",
    onClick: () => setCiteOpen(false),
    "aria-label": "Fechar"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "close",
    size: 18
  }))), /*#__PURE__*/React.createElement("div", {
    className: "cite-body"
  }, /*#__PURE__*/React.createElement("pre", {
    className: "cite-text"
  }, citation), /*#__PURE__*/React.createElement("div", {
    className: "cite-actions"
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn-secondary",
    onClick: () => setCiteOpen(false)
  }, "Fechar"), /*#__PURE__*/React.createElement("button", {
    className: "btn-primary",
    onClick: onCopyCite
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "content_copy",
    size: 14
  }), " Copiar cita\xE7\xE3o"))))), /*#__PURE__*/React.createElement("footer", {
    className: "footer"
  }, /*#__PURE__*/React.createElement("img", {
    src: "assets/triade-horizontal-black.png",
    alt: "Embrapa \xB7 Minist\xE9rio da Agricultura e Pecu\xE1ria \xB7 Governo do Brasil",
    className: "triade"
  }), /*#__PURE__*/React.createElement("div", {
    className: "foot-meta"
  }, /*#__PURE__*/React.createElement("div", null, "\xA9 Empresa Brasileira de Pesquisa Agropecu\xE1ria"), /*#__PURE__*/React.createElement("div", {
    className: "caption"
  }, "Minist\xE9rio da Agricultura e Pecu\xE1ria \xB7 Pipeline Bronze \u2192 Silver \u2192 Gold \xB7 BigQuery + Looker Studio"), /*#__PURE__*/React.createElement("div", {
    className: "caption"
  }, /*#__PURE__*/React.createElement("a", {
    href: "#"
  }, "www.embrapa.br"), " \xA0\xB7\xA0 ", /*#__PURE__*/React.createElement("a", {
    href: "#"
  }, "Servi\xE7o de Atendimento ao Cidad\xE3o (SAC)")))));
}
window.AppShell = AppShell;
})(); } catch (e) { __ds_ns.__errors.push({ path: "AppShell.jsx", error: String((e && e.message) || e) }); }

// Atoms.jsx
try { (() => {
// SectionHeader + small shared components

function SectionHeader({
  overline,
  title,
  action
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "section-head"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "overline"
  }, overline), /*#__PURE__*/React.createElement("h3", {
    className: "section-title"
  }, title)), action && /*#__PURE__*/React.createElement("div", {
    className: "section-action"
  }, action));
}
Object.assign(window, {
  SectionHeader
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "Atoms.jsx", error: String((e && e.message) || e) }); }

// Charts.chain.jsx
try { (() => {
// Charts.chain.jsx — visualizations for the extended (chain / lead-lag)
// perspectives. The chain balance reuses the existing <SankeyChart>; these
// two cover the monthly lead-lag view.
//
//   MonthlyOverlay — two 12-month profiles on one axis, month-labelled.
//   LagBars        — signed cross-correlation by lag (−6…+6 months).

// ── MonthlyOverlay ───────────────────────────────────────────────────
//   series : [{ name, color, data: number[12] }]
//   months : string[12]
function MonthlyOverlay({
  series,
  months,
  height = 280,
  label = 'índice (pico = 100)',
  markers = []
}) {
  const W = 720,
    H = height,
    P = {
      l: 40,
      r: 14,
      t: 16,
      b: 28
    };
  const n = 12;
  const all = series.flatMap(s => s.data);
  const maxY = Math.max(...all, 0) * 1.08 || 1;
  const x = i => P.l + i / (n - 1) * (W - P.l - P.r);
  const y = v => P.t + (1 - v / maxY) * (H - P.t - P.b);
  const yTicks = 4;
  const ticks = Array.from({
    length: yTicks + 1
  }, (_, i) => maxY / yTicks * i);
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, ticks.map((t, i) => /*#__PURE__*/React.createElement("g", {
    key: i
  }, /*#__PURE__*/React.createElement("line", {
    className: "grid",
    x1: P.l,
    x2: W - P.r,
    y1: y(t),
    y2: y(t)
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: y(t) + 3,
    textAnchor: "end"
  }, t.toLocaleString('pt-BR', {
    maximumFractionDigits: 0
  })))), markers.map((mk, i) => /*#__PURE__*/React.createElement("line", {
    key: 'mk' + i,
    x1: x(mk.month),
    x2: x(mk.month),
    y1: P.t,
    y2: H - P.b,
    stroke: mk.color,
    strokeWidth: "1.4",
    strokeDasharray: "4 4",
    opacity: "0.6"
  })), series.map((s, si) => {
    const pts = s.data.map((v, i) => `${x(i)},${y(v)}`).join(' ');
    return /*#__PURE__*/React.createElement("g", {
      key: si
    }, /*#__PURE__*/React.createElement("polyline", {
      points: pts,
      fill: "none",
      stroke: s.color,
      strokeWidth: "2.4",
      strokeLinejoin: "round"
    }), s.data.map((v, i) => /*#__PURE__*/React.createElement("circle", {
      key: i,
      cx: x(i),
      cy: y(v),
      r: "2.4",
      fill: s.color
    })));
  }), months.map((m, i) => /*#__PURE__*/React.createElement("text", {
    key: m,
    className: "axis",
    x: x(i),
    y: H - P.b + 15,
    textAnchor: "middle"
  }, m)), /*#__PURE__*/React.createElement("text", {
    className: "axis-label",
    x: P.l,
    y: 10
  }, label));
}

// ── LagBars ──────────────────────────────────────────────────────────
//   profile : [{ lag, corr }]   (lag in months, corr in −1…1)
//   best    : { lag, corr }     (highlighted)
function LagBars({
  profile,
  best,
  height = 240
}) {
  const W = 720,
    H = height,
    P = {
      l: 40,
      r: 14,
      t: 18,
      b: 34
    };
  const bandW = (W - P.l - P.r) / profile.length;
  const max = 1;
  const y0 = P.t + (H - P.t - P.b) / 2;
  const yScale = v => y0 - v / max * ((H - P.t - P.b) / 2);
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, /*#__PURE__*/React.createElement("line", {
    className: "axis-baseline",
    x1: P.l,
    x2: W - P.r,
    y1: y0,
    y2: y0,
    stroke: "var(--border-strong)"
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: yScale(1) + 3,
    textAnchor: "end"
  }, "+1"), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: y0 + 3,
    textAnchor: "end"
  }, "0"), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: yScale(-1) + 3,
    textAnchor: "end"
  }, "\u22121"), profile.map((d, i) => {
    const xx = P.l + i * bandW;
    const isBest = best && d.lag === best.lag;
    const v = d.corr;
    const yb = v >= 0 ? yScale(v) : y0;
    const h = Math.abs(yScale(v) - y0);
    const fill = isBest ? 'var(--embrapa-green)' : v >= 0 ? 'var(--viz-4)' : 'var(--err)';
    return /*#__PURE__*/React.createElement("g", {
      key: d.lag
    }, /*#__PURE__*/React.createElement("rect", {
      x: xx + 3,
      y: yb,
      width: bandW - 6,
      height: Math.max(1, h),
      fill: fill,
      opacity: isBest ? 1 : 0.7,
      rx: "2"
    }, /*#__PURE__*/React.createElement("title", null, "defasagem ", d.lag >= 0 ? '+' : '', d.lag, " m: r = ", d.corr.toFixed(2))), /*#__PURE__*/React.createElement("text", {
      className: "axis",
      x: xx + bandW / 2,
      y: H - P.b + 15,
      textAnchor: "middle",
      style: isBest ? {
        fontWeight: 700,
        fill: 'var(--embrapa-green-darker)'
      } : null
    }, d.lag >= 0 ? '+' : '', d.lag));
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis-label",
    x: P.l,
    y: 11
  }, "correla\xE7\xE3o (r)"), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: W - P.r,
    y: H - 4,
    textAnchor: "end",
    style: {
      opacity: 0.7
    }
  }, "defasagem dos embarques (meses) \u2192"));
}
Object.assign(window, {
  MonthlyOverlay,
  LagBars
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "Charts.chain.jsx", error: String((e && e.message) || e) }); }

// Charts.cross.jsx
try { (() => {
// Charts.cross.jsx — visualizations specific to the cross-source view.
// Generic and data-agnostic: they consume plain { label, color, unit,
// data:[{y,v}] } series, so they work unchanged when real bancos go live.
//
//   DualAxisLineChart — up to 2 distinct units, each on its own Y axis.
//   StackedPanels     — one synced mini-panel per series (any N, any units).
//
// Base-100 normalization reuses the shared <MultiLineChart> (Charts.jsx).

// Compact axis-tick formatter — shared impl in data.js (window.fmtAxisTick).
const _csFmtAxis = window.fmtAxisTick;

// ── DualAxisLineChart ───────────────────────────────────────────────
// Groups series by `unit`. The first unit maps to the LEFT axis, the
// second to the RIGHT. (The view caps dual-axis mode at 2 distinct units.)
function DualAxisLineChart({
  series,
  height = 320
}) {
  const W = 760,
    H = height,
    P = {
      l: 56,
      r: 60,
      t: 18,
      b: 30
    };
  const years = (series[0]?.data || []).map(d => d.y);
  const units = [];
  series.forEach(s => {
    if (!units.includes(s.unit)) units.push(s.unit);
  });
  const leftUnit = units[0],
    rightUnit = units[1];
  const maxFor = unit => {
    const vals = series.filter(s => s.unit === unit).flatMap(s => s.data.map(d => d.v));
    return Math.max(...vals, 0) * 1.1 || 1;
  };
  const minFor = unit => {
    const vals = series.filter(s => s.unit === unit).flatMap(s => s.data.map(d => d.v));
    return Math.min(...vals, 0);
  };
  const scale = {};
  // Scale EVERY unit to its own range so no series collapses to a flat line
  // when 3+ units are selected; only the axis labels are limited to two.
  units.forEach(u => {
    scale[u] = {
      min: minFor(u),
      max: maxFor(u)
    };
  });
  const x = i => P.l + i / (years.length - 1 || 1) * (W - P.l - P.r);
  const yFor = (unit, v) => {
    const sc = scale[unit] || {
      min: 0,
      max: 1
    };
    return P.t + (1 - (v - sc.min) / (sc.max - sc.min || 1)) * (H - P.t - P.b);
  };
  const yTicks = 4;
  const leftTicks = Array.from({
    length: yTicks + 1
  }, (_, i) => (scale[leftUnit]?.min ?? 0) + ((scale[leftUnit]?.max ?? 1) - (scale[leftUnit]?.min ?? 0)) / yTicks * i);
  const rightTicks = rightUnit ? Array.from({
    length: yTicks + 1
  }, (_, i) => (scale[rightUnit]?.min ?? 0) + ((scale[rightUnit]?.max ?? 1) - (scale[rightUnit]?.min ?? 0)) / yTicks * i) : [];
  const xTickEvery = Math.max(1, Math.ceil(years.length / 8));
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, leftTicks.map((t, i) => /*#__PURE__*/React.createElement("g", {
    key: 'l' + i
  }, /*#__PURE__*/React.createElement("line", {
    className: "grid",
    x1: P.l,
    x2: W - P.r,
    y1: yFor(leftUnit, t),
    y2: yFor(leftUnit, t)
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: yFor(leftUnit, t) + 3,
    textAnchor: "end"
  }, _csFmtAxis(t)))), rightTicks.map((t, i) => /*#__PURE__*/React.createElement("text", {
    key: 'r' + i,
    className: "axis",
    x: W - P.r + 6,
    y: yFor(rightUnit, t) + 3,
    textAnchor: "start"
  }, _csFmtAxis(t))), series.map((s, si) => {
    const pts = s.data.map((d, i) => `${x(i)},${yFor(s.unit, d.v)}`).join(' ');
    return /*#__PURE__*/React.createElement("g", {
      key: si
    }, /*#__PURE__*/React.createElement("polyline", {
      points: pts,
      fill: "none",
      stroke: s.color,
      strokeWidth: "2.25",
      strokeLinejoin: "round"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: x(s.data.length - 1),
      cy: yFor(s.unit, s.data[s.data.length - 1].v),
      r: "3.2",
      fill: s.color
    }));
  }), years.map((yv, i) => i % xTickEvery === 0 || i === years.length - 1 ? /*#__PURE__*/React.createElement("text", {
    key: yv,
    className: "axis",
    x: x(i),
    y: H - P.b + 16,
    textAnchor: "middle"
  }, yv) : null), /*#__PURE__*/React.createElement("text", {
    className: "axis-label",
    x: P.l - 48,
    y: 11,
    style: {
      fill: 'var(--fg-2)'
    }
  }, leftUnit || ''), rightUnit && /*#__PURE__*/React.createElement("text", {
    className: "axis-label",
    x: W - P.r + 2,
    y: 11,
    textAnchor: "start",
    style: {
      fill: 'var(--fg-2)'
    }
  }, rightUnit));
}

// ── StackedPanels ───────────────────────────────────────────────────
// One mini line-panel per series, stacked vertically and aligned on a
// shared year axis. Handles any number of series and any mix of units.
function StackedPanels({
  series,
  panelHeight = 96
}) {
  const W = 760,
    P = {
      l: 56,
      r: 14
    };
  const years = (series[0]?.data || []).map(d => d.y);
  const xTickEvery = Math.max(1, Math.ceil(years.length / 8));
  const x = i => P.l + i / (years.length - 1 || 1) * (W - P.l - P.r);
  return /*#__PURE__*/React.createElement("div", {
    className: "xs-panels"
  }, series.map((s, si) => {
    const H = panelHeight,
      pt = 14,
      pb = 10;
    const vals = s.data.map(d => d.v);
    const max = Math.max(...vals, 0) * 1.1 || 1;
    const min = Math.min(...vals, 0);
    const y = v => pt + (1 - (v - min) / (max - min || 1)) * (H - pt - pb);
    const pts = s.data.map((d, i) => `${x(i)},${y(d.v)}`).join(' ');
    const area = `${P.l},${H - pb} ${pts} ${x(s.data.length - 1)},${H - pb}`;
    const last = s.data[s.data.length - 1];
    return /*#__PURE__*/React.createElement("div", {
      className: "xs-panel",
      key: si
    }, /*#__PURE__*/React.createElement("div", {
      className: "xs-panel-head"
    }, /*#__PURE__*/React.createElement("span", {
      className: "xs-panel-dot",
      style: {
        background: s.color
      }
    }), /*#__PURE__*/React.createElement("span", {
      className: "xs-panel-label"
    }, s.label), /*#__PURE__*/React.createElement("span", {
      className: "xs-panel-src"
    }, s.bancoShort), /*#__PURE__*/React.createElement("span", {
      className: "xs-panel-unit tnum"
    }, _csFmtAxis(last?.v), " ", s.unit)), /*#__PURE__*/React.createElement("svg", {
      viewBox: `0 0 ${W} ${H}`,
      className: "chart",
      preserveAspectRatio: "none",
      style: {
        height: H
      }
    }, /*#__PURE__*/React.createElement("line", {
      className: "grid",
      x1: P.l,
      x2: W - P.r,
      y1: y(max / 1.1),
      y2: y(max / 1.1)
    }), /*#__PURE__*/React.createElement("line", {
      className: "grid",
      x1: P.l,
      x2: W - P.r,
      y1: y(min),
      y2: y(min)
    }), /*#__PURE__*/React.createElement("text", {
      className: "axis",
      x: P.l - 6,
      y: y(max / 1.1) + 3,
      textAnchor: "end"
    }, _csFmtAxis(max / 1.1)), /*#__PURE__*/React.createElement("polygon", {
      points: area,
      fill: s.color,
      opacity: "0.10"
    }), /*#__PURE__*/React.createElement("polyline", {
      points: pts,
      fill: "none",
      stroke: s.color,
      strokeWidth: "2",
      strokeLinejoin: "round"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: x(s.data.length - 1),
      cy: y(last.v),
      r: "3",
      fill: s.color
    })));
  }), /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} 22`,
    className: "chart xs-panels-axis",
    preserveAspectRatio: "none",
    style: {
      height: 22
    }
  }, years.map((yv, i) => i % xTickEvery === 0 || i === years.length - 1 ? /*#__PURE__*/React.createElement("text", {
    key: yv,
    className: "axis",
    x: x(i),
    y: 14,
    textAnchor: "middle"
  }, yv) : null)));
}
Object.assign(window, {
  DualAxisLineChart,
  StackedPanels
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "Charts.cross.jsx", error: String((e && e.message) || e) }); }

// Charts.flow.jsx
try { (() => {
// Charts.flow.jsx — generic flow / seasonality visualizations + the
// preview banner. These components are data-source agnostic: they consume
// the contracts from previewData.js and will be reused unchanged when the
// real bancos go live.

// ── PreviewBanner ─────────────────────────────────────────────────────
function PreviewBanner({
  banco,
  capabilityNote
}) {
  // Only promise a future "liberação" for a banco that ISN'T live yet. If the
  // banco passed is live (or absent), drop that clause — never claim a live
  // banco will be "liberado".
  const pending = banco && banco.status !== 'live';
  const date = pending && window.bancoMeta ? window.bancoMeta(banco.id).maturityDate || null : null;
  return /*#__PURE__*/React.createElement("div", {
    className: "pv-banner"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pv-badge"
  }, "Pr\xE9-visualiza\xE7\xE3o"), /*#__PURE__*/React.createElement("span", {
    className: "pv-text"
  }, "Dados ", /*#__PURE__*/React.createElement("strong", null, "sint\xE9ticos de demonstra\xE7\xE3o"), ". ", capabilityNote || '', ' ', pending ? /*#__PURE__*/React.createElement(React.Fragment, null, "Esta perspectiva j\xE1 est\xE1 constru\xEDda; quando ", /*#__PURE__*/React.createElement("strong", null, banco.short), " for liberado", date ? ` (${date})` : '', ", os mesmos gr\xE1ficos passam a refletir dados reais \u2014 sem mudan\xE7a de layout.") : /*#__PURE__*/React.createElement(React.Fragment, null, "Os mesmos gr\xE1ficos passam a refletir dados reais assim que o cruzamento ler o Gold real \u2014 sem mudan\xE7a de layout.")));
}

// ── SankeyChart — simplified two-column flow diagram ──────────────────
//   nodes : [{ id, label, side:'origin'|'dest', value }]
//   links : [{ source, target, value }]
function SankeyChart({
  nodes,
  links,
  height = 360,
  unit = ''
}) {
  const W = 720,
    H = height,
    P = {
      t: 16,
      b: 16
    };
  const colX = {
    origin: 150,
    dest: W - 150
  };
  const nodeW = 13,
    gap = 10;
  const origins = nodes.filter(n => n.side === 'origin');
  const dests = nodes.filter(n => n.side === 'dest');
  const layoutCol = list => {
    const total = list.reduce((s, n) => s + n.value, 0) || 1;
    const avail = H - P.t - P.b - gap * (list.length - 1);
    let y = P.t;
    const pos = {};
    list.forEach(n => {
      const h = Math.max(6, n.value / total * avail);
      pos[n.id] = {
        y,
        h,
        cy: y + h / 2
      };
      y += h + gap;
    });
    return pos;
  };
  const oPos = layoutCol(origins);
  const dPos = layoutCol(dests);
  const pos = {
    ...oPos,
    ...dPos
  };
  const COLORS = ['var(--viz-1)', 'var(--viz-2)', 'var(--viz-3)', 'var(--viz-4)', 'var(--viz-5)', 'var(--viz-7)'];
  const colorOf = id => COLORS[origins.findIndex(o => o.id === id) % COLORS.length] || 'var(--viz-1)';

  // track running offset within each node for ribbon stacking
  const oOff = {},
    dOff = {};
  origins.forEach(n => oOff[n.id] = 0);
  dests.forEach(n => dOff[n.id] = 0);
  const maxLink = Math.max(...links.map(l => l.value), 1);
  const ribbons = links.map((l, i) => {
    const s = pos[l.source],
      t = pos[l.target];
    if (!s || !t) return null;
    const sTotal = origins.find(o => o.id === l.source).value || 1;
    const tTotal = dests.find(d => d.id === l.target).value || 1;
    const sh = l.value / sTotal * s.h;
    const th = l.value / tTotal * t.h;
    const sy = s.y + oOff[l.source];
    oOff[l.source] += sh;
    const ty = t.y + dOff[l.target];
    dOff[l.target] += th;
    const x0 = colX.origin + nodeW,
      x1 = colX.dest;
    const mx = (x0 + x1) / 2;
    const path = `M${x0},${sy} C${mx},${sy} ${mx},${ty} ${x1},${ty} L${x1},${ty + th} C${mx},${ty + th} ${mx},${sy + sh} ${x0},${sy + sh} Z`;
    return /*#__PURE__*/React.createElement("path", {
      key: i,
      d: path,
      fill: colorOf(l.source),
      opacity: 0.22 + 0.4 * (l.value / maxLink)
    });
  });
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, ribbons, origins.map(n => /*#__PURE__*/React.createElement("g", {
    key: n.id
  }, /*#__PURE__*/React.createElement("rect", {
    x: colX.origin,
    y: pos[n.id].y,
    width: nodeW,
    height: pos[n.id].h,
    rx: "2",
    fill: colorOf(n.id)
  }), /*#__PURE__*/React.createElement("text", {
    className: "sankey-lbl",
    x: colX.origin - 8,
    y: pos[n.id].cy + 3,
    textAnchor: "end"
  }, n.label))), dests.map(n => /*#__PURE__*/React.createElement("g", {
    key: n.id
  }, /*#__PURE__*/React.createElement("rect", {
    x: colX.dest - nodeW,
    y: pos[n.id].y,
    width: nodeW,
    height: pos[n.id].h,
    rx: "2",
    fill: "var(--pres-gray-400)"
  }), /*#__PURE__*/React.createElement("text", {
    className: "sankey-lbl",
    x: colX.dest + 8,
    y: pos[n.id].cy + 3,
    textAnchor: "start"
  }, n.label))));
}

// ── MonthYearHeatmap — 12 months (cols) × years (rows) ────────────────
//   matrix : { [year]: number[12] }
function MonthYearHeatmap({
  matrix,
  years,
  unit = '',
  height
}) {
  const W = 720;
  const ROW_LABEL_W = 54,
    PAD_TOP = 24,
    PAD_BOT = 8;
  const ROW_H = 22,
    GAP = 3;
  const rows = years.slice().sort((a, b) => b - a);
  const H = height || PAD_TOP + rows.length * (ROW_H + GAP) + PAD_BOT;
  const cellW = (W - ROW_LABEL_W) / 12;
  const all = rows.flatMap(y => matrix[y]);
  const max = Math.max(...all, 1),
    min = Math.min(...all, 0);
  const STOPS = ['var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)', 'var(--heat-5)', 'var(--heat-6)', 'var(--heat-7)'];
  const color = v => STOPS[Math.min(STOPS.length - 1, Math.floor((v - min) / (max - min || 1) * (STOPS.length - 1) + 0.5))];
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart heatmap",
    preserveAspectRatio: "xMidYMid meet"
  }, window.MONTH_LABELS.map((m, i) => /*#__PURE__*/React.createElement("text", {
    key: m,
    className: "axis",
    x: ROW_LABEL_W + i * cellW + cellW / 2,
    y: 16,
    textAnchor: "middle"
  }, m)), rows.map((y, ri) => {
    const ry = PAD_TOP + ri * (ROW_H + GAP);
    return /*#__PURE__*/React.createElement("g", {
      key: y
    }, /*#__PURE__*/React.createElement("text", {
      className: "axis",
      x: ROW_LABEL_W - 8,
      y: ry + ROW_H * 0.7,
      textAnchor: "end"
    }, y), matrix[y].map((v, ci) => /*#__PURE__*/React.createElement("rect", {
      key: ci,
      x: ROW_LABEL_W + ci * cellW + 1,
      y: ry,
      width: cellW - 1,
      height: ROW_H,
      rx: "2",
      fill: color(v)
    }, /*#__PURE__*/React.createElement("title", null, window.MONTH_LABELS[ci], "/", y, ": ", v.toLocaleString('pt-BR'), " ", unit))));
  }));
}
Object.assign(window, {
  PreviewBanner,
  SankeyChart,
  MonthYearHeatmap
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "Charts.flow.jsx", error: String((e && e.message) || e) }); }

// Charts.geo.jsx
try { (() => {
// Charts.geo.jsx — geographic and matrix visualizations
//   · BrazilTileMap   choropleth-style hex/tile map of the 27 UFs
//   · Heatmap         year × category color matrix
//   · StackedArea     stacked area for product composition over time
//   · YoYBars         year-over-year variation, signed bars
//   · FlagBars        100% stacked bar for quality flag distribution
//   · RegionBars      vertical bar chart for region totals
//   · LorenzCurve     cumulative-share curve (used by Concentração)
//
// Hand-rolled SVG — no chart library. Sized for dashboard cards.

// ────────────────────────────────────────────────────────────────────
// BrazilTileMap — geospatial choropleth on a 9-row tile grid
// ────────────────────────────────────────────────────────────────────
function BrazilTileMap({
  data,
  valueKey = 'value',
  label = 'R$ mi',
  height = 420,
  onSelect
}) {
  // 8 cols × 9 rows; each cell ~ 56×52
  const COLS = 8,
    ROWS = 9;
  const CELL_W = 60,
    CELL_H = 56,
    GAP = 4;
  const W = COLS * (CELL_W + GAP);
  const H = ROWS * (CELL_H + GAP);
  const vals = data.map(d => d[valueKey] || 0);
  const max = vals.length ? Math.max(...vals) : 0;
  const min = vals.length ? Math.min(...vals) : 0;

  // 7-step sequential scale — single source of truth (--heat-* tokens)
  const STOPS = ['var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)', 'var(--heat-5)', 'var(--heat-6)', 'var(--heat-7)'];
  // Shared bucket index so cell fill and label color never disagree.
  const level = v => {
    if (!v) return -1;
    const t = (v - min) / (max - min || 1);
    return Math.min(STOPS.length - 1, Math.floor(t * (STOPS.length - 1) + 0.5));
  };
  const color = v => {
    const i = level(v);
    return i < 0 ? 'var(--heat-0)' : STOPS[i];
  };
  const textColor = v => {
    const i = level(v);
    // White only from --heat-5 down (dark enough); dark ink on light cells.
    return i < 0 ? 'var(--fg-3)' : i >= 4 ? '#fff' : 'var(--fg-1)';
  };

  // Region outline groups — faint categorical washes, driven by the viz scale
  // (regions are a categorical dimension; --viz-* is the categorical palette).
  const REGION_BG = {
    N: 'color-mix(in srgb, var(--viz-2) 10%, transparent)',
    NE: 'color-mix(in srgb, var(--viz-3) 10%, transparent)',
    CO: 'color-mix(in srgb, var(--viz-6) 10%, transparent)',
    SE: 'color-mix(in srgb, var(--viz-1) 10%, transparent)',
    S: 'color-mix(in srgb, var(--viz-9) 10%, transparent)'
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "bmap-wrap"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "bmap",
    preserveAspectRatio: "xMidYMid meet"
  }, data.map(d => {
    const x = d.col * (CELL_W + GAP);
    const y = d.row * (CELL_H + GAP);
    const v = d[valueKey] || 0;
    return /*#__PURE__*/React.createElement("g", {
      key: d.uf,
      className: "bmap-cell",
      onClick: onSelect ? () => onSelect(d) : undefined
    }, /*#__PURE__*/React.createElement("rect", {
      x: x,
      y: y,
      width: CELL_W,
      height: CELL_H,
      rx: "6",
      fill: color(v),
      stroke: REGION_BG[d.region],
      strokeWidth: "2"
    }), /*#__PURE__*/React.createElement("text", {
      x: x + CELL_W / 2,
      y: y + 22,
      textAnchor: "middle",
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 13,
        fontWeight: 700,
        fill: textColor(v)
      }
    }, d.uf), /*#__PURE__*/React.createElement("text", {
      x: x + CELL_W / 2,
      y: y + 40,
      textAnchor: "middle",
      style: {
        fontFamily: 'var(--font-body)',
        fontSize: 10.5,
        fill: textColor(v),
        opacity: 0.85
      }
    }, v ? v.toLocaleString('pt-BR', {
      maximumFractionDigits: 0
    }) : '—'));
  })), /*#__PURE__*/React.createElement("div", {
    className: "bmap-legend"
  }, /*#__PURE__*/React.createElement("span", {
    className: "caption"
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "bmap-scale"
  }, STOPS.map((c, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      background: c
    }
  }))), /*#__PURE__*/React.createElement("span", {
    className: "caption tnum"
  }, min.toLocaleString('pt-BR'), " \u2013 ", max.toLocaleString('pt-BR'))));
}

// ────────────────────────────────────────────────────────────────────
// Heatmap — year × category matrix
//   rows : array of { id, label, values: [{ y, v } ...] }
// ────────────────────────────────────────────────────────────────────
function Heatmap({
  rows,
  valueKey = 'v',
  valueLabel = '',
  height
}) {
  const W = 720;
  const ROW_LABEL_W = 120;
  const PAD_TOP = 22,
    PAD_BOTTOM = 22;
  const ROW_H = 22,
    GAP = 2;
  // No rows (e.g. all UFs filtered out) → empty plot area, never touch rows[0].
  if (!rows || rows.length === 0 || !rows[0].values?.length) {
    const H0 = height || PAD_TOP + PAD_BOTTOM;
    return /*#__PURE__*/React.createElement("svg", {
      viewBox: `0 0 ${W} ${H0}`,
      className: "chart heatmap",
      preserveAspectRatio: "xMidYMid meet"
    });
  }
  const cols = rows[0].values.map(d => d.y);
  const cellW = (W - ROW_LABEL_W) / cols.length;
  const H = height || PAD_TOP + rows.length * (ROW_H + GAP) + PAD_BOTTOM;
  const all = rows.flatMap(r => r.values.map(v => v[valueKey] || 0));
  const max = Math.max(...all);
  const min = Math.min(...all);
  const STOPS = ['var(--heat-1)', 'var(--heat-2)', 'var(--heat-3)', 'var(--heat-4)', 'var(--heat-5)', 'var(--heat-6)', 'var(--heat-7)'];
  const color = v => {
    if (v == null) return 'var(--heat-0)';
    const t = (v - min) / (max - min || 1);
    return STOPS[Math.min(STOPS.length - 1, Math.floor(t * (STOPS.length - 1) + 0.5))];
  };

  // Show every 4th year on x axis
  const xTickEvery = Math.max(1, Math.ceil(cols.length / 8));
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart heatmap",
    preserveAspectRatio: "xMidYMid meet"
  }, rows.map((r, ri) => {
    const ry = PAD_TOP + ri * (ROW_H + GAP);
    return /*#__PURE__*/React.createElement("g", {
      key: r.id
    }, /*#__PURE__*/React.createElement("text", {
      className: "axis",
      x: ROW_LABEL_W - 8,
      y: ry + ROW_H * 0.7,
      textAnchor: "end"
    }, r.label), r.values.map((d, ci) => /*#__PURE__*/React.createElement("rect", {
      key: d.y,
      x: ROW_LABEL_W + ci * cellW + 1,
      y: ry,
      width: cellW - 1,
      height: ROW_H,
      fill: color(d[valueKey]),
      rx: "1.5"
    }, /*#__PURE__*/React.createElement("title", null, r.label, " \xB7 ", d.y, " : ", (d[valueKey] || 0).toLocaleString('pt-BR'), " ", valueLabel))));
  }), cols.map((y, ci) => ci % xTickEvery === 0 || ci === cols.length - 1 ? /*#__PURE__*/React.createElement("text", {
    key: y,
    className: "axis",
    x: ROW_LABEL_W + ci * cellW + cellW / 2,
    y: H - 6,
    textAnchor: "middle"
  }, y) : null));
}

// ────────────────────────────────────────────────────────────────────
// StackedArea — products as stacked layers over time
//   series : [{ code, name, color, data: [{ y, v }] }]
// ────────────────────────────────────────────────────────────────────
function StackedArea({
  series,
  height = 260,
  valueKey = 'v',
  label = 'R$ mi'
}) {
  const W = 720,
    H = height,
    P = {
      l: 44,
      r: 12,
      t: 14,
      b: 28
    };
  // No series (e.g. empty basket) → render an empty plot area, never crash.
  if (!series || series.length === 0 || !series[0]?.data?.length) {
    return /*#__PURE__*/React.createElement("svg", {
      viewBox: `0 0 ${W} ${H}`,
      className: "chart",
      preserveAspectRatio: "xMidYMid meet"
    });
  }
  const years = series[0].data.map(d => d.y);
  // total per year for normalization (we render absolute stacks)
  const totals = years.map((_, i) => series.reduce((s, sr) => s + (sr.data[i][valueKey] || 0), 0));
  const maxY = Math.max(...totals) * 1.05 || 1;
  const x = i => P.l + i / (years.length - 1) * (W - P.l - P.r);
  const y = v => P.t + (1 - v / maxY) * (H - P.t - P.b);

  // Compute cumulative per layer
  const layers = series.map((sr, si) => {
    const top = sr.data.map((_, i) => {
      let acc = 0;
      for (let k = 0; k <= si; k++) acc += series[k].data[i][valueKey] || 0;
      return acc;
    });
    const bottom = sr.data.map((_, i) => {
      let acc = 0;
      for (let k = 0; k < si; k++) acc += series[k].data[i][valueKey] || 0;
      return acc;
    });
    const pts = [...top.map((v, i) => `${x(i)},${y(v)}`), ...bottom.map((v, i) => `${x(i)},${y(v)}`).reverse()].join(' ');
    return {
      ...sr,
      pts
    };
  });
  const yTicks = 4;
  const ticks = Array.from({
    length: yTicks + 1
  }, (_, i) => maxY / yTicks * i);
  const xTickEvery = Math.max(1, Math.ceil(years.length / 7));
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, ticks.map((t, i) => /*#__PURE__*/React.createElement("g", {
    key: i
  }, /*#__PURE__*/React.createElement("line", {
    className: "grid",
    x1: P.l,
    x2: W - P.r,
    y1: y(t),
    y2: y(t)
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: y(t) + 3,
    textAnchor: "end"
  }, t.toLocaleString('pt-BR', {
    maximumFractionDigits: 0
  })))), layers.map((l, i) => /*#__PURE__*/React.createElement("polygon", {
    key: i,
    points: l.pts,
    fill: l.color,
    opacity: 0.92
  }, /*#__PURE__*/React.createElement("title", null, l.name))), years.map((yv, i) => i % xTickEvery === 0 || i === years.length - 1 ? /*#__PURE__*/React.createElement("text", {
    key: yv,
    className: "axis",
    x: x(i),
    y: H - P.b + 14,
    textAnchor: "middle"
  }, yv) : null), /*#__PURE__*/React.createElement("text", {
    className: "axis-label",
    x: P.l,
    y: 10
  }, label));
}

// ────────────────────────────────────────────────────────────────────
// YoYBars — year-over-year variation, signed
// ────────────────────────────────────────────────────────────────────
function YoYBars({
  data,
  valueKey = 'v',
  height = 200
}) {
  const W = 720,
    H = height,
    P = {
      l: 36,
      r: 12,
      t: 14,
      b: 28
    };
  if (!data || data.length === 0) {
    return /*#__PURE__*/React.createElement("svg", {
      viewBox: `0 0 ${W} ${H}`,
      className: "chart",
      preserveAspectRatio: "xMidYMid meet"
    });
  }
  // prev === 0 (or missing) → 0% rather than a divide-by-zero NaN/Infinity.
  const yoy = data.map((d, i) => {
    const prev = i === 0 ? null : data[i - 1][valueKey];
    return {
      y: d.y,
      pct: i === 0 || !prev ? 0 : (d[valueKey] - prev) / prev * 100
    };
  });
  const max = Math.max(...yoy.map(d => Math.abs(d.pct))) * 1.15 || 1;
  const bandW = (W - P.l - P.r) / yoy.length;
  const y0 = P.t + (H - P.t - P.b) / 2;
  const yScale = v => y0 - v / max * ((H - P.t - P.b) / 2);
  const xTickEvery = Math.max(1, Math.ceil(yoy.length / 8));
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, /*#__PURE__*/React.createElement("line", {
    className: "axis-baseline",
    x1: P.l,
    x2: W - P.r,
    y1: y0,
    y2: y0
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: y0 + 3,
    textAnchor: "end"
  }, "0%"), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: yScale(max) + 3,
    textAnchor: "end"
  }, "+", max.toFixed(0)), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: yScale(-max) + 3,
    textAnchor: "end"
  }, "\u2212", max.toFixed(0)), yoy.slice(1).map((d, i) => {
    const xx = P.l + (i + 1) * bandW;
    const v = d.pct;
    const ybar = v >= 0 ? yScale(v) : y0;
    const h = Math.abs(yScale(v) - y0);
    const fill = v >= 0 ? 'var(--ok)' : 'var(--err)';
    return /*#__PURE__*/React.createElement("rect", {
      key: d.y,
      x: xx + 2,
      y: ybar,
      width: bandW - 4,
      height: h,
      fill: fill,
      opacity: "0.85",
      rx: "1"
    }, /*#__PURE__*/React.createElement("title", null, d.y, ": ", v >= 0 ? '+' : '', v.toFixed(1), "%"));
  }), yoy.map((d, i) => i % xTickEvery === 0 || i === yoy.length - 1 ? /*#__PURE__*/React.createElement("text", {
    key: d.y,
    className: "axis",
    x: P.l + i * bandW + bandW / 2,
    y: H - P.b + 14,
    textAnchor: "middle"
  }, d.y) : null));
}

// ────────────────────────────────────────────────────────────────────
// FlagBars — 100% stacked horizontal bars (per product / per UF)
// ────────────────────────────────────────────────────────────────────
function FlagBars({
  rows,
  flags,
  labelKey = 'name',
  height
}) {
  const W = 720;
  const ROW_LABEL_W = 170;
  // Reserve a right-hand gutter for the per-row % label so it is not clipped
  // by the SVG viewBox edge (labels are start-anchored just past the track).
  const VAL_W = 42;
  const BAR_H = 22,
    GAP = 8,
    PAD_TOP = 14,
    PAD_BOT = 14;
  const H = height || PAD_TOP + rows.length * (BAR_H + GAP) + PAD_BOT;
  const trackW = W - ROW_LABEL_W - 12 - VAL_W;
  // No rows or no flags selected → empty plot area, never crash on flags[0].
  if (!rows || rows.length === 0 || !flags || flags.length === 0) {
    return /*#__PURE__*/React.createElement("svg", {
      viewBox: `0 0 ${W} ${H}`,
      className: "chart",
      preserveAspectRatio: "xMidYMid meet"
    });
  }
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, rows.map((r, ri) => {
    const ry = PAD_TOP + ri * (BAR_H + GAP);
    let acc = 0;
    const ok = flags[0] && r[flags[0].id] || 0;
    return /*#__PURE__*/React.createElement("g", {
      key: r.code || r.uf || r[labelKey]
    }, /*#__PURE__*/React.createElement("text", {
      className: "axis",
      x: ROW_LABEL_W - 8,
      y: ry + BAR_H * 0.7,
      textAnchor: "end"
    }, r[labelKey]), flags.map(f => {
      const v = r[f.id] || 0;
      const x = ROW_LABEL_W + acc * trackW;
      const w = v * trackW;
      acc += v;
      return /*#__PURE__*/React.createElement("rect", {
        key: f.id,
        x: x,
        y: ry,
        width: w,
        height: BAR_H,
        fill: f.color,
        rx: "1"
      }, /*#__PURE__*/React.createElement("title", null, r[labelKey], " \xB7 ", f.label, ": ", (v * 100).toFixed(1), "%"));
    }), /*#__PURE__*/React.createElement("text", {
      className: "axis-val tnum",
      x: ROW_LABEL_W + trackW + 8,
      y: ry + BAR_H * 0.7,
      style: {
        fill: ok > 0.85 ? 'var(--ok)' : ok > 0.7 ? 'var(--fg-1)' : 'var(--warn)'
      }
    }, (ok * 100).toFixed(0), "%"));
  }));
}

// ────────────────────────────────────────────────────────────────────
// RegionBars — vertical bars for region totals
// ────────────────────────────────────────────────────────────────────
function RegionBars({
  data,
  valueKey = 'value',
  label = 'R$ mi',
  height = 220
}) {
  const W = 520,
    H = height,
    P = {
      l: 36,
      r: 12,
      t: 18,
      b: 38
    };
  const max = Math.max(...data.map(d => d[valueKey])) * 1.12 || 1;
  const bandW = (W - P.l - P.r) / data.length;
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, data.map((d, i) => {
    const x = P.l + i * bandW + bandW * 0.18;
    const w = bandW * 0.64;
    const h = d[valueKey] / max * (H - P.t - P.b);
    const y = H - P.b - h;
    return /*#__PURE__*/React.createElement("g", {
      key: d.id
    }, /*#__PURE__*/React.createElement("rect", {
      x: x,
      y: y,
      width: w,
      height: h,
      fill: d.color,
      rx: "3"
    }), /*#__PURE__*/React.createElement("text", {
      className: "axis-val tnum",
      x: x + w / 2,
      y: y - 6,
      textAnchor: "middle"
    }, d[valueKey].toLocaleString('pt-BR')), /*#__PURE__*/React.createElement("text", {
      className: "axis",
      x: x + w / 2,
      y: H - P.b + 14,
      textAnchor: "middle"
    }, d.label), /*#__PURE__*/React.createElement("text", {
      className: "axis",
      x: x + w / 2,
      y: H - P.b + 28,
      textAnchor: "middle",
      style: {
        opacity: 0.7,
        fontSize: 10
      }
    }, d.ufs, " UF"));
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis-label",
    x: P.l,
    y: 12
  }, label));
}

// ────────────────────────────────────────────────────────────────────
// LorenzCurve — cumulative share of value vs cumulative share of units.
//   values : number[]  (e.g. per-UF or per-product value)
function LorenzCurve({
  values,
  height = 300,
  color = 'var(--embrapa-green)',
  xLabel = 'unidades',
  yLabel = 'valor'
}) {
  const W = 420,
    H = height,
    P = {
      l: 44,
      r: 16,
      t: 16,
      b: 36
    };
  const sorted = values.slice().filter(v => v > 0).sort((a, b) => a - b);
  const n = sorted.length;
  const total = sorted.reduce((s, v) => s + v, 0) || 1;
  // cumulative points (0,0) … (1,1)
  const pts = [{
    x: 0,
    y: 0
  }];
  let acc = 0;
  sorted.forEach((v, i) => {
    acc += v;
    pts.push({
      x: (i + 1) / n,
      y: acc / total
    });
  });
  const x = fx => P.l + fx * (W - P.l - P.r);
  const y = fy => P.t + (1 - fy) * (H - P.t - P.b);
  const lorenz = pts.map(p => `${x(p.x)},${y(p.y)}`).join(' ');
  const areaPts = `${x(0)},${y(0)} ${lorenz} ${x(1)},${y(0)}`;
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, [0.25, 0.5, 0.75, 1].map(t => /*#__PURE__*/React.createElement("g", {
    key: t
  }, /*#__PURE__*/React.createElement("line", {
    className: "grid",
    x1: x(0),
    x2: x(1),
    y1: y(t),
    y2: y(t)
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: x(0) - 6,
    y: y(t) + 3,
    textAnchor: "end"
  }, (t * 100).toFixed(0), "%"))), /*#__PURE__*/React.createElement("line", {
    x1: x(0),
    y1: y(0),
    x2: x(1),
    y2: y(1),
    stroke: "var(--fg-3)",
    strokeWidth: "1.2",
    strokeDasharray: "4 4",
    opacity: "0.6"
  }), /*#__PURE__*/React.createElement("polygon", {
    points: areaPts,
    fill: color,
    opacity: "0.12"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: lorenz,
    fill: "none",
    stroke: color,
    strokeWidth: "2.2",
    strokeLinejoin: "round"
  }), [0.25, 0.5, 0.75, 1].map(t => /*#__PURE__*/React.createElement("text", {
    key: 'x' + t,
    className: "axis",
    x: x(t),
    y: H - P.b + 14,
    textAnchor: "middle"
  }, (t * 100).toFixed(0), "%")), /*#__PURE__*/React.createElement("text", {
    className: "axis-label",
    x: x(0),
    y: 10
  }, yLabel, " acum."), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: x(1),
    y: H - 6,
    textAnchor: "end",
    style: {
      opacity: 0.7
    }
  }, xLabel, " acum. \u2192"));
}
Object.assign(window, {
  BrazilTileMap,
  Heatmap,
  StackedArea,
  YoYBars,
  FlagBars,
  RegionBars,
  LorenzCurve
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "Charts.geo.jsx", error: String((e && e.message) || e) }); }

// Charts.jsx
try { (() => {
// Chart components — hand-rolled SVG, sized for dashboard cards. No chart library.

// Compact axis-tick formatter — shared impl in data.js (window.fmtAxisTick).
const _fmtAxisNum = window.fmtAxisTick;
function LineChart({
  data,
  height = 200,
  color = 'var(--viz-1)',
  label = 'BRL',
  valueKey = 'v'
}) {
  const W = 560,
    H = height,
    P = {
      l: 54,
      r: 12,
      t: 14,
      b: 28
    };
  const xs = data.map(d => d.y);
  const ys = data.map(d => d[valueKey]);
  const minY = 0;
  const maxY = Math.max(...ys) * 1.1 || 1;
  const x = i => P.l + i / (data.length - 1) * (W - P.l - P.r);
  const y = v => P.t + (1 - (v - minY) / (maxY - minY)) * (H - P.t - P.b);
  const pts = data.map((d, i) => `${x(i)},${y(d[valueKey])}`).join(' ');
  const area = `${P.l},${H - P.b} ${pts} ${W - P.r},${H - P.b}`;
  const yTicks = 4;
  const ticks = Array.from({
    length: yTicks + 1
  }, (_, i) => maxY / yTicks * i);
  const xTickEvery = Math.ceil(data.length / 6);
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, ticks.map((t, i) => /*#__PURE__*/React.createElement("g", {
    key: i
  }, /*#__PURE__*/React.createElement("line", {
    className: "grid",
    x1: P.l,
    x2: W - P.r,
    y1: y(t),
    y2: y(t)
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: y(t) + 3,
    textAnchor: "end"
  }, _fmtAxisNum(t)))), /*#__PURE__*/React.createElement("polygon", {
    points: area,
    fill: color,
    opacity: "0.10"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: pts,
    fill: "none",
    stroke: color,
    strokeWidth: "2"
  }), data.map((d, i) => i % 4 === 0 ? /*#__PURE__*/React.createElement("circle", {
    key: i,
    cx: x(i),
    cy: y(d[valueKey]),
    r: "2.5",
    fill: color
  }) : null), data.map((d, i) => i % xTickEvery === 0 || i === data.length - 1 ? /*#__PURE__*/React.createElement("text", {
    key: 'x' + i,
    className: "axis",
    x: x(i),
    y: H - P.b + 14,
    textAnchor: "middle"
  }, d.y) : null), /*#__PURE__*/React.createElement("text", {
    className: "axis-label",
    x: P.l,
    y: 10
  }, label));
}
function BarChart({
  data,
  height = 200,
  color = 'var(--viz-2)',
  label = 't (mil)',
  valueKey = 'value'
}) {
  const W = 560,
    H = height,
    P = {
      l: 60,
      r: 16,
      t: 14,
      b: 26
    };
  const max = Math.max(...data.map(d => d[valueKey])) * 1.1 || 1;
  const bandH = (H - P.t - P.b) / data.length;
  const bw = val => val / max * (W - P.l - P.r);
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, data.map((d, i) => {
    const yy = P.t + i * bandH + bandH * 0.15;
    const h = bandH * 0.7;
    return /*#__PURE__*/React.createElement("g", {
      key: d.uf || d.name
    }, /*#__PURE__*/React.createElement("text", {
      className: "axis",
      x: P.l - 8,
      y: yy + h * 0.7,
      textAnchor: "end"
    }, d.uf || d.name), /*#__PURE__*/React.createElement("rect", {
      x: P.l,
      y: yy,
      width: bw(d[valueKey]),
      height: h,
      fill: color,
      rx: "2"
    }), (() => {
      const tip = P.l + bw(d[valueKey]);
      const txt = d[valueKey].toLocaleString('pt-BR');
      // Place the value to the right of the bar tip; if that would
      // overflow the SVG right edge (long values on near-max bars get
      // clipped), flip it INSIDE the bar, right-aligned with white fill.
      const inside = tip + 6 + (txt.length * 6 + 6) > W - P.r;
      return /*#__PURE__*/React.createElement("text", {
        className: "axis-val tnum",
        x: inside ? tip - 6 : tip + 6,
        y: yy + h * 0.7,
        textAnchor: inside ? 'end' : 'start',
        style: inside ? {
          fill: '#fff'
        } : undefined
      }, txt);
    })());
  }));
}

// Donut chart for share-of-total
function Donut({
  data,
  size = 160,
  valueKey = 'share'
}) {
  const r = size / 2,
    ir = r * 0.62;
  let acc = 0;
  const total = data.reduce((s, d) => s + d[valueKey], 0);
  const slices = data.map(d => {
    const start = acc / total;
    acc += d[valueKey];
    const end = acc / total;
    const a0 = start * Math.PI * 2 - Math.PI / 2;
    const a1 = end * Math.PI * 2 - Math.PI / 2;
    const large = end - start > 0.5 ? 1 : 0;
    const x0 = r + r * Math.cos(a0),
      y0 = r + r * Math.sin(a0);
    const x1 = r + r * Math.cos(a1),
      y1 = r + r * Math.sin(a1);
    const xi0 = r + ir * Math.cos(a0),
      yi0 = r + ir * Math.sin(a0);
    const xi1 = r + ir * Math.cos(a1),
      yi1 = r + ir * Math.sin(a1);
    return {
      d: `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} L ${xi1} ${yi1} A ${ir} ${ir} 0 ${large} 0 ${xi0} ${yi0} Z`,
      fill: d.color || 'var(--viz-1)',
      label: d.name,
      value: d[valueKey]
    };
  });
  return /*#__PURE__*/React.createElement("div", {
    className: "donut-wrap"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${size} ${size}`,
    width: size,
    height: size
  }, slices.map((s, i) => /*#__PURE__*/React.createElement("path", {
    key: i,
    d: s.d,
    fill: s.fill
  })), /*#__PURE__*/React.createElement("circle", {
    cx: r,
    cy: r,
    r: ir - 2,
    fill: "#fff"
  })), /*#__PURE__*/React.createElement("ul", {
    className: "donut-legend"
  }, data.map((d, i) => /*#__PURE__*/React.createElement("li", {
    key: i
  }, /*#__PURE__*/React.createElement("span", {
    className: "ldot",
    style: {
      background: d.color
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "lname"
  }, d.name), /*#__PURE__*/React.createElement("span", {
    className: "lval tnum"
  }, (d[valueKey] * 100).toFixed(0), "%")))));
}

// MultiLineChart — several series on one axis (for comparison views).
//   series : [{ name, color, data: [{ y, v }] }]
function MultiLineChart({
  series,
  height = 260,
  valueKey = 'v',
  label = ''
}) {
  const W = 720,
    H = height,
    P = {
      l: 54,
      r: 12,
      t: 16,
      b: 28
    };
  const years = series[0]?.data.map(d => d.y) || [];
  const all = series.flatMap(s => s.data.map(d => d[valueKey]));
  const maxY = Math.max(...all, 0) * 1.08;
  const minY = Math.min(...all, 0);
  const x = i => P.l + i / (years.length - 1) * (W - P.l - P.r);
  const y = v => P.t + (1 - (v - minY) / (maxY - minY || 1)) * (H - P.t - P.b);
  const yTicks = 4;
  const ticks = Array.from({
    length: yTicks + 1
  }, (_, i) => minY + (maxY - minY) / yTicks * i);
  const xTickEvery = Math.max(1, Math.ceil(years.length / 7));
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    className: "chart",
    preserveAspectRatio: "xMidYMid meet"
  }, ticks.map((t, i) => /*#__PURE__*/React.createElement("g", {
    key: i
  }, /*#__PURE__*/React.createElement("line", {
    className: "grid",
    x1: P.l,
    x2: W - P.r,
    y1: y(t),
    y2: y(t)
  }), /*#__PURE__*/React.createElement("text", {
    className: "axis",
    x: P.l - 6,
    y: y(t) + 3,
    textAnchor: "end"
  }, _fmtAxisNum(t)))), series.map((s, si) => {
    const pts = s.data.map((d, i) => `${x(i)},${y(d[valueKey])}`).join(' ');
    return /*#__PURE__*/React.createElement("g", {
      key: si
    }, /*#__PURE__*/React.createElement("polyline", {
      points: pts,
      fill: "none",
      stroke: s.color,
      strokeWidth: "2",
      strokeLinejoin: "round"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: x(s.data.length - 1),
      cy: y(s.data[s.data.length - 1][valueKey]),
      r: "3",
      fill: s.color
    }));
  }), years.map((yv, i) => i % xTickEvery === 0 || i === years.length - 1 ? /*#__PURE__*/React.createElement("text", {
    key: yv,
    className: "axis",
    x: x(i),
    y: H - P.b + 14,
    textAnchor: "middle"
  }, yv) : null), /*#__PURE__*/React.createElement("text", {
    className: "axis-label",
    x: P.l,
    y: 10
  }, label));
}
Object.assign(window, {
  LineChart,
  BarChart,
  Donut,
  MultiLineChart
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "Charts.jsx", error: String((e && e.message) || e) }); }

// DataBoundary.jsx
try { (() => {
// DataBoundary.jsx — React glue for the pushdown query boundary:
//   • useBancoData(bancoId)  — query lifecycle + freshness polling
//   • FreshnessBanner        — "dados atualizados disponíveis · Recarregar"
//   • DataLoading            — skeleton shown while the pushdown query runs

const {
  useState: useDBState,
  useEffect: useDBEffect
} = React;

// Poll interval for the "did Gold change?" check (real deploy: server poll).
const FRESHNESS_POLL_MS = 12000;
function useBancoData(bancoId) {
  const [, force] = useDBState(0);
  useDBEffect(() => {
    const unsub = window.dataStore.subscribe(() => force(n => n + 1));
    window.dataStore.load(bancoId);
    return unsub;
  }, [bancoId]);

  // Periodic freshness check (mock: re-evaluates isStale; real: fetch version)
  useDBEffect(() => {
    const t = setInterval(() => force(n => n + 1), FRESHNESS_POLL_MS);
    return () => clearInterval(t);
  }, []);
  return {
    status: window.dataStore.status(bancoId),
    stale: window.dataStore.isStale(bancoId),
    error: window.dataStore.error(bancoId),
    loadedAt: window.dataStore.loadedAt(bancoId),
    version: window.dataStore.version(bancoId),
    latestAt: window.dataStore.latestAt(bancoId),
    reload: () => window.dataStore.load(bancoId)
  };
}
function FreshnessBanner({
  banco,
  latestAt,
  onReload
}) {
  const [reloading, setReloading] = useDBState(false);
  const handle = () => {
    setReloading(true);
    Promise.resolve(onReload()).then(() => setReloading(false));
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "fresh-banner"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fresh-dot"
  }), /*#__PURE__*/React.createElement("span", {
    className: "fresh-text"
  }, "Nova vers\xE3o da Gold publicada", latestAt && latestAt !== '—' ? ` · ${latestAt}` : '', ". Os resultados em cache est\xE3o desatualizados."), /*#__PURE__*/React.createElement("button", {
    className: "fresh-btn",
    onClick: handle,
    disabled: reloading
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "refresh",
    size: 14
  }), reloading ? 'Recarregando…' : 'Recarregar dados'));
}
function DataLoading({
  banco
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "dl-wrap"
  }, /*#__PURE__*/React.createElement("div", {
    className: "dl-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "dl-spinner"
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "dl-title"
  }, "Consultando ", banco ? banco.short : 'dados', "\u2026"), /*#__PURE__*/React.createElement("div", {
    className: "dl-sub"
  }, "Executando consulta no BigQuery (Serving Layer \xB7 pr\xE9-agregada)"))), /*#__PURE__*/React.createElement("div", {
    className: "dl-skel-row"
  }, /*#__PURE__*/React.createElement("div", {
    className: "dl-skel kpi"
  }), /*#__PURE__*/React.createElement("div", {
    className: "dl-skel kpi"
  }), /*#__PURE__*/React.createElement("div", {
    className: "dl-skel kpi"
  }), /*#__PURE__*/React.createElement("div", {
    className: "dl-skel kpi"
  })), /*#__PURE__*/React.createElement("div", {
    className: "dl-skel-row"
  }, /*#__PURE__*/React.createElement("div", {
    className: "dl-skel card"
  }), /*#__PURE__*/React.createElement("div", {
    className: "dl-skel card"
  })));
}
function DataError({
  banco,
  message,
  onRetry
}) {
  const [retrying, setRetrying] = useDBState(false);
  const handle = () => {
    setRetrying(true);
    Promise.resolve(onRetry()).then(() => setRetrying(false));
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "derr-wrap"
  }, /*#__PURE__*/React.createElement("div", {
    className: "derr-card"
  }, /*#__PURE__*/React.createElement("div", {
    className: "derr-icon"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "warning",
    size: 28
  })), /*#__PURE__*/React.createElement("h2", {
    className: "derr-title"
  }, "N\xE3o foi poss\xEDvel carregar ", banco ? banco.short : 'os dados'), /*#__PURE__*/React.createElement("p", {
    className: "derr-msg"
  }, message || 'Ocorreu um erro ao consultar a tabela Gold no BigQuery.'), /*#__PURE__*/React.createElement("p", {
    className: "derr-hint"
  }, "As consultas s\xE3o enviadas ao BigQuery sob demanda. Se a falha persistir, verifique a disponibilidade da fonte Gold e tente novamente."), /*#__PURE__*/React.createElement("button", {
    className: "derr-btn",
    onClick: handle,
    disabled: retrying
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "refresh",
    size: 14
  }), retrying ? 'Tentando novamente…' : 'Tentar novamente')));
}
Object.assign(window, {
  useBancoData,
  FreshnessBanner,
  DataLoading,
  DataError
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "DataBoundary.jsx", error: String((e && e.message) || e) }); }

// FilterMenu.jsx
try { (() => {
// FilterMenu.jsx — v3
// Expanded filter modal adapted from the updated sketch to the
// Embrapa Commodities Design System.
//
// Sections (live banco): products, period & value range, geography,
// quality, + a read-only list of the banco's remaining declared dimensions.
//   • Inline search input inside every multi-select header
//   • "Geografia" section is BANCO-ADAPTIVE: the cascade depth follows the
//     banco's geoLevel — Nações → Regiões → Estados → Municípios for
//     município-level bancos, dropping the Municípios column for UF-level
//     bancos, and the whole section is hidden when the banco has no geo.
//   • Product label, value-filter currency symbol/column and the value
//     shortcuts all come from the active banco (schema + baseCurrency), so
//     COMEX shows "Produto · NCM/SH" + US$, Comtrade "Produto · HS6", etc.
//   • Scrollable lists (260px max-height) for long enumerations
//   • Each multi-select has its own bulk actions row
//
// Selection cascades downward: unchecking "Norte" PRUNES its 7 states
// (and their municipalities) from the selection — so the applied filter
// always matches the visible cascade; checking "Pará" makes Pará's
// municipalities the only ones eligible in Municípios. Re-checking a
// parent leaves its children UNSELECTED (re-pick them, or use
// "Selecionar tudo") — enforced by the cascade-pruning effects below.

const {
  useState,
  useMemo
} = React;

// --- Domain data ---------------------------------------------------
// The product list is now resolved PER BANCO inside the component (see `PRODS`),
// from the active banco's snapshot — so there is no module-level PEVS copy.

// Quality flags derive from the single source of truth (window.QUALITY_FLAGS
// in data.js) so the labels shown here, in the chip bar and in the Qualidade
// view never drift apart. The raw flag token (data_quality_flag) is still
// surfaced verbatim alongside each pt-BR label.
// Period bounds derived from the live time series — never hardcode
// "1986–2024" so changing the source dataset propagates to the chips.
const YEAR_START = window.OVERVIEW_TS && window.OVERVIEW_TS[0]?.y || 1986;
const YEAR_END = window.OVERVIEW_TS && window.OVERVIEW_TS[window.OVERVIEW_TS.length - 1]?.y || 2024;
const QUALITY_CHIP = {
  OK: 'ok',
  ESTIMATED: 'info',
  MISSING_VALUE: 'warn',
  MISSING_QUANTITY: 'info',
  BOUNDARY_HISTORIC: 'muted',
  OUTLIER: 'err'
};
const QUALITY = (window.QUALITY_FLAGS || []).map(f => ({
  flag: f.id,
  label: f.label,
  chip: QUALITY_CHIP[f.id] || 'muted'
}));
const qualityLabelOf = id => {
  const f = QUALITY.find(x => x.flag === id);
  return f ? f.label : id;
};

// Derived from YEAR_START/YEAR_END (never hardcode the span) so changing the
// source dataset shifts the quick ranges and date bounds with it.
const QUICK_RANGES = [{
  id: 'all',
  label: 'Tudo',
  start: `${YEAR_START}-01`,
  end: `${YEAR_END}-12`
}, {
  id: '30a',
  label: '30 anos',
  start: `${YEAR_END - 29}-01`,
  end: `${YEAR_END}-12`
}, {
  id: '20a',
  label: '20 anos',
  start: `${YEAR_END - 19}-01`,
  end: `${YEAR_END}-12`
}, {
  id: '10a',
  label: '10 anos',
  start: `${YEAR_END - 9}-01`,
  end: `${YEAR_END}-12`
}, {
  id: '5a',
  label: '5 anos',
  start: `${YEAR_END - 4}-01`,
  end: `${YEAR_END}-12`
}];

// Nations — producer + main PEVS export destinations.
const NATIONS = [{
  iso: 'BR',
  name: 'Brasil',
  role: 'produtor'
}, {
  iso: 'CN',
  name: 'China',
  role: 'destino'
}, {
  iso: 'US',
  name: 'Estados Unidos',
  role: 'destino'
}, {
  iso: 'DE',
  name: 'Alemanha',
  role: 'destino'
}, {
  iso: 'NL',
  name: 'Países Baixos',
  role: 'destino'
}, {
  iso: 'FR',
  name: 'França',
  role: 'destino'
}, {
  iso: 'IT',
  name: 'Itália',
  role: 'destino'
}, {
  iso: 'GB',
  name: 'Reino Unido',
  role: 'destino'
}, {
  iso: 'ES',
  name: 'Espanha',
  role: 'destino'
}, {
  iso: 'JP',
  name: 'Japão',
  role: 'destino'
}, {
  iso: 'AR',
  name: 'Argentina',
  role: 'destino'
}, {
  iso: 'CL',
  name: 'Chile',
  role: 'destino'
}];

// Brazil's 5 macro-regions. Linked to BR nation.
const FM_REGIONS = [{
  id: 'N',
  name: 'Norte',
  nation: 'BR'
}, {
  id: 'NE',
  name: 'Nordeste',
  nation: 'BR'
}, {
  id: 'CO',
  name: 'Centro-Oeste',
  nation: 'BR'
}, {
  id: 'SE',
  name: 'Sudeste',
  nation: 'BR'
}, {
  id: 'S',
  name: 'Sul',
  nation: 'BR'
}];

// Brazil's 27 states (UFs), linked to their region.
const STATES = [{
  uf: 'AC',
  name: 'Acre',
  region: 'N'
}, {
  uf: 'AP',
  name: 'Amapá',
  region: 'N'
}, {
  uf: 'AM',
  name: 'Amazonas',
  region: 'N'
}, {
  uf: 'PA',
  name: 'Pará',
  region: 'N'
}, {
  uf: 'RO',
  name: 'Rondônia',
  region: 'N'
}, {
  uf: 'RR',
  name: 'Roraima',
  region: 'N'
}, {
  uf: 'TO',
  name: 'Tocantins',
  region: 'N'
}, {
  uf: 'AL',
  name: 'Alagoas',
  region: 'NE'
}, {
  uf: 'BA',
  name: 'Bahia',
  region: 'NE'
}, {
  uf: 'CE',
  name: 'Ceará',
  region: 'NE'
}, {
  uf: 'MA',
  name: 'Maranhão',
  region: 'NE'
}, {
  uf: 'PB',
  name: 'Paraíba',
  region: 'NE'
}, {
  uf: 'PE',
  name: 'Pernambuco',
  region: 'NE'
}, {
  uf: 'PI',
  name: 'Piauí',
  region: 'NE'
}, {
  uf: 'RN',
  name: 'Rio Grande do Norte',
  region: 'NE'
}, {
  uf: 'SE',
  name: 'Sergipe',
  region: 'NE'
}, {
  uf: 'DF',
  name: 'Distrito Federal',
  region: 'CO'
}, {
  uf: 'GO',
  name: 'Goiás',
  region: 'CO'
}, {
  uf: 'MT',
  name: 'Mato Grosso',
  region: 'CO'
}, {
  uf: 'MS',
  name: 'Mato Grosso do Sul',
  region: 'CO'
}, {
  uf: 'ES',
  name: 'Espírito Santo',
  region: 'SE'
}, {
  uf: 'MG',
  name: 'Minas Gerais',
  region: 'SE'
}, {
  uf: 'RJ',
  name: 'Rio de Janeiro',
  region: 'SE'
}, {
  uf: 'SP',
  name: 'São Paulo',
  region: 'SE'
}, {
  uf: 'PR',
  name: 'Paraná',
  region: 'S'
}, {
  uf: 'RS',
  name: 'Rio Grande do Sul',
  region: 'S'
}, {
  uf: 'SC',
  name: 'Santa Catarina',
  region: 'S'
}];

// Sample of leading PEVS-producing municipalities. (~40 from real PEVS data.)
const MUNICIPALITIES = [
// Norte
{
  code: '1302603',
  name: 'Manaus',
  uf: 'AM'
}, {
  code: '1501402',
  name: 'Belém',
  uf: 'PA'
}, {
  code: '1503606',
  name: 'Itacoatiara',
  uf: 'AM'
}, {
  code: '1507300',
  name: 'Marabá',
  uf: 'PA'
}, {
  code: '1506807',
  name: 'Santarém',
  uf: 'PA'
}, {
  code: '1504208',
  name: 'Parintins',
  uf: 'AM'
}, {
  code: '1100205',
  name: 'Porto Velho',
  uf: 'RO'
}, {
  code: '1100122',
  name: 'Cacoal',
  uf: 'RO'
}, {
  code: '1200401',
  name: 'Rio Branco',
  uf: 'AC'
}, {
  code: '1600303',
  name: 'Macapá',
  uf: 'AP'
}, {
  code: '1400100',
  name: 'Boa Vista',
  uf: 'RR'
}, {
  code: '1721000',
  name: 'Palmas',
  uf: 'TO'
}, {
  code: '1505031',
  name: 'Oriximiná',
  uf: 'PA'
},
// Nordeste
{
  code: '2111300',
  name: 'São Luís',
  uf: 'MA'
}, {
  code: '2105302',
  name: 'Imperatriz',
  uf: 'MA'
}, {
  code: '2101400',
  name: 'Bacabal',
  uf: 'MA'
}, {
  code: '2211001',
  name: 'Teresina',
  uf: 'PI'
}, {
  code: '2927408',
  name: 'Salvador',
  uf: 'BA'
}, {
  code: '2304400',
  name: 'Fortaleza',
  uf: 'CE'
}, {
  code: '2611606',
  name: 'Recife',
  uf: 'PE'
}, {
  code: '2102309',
  name: 'Caxias',
  uf: 'MA'
},
// Centro-Oeste
{
  code: '5103403',
  name: 'Cuiabá',
  uf: 'MT'
}, {
  code: '5108402',
  name: 'Sinop',
  uf: 'MT'
}, {
  code: '5002704',
  name: 'Campo Grande',
  uf: 'MS'
}, {
  code: '5208707',
  name: 'Goiânia',
  uf: 'GO'
}, {
  code: '5300108',
  name: 'Brasília',
  uf: 'DF'
},
// Sudeste
{
  code: '3550308',
  name: 'São Paulo',
  uf: 'SP'
}, {
  code: '3304557',
  name: 'Rio de Janeiro',
  uf: 'RJ'
}, {
  code: '3106200',
  name: 'Belo Horizonte',
  uf: 'MG'
}, {
  code: '3205309',
  name: 'Vitória',
  uf: 'ES'
}, {
  code: '3157807',
  name: 'Uberlândia',
  uf: 'MG'
},
// Sul
{
  code: '4106902',
  name: 'Curitiba',
  uf: 'PR'
}, {
  code: '4314902',
  name: 'Porto Alegre',
  uf: 'RS'
}, {
  code: '4205407',
  name: 'Florianópolis',
  uf: 'SC'
}, {
  code: '4106407',
  name: 'Cascavel',
  uf: 'PR'
}, {
  code: '4307005',
  name: 'Erechim',
  uf: 'RS'
}, {
  code: '4304572',
  name: 'Caxias do Sul',
  uf: 'RS'
}, {
  code: '4209102',
  name: 'Lages',
  uf: 'SC'
}];

// Name universe the município picker can address — read by dataFilters so a
// município the picker can't address (data leader outside this partial list)
// stays governed by the UF filter alone instead of being wrongly excluded.
window.MUNI_PICKER_NAMES = new Set(MUNICIPALITIES.map(m => m.name));

// ----- icons ------------------------------------------------------
const I = {
  filter: /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M3 5h18l-7 9v6l-4-2v-4z"
  })),
  close: /*#__PURE__*/React.createElement("svg", {
    width: "18",
    height: "18",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.6",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M6 6l12 12M18 6L6 18"
  })),
  arrow: /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M5 12h14M13 6l6 6-6 6"
  })),
  pencil: /*#__PURE__*/React.createElement("svg", {
    width: "13",
    height: "13",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 20h4l10-10-4-4L4 16zM14 6l4 4"
  })),
  search: /*#__PURE__*/React.createElement("svg", {
    width: "13",
    height: "13",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "11",
    cy: "11",
    r: "6"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M20 20l-4-4"
  })),
  cascade: /*#__PURE__*/React.createElement("svg", {
    width: "11",
    height: "11",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M8 6h8M8 12h6M8 18h4M4 6v.01M4 12v.01M4 18v.01"
  }))
};

// ----- inline search input ----------------------------------------
function SearchInput({
  value,
  onChange,
  placeholder
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: "fm-search"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-search-icn"
  }, I.search), /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: value,
    onChange: e => onChange(e.target.value),
    placeholder: placeholder || 'Buscar…'
  }), value && /*#__PURE__*/React.createElement("button", {
    className: "fm-search-clear",
    onClick: () => onChange(''),
    "aria-label": "Limpar busca"
  }, "\xD7"));
}

// ----- bulk actions row -------------------------------------------
function BulkActions({
  all,
  none,
  invert,
  selectedCount,
  totalCount,
  compact
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: 'fm-bulk' + (compact ? ' compact' : '')
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: all,
    disabled: selectedCount === totalCount
  }, "Selecionar tudo"), /*#__PURE__*/React.createElement("span", {
    className: "sep-dot",
    "aria-hidden": "true"
  }), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: none,
    disabled: selectedCount === 0
  }, "Limpar"), /*#__PURE__*/React.createElement("span", {
    className: "sep-dot",
    "aria-hidden": "true"
  }), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: invert
  }, "Inverter"));
}

// ----- reusable column for the geography cascade -----------------
function GeoColumn({
  title,
  items,
  keyAttr,
  displayAttr,
  getMeta,
  selected,
  setSelected,
  search,
  setSearch,
  disabledReason,
  emptyAllNote
}) {
  const filtered = useMemo(() => {
    if (!search) return items;
    const q = search.toLowerCase();
    return items.filter(x => x[displayAttr].toLowerCase().includes(q) || x[keyAttr] && String(x[keyAttr]).toLowerCase().includes(q));
  }, [items, search, displayAttr, keyAttr]);
  const toggle = val => {
    const next = new Set(selected);
    next.has(val) ? next.delete(val) : next.add(val);
    setSelected(next);
  };

  // Bulk actions operate on the SEARCH-FILTERED ("visible") items, so e.g.
  // searching "Pa" then "Limpar" only clears matches — never the whole Set.
  // With no search, `filtered` === items, so behaviour is unchanged.
  const visKeys = filtered.map(x => x[keyAttr]);
  const visSet = new Set(visKeys);
  const allOn = () => setSelected(new Set([...selected, ...visKeys]));
  const allOff = () => setSelected(new Set([...selected].filter(k => !visSet.has(k))));
  const allInv = () => {
    const n = new Set(selected);
    visKeys.forEach(k => n.has(k) ? n.delete(k) : n.add(k));
    setSelected(n);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "fm-geo-col"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-geo-col-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-geo-title"
  }, title), /*#__PURE__*/React.createElement("span", {
    className: "fm-geo-count"
  }, /*#__PURE__*/React.createElement("strong", null, selected.size), "/", items.length)), /*#__PURE__*/React.createElement(SearchInput, {
    value: search,
    onChange: setSearch,
    placeholder: `Buscar em ${title.toLowerCase()}…`
  }), /*#__PURE__*/React.createElement("div", {
    className: "fm-geo-list"
  }, disabledReason && /*#__PURE__*/React.createElement("div", {
    className: "fm-geo-empty"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-cascade-icn"
  }, I.cascade), disabledReason), !disabledReason && emptyAllNote && selected.size === 0 && /*#__PURE__*/React.createElement("div", {
    className: "fm-geo-allnote"
  }, emptyAllNote), !disabledReason && filtered.length === 0 && /*#__PURE__*/React.createElement("div", {
    className: "fm-geo-empty"
  }, "Nenhum resultado."), !disabledReason && filtered.map(item => {
    const on = selected.has(item[keyAttr]);
    const meta = getMeta ? getMeta(item) : null;
    return /*#__PURE__*/React.createElement("label", {
      key: item[keyAttr],
      className: 'fm-check geo' + (on ? ' is-on' : '')
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: on,
      onChange: () => toggle(item[keyAttr])
    }), /*#__PURE__*/React.createElement("span", {
      className: "fm-name"
    }, item[displayAttr]), meta && /*#__PURE__*/React.createElement("span", {
      className: "fm-code"
    }, meta));
  })), /*#__PURE__*/React.createElement(BulkActions, {
    all: allOn,
    none: allOff,
    invert: allInv,
    selectedCount: visKeys.filter(k => selected.has(k)).length,
    totalCount: filtered.length,
    compact: true
  }));
}

// ==================================================================
// Controlled component:
//   <FilterMenu open banco="ibge_pevs" onClose onApply />
// The menu is SCOPED to the active banco (chosen in the sidebar):
//   • live banco  → full functional filter sections
//   • soon banco  → read-only preview of its planned filter dimensions
// onApply receives a display-summary object the trigger row can render as
// chips. `value` is the currently-APPLIED raw filter (basket/flags/states/…);
// the panel seeds itself from it each time it opens, so it always mirrors
// what's live (incl. a shared deep-link) instead of silently resetting to all.
function FilterMenu({
  open = false,
  banco = 'ibge_pevs',
  value,
  onClose,
  onApply
}) {
  const close = () => {
    if (typeof onClose === 'function') onClose();
  };
  const bancoMeta = window.bancoById ? window.bancoById(banco) : null;
  const schema = window.filterSchemaFor ? window.filterSchemaFor(banco) : null;
  const isLive = bancoMeta ? bancoMeta.status === 'live' : true;
  const hasGeo = !!(bancoMeta && bancoMeta.provides && bancoMeta.provides.includes('geo'));

  // ── Per-banco descriptors so the live menu is CORRECT for each banco
  // (no longer always PEVS): currency symbol/column, geo granularity, the
  // product dimension's label, and the banco-specific dimensions not yet
  // covered by the functional sections (surfaced read-only below).
  const geoLevel = window.geoLevelFor ? window.geoLevelFor(banco) : hasGeo ? 'municipio' : null;
  const showMunis = geoLevel === 'municipio';
  const baseCcy = bancoMeta && bancoMeta.baseCurrency || 'BRL';
  const sym = window.CURRENCY_FX && window.CURRENCY_FX[baseCcy] && window.CURRENCY_FX[baseCcy].symbol || 'R$';
  const fmtVal = v => window.fmtCompactValue(v, sym);
  const dims = schema && schema.dims || [];
  const prodDim = dims.find(d => d.type === 'products' || d.type === 'multi-tree');
  const prodLabel = prodDim && prodDim.label || `Produtos · ${bancoMeta ? bancoMeta.short : 'PEVS'}`;
  const valDim = dims.find(d => d.type === 'value-range' || d.type === 'period-value');
  const valColumn = (valDim && valDim.column ? valDim.column.split('·').pop().trim() : null) || 'val_real_ipca_brl';
  // Dimensions declared for this banco that the functional sections above do
  // not yet expose (e.g. fluxo, via, país, reporter). Shown read-only so the
  // schema is never silently ignored on a live banco.
  const COVERED_TYPES = ['products', 'multi-tree', 'date-range', 'period-value', 'value-range', 'geo-cascade', 'flags'];
  const COVERED_IDS = ['uf_origem'];
  const extraDims = dims.filter(d => !COVERED_TYPES.includes(d.type) && !COVERED_IDS.includes(d.id));

  // Active banco's product universe (NOT the hardcoded PEVS list) so the picker
  // shows the right commodities/codes per banco (NCM for COMEX, HS6 for
  // Comtrade, …). For PEVS this equals window.PRODUCTS → behavior unchanged.
  const PRODS = useMemo(() => {
    const snap = window.dataStore && window.dataStore.get && window.dataStore.get(banco) || window.snapshotFor && window.snapshotFor(banco) || null;
    return (snap && snap.products || window.PRODUCTS || []).map(p => ({
      code: p.code,
      name: p.name,
      unit: p.unit,
      family: p.family
    }));
  }, [banco]);

  // multi-selects (Sets)
  const [products, setProducts] = useState(new Set(PRODS.map(p => p.code)));
  const [flags, setFlags] = useState(new Set(QUALITY.map(f => f.flag)));
  const [nations, setNations] = useState(new Set(['BR']));
  const [regions, setRegions] = useState(new Set(FM_REGIONS.map(r => r.id)));
  const [states, setStates] = useState(new Set(STATES.map(s => s.uf)));
  const [munis, setMunis] = useState(new Set(MUNICIPALITIES.map(m => m.code))); // all by default (0 = none, same as the other dimensions)

  // search strings, one per multi-select
  const [qProducts, setQProducts] = useState('');
  const [qFlags, setQFlags] = useState('');
  const [qNations, setQNations] = useState('');
  const [qRegions, setQRegions] = useState('');
  const [qStates, setQStates] = useState('');
  const [qMunis, setQMunis] = useState('');

  // period
  const [quickRange, setQuickRange] = useState('all');
  const [startDate, setStartDate] = useState(`${YEAR_START}-01`);
  const [endDate, setEndDate] = useState(`${YEAR_END}-12`);

  // per-row value (filter range — in BRL, no conversion)
  // null = no limit
  const [valueMin, setValueMin] = useState(null);
  const [valueMax, setValueMax] = useState(null);

  // ----- cascade-aware lists (children gated by parent selection)
  const eligibleRegions = useMemo(() => FM_REGIONS.filter(r => nations.has(r.nation)), [nations]);
  const eligibleStates = useMemo(() => STATES.filter(s => regions.has(s.region) && eligibleRegions.some(r => r.id === s.region)), [regions, eligibleRegions]);
  const eligibleMunis = useMemo(() => MUNICIPALITIES.filter(m => states.has(m.uf) && eligibleStates.some(s => s.uf === m.uf)), [states, eligibleStates]);

  // Cascade pruning — deselecting a parent removes its now-ineligible children
  // from the selection Sets, so the APPLIED filter matches the visible cascade
  // (counts never read "27/23", and dropping a region/nation actually excludes
  // its data). Re-selecting a parent leaves children unselected — re-pick them
  // or use "Selecionar tudo".
  React.useEffect(() => {
    const ok = new Set(eligibleRegions.map(r => r.id));
    setRegions(prev => {
      const next = new Set([...prev].filter(id => ok.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [eligibleRegions]);
  React.useEffect(() => {
    const ok = new Set(eligibleStates.map(s => s.uf));
    setStates(prev => {
      const next = new Set([...prev].filter(uf => ok.has(uf)));
      return next.size === prev.size ? prev : next;
    });
  }, [eligibleStates]);
  React.useEffect(() => {
    const ok = new Set(eligibleMunis.map(m => m.code));
    setMunis(prev => {
      const next = new Set([...prev].filter(c => ok.has(c)));
      return next.size === prev.size ? prev : next;
    });
  }, [eligibleMunis]);

  // Seed the panel from the currently-APPLIED filter every time it opens, so
  // it mirrors the live state (a shared deep-link, or a prior apply) instead of
  // its hardcoded defaults. Missing dimensions fall back to "all selected".
  const wasOpen = React.useRef(false);
  React.useEffect(() => {
    if (open && !wasOpen.current) {
      const v = value || {};
      setProducts(v.basket != null ? new Set(v.basket) : new Set(PRODS.map(p => p.code)));
      setFlags(v.flags != null ? new Set(v.flags) : new Set(QUALITY.map(f => f.flag)));
      setNations(v.nations != null ? new Set(v.nations) : new Set(['BR']));
      setRegions(v.regions != null ? new Set(v.regions) : new Set(FM_REGIONS.map(r => r.id)));
      setStates(v.states != null ? new Set(v.states) : new Set(STATES.map(s => s.uf)));
      setMunis(v.munis != null ? new Set(v.munis) : new Set(MUNICIPALITIES.map(m => m.code)));
      const sd = v.startDate || `${YEAR_START}-01`;
      const ed = v.endDate || `${YEAR_END}-12`;
      setStartDate(sd);
      setEndDate(ed);
      setQuickRange(sd === `${YEAR_START}-01` && ed === `${YEAR_END}-12` ? 'all' : null);
      setValueMin(v.valueMin ?? null);
      setValueMax(v.valueMax ?? null);
    }
    wasOpen.current = open;
  }, [open]);

  // products / flags filtered by search
  const filteredProducts = useMemo(() => {
    if (!qProducts) return PRODS;
    const q = qProducts.toLowerCase();
    return PRODS.filter(p => p.name.toLowerCase().includes(q) || p.code.includes(q));
  }, [qProducts, PRODS]);
  const filteredFlags = useMemo(() => {
    if (!qFlags) return QUALITY;
    const q = qFlags.toLowerCase();
    return QUALITY.filter(f => f.flag.toLowerCase().includes(q) || f.label.toLowerCase().includes(q));
  }, [qFlags]);

  // helpers
  const toggleIn = (set, val) => {
    const next = new Set(set);
    next.has(val) ? next.delete(val) : next.add(val);
    return next;
  };

  // quick range
  const applyQuick = id => {
    const r = QUICK_RANGES.find(x => x.id === id);
    if (!r) return;
    setQuickRange(id);
    setStartDate(r.start);
    setEndDate(r.end);
  };
  const onDateChange = (which, v) => {
    // Defense in depth: the inputs' min/max already constrain the native
    // picker, but a typed/programmatic value could invert the range. Clamp so
    // start ≤ end always holds (no "2020–2000").
    if (which === 'start') {
      setStartDate(v);
      if (v > endDate) setEndDate(v);
    } else {
      setEndDate(v);
      if (v < startDate) setStartDate(v);
    }
    setQuickRange(null);
  };

  // summary
  const summary = useMemo(() => {
    const prodTxt = products.size === PRODS.length ? `${PRODS.length} produtos (todos)` : `${products.size} de ${PRODS.length} produtos`;
    const period = `${formatMonth(startDate)}–${formatMonth(endDate)}`;
    const geoTxt = !hasGeo ? 'sem recorte geográfico' : nations.size === NATIONS.length && regions.size === FM_REGIONS.length && states.size === STATES.length && (!showMunis || munis.size === MUNICIPALITIES.length) ? 'todo o território' : nations.size === 1 && nations.has('BR') && states.size === STATES.length && (!showMunis || munis.size === MUNICIPALITIES.length) ? 'Brasil · todos os estados' : showMunis ? `${nations.size} nação(ões), ${states.size} UF, ${munis.size === MUNICIPALITIES.length ? 'todos os' : munis.size} municípios` : `${nations.size} nação(ões), ${states.size} UF`;
    return {
      prodTxt,
      period,
      geoTxt
    };
  }, [products, startDate, endDate, nations, regions, states, munis, hasGeo, showMunis]);

  // chip-bar summary published on apply (display strings only)
  const buildChipSummary = (vMin = valueMin, vMax = valueMax) => {
    const prodChip = window.chipFmt.products(products.size, PRODS.length, (PRODS.find(p => products.has(p.code)) || {}).name);
    const periodChip = quickRange === 'all' ? `${YEAR_START}–${YEAR_END}` : `${formatMonth(startDate)}–${formatMonth(endDate)}`;
    const valueChip = window.chipFmt.valueRange(vMin, vMax, sym);
    const muniFull = !showMunis || munis.size === MUNICIPALITIES.length; // all listed (or no municipal level) = no municipal slice
    const geoChip = !hasGeo ? 'Não se aplica' : nations.size === 1 && nations.has('BR') && states.size === STATES.length && muniFull ? `Brasil · ${STATES.length} UFs` : nations.size === NATIONS.length && regions.size === FM_REGIONS.length && states.size === STATES.length && muniFull ? 'Todo o território' : !muniFull ? `${states.size} ${states.size === 1 ? 'UF' : 'UFs'} · ${munis.size} ${munis.size === 1 ? 'município' : 'municípios'}` : `${nations.size} ${nations.size === 1 ? 'nação' : 'nações'} · ${states.size} ${states.size === 1 ? 'UF' : 'UFs'}`;
    const qualityChip = window.chipFmt.quality([...flags], QUALITY.length, qualityLabelOf);
    return {
      products: prodChip,
      period: periodChip,
      valueRange: valueChip,
      geo: geoChip,
      quality: qualityChip
    };
  };
  const applyAndClose = () => {
    // Normalize an inverted value range (min > max) before publishing, so the
    // chip and stored filter never show a backwards "R$ 1 mi – R$ 1 mil".
    let vMin = valueMin,
      vMax = valueMax;
    if (vMin != null && vMax != null && vMin > vMax) {
      const t = vMin;
      vMin = vMax;
      vMax = t;
    }
    if (typeof onApply === 'function') {
      onApply({
        ...buildChipSummary(vMin, vMax),
        basket: [...products],
        flags: [...flags],
        nations: [...nations],
        regions: [...regions],
        states: [...states],
        munis: [...munis],
        // Selected município NAMES (the data keys by city name, not code) so
        // the engine can actually narrow topMunis by the município selection.
        muniNames: [...munis].map(c => (MUNICIPALITIES.find(m => m.code === c) || {}).name).filter(Boolean),
        startDate,
        endDate,
        valueMin: vMin,
        valueMax: vMax
      });
    }
    close();
  };

  // restore defaults
  const restoreDefaults = () => {
    setProducts(new Set(PRODS.map(p => p.code)));
    setFlags(new Set(QUALITY.map(f => f.flag)));
    setNations(new Set(['BR']));
    setRegions(new Set(FM_REGIONS.map(r => r.id)));
    setStates(new Set(STATES.map(s => s.uf)));
    setMunis(new Set(MUNICIPALITIES.map(m => m.code)));
    applyQuick('all');
    setValueMin(null);
    setValueMax(null);
    [setQProducts, setQFlags, setQNations, setQRegions, setQStates, setQMunis].forEach(fn => fn(''));
  };
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    className: "fm-backdrop",
    onClick: close
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-modal wide",
    onClick: e => e.stopPropagation(),
    role: "dialog",
    "aria-labelledby": "fm-title"
  }, /*#__PURE__*/React.createElement("header", {
    className: "fm-head"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-head-text"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-head-over"
  }, "Filtros \xB7 ", bancoMeta ? bancoMeta.short : 'Banco', schema && /*#__PURE__*/React.createElement("span", {
    className: "fm-head-table"
  }, " \xB7 ", /*#__PURE__*/React.createElement("code", null, window.bancoTable(banco)))), /*#__PURE__*/React.createElement("span", {
    id: "fm-title",
    className: "fm-title"
  }, isLive ? 'Editar filtros' : 'Dimensões filtráveis'), /*#__PURE__*/React.createElement("span", {
    className: "fm-summary"
  }, isLive ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("strong", null, summary.prodTxt), " \xB7 ", summary.period, " \xB7 ", summary.geoTxt) : /*#__PURE__*/React.createElement(React.Fragment, null, "Pr\xE9-visualiza\xE7\xE3o \xB7 este banco ser\xE1 habilitado em ", /*#__PURE__*/React.createElement("strong", null, bancoMeta?.plannedRelease || 'breve')))), /*#__PURE__*/React.createElement("button", {
    className: "fm-close",
    onClick: close,
    "aria-label": "Fechar"
  }, I.close)), !isLive ? /*#__PURE__*/React.createElement(FilterPreview, {
    schema: schema,
    banco: bancoMeta,
    onClose: close
  }) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "fm-body"
  }, /*#__PURE__*/React.createElement("section", {
    className: "fm-section"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head-l"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-label"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-num"
  }, "01"), prodLabel), /*#__PURE__*/React.createElement(SearchInput, {
    value: qProducts,
    onChange: setQProducts,
    placeholder: "Buscar produto ou c\xF3digo\u2026"
  })), /*#__PURE__*/React.createElement("span", {
    className: "fm-section-meta"
  }, /*#__PURE__*/React.createElement("strong", null, products.size), " de ", PRODS.length, " selecionados")), /*#__PURE__*/React.createElement("div", {
    className: "fm-section-inner"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-grid-scroll"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-grid"
  }, filteredProducts.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "fm-empty-grid"
  }, "Nenhum produto corresponde a \u201C", qProducts, "\u201D.") : filteredProducts.map(p => {
    const on = products.has(p.code);
    return /*#__PURE__*/React.createElement("label", {
      key: p.code,
      className: 'fm-check' + (on ? ' is-on' : '')
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: on,
      onChange: () => setProducts(s => toggleIn(s, p.code))
    }), /*#__PURE__*/React.createElement("span", {
      className: "fm-name"
    }, p.name), /*#__PURE__*/React.createElement("span", {
      className: "fm-code"
    }, p.code));
  }))), /*#__PURE__*/React.createElement(BulkActions, {
    all: () => setProducts(prev => new Set([...prev, ...filteredProducts.map(p => p.code)])),
    none: () => {
      const vis = new Set(filteredProducts.map(p => p.code));
      setProducts(prev => new Set([...prev].filter(c => !vis.has(c))));
    },
    invert: () => setProducts(prev => {
      const n = new Set(prev);
      filteredProducts.forEach(p => n.has(p.code) ? n.delete(p.code) : n.add(p.code));
      return n;
    }),
    selectedCount: filteredProducts.filter(p => products.has(p.code)).length,
    totalCount: filteredProducts.length
  }))), /*#__PURE__*/React.createElement("section", {
    className: "fm-section"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head-l"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-label"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-num"
  }, "02"), "Per\xEDodo & faixa de valor")), /*#__PURE__*/React.createElement("span", {
    className: "fm-section-meta"
  }, formatMonth(startDate), "\u2013", formatMonth(endDate), " \xB7", ' ', valueMin == null && valueMax == null ? 'sem limite por linha' : 'valor por linha: ' + (valueMin != null ? fmtVal(valueMin) : '—') + ' – ' + (valueMax != null ? fmtVal(valueMax) : '—'))), /*#__PURE__*/React.createElement("div", {
    className: "fm-row-2"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-col"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-col-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-label"
  }, "Per\xEDodo de refer\xEAncia"), /*#__PURE__*/React.createElement("span", {
    className: "fm-section-meta"
  }, quickRange ? /*#__PURE__*/React.createElement("strong", null, QUICK_RANGES.find(r => r.id === quickRange).label) : 'Intervalo personalizado')), /*#__PURE__*/React.createElement("div", {
    className: "fm-quick"
  }, QUICK_RANGES.map(r => /*#__PURE__*/React.createElement("button", {
    key: r.id,
    className: quickRange === r.id ? 'on' : '',
    onClick: () => applyQuick(r.id),
    type: "button"
  }, r.id === 'all' ? 'Tudo' : 'Últimos ' + r.label))), /*#__PURE__*/React.createElement("div", {
    className: "fm-date-row"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-date-field"
  }, /*#__PURE__*/React.createElement("label", {
    htmlFor: "fm-start"
  }, "In\xEDcio"), /*#__PURE__*/React.createElement("input", {
    id: "fm-start",
    className: "fm-date",
    type: "month",
    value: startDate,
    min: `${YEAR_START}-01`,
    max: endDate,
    onChange: e => onDateChange('start', e.target.value)
  })), /*#__PURE__*/React.createElement("div", {
    className: "fm-arrow"
  }, I.arrow), /*#__PURE__*/React.createElement("div", {
    className: "fm-date-field"
  }, /*#__PURE__*/React.createElement("label", {
    htmlFor: "fm-end"
  }, "Fim"), /*#__PURE__*/React.createElement("input", {
    id: "fm-end",
    className: "fm-date",
    type: "month",
    value: endDate,
    min: startDate,
    max: `${YEAR_END}-12`,
    onChange: e => onDateChange('end', e.target.value)
  })))), /*#__PURE__*/React.createElement("div", {
    className: "fm-divider",
    "aria-hidden": "true"
  }), /*#__PURE__*/React.createElement("div", {
    className: "fm-col"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-col-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-label"
  }, "Faixa de valor por linha"), /*#__PURE__*/React.createElement("span", {
    className: "fm-section-meta"
  }, valColumn)), /*#__PURE__*/React.createElement("p", {
    className: "fm-col-help"
  }, "Inclua apenas linhas cujo valor monet\xE1rio esteja dentro da faixa. Os limites s\xE3o aplicados sobre o valor em ", /*#__PURE__*/React.createElement("strong", null, sym), "; a moeda e corre\xE7\xE3o de exibi\xE7\xE3o s\xE3o definidas em ", /*#__PURE__*/React.createElement("strong", null, "Conven\xE7\xF5es m\xE9tricas"), "."), /*#__PURE__*/React.createElement("div", {
    className: "fm-sub"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-sub-label"
  }, "Limites"), /*#__PURE__*/React.createElement("div", {
    className: "fm-range-row"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-range-field"
  }, /*#__PURE__*/React.createElement("label", {
    htmlFor: "fm-vmin"
  }, "M\xEDnimo (", sym, ")"), /*#__PURE__*/React.createElement("input", {
    id: "fm-vmin",
    type: "number",
    inputMode: "numeric",
    min: "0",
    step: "1000",
    placeholder: "sem limite",
    value: valueMin == null ? '' : valueMin,
    onChange: e => {
      const v = e.target.value;
      setValueMin(v === '' ? null : Math.max(0, Number(v)));
    }
  })), /*#__PURE__*/React.createElement("div", {
    className: "fm-arrow"
  }, I.arrow), /*#__PURE__*/React.createElement("div", {
    className: "fm-range-field"
  }, /*#__PURE__*/React.createElement("label", {
    htmlFor: "fm-vmax"
  }, "M\xE1ximo (", sym, ")"), /*#__PURE__*/React.createElement("input", {
    id: "fm-vmax",
    type: "number",
    inputMode: "numeric",
    min: "0",
    step: "1000",
    placeholder: "sem limite",
    value: valueMax == null ? '' : valueMax,
    onChange: e => {
      const v = e.target.value;
      setValueMax(v === '' ? null : Math.max(0, Number(v)));
    }
  })))), /*#__PURE__*/React.createElement("div", {
    className: "fm-sub"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-sub-label"
  }, "Atalhos \xB7 valor m\xEDnimo"), /*#__PURE__*/React.createElement("div", {
    className: "fm-quick"
  }, (window.VALUE_PRESETS || []).map(p => ({
    ...p,
    label: p.suffix ? `≥ ${sym} ${p.suffix}` : 'Sem limite'
  })).map(p => {
    const on = valueMin === p.min && valueMax === p.max;
    return /*#__PURE__*/React.createElement("button", {
      key: p.id,
      type: "button",
      className: on ? 'on' : '',
      onClick: () => {
        setValueMin(p.min);
        setValueMax(p.max);
      }
    }, p.label);
  })))))), hasGeo && /*#__PURE__*/React.createElement("section", {
    className: "fm-section"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head-l"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-label"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-num"
  }, "03"), "Geografia"), /*#__PURE__*/React.createElement("span", {
    className: "fm-cascade-hint"
  }, I.cascade, " Sele\xE7\xE3o em cascata \xB7 na\xE7\xE3o \u25B8 regi\xE3o \u25B8 estado", showMunis ? ' ▸ município' : '')), /*#__PURE__*/React.createElement("span", {
    className: "fm-section-meta"
  }, /*#__PURE__*/React.createElement("strong", null, nations.size), " ", nations.size === 1 ? 'nação' : 'nações', " \xB7", ' ', /*#__PURE__*/React.createElement("strong", null, regions.size), " ", regions.size === 1 ? 'região' : 'regiões', " \xB7", ' ', /*#__PURE__*/React.createElement("strong", null, states.size), " ", states.size === 1 ? 'UF' : 'UFs', showMunis && /*#__PURE__*/React.createElement(React.Fragment, null, ' ', "\xB7", ' ', /*#__PURE__*/React.createElement("strong", null, munis.size), " ", munis.size === 1 ? 'município' : 'municípios'))), /*#__PURE__*/React.createElement("div", {
    className: "fm-section-inner"
  }, /*#__PURE__*/React.createElement("div", {
    className: 'fm-geo-grid' + (showMunis ? '' : ' cols-3')
  }, /*#__PURE__*/React.createElement(GeoColumn, {
    title: "Na\xE7\xF5es",
    items: NATIONS,
    keyAttr: "iso",
    displayAttr: "name",
    getMeta: x => x.iso,
    selected: nations,
    setSelected: setNations,
    search: qNations,
    setSearch: setQNations
  }), /*#__PURE__*/React.createElement(GeoColumn, {
    title: "Regi\xF5es",
    items: eligibleRegions,
    keyAttr: "id",
    displayAttr: "name",
    getMeta: x => x.id,
    selected: regions,
    setSelected: setRegions,
    search: qRegions,
    setSearch: setQRegions,
    disabledReason: nations.size === 0 ? 'Selecione ao menos uma nação.' : null
  }), /*#__PURE__*/React.createElement(GeoColumn, {
    title: "Estados",
    items: eligibleStates,
    keyAttr: "uf",
    displayAttr: "name",
    getMeta: x => x.uf,
    selected: states,
    setSelected: setStates,
    search: qStates,
    setSearch: setQStates,
    disabledReason: eligibleRegions.length === 0 || regions.size === 0 ? 'Selecione ao menos uma região.' : null
  }), showMunis && /*#__PURE__*/React.createElement(GeoColumn, {
    title: "Munic\xEDpios",
    items: eligibleMunis,
    keyAttr: "code",
    displayAttr: "name",
    getMeta: x => x.uf,
    selected: munis,
    setSelected: setMunis,
    search: qMunis,
    setSearch: setQMunis,
    disabledReason: eligibleStates.length === 0 || states.size === 0 ? 'Selecione ao menos um estado.' : null
  })), showMunis && /*#__PURE__*/React.createElement("div", {
    className: "fm-geo-foot"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-meta"
  }, "Lista parcial: ", MUNICIPALITIES.length, " munic\xEDpios l\xEDderes.", ' ', /*#__PURE__*/React.createElement("a", {
    href: "#",
    onClick: e => e.preventDefault()
  }, "Carregar todos os 5 570"))))), /*#__PURE__*/React.createElement("section", {
    className: "fm-section"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head-l"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-label"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-num"
  }, hasGeo ? '04' : '03'), "Qualidade dos dados \xB7 ", /*#__PURE__*/React.createElement("span", {
    className: "mono lowercase"
  }, "data_quality_flag")), /*#__PURE__*/React.createElement(SearchInput, {
    value: qFlags,
    onChange: setQFlags,
    placeholder: "Buscar flag\u2026"
  })), /*#__PURE__*/React.createElement("span", {
    className: "fm-section-meta"
  }, /*#__PURE__*/React.createElement("strong", null, flags.size), " de ", QUALITY.length, " selecionadas")), /*#__PURE__*/React.createElement("div", {
    className: "fm-section-inner"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-grid-scroll"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-grid"
  }, filteredFlags.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "fm-empty-grid"
  }, "Nenhuma flag corresponde a \u201C", qFlags, "\u201D.") : filteredFlags.map(q => {
    const on = flags.has(q.flag);
    return /*#__PURE__*/React.createElement("label", {
      key: q.flag,
      className: 'fm-check' + (on ? ' is-on' : '')
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: on,
      onChange: () => setFlags(s => toggleIn(s, q.flag))
    }), /*#__PURE__*/React.createElement("span", {
      className: "fm-name"
    }, q.label), /*#__PURE__*/React.createElement("span", {
      className: "fm-code mono"
    }, q.flag));
  }))), /*#__PURE__*/React.createElement(BulkActions, {
    all: () => setFlags(prev => new Set([...prev, ...filteredFlags.map(q => q.flag)])),
    none: () => {
      const vis = new Set(filteredFlags.map(q => q.flag));
      setFlags(prev => new Set([...prev].filter(f => !vis.has(f))));
    },
    invert: () => setFlags(prev => {
      const n = new Set(prev);
      filteredFlags.forEach(q => n.has(q.flag) ? n.delete(q.flag) : n.add(q.flag));
      return n;
    }),
    selectedCount: filteredFlags.filter(q => flags.has(q.flag)).length,
    totalCount: filteredFlags.length
  }))), extraDims.length > 0 && /*#__PURE__*/React.createElement("section", {
    className: "fm-section"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-section-head-l"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-label"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-section-num"
  }, "+"), "Dimens\xF5es espec\xEDficas \xB7 ", bancoMeta ? bancoMeta.short : '')), /*#__PURE__*/React.createElement("span", {
    className: "fm-section-meta"
  }, extraDims.length, " ", extraDims.length === 1 ? 'dimensão' : 'dimensões', " \xB7 em breve filtr\xE1veis")), /*#__PURE__*/React.createElement("div", {
    className: "fm-section-inner"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-extra-note"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-extra-badge"
  }, "Em breve"), /*#__PURE__*/React.createElement("span", null, "Dimens\xF5es pr\xF3prias deste banco. J\xE1 declaradas no schema e ficar\xE3o filtr\xE1veis quando a Gold completa for publicada.")), /*#__PURE__*/React.createElement("div", {
    className: "fm-extra-grid"
  }, extraDims.map(d => /*#__PURE__*/React.createElement("div", {
    key: d.id,
    className: "fm-extra-dim"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-extra-dim-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-extra-dim-label"
  }, d.label), /*#__PURE__*/React.createElement("span", {
    className: "fm-extra-dim-type"
  }, d.type)), /*#__PURE__*/React.createElement("code", {
    className: "fm-extra-dim-col"
  }, d.column), d.options && /*#__PURE__*/React.createElement("div", {
    className: "fm-extra-opts"
  }, d.options.map(o => /*#__PURE__*/React.createElement("span", {
    key: o,
    className: "fm-extra-opt"
  }, o))))))))), /*#__PURE__*/React.createElement("footer", {
    className: "fm-foot"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-foot-info"
  }, "Os filtros ser\xE3o aplicados sobre ", /*#__PURE__*/React.createElement("strong", null, window.bancoTable(banco) || 'gold_pevs_production'), /*#__PURE__*/React.createElement("span", {
    className: "fm-dot"
  }), bancoMeta?.prov?.refresh ? `Refresh ${bancoMeta.prov.refresh}` : 'Atualização diária às 06h00 BRT'), /*#__PURE__*/React.createElement("button", {
    className: "btn-ghost",
    onClick: restoreDefaults
  }, "Restaurar padr\xE3o"), /*#__PURE__*/React.createElement("button", {
    className: "btn-secondary",
    onClick: close
  }, "Cancelar"), /*#__PURE__*/React.createElement("button", {
    className: "btn-primary",
    onClick: applyAndClose
  }, "Aplicar filtros")))));
}

// ----- Preview body for soon bancos -------------------------------
// Renders the planned filter dimensions read-only, grouped by tier,
// so the researcher sees what they'll be able to filter once live.
function FilterPreview({
  schema,
  banco,
  onClose
}) {
  const TIER = window.TIER_LABEL || {};
  const dims = schema && schema.dims || [];
  const tiers = ['universal', 'shared', 'specific'];
  const byTier = tiers.map(t => ({
    tier: t,
    items: dims.filter(d => d.tier === t)
  })).filter(g => g.items.length > 0);
  return /*#__PURE__*/React.createElement("div", {
    className: "fm-body fm-preview"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-preview-banner"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-preview-badge"
  }, "Em breve"), /*#__PURE__*/React.createElement("span", null, "Este banco ainda n\xE3o foi liberado no backend. Abaixo est\xE3o as dimens\xF5es que estar\xE3o dispon\xEDveis para filtragem assim que a tabela ", /*#__PURE__*/React.createElement("code", null, window.bancoTable(banco)), " for publicada", banco?.plannedRelease ? ` (previsão ${banco.plannedRelease})` : '', ".")), byTier.map(g => /*#__PURE__*/React.createElement("section", {
    key: g.tier,
    className: "fm-preview-group"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-preview-group-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-preview-tier"
  }, TIER[g.tier] || g.tier), /*#__PURE__*/React.createElement("span", {
    className: "fm-preview-tier-meta"
  }, g.items.length, " dimens\xE3o(\xF5es)")), /*#__PURE__*/React.createElement("div", {
    className: "fm-preview-grid"
  }, g.items.map(d => /*#__PURE__*/React.createElement("div", {
    key: d.id,
    className: "fm-preview-dim"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-preview-dim-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-preview-dim-label"
  }, d.label), /*#__PURE__*/React.createElement("span", {
    className: "fm-preview-dim-type"
  }, d.type)), /*#__PURE__*/React.createElement("code", {
    className: "fm-preview-dim-col"
  }, d.column), /*#__PURE__*/React.createElement("p", {
    className: "fm-preview-dim-hint"
  }, d.hint), d.options && /*#__PURE__*/React.createElement("div", {
    className: "fm-preview-opts"
  }, d.options.map(o => /*#__PURE__*/React.createElement("span", {
    key: o,
    className: "fm-preview-opt"
  }, o)))))))), /*#__PURE__*/React.createElement("footer", {
    className: "fm-foot"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fm-foot-info"
  }, dims.length, " dimens\xF5es previstas \xB7 scoped a ", /*#__PURE__*/React.createElement("strong", null, window.bancoTable(banco))), /*#__PURE__*/React.createElement("button", {
    className: "btn-primary",
    onClick: onClose
  }, "Entendi")));
}
function formatMonth(iso) {
  if (!iso) return '—';
  const [y, m] = iso.split('-');
  return `${m}/${y}`;
}
window.FilterMenu = FilterMenu;
})(); } catch (e) { __ds_ns.__errors.push({ path: "FilterMenu.jsx", error: String((e && e.message) || e) }); }

// FilterTriggerBar.jsx
try { (() => {
// FilterTriggerBar — active-filter chip row that opens the FilterMenu modal.
// Replaces the legacy <FilterBar> dropdown row.

function FilterTriggerBar({
  summary,
  onOpen,
  onExport,
  live = true,
  banco = null,
  view = null
}) {
  // Soon banco → slim preview trigger (no real filters/data to export yet).
  if (!live) {
    return /*#__PURE__*/React.createElement("div", {
      className: "fm-trigger-bar preview"
    }, /*#__PURE__*/React.createElement("span", {
      className: "fm-tb-label"
    }, "Filtros"), /*#__PURE__*/React.createElement("span", {
      className: "fm-tb-preview-note"
    }, "Dispon\xEDveis quando ", /*#__PURE__*/React.createElement("strong", null, banco ? banco.short : 'o banco'), " for liberado", banco?.plannedRelease ? ` · previsão ${banco.plannedRelease}` : ''), /*#__PURE__*/React.createElement("span", {
      className: "fm-spacer"
    }), /*#__PURE__*/React.createElement("button", {
      className: "fm-edit-btn",
      onClick: onOpen
    }, /*#__PURE__*/React.createElement("svg", {
      width: "13",
      height: "13",
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.8",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement("circle", {
      cx: "11",
      cy: "11",
      r: "7"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M21 21l-4.3-4.3"
    })), "Ver dimens\xF5es previstas"));
  }
  const chips = [{
    k: 'Produtos',
    v: summary.products
  }, {
    k: 'Período',
    v: summary.period
  }, {
    k: 'Faixa de valor',
    v: summary.valueRange
  }, {
    k: 'Geografia',
    v: summary.geo
  }, {
    k: 'Qualidade',
    v: summary.quality
  }];
  const canExport = !window.canExportView || window.canExportView(view);
  return /*#__PURE__*/React.createElement("div", {
    className: "fm-trigger-bar"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-tb-label"
  }, "Filtros ativos"), chips.map((c, i) => /*#__PURE__*/React.createElement("span", {
    key: i,
    className: "fm-chip-filter"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fm-chip-k"
  }, c.k), c.v)), /*#__PURE__*/React.createElement("span", {
    className: "fm-spacer"
  }), /*#__PURE__*/React.createElement("button", {
    className: "fm-edit-btn",
    onClick: onOpen
  }, /*#__PURE__*/React.createElement("svg", {
    width: "13",
    height: "13",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 20h4l10-10-4-4L4 16zM14 6l4 4"
  })), "Editar filtros"), canExport && /*#__PURE__*/React.createElement("button", {
    className: "fm-export-btn",
    onClick: onExport,
    title: "Baixar dados filtrados em CSV"
  }, /*#__PURE__*/React.createElement("svg", {
    width: "13",
    height: "13",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: "7 10 12 15 17 10"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "12",
    y1: "15",
    x2: "12",
    y2: "3"
  })), "Exportar CSV"));
}
window.FilterTriggerBar = FilterTriggerBar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "FilterTriggerBar.jsx", error: String((e && e.message) || e) }); }

// Glossary.jsx
try { (() => {
// Glossary — two surfaces:
//   <Glossary scope="b1" />         per-banco glossary (topnav view)
//   <Glossary scope="global" />     searchable across all bancos (sidebar info)

const {
  useState: useGlossState,
  useMemo: useGlossMemo
} = React;
function Glossary({
  scope = 'global'
}) {
  const [q, setQ] = useGlossState('');
  const [activeCat, setActiveCat] = useGlossState('Todas');
  const sources = scope === 'global' ? Object.entries(window.GLOSSARY) : [[scope, window.GLOSSARY[scope]]];

  // Flatten with banco metadata
  const all = useGlossMemo(() => {
    const out = [];
    sources.forEach(([bid, b]) => {
      b.terms.forEach(t => out.push({
        ...t,
        bancoId: bid,
        bancoLabel: b.label
      }));
    });
    return out;
  }, [scope]);

  // Categories present in current scope
  const cats = useGlossMemo(() => {
    const set = new Set(all.map(t => t.cat).filter(Boolean));
    return ['Todas', ...[...set].sort()];
  }, [all]);

  // Apply filters
  const matches = useGlossMemo(() => {
    const needle = q.trim().toLowerCase();
    return all.filter(t => {
      if (activeCat !== 'Todas' && t.cat !== activeCat) return false;
      if (!needle) return true;
      return t.term.toLowerCase().includes(needle) || t.short.toLowerCase().includes(needle) || t.tag && t.tag.toLowerCase().includes(needle);
    });
  }, [all, q, activeCat]);

  // Group results by banco (global) or by category (per-banco)
  const groups = useGlossMemo(() => {
    if (scope === 'global') {
      const map = new Map();
      matches.forEach(t => {
        if (!map.has(t.bancoId)) map.set(t.bancoId, {
          id: t.bancoId,
          label: t.bancoLabel,
          sub: window.GLOSSARY[t.bancoId].sub,
          items: []
        });
        map.get(t.bancoId).items.push(t);
      });
      return [...map.values()];
    }
    // per-banco: group by category
    const map = new Map();
    matches.forEach(t => {
      const c = t.cat || 'Outros';
      if (!map.has(c)) map.set(c, {
        id: c,
        label: c,
        items: []
      });
      map.get(c).items.push(t);
    });
    return [...map.values()];
  }, [matches, scope]);
  const totalLabel = scope === 'global' ? `${matches.length} ${matches.length === 1 ? 'termo' : 'termos'} · ${groups.length} ${groups.length === 1 ? 'grupo' : 'grupos'}` : `${matches.length} de ${all.length} termos`;
  return /*#__PURE__*/React.createElement("div", {
    className: "gloss"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gloss-controls"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gloss-search"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "search",
    size: 14
  }), /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: q,
    onChange: e => setQ(e.target.value),
    placeholder: scope === 'global' ? 'Buscar termo, coluna ou definição em todos os bancos…' : 'Buscar termo, coluna ou definição neste banco…'
  }), q && /*#__PURE__*/React.createElement("button", {
    className: "gloss-clear",
    onClick: () => setQ(''),
    "aria-label": "Limpar busca"
  }, "\xD7")), /*#__PURE__*/React.createElement("div", {
    className: "gloss-cats"
  }, cats.map(c => /*#__PURE__*/React.createElement("button", {
    key: c,
    className: 'gloss-cat' + (activeCat === c ? ' on' : ''),
    onClick: () => setActiveCat(c)
  }, c))), /*#__PURE__*/React.createElement("span", {
    className: "gloss-count"
  }, totalLabel)), matches.length === 0 && /*#__PURE__*/React.createElement("div", {
    className: "card subtle gloss-empty"
  }, /*#__PURE__*/React.createElement("strong", null, "Nenhum termo corresponde a \u201C", q, "\u201D."), /*#__PURE__*/React.createElement("p", {
    className: "caption"
  }, "Tente outra palavra, ou troque a categoria para \"Todas\".")), groups.map(g => /*#__PURE__*/React.createElement("section", {
    key: g.id,
    className: "gloss-group"
  }, /*#__PURE__*/React.createElement("header", {
    className: "gloss-group-head"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "overline"
  }, scope === 'global' ? window.GLOSSARY[g.id]?.kind === 'tema' ? 'Tema' : 'Banco' : 'Categoria'), /*#__PURE__*/React.createElement("h2", {
    className: "gloss-group-title"
  }, g.label), g.sub && /*#__PURE__*/React.createElement("div", {
    className: "caption"
  }, g.sub)), /*#__PURE__*/React.createElement("span", {
    className: "caption"
  }, g.items.length, " ", g.items.length === 1 ? 'termo' : 'termos')), /*#__PURE__*/React.createElement("div", {
    className: "gloss-list"
  }, g.items.map((t, i) => /*#__PURE__*/React.createElement("article", {
    key: t.bancoId + ':' + t.term + ':' + i,
    className: "gloss-row"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gloss-row-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "gloss-term"
  }, t.term), t.tag && /*#__PURE__*/React.createElement("span", {
    className: "gloss-tag"
  }, t.tag), scope === 'global' && /*#__PURE__*/React.createElement("span", {
    className: "gloss-banco"
  }, t.bancoLabel), scope !== 'global' && t.cat && /*#__PURE__*/React.createElement("span", {
    className: "gloss-banco subtle"
  }, t.cat)), /*#__PURE__*/React.createElement("p", {
    className: "gloss-short"
  }, t.short)))))));
}
window.Glossary = Glossary;
})(); } catch (e) { __ds_ns.__errors.push({ path: "Glossary.jsx", error: String((e && e.message) || e) }); }

// Icon.jsx
try { (() => {
// Inline-SVG icon set — stroke-based, 1.8 weight, 24×24 grid.
// We use these instead of an icon font for reliability.

function Icon({
  name,
  size = 18
}) {
  const p = ICONS[name];
  if (!p) return null;
  return /*#__PURE__*/React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg",
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      flexShrink: 0
    },
    dangerouslySetInnerHTML: {
      __html: p
    }
  });
}
const ICONS = {
  // Navigation
  dashboard: `<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>`,
  eco: `<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 22c1.7-2.5 4.6-7 8-10"/>`,
  map: `<path d="M9 4 3 6v15l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v15"/><path d="M15 6v15"/>`,
  fact_check: `<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m9 10 1.5 1.5L13 9"/><path d="M16 11h2"/><path d="m9 16 1.5 1.5L13 15"/><path d="M16 17h2"/>`,
  database: `<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>`,
  hub: `<circle cx="12" cy="12" r="2.4"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/><path d="M10.3 10.6 6.3 7.2"/><path d="m13.7 10.6 4-3.4"/><path d="m10.3 13.4-4 3.4"/><path d="m13.7 13.4 4 3.4"/>`,
  download: `<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>`,
  api: `<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>`,
  help: `<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>`,
  info: `<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>`,
  notifications: `<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>`,
  schedule: `<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>`,
  arrow_upward: `<line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>`,
  arrow_downward: `<line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>`,
  search: `<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>`,
  filter: `<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>`,
  menu_book: `<path d="M2 19V5a2 2 0 0 1 2-2h6v18H4a2 2 0 0 1-2-2z"/><path d="M22 19V5a2 2 0 0 0-2-2h-6v18h6a2 2 0 0 0 2-2z"/>`,
  refresh: `<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>`,
  format_quote: `<path d="M7 7h4v6H5v-2c0-2 .5-3 2-4zm8 0h4v6h-6v-2c0-2 .5-3 2-4z"/>`,
  link: `<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1.5-1.5"/>`,
  content_copy: `<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>`,
  close: `<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>`,
  expand_more: `<polyline points="6 9 12 15 18 9"/>`,
  warning: `<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>`,
  pulse: `<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>`,
  trending_up: `<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>`
};
window.Icon = Icon;
})(); } catch (e) { __ds_ns.__errors.push({ path: "Icon.jsx", error: String((e && e.message) || e) }); }

// MainScreen.jsx
try { (() => {
// MainScreen — thin router that picks the right view component
// for the active perspective (topnav) or info page (sidebar).

function MainScreen({
  filters,
  view = 'overview',
  database = 'ibge_pevs',
  infoPage = null,
  basket = null,
  conventions = null,
  setDatabase = null,
  crossState = null,
  setCrossState = null
}) {
  const VIEW_LABEL = Object.fromEntries((window.VIEW_GROUPS || []).flatMap(g => g.views.map(v => [v.id, v.label])));
  const BANCO_LABEL = Object.fromEntries((window.BANCOS || []).map(b => [b.id, b.short]));
  const BANCO_SUB = Object.fromEntries((window.BANCOS || []).map(b => [b.id, b.sub]));
  const BANCO_PROV = Object.fromEntries((window.BANCOS || []).filter(b => b.status === 'live').map(b => [b.id, {
    source: b.short,
    table: window.bancoTable(b.id),
    ...b.prov
  }]));

  // Compute active unit families from the basket
  const families = window.familiesInBasket(basket, database);

  // ---- Info pages (sidebar) ----
  if (infoPage === 'glossary') {
    return /*#__PURE__*/React.createElement("div", {
      className: "screen"
    }, /*#__PURE__*/React.createElement("div", {
      className: "page-hero"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "overline"
    }, "Informa\xE7\xF5es"), /*#__PURE__*/React.createElement("h1", {
      className: "page-title"
    }, "Gloss\xE1rio global"), /*#__PURE__*/React.createElement("p", {
      className: "page-sub"
    }, "Pesquise termos, c\xF3digos e colunas em todos os bancos do dashboard. Filtre por categoria ou banco de origem."))), /*#__PURE__*/React.createElement(window.Glossary, {
      scope: "global"
    }));
  }
  if (infoPage === 'curation') {
    return /*#__PURE__*/React.createElement("div", {
      className: "screen",
      "data-screen-label": "Curadoria"
    }, /*#__PURE__*/React.createElement("div", {
      className: "page-hero"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "overline"
    }, "Curadoria \xB7 conhecimento do pesquisador"), /*#__PURE__*/React.createElement("h1", {
      className: "page-title"
    }, "Enriquecimento dos dados"), /*#__PURE__*/React.createElement("p", {
      className: "page-sub"
    }, "Adicione conhecimento \xE0s dimens\xF5es dos bancos \u2014 n\xEDvel de industrializa\xE7\xE3o dos c\xF3digos e finalidade econ\xF4mica dos fluxos. Essas anota\xE7\xF5es destravam as", /*#__PURE__*/React.createElement("strong", null, " An\xE1lises curadas"), " no modo Multi-fonte."))), /*#__PURE__*/React.createElement(window.ViewCuration, null));
  }
  if (infoPage) {
    return /*#__PURE__*/React.createElement("div", {
      className: "screen"
    }, /*#__PURE__*/React.createElement("div", {
      className: "page-hero"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "overline"
    }, "Informa\xE7\xF5es"), /*#__PURE__*/React.createElement("h1", {
      className: "page-title"
    }, infoPage === 'about' ? 'Sobre o dashboard' : 'Saúde do sistema'), /*#__PURE__*/React.createElement("p", {
      className: "page-sub"
    }, infoPage === 'about' ? 'O que é o dashboard, quais bancos compõem a base, como os dados são processados e como interpretar cada perspectiva.' : 'Status das execuções de pipeline, frescor dos dados e qualidade das tabelas Gold.'))), infoPage === 'about' ? /*#__PURE__*/React.createElement(window.ViewAbout, null) : infoPage === 'health' ? /*#__PURE__*/React.createElement(window.ViewHealth, null) : /*#__PURE__*/React.createElement("div", {
      className: "card subtle"
    }, /*#__PURE__*/React.createElement(window.SectionHeader, {
      overline: "Em constru\xE7\xE3o",
      title: "Conte\xFAdo em prepara\xE7\xE3o"
    }), /*#__PURE__*/React.createElement("p", {
      className: "caption",
      style: {
        padding: '8px 4px 4px'
      }
    }, "Conte\xFAdo desta p\xE1gina ser\xE1 detalhado em pr\xF3xima itera\xE7\xE3o.")));
  }

  // ---- Per-banco glossary (topnav) ----
  if (view === 'glossary') {
    const banco = window.GLOSSARY[database];
    if (!banco) {
      return /*#__PURE__*/React.createElement("div", {
        className: "screen"
      }, /*#__PURE__*/React.createElement("div", {
        className: "page-hero"
      }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
        className: "overline"
      }, "Gloss\xE1rio"), /*#__PURE__*/React.createElement("h1", {
        className: "page-title"
      }, "Gloss\xE1rio do banco em prepara\xE7\xE3o"), /*#__PURE__*/React.createElement("p", {
        className: "page-sub"
      }, "O gloss\xE1rio espec\xEDfico deste banco ser\xE1 publicado junto da libera\xE7\xE3o dos dados. Use o gloss\xE1rio global na barra lateral para buscar termos compartilhados."))));
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "screen"
    }, /*#__PURE__*/React.createElement("div", {
      className: "page-hero"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "overline"
    }, "Gloss\xE1rio \xB7 ", banco.label), /*#__PURE__*/React.createElement("h1", {
      className: "page-title"
    }, "Termos e colunas \xB7 ", banco.label), /*#__PURE__*/React.createElement("p", {
      className: "page-sub"
    }, banco.sub, ". Defini\xE7\xF5es dos termos, fontes e colunas usados nesta perspectiva. Use o gloss\xE1rio global na barra lateral para buscar em todos os bancos."))), /*#__PURE__*/React.createElement(window.Glossary, {
      scope: database
    }));
  }

  // ---- Cross-source perspectives (operate ACROSS bancos) --------------
  // Meta-perspectives: they don't read the active banco's snapshot, so they
  // render before banco resolution / soon / capability gating. cross_source
  // is the picker-driven one (its selection lives in crossState); the others
  // are self-contained analytical views with fixed `sources`.
  const _cvm = window.viewById ? window.viewById(view) : null;
  if (_cvm && _cvm.crossBanco) {
    const isPicker = _cvm.id === 'cross_source';
    const baseSeries = crossState && crossState.series || window.DEFAULT_CROSS_STATE.series;
    const srcIds = isPicker ? [...new Set(baseSeries.map(s => s.b))] : _cvm.sources || [];
    const srcShorts = srcIds.map(id => window.bancoById(id)?.short).filter(Boolean).join(' · ');
    const Comp = window.viewComponent(_cvm.id);
    return /*#__PURE__*/React.createElement("div", {
      className: "screen",
      "data-screen-label": `Perspectiva · ${VIEW_LABEL[view]}`
    }, /*#__PURE__*/React.createElement("div", {
      className: "page-hero"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "overline"
    }, "An\xE1lise cruzada \xB7 multi-fonte"), /*#__PURE__*/React.createElement("h1", {
      className: "page-title"
    }, VIEW_LABEL[view]), /*#__PURE__*/React.createElement("p", {
      className: "page-sub"
    }, isPicker ? 'Compare séries históricas anuais de bancos diferentes no mesmo eixo de tempo — a evolução não é mais limitada a um banco ativo por vez.' : _cvm.desc)), /*#__PURE__*/React.createElement("div", {
      className: "hero-meta"
    }, /*#__PURE__*/React.createElement("div", {
      className: "meta-group"
    }, /*#__PURE__*/React.createElement("div", {
      className: "meta-group-head"
    }, "Cruzamento ativo"), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Fontes"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, srcShorts || '—')), isPicker && /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "S\xE9ries"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val tnum"
    }, /*#__PURE__*/React.createElement("strong", null, baseSeries.length), " ", /*#__PURE__*/React.createElement("small", null, "de 4"))), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Alinhamento"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, _cvm.align || 'eixo temporal (ano)'))))), isPicker ? /*#__PURE__*/React.createElement(window.ViewCrossSource, {
      value: crossState || window.DEFAULT_CROSS_STATE,
      onChange: setCrossState
    }) : Comp ? /*#__PURE__*/React.createElement(Comp, {
      view: _cvm.id
    }) : null);
  }

  // ---- Resolve banco from the registry ----------
  const banco = window.bancoById(database);
  const isSoon = banco && banco.status === 'soon';

  // Preview perspectives bring their own banco-keyed (synthetic) data, so
  // they render even while the banco itself is 'soon'. They take precedence
  // over the banco-level coming-soon — but ONLY when the view applies.
  const _vm = window.viewById ? window.viewById(view) : null;
  const _compat = window.viewAppliesTo ? window.viewAppliesTo(view, database) : {
    applies: true,
    missing: []
  };
  if (_vm && _vm.selfData && _compat.applies) {
    const PreviewComp = window.viewComponent(view);
    if (PreviewComp) {
      return /*#__PURE__*/React.createElement("div", {
        className: "screen"
      }, /*#__PURE__*/React.createElement("div", {
        className: "page-hero"
      }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
        className: "overline"
      }, banco.short, " \xB7 ", _vm.group?.label), /*#__PURE__*/React.createElement("h1", {
        className: "page-title"
      }, VIEW_LABEL[view]), /*#__PURE__*/React.createElement("p", {
        className: "page-sub"
      }, banco.sub))), /*#__PURE__*/React.createElement(PreviewComp, {
        summary: filters,
        conventions: conventions,
        database: database
      }));
    }
  }

  // ---- Perspective not applicable to this banco (capability mismatch) --
  // A permanent incompatibility outranks the temporary 'Em breve' of a
  // soon banco — so this check runs BEFORE the isSoon block. (selfData
  // preview views already returned above.)
  if (_vm && !_compat.applies) {
    const supporters = window.bancosSupporting ? window.bancosSupporting(view) : [];
    return /*#__PURE__*/React.createElement("div", {
      className: "screen"
    }, /*#__PURE__*/React.createElement("div", {
      className: "page-hero"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "overline"
    }, BANCO_LABEL[database], " \xB7 ", _vm.group?.label), /*#__PURE__*/React.createElement("h1", {
      className: "page-title"
    }, _vm.label), /*#__PURE__*/React.createElement("p", {
      className: "page-sub"
    }, BANCO_SUB[database])), /*#__PURE__*/React.createElement("div", {
      className: "hero-meta"
    }, /*#__PURE__*/React.createElement("div", {
      className: "meta-group"
    }, /*#__PURE__*/React.createElement("div", {
      className: "meta-group-head"
    }, "Compatibilidade"), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Disponibilidade"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, /*#__PURE__*/React.createElement("strong", null, "N\xE3o se aplica"))), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Requer"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, window.missingCapsLabel(_compat.missing))), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Banco ativo"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, banco.short))))), /*#__PURE__*/React.createElement(window.ViewNotApplicable, {
      viewMeta: _vm,
      banco: banco,
      missing: _compat.missing,
      supporters: supporters,
      onPickBanco: id => {
        if (setDatabase) setDatabase(id);
      }
    }));
  }

  // ---- Em breve placeholder for non-live bancos -----------------------
  if (isSoon) {
    const bm = window.bancoMeta(database);
    return /*#__PURE__*/React.createElement("div", {
      className: "screen"
    }, /*#__PURE__*/React.createElement("div", {
      className: "page-hero"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "overline"
    }, banco.short, " \xB7 ", bm.domain), /*#__PURE__*/React.createElement("h1", {
      className: "page-title"
    }, VIEW_LABEL[view]), /*#__PURE__*/React.createElement("p", {
      className: "page-sub"
    }, banco.sub)), /*#__PURE__*/React.createElement("div", {
      className: "hero-meta"
    }, /*#__PURE__*/React.createElement("div", {
      className: "meta-group"
    }, /*#__PURE__*/React.createElement("div", {
      className: "meta-group-head"
    }, "Status do banco"), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Maturidade"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val",
      style: {
        display: 'flex',
        justifyContent: 'flex-end'
      }
    }, /*#__PURE__*/React.createElement(window.MaturityTag, {
      banco: banco,
      size: "sm"
    }))), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Uso"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val",
      style: {
        display: 'flex',
        justifyContent: 'flex-end'
      }
    }, /*#__PURE__*/React.createElement(window.UsageTag, {
      active: true
    }))), bm.maturityDate && /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Previs\xE3o"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val tnum"
    }, bm.maturityDate)), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Tabela Gold"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, /*#__PURE__*/React.createElement("code", null, window.bancoTable(database)))), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Fonte"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, bm.source))))), /*#__PURE__*/React.createElement(window.ViewComingSoon, {
      banco: banco,
      view: view
    }));
  }

  // ---- Provenance + selection block (live banco) ----
  const prov = BANCO_PROV[database];

  // ---- Perspective not applicable to this banco (capability mismatch) --
  // Distinct from 'soon': even when built, this view won't apply here.
  // (The actual not-applicable gating already ran above via _compat; here we
  // only need the view meta to detect a built-but-'soon' perspective.)
  const viewMeta = window.viewById ? window.viewById(view) : null;

  // ---- Perspective not yet built (banco live, view 'soon') ------------
  if (viewMeta && viewMeta.status === 'soon') {
    return /*#__PURE__*/React.createElement("div", {
      className: "screen"
    }, /*#__PURE__*/React.createElement("div", {
      className: "page-hero"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "overline"
    }, BANCO_LABEL[database], " \xB7 ", viewMeta.group?.label), /*#__PURE__*/React.createElement("h1", {
      className: "page-title"
    }, viewMeta.label), /*#__PURE__*/React.createElement("p", {
      className: "page-sub"
    }, BANCO_SUB[database])), /*#__PURE__*/React.createElement("div", {
      className: "hero-meta"
    }, /*#__PURE__*/React.createElement("div", {
      className: "meta-group"
    }, /*#__PURE__*/React.createElement("div", {
      className: "meta-group-head"
    }, "Status da perspectiva"), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Disponibilidade"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, /*#__PURE__*/React.createElement("strong", null, "Em breve"))), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Categoria"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, viewMeta.group?.label)), /*#__PURE__*/React.createElement("div", {
      className: "meta-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "meta-label"
    }, "Banco ativo"), /*#__PURE__*/React.createElement("span", {
      className: "meta-val"
    }, prov.source))))), /*#__PURE__*/React.createElement(window.ViewPerspectiveSoon, {
      viewMeta: viewMeta
    }));
  }

  // Derive selection effects from the SAME filter engine the views use,
  // so the hero counters reflect EVERY active dimension (products, value,
  // period, UF, quality) — not just products × value.
  const _f = window.applyFilters ? window.applyFilters(filters || {}, database) : null;
  const _shares = _f && _f._shares || {};
  // UFs that survive the state filter AND still carry production.
  const ufsCovered = _f ? _f.ufData.filter(u => u.value > 0).length : (window.UF_DATA || []).filter(u => u.value > 0).length;
  // Years inside the active period window.
  const yearsCovered = _f ? _f.ts.length : prov.yearsTotal;
  // Approximate selection counts from current filters. basket == null means
  // "no filter" (all); an explicit (possibly empty) basket counts literally —
  // zero selected products must read 0, never fall back to the total.
  const productsSelected = basket == null ? prov.productsTotal : basket.length;
  const rowsAfter = Math.round(prov.totalRows * (_shares.productShare ?? 1) * (_shares.valueShare ?? 1) * (_shares.yearShare ?? 1) * (_shares.flagShare ?? 1) * (_shares.stateShare ?? 1));
  const fmtRows = window.fmtRows; // shared compact mi/mil counter (data.js)
  const rowsTotalLabel = fmtRows(prov.totalRows);
  const rowsAfterLabel = fmtRows(rowsAfter);

  // ---- Data views ----
  const ViewComponent = window.viewComponent(view) || window.ViewOverview;
  return /*#__PURE__*/React.createElement("div", {
    className: "screen"
  }, /*#__PURE__*/React.createElement(window.MaturityBanner, {
    banco: banco
  }), /*#__PURE__*/React.createElement("div", {
    className: "page-hero"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "overline"
  }, "Pesquisa hist\xF3rica \xB7 ", BANCO_LABEL[database]), /*#__PURE__*/React.createElement("h1", {
    className: "page-title"
  }, VIEW_LABEL[view]), /*#__PURE__*/React.createElement("p", {
    className: "page-sub"
  }, BANCO_SUB[database], " \xB7 s\xE9ries hist\xF3ricas para an\xE1lise da evolu\xE7\xE3o temporal de produ\xE7\xE3o e explora\xE7\xE3o de cada commodity.")), /*#__PURE__*/React.createElement("div", {
    className: "hero-meta"
  }, /*#__PURE__*/React.createElement("div", {
    className: "meta-group"
  }, /*#__PURE__*/React.createElement("div", {
    className: "meta-group-head"
  }, "Proveni\xEAncia"), /*#__PURE__*/React.createElement("div", {
    className: "meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Banco"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val"
  }, prov.source, " \xB7 ", /*#__PURE__*/React.createElement("code", null, prov.table))), /*#__PURE__*/React.createElement("div", {
    className: "meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Status"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val",
    style: {
      display: 'flex',
      gap: '6px',
      alignItems: 'center',
      justifyContent: 'flex-end'
    }
  }, /*#__PURE__*/React.createElement(window.MaturityTag, {
    banco: banco,
    size: "sm"
  }), /*#__PURE__*/React.createElement(window.UsageTag, {
    active: true
  }))), /*#__PURE__*/React.createElement("div", {
    className: "meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "\xDAltima safra"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, prov.lastCrop, " ", /*#__PURE__*/React.createElement("small", null, "\xB7 ", prov.lastCropDate))), /*#__PURE__*/React.createElement("div", {
    className: "meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Refresh Gold"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, prov.refresh))), /*#__PURE__*/React.createElement("div", {
    className: "meta-group"
  }, /*#__PURE__*/React.createElement("div", {
    className: "meta-group-head"
  }, "Sele\xE7\xE3o ativa"), /*#__PURE__*/React.createElement("div", {
    className: "meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Linhas"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, /*#__PURE__*/React.createElement("strong", null, rowsAfterLabel), " ", /*#__PURE__*/React.createElement("small", null, "de ", rowsTotalLabel))), /*#__PURE__*/React.createElement("div", {
    className: "meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Produtos"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, productsSelected, " / ", prov.productsTotal)), /*#__PURE__*/React.createElement("div", {
    className: "meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "UFs cobertas"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, ufsCovered, " / ", prov.ufsTotal)), /*#__PURE__*/React.createElement("div", {
    className: "meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Anos cobertos"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, yearsCovered, " / ", prov.yearsTotal))))), /*#__PURE__*/React.createElement(ViewComponent, {
    families: families,
    summary: filters,
    database: database,
    conventions: conventions || window.DEFAULT_CONVENTIONS
  }));
}
Object.assign(window, {
  MainScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "MainScreen.jsx", error: String((e && e.message) || e) }); }

// MetricConventions.jsx
try { (() => {
// MetricConventions — display-time metric configuration strip.
// Sits BELOW the active-filter chips, ABOVE the dashboard views.
//
// Filters reduce *which rows* enter the visualization.
// Conventions decide *how those rows are displayed*: which currency,
// whether values are nominal or inflation-adjusted, and which units
// are used for mass / volume readouts.
//
// Controlled component:
//   <MetricConventions value={...} onChange={fn(next)} />
// where value is:
//   { currency: 'BRL'|'USD'|'EUR'|'CNY',
//     correction: 'Nominal'|'IPCA'|'IGP-M'|'IGP-DI',
//     units: { mass: 't', volume: 'm³', … }  // display unit per family }

function MetricConventions({
  value,
  onChange,
  families
}) {
  const set = patch => onChange({
    ...value,
    ...patch
  });

  // Physical-unit groups are REGISTRY-DRIVEN: one group per family present
  // in the data (familiesInBasket). Mass/volume keep their dedicated conv
  // fields for back-compat; any other family stores its unit in value.units.
  const physFams = (families && families.length ? families : ['mass', 'volume']).filter(f => window.UNIT_FAMILIES[f]);
  const unitFor = fid => value.units && value.units[fid] || window.defaultUnitOf(fid);
  const setUnitFor = (fid, id) => set({
    units: {
      ...(value.units || {}),
      [fid]: id
    }
  });
  const Group = ({
    label,
    options,
    active,
    onPick,
    mono
  }) => /*#__PURE__*/React.createElement("div", {
    className: "mc-group"
  }, /*#__PURE__*/React.createElement("span", {
    className: "mc-label"
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "seg"
  }, options.map(o => /*#__PURE__*/React.createElement("button", {
    key: o.id,
    type: "button",
    className: 'seg-opt ' + (active === o.id ? 'on' : ''),
    onClick: () => onPick(o.id)
  }, /*#__PURE__*/React.createElement("span", {
    className: mono ? 'tnum' : ''
  }, o.id), o.sub && /*#__PURE__*/React.createElement("small", null, o.sub)))));
  return /*#__PURE__*/React.createElement("div", {
    className: "mc-bar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "mc-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "mc-overline"
  }, "Conven\xE7\xF5es m\xE9tricas"), /*#__PURE__*/React.createElement("span", {
    className: "mc-caption"
  }, "Como os valores e quantidades s\xE3o exibidos \u2014 n\xE3o altera quais linhas entram na visualiza\xE7\xE3o."), /*#__PURE__*/React.createElement("label", {
    className: "mc-check",
    title: "Reescala automaticamente entre mil/mi/bi para evitar n\xFAmeros longos"
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: !!value.autoScale,
    onChange: e => set({
      autoScale: e.target.checked
    })
  }), /*#__PURE__*/React.createElement("span", null, "Auto-escala (mil/mi/bi)"))), /*#__PURE__*/React.createElement("div", {
    className: "mc-groups"
  }, /*#__PURE__*/React.createElement(Group, {
    label: "Moeda",
    mono: true,
    options: [{
      id: 'BRL',
      sub: 'R$'
    }, {
      id: 'USD',
      sub: 'US$'
    }, {
      id: 'EUR',
      sub: '€'
    }, {
      id: 'CNY',
      sub: '¥'
    }],
    active: value.currency,
    onPick: id => set({
      currency: id
    })
  }), /*#__PURE__*/React.createElement(Group, {
    label: "Corre\xE7\xE3o monet\xE1ria",
    options: [{
      id: 'Nominal',
      sub: 'sem corr.'
    }, {
      id: 'IPCA',
      sub: 'IBGE'
    }, {
      id: 'IGP-M',
      sub: 'FGV'
    }, {
      id: 'IGP-DI',
      sub: 'FGV'
    }],
    active: value.correction,
    onPick: id => set({
      correction: id
    })
  }), physFams.map(fid => {
    const fam = window.UNIT_FAMILIES[fid];
    return /*#__PURE__*/React.createElement(Group, {
      key: fid,
      label: fam.label,
      mono: true,
      options: (fam.units || []).map(u => ({
        id: u.id,
        sub: u.long
      })),
      active: unitFor(fid),
      onPick: id => setUnitFor(fid, id)
    });
  })));
}

// Helpers — exported on window for use by views ----------------------

window.DEFAULT_CONVENTIONS = {
  currency: 'BRL',
  correction: 'IPCA',
  units: {
    mass: 't',
    volume: 'm³'
  },
  autoScale: false
};
// Display unit chosen for a family (falls back to the registry default).
window.unitOf = (conv, fam) => conv && conv.units && conv.units[fam] || window.defaultUnitOf(fam);

// Auto-scale helper — picks a (factor, suffix) so the number sits in a
// readable magnitude. Used only when conv.autoScale === true.
window.autoScaleNum = v => {
  const a = Math.abs(v);
  if (a >= 1e9) return {
    factor: 1e9,
    suffix: 'bi'
  };
  if (a >= 1e6) return {
    factor: 1e6,
    suffix: 'mi'
  };
  if (a >= 1e3) return {
    factor: 1e3,
    suffix: 'mil'
  };
  return {
    factor: 1,
    suffix: ''
  };
};
function _fmtRescaled(v, conv, unitSuffix) {
  if (conv.autoScale) {
    const {
      factor,
      suffix
    } = window.autoScaleNum(v);
    const scaled = v / factor;
    const txt = scaled.toLocaleString('pt-BR', {
      maximumFractionDigits: scaled < 10 ? 2 : scaled < 100 ? 1 : 0
    });
    return suffix ? `${txt} ${suffix} ${unitSuffix}`.trim() : `${txt} ${unitSuffix}`.trim();
  }
  return v.toLocaleString('pt-BR', {
    maximumFractionDigits: 0
  }) + ' ' + unitSuffix;
}

// Currency conversion factors vs. BRL (illustrative · last-year rates)
window.CURRENCY_FX = {
  BRL: {
    rate: 1,
    symbol: 'R$',
    long: 'Real'
  },
  USD: {
    rate: 0.205,
    symbol: 'US$',
    long: 'Dólar'
  },
  EUR: {
    rate: 0.187,
    symbol: '€',
    long: 'Euro'
  },
  CNY: {
    rate: 1.490,
    symbol: '¥',
    long: 'Yuan'
  }
};

// Mock nominal-deflation factor: when Nominal correction is picked we
// scale the *real* values down to a plausible "as-paid-then" figure.
// Real pipeline: real = nominal × cumulative_inflation; reversing here.
window.CORRECTION_FACTOR = {
  IPCA: 1.00,
  'IGP-M': 1.06,
  'IGP-DI': 1.04,
  Nominal: 0.22 // illustrative — shrinks 2024 real values back to ~nominal
};

// Multiplicative display factor for a *value* (correction factor × display FX
// rate). Stored values are BRL-CANONICAL: PEVS/SEFAZ are already in R$, and
// the COMEX/Comtrade snapshots store BRL-EQUIVALENT figures (USD ÷ USD-rate,
// see previewData.js) on purpose — so this single BRL-based factor renders the
// real US$ amounts once changeDatabase defaults their display currency to USD.
// Every manual value-scaling site (views building chart series by hand) MUST
// use this so they agree with applyConv / formatValue.
window.convFactor = conv => {
  const fx = (window.CURRENCY_FX[conv.currency] || {
    rate: 1
  }).rate;
  const cf = window.CORRECTION_FACTOR[conv.correction] ?? 1;
  return cf * fx;
};

// Convert a BRL-canonical value through the active currency + correction.
window.applyConv = (val, conv) => {
  if (val == null) return null;
  return val * window.convFactor(conv);
};

// Format a BRL-canonical value through the active convention.
// Auto-scale (mil/mi/bi) only when conv.autoScale === true.
window.formatValue = (brl, conv) => {
  if (brl == null) return '—';
  const sym = window.CURRENCY_FX[conv.currency].symbol;
  const v = window.applyConv(brl, conv);
  if (conv.autoScale) {
    const {
      factor,
      suffix
    } = window.autoScaleNum(v);
    const scaled = v / factor;
    const txt = scaled.toLocaleString('pt-BR', {
      maximumFractionDigits: scaled < 10 ? 2 : scaled < 100 ? 1 : 0
    });
    return suffix ? `${sym} ${txt} ${suffix}` : `${sym} ${txt}`;
  }
  return sym + ' ' + v.toLocaleString('pt-BR', {
    maximumFractionDigits: 0
  });
};

// Axis label — when auto-scale is ON, append the picked suffix for the
// passed reference magnitude; otherwise just the currency symbol.
window.valueAxisLabel = (conv, refMagnitude) => {
  const sym = window.CURRENCY_FX[conv.currency].symbol;
  if (conv.autoScale && refMagnitude != null) {
    const {
      suffix
    } = window.autoScaleNum(refMagnitude);
    return suffix ? `${sym} ${suffix}` : sym;
  }
  return sym;
};

// Convert a series {y, v: value in banco base currency} to displayed currency.
window.convertSeries = (series, conv, key = 'v') => {
  const factor = window.convFactor(conv);
  return series.map(d => ({
    ...d,
    [key]: d[key] * factor
  }));
};

// Mass / volume: native data is in t (mass) and m³ (volume) at internal scale.
// OVERVIEW_TS.q_mass holds *thousands of tonnes*; PRODUCT_TS.q (mass) same.
// OVERVIEW_TS.q_vol holds *millions of m³*; PRODUCT_TS.q (volume) same.
//
// Display rule (per user request): never auto-rescale to abbreviated units.
// The user picks t or kg → we render in t or kg. Same for m³ vs L.

window.formatMassQty = (milT, conv) => {
  if (milT == null) return '—';
  const v = milT * window.massQtyMul(conv);
  return _fmtRescaled(v, conv, window.unitOf(conv, 'mass'));
};
window.formatVolumeQty = (miM3, conv) => {
  if (miM3 == null) return '—';
  const v = miM3 * window.volumeQtyMul(conv);
  return _fmtRescaled(v, conv, window.unitOf(conv, 'volume'));
};

// Multipliers: internal dataset units (mil t / mi m³) → selected display
// unit, via the registry factors so any member unit (kg/t/@/sc, L/m³/hL…)
// converts correctly. internal mass = mil t (×1000 t); internal vol = mi m³.
window.massQtyMul = conv => 1000 / window.unitToBase('mass', window.unitOf(conv, 'mass'));
window.volumeQtyMul = conv => 1e6 / window.unitToBase('volume', window.unitOf(conv, 'volume'));
window.massAxisLabel = conv => window.unitOf(conv, 'mass');
window.volumeAxisLabel = conv => window.unitOf(conv, 'volume');

// Human label for the active monetary convention (e.g. "USD · IPCA").
window.conventionMonetaryLabel = conv => conv.currency + (conv.correction === 'Nominal' ? ' · nominal' : ' · ' + conv.correction);

// scaleSeries — rescales a series + returns the matching axis label.
// When conv.autoScale is OFF, returns the data as-is and unitSuffix only.
// When ON, divides every value by autoScale(refMagnitude).factor and
// builds the label respecting unit grammar:
//   currency → "R$ bi"  (symbol before suffix)
//   physical → "bi t"   (suffix before unit)
window.scaleSeries = (series, refMag, conv, valueKey, unitSuffix) => {
  if (!conv.autoScale) {
    return {
      data: series,
      label: unitSuffix
    };
  }
  const {
    factor,
    suffix
  } = window.autoScaleNum(refMag);
  if (!suffix) return {
    data: series,
    label: unitSuffix
  };
  const data = series.map(d => ({
    ...d,
    [valueKey]: d[valueKey] / factor
  }));
  // Currency symbols sit BEFORE the magnitude suffix ("R$ bi"),
  // physical units sit AFTER ("bi t").
  const CURRENCY_SYMS = ['R$', 'US$', '€', '¥'];
  const label = CURRENCY_SYMS.includes(unitSuffix) ? `${unitSuffix} ${suffix}` : `${suffix} ${unitSuffix}`.trim();
  return {
    data,
    label
  };
};
window.MetricConventions = MetricConventions;
})(); } catch (e) { __ds_ns.__errors.push({ path: "MetricConventions.jsx", error: String((e && e.message) || e) }); }

// Sparkline.jsx
try { (() => {
// Sparkline + KpiCardSpark — small KPI primitives shared by the data views.
// Extracted from the original MainScreen so all <ViewX> files can use them.

function Sparkline({
  data,
  color = 'var(--viz-1)',
  valueKey = 'v',
  width = 120,
  height = 32
}) {
  const ys = data.map(d => d[valueKey]);
  const min = Math.min(...ys),
    max = Math.max(...ys);
  const span = max - min || 1;
  const x = i => i / (data.length - 1) * (width - 2) + 1;
  const y = v => height - 2 - (v - min) / span * (height - 4);
  const pts = data.map((d, i) => `${x(i)},${y(d[valueKey])}`).join(' ');
  const area = `1,${height - 1} ${pts} ${width - 1},${height - 1}`;
  const last = data[data.length - 1];
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${width} ${height}`,
    width: width,
    height: height,
    style: {
      display: 'block'
    }
  }, /*#__PURE__*/React.createElement("polygon", {
    points: area,
    fill: color,
    opacity: "0.10"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: pts,
    fill: "none",
    stroke: color,
    strokeWidth: "1.5",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: x(data.length - 1),
    cy: y(last[valueKey]),
    r: "2.2",
    fill: color
  }));
}
function KpiCardSpark({
  label,
  value,
  sub,
  delta,
  deltaPositive,
  spark,
  sparkColor,
  sparkKey = 'v'
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "kpi-card spark"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-top"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-ov"
  }, label), spark && /*#__PURE__*/React.createElement(Sparkline, {
    data: spark,
    color: sparkColor,
    valueKey: sparkKey
  })), /*#__PURE__*/React.createElement("div", {
    className: "kpi-val tnum"
  }, value), /*#__PURE__*/React.createElement("div", {
    className: "kpi-sub"
  }, delta != null && /*#__PURE__*/React.createElement("span", {
    className: 'kpi-delta ' + (deltaPositive ? 'up' : 'down')
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: deltaPositive ? 'arrow_upward' : 'arrow_downward',
    size: 12
  }), delta), /*#__PURE__*/React.createElement("span", null, sub)));
}
Object.assign(window, {
  Sparkline,
  KpiCardSpark
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "Sparkline.jsx", error: String((e && e.message) || e) }); }

// Status.jsx
try { (() => {
// Status.jsx — shared indicators for the TWO banco status axes:
//   • maturity (dataset lifecycle) — build-time readiness, from the registry
//     window.MATURITY (bancos.js). Frontend only displays it.
//   • usage status — ativo/inativo, derived from the active selection.
// All components read the registry so adding/retuning a stage = one edit there.

// ── Maturity tag: colored dot + label. ─────────────────────────────
function MaturityTag({
  banco,
  status,
  size,
  withIcon
}) {
  const m = status ? window.MATURITY[status] || window.MATURITY.planejado : window.maturityMeta(banco);
  return /*#__PURE__*/React.createElement("span", {
    className: 'mat-tag mat-' + m.id + (size === 'sm' ? ' sm' : ''),
    title: m.desc
  }, /*#__PURE__*/React.createElement("span", {
    className: "mat-tag-dot",
    style: {
      background: m.color
    }
  }), m.label);
}

// ── Usage dot: filled = ativo (feeds the current view), hollow = inativo. ─
function UsageDot({
  active
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: 'use-dot ' + (active ? 'on' : 'off'),
    title: active ? 'Ativo · fonte dos dados em tela' : 'Inativo',
    "aria-label": active ? 'Ativo' : 'Inativo'
  });
}

// ── Usage tag: explicit ativo/inativo pill (hero / about). ──────────────
function UsageTag({
  active
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: 'use-tag ' + (active ? 'on' : 'off')
  }, /*#__PURE__*/React.createElement("span", {
    className: 'use-dot ' + (active ? 'on' : 'off')
  }), active ? 'Ativo' : 'Inativo');
}

// ── Caveat banner shown atop data views for beta / manutencao /
//    descontinuado (the caveat:true stages). ─────────────────────────
function MaturityBanner({
  banco
}) {
  if (!banco) return null;
  const m = window.maturityMeta(banco);
  if (!m.caveat) return null;
  const FALLBACK = {
    beta: 'Cobertura ainda parcial — alguns períodos podem não estar completos e os valores podem mudar.',
    manutencao: 'Correção/atualização em andamento — alguns valores podem mudar.',
    descontinuado: 'Banco descontinuado e sem manutenção — será removido em breve. Exporte o que precisar.'
  };
  const fallback = FALLBACK[m.id] || m.desc;
  return /*#__PURE__*/React.createElement("div", {
    className: 'mat-banner mat-banner-' + m.id,
    style: {
      '--st-color': m.color
    },
    role: "status"
  }, /*#__PURE__*/React.createElement("span", {
    className: "mat-banner-dot",
    style: {
      background: m.color
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "mat-banner-body"
  }, /*#__PURE__*/React.createElement("strong", null, m.label, "."), ' ', /*#__PURE__*/React.createElement("span", null, banco.maturityNote || fallback), banco.maturityDate ? /*#__PURE__*/React.createElement("span", {
    className: "mat-banner-date tnum"
  }, " \xB7 ", banco.maturityDate) : null));
}

// ── Legend documenting every maturity stage (window.MATURITY). ─────────
function MaturityLegend({
  compact
}) {
  const rows = Object.values(window.MATURITY).sort((a, b) => a.order - b.order);
  return /*#__PURE__*/React.createElement("div", {
    className: 'mat-legend' + (compact ? ' compact' : '')
  }, rows.map(m => /*#__PURE__*/React.createElement("div", {
    key: m.id,
    className: "mat-legend-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: 'mat-tag mat-' + m.id
  }, /*#__PURE__*/React.createElement("span", {
    className: "mat-tag-dot",
    style: {
      background: m.color
    }
  }), m.label), /*#__PURE__*/React.createElement("span", {
    className: "mat-legend-desc"
  }, m.desc))));
}
Object.assign(window, {
  MaturityTag,
  UsageDot,
  UsageTag,
  MaturityBanner,
  MaturityLegend
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "Status.jsx", error: String((e && e.message) || e) }); }

// UnitFamily.jsx
try { (() => {
// UnitFamily — surfaces the active unit families (mass/volume) for the current
// basket so the researcher never accidentally compares incompatible quantities.

function UnitFamilyBanner({
  families
}) {
  const F = window.UNIT_FAMILIES;
  // Nothing selected → no quantity families → no banner (zero means none).
  if (!families || families.length === 0) return null;
  const mixed = families.length > 1;
  if (!mixed) {
    const f = F[families[0]];
    return /*#__PURE__*/React.createElement("div", {
      className: "ufam-banner single"
    }, /*#__PURE__*/React.createElement("span", {
      className: "ufam-dot",
      style: {
        background: 'var(--embrapa-green)'
      }
    }), /*#__PURE__*/React.createElement("span", {
      className: "ufam-label"
    }, "Fam\xEDlia de unidades"), /*#__PURE__*/React.createElement("strong", null, f.label, " \xB7 ", f.unit), /*#__PURE__*/React.createElement("span", {
      className: "ufam-note"
    }, "Todos os produtos da cesta s\xE3o medidos em ", f.long, "; quantidades s\xE3o som\xE1veis."));
  }
  return /*#__PURE__*/React.createElement("div", {
    className: "ufam-banner mixed"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ufam-dot warn"
  }), /*#__PURE__*/React.createElement("span", {
    className: "ufam-label"
  }, "Cesta mista"), /*#__PURE__*/React.createElement("strong", null, families.map(id => `${F[id].label} (${F[id].unit})`).join(' + ')), /*#__PURE__*/React.createElement("span", {
    className: "ufam-note"
  }, "Quantidades de fam\xEDlias diferentes ", /*#__PURE__*/React.createElement("u", null, "n\xE3o"), " s\xE3o agregadas: cada m\xE9trica de quantidade aparece separada por fam\xEDlia e unidade. Valor monet\xE1rio permanece agreg\xE1vel e som\xE1vel."));
}

// Tag for inline use inside chart titles / KPI labels.
// When `conv` is provided, the displayed unit reflects the active
// metric-conventions selection (kg/t for mass · L/m³ for volume).
function UnitFamilyTag({
  family,
  conv
}) {
  const f = window.UNIT_FAMILIES[family];
  const unit = !conv ? f.unit : conv.units && conv.units[family] || f.unit;
  return /*#__PURE__*/React.createElement("span", {
    className: "ufam-tag",
    style: {
      color: f.color || 'var(--fg-2)'
    }
  }, f.label, " \xB7 ", unit);
}
Object.assign(window, {
  UnitFamilyBanner,
  UnitFamilyTag
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "UnitFamily.jsx", error: String((e && e.message) || e) }); }

// ViewAbout.jsx
try { (() => {
// ViewAbout — institutional "Sobre o dashboard" page.
// Pure structured content: purpose, datasets, perspectives, pipeline,
// usage tips, credits. No insights, no live data — just what the
// dashboard is and how to use it.

function ViewAbout() {
  const bancos = window.visibleBancos ? window.visibleBancos() : window.BANCOS || [];
  const livePev = window.bancoById ? window.bancoById('ibge_pevs') : null;
  const yearStart = livePev?.prov?.yearStart || 1986;

  // Perspectives derived from the single registry (views.js · VIEW_GROUPS) so
  // this page never goes stale when a view is added/removed. The glossary is a
  // reference tool (not an analytical perspective), so it stays out of this
  // list — but its group still counts toward the categories.
  const VIEWS = (window.VIEW_GROUPS || []).flatMap(g => g.views.map(v => ({
    id: v.id,
    title: v.label,
    desc: v.desc,
    group: g.label
  }))).filter(v => v.id !== 'glossary' && v.desc);
  const viewGroupCount = (window.VIEW_GROUPS || []).length;

  // Gold table names derived from the banco registry (bancos.js), rather than
  // repeated in the pipeline text.
  const goldTables = bancos.map(b => window.bancoTable(b.id)).join(', ');

  // App version is config; the date follows the snapshot refresh (bancos.js).
  const APP_VERSION = 'v0.4.2';
  const refreshDate = (livePev?.prov?.refresh || '').split(' · ')[0] || '—';
  const PIPELINE = [{
    stage: 'Bronze',
    hint: 'Raw',
    desc: 'Ingestão direta das fontes oficiais sem transformação: tabelas SIDRA, arquivos do COMEX, downloads UN Comtrade, extrações SEFAZ. Auditoria por hash de arquivo e timestamp de ingestão.'
  }, {
    stage: 'Silver',
    hint: 'Conformed',
    desc: 'Normalização de esquemas, conciliação de códigos (NCM ↔ SH6, IBGE ↔ TOM/SIAFI), reconstrução de séries históricas e marcação da dimensão data_quality_flag.'
  }, {
    stage: 'Gold',
    hint: 'Analytics',
    desc: `Tabelas desnormalizadas e enriquecidas por banco (${goldTables}). Convenções monetárias e cobertura temporal aplicadas. Fonte direta do dashboard.`
  }];
  const TIPS = [{
    title: 'Filtros não são iguais a convenções métricas',
    desc: 'Filtros reduzem quais linhas entram na visualização (produtos, período, UFs e municípios, flags, faixa de valor). Convenções métricas decidem como essas linhas são exibidas (moeda, correção monetária, unidade de massa e volume). Os dois são independentes.'
  }, {
    title: 'Famílias de unidades nunca se misturam',
    desc: 'Quantidades em massa (t/kg) e em volume (m³/L) jamais são somadas. Quando a cesta selecionada contém produtos de famílias diferentes, o dashboard mostra uma métrica de quantidade por família. Valor monetário (BRL) permanece agregável.'
  }, {
    title: 'Citação e compartilhamento',
    desc: 'Use “Citar painel” no canto superior direito para gerar uma referência ABNT do estado atual (banco, perspectiva, recorte e convenções). “Compartilhar” copia uma URL que reproduz toda a seleção atual.'
  }, {
    title: 'Exportação',
    desc: 'O botão “Exportar CSV”, ao lado de “Editar filtros”, baixa a fatia atual de dados — com todos os filtros aplicados, na resolução máxima disponível na tabela Gold.'
  }];
  const CREDITS = [{
    role: 'Coordenação científica',
    who: 'Embrapa — Empresa Brasileira de Pesquisa Agropecuária'
  }, {
    role: 'Vinculação institucional',
    who: 'Ministério da Agricultura e Pecuária · Governo Federal'
  }, {
    role: 'Fontes de dados',
    who: 'IBGE · MDIC SECEX · UN Statistics Division · SEFAZ estaduais'
  }, {
    role: 'Engenharia de dados',
    who: 'Pipeline Medalhão sobre BigQuery — ingestão, conformação e enriquecimento'
  }, {
    role: 'Apresentação',
    who: 'Dashboard interativo HTML + visualizações SVG próprias'
  }];
  return /*#__PURE__*/React.createElement("div", {
    className: "ab-stack"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card ab-purpose"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Prop\xF3sito",
    title: "An\xE1lise hist\xF3rica de commodities brasileiras"
  }), /*#__PURE__*/React.createElement("p", {
    className: "ab-lead"
  }, "Esta \xE9 uma ferramenta cient\xEDfica desenvolvida pela ", /*#__PURE__*/React.createElement("strong", null, "Embrapa"), " para permitir que pesquisadores acompanhem a evolu\xE7\xE3o temporal da produ\xE7\xE3o, explora\xE7\xE3o, comercializa\xE7\xE3o e exporta\xE7\xE3o de commodities brasileiras. O foco \xE9 exclusivamente anal\xEDtico \u2014 n\xE3o h\xE1 recomenda\xE7\xF5es automatizadas, proje\xE7\xF5es ou opini\xF5es. Todos os n\xFAmeros vis\xEDveis v\xEAm diretamente das tabelas Gold do pipeline."), /*#__PURE__*/React.createElement("p", {
    className: "ab-lead"
  }, "O recorte temporal dispon\xEDvel depende da fonte: a base IBGE PEVS cobre desde ", /*#__PURE__*/React.createElement("strong", null, yearStart), "; com\xE9rcio exterior (MDIC, UN Comtrade) j\xE1 est\xE1 dispon\xEDvel com cobertura pr\xF3pria, e o com\xE9rcio interno (SEFAZ) ser\xE1 liberado em seguida.")), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Bancos de dados",
    title: "O que voc\xEA encontra aqui",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, bancos.length, " bancos \xB7 ", bancos.filter(b => b.status === 'live').length, " dispon\xEDvel(is)")
  }), /*#__PURE__*/React.createElement("div", {
    className: "ab-banco-grid"
  }, bancos.map(b => {
    const bm = window.bancoMeta(b.id);
    return /*#__PURE__*/React.createElement("div", {
      key: b.id,
      className: 'ab-banco mat-' + b.maturity
    }, /*#__PURE__*/React.createElement("div", {
      className: "ab-banco-head"
    }, /*#__PURE__*/React.createElement("span", {
      className: "ab-banco-short"
    }, b.short), /*#__PURE__*/React.createElement(window.MaturityTag, {
      banco: b
    })), /*#__PURE__*/React.createElement("div", {
      className: "ab-banco-domain"
    }, bm.domain), /*#__PURE__*/React.createElement("p", {
      className: "ab-banco-sub"
    }, b.sub), /*#__PURE__*/React.createElement("dl", {
      className: "ab-banco-meta"
    }, /*#__PURE__*/React.createElement("dt", null, "Granularidade"), /*#__PURE__*/React.createElement("dd", null, bm.scope), /*#__PURE__*/React.createElement("dt", null, "Fonte"), /*#__PURE__*/React.createElement("dd", null, bm.source), /*#__PURE__*/React.createElement("dt", null, "Tabela"), /*#__PURE__*/React.createElement("dd", null, /*#__PURE__*/React.createElement("code", null, bm.table)), bm.maturityDate && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dt", null, "Conclus\xE3o prevista"), /*#__PURE__*/React.createElement("dd", {
      className: "tnum"
    }, bm.maturityDate))));
  })), /*#__PURE__*/React.createElement("div", {
    className: "ab-mat-legend"
  }, /*#__PURE__*/React.createElement("div", {
    className: "ab-mat-legend-head"
  }, "Maturidade dos bancos"), /*#__PURE__*/React.createElement(window.MaturityLegend, null))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Perspectivas anal\xEDticas",
    title: `${VIEWS.length} perspectivas em ${viewGroupCount} categorias`
  }), /*#__PURE__*/React.createElement("div", {
    className: "ab-view-grid"
  }, VIEWS.map((v, i) => /*#__PURE__*/React.createElement("div", {
    key: v.id,
    className: "ab-view"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ab-view-num tnum"
  }, String(i + 1).padStart(2, '0')), /*#__PURE__*/React.createElement("h3", {
    className: "ab-view-title"
  }, v.title, /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 400,
      color: 'var(--fg-3)'
    }
  }, " \xB7 ", v.group)), /*#__PURE__*/React.createElement("p", {
    className: "ab-view-desc"
  }, v.desc))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Como os dados s\xE3o processados",
    title: "Arquitetura Medalh\xE3o \xB7 Bronze \u2192 Silver \u2192 Gold"
  }), /*#__PURE__*/React.createElement("div", {
    className: "ab-pipeline"
  }, PIPELINE.map((s, i) => /*#__PURE__*/React.createElement(React.Fragment, {
    key: s.stage
  }, /*#__PURE__*/React.createElement("div", {
    className: 'ab-stage ab-stage-' + s.stage.toLowerCase()
  }, /*#__PURE__*/React.createElement("div", {
    className: "ab-stage-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ab-stage-name"
  }, s.stage), /*#__PURE__*/React.createElement("span", {
    className: "ab-stage-hint"
  }, s.hint)), /*#__PURE__*/React.createElement("p", {
    className: "ab-stage-desc"
  }, s.desc)), i < PIPELINE.length - 1 && /*#__PURE__*/React.createElement("div", {
    className: "ab-stage-arrow",
    "aria-hidden": "true"
  }, "\u2192"))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Como usar",
    title: "Conven\xE7\xF5es importantes antes de interpretar"
  }), /*#__PURE__*/React.createElement("div", {
    className: "ab-tips"
  }, TIPS.map((t, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "ab-tip"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "ab-tip-title"
  }, t.title), /*#__PURE__*/React.createElement("p", {
    className: "ab-tip-desc"
  }, t.desc))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Cr\xE9ditos e proveni\xEAncia",
    title: "Quem mant\xE9m o dashboard"
  }), /*#__PURE__*/React.createElement("dl", {
    className: "ab-credits"
  }, CREDITS.map((c, i) => /*#__PURE__*/React.createElement(React.Fragment, {
    key: i
  }, /*#__PURE__*/React.createElement("dt", null, c.role), /*#__PURE__*/React.createElement("dd", null, c.who)))), /*#__PURE__*/React.createElement("div", {
    className: "ab-version"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Vers\xE3o"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, APP_VERSION, " \xB7 ", refreshDate)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Contato t\xE9cnico"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val"
  }, "igor.lopes@embrapa.br")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Licen\xE7a dos dados"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val"
  }, "Atribui\xE7\xE3o obrigat\xF3ria (Embrapa + fonte original)")))));
}
window.ViewAbout = ViewAbout;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewAbout.jsx", error: String((e && e.message) || e) }); }

// ViewComingSoon.jsx
try { (() => {
// ViewComingSoon — structured placeholder shown when the active banco
// (selected in the sidebar) is not yet wired to the backend.
// Renders the planned schema + scope so the researcher knows what to
// expect when the dataset goes live, instead of an empty dashboard.

function ViewComingSoon({
  banco,
  view
}) {
  if (!banco) return null;
  const bm = window.bancoMeta ? window.bancoMeta(banco.id) : banco; // provenance via backend seam
  const captionTxt = banco.maturity === 'planejado' ? 'sem prazo definido' : 'previsão · ' + (bm.maturityDate || '—');
  return /*#__PURE__*/React.createElement("div", {
    className: "cs-stack"
  }, /*#__PURE__*/React.createElement("div", {
    className: "cs-hero"
  }, /*#__PURE__*/React.createElement("div", {
    className: "cs-hero-l"
  }, /*#__PURE__*/React.createElement("div", {
    className: "cs-eyebrow"
  }, /*#__PURE__*/React.createElement(window.MaturityTag, {
    banco: banco
  }), /*#__PURE__*/React.createElement("span", {
    className: "caption"
  }, captionTxt)), /*#__PURE__*/React.createElement("h2", {
    className: "cs-title"
  }, banco.label), /*#__PURE__*/React.createElement("p", {
    className: "cs-sub"
  }, banco.sub)), /*#__PURE__*/React.createElement("div", {
    className: "cs-hero-r"
  }, /*#__PURE__*/React.createElement("div", {
    className: "cs-meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Dom\xEDnio"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val"
  }, bm.domain)), /*#__PURE__*/React.createElement("div", {
    className: "cs-meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Granularidade"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val"
  }, bm.scope)), /*#__PURE__*/React.createElement("div", {
    className: "cs-meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Fonte"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val"
  }, bm.source)), /*#__PURE__*/React.createElement("div", {
    className: "cs-meta-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Tabela Gold"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val"
  }, /*#__PURE__*/React.createElement("code", null, window.bancoTable(banco.id)))))), /*#__PURE__*/React.createElement("div", {
    className: "grid-2 cs-grid"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Esquema planejado",
    title: "Colunas que o banco vai expor",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, banco.plannedScope?.length || 0, " colunas")
  }), /*#__PURE__*/React.createElement("div", {
    className: "cs-cols"
  }, (banco.plannedScope || []).map((c, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "cs-col-row"
  }, /*#__PURE__*/React.createElement("code", {
    className: "cs-col-name"
  }, c.col), /*#__PURE__*/React.createElement("p", {
    className: "cs-col-desc"
  }, c.desc))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Cobertura prevista",
    title: "O que esperar quando o banco for liberado"
  }), /*#__PURE__*/React.createElement("dl", {
    className: "cs-cov"
  }, bm.cobertura?.years && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dt", null, "Cobertura temporal"), /*#__PURE__*/React.createElement("dd", null, bm.cobertura.years)), bm.cobertura?.atualizacao && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dt", null, "Cad\xEAncia de atualiza\xE7\xE3o"), /*#__PURE__*/React.createElement("dd", null, bm.cobertura.atualizacao)), bm.cobertura?.granularidade && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dt", null, "Granularidade da Gold"), /*#__PURE__*/React.createElement("dd", {
    className: "mono"
  }, bm.cobertura.granularidade)), bm.cobertura?.restricoes && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dt", null, "Restri\xE7\xF5es"), /*#__PURE__*/React.createElement("dd", null, bm.cobertura.restricoes))), /*#__PURE__*/React.createElement("div", {
    className: "cs-note"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "info",
    size: 14
  }), /*#__PURE__*/React.createElement("span", null, "Esta perspectiva (", /*#__PURE__*/React.createElement("strong", null, labelOf(view)), ") ser\xE1 habilitada automaticamente assim que o backend expor a tabela ", /*#__PURE__*/React.createElement("code", null, window.bancoTable(banco.id)), ". Os componentes de visualiza\xE7\xE3o j\xE1 existem e ser\xE3o reaproveitados.")))));
}

// Resolve the perspective label from the single source of truth (views.js),
// so every registered view — not just a hardcoded subset — shows its proper
// name when a soon banco renders this placeholder.
function labelOf(view) {
  return window.viewLabel && window.viewLabel(view) || view;
}
window.ViewComingSoon = ViewComingSoon;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewComingSoon.jsx", error: String((e && e.message) || e) }); }

// ViewConcentration.jsx
try { (() => {
// ViewConcentration — how concentrated production is, geographically
// and by product. Lorenz curve + Gini + HHI. Applies to any banco
// (requires no special capability). Honours active filters.
//
// Gini: 0 = perfectly even, 1 = all in one unit.
// HHI:  sum of squared percentage shares (0–10000). >2500 = highly
//       concentrated (US DoJ convention).

function ViewConcentration({
  summary,
  conventions,
  database
}) {
  const conv = conventions || window.DEFAULT_CONVENTIONS;
  const filtered = window.applyFilters(summary || {}, database);
  const hasGeo = filtered.ufDataFull.length > 0;

  // ── Geographic distribution (by UF) ─────────────────────────────────
  const ufValues = filtered.ufData.map(u => u.value).filter(v => v > 0);
  const ufSorted = filtered.ufData.slice().filter(u => u.value > 0).sort((a, b) => b.value - a.value);

  // ── Product distribution (latest year, by product) ──────────────────
  const prodValues = Object.entries(filtered.productTS).map(([code, s]) => {
    const last = s[s.length - 1];
    return {
      code,
      name: (filtered.products.find(p => p.code === code) || {}).name || code,
      value: last ? last.v : 0
    };
  }).filter(p => p.value > 0).sort((a, b) => b.value - a.value);

  // ── Metrics ──────────────────────────────────────────────────────────
  const gini = vals => {
    const s = vals.slice().filter(v => v > 0).sort((a, b) => a - b);
    const n = s.length;
    if (n < 2) return 0;
    const total = s.reduce((a, b) => a + b, 0);
    if (!total) return 0;
    let cum = 0;
    s.forEach((v, i) => {
      cum += (i + 1) * v;
    });
    return 2 * cum / (n * total) - (n + 1) / n;
  };
  const hhi = vals => {
    const total = vals.reduce((a, b) => a + b, 0);
    if (!total) return 0;
    return vals.reduce((s, v) => s + Math.pow(v / total * 100, 2), 0);
  };
  const topNShare = (sorted, n) => {
    const total = sorted.reduce((s, x) => s + x.value, 0) || 1;
    return sorted.slice(0, n).reduce((s, x) => s + x.value, 0) / total;
  };
  const ufGini = gini(ufValues);
  const ufHHI = hhi(ufValues);
  const prodGini = gini(prodValues.map(p => p.value));
  const prodHHI = hhi(prodValues.map(p => p.value));
  const top5UF = topNShare(ufSorted, 5);
  const top3Prod = topNShare(prodValues, 3);
  const hhiBand = h => h > 2500 ? {
    label: 'alta concentração',
    color: 'var(--err)'
  } : h > 1500 ? {
    label: 'concentração moderada',
    color: 'var(--warn)'
  } : {
    label: 'baixa concentração',
    color: 'var(--ok)'
  };
  const giniBand = g => g > 0.6 ? {
    label: 'muito desigual',
    color: 'var(--err)'
  } : g > 0.4 ? {
    label: 'desigual',
    color: 'var(--warn)'
  } : {
    label: 'relativamente uniforme',
    color: 'var(--ok)'
  };

  // Gini/Lorenz need ≥2 units to mean anything. With a single product/UF the
  // formula degenerates to 0 ("relativamente uniforme"), which contradicts the
  // HHI reading (max concentration). Surface "n/d" instead of a false reading.
  const giniInfo = (count, g) => count < 2 ? {
    value: 'n/d',
    label: count === 1 ? 'unidade única' : 'sem dados',
    color: 'var(--fg-4)'
  } : {
    value: g.toFixed(2).replace('.', ','),
    ...giniBand(g)
  };
  const ufG = giniInfo(ufValues.length, ufGini);
  const prodG = giniInfo(prodValues.length, prodGini);
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, hasGeo ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Gini \xB7 geogr\xE1fico (UF)",
    value: ufG.value,
    sub: ufG.label
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "HHI \xB7 geogr\xE1fico (UF)",
    value: Math.round(ufHHI).toLocaleString('pt-BR'),
    sub: hhiBand(ufHHI).label
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Concentra\xE7\xE3o top-5 UFs",
    value: window.fmtPct(top5UF),
    sub: `de ${ufSorted.length} ${ufSorted.length === 1 ? 'UF' : 'UFs'} com produção`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Concentra\xE7\xE3o top-3 produtos",
    value: window.fmtPct(top3Prod),
    sub: `de ${prodValues.length} ${prodValues.length === 1 ? 'produto' : 'produtos'} na cesta`
  })) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Gini \xB7 por produto",
    value: prodG.value,
    sub: prodG.label
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "HHI \xB7 por produto",
    value: Math.round(prodHHI).toLocaleString('pt-BR'),
    sub: hhiBand(prodHHI).label
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Concentra\xE7\xE3o top-3 produtos",
    value: window.fmtPct(top3Prod),
    sub: `de ${prodValues.length} ${prodValues.length === 1 ? 'produto' : 'produtos'} na cesta`
  }))), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, hasGeo && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Curva de Lorenz · geográfica · ${filtered.yearEnd}`,
    title: `Desigualdade entre UFs · Gini ${ufG.value}`,
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption",
      style: {
        color: ufG.color
      }
    }, ufG.label)
  }), /*#__PURE__*/React.createElement(window.LorenzCurve, {
    values: ufValues,
    color: "var(--viz-2)",
    xLabel: "UFs",
    yLabel: "valor",
    height: 300
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Curva de Lorenz · por produto · ${filtered.yearEnd}`,
    title: `Desigualdade entre produtos · Gini ${prodG.value}`,
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption",
      style: {
        color: prodG.color
      }
    }, prodG.label)
  }), /*#__PURE__*/React.createElement(window.LorenzCurve, {
    values: prodValues.map(p => p.value),
    color: "var(--viz-5)",
    xLabel: "produtos",
    yLabel: "valor",
    height: 300
  }))), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, hasGeo && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Participação acumulada · UFs · ${filtered.yearEnd}`,
    title: "Quem concentra a produ\xE7\xE3o"
  }), /*#__PURE__*/React.createElement("div", {
    className: "conc-list"
  }, (() => {
    const total = ufSorted.reduce((s, u) => s + u.value, 0) || 1;
    let acc = 0;
    return ufSorted.slice(0, 10).map((u, i) => {
      const share = u.value / total;
      acc += share;
      return /*#__PURE__*/React.createElement("div", {
        key: u.uf,
        className: "conc-row"
      }, /*#__PURE__*/React.createElement("span", {
        className: "conc-rank tnum"
      }, "#", i + 1), /*#__PURE__*/React.createElement("span", {
        className: "conc-name"
      }, u.uf, " \xB7 ", u.name), /*#__PURE__*/React.createElement("div", {
        className: "conc-bar"
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          width: (share * 100).toFixed(1) + '%',
          background: 'var(--viz-2)'
        }
      })), /*#__PURE__*/React.createElement("span", {
        className: "conc-share tnum"
      }, window.fmtPct(share)), /*#__PURE__*/React.createElement("span", {
        className: "conc-acc tnum"
      }, window.fmtPct(acc)));
    });
  })(), /*#__PURE__*/React.createElement("div", {
    className: "conc-head-note"
  }, /*#__PURE__*/React.createElement("span", null), /*#__PURE__*/React.createElement("span", null), /*#__PURE__*/React.createElement("span", null), /*#__PURE__*/React.createElement("span", {
    className: "caption"
  }, "indiv."), /*#__PURE__*/React.createElement("span", {
    className: "caption"
  }, "acum.")))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "\xCDndice Herfindahl-Hirschman (HHI)",
    title: "Leitura da concentra\xE7\xE3o"
  }), /*#__PURE__*/React.createElement("div", {
    className: "conc-hhi"
  }, hasGeo && /*#__PURE__*/React.createElement("div", {
    className: "conc-hhi-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "conc-hhi-label"
  }, "Geogr\xE1fico (UF)"), /*#__PURE__*/React.createElement("div", {
    className: "conc-hhi-track"
  }, /*#__PURE__*/React.createElement("div", {
    className: "conc-hhi-fill",
    style: {
      width: Math.min(100, ufHHI / 10000 * 100) + '%',
      background: hhiBand(ufHHI).color
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "conc-hhi-mark",
    style: {
      left: '15%'
    },
    title: "1500"
  }), /*#__PURE__*/React.createElement("span", {
    className: "conc-hhi-mark",
    style: {
      left: '25%'
    },
    title: "2500"
  })), /*#__PURE__*/React.createElement("span", {
    className: "conc-hhi-val tnum"
  }, Math.round(ufHHI).toLocaleString('pt-BR'))), /*#__PURE__*/React.createElement("div", {
    className: "conc-hhi-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "conc-hhi-label"
  }, "Por produto"), /*#__PURE__*/React.createElement("div", {
    className: "conc-hhi-track"
  }, /*#__PURE__*/React.createElement("div", {
    className: "conc-hhi-fill",
    style: {
      width: Math.min(100, prodHHI / 10000 * 100) + '%',
      background: hhiBand(prodHHI).color
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "conc-hhi-mark",
    style: {
      left: '15%'
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "conc-hhi-mark",
    style: {
      left: '25%'
    }
  })), /*#__PURE__*/React.createElement("span", {
    className: "conc-hhi-val tnum"
  }, Math.round(prodHHI).toLocaleString('pt-BR'))), /*#__PURE__*/React.createElement("dl", {
    className: "conc-scale"
  }, /*#__PURE__*/React.createElement("dt", null, /*#__PURE__*/React.createElement("span", {
    className: "conc-dot",
    style: {
      background: 'var(--ok)'
    }
  }), "< 1500"), /*#__PURE__*/React.createElement("dd", null, "baixa concentra\xE7\xE3o"), /*#__PURE__*/React.createElement("dt", null, /*#__PURE__*/React.createElement("span", {
    className: "conc-dot",
    style: {
      background: 'var(--warn)'
    }
  }), "1500\u20132500"), /*#__PURE__*/React.createElement("dd", null, "concentra\xE7\xE3o moderada"), /*#__PURE__*/React.createElement("dt", null, /*#__PURE__*/React.createElement("span", {
    className: "conc-dot",
    style: {
      background: 'var(--err)'
    }
  }), "> 2500"), /*#__PURE__*/React.createElement("dd", null, "alta concentra\xE7\xE3o")), /*#__PURE__*/React.createElement("p", {
    className: "caption conc-note"
  }, "HHI = soma dos quadrados das participa\xE7\xF5es percentuais. As marcas no trilho indicam os limiares 1500 e 2500 (conven\xE7\xE3o US DoJ).")))));
}
window.ViewConcentration = ViewConcentration;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewConcentration.jsx", error: String((e && e.message) || e) }); }

// ViewCrossSource.jsx
try { (() => {
// ViewCrossSource — the "Cruzamento entre fontes" perspective.
// Compares 2–4 annual series drawn from DIFFERENT bancos on a shared time
// axis. All data flows through window.crossSeries (crossSource.js); this
// component only orchestrates selection, the visualization toggle and the
// derived analytics. Controlled via { value, onChange } so the selection
// travels in the shared URL / citation (see Dashboard.html + AppShell).

const {
  useMemo: useCSMemo
} = React;

// Default landing selection — the flagship cross-source question:
// IBGE annual production value × MDIC annual export value.
window.DEFAULT_CROSS_STATE = {
  series: [{
    b: 'ibge_pevs',
    m: 'prod_value'
  }, {
    b: 'mdic_comex',
    m: 'exp_value'
  }],
  mode: 'base100',
  // 'base100' | 'dual' | 'panels'
  y0: null,
  // null → use the common comparable window
  y1: null
};
const CS_COLORS = ['var(--viz-1)', 'var(--viz-3)', 'var(--viz-9)', 'var(--viz-10)'];
const CS_MAX = 4;
function ViewCrossSource({
  value,
  onChange
}) {
  const cs = value || window.DEFAULT_CROSS_STATE;
  const set = patch => onChange && onChange({
    ...cs,
    ...patch
  });
  const refs = cs.series || [];
  const refKey = r => r.b + ':' + r.m;
  const selectedKeys = refs.map(refKey);

  // Common comparable window (intersection of coverages) + union bounds.
  const common = window.crossCommonWindow(refs.map(r => ({
    banco: r.b,
    metric: r.m
  })));
  const clamp = y => Math.min(common.y1, Math.max(common.y0, y));
  const effY0 = clamp(cs.y0 || common.y0);
  const effY1 = clamp(cs.y1 || common.y1);
  const yearOpts = [];
  for (let y = common.y0; y <= common.y1; y++) yearOpts.push(y);

  // Resolve each selected ref to an aligned series within the window.
  const seriesResults = refs.map((r, i) => {
    const s = window.crossSeries(r.b, r.m, {
      y0: effY0,
      y1: effY1
    });
    if (!s) return null;
    return {
      ...s,
      color: CS_COLORS[i % CS_COLORS.length],
      bancoShort: s.bancoMeta.short
    };
  }).filter(Boolean);
  const anyPreview = seriesResults.some(s => s.preview);
  const firstPreviewBanco = (seriesResults.find(s => s.preview) || {}).bancoMeta || null;
  const units = [...new Set(seriesResults.map(s => s.unit))];
  const families = [...new Set(seriesResults.map(s => s.family))];

  // ── Toggle a (banco, metric) ref in/out of the selection ──────────────
  const toggleRef = (b, m) => {
    const k = b + ':' + m;
    const exists = selectedKeys.includes(k);
    let next;
    if (exists) {
      if (refs.length <= 1) return; // keep at least one series
      next = refs.filter(r => refKey(r) !== k);
    } else {
      if (refs.length >= CS_MAX) return; // cap at 4
      next = [...refs, {
        b,
        m
      }];
    }
    // New selection ⇒ let the window recompute from the new overlap.
    set({
      series: next,
      y0: null,
      y1: null
    });
  };

  // ── Per-series metrics (variação acumulada, CAGR) ─────────────────────
  const items = seriesResults.map(s => {
    const pts = s.points;
    const v0 = pts[0]?.v || 0,
      vT = pts[pts.length - 1]?.v || 0;
    return {
      ...s,
      v0,
      vT,
      cagr: window.cagrPct(v0, vT, pts.length - 1),
      accum: window.accumPct(v0, vT)
    };
  });

  // ── Pairwise correlation on YoY growth (shared helpers · seriesUtils.js) ─
  const growths = items.map(it => window.seriesGrowth(it.points));
  const corr = items.map((_, i) => items.map((_, j) => window.pearson(growths[i], growths[j])));
  const corrColor = window.corrColor;

  // ── Ratio panel: only when exactly 2 series share an identical unit ───
  const ratioEligible = items.length === 2 && items[0].unit === items[1].unit;
  const ratioSeries = ratioEligible ? items[0].points.map((d, i) => ({
    y: d.y,
    v: (items[1].points[i]?.v || 0) / (d.v || 1) * 100
  })) : null;
  const ratioMean = ratioSeries && ratioSeries.length ? ratioSeries.reduce((s, d) => s + d.v, 0) / ratioSeries.length : 0;

  // ── Chart series in the shape each chart expects ──────────────────────
  const base100 = items.map(it => ({
    name: `${it.label} · ${it.bancoShort}`,
    color: it.color,
    data: it.points.map(d => ({
      y: d.y,
      v: it.v0 ? d.v / it.v0 * 100 : 0
    }))
  }));
  const axisSeries = items.map(it => ({
    label: it.label,
    color: it.color,
    unit: it.unit,
    bancoShort: it.bancoShort,
    data: it.points
  }));
  const MODES = [{
    id: 'base100',
    label: 'Base 100'
  }, {
    id: 'dual',
    label: 'Eixo duplo'
  }, {
    id: 'panels',
    label: 'Painéis'
  }];
  const mode = cs.mode || 'base100';
  const dualTooManyUnits = mode === 'dual' && units.length > 2;
  const fmtV = (v, unit) => v == null ? '—' : v.toLocaleString('pt-BR', {
    maximumFractionDigits: v < 10 ? 2 : v < 1000 ? 1 : 0
  }) + ' ' + unit;
  return /*#__PURE__*/React.createElement(React.Fragment, null, anyPreview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: firstPreviewBanco,
    capabilityNote: "S\xE9ries de bancos ainda n\xE3o liberados entram como demonstra\xE7\xE3o."
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "S\xE9ries comparadas",
    value: `${items.length} / ${CS_MAX}`,
    sub: `de ${new Set(items.map(i => i.banco)).size} ${new Set(items.map(i => i.banco)).size === 1 ? 'banco' : 'bancos'}`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Janela compar\xE1vel",
    value: `${effY0}–${effY1}`,
    sub: `fontes cobrem ${common.union[0]}–${common.union[1]}`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Fam\xEDlias de unidade",
    value: families.length,
    sub: families.map(f => window.METRIC_FAMILIES[f]?.label || f).join(' · ')
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: ratioEligible ? 'Razão média (par)' : 'Correlação (par principal)',
    value: ratioEligible ? ratioMean.toFixed(1).replace('.', ',') + '%' : items.length >= 2 ? corr[0][1].toFixed(2).replace('.', ',') : '—',
    sub: ratioEligible ? `${items[1].label} ÷ ${items[0].label}` : 'variação interanual'
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Montagem do cruzamento",
    title: "Selecione as s\xE9ries a comparar",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, items.length, " de ", CS_MAX, " \xB7 m\xEDn. 1")
  }), /*#__PURE__*/React.createElement("div", {
    className: "xs-picker"
  }, (window.visibleBancos ? window.visibleBancos() : window.BANCOS || []).map(b => /*#__PURE__*/React.createElement("div", {
    key: b.id,
    className: "xs-bank"
  }, /*#__PURE__*/React.createElement("div", {
    className: "xs-bank-head"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "database",
    size: 14
  }), /*#__PURE__*/React.createElement("span", {
    className: "xs-bank-short"
  }, b.short), b.status === 'soon' && /*#__PURE__*/React.createElement("span", {
    className: "xs-bank-tag"
  }, window.bancoAvailability(b))), /*#__PURE__*/React.createElement("div", {
    className: "xs-bank-metrics"
  }, (b.metrics || []).map(m => {
    const k = b.id + ':' + m.id;
    const on = selectedKeys.includes(k);
    const idx = selectedKeys.indexOf(k);
    const atCap = !on && refs.length >= CS_MAX;
    return /*#__PURE__*/React.createElement("button", {
      key: k,
      className: 'xs-chip' + (on ? ' on' : '') + (atCap ? ' disabled' : ''),
      onClick: () => !atCap && toggleRef(b.id, m.id),
      style: on ? {
        background: CS_COLORS[idx % CS_COLORS.length],
        borderColor: CS_COLORS[idx % CS_COLORS.length],
        color: '#fff'
      } : null,
      title: `${m.agg} · ${window.METRIC_FAMILIES[m.family]?.label || m.family}`
    }, /*#__PURE__*/React.createElement("span", {
      className: "xs-chip-label"
    }, m.label), /*#__PURE__*/React.createElement("span", {
      className: "xs-chip-unit tnum"
    }, window.crossSeries(b.id, m.id, {})?.unit || m.unit));
  })))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Sobreposi\xE7\xE3o no tempo",
    title: "Evolu\xE7\xE3o hist\xF3rica comparada",
    action: /*#__PURE__*/React.createElement("div", {
      className: "xs-controls"
    }, /*#__PURE__*/React.createElement("div", {
      className: "xs-years"
    }, /*#__PURE__*/React.createElement("select", {
      className: "xs-select",
      value: effY0,
      onChange: e => set({
        y0: Math.min(Number(e.target.value), effY1)
      })
    }, yearOpts.filter(y => y <= effY1).map(y => /*#__PURE__*/React.createElement("option", {
      key: y,
      value: y
    }, y))), /*#__PURE__*/React.createElement("span", {
      className: "xs-years-sep"
    }, "\u2192"), /*#__PURE__*/React.createElement("select", {
      className: "xs-select",
      value: effY1,
      onChange: e => set({
        y1: Math.max(Number(e.target.value), effY0)
      })
    }, yearOpts.filter(y => y >= effY0).map(y => /*#__PURE__*/React.createElement("option", {
      key: y,
      value: y
    }, y)))), /*#__PURE__*/React.createElement("div", {
      className: "seg xs-seg"
    }, MODES.map(o => /*#__PURE__*/React.createElement("button", {
      key: o.id,
      className: 'seg-opt ' + (mode === o.id ? 'on' : ''),
      onClick: () => set({
        mode: o.id
      })
    }, o.label))))
  }), /*#__PURE__*/React.createElement("div", {
    className: "xs-mode-note"
  }, mode === 'base100' && /*#__PURE__*/React.createElement(React.Fragment, null, "Cada s\xE9rie reindexada a ", /*#__PURE__*/React.createElement("strong", null, "100 em ", effY0), " \u2014 compara trajet\xF3rias independentemente da unidade (", units.join(' · '), ")."), mode === 'dual' && !dualTooManyUnits && /*#__PURE__*/React.createElement(React.Fragment, null, "Cada unidade no seu pr\xF3prio eixo: ", /*#__PURE__*/React.createElement("strong", null, units[0]), " \xE0 esquerda", units[1] ? /*#__PURE__*/React.createElement(React.Fragment, null, " \xB7 ", /*#__PURE__*/React.createElement("strong", null, units[1]), " \xE0 direita") : '', ". Escalas independentes \u2014 compare formato, n\xE3o n\xEDvel."), mode === 'dual' && dualTooManyUnits && /*#__PURE__*/React.createElement(React.Fragment, null, "Eixo duplo comporta 2 unidades; a sele\xE7\xE3o tem ", units.length, " (", units.join(' · '), "). Use ", /*#__PURE__*/React.createElement("strong", null, "Base 100"), " ou ", /*#__PURE__*/React.createElement("strong", null, "Pain\xE9is"), " para ver todas com fidelidade."), mode === 'panels' && /*#__PURE__*/React.createElement(React.Fragment, null, "Um painel por s\xE9rie, alinhados no eixo de tempo \u2014 leitura fiel das unidades nativas, sem for\xE7ar escala comum.")), mode === 'base100' && /*#__PURE__*/React.createElement(window.MultiLineChart, {
    series: base100,
    label: `índice (${effY0}=100)`,
    valueKey: "v",
    height: 320
  }), mode === 'dual' && /*#__PURE__*/React.createElement(window.DualAxisLineChart, {
    series: axisSeries,
    height: 320
  }), mode === 'panels' && /*#__PURE__*/React.createElement(window.StackedPanels, {
    series: axisSeries
  }), /*#__PURE__*/React.createElement("div", {
    className: "xs-legend"
  }, items.map(it => /*#__PURE__*/React.createElement("span", {
    key: it.key,
    className: "xs-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "xs-legend-dot",
    style: {
      background: it.color
    }
  }), /*#__PURE__*/React.createElement("strong", null, it.label), /*#__PURE__*/React.createElement("span", {
    className: "xs-legend-src"
  }, it.bancoShort, " \xB7 ", it.unit, it.preview ? ' · prévia' : ''))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Métricas comparativas · ${effY0}–${effY1}`,
    title: "Crescimento de cada s\xE9rie na janela"
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-table-wrap"
  }, /*#__PURE__*/React.createElement("table", {
    className: "pc-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "S\xE9rie"), /*#__PURE__*/React.createElement("th", null, "Fonte"), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, effY0), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, effY1), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "Varia\xE7\xE3o acumulada"), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "CAGR (a.a.)"))), /*#__PURE__*/React.createElement("tbody", null, items.map(it => /*#__PURE__*/React.createElement("tr", {
    key: it.key
  }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("span", {
    className: "pc-row-dot",
    style: {
      background: it.color
    }
  }), it.label), /*#__PURE__*/React.createElement("td", null, it.bancoShort, it.preview ? /*#__PURE__*/React.createElement("span", {
    className: "xs-tbl-preview"
  }, "pr\xE9via") : ''), /*#__PURE__*/React.createElement("td", {
    className: "num tnum"
  }, fmtV(it.v0, it.unit)), /*#__PURE__*/React.createElement("td", {
    className: "num tnum"
  }, fmtV(it.vT, it.unit)), /*#__PURE__*/React.createElement("td", {
    className: "num tnum",
    style: {
      color: it.accum >= 0 ? 'var(--ok)' : 'var(--err)'
    }
  }, window.fmtSigned(it.accum, 0)), /*#__PURE__*/React.createElement("td", {
    className: "num tnum",
    style: {
      color: it.cagr >= 0 ? 'var(--ok)' : 'var(--err)'
    }
  }, window.fmtSigned(it.cagr, 1)))))))), ratioEligible && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Raz\xE3o entre s\xE9ries",
    title: `${items[1].label} como % de ${items[0].label}`,
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "m\xE9dia ", ratioMean.toFixed(1).replace('.', ','), "%")
  }), /*#__PURE__*/React.createElement(window.MultiLineChart, {
    series: [{
      name: 'razão (%)',
      color: 'var(--embrapa-blue)',
      data: ratioSeries
    }],
    label: "%",
    valueKey: "v",
    height: 240
  }), /*#__PURE__*/React.createElement("p", {
    className: "caption xs-ratio-note"
  }, "Ambas as s\xE9ries est\xE3o em ", /*#__PURE__*/React.createElement("strong", null, items[0].unit), ", ent\xE3o a raz\xE3o \xE9 direta. Quando uma fonte \xE9 produ\xE7\xE3o e a outra exporta\xE7\xE3o, esta curva \xE9 o", /*#__PURE__*/React.createElement("strong", null, " coeficiente de exporta\xE7\xE3o"), " \u2014 quanto do produzido seguiu para fora.")), items.length >= 2 && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Correla\xE7\xE3o cruzada \xB7 varia\xE7\xE3o interanual",
    title: "Qu\xE3o sincronizadas s\xE3o as fontes",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "Pearson \xB7 \u22121 a +1")
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-corr-wrap"
  }, /*#__PURE__*/React.createElement("table", {
    className: "pc-corr"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null), items.map(it => /*#__PURE__*/React.createElement("th", {
    key: it.key,
    title: `${it.label} · ${it.bancoShort}`
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-corr-dot",
    style: {
      background: it.color
    }
  }), it.bancoShort)))), /*#__PURE__*/React.createElement("tbody", null, items.map((rowIt, i) => /*#__PURE__*/React.createElement("tr", {
    key: rowIt.key
  }, /*#__PURE__*/React.createElement("th", {
    title: `${rowIt.label} · ${rowIt.bancoShort}`
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-corr-dot",
    style: {
      background: rowIt.color
    }
  }), rowIt.label), items.map((colIt, j) => {
    const r = corr[i][j];
    return /*#__PURE__*/React.createElement("td", {
      key: colIt.key,
      className: "tnum",
      style: {
        background: i === j ? 'var(--bg-surface-2)' : corrColor(r),
        color: Math.abs(r) > 0.6 ? '#fff' : 'var(--fg-1)'
      }
    }, i === j ? '—' : r.toFixed(2).replace('.', ','));
  }))))), /*#__PURE__*/React.createElement("p", {
    className: "caption pc-corr-note"
  }, "Verde: fontes que sobem e descem juntas no mesmo ano. Vermelho: movimentos opostos."))));
}
window.ViewCrossSource = ViewCrossSource;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewCrossSource.jsx", error: String((e && e.message) || e) }); }

// ViewCuratedAnalyses.jsx
try { (() => {
// ViewCuratedAnalyses.jsx — analyses POWERED BY the enrichment layer. They
// subscribe to the store, so editing the Curadoria re-renders them live.
//   · ViewValueAdded   — exports split by industrialization (bruta × processada)
//   · ViewMarketNature — trade value by curated economic purpose (consumo × processamento)
// Both render synthetic preview until the trade bancos are live.

const {
  useState: useCaState,
  useEffect: useCaEffect
} = React;
function useEnrichmentTick() {
  const [, force] = useCaState(0);
  useCaEffect(() => window.enrichment.subscribe(() => force(n => n + 1)), []);
}
const caNum = window.numBR,
  caPct = window.pctBR;

// ── Value added: bruta × processada ───────────────────────────────────
function ViewValueAdded() {
  useEnrichmentTick();
  const [group, setGroup] = useCaState(null);
  const data = window.valueAddedAnalysis(group);
  const banco = window.bancoById('mdic_comex');
  const last = data.series[data.series.length - 1];
  const first = data.series[0];
  const areaSeries = [{
    name: 'Bruta',
    color: 'var(--viz-3)',
    data: data.byLevel.bruta
  }, {
    name: 'Processada',
    color: 'var(--viz-2)',
    data: data.byLevel.processada
  }];
  const shareTs = data.series.map(d => ({
    y: d.y,
    v: d.procShare
  }));
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "Exporta\xE7\xE3o por c\xF3digo entra como demonstra\xE7\xE3o at\xE9 o MDIC ser ligado; a classifica\xE7\xE3o bruta/processada vem da Curadoria e pode ser editada l\xE1."
  }), /*#__PURE__*/React.createElement("div", {
    className: "pp-selector"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pp-selector-label"
  }, "Commodity"), /*#__PURE__*/React.createElement("div", {
    className: "pp-chips"
  }, /*#__PURE__*/React.createElement("button", {
    className: 'pp-chip ' + (!group ? 'on' : ''),
    onClick: () => setGroup(null),
    style: !group ? {
      background: 'var(--embrapa-green)',
      borderColor: 'var(--embrapa-green)',
      color: '#fff'
    } : null
  }, "Todas curadas"), window.ENRICH_GROUPS.map(g => {
    const on = group === g.id;
    return /*#__PURE__*/React.createElement("button", {
      key: g.id,
      className: 'pp-chip ' + (on ? 'on' : ''),
      onClick: () => setGroup(g.id),
      style: on ? {
        background: 'var(--embrapa-green)',
        borderColor: 'var(--embrapa-green)',
        color: '#fff'
      } : null
    }, g.label);
  }))), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Exporta\xE7\xE3o processada",
    value: caPct(last?.procShare),
    sub: `${last?.y} · do valor exportado`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Varia\xE7\xE3o na janela",
    value: window.fmtSigned((last?.procShare || 0) - (first?.procShare || 0), 1, ' p.p.'),
    deltaPositive: (last?.procShare || 0) >= (first?.procShare || 0),
    sub: `${first?.y}–${last?.y}`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Pr\xEAmio do processado",
    value: '×' + caNum(last?.premium, 1),
    sub: "pre\xE7o processada \xF7 bruta"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "C\xF3digos na an\xE1lise",
    value: data.nCodes,
    sub: "inclu\xEDdos e classificados"
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Valor exportado por n\xEDvel \xB7 US$ bi",
    title: "Quanto sai bruto e quanto sai processado",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "classifica\xE7\xE3o da Curadoria")
  }), data.nCodes < 1 ? /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '24px 4px',
      textAlign: 'center'
    }
  }, "Nenhum c\xF3digo bruto/processado inclu\xEDdo para esta sele\xE7\xE3o. Ajuste em ", /*#__PURE__*/React.createElement("strong", null, "Curadoria"), ".") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.StackedArea, {
    series: areaSeries,
    valueKey: "v",
    label: "US$ bi",
    height: 300
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-legend"
  }, areaSeries.map(s => /*#__PURE__*/React.createElement("span", {
    key: s.name,
    className: "pc-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-legend-dot",
    style: {
      background: s.color
    }
  }), s.name))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Participa\xE7\xE3o do processado no tempo",
    title: "A pauta est\xE1 agregando mais valor?",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "% \xB7 valor processado \xF7 total")
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: shareTs,
    valueKey: "v",
    label: "% processado",
    color: "var(--viz-2)",
    height: 240
  }), /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '8px 4px 0'
    }
  }, "Reclassifique um c\xF3digo entre ", /*#__PURE__*/React.createElement("strong", null, "bruta"), " e ", /*#__PURE__*/React.createElement("strong", null, "processada"), " na Curadoria e esta an\xE1lise se atualiza \u2014 \xE9 o conhecimento do pesquisador entrando no dado.")));
}

// ── Economic purpose: consume × process ───────────────────────────────
function ViewMarketNature() {
  useEnrichmentTick();
  const data = window.marketNatureAnalysis();
  const banco = window.bancoById('mdic_comex');
  const L = data.latest;
  const total = window.ENRICH_MARKETS.reduce((s, m) => s + (L[m.id] || 0), 0) || 1;
  const areaSeries = window.ENRICH_MARKETS.map(m => ({
    name: m.short,
    color: m.color,
    data: data.series.map(d => ({
      y: d.y,
      v: d[m.id]
    }))
  }));
  const donut = window.ENRICH_MARKETS.map(m => ({
    name: m.short,
    value: L[m.id],
    share: L[m.id] / total,
    color: m.color
  }));
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "Valores por fluxo entram como demonstra\xE7\xE3o at\xE9 o MDIC ser ligado; a finalidade (consumo/processamento) de cada par regime \xD7 fluxo vem da Curadoria."
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, window.ENRICH_MARKETS.map(m => /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    key: m.id,
    label: m.label,
    value: 'US$ ' + caNum(L[m.id], 1) + ' bi',
    sub: caPct(L[m.id] / total * 100) + ' do total'
  })), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Janela",
    value: `${data.series[0].y}–${L.y}`,
    sub: "cobertura compar\xE1vel"
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Valor por finalidade econ\xF4mica \xB7 US$ bi",
    title: "Comprando/vendendo para consumir ou para processar",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "classifica\xE7\xE3o da Curadoria")
  }), /*#__PURE__*/React.createElement(window.StackedArea, {
    series: areaSeries,
    valueKey: "v",
    label: "US$ bi",
    height: 300
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-legend"
  }, areaSeries.map(s => /*#__PURE__*/React.createElement("span", {
    key: s.name,
    className: "pc-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-legend-dot",
    style: {
      background: s.color
    }
  }), s.name)))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Composição · ${L.y}`,
    title: "Quanto vai para consumo vs. processamento"
  }), /*#__PURE__*/React.createElement(window.Donut, {
    data: donut,
    valueKey: "share",
    size: 170
  }), /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '8px 4px 0'
    }
  }, "A dire\xE7\xE3o (comprar/vender) vem do fluxo; a ", /*#__PURE__*/React.createElement("strong", null, "finalidade"), " (consumo ou processamento) vem da Curadoria. Reclassifique um par regime \xD7 fluxo e esta an\xE1lise se atualiza.")));
}
Object.assign(window, {
  ViewValueAdded,
  ViewMarketNature
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewCuratedAnalyses.jsx", error: String((e && e.message) || e) }); }

// ViewCuration.jsx
try { (() => {
// ViewCuration.jsx — the researcher CURATION surface. Two editable tables
// over the shared institutional enrichment store (enrichment.js). Edits
// persist + notify, so analyses react live. No per-row provenance in v1
// (per the brief) — just the values.

const {
  useState: useCurState,
  useEffect: useCurEffect
} = React;
function ViewCuration() {
  const [, force] = useCurState(0);
  useCurEffect(() => window.enrichment.subscribe(() => force(n => n + 1)), []);
  const [tab, setTab] = useCurState('codes');
  const [codesView, setCodesView] = useCurState('commodity');
  const [justApplied, setJustApplied] = useCurState(false);
  const committing = window.enrichment.isCommitting();
  const onApply = () => {
    window.enrichment.apply(() => {
      setJustApplied(true);
      setTimeout(() => setJustApplied(false), 2800);
    });
  };
  const stats = window.enrichment.stats();
  const pending = window.enrichment.pendingCount();
  const bancoShort = id => (window.bancoById ? window.bancoById(id)?.short : id) || id;
  const CodeRow = (c, nested) => {
    const todo = !c.level;
    return /*#__PURE__*/React.createElement("tr", {
      key: c.id,
      className: (nested ? 'cur-coderow-nested' : '') + (todo ? ' cur-coderow-todo' : '')
    }, /*#__PURE__*/React.createElement("td", null, nested ? null : /*#__PURE__*/React.createElement("span", {
      className: "cur-src"
    }, bancoShort(c.source))), /*#__PURE__*/React.createElement("td", {
      className: "tnum"
    }, c.code), /*#__PURE__*/React.createElement("td", null, c.desc, todo && /*#__PURE__*/React.createElement("span", {
      className: "cur-todo-pill"
    }, "a classificar")), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("select", {
      className: 'xs-select cur-level' + (todo ? ' cur-level-empty' : ''),
      value: c.level || '',
      onChange: e => window.enrichment.setCode(c.id, {
        level: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u2014 a classificar \u2014"), window.ENRICH_LEVELS.map(l => /*#__PURE__*/React.createElement("option", {
      key: l.id,
      value: l.id
    }, l.label)))));
  };
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "cur-note"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "info",
    size: 16
  }), /*#__PURE__*/React.createElement("span", null, "Curadoria ", /*#__PURE__*/React.createElement("strong", null, "institucional compartilhada"), ": o conhecimento adicionado aqui vale para todos os pesquisadores e alimenta as an\xE1lises curadas. A worklist \xE9 um", /*#__PURE__*/React.createElement("strong", null, " LEFT JOIN"), " entre os c\xF3digos da Gold e o log de classifica\xE7\xE3o \u2014 c\xF3digos sem classifica\xE7\xE3o aparecem como ", /*#__PURE__*/React.createElement("strong", null, "a classificar"), ". As altera\xE7\xF5es s\xF3 entram na base ao clicar em ", /*#__PURE__*/React.createElement("strong", null, "Aplicar"), ".")), /*#__PURE__*/React.createElement("div", {
    className: 'cur-apply ' + (committing ? 'committing' : pending > 0 ? 'dirty' : justApplied ? 'done' : '')
  }, /*#__PURE__*/React.createElement("span", {
    className: "cur-apply-status"
  }, committing ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: "cur-spinner"
  }), " Gravando no log de classifica\xE7\xE3o (SCD2) e refazendo o JOIN ao vivo\u2026") : pending > 0 ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: "cur-apply-dot"
  }), /*#__PURE__*/React.createElement("strong", null, pending), "\xA0", pending > 1 ? 'alterações não aplicadas' : 'alteração não aplicada', " \xE0 base") : justApplied ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.Icon, {
    name: "fact_check",
    size: 15
  }), " Aplicado \xE0 base \u2014 an\xE1lises re-sincronizadas") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.Icon, {
    name: "fact_check",
    size: 15
  }), " Curadoria aplicada \u2014 a dimens\xE3o est\xE1 em sincronia com a base")), /*#__PURE__*/React.createElement("div", {
    className: "cur-apply-actions"
  }, pending > 0 && !committing && /*#__PURE__*/React.createElement("button", {
    className: "btn-secondary",
    onClick: () => window.enrichment.discard()
  }, "Descartar"), /*#__PURE__*/React.createElement("button", {
    className: "btn-primary",
    disabled: pending === 0 || committing,
    onClick: onApply
  }, committing ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: "cur-spinner cur-spinner-btn"
  }), " Aplicando\u2026") : 'Aplicar à base'))), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "C\xF3digos na worklist",
    value: stats.codesTotal,
    sub: "Gold DISTINCT \u27D5 log"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "A classificar",
    value: stats.unclassified,
    sub: "sem linha no log (NULL)"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Bruta",
    value: stats.byLevel.bruta,
    sub: "c\xF3digos classificados"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Processada",
    value: stats.byLevel.processada,
    sub: "c\xF3digos classificados"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Pares classificados",
    value: `${stats.flowsClassified} / ${stats.flowsTotal}`,
    sub: "regime \xD7 fluxo"
  })), /*#__PURE__*/React.createElement("div", {
    className: "cur-tabs seg"
  }, /*#__PURE__*/React.createElement("button", {
    className: 'seg-opt ' + (tab === 'codes' ? 'on' : ''),
    onClick: () => setTab('codes')
  }, "C\xF3digos & industrializa\xE7\xE3o"), /*#__PURE__*/React.createElement("button", {
    className: 'seg-opt ' + (tab === 'flows' ? 'on' : ''),
    onClick: () => setTab('flows')
  }, "Aduana & finalidade econ\xF4mica")), tab === 'codes' && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "C\xF3digos entre fontes \xB7 n\xEDvel de industrializa\xE7\xE3o",
    title: "Classifique cada c\xF3digo como bruto ou processado",
    action: /*#__PURE__*/React.createElement("div", {
      className: "cur-group-by"
    }, /*#__PURE__*/React.createElement("span", {
      className: "cur-group-label"
    }, "Agrupar por"), /*#__PURE__*/React.createElement("div", {
      className: "seg cur-codes-seg"
    }, /*#__PURE__*/React.createElement("button", {
      className: 'seg-opt ' + (codesView === 'commodity' ? 'on' : ''),
      onClick: () => setCodesView('commodity')
    }, /*#__PURE__*/React.createElement(window.Icon, {
      name: "eco",
      size: 14
    }), " Commodity"), /*#__PURE__*/React.createElement("button", {
      className: 'seg-opt ' + (codesView === 'banco' ? 'on' : ''),
      onClick: () => setCodesView('banco')
    }, /*#__PURE__*/React.createElement(window.Icon, {
      name: "database",
      size: 14
    }), " Banco")))
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-table-wrap"
  }, /*#__PURE__*/React.createElement("table", {
    className: "pc-table cur-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Fonte"), /*#__PURE__*/React.createElement("th", null, "C\xF3digo"), /*#__PURE__*/React.createElement("th", null, "Descri\xE7\xE3o"), /*#__PURE__*/React.createElement("th", null, "N\xEDvel de industrializa\xE7\xE3o"))), /*#__PURE__*/React.createElement("tbody", null, codesView === 'commodity' ? window.ENRICH_GROUPS.map(g => {
    const rows = window.enrichment.codes().filter(c => c.group === g.id);
    if (!rows.length) return null;
    return /*#__PURE__*/React.createElement(React.Fragment, {
      key: g.id
    }, /*#__PURE__*/React.createElement("tr", {
      className: "cur-grouprow"
    }, /*#__PURE__*/React.createElement("td", {
      colSpan: 4
    }, g.label)), rows.map(c => CodeRow(c)));
  }) : [...new Set(window.enrichment.codes().map(c => c.source))].map(src => {
    const srcCodes = window.enrichment.codes().filter(c => c.source === src);
    const chapters = [...new Set(srcCodes.map(c => window.enrichment.chapterOf(src, c.code)))];
    return /*#__PURE__*/React.createElement(React.Fragment, {
      key: src
    }, /*#__PURE__*/React.createElement("tr", {
      className: "cur-bancorow"
    }, /*#__PURE__*/React.createElement("td", {
      colSpan: 4
    }, /*#__PURE__*/React.createElement(window.Icon, {
      name: "database",
      size: 13
    }), " ", bancoShort(src))), chapters.map(ch => /*#__PURE__*/React.createElement(React.Fragment, {
      key: src + ':' + ch
    }, /*#__PURE__*/React.createElement("tr", {
      className: "cur-chaprow"
    }, /*#__PURE__*/React.createElement("td", {
      colSpan: 4
    }, ch)), srcCodes.filter(c => window.enrichment.chapterOf(src, c.code) === ch).map(c => CodeRow(c, true)))));
  }))))), tab === 'flows' && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Par regime \xD7 fluxo \xB7 finalidade econ\xF4mica",
    title: "A finalidade depende do par regime + fluxo",
    action: /*#__PURE__*/React.createElement("span", {
      className: "cur-legend"
    }, window.ENRICH_MARKETS.map(m => /*#__PURE__*/React.createElement("span", {
      key: m.id,
      className: "cur-legend-item"
    }, /*#__PURE__*/React.createElement("span", {
      className: "cur-legend-dot",
      style: {
        background: m.color
      }
    }), m.short)))
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-table-wrap"
  }, /*#__PURE__*/React.createElement("table", {
    className: "pc-table cur-table cur-matrix"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
    className: "cur-corner"
  }, /*#__PURE__*/React.createElement("span", {
    className: "cur-corner-col"
  }, "Fluxo comercial \u2192"), /*#__PURE__*/React.createElement("span", {
    className: "cur-corner-row"
  }, "Regime aduaneiro \u2193")), window.enrichment.flowTypes().map(f => /*#__PURE__*/React.createElement("th", {
    key: f.id,
    className: "cur-c",
    title: f.label + ' — ' + f.hint
  }, /*#__PURE__*/React.createElement("span", {
    className: "cur-hashint"
  }, f.term))))), /*#__PURE__*/React.createElement("tbody", null, window.enrichment.regimes().map(r => /*#__PURE__*/React.createElement("tr", {
    key: r.id
  }, /*#__PURE__*/React.createElement("td", {
    title: r.label + ' — ' + r.hint
  }, /*#__PURE__*/React.createElement("div", {
    className: "cur-regime cur-hashint"
  }, r.term)), window.enrichment.flowTypes().map(f => {
    const v = window.enrichment.pairMarket(r.id, f.id);
    return /*#__PURE__*/React.createElement("td", {
      key: f.id,
      className: "cur-c"
    }, /*#__PURE__*/React.createElement("select", {
      className: 'cur-cell ' + (v ? 'mk-' + v : 'cur-cell-empty'),
      value: v || '',
      onChange: e => window.enrichment.setPair(r.id, f.id, e.target.value || null)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u2014"), window.ENRICH_MARKETS.map(m => /*#__PURE__*/React.createElement("option", {
      key: m.id,
      value: m.id
    }, m.short))));
  }))))))));
}
window.ViewCuration = ViewCuration;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewCuration.jsx", error: String((e && e.message) || e) }); }

// ViewFlows.jsx
try { (() => {
// ViewFlows — territorial flows (origin → destination). Generic across
// MDIC / SEFAZ / UN Comtrade via the flowData contract. Renders synthetic
// preview data until the banco is live.

function ViewFlows({
  summary,
  conventions,
  database
}) {
  const banco = window.bancoById(database);
  const data = window.flowData(database, summary);
  const totalOut = data.nodes.filter(n => n.side === 'origin').reduce((s, n) => s + n.value, 0);
  const topOrigin = data.nodes.filter(n => n.side === 'origin').sort((a, b) => b.value - a.value)[0];
  const topDest = data.nodes.filter(n => n.side === 'dest').sort((a, b) => b.value - a.value)[0];
  const fmt = v => data.unit + ' ' + (v >= 1000 ? (v / 1000).toFixed(1).replace('.', ',') + ' bi' : v + ' mi');
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "Fluxos exigem pares origem \u2192 destino, ainda n\xE3o dispon\xEDveis nesta fonte."
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Fluxo total",
    value: fmt(totalOut),
    sub: `${data.links.length} rotas mapeadas`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: `Maior origem · ${data.originLabel}`,
    value: topOrigin?.label || '—',
    sub: fmt(topOrigin?.value || 0)
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: `Maior destino · ${data.destLabel}`,
    value: topDest?.label || '—',
    sub: fmt(topDest?.value || 0)
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Granularidade",
    value: banco?.scope || '—',
    sub: banco?.domain || ''
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Diagrama de fluxo · ${data.originLabel} → ${data.destLabel}`,
    title: "Para onde a produ\xE7\xE3o vai",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, data.unit, " \xB7 valores ilustrativos")
  }), /*#__PURE__*/React.createElement(window.SankeyChart, {
    nodes: data.nodes,
    links: data.links,
    unit: data.unit,
    height: 380
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Rotas principais",
    title: `Maiores fluxos ${data.originLabel} → ${data.destLabel}`
  }), /*#__PURE__*/React.createElement("div", {
    className: "flow-routes"
  }, data.links.slice().sort((a, b) => b.value - a.value).slice(0, 8).map((l, i) => {
    const o = data.nodes.find(n => n.id === l.source);
    const d = data.nodes.find(n => n.id === l.target);
    const max = Math.max(...data.links.map(x => x.value));
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: "flow-route"
    }, /*#__PURE__*/React.createElement("span", {
      className: "flow-route-od"
    }, o?.label, " ", /*#__PURE__*/React.createElement("span", {
      className: "flow-arrow"
    }, "\u2192"), " ", d?.label), /*#__PURE__*/React.createElement("div", {
      className: "flow-route-bar"
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: l.value / max * 100 + '%'
      }
    })), /*#__PURE__*/React.createElement("span", {
      className: "flow-route-val tnum"
    }, fmt(l.value)));
  }))));
}
window.ViewFlows = ViewFlows;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewFlows.jsx", error: String((e && e.message) || e) }); }

// ViewGeography.jsx
try { (() => {
// ViewGeography — territorial distribution of production, value and volume.
// All scales come from the global metric conventions (props.conventions).

const {
  useState: useGeoState,
  useMemo: useGeoMemo,
  useEffect: useGeoEffect
} = React;
function ViewGeography({
  families,
  conventions,
  summary,
  database
}) {
  const conv = conventions || window.DEFAULT_CONVENTIONS;
  // UF_DATA.value is in banco base currency (mi) internally — scale by 1e6 to
  // absolute, then convert through the base-aware factor.
  // UF_DATA.q_mass is in mil t internally; UF_DATA.q_vol is in mi m³.
  const valueMul = window.convFactor(conv) * 1e6; // mi → absolute, base-aware
  const massMul = window.massQtyMul(conv); // 1e3 (t) or 1e6 (kg)
  const volMul = window.volumeQtyMul(conv); // 1e6 (m³) or 1e9 (L)
  const valueUnitLabel = window.valueAxisLabel(conv); // "R$" / "US$" / etc.
  const massUnitLabel = window.massAxisLabel(conv); // "t" or "kg"
  const volUnitLabel = window.volumeAxisLabel(conv); // "m³" or "L"

  const filtered = window.applyFilters(summary || {}, database);
  const [dim, setDim] = useGeoState('value');
  const [scope, setScope] = useGeoState('uf');
  const massFamily = families.includes('mass');
  const volFamily = families.includes('volume');

  // Dimensions with active unit label
  const dims = [{
    id: 'value',
    label: 'Valor',
    key: 'value',
    unit: valueUnitLabel,
    mul: valueMul,
    available: true
  }, {
    id: 'mass',
    label: 'Quantidade (massa)',
    key: 'q_mass',
    unit: massUnitLabel,
    mul: massMul,
    available: massFamily
  }, {
    id: 'volume',
    label: 'Quantidade (volume)',
    key: 'q_vol',
    unit: volUnitLabel,
    mul: volMul,
    available: volFamily
  }].filter(d => d.available);

  // If the active dimension is no longer available (e.g. the basket changed
  // from a mixed cesta to mass-only), reset to the first available one.
  // Done in an effect — never call setState during render.
  useGeoEffect(() => {
    if (!dims.find(d => d.id === dim)) setDim(dims[0].id);
  }, [dim, massFamily, volFamily]);
  const activeDim = dims.find(d => d.id === dim) || dims[0];
  const valueKey = activeDim.key;
  const unit = activeDim.unit;
  const mul = activeDim.mul;

  // Scale geo datasets according to active dimension's multiplier
  const scaledUFs = useGeoMemo(() => filtered.ufData.map(u => ({
    ...u,
    [valueKey]: u[valueKey] * mul
  })), [valueKey, mul, filtered]);
  const scaledRegions = useGeoMemo(() => filtered.regionData.map(r => ({
    ...r,
    [valueKey]: r[valueKey] * mul
  })), [valueKey, mul, filtered]);
  const scaledMunis = useGeoMemo(() => filtered.topMunis.map(m => ({
    ...m,
    [valueKey]: (m[valueKey] || 0) * mul
  })), [valueKey, mul, filtered]);

  // Heatmap: year × UF
  const heatRows = useGeoMemo(() => {
    const ts = filtered.ts;
    if (!ts.length) return [];
    const tsMax = Math.max(...ts.map(d => d.v), 1);
    return scaledUFs.slice().sort((a, b) => b[valueKey] - a[valueKey]).slice(0, 12).map(u => ({
      id: u.uf,
      label: `${u.uf} · ${u.name}`,
      values: ts.map(t => ({
        y: t.y,
        v: Math.round(u[valueKey] * (t.v / tsMax) * 100) / 100
      }))
    }));
  }, [valueKey, scaledUFs]);
  const top10ufs = scaledUFs.slice().sort((a, b) => b[valueKey] - a[valueKey]).slice(0, 10);

  // ---- Auto-scale all geo datasets to a shared factor (when ON) -----
  const sharedMax = Math.max(...scaledUFs.map(u => u[valueKey] || 0));
  const ufScaled = window.scaleSeries(scaledUFs, sharedMax, conv, valueKey, unit);
  const regScaled = window.scaleSeries(scaledRegions, Math.max(...scaledRegions.map(r => r[valueKey] || 0)), conv, valueKey, unit);
  const top10Scaled = window.scaleSeries(top10ufs, sharedMax, conv, valueKey, unit);
  const muniMax = Math.max(...scaledMunis.map(m => m[valueKey] || 0));
  const muniScaled = window.scaleSeries(scaledMunis, muniMax, conv, valueKey, unit);
  const heatMax = Math.max(...heatRows.flatMap(r => r.values.map(v => v.v)));
  const heatScaled = (() => {
    if (!conv.autoScale) return {
      rows: heatRows,
      label: unit
    };
    const {
      factor,
      suffix
    } = window.autoScaleNum(heatMax);
    if (!suffix) return {
      rows: heatRows,
      label: unit
    };
    const CURRENCY_SYMS = ['R$', 'US$', '€', '¥'];
    const label = CURRENCY_SYMS.includes(unit) ? `${unit} ${suffix}` : `${suffix} ${unit}`.trim();
    return {
      rows: heatRows.map(r => ({
        ...r,
        values: r.values.map(v => ({
          ...v,
          v: v.v / factor
        }))
      })),
      label
    };
  })();
  const displayUnit = ufScaled.label;
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.UnitFamilyBanner, {
    families: families
  }), /*#__PURE__*/React.createElement("div", {
    className: "geo-controls"
  }, /*#__PURE__*/React.createElement("div", {
    className: "geo-control-grp"
  }, /*#__PURE__*/React.createElement("span", {
    className: "overline"
  }, "M\xE9trica"), /*#__PURE__*/React.createElement("div", {
    className: "seg"
  }, dims.map(d => /*#__PURE__*/React.createElement("button", {
    key: d.id,
    className: 'seg-opt ' + (dim === d.id ? 'on' : ''),
    onClick: () => setDim(d.id)
  }, d.label)))), /*#__PURE__*/React.createElement("div", {
    className: "geo-control-grp"
  }, /*#__PURE__*/React.createElement("span", {
    className: "overline"
  }, "Granularidade"), /*#__PURE__*/React.createElement("div", {
    className: "seg"
  }, /*#__PURE__*/React.createElement("button", {
    className: 'seg-opt ' + (scope === 'region' ? 'on' : ''),
    onClick: () => setScope('region')
  }, "Regi\xE3o"), /*#__PURE__*/React.createElement("button", {
    className: 'seg-opt ' + (scope === 'uf' ? 'on' : ''),
    onClick: () => setScope('uf')
  }, "UF"), /*#__PURE__*/React.createElement("button", {
    className: 'seg-opt ' + (scope === 'municipio' ? 'on' : ''),
    onClick: () => setScope('municipio')
  }, "Munic\xEDpio")))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Mapa de calor · ${activeDim.label} · ${displayUnit} · ${filtered.yearEnd}`,
    title: scope === 'region' ? 'Distribuição por região' : scope === 'uf' ? 'Distribuição por UF' : 'Distribuição por município (top)'
  }), scope === 'region' && /*#__PURE__*/React.createElement(window.RegionBars, {
    data: regScaled.data,
    valueKey: valueKey,
    label: regScaled.label,
    height: 280
  }), scope === 'uf' && /*#__PURE__*/React.createElement(window.BrazilTileMap, {
    data: ufScaled.data,
    valueKey: valueKey,
    label: displayUnit
  }), scope === 'municipio' && /*#__PURE__*/React.createElement("div", {
    className: "muni-list"
  }, muniScaled.data.filter(m => valueKey === 'value' || m[valueKey] != null && m[valueKey] > 0).map((m, i, arr) => {
    const max = Math.max(...arr.map(x => x[valueKey] || 0));
    const v = m[valueKey] || 0;
    return /*#__PURE__*/React.createElement("div", {
      key: m.city + m.uf,
      className: "muni-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "muni-rank tnum"
    }, "#", i + 1), /*#__PURE__*/React.createElement("span", {
      className: "muni-name"
    }, m.city), /*#__PURE__*/React.createElement("span", {
      className: "muni-uf"
    }, m.uf), /*#__PURE__*/React.createElement("span", {
      className: "muni-product"
    }, m.product), /*#__PURE__*/React.createElement("div", {
      className: "muni-bar"
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: (v / max * 100).toFixed(1) + '%',
        background: 'var(--viz-2)'
      }
    })), /*#__PURE__*/React.createElement("span", {
      className: "muni-val tnum"
    }, v.toLocaleString('pt-BR', {
      maximumFractionDigits: 1
    }), " ", muniScaled.label));
  }))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Evolução temporal · ${activeDim.label} (${heatScaled.label})`,
    title: `Mapa de calor · ano × UF (${heatScaled.rows.length} maiores)`
  }), /*#__PURE__*/React.createElement(window.Heatmap, {
    rows: heatScaled.rows,
    valueKey: "v",
    valueLabel: heatScaled.label
  })), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Top 10 · ${activeDim.label}`,
    title: `Maiores estados produtores · ${filtered.yearEnd}`,
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, activeDim.label, " (", top10Scaled.label, ")")
  }), /*#__PURE__*/React.createElement(window.BarChart, {
    data: top10Scaled.data,
    valueKey: valueKey,
    color: "var(--viz-2)",
    height: 320
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `${activeDim.label} · ${filtered.yearEnd}`,
    title: "Soma por regi\xE3o",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, regScaled.data.length, " macrorregi\xF5es \xB7 ", regScaled.label)
  }), /*#__PURE__*/React.createElement(window.RegionBars, {
    data: regScaled.data,
    valueKey: valueKey,
    label: regScaled.label,
    height: 320
  }))));
}
window.ViewGeography = ViewGeography;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewGeography.jsx", error: String((e && e.message) || e) }); }

// ViewHealth.jsx
try { (() => {
// ViewHealth — institutional "Saúde do sistema" page.
// Pure operational status: pipeline runs, data freshness, SLAs, alerts.
// Live datasets read from window.QUALITY_TS for the OK trend; everything
// else is synthetic but kept inside the file so it stays auditable.

function ViewHealth() {
  const bancos = window.visibleBancos ? window.visibleBancos() : window.BANCOS || [];
  // lastRun / goldRows are NOT re-typed here — they track the registry.
  const PEV_PROV = window.bancoById && window.bancoById('ibge_pevs')?.prov || {};

  // ── Per-banco OPERATIONAL facts (independent of maturity) ────────────
  // These describe how the pipeline is RUNNING (not how mature it is):
  // last run health, errors, freshness. Synthetic but distinct so the
  // operational column doesn't merely echo the maturity tag.
  const provFacts = id => {
    const p = window.bancoById && window.bancoById(id)?.prov || {};
    return {
      lastRun: p.refresh || '—',
      goldRows: p.totalRows,
      sourcePublished: p.lastCropDate || '—'
    };
  };
  const STATE = {
    ibge_pevs: {
      lastRun: PEV_PROV.refresh || '—',
      durationSec: 184,
      goldRows: PEV_PROV.totalRows || 0,
      goldRowsDelta: +42_109,
      sourcePublished: '27 set 2024',
      freshness: 'pré-anual',
      // annual-harvest banco
      slaPct: 99.6,
      runOk: true,
      lastRunErrors: 0
    },
    mdic_comex: {
      ...provFacts('mdic_comex'),
      durationSec: 96,
      goldRowsDelta: +8_240,
      slaPct: 99.1,
      runOk: true,
      lastRunErrors: 0
    },
    un_comtrade: {
      ...provFacts('un_comtrade'),
      durationSec: 410,
      goldRowsDelta: +3_110,
      slaPct: 96.8,
      runOk: true,
      lastRunErrors: 0
    },
    ibge_pam: {
      ...provFacts('ibge_pam'),
      durationSec: 152,
      goldRowsDelta: +12_400,
      slaPct: 98.3,
      runOk: true,
      lastRunErrors: 0
    },
    sefaz_nf: {}
  };

  // ── 14-day pipeline run history ─────────────────────────────────────
  // Recent date list (D-13 → D-0); status per day. Anchored to the real
  // current date so "hoje" and the 14-day window actually advance.
  const today = new Date();
  const RUN_HISTORY = Array.from({
    length: 14
  }, (_, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() - (13 - i));
    // synthetic but plausible — most OK, one warn, one fail spread out
    const seed = i;
    let status = 'ok';
    if (seed === 4) status = 'warn';
    if (seed === 9) status = 'fail';
    return {
      date: d.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: 'short'
      }),
      iso: d.toISOString().slice(0, 10),
      status,
      runs: (window.visibleBancos ? window.visibleBancos() : window.BANCOS || []).filter(b => b.status === 'live').length // connected bancos on the daily calendar
    };
  });

  // ── Sources & freshness ─────────────────────────────────────────────
  const SOURCES = [{
    name: 'IBGE SIDRA',
    banco: 'ibge_pevs',
    lastPublished: '27 set 2024',
    lastPublishedIso: '2024-09-27',
    cadence: 'anual',
    url: 'sidra.ibge.gov.br/pesquisa/pevs',
    status: 'live'
  }, {
    name: 'IBGE SIDRA (PAM)',
    banco: 'ibge_pam',
    lastPublished: 'set 2025',
    lastPublishedIso: '2025-09-15',
    cadence: 'anual',
    url: 'sidra.ibge.gov.br/pesquisa/pam',
    status: 'live'
  }, {
    name: 'MDIC SECEX',
    banco: 'mdic_comex',
    lastPublished: '—',
    cadence: 'mensal (D+30)',
    url: 'comexstat.mdic.gov.br',
    status: 'pending'
  }, {
    name: 'UN Comtrade',
    banco: 'un_comtrade',
    lastPublished: '—',
    cadence: 'anual + revisões trimestrais',
    url: 'comtradeplus.un.org',
    status: 'pending'
  }, {
    name: 'SEFAZ NFe',
    banco: 'sefaz_nf',
    lastPublished: '—',
    cadence: 'diária (D+1)',
    url: 'nfe.fazenda.gov.br',
    status: 'pending'
  }];

  // ── Active alerts ────────────────────────────────────────────────────
  // Coverage lint: live bancos need an operational seed (STATE) and every
  // visible banco an upstream source (SOURCES) — both are curated here.
  if (window.auditBancoCoverage) {
    window.auditBancoCoverage('saúde · execução por banco (ViewHealth.jsx)', b => STATE[b.id] && STATE[b.id].lastRun, {
      onlyLive: true
    });
    window.auditBancoCoverage('saúde · frescor das fontes (ViewHealth.jsx)', b => SOURCES.some(s => s.banco === b.id));
  }
  const ALERTS = [{
    level: 'info',
    title: 'PEVS 2025 em apuração pelo IBGE',
    desc: 'A safra mais recente publicada é a PEVS 2024 (27 set 2024). A edição ano-base 2025 está em apuração, com divulgação prevista para set/2026. Até lá, o banco reflete a safra 2024.',
    since: '27 set 2024'
  }, {
    level: 'warn',
    banco: 'ibge_pevs',
    title: 'Aumento de OUTLIER em borracha (látex) · 2023',
    desc: 'Detector estatístico marcou 3,2% das linhas (média histórica: 1,8%). Investigação registrada em #DAT-2026-118.',
    since: '14 mai 2026'
  }];

  // ── Operational HEALTH — DERIVED FROM OPERATIONS, not from maturity ───
  // Answers "is it operating well RIGHT NOW?" (runs, freshness, errors,
  // alerts), a distinct axis from "how mature/implemented is it?". That is
  // why an estavel banco can be "Em atenção" (active alert or stale Gold) and
  // a beta banco can be "Saudável" (pipeline running normally). "Source down"
  // is HEALTH ("Falha"), never a maturity stage.
  const operationalStatus = b => {
    const m = window.maturityMeta(b);
    if (!m.hasData) return b.maturity === 'planejado' ? 'planned' : 'pending'; // nothing operating yet
    if (window.dataStore && window.dataStore.error(b.id)) return 'fail'; // source down / load failure
    const o = STATE[b.id] || {};
    if (o.runOk === false || (o.lastRunErrors || 0) > 0) return 'fail'; // run failed
    const al = ALERTS.find(a => a.banco === b.id && (a.level === 'warn' || a.level === 'fail'));
    if (al) return al.level; // active banco alert
    if (window.dataStore && window.dataStore.isStale(b.id)) return 'warn'; // stale snapshot
    if (o.overdue) return 'warn'; // freshness overdue
    return 'ok';
  };
  bancos.forEach(b => {
    STATE[b.id] = STATE[b.id] || {};
    STATE[b.id].status = operationalStatus(b);
  });

  // ── KPI strip aggregates ────────────────────────────────────────────
  const liveDefined = bancos.filter(b => b.status === 'live');
  const liveBancos = liveDefined.filter(b => STATE[b.id]?.status === 'ok');
  const pendingCount = bancos.filter(b => b.status === 'soon').length;
  const failsRecent = RUN_HISTORY.filter(r => r.status === 'fail').length;
  const totalRuns = RUN_HISTORY.length;
  const slaWindow = totalRuns ? (totalRuns - failsRecent) / totalRuns * 100 : 100;

  // Last pipeline run = the live banco's snapshot facts (no hardcoded KPI).
  const liveBanco = bancos.find(b => b.id === 'ibge_pevs');
  const liveState = STATE.ibge_pevs;
  const fmtDur = s => `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`;
  const MONTH_IDX = {
    jan: 0,
    fev: 1,
    mar: 2,
    abr: 3,
    mai: 4,
    jun: 5,
    jul: 6,
    ago: 7,
    set: 8,
    out: 9,
    nov: 10,
    dez: 11
  };
  const runDatePart = (liveState.lastRun || '').split(' · ')[0]; // "28 mai 2026"
  const runTimePart = ((liveState.lastRun || '').split(' · ')[1] || '').replace(/\s*BRT/i, ''); // "04:30"
  const rdp = runDatePart.split(/\s+/); // ["28","mai","2026"]
  const runDate = rdp.length >= 3 ? new Date(+rdp[2], MONTH_IDX[rdp[1]?.toLowerCase()] ?? 0, +rdp[0]) : null;
  const runIsToday = runDate && runDate.toDateString() === today.toDateString();
  const lastRunLabel = (runIsToday ? 'hoje' : rdp.slice(0, 2).join(' ')) + (runTimePart ? ' · ' + runTimePart : '');

  // Overall system status = worst of the live bancos + any active warn alert.
  const liveStatuses = liveDefined.map(b => STATE[b.id]?.status).filter(Boolean);
  const overall = liveStatuses.includes('fail') ? 'fail' : liveStatuses.includes('warn') || ALERTS.some(a => a.level === 'warn') ? 'warn' : 'ok';
  const OVERALL = {
    ok: {
      color: 'var(--ok)',
      label: 'Operacional',
      note: 'todas as execuções planejadas concluíram nas últimas 24h'
    },
    warn: {
      color: 'var(--warn)',
      label: 'Em atenção',
      note: `${ALERTS.filter(a => a.level === 'warn').length} alerta(s) de atenção em aberto`
    },
    fail: {
      color: 'var(--err)',
      label: 'Falha',
      note: 'há execução com falha — verifique a tabela por banco'
    }
  }[overall];
  const STATUS_LABEL = {
    ok: {
      label: 'Saudável',
      color: 'var(--ok)'
    },
    warn: {
      label: 'Em atenção',
      color: 'var(--warn)'
    },
    fail: {
      label: 'Falha',
      color: 'var(--err)'
    },
    pending: {
      label: 'Aguardando ingestão',
      color: 'var(--fg-3)'
    },
    planned: {
      label: 'Planejado',
      color: 'var(--pres-gray-400)'
    },
    info: {
      label: 'Informativo',
      color: 'var(--info)'
    }
  };
  const fmtRows = window.fmtRows; // shared compact mi/mil counter (data.js)

  return /*#__PURE__*/React.createElement("div", {
    className: "ab-stack"
  }, /*#__PURE__*/React.createElement("div", {
    className: "kpi-row hs-kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Status geral do sistema",
    value: /*#__PURE__*/React.createElement("span", {
      className: "hs-status-pill",
      style: {
        '--st-color': OVERALL.color
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "hs-dot",
      style: {
        background: OVERALL.color
      }
    }), OVERALL.label),
    sub: OVERALL.note
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Bancos saud\xE1veis",
    value: `${liveBancos.length} / ${liveDefined.length}`,
    sub: `${pendingCount} aguardando ingestão`,
    spark: window.QUALITY_TS.slice(-12),
    sparkKey: "ok",
    sparkColor: "var(--ok)"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "\xDAltima execu\xE7\xE3o do pipeline",
    value: lastRunLabel,
    sub: `${liveBanco?.id || '—'} · ${fmtDur(liveState.durationSec)} · ${liveState.lastRunErrors} erros`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Falhas nos \xFAltimos 14 dias",
    value: failsRecent.toString(),
    sub: failsRecent === 0 ? 'série limpa' : `${failsRecent} ${failsRecent === 1 ? 'falha' : 'falhas'} em ${totalRuns} execuções · ${slaWindow.toFixed(1).replace('.', ',')}% SLA`
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Pushdown \xB7 Cloud Run stateless",
    title: "Consultas ao BigQuery e cache do servi\xE7o",
    action: /*#__PURE__*/React.createElement("div", {
      className: "hdr-actions"
    }, /*#__PURE__*/React.createElement("button", {
      className: "btn-ghost",
      onClick: () => {
        window.dataStore.simulateError('ibge_pevs');
      }
    }, /*#__PURE__*/React.createElement(window.Icon, {
      name: "warning",
      size: 14
    }), " Simular falha de consulta"), /*#__PURE__*/React.createElement("button", {
      className: "btn-secondary",
      onClick: () => window.dataStore.bumpGold('ibge_pevs')
    }, /*#__PURE__*/React.createElement(window.Icon, {
      name: "refresh",
      size: 14
    }), " Simular atualiza\xE7\xE3o da Gold"))
  }), /*#__PURE__*/React.createElement("div", {
    className: "hs-snap"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hs-snap-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Vers\xE3o em cache (IBGE PEVS)"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, window.dataStore.version('ibge_pevs') || '—')), /*#__PURE__*/React.createElement("div", {
    className: "hs-snap-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Vers\xE3o upstream na Gold"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, window.dataStore.latestVersion('ibge_pevs') || '—')), /*#__PURE__*/React.createElement("div", {
    className: "hs-snap-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Estado do cache"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val"
  }, window.dataStore.isStale('ibge_pevs') ? /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--warn)',
      fontWeight: 600
    }
  }, "Desatualizado \xB7 invalida\xE7\xE3o pendente") : /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--ok)',
      fontWeight: 600
    }
  }, "Sincronizado"))), /*#__PURE__*/React.createElement("p", {
    className: "caption hs-snap-note"
  }, "No deploy, o Cloud Run \xE9 stateless: cada intera\xE7\xE3o vira uma consulta SQL parametrizada empurrada ao BigQuery, e o ", /*#__PURE__*/React.createElement("strong", null, "flask-caching"), " memoiza os resultados pequenos por par\xE2metro + vers\xE3o da Gold. \"Simular atualiza\xE7\xE3o\" muda a vers\xE3o upstream (invalida o cache e dispara o aviso de recarga ao voltar para uma view de dados); \"Simular falha de consulta\" arma um erro na pr\xF3xima consulta do banco, exibindo a tela de erro com op\xE7\xE3o de tentar novamente."))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Sa\xFAde por banco de dados",
    title: "Estado atual da pipeline em cada fonte",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, bancos.length, " bancos monitorados")
  }), /*#__PURE__*/React.createElement("div", {
    className: "hs-table-wrap"
  }, /*#__PURE__*/React.createElement("table", {
    className: "hs-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Banco"), /*#__PURE__*/React.createElement("th", null, "Maturidade"), /*#__PURE__*/React.createElement("th", null, "Opera\xE7\xE3o"), /*#__PURE__*/React.createElement("th", null, "\xDAltima execu\xE7\xE3o Gold"), /*#__PURE__*/React.createElement("th", null, "Linhas Gold"), /*#__PURE__*/React.createElement("th", null, "Fonte publicada"), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "SLA 30d"))), /*#__PURE__*/React.createElement("tbody", null, bancos.map(b => {
    const s = STATE[b.id] || {
      status: 'pending'
    };
    const meta = STATUS_LABEL[s.status];
    return /*#__PURE__*/React.createElement("tr", {
      key: b.id
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("div", {
      className: "hs-banco"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hs-banco-short"
    }, b.short), /*#__PURE__*/React.createElement("span", {
      className: "hs-banco-table"
    }, /*#__PURE__*/React.createElement("code", null, window.bancoTable(b.id))))), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(window.MaturityTag, {
      banco: b,
      size: "sm"
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("span", {
      className: "hs-status-pill",
      style: {
        '--st-color': meta.color
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "hs-dot",
      style: {
        background: meta.color
      }
    }), meta.label)), /*#__PURE__*/React.createElement("td", {
      className: "tnum"
    }, s.lastRun || '—', s.durationSec != null && /*#__PURE__*/React.createElement("small", {
      className: "hs-dur"
    }, " \xB7 ", Math.floor(s.durationSec / 60), "m ", s.durationSec % 60, "s")), /*#__PURE__*/React.createElement("td", {
      className: "tnum"
    }, s.goldRows != null ? fmtRows(s.goldRows) : '—', s.goldRowsDelta != null && /*#__PURE__*/React.createElement("small", {
      className: "hs-delta"
    }, s.goldRowsDelta >= 0 ? '+' : '', fmtRows(s.goldRowsDelta))), /*#__PURE__*/React.createElement("td", {
      className: "tnum"
    }, s.sourcePublished || '—'), /*#__PURE__*/React.createElement("td", {
      className: "num tnum"
    }, s.slaPct != null ? s.slaPct.toFixed(1).replace('.', ',') + '%' : '—'));
  }))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Maturidade",
    title: "O que cada est\xE1gio significa",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "eixo de ciclo de vida do banco")
  }), /*#__PURE__*/React.createElement(window.MaturityLegend, null)), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Execu\xE7\xF5es recentes",
    title: "\xDAltimos 14 dias \xB7 todas as bancas",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, RUN_HISTORY.length, " execu\xE7\xF5es di\xE1rias")
  }), /*#__PURE__*/React.createElement("div", {
    className: "hs-runs"
  }, RUN_HISTORY.map((r, i) => {
    const meta = STATUS_LABEL[r.status];
    return /*#__PURE__*/React.createElement("div", {
      key: r.iso,
      className: 'hs-run hs-run-' + r.status,
      title: `${r.date} · ${meta.label}`
    }, /*#__PURE__*/React.createElement("span", {
      className: "hs-run-bar",
      style: {
        background: meta.color
      }
    }), /*#__PURE__*/React.createElement("span", {
      className: "hs-run-date"
    }, r.date));
  })), /*#__PURE__*/React.createElement("div", {
    className: "hs-runs-legend"
  }, ['ok', 'warn', 'fail'].map(s => /*#__PURE__*/React.createElement("span", {
    key: s,
    className: "qa-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "qa-dot",
    style: {
      background: STATUS_LABEL[s].color
    }
  }), STATUS_LABEL[s].label)))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Frescor das fontes",
    title: "Quando cada fonte publicou pela \xFAltima vez",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, SOURCES.length, " fontes oficiais")
  }), /*#__PURE__*/React.createElement("div", {
    className: "hs-sources"
  }, SOURCES.filter(src => window.isBancoVisible(src.banco)).map(src => /*#__PURE__*/React.createElement("div", {
    key: src.name,
    className: 'hs-source ' + src.status
  }, /*#__PURE__*/React.createElement("div", {
    className: "hs-source-l"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hs-source-name"
  }, src.name), /*#__PURE__*/React.createElement("div", {
    className: "hs-source-meta"
  }, /*#__PURE__*/React.createElement("code", null, src.url), " \xB7 cad\xEAncia ", src.cadence)), /*#__PURE__*/React.createElement("div", {
    className: "hs-source-r"
  }, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "\xDAltima publica\xE7\xE3o"), /*#__PURE__*/React.createElement("span", {
    className: "meta-val tnum"
  }, src.lastPublished)))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Alertas ativos",
    title: `${ALERTS.length} aviso(s) em aberto`
  }), /*#__PURE__*/React.createElement("div", {
    className: "hs-alerts"
  }, ALERTS.length === 0 ? /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '12px 4px'
    }
  }, "Nenhum alerta ativo no momento.") : ALERTS.map((a, i) => {
    const meta = STATUS_LABEL[a.level];
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: 'hs-alert hs-alert-' + a.level
    }, /*#__PURE__*/React.createElement("div", {
      className: "hs-alert-head"
    }, /*#__PURE__*/React.createElement("span", {
      className: "hs-status-pill",
      style: {
        '--st-color': meta.color
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "hs-dot",
      style: {
        background: meta.color
      }
    }), meta.label), /*#__PURE__*/React.createElement("span", {
      className: "hs-alert-title"
    }, a.title), /*#__PURE__*/React.createElement("span", {
      className: "hs-alert-since caption"
    }, "desde ", a.since)), /*#__PURE__*/React.createElement("p", {
      className: "hs-alert-desc"
    }, a.desc));
  }))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Qualidade dos dados \xB7 hist\xF3rico",
    title: "% de linhas \xEDntegras (flag = OK) \xB7 IBGE PEVS",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "Para diagn\xF3stico completo, veja Qualidade dos dados")
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: window.QUALITY_TS.map(d => ({
      y: d.y,
      v: d.ok * 100
    })),
    label: "% OK",
    valueKey: "v",
    color: "var(--ok)",
    height: 220
  })));
}
window.ViewHealth = ViewHealth;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewHealth.jsx", error: String((e && e.message) || e) }); }

// ViewNotApplicable.jsx
try { (() => {
// ViewNotApplicable — shown when a perspective is selected that doesn't
// apply to the active banco (the banco lacks the data capability the view
// requires). Distinct from ViewComingSoon (whole banco awaiting ingest)
// and ViewPerspectiveSoon (view applies but not yet built).
//
// Acts as the inverse indicator: tells the researcher WHICH bancos do
// support this perspective, and lets them switch directly.

function ViewNotApplicable({
  viewMeta,
  banco,
  missing,
  supporters,
  onPickBanco
}) {
  if (!viewMeta) return null;
  return /*#__PURE__*/React.createElement("div", {
    className: "cs-stack"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card na-hero"
  }, /*#__PURE__*/React.createElement("div", {
    className: "na-hero-l"
  }, /*#__PURE__*/React.createElement("div", {
    className: "cs-eyebrow"
  }, /*#__PURE__*/React.createElement("span", {
    className: "na-badge"
  }, "N\xE3o se aplica"), viewMeta.group && /*#__PURE__*/React.createElement("span", {
    className: "caption"
  }, viewMeta.group.label, " \xB7 ", viewMeta.group.hint)), /*#__PURE__*/React.createElement("h2", {
    className: "cs-title"
  }, viewMeta.label), /*#__PURE__*/React.createElement("p", {
    className: "cs-sub"
  }, "Esta perspectiva n\xE3o est\xE1 dispon\xEDvel para ", /*#__PURE__*/React.createElement("strong", null, banco?.short || 'este banco'), ", que n\xE3o possui ", missing && missing.length ? /*#__PURE__*/React.createElement("strong", null, window.missingCapsLabel(missing)) : 'a dimensão necessária', "."), /*#__PURE__*/React.createElement("p", {
    className: "cs-sub na-desc"
  }, viewMeta.desc))), supporters && supporters.length > 0 ? /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Onde usar esta perspectiva",
    title: "Bancos compat\xEDveis",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, supporters.length, " de ", (window.visibleBancos ? window.visibleBancos() : window.BANCOS || []).length, " bancos")
  }), /*#__PURE__*/React.createElement("div", {
    className: "na-bancos"
  }, supporters.map(b => /*#__PURE__*/React.createElement("button", {
    key: b.id,
    className: 'na-banco ' + (b.status === 'live' ? 'live' : 'soon'),
    onClick: () => onPickBanco && onPickBanco(b.id),
    title: b.status === 'live' ? `Trocar para ${b.short}` : `${b.short} · ${window.bancoAvailability(b).toLowerCase()}`
  }, /*#__PURE__*/React.createElement("div", {
    className: "na-banco-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "na-banco-short"
  }, b.short), /*#__PURE__*/React.createElement("span", {
    className: 'na-banco-tag ' + b.status
  }, window.bancoAvailability(b))), /*#__PURE__*/React.createElement("div", {
    className: "na-banco-domain"
  }, b.domain), /*#__PURE__*/React.createElement("p", {
    className: "na-banco-sub"
  }, b.sub), b.status === 'live' && /*#__PURE__*/React.createElement("span", {
    className: "na-banco-cta"
  }, "Trocar para este banco \u2192")))), /*#__PURE__*/React.createElement("div", {
    className: "cs-note"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "info",
    size: 14
  }), /*#__PURE__*/React.createElement("span", null, "A sele\xE7\xE3o de banco fica na barra lateral. Trocar de banco mant\xE9m os filtros compat\xEDveis e redefine apenas os que n\xE3o existem na nova fonte."))) : /*#__PURE__*/React.createElement("div", {
    className: "card subtle"
  }, /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '16px 4px'
    }
  }, "Nenhum banco dispon\xEDvel oferece esta perspectiva no momento.")));
}
window.ViewNotApplicable = ViewNotApplicable;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewNotApplicable.jsx", error: String((e && e.message) || e) }); }

// ViewOverview.jsx
try { (() => {
// ViewOverview — a digest of the other three perspectives.
// All datasets pass through window.applyFilters(summary) so KPIs,
// charts and the donut only reflect the rows the researcher selected.

function ViewOverview({
  families,
  summary,
  database,
  conventions
}) {
  const conv = conventions || window.DEFAULT_CONVENTIONS;
  const monLabel = window.conventionMonetaryLabel(conv);
  const valAxis = window.valueAxisLabel(conv);
  const filtered = window.applyFilters(summary || {}, database);

  // ts.v is in R$ bi; scale to absolute.
  const ts = filtered.ts.map(d => ({
    ...d,
    v: d.v * 1e9
  }));
  const last = ts[ts.length - 1] || {
    v: 0,
    q_mass: 0,
    q_vol: 0
  };
  const prev = ts[ts.length - 2] || last;
  const first = ts[0] || last;
  const deltaV = prev.v ? (last.v - prev.v) / prev.v * 100 : 0;
  const deltaTotV = first.v ? (last.v - first.v) / first.v * 100 : 0;
  const spark12 = ts.slice(-12);

  // Quality digest from filtered flag set
  const okFlag = filtered.qualityFlags.find(f => f.id === 'OK');
  const okShare = okFlag ? okFlag.share : 0;
  const okCount = okFlag ? okFlag.count : 0;
  const ufCovered = filtered.ufData.filter(u => u.value > 0).length;
  const top3 = filtered.ufData.slice().sort((a, b) => b.value - a.value).slice(0, 3);
  const hasGeo = filtered.ufDataFull.length > 0;
  const massFamily = families.includes('mass');
  const volFamily = families.includes('volume');
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.UnitFamilyBanner, {
    families: families
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: `Valor total · ${monLabel}`,
    value: window.formatValue(last.v, conv),
    delta: window.fmtSigned(deltaV),
    deltaPositive: deltaV >= 0,
    sub: `${last.y || ''} vs. ${prev.y || ''}`,
    spark: window.convertSeries(spark12, conv),
    sparkKey: "v",
    sparkColor: "var(--viz-1)"
  }), massFamily && /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: /*#__PURE__*/React.createElement(React.Fragment, null, "Quantidade \xB7 ", /*#__PURE__*/React.createElement(window.UnitFamilyTag, {
      family: "mass",
      conv: conv
    })),
    value: window.formatMassQty(last.q_mass, conv),
    delta: window.fmtSigned(prev.q_mass ? (last.q_mass - prev.q_mass) / prev.q_mass * 100 : 0),
    deltaPositive: last.q_mass >= prev.q_mass,
    sub: `${last.y || ''} vs. ${prev.y || ''}`,
    spark: spark12,
    sparkKey: "q_mass",
    sparkColor: "var(--viz-2)"
  }), volFamily && /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: /*#__PURE__*/React.createElement(React.Fragment, null, "Quantidade \xB7 ", /*#__PURE__*/React.createElement(window.UnitFamilyTag, {
      family: "volume",
      conv: conv
    })),
    value: window.formatVolumeQty(last.q_vol, conv),
    delta: window.fmtSigned(prev.q_vol ? (last.q_vol - prev.q_vol) / prev.q_vol * 100 : 0),
    deltaPositive: last.q_vol >= prev.q_vol,
    sub: `${last.y || ''} vs. ${prev.y || ''}`,
    spark: spark12,
    sparkKey: "q_vol",
    sparkColor: "var(--viz-4)"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Linhas \xEDntegras (flag = OK)",
    value: window.fmtPct(okShare),
    sub: okCount ? (okCount / 1e6).toFixed(1).replace('.', ',') + ' mi linhas' : 'OK não selecionada',
    spark: filtered.qualityTs.slice(-12),
    sparkKey: "ok",
    sparkColor: "var(--ok)"
  })), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, (() => {
    const series = window.convertSeries(ts, conv);
    const max = Math.max(...series.map(d => d.v), 0);
    const {
      data,
      label
    } = window.scaleSeries(series, max, conv, 'v', valAxis);
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.SectionHeader, {
      overline: `Série histórica · ${filtered.yearStart}–${filtered.yearEnd} · ${monLabel}`,
      title: 'Variação acumulada: ' + window.fmtSigned(deltaTotV, 0)
    }), /*#__PURE__*/React.createElement(window.LineChart, {
      data: data,
      label: label,
      valueKey: "v",
      color: "var(--viz-1)",
      height: 240
    }));
  })()), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Composição · ${filtered.yearEnd}`,
    title: "Participa\xE7\xE3o por produto",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, filtered.selectedProducts.length, " de ", filtered.productsTotal, " produtos")
  }), filtered.topProducts.length === 0 ? /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '24px 4px',
      textAlign: 'center'
    }
  }, "Nenhum produto selecionado nos filtros.") : /*#__PURE__*/React.createElement(window.Donut, {
    data: filtered.topProducts,
    size: 180,
    valueKey: "share"
  }))), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, hasGeo && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, (() => {
    const ufRows = filtered.ufData.map(u => ({
      ...u,
      value: u.value * 1e6 * window.convFactor(conv)
    }));
    const max = Math.max(...ufRows.map(u => u.value), 0);
    const {
      data,
      label
    } = window.scaleSeries(ufRows, max, conv, 'value', valAxis);
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.SectionHeader, {
      overline: `Distribuição geográfica · ${filtered.yearEnd}`,
      title: `Valor por UF · ${label}`,
      action: /*#__PURE__*/React.createElement("span", {
        className: "caption"
      }, top3.length ? 'Top 3: ' + top3.map(u => u.uf).join(' · ') : '—')
    }), /*#__PURE__*/React.createElement(window.BrazilTileMap, {
      data: data,
      valueKey: "value",
      label: label
    }));
  })()), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Qualidade dos dados \xB7 agregado",
    title: hasGeo ? 'Cobertura geográfica: ' + ufCovered + ' / ' + (filtered.ufDataFull.length || 0) + ' UFs' : 'Distribuição de flags de qualidade',
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, filtered.qualityFlags.length, " de ", window.QUALITY_FLAGS.length, " flags")
  }), /*#__PURE__*/React.createElement("div", {
    className: "qa-summary"
  }, filtered.qualityFlags.map(f => /*#__PURE__*/React.createElement("div", {
    key: f.id,
    className: "qa-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "qa-dot",
    style: {
      background: f.color
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "qa-label"
  }, f.label), /*#__PURE__*/React.createElement("span", {
    className: "qa-count tnum"
  }, (f.count / 1000).toLocaleString('pt-BR', {
    maximumFractionDigits: 0
  }), "k"), /*#__PURE__*/React.createElement("span", {
    className: "qa-share tnum"
  }, window.fmtPct(f.share))))))));
}
window.ViewOverview = ViewOverview;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewOverview.jsx", error: String((e && e.message) || e) }); }

// ViewPartners.jsx
try { (() => {
// ViewPartners — trading-partner rankings (country or UF). Generic via
// the partnerData contract. Synthetic preview until the banco is live.

function ViewPartners({
  summary,
  conventions,
  database
}) {
  const banco = window.bancoById(database);
  const data = window.partnerData(database, summary);
  const total = data.partners.reduce((s, p) => s + p.value, 0) || 1;
  const top = data.partners[0];
  const fmt = v => data.unit + ' ' + (v >= 1000 ? (v / 1000).toFixed(1).replace('.', ',') + ' bi' : v + ' mi');
  const max = Math.max(...data.partners.map(p => p.value), 1);
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "Rankings de parceiros exigem a dimens\xE3o de parceiro comercial, ainda n\xE3o dispon\xEDvel nesta fonte."
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: `Maior ${data.flowLabel}`,
    value: top?.name || '—',
    sub: fmt(top?.value || 0)
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Parceiros mapeados",
    value: data.partners.length,
    sub: `fluxo total ${fmt(total)}`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Concentra\xE7\xE3o top-3",
    value: window.fmtPct(data.partners.slice(0, 3).reduce((s, p) => s + p.value, 0) / total),
    sub: "do fluxo total"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Granularidade",
    value: banco?.scope || '—',
    sub: banco?.domain || ''
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Ranking · ${data.flowLabel}`,
    title: "Maiores parceiros comerciais",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, data.unit, " \xB7 exporta\xE7\xE3o + importa\xE7\xE3o")
  }), /*#__PURE__*/React.createElement("div", {
    className: "ptn-list"
  }, data.partners.map((p, i) => /*#__PURE__*/React.createElement("div", {
    key: p.name,
    className: "ptn-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ptn-rank tnum"
  }, "#", i + 1), /*#__PURE__*/React.createElement("span", {
    className: "ptn-name"
  }, p.name), /*#__PURE__*/React.createElement("div", {
    className: "ptn-bars"
  }, /*#__PURE__*/React.createElement("div", {
    className: "ptn-bar exp",
    style: {
      width: p.exp / max * 100 + '%'
    },
    title: 'Exportação ' + fmt(p.exp)
  }), /*#__PURE__*/React.createElement("div", {
    className: "ptn-bar imp",
    style: {
      width: p.imp / max * 100 + '%'
    },
    title: 'Importação ' + fmt(p.imp)
  })), /*#__PURE__*/React.createElement("span", {
    className: "ptn-val tnum"
  }, fmt(p.value))))), /*#__PURE__*/React.createElement("div", {
    className: "ptn-legend"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ptn-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ptn-legend-dot exp"
  }), "Exporta\xE7\xE3o"), /*#__PURE__*/React.createElement("span", {
    className: "ptn-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ptn-legend-dot imp"
  }), "Importa\xE7\xE3o"))));
}
window.ViewPartners = ViewPartners;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewPartners.jsx", error: String((e && e.message) || e) }); }

// ViewPerspectiveSoon.jsx
try { (() => {
// ViewPerspectiveSoon — placeholder for analytical perspectives that
// are planned but not yet built (the banco IS live, but this view isn't).
// Distinct from ViewComingSoon, which covers a whole banco awaiting ingest.

function ViewPerspectiveSoon({
  viewMeta
}) {
  if (!viewMeta) return null;
  const group = viewMeta.group;
  return /*#__PURE__*/React.createElement("div", {
    className: "cs-stack"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card ps-hero"
  }, /*#__PURE__*/React.createElement("div", {
    className: "ps-hero-l"
  }, /*#__PURE__*/React.createElement("div", {
    className: "cs-eyebrow"
  }, /*#__PURE__*/React.createElement("span", {
    className: "cs-badge"
  }, "Em breve"), group && /*#__PURE__*/React.createElement("span", {
    className: "caption"
  }, group.label, " \xB7 ", group.hint)), /*#__PURE__*/React.createElement("h2", {
    className: "cs-title"
  }, viewMeta.label), /*#__PURE__*/React.createElement("p", {
    className: "cs-sub"
  }, viewMeta.desc))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "O que esta perspectiva vai trazer",
    title: "Elementos planejados",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, viewMeta.planned?.length || 0, " blocos")
  }), /*#__PURE__*/React.createElement("div", {
    className: "ps-planned"
  }, (viewMeta.planned || []).map((p, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "ps-planned-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "ps-planned-num tnum"
  }, String(i + 1).padStart(2, '0')), /*#__PURE__*/React.createElement("span", {
    className: "ps-planned-text"
  }, p)))), /*#__PURE__*/React.createElement("div", {
    className: "cs-note"
  }, /*#__PURE__*/React.createElement(window.Icon, {
    name: "info",
    size: 14
  }), /*#__PURE__*/React.createElement("span", null, "Esta perspectiva j\xE1 est\xE1 prevista na arquitetura. Os filtros e conven\xE7\xF5es m\xE9tricas selecionados ser\xE3o aplicados automaticamente assim que ela for publicada \u2014 sem necessidade de reconfigurar a an\xE1lise."))));
}
window.ViewPerspectiveSoon = ViewPerspectiveSoon;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewPerspectiveSoon.jsx", error: String((e && e.message) || e) }); }

// ViewProductCompare.jsx
try { (() => {
// ViewProductCompare — compare 2–4 commodities side by side.
// Normalized series (base 100), accumulated change, CAGR, and pairwise
// correlation. Honours active filters (selectable products limited to
// the basket) and conventions (currency for the absolute table column).

const {
  useState: usePCState
} = React;
function ViewProductCompare({
  summary,
  conventions,
  database
}) {
  const conv = conventions || window.DEFAULT_CONVENTIONS;
  const cvf = window.convFactor(conv); // base-aware value factor

  const filtered = window.applyFilters(summary || {}, database);
  const available = filtered.selectedProducts.filter(c => filtered.allProductTS[c]);
  const COLORS = ['var(--viz-1)', 'var(--viz-3)', 'var(--viz-5)', 'var(--viz-7)'];
  const MAX = 4;

  // Default: top 3 by latest value
  const defaultSel = available.map(c => ({
    c,
    v: filtered.allProductTS[c].slice(-1)[0]?.v || 0
  })).sort((a, b) => b.v - a.v).slice(0, 3).map(x => x.c);
  const [sel, setSel] = usePCState(defaultSel);

  // Keep selection valid against the current basket
  const active = sel.filter(c => available.includes(c)).slice(0, MAX);
  const activeSel = active.length ? active : defaultSel;
  const toggle = c => {
    setSel(prev => {
      const cur = prev.filter(x => available.includes(x));
      if (cur.includes(c)) return cur.filter(x => x !== c);
      if (cur.length >= MAX) return cur; // cap at 4
      return [...cur, c];
    });
  };
  const yearStart = filtered.yearStart,
    yearEnd = filtered.yearEnd;

  // Build per-product windows + metrics
  const items = activeSel.map((code, i) => {
    const prod = filtered.products.find(p => p.code === code);
    const win = filtered.allProductTS[code].filter(d => d.y >= yearStart && d.y <= yearEnd);
    const v0 = win[0]?.v || 0,
      vT = win[win.length - 1]?.v || 0;
    return {
      code,
      prod,
      win,
      color: COLORS[i % COLORS.length],
      v0,
      vT,
      cagr: window.cagrPct(v0, vT, win.length - 1),
      accum: window.accumPct(v0, vT),
      absT: vT * 1e6 * cvf
    };
  });

  // Normalized series (base 100 at yearStart)
  const normSeries = items.map(it => ({
    name: it.prod.name,
    color: it.color,
    data: it.win.map(d => ({
      y: d.y,
      v: it.v0 ? d.v / it.v0 * 100 : 0
    }))
  }));

  // Pairwise Pearson correlation on YoY growth (shared helpers · seriesUtils.js)
  const growths = items.map(it => window.seriesGrowth(it.win));
  const corrMatrix = items.map((_, i) => items.map((_, j) => window.pearson(growths[i], growths[j])));
  const corrColor = window.corrColor;
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "pp-selector"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pp-selector-label"
  }, "Comparar commodities ", /*#__PURE__*/React.createElement("small", {
    className: "pc-cap"
  }, "(at\xE9 ", MAX, ")")), /*#__PURE__*/React.createElement("div", {
    className: "pp-chips"
  }, available.map(c => {
    const p = filtered.products.find(x => x.code === c);
    const on = activeSel.includes(c);
    const idx = activeSel.indexOf(c);
    const atCap = !on && activeSel.length >= MAX;
    return /*#__PURE__*/React.createElement("button", {
      key: c,
      className: 'pp-chip ' + (on ? 'on' : '') + (atCap ? ' disabled' : ''),
      onClick: () => !atCap && toggle(c),
      style: on ? {
        background: COLORS[idx % COLORS.length],
        borderColor: COLORS[idx % COLORS.length],
        color: '#fff'
      } : null,
      title: atCap ? `Máximo de ${MAX} commodities` : p.name
    }, /*#__PURE__*/React.createElement("span", {
      className: 'pp-chip-fam ' + p.family
    }), p.name);
  }))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Séries normalizadas · base 100 em ${yearStart}`,
    title: "Evolu\xE7\xE3o relativa do valor",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, items.length, " commodities")
  }), /*#__PURE__*/React.createElement(window.MultiLineChart, {
    series: normSeries,
    label: `índice (${yearStart}=100)`,
    valueKey: "v",
    height: 300
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-legend"
  }, items.map(it => /*#__PURE__*/React.createElement("span", {
    key: it.code,
    className: "pc-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-legend-dot",
    style: {
      background: it.color
    }
  }), it.prod.name)))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Métricas comparativas · ${yearStart}–${yearEnd}`,
    title: "Crescimento e magnitude"
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-table-wrap"
  }, /*#__PURE__*/React.createElement("table", {
    className: "pc-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Commodity"), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "Valor ", yearEnd), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "Varia\xE7\xE3o acumulada"), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "CAGR (a.a.)"), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "Fam\xEDlia"))), /*#__PURE__*/React.createElement("tbody", null, items.map(it => /*#__PURE__*/React.createElement("tr", {
    key: it.code
  }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("span", {
    className: "pc-row-dot",
    style: {
      background: it.color
    }
  }), it.prod.name), /*#__PURE__*/React.createElement("td", {
    className: "num tnum"
  }, window.formatValue(it.vT * 1e6, conv)), /*#__PURE__*/React.createElement("td", {
    className: "num tnum",
    style: {
      color: it.accum >= 0 ? 'var(--ok)' : 'var(--err)'
    }
  }, window.fmtSigned(it.accum, 0)), /*#__PURE__*/React.createElement("td", {
    className: "num tnum",
    style: {
      color: it.cagr >= 0 ? 'var(--ok)' : 'var(--err)'
    }
  }, window.fmtSigned(it.cagr, 1)), /*#__PURE__*/React.createElement("td", {
    className: "num"
  }, window.UNIT_FAMILIES[it.prod.family].label))))))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Correla\xE7\xE3o cruzada \xB7 varia\xE7\xE3o interanual",
    title: "Qu\xE3o sincronizadas s\xE3o as trajet\xF3rias",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "Pearson \xB7 \u22121 a +1")
  }), items.length < 2 ? /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '20px 4px',
      textAlign: 'center'
    }
  }, "Selecione ao menos 2 commodities para calcular correla\xE7\xE3o.") : /*#__PURE__*/React.createElement("div", {
    className: "pc-corr-wrap"
  }, /*#__PURE__*/React.createElement("table", {
    className: "pc-corr"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null), items.map(it => /*#__PURE__*/React.createElement("th", {
    key: it.code,
    title: it.prod.name
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-corr-dot",
    style: {
      background: it.color
    }
  }), it.prod.code)))), /*#__PURE__*/React.createElement("tbody", null, items.map((rowIt, i) => /*#__PURE__*/React.createElement("tr", {
    key: rowIt.code
  }, /*#__PURE__*/React.createElement("th", {
    title: rowIt.prod.name
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-corr-dot",
    style: {
      background: rowIt.color
    }
  }), rowIt.prod.name), items.map((colIt, j) => {
    const r = corrMatrix[i][j];
    return /*#__PURE__*/React.createElement("td", {
      key: colIt.code,
      className: "tnum",
      style: {
        background: i === j ? 'var(--bg-surface-2)' : corrColor(r),
        color: Math.abs(r) > 0.6 ? '#fff' : 'var(--fg-1)'
      }
    }, i === j ? '—' : r.toFixed(2).replace('.', ','));
  }))))), /*#__PURE__*/React.createElement("p", {
    className: "caption pc-corr-note"
  }, "Verde: trajet\xF3rias que sobem e descem juntas. Vermelho: movimentos opostos."))));
}
window.ViewProductCompare = ViewProductCompare;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewProductCompare.jsx", error: String((e && e.message) || e) }); }

// ViewProductProfile.jsx
try { (() => {
// ViewProductProfile — deep dive into a SINGLE commodity.
// Only meaningful for bancos that provide the 'product' capability.
// Honours active filters: the product selector is limited to the
// basket (filtered.selectedProducts); value/qty respect conventions.

const {
  useState: usePPState
} = React;
function ViewProductProfile({
  families,
  summary,
  database,
  conventions
}) {
  const conv = conventions || window.DEFAULT_CONVENTIONS;
  const monLabel = window.conventionMonetaryLabel(conv);
  const fx = window.CURRENCY_FX[conv.currency];
  const cvf = window.convFactor(conv); // base-aware value factor (corr × rate ÷ baseRate)

  const filtered = window.applyFilters(summary || {}, database);
  const available = filtered.selectedProducts.filter(c => filtered.allProductTS[c]);
  const hasGeo = filtered.ufDataFull.length > 0;
  // Code scheme label — declared per banco in bancos.js (dimensions.product),
  // not branched on bancoId here.
  const codeLabel = window.bancoDim(database, 'product').codeLabel || 'Código';

  // Selected product (default = largest by latest value within basket)
  const defaultCode = (() => {
    if (!available.length) return null;
    return available.map(c => ({
      c,
      v: filtered.allProductTS[c].slice(-1)[0]?.v || 0
    })).sort((a, b) => b.v - a.v)[0].c;
  })();
  const [code, setCode] = usePPState(defaultCode);
  const activeCode = code && available.includes(code) ? code : defaultCode;
  if (!activeCode) {
    return /*#__PURE__*/React.createElement("div", {
      className: "card subtle"
    }, /*#__PURE__*/React.createElement("p", {
      className: "caption",
      style: {
        padding: '20px 4px',
        textAlign: 'center'
      }
    }, "Nenhum produto dispon\xEDvel na sele\xE7\xE3o atual. Ajuste os filtros para escolher uma commodity."));
  }
  const prod = filtered.products.find(p => p.code === activeCode);
  const family = prod.family;
  const unitAx = family === 'mass' ? window.massAxisLabel(conv) : window.volumeAxisLabel(conv);
  const qtyMul = family === 'mass' ? window.massQtyMul(conv) : window.volumeQtyMul(conv);

  // Per-product series (PRODUCT_TS.v in base-currency mi, .q in thousands of native unit)
  const raw = filtered.allProductTS[activeCode];
  const yearStart = filtered.yearStart,
    yearEnd = filtered.yearEnd;
  const win = raw.filter(d => d.y >= yearStart && d.y <= yearEnd);

  // Total basket value per year (for market share within the cesta)
  const totalByYear = {};
  Object.values(filtered.productTS).forEach(series => {
    series.forEach(d => {
      totalByYear[d.y] = (totalByYear[d.y] || 0) + d.v;
    });
  });

  // Build display series
  const valueSeries = win.map(d => ({
    y: d.y,
    v: d.v * 1e6 * cvf
  })); // absolute currency
  const qtySeries = win.map(d => ({
    y: d.y,
    q: d.q * qtyMul
  })); // native unit (×mul)
  const priceSeries = win.map(d => ({
    y: d.y,
    v: d.v * 1e6 * cvf / (d.q * 1e3)
  })); // moeda/unidade
  const shareSeries = win.map(d => ({
    y: d.y,
    v: totalByYear[d.y] ? d.v / totalByYear[d.y] * 100 : 0
  }));
  const last = win[win.length - 1] || {
    v: 0,
    q: 0
  };
  const prev = win[win.length - 2] || last;
  const lastValAbs = last.v * 1e6 * cvf;
  const prevValAbs = prev.v * 1e6 * cvf;
  const deltaV = prevValAbs ? (lastValAbs - prevValAbs) / prevValAbs * 100 : 0;
  const lastPrice = last.v * 1e6 * cvf / (last.q * 1e3);
  const lastShare = totalByYear[last.y] ? last.v / totalByYear[last.y] * 100 : 0;

  // Per-product UF ranking — deterministic allocation of the product's
  // latest national value across UFs, biased by region affinity (data.js →
  // window.PRODUCT_REGION_AFFINITY, the single source) so the ranking is
  // plausible and product-specific.
  const aff = (window.PRODUCT_REGION_AFFINITY || {})[activeCode] || {};
  const ufAlloc = (() => {
    const seedChar = activeCode.charCodeAt(4);
    const weighted = filtered.ufDataFull.map((u, i) => {
      const base = u.value;
      const regionMul = aff[u.region] || 0.5;
      const jitter = 0.8 + 0.4 * Math.abs(Math.sin(i * 1.7 + seedChar));
      return {
        uf: u.uf,
        name: u.name,
        region: u.region,
        w: base * regionMul * jitter
      };
    });
    const totalW = weighted.reduce((s, u) => s + u.w, 0) || 1;
    const prodValAbs = lastValAbs;
    return weighted.map(u => ({
      ...u,
      value: u.w / totalW * prodValAbs
    })).sort((a, b) => b.value - a.value).slice(0, 10);
  })();
  const ufScaled = window.scaleSeries(ufAlloc, Math.max(...ufAlloc.map(u => u.value), 0), conv, 'value', fx.symbol);

  // Quality for this product (may be absent from the curated subset)
  const qaRow = filtered.qualityByProduct.find(r => r.code === activeCode);

  // Auto-scale value/qty/price series for charts
  const valScaled = window.scaleSeries(valueSeries, Math.max(...valueSeries.map(d => d.v), 0), conv, 'v', fx.symbol);
  const qtyScaled = window.scaleSeries(qtySeries, Math.max(...qtySeries.map(d => d.q), 0), conv, 'q', unitAx);
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "pp-selector"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pp-selector-label"
  }, "Commodity em an\xE1lise"), /*#__PURE__*/React.createElement("div", {
    className: "pp-chips"
  }, available.map(c => {
    const p = filtered.products.find(x => x.code === c);
    return /*#__PURE__*/React.createElement("button", {
      key: c,
      className: 'pp-chip ' + (c === activeCode ? 'on' : ''),
      onClick: () => setCode(c)
    }, /*#__PURE__*/React.createElement("span", {
      className: 'pp-chip-fam ' + p.family
    }), p.name);
  }))), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: `Valor · ${monLabel}`,
    value: window.formatValue(last.v * 1e6, conv),
    delta: window.fmtSigned(deltaV),
    deltaPositive: deltaV >= 0,
    sub: `${last.y} vs. ${prev.y}`,
    spark: win.slice(-12).map(d => ({
      y: d.y,
      v: d.v
    })),
    sparkKey: "v",
    sparkColor: "var(--viz-1)"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: /*#__PURE__*/React.createElement(React.Fragment, null, "Quantidade \xB7 ", /*#__PURE__*/React.createElement(window.UnitFamilyTag, {
      family: family,
      conv: conv
    })),
    value: (last.q * qtyMul).toLocaleString('pt-BR', {
      maximumFractionDigits: 0
    }) + ' ' + unitAx,
    delta: window.fmtSigned(prev.q ? (last.q - prev.q) / prev.q * 100 : 0),
    deltaPositive: last.q >= prev.q,
    sub: `${last.y} vs. ${prev.y}`,
    spark: win.slice(-12).map(d => ({
      y: d.y,
      q: d.q
    })),
    sparkKey: "q",
    sparkColor: family === 'mass' ? 'var(--viz-2)' : 'var(--viz-4)'
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Pre\xE7o m\xE9dio impl\xEDcito",
    value: fx.symbol + ' ' + lastPrice.toLocaleString('pt-BR', {
      maximumFractionDigits: 2
    }) + ' /' + prod.unit,
    sub: "valor \xF7 quantidade",
    spark: priceSeries.slice(-12),
    sparkKey: "v",
    sparkColor: "var(--viz-7)"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Participa\xE7\xE3o na cesta",
    value: window.fmtPct(lastShare / 100),
    sub: `${filtered.selectedProducts.length} ${filtered.selectedProducts.length === 1 ? 'produto' : 'produtos'} na cesta`,
    spark: shareSeries.slice(-12),
    sparkKey: "v",
    sparkColor: "var(--viz-5)"
  })), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Série de valor · ${monLabel}`,
    title: `${prod.name} · valor (${valScaled.label})`
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: valScaled.data,
    label: valScaled.label,
    valueKey: "v",
    color: "var(--viz-1)",
    height: 230
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: /*#__PURE__*/React.createElement(React.Fragment, null, "S\xE9rie de quantidade \xB7 ", /*#__PURE__*/React.createElement(window.UnitFamilyTag, {
      family: family,
      conv: conv
    })),
    title: `${prod.name} · quantidade (${qtyScaled.label})`
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: qtyScaled.data,
    label: qtyScaled.label,
    valueKey: "q",
    color: family === 'mass' ? 'var(--viz-2)' : 'var(--viz-4)',
    height: 230
  }))), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Pre\xE7o m\xE9dio impl\xEDcito \xB7 valor \xF7 quantidade",
    title: `${fx.symbol} por ${prod.unit} · ${yearStart}–${yearEnd}`
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: priceSeries,
    label: fx.symbol + '/' + prod.unit,
    valueKey: "v",
    color: "var(--viz-7)",
    height: 220
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Participa\xE7\xE3o na cesta \xB7 % do valor total",
    title: `Participação de ${prod.name} na cesta`
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: shareSeries,
    label: "% da cesta",
    valueKey: "v",
    color: "var(--viz-5)",
    height: 220
  }))), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, hasGeo && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Ranking de UFs produtoras · ${yearEnd}`,
    title: `Onde ${prod.name} é produzido`,
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "Top 10 \xB7 ", ufScaled.label)
  }), /*#__PURE__*/React.createElement(window.BarChart, {
    data: ufScaled.data,
    valueKey: "value",
    color: "var(--viz-2)",
    height: 320
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Ficha t\xE9cnica",
    title: prod.name
  }), /*#__PURE__*/React.createElement("dl", {
    className: "pp-spec"
  }, /*#__PURE__*/React.createElement("dt", null, codeLabel), /*#__PURE__*/React.createElement("dd", {
    className: "tnum"
  }, prod.code), /*#__PURE__*/React.createElement("dt", null, "Unidade nativa"), /*#__PURE__*/React.createElement("dd", null, prod.unit, " (", window.UNIT_FAMILIES[family].long, ")"), /*#__PURE__*/React.createElement("dt", null, "Fam\xEDlia de unidade"), /*#__PURE__*/React.createElement("dd", null, window.UNIT_FAMILIES[family].label), /*#__PURE__*/React.createElement("dt", null, "Cobertura temporal"), /*#__PURE__*/React.createElement("dd", {
    className: "tnum"
  }, yearStart, "\u2013", yearEnd), /*#__PURE__*/React.createElement("dt", null, "Valor (", last.y, ")"), /*#__PURE__*/React.createElement("dd", null, window.formatValue(last.v * 1e6, conv)), /*#__PURE__*/React.createElement("dt", null, "Participa\xE7\xE3o na cesta"), /*#__PURE__*/React.createElement("dd", null, window.fmtPct(lastShare / 100)), qaRow && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dt", null, "Linhas \xEDntegras (OK)"), /*#__PURE__*/React.createElement("dd", null, window.fmtPct(qaRow.OK))), qaRow && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dt", null, "Valor ausente"), /*#__PURE__*/React.createElement("dd", null, window.fmtPct(qaRow.MISSING_VALUE)))))));
}
window.ViewProductProfile = ViewProductProfile;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewProductProfile.jsx", error: String((e && e.message) || e) }); }

// ViewProductivity.jsx
try { (() => {
// ViewProductivity — agricultural AREA × YIELD perspective. Meaningful only
// for bancos that provide the 'yield' capability (IBGE PAM). Pick a crop and
// see its national yield/area trajectory plus the per-UF productivity geography.
//
// Self-data view: it reads its own synthetic adapter (window.productivityData),
// exactly like ViewFlows/ViewSeasonality. To go live, swap that adapter's body
// for a real query against the PAM Gold table — this component does not change.
// The beta caveat banner is rendered globally by MainScreen (window.MaturityBanner),
// so it is intentionally NOT repeated here.

const {
  useState: useProdState
} = React;
function ViewProductivity({
  summary,
  conventions,
  database
}) {
  const banco = window.bancoById(database);
  const [crop, setCrop] = useProdState(null);
  const data = window.productivityData(database, crop, summary);
  if (!data) {
    return /*#__PURE__*/React.createElement("div", {
      className: "card subtle"
    }, /*#__PURE__*/React.createElement("p", {
      className: "caption",
      style: {
        padding: '20px 4px',
        textAlign: 'center'
      }
    }, "Esta fonte n\xE3o exp\xF5e rendimento agr\xEDcola. Selecione um banco com a dimens\xE3o de produtividade."));
  }
  const activeCrop = data.crop.code;
  const yUnit = data.yieldUnit;
  const fmtY = v => window.numBR(Math.round(v), 0) + ' ' + yUnit;
  const fmtArea = v => v >= 1e6 ? window.numBR(v / 1e6, 1) + ' mi ha' : window.numBR(v / 1e3, 0) + ' mil ha';
  const fmtProd = v => v >= 1e6 ? window.numBR(v / 1e6, 1) + ' mi t' : window.numBR(v / 1e3, 0) + ' mil t';
  const series = data.series;
  const last = series[series.length - 1] || {
    y: 0,
    yieldKgHa: 0,
    areaHa: 0,
    prodT: 0
  };
  const prev = series[series.length - 2] || last;
  const yDelta = prev.yieldKgHa ? (last.yieldKgHa - prev.yieldKgHa) / prev.yieldKgHa * 100 : 0;
  const aDelta = prev.areaHa ? (last.areaHa - prev.areaHa) / prev.areaHa * 100 : 0;
  const mapData = data.byUF.map(u => ({
    ...u,
    yieldKgHa: Math.round(u.yieldKgHa)
  }));
  const byUFTop = data.byUF.slice().sort((a, b) => b.yieldKgHa - a.yieldKgHa).slice(0, 12).map(u => ({
    uf: u.uf,
    name: u.name,
    yieldKgHa: Math.round(u.yieldKgHa)
  }));
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "pp-selector"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pp-selector-label"
  }, "Lavoura em an\xE1lise"), /*#__PURE__*/React.createElement("div", {
    className: "pp-chips"
  }, data.crops.map(c => /*#__PURE__*/React.createElement("button", {
    key: c.code,
    className: 'pp-chip ' + (c.code === activeCrop ? 'on' : ''),
    onClick: () => setCrop(c.code)
  }, c.name)))), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: /*#__PURE__*/React.createElement(React.Fragment, null, "Rendimento nacional \xB7 ", /*#__PURE__*/React.createElement(window.UnitFamilyTag, {
      family: "rendimento",
      conv: conventions
    })),
    value: fmtY(last.yieldKgHa),
    delta: window.fmtSigned(yDelta),
    deltaPositive: yDelta >= 0,
    sub: `${last.y} vs. ${prev.y}`,
    spark: series.slice(-12).map(d => ({
      y: d.y,
      v: d.yieldKgHa
    })),
    sparkKey: "v",
    sparkColor: "var(--viz-6)"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "\xC1rea colhida",
    value: fmtArea(last.areaHa),
    delta: window.fmtSigned(aDelta),
    deltaPositive: aDelta >= 0,
    sub: `safra ${last.y}`,
    spark: series.slice(-12).map(d => ({
      y: d.y,
      v: d.areaHa
    })),
    sparkKey: "v",
    sparkColor: "var(--viz-10)"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Produ\xE7\xE3o",
    value: fmtProd(last.prodT),
    sub: `rendimento × área · ${last.y}`,
    spark: series.slice(-12).map(d => ({
      y: d.y,
      v: d.prodT
    })),
    sparkKey: "v",
    sparkColor: "var(--viz-2)"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "CAGR do rendimento",
    value: window.fmtSigned(data.national.yieldCagr),
    sub: `ganho de produtividade · ${series[0].y}–${last.y}`,
    spark: series.slice(-12).map(d => ({
      y: d.y,
      v: d.yieldKgHa
    })),
    sparkKey: "v",
    sparkColor: "var(--viz-7)"
  })), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Rendimento médio · ${yUnit}`,
    title: `${data.crop.name} · produtividade nacional`
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: series.map(d => ({
      y: d.y,
      v: Math.round(d.yieldKgHa)
    })),
    label: yUnit,
    valueKey: "v",
    color: "var(--viz-6)",
    height: 230
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Área colhida · ${data.areaUnit}`,
    title: `${data.crop.name} · área colhida`
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: series.map(d => ({
      y: d.y,
      v: Math.round(d.areaHa)
    })),
    label: data.areaUnit,
    valueKey: "v",
    color: "var(--viz-10)",
    height: 230
  }))), /*#__PURE__*/React.createElement("div", {
    className: "grid-2"
  }, /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Produtividade por UF · ${last.y}`,
    title: `Onde ${data.crop.name} rende mais`,
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, yUnit)
  }), /*#__PURE__*/React.createElement(window.BrazilTileMap, {
    data: mapData,
    valueKey: "yieldKgHa",
    label: yUnit,
    height: 420
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Ranking de rendimento · ${last.y}`,
    title: "UFs mais produtivas",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "Top 12 \xB7 ", yUnit)
  }), /*#__PURE__*/React.createElement(window.BarChart, {
    data: byUFTop,
    valueKey: "yieldKgHa",
    color: "var(--viz-6)",
    height: 360
  }))));
}
window.ViewProductivity = ViewProductivity;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewProductivity.jsx", error: String((e && e.message) || e) }); }

// ViewQuality.jsx
try { (() => {
// ViewQuality — data-quality diagnostics across the banco.
// Honours active filters: selected flags, selected products (per-product
// breakdown), selected UFs (geographic quality map), and year window.

// Maps each data_quality_flag id to its key in window.QUALITY_TS.
// Most are just the lowercased id, but BOUNDARY_HISTORIC is stored as
// `boundary` in the time series — without this map that band renders
// flat-zero and the temporal stack never reaches 100%.
const QTS_KEY = {
  OK: 'ok',
  ESTIMATED: 'estimated',
  MISSING_VALUE: 'missing_value',
  MISSING_QUANTITY: 'missing_quantity',
  OUTLIER: 'outlier',
  BOUNDARY_HISTORIC: 'boundary'
};
function ViewQuality({
  summary,
  database
}) {
  const filtered = window.applyFilters(summary || {}, database);
  const flags = filtered.qualityFlags;
  const ts = filtered.qualityTs;
  const total = flags.reduce((s, f) => s + f.count, 0) || 1;
  const okFlag = flags.find(f => f.id === 'OK');
  const okCount = okFlag ? okFlag.count : 0;
  const flagSet = new Set(flags.map(f => f.id));
  // Restrict per-product breakdown to selected products AND selected flags.
  // We zero out unselected flag columns and re-normalize each row.
  const selectedProductNames = new Set(filtered.selectedProducts.map(c => (filtered.products.find(p => p.code === c) || {}).name).filter(Boolean));
  const qaByProduct = filtered.qualityByProduct.filter(r => selectedProductNames.has(r.name)).map(r => {
    const row = {
      code: r.code,
      name: r.name
    };
    let sum = 0;
    window.QUALITY_FLAGS.forEach(f => {
      const v = flagSet.has(f.id) ? r[f.id] || 0 : 0;
      row[f.id] = v;
      sum += v;
    });
    // re-normalize to 100% of the selected flag world
    if (sum > 0) window.QUALITY_FLAGS.forEach(f => {
      row[f.id] = row[f.id] / sum;
    });
    return row;
  });

  // Restrict geographic quality map to selected UFs. null = no filter (all);
  // explicit empty = none (consistent with the data layer).
  const stateSet = summary && summary.states != null ? new Set(summary.states) : null;
  const qaByUf = filtered.qualityByUf.filter(u => !stateSet || stateSet.has(u.uf));
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "qa-flag-row"
  }, flags.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "qa-flag-card",
    style: {
      gridColumn: '1 / -1'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "qa-flag-label"
  }, "Nenhuma flag selecionada nos filtros.")) : flags.map(f => /*#__PURE__*/React.createElement("div", {
    key: f.id,
    className: "qa-flag-card"
  }, /*#__PURE__*/React.createElement("div", {
    className: "qa-flag-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "qa-dot",
    style: {
      background: f.color
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "qa-flag-label"
  }, f.label)), /*#__PURE__*/React.createElement("div", {
    className: "qa-flag-val tnum",
    style: {
      color: f.id === 'OK' ? 'var(--ok)' : 'var(--fg-1)'
    }
  }, window.fmtPct(f.share)), /*#__PURE__*/React.createElement("div", {
    className: "qa-flag-sub tnum"
  }, f.count.toLocaleString('pt-BR'), " linhas")))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Evolu\xE7\xE3o temporal \xB7 qualidade dos dados",
    title: `% de linhas íntegras (flag = OK) · ${filtered.yearStart}–${filtered.yearEnd}`,
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, okCount ? okCount.toLocaleString('pt-BR') : '—', " de ", total.toLocaleString('pt-BR'), " linhas \xEDntegras")
  }), okFlag ? /*#__PURE__*/React.createElement(window.LineChart, {
    data: ts.map(d => ({
      y: d.y,
      v: d.ok * 100
    })),
    label: "% OK",
    valueKey: "v",
    color: "var(--ok)",
    height: 240
  }) : /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '24px 4px',
      textAlign: 'center'
    }
  }, "Flag ", /*#__PURE__*/React.createElement("code", null, "OK"), " n\xE3o est\xE1 entre as selecionadas nos filtros.")), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Distribuição de flags · ${filtered.yearEnd}`,
    title: "Por produto",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, qaByProduct.length, " de ", filtered.qualityByProduct.length, " produtos")
  }), qaByProduct.length === 0 ? /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '24px 4px',
      textAlign: 'center'
    }
  }, "Nenhum produto selecionado nos filtros.") : /*#__PURE__*/React.createElement(window.FlagBars, {
    rows: qaByProduct,
    flags: flags,
    labelKey: "name"
  }), /*#__PURE__*/React.createElement("div", {
    className: "qa-legend"
  }, flags.map(f => /*#__PURE__*/React.createElement("span", {
    key: f.id,
    className: "qa-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "qa-dot",
    style: {
      background: f.color
    }
  }), f.label)))), filtered.qualityByUf.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Qualidade geográfica · ${filtered.yearEnd}`,
    title: "% de linhas n\xE3o-\xEDntegras por UF",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, qaByUf.length, " de ", filtered.qualityByUf.length, " UFs")
  }), /*#__PURE__*/React.createElement(window.BrazilTileMap, {
    data: qaByUf.map(u => ({
      ...u,
      v: Math.round(u.not_ok * 1000) / 10
    })),
    valueKey: "v",
    label: "% \u2260 OK"
  })), flags.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Composi\xE7\xE3o temporal \xB7 flags",
    title: `Share por flag · ${filtered.yearStart}–${filtered.yearEnd}`
  }), /*#__PURE__*/React.createElement(window.StackedArea, {
    series: flags.slice().reverse().map(f => ({
      code: f.id,
      name: f.label,
      color: f.color,
      data: ts.map(d => ({
        y: d.y,
        v: (d[QTS_KEY[f.id] || f.id.toLowerCase()] || 0) * 100
      }))
    })),
    valueKey: "v",
    label: "% linhas",
    height: 260
  }), /*#__PURE__*/React.createElement("div", {
    className: "qa-legend"
  }, flags.map(f => /*#__PURE__*/React.createElement("span", {
    key: f.id,
    className: "qa-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "qa-dot",
    style: {
      background: f.color
    }
  }), f.label)))));
}
window.ViewQuality = ViewQuality;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewQuality.jsx", error: String((e && e.message) || e) }); }

// ViewSeasonality.jsx
try { (() => {
// ViewSeasonality — month × year patterns. Generic via the monthlyData
// contract. Synthetic preview until a banco with monthly granularity is live.

function ViewSeasonality({
  summary,
  conventions,
  database
}) {
  const banco = window.bancoById(database);
  const data = window.monthlyData(database, summary);
  const peakIdx = data.monthlyAvg.indexOf(Math.max(...data.monthlyAvg));
  const lowIdx = data.monthlyAvg.indexOf(Math.min(...data.monthlyAvg));
  const amplitude = data.monthlyAvg[peakIdx] / (data.monthlyAvg[lowIdx] || 1);
  const fmt = v => data.unit + ' ' + v.toLocaleString('pt-BR');
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "A an\xE1lise sazonal exige granularidade mensal/di\xE1ria, ainda n\xE3o dispon\xEDvel nesta fonte."
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "M\xEAs de pico",
    value: window.MONTH_LABELS[peakIdx],
    sub: fmt(data.monthlyAvg[peakIdx]) + ' (média)'
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "M\xEAs de vale",
    value: window.MONTH_LABELS[lowIdx],
    sub: fmt(data.monthlyAvg[lowIdx]) + ' (média)'
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Amplitude sazonal",
    value: '×' + amplitude.toFixed(2).replace('.', ','),
    sub: "pico \xF7 vale"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Cobertura",
    value: data.years.length + ' anos',
    sub: `${data.years[0]}–${data.years[data.years.length - 1]}`
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Mapa de calor \xB7 m\xEAs \xD7 ano",
    title: "Padr\xE3o sazonal ao longo dos anos",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, data.unit, " \xB7 valores ilustrativos")
  }), /*#__PURE__*/React.createElement(window.MonthYearHeatmap, {
    matrix: data.matrix,
    years: data.years,
    unit: data.unit
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Perfil sazonal m\xE9dio",
    title: "M\xE9dia de cada m\xEAs no per\xEDodo"
  }), /*#__PURE__*/React.createElement(window.BarChart, {
    data: data.monthlyAvg.map((v, m) => ({
      name: window.MONTH_LABELS[m],
      value: v
    })),
    valueKey: "value",
    color: "var(--viz-3)",
    height: 300
  })));
}
window.ViewSeasonality = ViewSeasonality;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewSeasonality.jsx", error: String((e && e.message) || e) }); }

// ViewValueVolume.jsx
try { (() => {
// ViewValueVolume — historic evolution of value and quantity,
// with quantity strictly segregated by unit family.
// All currency / correction / mass / volume formatting goes through
// the global metric conventions (props.conventions).

function ViewValueVolume({
  families,
  conventions,
  summary,
  database
}) {
  const conv = conventions || window.DEFAULT_CONVENTIONS;
  const ccyLabel = window.conventionMonetaryLabel(conv);
  const fx = window.CURRENCY_FX[conv.currency];
  const ccyColor = {
    BRL: 'var(--viz-1)',
    USD: 'var(--viz-2)',
    EUR: 'var(--viz-3)',
    CNY: 'var(--viz-4)'
  }[conv.currency];
  const massMul = window.massQtyMul(conv);
  const volMul = window.volumeQtyMul(conv);
  const massAx = window.massAxisLabel(conv);
  const volAx = window.volumeAxisLabel(conv);

  // Scale internal units to absolute (no auto-rescale on display).
  //   ts.v       : R$ bi  → R$
  //   d.q_mass   : mil t  → t   (× massQtyMul handles t→kg too)
  //   d.q_vol    : mi m³  → m³  (× volumeQtyMul handles m³→L too)
  const filtered = window.applyFilters(summary || {}, database);
  const ts = filtered.ts.map(d => ({
    ...d,
    v: d.v * 1e9
  }));
  const valueSeries = window.convertSeries(ts, conv);
  // massMul / volMul map (mil t, mi m³) → (t/kg, m³/L)
  const massSeries = ts.map(d => ({
    y: d.y,
    q_mass: d.q_mass * massMul
  }));
  const volSeries = ts.map(d => ({
    y: d.y,
    q_vol: d.q_vol * volMul
  }));

  // Per-product stacked series — split by family, scaled by current units
  const PRODS = filtered.products;
  const COLORS = [...window.VIZ_SCALE, 'var(--pres-gray-200)', 'var(--pres-gray-300)'];
  const productSeries = family => Object.entries(filtered.productTS).map(([code, data], i) => ({
    code,
    name: PRODS.find(p => p.code === code)?.name || code,
    family: data[0]?.family,
    // PRODUCT_TS.q is in mil units (mil t / mi m³); scale to display unit.
    data: data.map(d => ({
      ...d,
      q: d.q * (family === 'mass' ? massMul : volMul)
    })),
    color: COLORS[i % COLORS.length]
  })).filter(s => s.family === family);

  // Value-stacked applies currency + correction (base-aware).
  const cvf = window.convFactor(conv);
  // PRODUCT_TS.v is in base-currency mi internally; multiply 1e6 to absolute.
  const valueStacked = Object.entries(filtered.productTS).map(([code, data], i) => ({
    code,
    name: PRODS.find(p => p.code === code)?.name || code,
    data: data.map(d => ({
      ...d,
      v: d.v * 1e6 * cvf
    })),
    color: COLORS[i % COLORS.length]
  }));

  // ---- Scale series for charts when auto-scale is enabled ----------
  const valueMax = Math.max(...valueSeries.map(d => d.v), 0);
  const valueScaled = window.scaleSeries(valueSeries, valueMax, conv, 'v', fx.symbol);
  const massMax = Math.max(...massSeries.map(d => d.q_mass), 0);
  const massScaled = window.scaleSeries(massSeries, massMax, conv, 'q_mass', massAx);
  const volMax = Math.max(...volSeries.map(d => d.q_vol), 0);
  const volScaled = window.scaleSeries(volSeries, volMax, conv, 'q_vol', volAx);

  // Stacked: scale each layer using the same factor (sum-based ref)
  const _scaleStack = (layers, key, unit) => {
    if (!layers.length || !layers[0].data.length) return {
      layers,
      label: unit
    };
    if (!conv.autoScale) return {
      layers,
      label: unit
    };
    const yearTotals = layers[0].data.map((_, i) => layers.reduce((s, l) => s + (l.data[i][key] || 0), 0));
    const max = Math.max(...yearTotals);
    const {
      factor,
      suffix
    } = window.autoScaleNum(max);
    if (!suffix) return {
      layers,
      label: unit
    };
    const CURRENCY_SYMS = ['R$', 'US$', '€', '¥'];
    const out = layers.map(l => ({
      ...l,
      data: l.data.map(d => ({
        ...d,
        [key]: d[key] / factor
      }))
    }));
    const label = CURRENCY_SYMS.includes(unit) ? `${unit} ${suffix}` : `${suffix} ${unit}`.trim();
    return {
      layers: out,
      label
    };
  };
  const valueStackScaled = _scaleStack(valueStacked, 'v', fx.symbol);
  const massStackScaled = _scaleStack(productSeries('mass'), 'q', massAx);
  const volStackScaled = _scaleStack(productSeries('volume'), 'q', volAx);
  const last = valueSeries[valueSeries.length - 1] || {
    v: 0
  };
  const first = valueSeries[0] || {
    v: 0
  };
  const totalDelta = first.v ? (last.v - first.v) / first.v * 100 : 0;
  const yearStart = filtered.yearStart;
  const yearEnd = filtered.yearEnd;
  const massFamily = families.includes('mass');
  const volFamily = families.includes('volume');
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.UnitFamilyBanner, {
    families: families
  }), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Série histórica · ${ccyLabel}`,
    title: `Valor total · ${valueScaled.label} · ${yearStart}–${yearEnd}`,
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "Varia\xE7\xE3o acumulada: ", /*#__PURE__*/React.createElement("strong", null, window.fmtSigned(totalDelta, 0)))
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: valueScaled.data,
    label: valueScaled.label,
    valueKey: "v",
    color: ccyColor,
    height: 260
  })), /*#__PURE__*/React.createElement("div", {
    className: 'grid-' + (families.length === 2 ? '2' : '1')
  }, massFamily && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: /*#__PURE__*/React.createElement(React.Fragment, null, "S\xE9rie hist\xF3rica \xB7 ", /*#__PURE__*/React.createElement(window.UnitFamilyTag, {
      family: "mass",
      conv: conv
    })),
    title: `Quantidade · ${massScaled.label}`
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: massScaled.data,
    label: massScaled.label,
    valueKey: "q_mass",
    color: "var(--viz-2)",
    height: 220
  })), volFamily && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: /*#__PURE__*/React.createElement(React.Fragment, null, "S\xE9rie hist\xF3rica \xB7 ", /*#__PURE__*/React.createElement(window.UnitFamilyTag, {
      family: "volume",
      conv: conv
    })),
    title: `Quantidade · ${volScaled.label}`
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: volScaled.data,
    label: volScaled.label,
    valueKey: "q_vol",
    color: "var(--viz-4)",
    height: 220
  }))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Variação interanual · valor (${ccyLabel})`,
    title: `Crescimento ano a ano · ${yearStart + 1}–${yearEnd}`
  }), /*#__PURE__*/React.createElement(window.YoYBars, {
    data: valueSeries,
    valueKey: "v",
    height: 200
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: `Composição histórica · valor (${valueStackScaled.label})`,
    title: `Empilhamento por produto · ${yearStart}–${yearEnd}`
  }), /*#__PURE__*/React.createElement(window.StackedArea, {
    series: valueStackScaled.layers,
    valueKey: "v",
    label: valueStackScaled.label,
    height: 280
  })), /*#__PURE__*/React.createElement("div", {
    className: 'grid-' + (families.length === 2 ? '2' : '1')
  }, massFamily && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: /*#__PURE__*/React.createElement(React.Fragment, null, "Composi\xE7\xE3o hist\xF3rica \xB7 quantidade ", /*#__PURE__*/React.createElement(window.UnitFamilyTag, {
      family: "mass",
      conv: conv
    })),
    title: `Produtos em massa · ${massStackScaled.label}`
  }), /*#__PURE__*/React.createElement(window.StackedArea, {
    series: massStackScaled.layers,
    valueKey: "q",
    label: massStackScaled.label,
    height: 240
  })), volFamily && /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: /*#__PURE__*/React.createElement(React.Fragment, null, "Composi\xE7\xE3o hist\xF3rica \xB7 quantidade ", /*#__PURE__*/React.createElement(window.UnitFamilyTag, {
      family: "volume",
      conv: conv
    })),
    title: `Produtos em volume · ${volStackScaled.label}`
  }), /*#__PURE__*/React.createElement(window.StackedArea, {
    series: volStackScaled.layers,
    valueKey: "q",
    label: volStackScaled.label,
    height: 240
  }))));
}
window.ViewValueVolume = ViewValueVolume;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewValueVolume.jsx", error: String((e && e.message) || e) }); }

// ViewsChain.jsx
try { (() => {
// ViewsChain.jsx — the two EXTENDED multi-source perspectives:
//   · ViewChainBalance — supply balance across PEVS→SEFAZ→MDIC→Comtrade
//                        (reconciled mass split + world-market slice).
//   · ViewHarvestLag   — harvest (PEVS, modeled monthly) vs shipments
//                        (MDIC monthly): how many months exports lag the crop.
// Both read crossChain.js contracts and reuse existing charts.

const {
  useState: useChState
} = React;
const chNum = window.numBR,
  chPct = window.pctBR;

// ── (5) Chain balance ──────────────────────────────────────────────────
function ViewChainBalance({
  view
}) {
  const [product, setProduct] = useChState(null);
  const [year, setYear] = useChState(2024);
  const data = window.chainBalance(product, year);
  const banco = window.crossPreviewBanco(view);
  const years = [];
  for (let y = 2024; y >= 1997; y--) years.push(y);
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "Produ\xE7\xE3o \xE9 real (IBGE); a divis\xE3o entre interno (SEFAZ), exportado (MDIC) e o mercado mundial (Comtrade) entra como demonstra\xE7\xE3o at\xE9 essas fontes serem ligadas."
  }), /*#__PURE__*/React.createElement("div", {
    className: "ch-toolbar"
  }, /*#__PURE__*/React.createElement(window.CrossProductPicker, {
    value: product,
    onChange: setProduct
  }), /*#__PURE__*/React.createElement("div", {
    className: "ch-year"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pp-selector-label"
  }, "Ano"), /*#__PURE__*/React.createElement("select", {
    className: "xs-select",
    value: year,
    onChange: e => setYear(Number(e.target.value))
  }, years.map(y => /*#__PURE__*/React.createElement("option", {
    key: y,
    value: y
  }, y))))), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Produ\xE7\xE3o",
    value: chNum(data.produced) + ' mil t',
    sub: `${year} · base do balanço`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Exportado",
    value: chPct(data.expFrac * 100),
    sub: `${chNum(data.exported)} mil t p/ fora`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Com\xE9rcio interno",
    value: chPct(data.intFrac * 100),
    sub: `${chNum(data.internal)} mil t entre UFs`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Fatia no mundo",
    value: chPct(data.worldShare),
    sub: `exportação ÷ mercado mundial`
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Balan\xE7o de oferta \xB7 massa conservada",
    title: "Para onde vai o que se produz",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "mil t \xB7 IBGE \u2192 SEFAZ \xB7 MDIC")
  }), /*#__PURE__*/React.createElement(window.SankeyChart, {
    nodes: data.sankey.nodes,
    links: data.sankey.links,
    unit: "mil t",
    height: 300
  }), /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '8px 4px 0'
    }
  }, "Conserva\xE7\xE3o f\xEDsica: ", /*#__PURE__*/React.createElement("strong", null, "produ\xE7\xE3o = com\xE9rcio interno + exporta\xE7\xE3o + consumo/estoque"), ". O res\xEDduo (consumo dom\xE9stico e estoque) \xE9 o que sobra do balan\xE7o \u2014 algo que nenhuma fonte isolada calcula.")), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Da exporta\xE7\xE3o ao mercado mundial",
    title: "O quanto o Brasil representa l\xE1 fora",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "base valor \xB7 MDIC \xF7 Comtrade")
  }), /*#__PURE__*/React.createElement("div", {
    className: "ch-world"
  }, /*#__PURE__*/React.createElement("div", {
    className: "ch-world-bar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "ch-world-fill",
    style: {
      width: Math.max(2, Math.min(100, data.worldShare)) + '%'
    }
  }, /*#__PURE__*/React.createElement("span", null, "Brasil \xB7 ", chPct(data.worldShare))), /*#__PURE__*/React.createElement("span", {
    className: "ch-world-rest"
  }, "resto do mundo")), /*#__PURE__*/React.createElement("div", {
    className: "ch-world-meta"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Exporta\xE7\xE3o BR"), /*#__PURE__*/React.createElement("strong", null, "US$ ", chNum(data.exportUsd, 1), " bi")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "meta-label"
  }, "Mercado mundial"), /*#__PURE__*/React.createElement("strong", null, "US$ ", chNum(data.worldTotal), " bi"))))));
}

// ── (6) Harvest → shipment lag ──────────────────────────────────────
function ViewHarvestLag({
  view
}) {
  const [product, setProduct] = useChState(null);
  const data = window.harvestShipmentLag(product);
  const banco = window.crossPreviewBanco(view);
  const series = [{
    name: 'Safra (produção)',
    color: 'var(--viz-2)',
    data: data.production
  }, {
    name: 'Embarques (exportação)',
    color: 'var(--viz-3)',
    data: data.shipments
  }];
  const markers = [{
    month: data.peakHarvest,
    color: 'var(--viz-2)'
  }, {
    month: data.peakShip,
    color: 'var(--viz-3)'
  }];
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "Os embarques mensais entram como demonstra\xE7\xE3o at\xE9 o MDIC ser ligado; o perfil mensal da safra \xE9 modelado a partir do total anual do IBGE (que n\xE3o publica produ\xE7\xE3o mensal)."
  }), /*#__PURE__*/React.createElement(window.CrossProductPicker, {
    value: product,
    onChange: setProduct
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Defasagem",
    value: `${data.lagMonths >= 0 ? '+' : ''}${data.lagMonths} ${Math.abs(data.lagMonths) === 1 ? 'mês' : 'meses'}`,
    sub: "embarques ap\xF3s a safra"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Correla\xE7\xE3o no lag",
    value: data.corrAtLag.toFixed(2).replace('.', ','),
    sub: "alinhamento safra \xD7 embarque"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Pico da safra",
    value: data.months[data.peakHarvest],
    sub: "m\xEAs de maior produ\xE7\xE3o"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Pico de embarque",
    value: data.months[data.peakShip],
    sub: "m\xEAs de maior exporta\xE7\xE3o"
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Perfil mensal \xB7 safra vs. embarque",
    title: "Quando se colhe e quando se embarca",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "\xEDndice (pico = 100) \xB7 IBGE \xD7 MDIC")
  }), /*#__PURE__*/React.createElement(window.MonthlyOverlay, {
    series: series,
    months: data.months,
    markers: markers
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-legend"
  }, series.map(s => /*#__PURE__*/React.createElement("span", {
    key: s.name,
    className: "pc-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-legend-dot",
    style: {
      background: s.color
    }
  }), s.name)))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Correla\xE7\xE3o por defasagem",
    title: "Em que defasagem os dois se alinham",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "r \xB7 embarques deslocados \xB16 meses")
  }), /*#__PURE__*/React.createElement(window.LagBars, {
    profile: data.lagProfile,
    best: {
      lag: data.lagMonths,
      corr: data.corrAtLag
    }
  }), /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '8px 4px 0'
    }
  }, "A barra verde marca a defasagem de maior correla\xE7\xE3o: os embarques seguem o pico da safra em", /*#__PURE__*/React.createElement("strong", null, " ", data.lagMonths >= 0 ? data.lagMonths : 0, " ", Math.abs(data.lagMonths) === 1 ? 'mês' : 'meses'), ". S\xF3 vis\xEDvel com granularidade mensal \u2014 invis\xEDvel em dado anual.")));
}
Object.assign(window, {
  ViewChainBalance,
  ViewHarvestLag
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewsChain.jsx", error: String((e && e.message) || e) }); }

// ViewsMultiSource.jsx
try { (() => {
// ViewsMultiSource.jsx — the four analytical multi-source perspectives.
// All read through crossAnalytics.js contracts; all are self-contained
// (own commodity selector), since unlike "Cruzamento entre fontes" they
// don't need a lifted multi-series selection. Charts are reused as-is.

const {
  useState: useMSState
} = React;

// Shared commodity selector (single-select; null = whole basket).
function CrossProductPicker({
  value,
  onChange
}) {
  const prods = window.PRODUCTS || [];
  return /*#__PURE__*/React.createElement("div", {
    className: "pp-selector"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pp-selector-label"
  }, "Commodity"), /*#__PURE__*/React.createElement("div", {
    className: "pp-chips"
  }, /*#__PURE__*/React.createElement("button", {
    className: 'pp-chip ' + (!value ? 'on' : ''),
    onClick: () => onChange(null),
    style: !value ? {
      background: 'var(--embrapa-green)',
      borderColor: 'var(--embrapa-green)',
      color: '#fff'
    } : null
  }, "Cesta completa"), prods.map(p => {
    const on = value === p.code;
    return /*#__PURE__*/React.createElement("button", {
      key: p.code,
      className: 'pp-chip ' + (on ? 'on' : ''),
      onClick: () => onChange(p.code),
      style: on ? {
        background: 'var(--embrapa-green)',
        borderColor: 'var(--embrapa-green)',
        color: '#fff'
      } : null,
      title: p.name
    }, /*#__PURE__*/React.createElement("span", {
      className: 'pp-chip-fam ' + p.family
    }), p.name);
  })));
}
const msNum = window.numBR,
  msPct = window.pctBR;

// ── (1) Export coefficient ──────────────────────────────────────────────────
function ViewExportCoef({
  view
}) {
  const [product, setProduct] = useMSState(null);
  const data = window.exportCoefficient(product);
  const banco = window.crossPreviewBanco(view);
  const ranked = data.byUf.filter(u => u.production > 0).sort((a, b) => b.coefPct - a.coefPct);
  const top = ranked[0],
    bottom = ranked[ranked.length - 1];
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "Produ\xE7\xE3o \xE9 real (IBGE); a parcela exportada por UF entra como demonstra\xE7\xE3o at\xE9 o MDIC ser ligado."
  }), /*#__PURE__*/React.createElement(CrossProductPicker, {
    value: product,
    onChange: setProduct
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Coeficiente nacional",
    value: msPct(data.national.coefPct),
    sub: "do produzido segue p/ exporta\xE7\xE3o"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "UF mais exportadora",
    value: top?.uf || '—',
    sub: `${msPct(top?.coefPct || 0)} da produção`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "UF mais interna",
    value: bottom?.uf || '—',
    sub: `${msPct(bottom?.coefPct || 0)} exportado`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Produ\xE7\xE3o considerada",
    value: msNum(data.national.production) + ' mil t',
    sub: `${ranked.length} ${ranked.length === 1 ? 'UF' : 'UFs'} com produção`
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Orienta\xE7\xE3o exportadora \xB7 por UF",
    title: "Quanto da produ\xE7\xE3o de cada estado vai para fora",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "% exportado \xB7 IBGE \xD7 MDIC")
  }), /*#__PURE__*/React.createElement(window.BrazilTileMap, {
    data: data.byUf,
    valueKey: "coefPct",
    label: "% exportado"
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Coeficiente nacional no tempo",
    title: "Evolu\xE7\xE3o da orienta\xE7\xE3o exportadora",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "1997\u20132024 \xB7 valores ilustrativos")
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: data.timeseries,
    valueKey: "v",
    label: "%",
    color: "var(--embrapa-green)",
    height: 260
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Ranking \xB7 maior orienta\xE7\xE3o exportadora",
    title: "UFs por coeficiente"
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-table-wrap"
  }, /*#__PURE__*/React.createElement("table", {
    className: "pc-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "UF"), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "Produ\xE7\xE3o (mil t)"), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "Exportado (mil t)"), /*#__PURE__*/React.createElement("th", {
    className: "num"
  }, "Coeficiente"))), /*#__PURE__*/React.createElement("tbody", null, ranked.slice(0, 10).map(u => /*#__PURE__*/React.createElement("tr", {
    key: u.uf
  }, /*#__PURE__*/React.createElement("td", null, u.name, " ", /*#__PURE__*/React.createElement("small", {
    style: {
      color: 'var(--fg-3)'
    }
  }, u.uf)), /*#__PURE__*/React.createElement("td", {
    className: "num tnum"
  }, msNum(u.production, 1)), /*#__PURE__*/React.createElement("td", {
    className: "num tnum"
  }, msNum(u.exportV, 1)), /*#__PURE__*/React.createElement("td", {
    className: "num tnum",
    style: {
      color: 'var(--embrapa-green-darker)',
      fontWeight: 600
    }
  }, msPct(u.coefPct)))))))));
}

// ── (2) Brazil in the world market ─────────────────────────────────────
function ViewMarketShare({
  view
}) {
  const [product, setProduct] = useMSState(null);
  const data = window.marketShare(product);
  const banco = window.crossPreviewBanco(view);
  const last = data.series[data.series.length - 1];
  const first = data.series[0];
  const peak = data.series.reduce((m, d) => d.share > m.share ? d : m, data.series[0]);
  const shareTs = data.series.map(d => ({
    y: d.y,
    v: d.share
  }));
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "Exporta\xE7\xE3o brasileira e total mundial entram como demonstra\xE7\xE3o at\xE9 MDIC e UN Comtrade serem ligados."
  }), /*#__PURE__*/React.createElement(CrossProductPicker, {
    value: product,
    onChange: setProduct
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Participa\xE7\xE3o atual",
    value: msPct(last?.share),
    sub: `${last?.y} · do mercado mundial`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Pico hist\xF3rico",
    value: msPct(peak?.share),
    sub: `em ${peak?.y}`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Varia\xE7\xE3o na janela",
    value: window.fmtSigned((last?.share || 0) - (first?.share || 0), 1, ' p.p.'),
    deltaPositive: (last?.share || 0) >= (first?.share || 0),
    sub: `${first?.y}–${last?.y}`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Exporta\xE7\xE3o BR",
    value: 'US$ ' + msNum(last?.br, 1) + ' bi',
    sub: `mundo: US$ ${msNum(last?.world)} bi`
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Participa\xE7\xE3o no mercado mundial",
    title: "Fra\xE7\xE3o brasileira da exporta\xE7\xE3o global",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "% \xB7 MDIC \xF7 UN Comtrade")
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: shareTs,
    valueKey: "v",
    label: "% do mundo",
    color: "var(--viz-1)",
    height: 280
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Participa\xE7\xE3o por commodity \xB7 \xFAltimo ano",
    title: "Onde o Brasil pesa mais no mundo"
  }), /*#__PURE__*/React.createElement(window.BarChart, {
    data: data.byProduct.slice(0, 10).map(p => ({
      name: p.name,
      value: p.share
    })),
    valueKey: "value",
    color: "var(--viz-1)",
    label: "% do mundo",
    height: 300
  })));
}

// ── (3) Price: farm-gate vs. FOB ──────────────────────────────────────
function ViewPriceSpread({
  view
}) {
  const [product, setProduct] = useMSState(null);
  const data = window.priceSpread(product);
  const banco = window.crossPreviewBanco(view);
  const last = data.series[data.series.length - 1];
  const markupTs = data.series.map(d => ({
    y: d.y,
    v: d.markup
  }));
  const lineSeries = [{
    name: 'Preço de exportação (FOB)',
    color: 'var(--viz-3)',
    data: data.series.map(d => ({
      y: d.y,
      v: d.fob
    }))
  }, {
    name: 'Preço na porteira (produção)',
    color: 'var(--viz-2)',
    data: data.series.map(d => ({
      y: d.y,
      v: d.gate
    }))
  }];
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "Pre\xE7o de exporta\xE7\xE3o entra como demonstra\xE7\xE3o at\xE9 o MDIC ser ligado; o pre\xE7o na porteira deriva da produ\xE7\xE3o real (IBGE)."
  }), /*#__PURE__*/React.createElement(CrossProductPicker, {
    value: product,
    onChange: setProduct
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Pre\xE7o FOB atual",
    value: 'US$ ' + msNum(last?.fob, 2) + '/kg',
    sub: `${last?.y} · no porto`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Pre\xE7o na porteira",
    value: 'US$ ' + msNum(last?.gate, 2) + '/kg',
    sub: "na produ\xE7\xE3o"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Markup",
    value: '×' + msNum(last?.markup, 1),
    sub: "FOB \xF7 porteira"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Spread",
    value: 'US$ ' + msNum(last?.spread, 2) + '/kg',
    sub: "valor agregado entre porteira e porto"
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Porteira vs. porto \xB7 US$/kg",
    title: "Onde o valor \xE9 capturado",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "IBGE \xD7 MDIC")
  }), /*#__PURE__*/React.createElement(window.MultiLineChart, {
    series: lineSeries,
    valueKey: "v",
    label: "US$/kg",
    height: 300
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-legend"
  }, lineSeries.map(s => /*#__PURE__*/React.createElement("span", {
    key: s.name,
    className: "pc-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-legend-dot",
    style: {
      background: s.color
    }
  }), s.name)))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Markup no tempo",
    title: "Quantas vezes o porto vale a porteira",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "\xD7 \xB7 FOB \xF7 porteira")
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: markupTs,
    valueKey: "v",
    label: "\xD7",
    color: "var(--embrapa-blue)",
    height: 240
  })));
}

// ── (4) Espelho comercial ─────────────────────────────────────────────
function ViewMirror({
  view
}) {
  const [product, setProduct] = useMSState(null);
  const data = window.tradeMirror(product);
  const banco = window.crossPreviewBanco(view);
  const last = data.series[data.series.length - 1];
  const avgDisc = data.discrepancy.reduce((s, d) => s + d.v, 0) / (data.discrepancy.length || 1);
  const lineSeries = [{
    name: 'MDIC · SECEX',
    color: 'var(--viz-1)',
    data: data.series.map(d => ({
      y: d.y,
      v: d.mdic
    }))
  }, {
    name: 'UN Comtrade (Brasil)',
    color: 'var(--viz-3)',
    data: data.series.map(d => ({
      y: d.y,
      v: d.comtrade
    }))
  }, {
    name: 'Reportado pelos parceiros',
    color: 'var(--viz-9)',
    data: data.series.map(d => ({
      y: d.y,
      v: d.partners
    }))
  }];
  return /*#__PURE__*/React.createElement(React.Fragment, null, data.preview && /*#__PURE__*/React.createElement(window.PreviewBanner, {
    banco: banco,
    capabilityNote: "As tr\xEAs leituras da mesma exporta\xE7\xE3o entram como demonstra\xE7\xE3o at\xE9 MDIC e UN Comtrade serem ligados."
  }), /*#__PURE__*/React.createElement(CrossProductPicker, {
    value: product,
    onChange: setProduct
  }), /*#__PURE__*/React.createElement("div", {
    className: "kpi-row"
  }, /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Diverg\xEAncia m\xE9dia",
    value: msPct(avgDisc),
    sub: "entre a maior e a menor fonte"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Maior reporte",
    value: "Parceiros",
    sub: "tendem a registrar mais que a origem"
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Exporta\xE7\xE3o MDIC",
    value: 'US$ ' + msNum(last?.mdic, 1) + ' bi',
    sub: `${last?.y}`
  }), /*#__PURE__*/React.createElement(window.KpiCardSpark, {
    label: "Janela",
    value: "1997\u20132024",
    sub: "cobertura compar\xE1vel"
  })), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "A mesma exporta\xE7\xE3o, tr\xEAs fontes",
    title: "MDIC \xD7 Comtrade \xD7 parceiros",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "US$ bi \xB7 valores ilustrativos")
  }), /*#__PURE__*/React.createElement(window.MultiLineChart, {
    series: lineSeries,
    valueKey: "v",
    label: "US$ bi",
    height: 300
  }), /*#__PURE__*/React.createElement("div", {
    className: "pc-legend"
  }, lineSeries.map(s => /*#__PURE__*/React.createElement("span", {
    key: s.name,
    className: "pc-legend-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "pc-legend-dot",
    style: {
      background: s.color
    }
  }), s.name)))), /*#__PURE__*/React.createElement("div", {
    className: "card"
  }, /*#__PURE__*/React.createElement(window.SectionHeader, {
    overline: "Diverg\xEAncia no tempo",
    title: "Qu\xE3o distantes est\xE3o as fontes",
    action: /*#__PURE__*/React.createElement("span", {
      className: "caption"
    }, "% \xB7 (m\xE1x \u2212 m\xEDn) \xF7 m\xE9dia")
  }), /*#__PURE__*/React.createElement(window.LineChart, {
    data: data.discrepancy,
    valueKey: "v",
    label: "% diverg\xEAncia",
    color: "var(--status-warn)",
    height: 240
  }), /*#__PURE__*/React.createElement("p", {
    className: "caption",
    style: {
      padding: '10px 2px 2px'
    }
  }, "Diverg\xEAncias persistentes apontam diferen\xE7as de metodologia, defasagem de revis\xE3o ou cobertura \u2014 um diagn\xF3stico que nenhuma fonte isolada revela.")));
}
Object.assign(window, {
  CrossProductPicker,
  ViewExportCoef,
  ViewMarketShare,
  ViewPriceSpread,
  ViewMirror
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ViewsMultiSource.jsx", error: String((e && e.message) || e) }); }

// bancos.js
try { (() => {
// bancos.js — central registry for every data source the dashboard
// can consume. Adding a new banco = adding an entry here (no other
// hard-coded banco logic exists in the codebase).
//
// TWO STATUS AXES (kept separate on purpose — never let them blur):
//
//   • maturity — DATASET LIFECYCLE / maturity (how built-out the banco is).
//     A build-time property reported by the backend; the frontend only
//     displays it. One of window.MATURITY, in lifecycle order:
//       planejado · desenvolvimento · beta · estavel · manutencao ·
//       descontinuado
//     `hasData: true` stages (beta/estavel/manutencao/descontinuado) render
//     the real perspectives (with a caveat banner where caveat:true); the
//     future stages (planejado/desenvolvimento) render the placeholder.
//     NOTE: "source down right now" is NOT a maturity stage — that is a
//     RUNTIME HEALTH state (shown in the UI as "Saudável" · "Em atenção" ·
//     "Falha"), derived live in ViewHealth from pipeline runs / freshness /
//     load errors. The two axes are orthogonal: an estavel banco can be in a
//     failed health state; a beta banco can be healthy.
//
//   • usage (active/inactive) — DERIVED at render time: a banco is "active"
//     when it is the source feeding what the user currently sees (the
//     selected banco in single mode; an included source in multi-fonte).
//     Never stored.
//
//   • visible (true/false) — VISIBILITY, decided by the backend. When
//     `visible: false` the frontend hides the banco's existence EVERYWHERE
//     (sidebar, About page, Health page, cross-source picker, capability
//     lists, URL restore). Default is visible. Use it to declutter the UI on
//     demand — independent of maturity (an estavel banco can be hidden; a
//     hidden banco keeps its maturity, it just isn't shown). Enumerate the shown
//     set with window.visibleBancos(); bancoById() still resolves any id.
//
// The legacy `status: 'live'|'soon'` is now DERIVED from maturity.hasData
// (defined via Object.defineProperty after the array) so existing routing,
// CSV gating and cross-source preview logic keep working unchanged.
//
// Provenance (`prov`) applies to bancos with data; `plannedScope`/`cobertura`
// describe what a not-yet-built banco will expose.

// ── Maturity registry (single source of truth) ─────────────────────────
// Ordered along the dataset lifecycle (Planejado → … → Descontinuado).
// `hasData` decides whether perspectives render real data (+ a caveat banner
// for beta/manutencao/descontinuado) or the placeholder. Industry-standard
// release-maturity vocabulary; kept strictly distinct from runtime health.
window.MATURITY = {
  planejado: {
    id: 'planejado',
    label: 'Planejado',
    color: 'var(--pres-gray-400)',
    hasData: false,
    future: true,
    order: 1,
    desc: 'No roadmap, mas sem implementação iniciada nem prazo definido.'
  },
  desenvolvimento: {
    id: 'desenvolvimento',
    label: 'Em desenvolvimento',
    color: 'var(--status-mat-dev)',
    hasData: false,
    future: true,
    order: 2,
    desc: 'Implementação em andamento, com data prevista de conclusão.'
  },
  beta: {
    id: 'beta',
    label: 'Beta',
    color: 'var(--info)',
    hasData: true,
    caveat: true,
    order: 3,
    desc: 'Disponível para uso, mas com cobertura ainda parcial e sujeita a mudanças.'
  },
  estavel: {
    id: 'estavel',
    label: 'Estável',
    color: 'var(--ok)',
    hasData: true,
    order: 4,
    desc: 'Banco em produção — 100% pronto para consumo e análise.'
  },
  manutencao: {
    id: 'manutencao',
    label: 'Em manutenção',
    color: 'var(--warn)',
    hasData: true,
    caveat: true,
    order: 5,
    desc: 'Em produção, porém em correção de cálculo/tabela ou atualização programada.'
  },
  descontinuado: {
    id: 'descontinuado',
    label: 'Descontinuado',
    color: 'var(--status-mat-sunset)',
    hasData: true,
    caveat: true,
    sunset: true,
    order: 6,
    desc: 'Banco obsoleto — não recebe mais manutenção e será removido em breve.'
  }
};
window.maturityMeta = b => window.MATURITY[b && b.maturity || 'planejado'] || window.MATURITY.planejado;

// Short availability label for banco pickers/tags, derived from maturity.
// 'Disponível' once the banco has data; otherwise it mirrors the no-data
// stage so a planned-but-undated banco doesn't over-promise with "Em breve":
//   desenvolvimento (committed, has a date) → "Em breve"
//   planejado       (no ETA)                → "Sem previsão"
window.bancoAvailability = b => {
  if (window.maturityMeta(b).hasData) return 'Disponível';
  return b && b.maturity === 'desenvolvimento' ? 'Em breve' : 'Sem previsão';
};
window.BANCOS = [
// ─── Live ────────────────────────────────────────────────────────────
{
  id: 'ibge_pevs',
  short: 'IBGE PEVS',
  label: 'IBGE · Produção da Extração Vegetal e da Silvicultura',
  sub: 'Produção e exploração de commodities no território brasileiro',
  domain: 'Produção interna',
  scope: 'Brasil · UF · município',
  source: 'IBGE',
  table: 'gold_pevs_production',
  maturity: 'estavel',
  // Data capabilities this banco exposes (see CAPABILITIES in views.js).
  // IBGE PEVS = production only: products, geography, quality — annual,
  // no origin→destination flow, no commercial partner.
  provides: ['product', 'geo', 'quality'],
  // Canonical currency for this banco. Values are stored BRL-canonical
  // (PEVS is natively R$); changeDatabase resets the DISPLAY currency to this
  // so the right symbol shows by default. Finest geo granularity the banco
  // exposes ('municipio' | 'uf' | null) — drives the FilterMenu's geography
  // cascade depth so it never offers a level the banco lacks.
  baseCurrency: 'BRL',
  geoLevel: 'municipio',
  // Business-semantic descriptors for this banco's dimensions — display
  // labels + universe kind ('uf' = Brazilian states, 'country' = nations) +
  // product code scheme, DECLARED here so adapters/views never branch on
  // bancoId. PEVS is production-only (no flow/partner); the geo labels are
  // harmless defaults.
  dimensions: {
    origin: {
      label: 'UF de origem',
      kind: 'uf'
    },
    dest: {
      label: 'UF de destino',
      kind: 'uf'
    },
    partner: {
      label: 'UF parceira',
      kind: 'uf'
    },
    product: {
      codeLabel: 'Código PEVS'
    }
  },
  // Comparable ANNUAL series this banco can contribute to the cross-source
  // perspective (see crossSource.js). Each metric is a single time series
  // keyed by year. `family` groups metrics that share a physical/value
  // dimension (currency / mass / volume / ratio) so the cross view knows
  // which series can share an axis or form a ratio. `years` is the native
  // coverage; the cross view intersects coverages across selected series.
  metrics: [{
    id: 'prod_value',
    label: 'Valor da produção',
    family: 'currency',
    unit: 'R$',
    agg: 'Valor real (IPCA) da extração vegetal',
    years: [1986, 2024]
  }, {
    id: 'prod_mass',
    label: 'Quantidade produzida (massa)',
    family: 'mass',
    unit: 't',
    agg: 'Massa colhida das espécies de família massa',
    years: [1986, 2024]
  }, {
    id: 'prod_volume',
    label: 'Quantidade produzida (volume)',
    family: 'volume',
    unit: 'm³',
    agg: 'Volume das espécies de família volume',
    years: [1986, 2024]
  }],
  // Derive product/UF/year totals from the live datasets instead of
  // hardcoding them in the registry — keeps everything in sync if
  // data.js changes (e.g. a new PEVS product or extra year of data).
  prov: {
    lastCrop: 'PEVS 2024',
    lastCropDate: 'publ. 27 set 2024',
    refresh: '28 mai 2026 · 04:30 BRT',
    totalRows: 11_177_427,
    get productsTotal() {
      return (window.PRODUCTS || []).length;
    },
    get ufsTotal() {
      return (window.UF_DATA || []).length;
    },
    get yearsTotal() {
      const ts = window.OVERVIEW_TS || [];
      return ts.length;
    },
    get yearStart() {
      const ts = window.OVERVIEW_TS || [];
      return ts[0]?.y || 1986;
    },
    get yearEnd() {
      const ts = window.OVERVIEW_TS || [];
      return ts[ts.length - 1]?.y || 2024;
    }
  }
},
// ─── Connected (representative snapshots) ─────────────────────────────
// COMEX = estavel, Comtrade = beta (partial coverage). Both have data
// (hasData) and render real perspectives. SEFAZ stays 'planejado'.
{
  id: 'ibge_pam',
  short: 'IBGE PAM',
  label: 'IBGE · Produção Agrícola Municipal',
  sub: 'Área, produção e rendimento das lavouras temporárias e permanentes',
  domain: 'Produção agrícola',
  scope: 'Brasil · UF · município',
  source: 'IBGE',
  table: 'gold_pam_production',
  // Beta: freshly connected agricultural banco, partial coverage → renders
  // real perspectives with a caveat banner. Demonstrates that a NEW domain
  // (lavouras) plugs in by declaration alone.
  maturity: 'beta',
  maturityNote: 'Banco agrícola recém-conectado — cobertura inicial (lavouras principais), em expansão.',
  maturityDate: '1º trimestre/2027',
  // Production banco WITH the agricultural capabilities: product, geography,
  // area (planted/harvested) and yield (productivity). Annual → NO flow /
  // partner / monthly (those perspectives gate off with "Não se aplica").
  provides: ['product', 'geo', 'area', 'yield', 'quality'],
  baseCurrency: 'BRL',
  geoLevel: 'municipio',
  dimensions: {
    origin: {
      label: 'UF produtora',
      kind: 'uf'
    },
    dest: {
      label: 'UF produtora',
      kind: 'uf'
    },
    partner: {
      label: 'UF produtora',
      kind: 'uf'
    },
    product: {
      codeLabel: 'Código PAM'
    }
  },
  // Cross-source metrics — adds the new area/rendimento families to the
  // catalog so PAM series can be plotted alongside trade/production series.
  metrics: [{
    id: 'prod_value',
    label: 'Valor da produção',
    family: 'currency',
    unit: 'R$',
    agg: 'Valor da produção das lavouras',
    years: [1990, 2024]
  }, {
    id: 'prod_quantity',
    label: 'Quantidade produzida',
    family: 'mass',
    unit: 't',
    agg: 'Produção colhida (massa)',
    years: [1990, 2024]
  }, {
    id: 'area_harvested',
    label: 'Área colhida',
    family: 'area',
    unit: 'ha',
    agg: 'Área colhida das lavouras',
    years: [1990, 2024]
  }, {
    id: 'yield',
    label: 'Rendimento médio',
    family: 'rendimento',
    unit: 'kg/ha',
    agg: 'Produção ÷ área colhida (área-ponderada)',
    years: [1990, 2024]
  }],
  prov: {
    lastCrop: 'PAM 2024',
    lastCropDate: 'publ. set 2025',
    refresh: '30 mai 2026 · 04:45 BRT',
    totalRows: 8_932_140,
    productsTotal: 5,
    ufsTotal: 27,
    yearStart: 1990,
    yearEnd: 2024,
    yearsTotal: 35
  },
  plannedScope: [{
    col: 'produto (lavoura)',
    desc: 'Cultura agrícola — temporária ou permanente.'
  }, {
    col: 'uf · município',
    desc: 'Localização da lavoura (até o nível municipal).'
  }, {
    col: 'area_plantada · area_colhida',
    desc: 'Área destinada e efetivamente colhida (ha).'
  }, {
    col: 'quantidade_produzida',
    desc: 'Produção colhida (t).'
  }, {
    col: 'rendimento_medio',
    desc: 'Produtividade = produção ÷ área colhida (kg/ha).'
  }, {
    col: 'valor_producao',
    desc: 'Valor da produção (R$).'
  }],
  cobertura: {
    years: '1990 → presente',
    atualizacao: 'anual',
    granularidade: 'lavoura × município × ano'
  }
}, {
  id: 'mdic_comex',
  short: 'MDIC COMEX',
  label: 'MDIC · Comércio Exterior',
  sub: 'Exportação e importação brasileiras por estado de origem, produto e parceiro comercial',
  domain: 'Comércio exterior',
  scope: 'UF de origem ↔ países parceiros',
  source: 'MDIC · SECEX',
  table: 'gold_comex_flows',
  maturity: 'estavel',
  // Exports by UF of origin → partner country, monthly, with product
  // (NCM) and quality. Has flow + partner + monthly.
  provides: ['product', 'geo', 'flow', 'partner', 'monthly', 'quality'],
  // Values in USD (FOB/CIF); geography at origin-state (UF) level (no
  // municipal breakdown).
  baseCurrency: 'USD',
  geoLevel: 'uf',
  dimensions: {
    origin: {
      label: 'UF de origem',
      kind: 'uf'
    },
    dest: {
      label: 'país parceiro',
      kind: 'country'
    },
    partner: {
      label: 'país parceiro',
      kind: 'country'
    },
    product: {
      codeLabel: 'Código NCM'
    }
  },
  metrics: [{
    id: 'exp_value',
    label: 'Valor exportado (FOB)',
    family: 'currency',
    unit: 'US$',
    agg: 'Soma do valor FOB das exportações',
    years: [1997, 2024]
  }, {
    id: 'imp_value',
    label: 'Valor importado (CIF)',
    family: 'currency',
    unit: 'US$',
    agg: 'Soma do valor das importações',
    years: [1997, 2024]
  }, {
    id: 'exp_weight',
    label: 'Peso exportado',
    family: 'mass',
    unit: 'kg',
    agg: 'Soma do peso líquido exportado',
    years: [1997, 2024]
  }, {
    id: 'exp_price',
    label: 'Preço médio (US$/kg)',
    family: 'ratio',
    unit: 'US$/kg',
    agg: 'Valor FOB ÷ peso líquido',
    years: [1997, 2024]
  }],
  // Provenance (live). Representative snapshot generated from the explicit
  // contract shape (02_SNAPSHOT_CONTRACTS.md), castanha/nut chain demo
  // parameters, until the real Gold is wired.
  prov: {
    lastCrop: 'COMEX 2024 · M12',
    lastCropDate: 'publ. jan 2025',
    refresh: '29 mai 2026 · 05:10 BRT',
    totalRows: 1_284_530,
    productsTotal: 5,
    ufsTotal: 27,
    yearStart: 1997,
    yearEnd: 2024,
    yearsTotal: 28
  },
  plannedScope: [{
    col: 'NCM · SH4 · SH6',
    desc: 'Classificação harmonizada do produto exportado.'
  }, {
    col: 'uf_origem',
    desc: 'UF onde a mercadoria foi produzida ou está estabelecido o exportador.'
  }, {
    col: 'pais_destino · pais_origem',
    desc: 'Parceiro comercial na operação.'
  }, {
    col: 'via',
    desc: 'Modalidade de transporte (marítima · aérea · rodoviária).'
  }, {
    col: 'val_fob_usd · peso_kg · qtd_est',
    desc: 'Valor FOB em USD, peso líquido e quantidade estatística.'
  }],
  cobertura: {
    years: '1997 → presente',
    atualizacao: 'mensal (D+30)',
    granularidade: 'NCM × UF × país × via × ano-mês'
  }
}, {
  id: 'un_comtrade',
  short: 'UN COMTRADE',
  label: 'UN Comtrade · Estatísticas de Comércio Internacional',
  sub: 'Fluxos de comércio entre nações reportados à Divisão de Estatística da ONU',
  domain: 'Comércio internacional',
  scope: 'País → país (com ou sem filtro Brasil)',
  source: 'UN Statistics Division',
  table: 'gold_comtrade_flows',
  maturity: 'beta',
  // Connected & loaded, but the UN Comtrade API rate limits make the full
  // historical backfill impossible to finish in one pass — the deep history
  // (pre-2010) is still being ingested in throttled batches.
  maturityNote: 'Backfill histórico (1988–2010) parcial — limite de requisições da API UN Comtrade.',
  maturityDate: '4º trimestre/2026',
  // Country → country flows. Product (HS6), flow, partner, quality.
  // Geography is country-level only (no Brazilian UF/município).
  provides: ['product', 'flow', 'partner', 'quality'],
  // Values in USD; country↔country trade, no national geographic dimension.
  baseCurrency: 'USD',
  geoLevel: null,
  dimensions: {
    origin: {
      label: 'país reporter',
      kind: 'country'
    },
    dest: {
      label: 'país parceiro',
      kind: 'country'
    },
    partner: {
      label: 'país parceiro',
      kind: 'country'
    },
    product: {
      codeLabel: 'Código HS6'
    }
  },
  metrics: [{
    id: 'exp_value',
    label: 'Valor exportado (BR)',
    family: 'currency',
    unit: 'US$',
    agg: 'Exportações brasileiras declaradas à ONU',
    years: [1988, 2024]
  }, {
    id: 'imp_value',
    label: 'Valor importado (BR)',
    family: 'currency',
    unit: 'US$',
    agg: 'Importações brasileiras declaradas à ONU',
    years: [1988, 2024]
  }, {
    id: 'world_exp',
    label: 'Exportação mundial',
    family: 'currency',
    unit: 'US$',
    agg: 'Total mundial do produto (todos reporters)',
    years: [1988, 2024]
  }],
  // Provenance (live). Representative snapshot generated from the explicit
  // contract shape (02_SNAPSHOT_CONTRACTS.md), HS 0801 nut-trade demo
  // parameters, until the real Gold is wired.
  // Country-level only → no UF dimension (ufsTotal = 0).
  prov: {
    lastCrop: 'Comtrade 2024',
    lastCropDate: 'rev. 2025T1',
    refresh: '29 mai 2026 · 05:10 BRT',
    totalRows: 642_180,
    productsTotal: 5,
    ufsTotal: 0,
    yearStart: 1988,
    yearEnd: 2024,
    yearsTotal: 37
  },
  plannedScope: [{
    col: 'reporter · partner',
    desc: 'Países envolvidos no fluxo declarado.'
  }, {
    col: 'flow',
    desc: 'Direção do fluxo (export · import · re-export).'
  }, {
    col: 'HS6',
    desc: 'Sistema Harmonizado a 6 dígitos.'
  }, {
    col: 'val_usd · qty · qty_unit',
    desc: 'Valor FOB/CIF, quantidade líquida e unidade estatística.'
  }, {
    col: 'data_quality',
    desc: 'Bandeira (final · preliminar · estimado · mirror).'
  }],
  cobertura: {
    years: '1988 → presente',
    atualizacao: 'anual + revisões trimestrais',
    granularidade: 'HS6 × par de países × ano'
  }
}, {
  id: 'sefaz_nf',
  short: 'SEFAZ NFe',
  label: 'SEFAZ · Fluxos de Notas Fiscais Eletrônicas',
  sub: 'Comércio interno brasileiro reconstruído a partir de NFe inter-estaduais e intermunicipais',
  domain: 'Comércio interno',
  scope: 'UF ↔ UF · município ↔ município',
  source: 'Receita · SEFAZ',
  table: 'gold_nfe_flows',
  maturity: 'planejado',
  // Internal trade: UF↔UF / município↔município flows, daily, with
  // product (NCM), partner (the counterpart UF), monthly+ and quality.
  provides: ['product', 'geo', 'flow', 'partner', 'monthly', 'quality'],
  // Values in BRL; geography down to municipality level (origin/destination).
  baseCurrency: 'BRL',
  geoLevel: 'municipio',
  dimensions: {
    origin: {
      label: 'UF de origem',
      kind: 'uf'
    },
    dest: {
      label: 'UF de destino',
      kind: 'uf'
    },
    partner: {
      label: 'UF parceira',
      kind: 'uf'
    },
    product: {
      codeLabel: 'Código NCM'
    }
  },
  metrics: [{
    id: 'internal_value',
    label: 'Valor das operações',
    family: 'currency',
    unit: 'R$',
    agg: 'Soma do valor das NFe inter/intraestaduais',
    years: [2010, 2024]
  }, {
    id: 'internal_weight',
    label: 'Peso movimentado',
    family: 'mass',
    unit: 'kg',
    agg: 'Soma do peso transportado',
    years: [2010, 2024]
  }, {
    id: 'icms_total',
    label: 'ICMS recolhido',
    family: 'currency',
    unit: 'R$',
    agg: 'Soma do ICMS das operações',
    years: [2010, 2024]
  }],
  plannedScope: [{
    col: 'cfop',
    desc: 'Natureza da operação fiscal.'
  }, {
    col: 'uf_origem · municipio_origem',
    desc: 'Localização do remetente.'
  }, {
    col: 'uf_destino · municipio_destino',
    desc: 'Localização do destinatário.'
  }, {
    col: 'ncm',
    desc: 'Classificação do produto.'
  }, {
    col: 'val_operacao · val_icms',
    desc: 'Valor total da operação e do imposto recolhido.'
  }, {
    col: 'cnae_remetente · cnae_destino',
    desc: 'Setor de atividade econômica das partes.'
  }],
  cobertura: {
    years: '2010 → presente',
    atualizacao: 'diária (defasagem 24h)',
    granularidade: 'NCM × CFOP × par UF/município × dia',
    restricoes: 'Agregação com preservação de sigilo abaixo de N=5 estabelecimentos.'
  }
}];
window.bancoById = id => window.BANCOS.find(b => b.id === id) || window.BANCOS[0];

// Canonical / default DISPLAY currency for a banco. COMEX/Comtrade snapshots
// store BRL-equivalent values (see previewData.js) and default their display
// to USD so the real US$ figures render. Used to reset the display currency on
// banco switch and to label the value filter. Falls back to BRL.
window.canonCurrencyFor = id => {
  const b = window.bancoById ? window.bancoById(id) : null;
  return b && b.baseCurrency || 'BRL';
};
// Business-semantic descriptor for a banco DIMENSION (origin/dest/partner geo
// + product code scheme). Declared per banco in `dimensions` — adapters/views
// read labels & universe kind from HERE instead of branching on bancoId.
window.bancoDim = (id, dim) => {
  const b = window.bancoById ? window.bancoById(id) : null;
  return b && b.dimensions && b.dimensions[dim] || {};
};
// Finest geographic granularity a banco exposes ('municipio' | 'uf' | null).
window.geoLevelFor = id => {
  const b = window.bancoById ? window.bancoById(id) : null;
  if (!b) return null;
  if (b.geoLevel !== undefined) return b.geoLevel;
  return (b.provides || []).includes('geo') ? 'municipio' : null;
};

// Visibility axis (backend-controlled). `visible: false` hides a banco from the
// whole UI; default (undefined/true) shows it. UI enumerations use this helper;
// bancoById stays over the full list so an id can always be resolved.
window.isBancoVisible = b => {
  const banco = typeof b === 'string' ? window.bancoById(b) : b;
  return !!banco && banco.visible !== false;
};
window.visibleBancos = () => (window.BANCOS || []).filter(b => b.visible !== false);

// Gold table name to DISPLAY: prefer the backend-reported name (dataStore),
// fall back to the registry literal (declared/planned, e.g. for not-connected
// bancos). One resolver so a backend rename propagates to the whole UI.
window.bancoTable = id => {
  const fromBackend = window.dataStore && window.dataStore.table ? window.dataStore.table(id) : null;
  return fromBackend || (window.bancoById && window.bancoById(id) || {}).table || null;
};

// Provenance metadata resolver: the registry banco (UI declaration + fallback)
// OVERLAID with whatever the backend reports (dataStore.meta). The UI reads
// provenance through this — never registry literals directly — so any field
// the backend reports (table, source, granularity, coverage, refresh, counts,
// expected-completion) is authoritative and can't diverge from reality.
window.bancoMeta = id => {
  const b = window.bancoById && window.bancoById(id) || {};
  const back = window.dataStore && window.dataStore.meta ? window.dataStore.meta(id) || {} : {};
  const clean = {};
  Object.keys(back).forEach(k => {
    if (back[k] != null) clean[k] = back[k];
  });
  return {
    ...b,
    ...clean
  };
};

// Derive the legacy `status` ('live'|'soon') from maturity.hasData so all
// existing routing / CSV gating / cross-source preview logic keeps working
// while the UI reads the richer maturity stage. Single source of truth.
window.BANCOS.forEach(b => {
  if (!('maturity' in b)) b.maturity = 'planejado';
  Object.defineProperty(b, 'status', {
    get() {
      return (window.MATURITY[b.maturity] || {}).hasData ? 'live' : 'soon';
    },
    enumerable: true,
    configurable: true
  });
});

// Cross-source helpers: every (banco, metric) pair the dashboard can plot
// side by side. `metricById` resolves one pair; `allMetricRefs` enumerates
// them for the series picker.
window.metricById = (bancoId, metricId) => {
  const b = window.bancoById(bancoId);
  return b && b.metrics ? b.metrics.find(m => m.id === metricId) || null : null;
};
window.allMetricRefs = () => (window.visibleBancos ? window.visibleBancos() : window.BANCOS || []).flatMap(b => (b.metrics || []).map(m => ({
  banco: b.id,
  metric: m.id,
  bancoMeta: b,
  metricMeta: m
})));

// Family display labels shared by the cross-source view.
window.METRIC_FAMILIES = {
  currency: {
    label: 'valor monetário'
  },
  mass: {
    label: 'massa'
  },
  volume: {
    label: 'volume'
  },
  ratio: {
    label: 'razão / índice'
  },
  area: {
    label: 'área'
  },
  rendimento: {
    label: 'rendimento / produtividade'
  }
};

// ── Dev-time COVERAGE LINT ───────────────────────────────────────────────
// A few per-banco maps are CURATED, not derived from this registry: the
// glossary (glossary.js), the cross-source series builders (crossSource.js)
// and the health table/sources (ViewHealth.jsx). When a new visible banco is
// plugged in, those are the spots most likely to be forgotten. This helper
// warns ONCE per map (console only — never touches data) when a visible banco
// has no entry, mirroring viewComponent's "warn loudly instead of failing
// silently". `hasEntry(banco)` returns whether the map covers that banco.
window.__bancoCoverageWarned = window.__bancoCoverageWarned || {};
window.auditBancoCoverage = (mapLabel, hasEntry, opts) => {
  opts = opts || {};
  if (window.__bancoCoverageWarned[mapLabel]) return; // once per map
  window.__bancoCoverageWarned[mapLabel] = true;
  const list = window.visibleBancos ? window.visibleBancos() : window.BANCOS || [];
  const missing = list.filter(b => !opts.onlyLive || b.status === 'live').filter(b => {
    try {
      return !hasEntry(b);
    } catch (e) {
      return true;
    }
  }).map(b => b.id);
  if (missing.length) {
    console.warn(`[cobertura] ${mapLabel}: banco(s) visível(is) sem entrada → ${missing.join(', ')}. ` + `Adicione a entrada correspondente (ver CLAUDE.md · "plugar um banco de um domínio novo").`);
  }
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "bancos.js", error: String((e && e.message) || e) }); }

// chipFmt.js
try { (() => {
// chipFmt.js — shared formatters for the filter trigger-bar "chips".
//
// The chip labels (products / value range / quality) were implemented THREE
// times with identical rules: FilterMenu.buildChipSummary (operates on Sets),
// Dashboard.chipsFromRestoredSummary and Dashboard.defaultChipsFor (operate on
// arrays). A divergence there means a shared URL shows different chips than the
// FilterMenu would. Centralised here as pure functions over primitives so all
// three call ONE implementation. Loaded with the other data-layer scripts.

// Compact monetary label (sym-aware): "R$ 1,2 bi" / "US$ 340 mil".
// Replaces the per-file copies (FilterMenu.formatBRLcompact + Dashboard.compactBRL).
// Negative-safe so an inverted range still reads correctly.
window.fmtCompactValue = (v, sym = 'R$') => {
  if (v == null) return '—';
  const a = Math.abs(v),
    sign = v < 0 ? '-' : '';
  const f = (div, dp, suf) => `${sign}${sym} ` + (a / div).toFixed(dp).replace('.', ',') + suf;
  if (a >= 1e9) return f(1e9, 1, ' bi');
  if (a >= 1e6) return f(1e6, 1, ' mi');
  if (a >= 1e3) return f(1e3, 0, ' mil');
  return `${sign}${sym} ` + a.toLocaleString('pt-BR');
};
window.chipFmt = {
  // Product basket → chip. count = selected, total = catalogue size,
  // firstName = name to show when exactly one is selected.
  products(count, total, firstName) {
    if (count == null) return `Todos (${total})`; // null = no filter = all
    if (count === 0) return 'Nenhum';
    if (count === total) return `Todos (${total})`;
    if (count === 1) return firstName || `1 de ${total}`;
    return `${count} de ${total}`;
  },
  // Year range → chip ("1986–2024").
  period(startYear, endYear) {
    return `${startYear}\u2013${endYear}`;
  },
  // Value range → chip. sym is the active currency symbol.
  valueRange(min, max, sym = 'R$') {
    const f = v => window.fmtCompactValue(v, sym);
    if (min == null && max == null) return 'Sem limite';
    if (min != null && max != null) return `${f(min)} \u2013 ${f(max)}`;
    if (min != null) return `\u2265 ${f(min)}`;
    return `\u2264 ${f(max)}`;
  },
  // Quality flags → chip. count null = no filter = all; labelOf maps id→label.
  quality(ids, total, labelOf) {
    if (ids == null) return `Todas (${total})`;
    if (ids.length === 0) return 'Nenhuma';
    if (ids.length === total) return `Todas (${total})`;
    const head = ids.slice(0, 2).map(labelOf).join(' \u00b7 ');
    return head + (ids.length > 2 ? ` +${ids.length - 2}` : '');
  },
  // States-only geography → chip (Dashboard's banco-aware default & restore).
  // hasGeo false = the banco has no geographic dimension.
  geoStates(stateCount, ufTotal, hasGeo) {
    if (!hasGeo) return 'Não se aplica';
    if (!stateCount || stateCount === ufTotal) return `Brasil \u00b7 ${ufTotal} UFs`;
    return `${stateCount} ${stateCount === 1 ? 'UF' : 'UFs'}`;
  }
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "chipFmt.js", error: String((e && e.message) || e) }); }

// contracts.js
try { (() => {
// contracts.js — THE SINGLE SOURCE OF TRUTH FOR DATA SHAPE.
//
// The dashboard has ONE seam between data and UI: a per-banco serving
// snapshot, four preview adapters, the cross-source/analytics/chain builders
// and the enrichment layer. Every one of those returns a fixed SHAPE; to go
// live the backend swaps the *body* of the producer and keeps the shape.
//
// This file is where that shape is DEFINED ONCE — in code, executable and
// enforced — so it can never silently drift from prose docs:
//
//   1. @typedef blocks below  → the human-readable shape reference. The other
//      builder files (previewData.js, crossSource.js, crossAnalytics.js,
//      crossChain.js, enrichment.js) and the handoff doc
//      (design_handoff_commodities_backend/02_SNAPSHOT_CONTRACTS.md) POINT
//      here instead of re-typing keys — no duplication, no drift.
//
//   2. window.SNAPSHOT_CONTRACTS  → the machine-readable required-keys
//      registry. One entry per producer; lists the keys a view depends on.
//
//   3. window.auditSnapshotContracts()  → a runtime drift LINT. It calls each
//      live producer and console.warns (once) if the returned object is
//      missing a contracted key. Mirrors window.auditBancoCoverage: console
//      only, never touches data. So if a builder loses a key the contract
//      promises, you see it in the console instead of a broken chart.
//
// The CONCRETE demo values (castanha chain etc.) live in demoFixture.js and
// are NOT part of the contract — only the shape is normative.

// ════════════════════════════════════════════════════════════════════════
//  SHAPE REFERENCE (@typedef) — the canonical definition the docs point to
// ════════════════════════════════════════════════════════════════════════
//
// ── Per-banco serving snapshot — window.snapshotFor(bancoId) ─────────────
//    PEVS-shaped pre-aggregated result a pushdown query returns. IBGE PEVS is
//    the reference (served from data.js globals via dataStore.datasetFor);
//    every other banco produces the SAME keys from window.snapshotFor.
//
// @typedef {Object} BancoSnapshot
// @property {{code:string,name:string,unit:string,family:string}[]} products       Product universe (family ∈ mass|volume|…).
// @property {Object.<string,{y:number,v:number,q:number,family:string}[]>} productTS  Per-product annual series, keyed by code. v=value (canonical), q=quantity.
// @property {{y:number,v:number,q:number,q_mass:number,q_vol?:number}[]} overviewTS  Annual aggregate (v in bi; q_* per family — NEVER summed across families).
// @property {{uf:string,name:string,region:string,col:number,row:number,value:number,q_mass:number,q_vol?:number}[]} ufData  Per-UF tile-map rows. ONLY for bancos providing `geo` (empty otherwise).
// @property {{id:string,label:string,color:string,count:number,share:number}[]} quality  Quality-flag distribution (shared taxonomy).
// @property {{y:number,ok:number,missing_value:number,missing_quantity:number,estimated:number,outlier:number,boundary:number}[]} [qualityTs]  Quality over coverage years.
// @property {Object[]} [qualityByProduct]  Per-product flag shares (keys = flag ids).
// @property {Object[]} [qualityByUf]       Per-UF not_ok share (tile-map shaped).
// @property {Object[]} [topMunis]          Municipality table (may be empty).
// @property {Object[]} [regions]           Region registry passthrough.
// @property {string}   [table]             Backend-reported Gold table name.
// @property {boolean}  [_synthetic]        Marker: representative, not real Gold.
//
// ── Preview adapters (previewData.js) ────────────────────────────────────
//
// @typedef {Object} FlowData            window.flowData(bancoId, summary)
// @property {boolean} preview
// @property {string}  unit
// @property {string}  originLabel        Dimension label for the origin side.
// @property {string}  destLabel          Dimension label for the destination side.
// @property {{id:string,label:string,side:'origin'|'dest',value:number}[]} nodes
// @property {{source:string,target:string,value:number}[]} links
//
// @typedef {Object} PartnerData         window.partnerData(bancoId, summary)
// @property {boolean} preview
// @property {string}  flowLabel
// @property {string}  unit
// @property {{name:string,exp:number,imp:number,value:number}[]} partners
//
// @typedef {Object} MonthlyData         window.monthlyData(bancoId, summary)
// @property {boolean} preview
// @property {string}  unit
// @property {number[]} years
// @property {number[]} months           [1..12]
// @property {Object.<number,number[]>} matrix   year → 12 monthly values.
// @property {number[]} monthlyAvg       12 values.
// @property {{ym:string,y:number,m:number,v:number}[]} series
//
// @typedef {Object} ProductivityData    window.productivityData(bancoId, cropCode, summary)
// @property {boolean} preview
// @property {string}  yieldUnit         e.g. 'kg/ha' (intensity — area-weighted mean, NEVER summed).
// @property {string}  areaUnit          e.g. 'ha'.
// @property {{code:string,name:string}}   crop
// @property {{code:string,name:string}[]} crops
// @property {{yieldKgHa:number,areaHa:number,prodT:number,yieldCagr:number}} national
// @property {{y:number,yieldKgHa:number,areaHa:number,prodT:number}[]} series   prodT = yieldKgHa × areaHa ÷ 1000.
// @property {{uf:string,name:string,region:string,col:number,row:number,yieldKgHa:number,areaHa:number,prodT:number}[]} byUF
//
// ── Cross-source builders (crossSource.js) ───────────────────────────────
//
// @typedef {Object} SeriesResult        window.crossSeries(bancoId, metricId, {y0,y1})
// @property {string}  banco
// @property {string}  metric
// @property {Object}  bancoMeta          Registry object (bancos.js).
// @property {Object}  metricMeta         Registry object (bancos.js).
// @property {string}  key                'banco:metric' — stable id.
// @property {string}  label
// @property {string}  unit               DISPLAY unit incl. magnitude (e.g. 'US$ bi', 'mil t'). Two series share an axis IFF unit strings match.
// @property {string}  family             currency | mass | volume | ratio | area | rendimento
// @property {boolean} preview
// @property {[number,number]} coverage
// @property {{y:number,v:number}[]} points
//
// ── Cross analytics (crossAnalytics.js) ──────────────────────────────────
//
// @typedef {Object} ExportCoefficient   window.exportCoefficient(productCode)
// @property {boolean} preview
// @property {string}  unit
// @property {{uf:string,name:string,region:string,col:number,row:number,production:number,exportV:number,coefPct:number}[]} byUf
// @property {{production:number,exportV:number,coefPct:number}} national
// @property {{y:number,v:number}[]} timeseries
//
// @typedef {Object} MarketShare         window.marketShare(productCode)
// @property {boolean} preview
// @property {string}  unit
// @property {{y:number,br:number,world:number,share:number}[]} series
// @property {{code:string,name:string,share:number}[]} byProduct
//
// @typedef {Object} PriceSpread         window.priceSpread(productCode)
// @property {boolean} preview
// @property {string}  unit
// @property {{y:number,gate:number,fob:number,spread:number,markup:number}[]} series
//
// @typedef {Object} TradeMirror         window.tradeMirror(productCode)
// @property {boolean} preview
// @property {string}  unit
// @property {{y:number,mdic:number,comtrade:number,partners:number}[]} series
// @property {{y:number,v:number}[]} discrepancy
//
// ── Cross chain — EXTENDED contracts (crossChain.js) ─────────────────────
//
// @typedef {Object} ChainBalance        window.chainBalance(productCode, year)
// @property {boolean} preview
// @property {string}  unit
// @property {number}  year
// @property {number}  produced          produced = exported + internal + domestic (mass conserved).
// @property {number}  exported
// @property {number}  internal
// @property {number}  domestic
// @property {number}  expFrac
// @property {number}  intFrac
// @property {number}  domFrac
// @property {number}  worldShare
// @property {number}  worldTotal
// @property {number}  exportUsd
// @property {{nodes:{id:string,label:string,side:string,value:number}[],links:{source:string,target:string,value:number}[]}} sankey
//
// @typedef {Object} HarvestShipmentLag  window.harvestShipmentLag(productCode)
// @property {boolean}  preview
// @property {string[]} months           12 labels.
// @property {number[]} production        12 monthly values (peak=100; MODELED from annual PEVS).
// @property {number[]} shipments         12 monthly values (peak=100; MDIC monthly).
// @property {number}   peakHarvest       Month index 0–11.
// @property {number}   peakShip          Month index 0–11.
// @property {number}   lagMonths         Best cross-correlation lag.
// @property {number}   corrAtLag
// @property {{lag:number,corr:number}[]} lagProfile   lag −6…+6.
//
// ── Enrichment analyses (enrichment.js) ──────────────────────────────────
//
// @typedef {Object} ValueAddedAnalysis  window.valueAddedAnalysis(groupId)
// @property {boolean}  preview
// @property {number[]} years
// @property {{bruta:{y:number,v:number}[],processada:{y:number,v:number}[]}} byLevel
// @property {{y:number,brutaV:number,procV:number,procShare:number,premium:number,priceB:number,priceP:number}[]} series
//
// @typedef {Object} MarketNatureAnalysis  window.marketNatureAnalysis()
// @property {boolean}  preview
// @property {number[]} years
// @property {Object[]} series            One row per year; a key per ENRICH_MARKETS id.
// @property {Object}   latest            Last series row.

(function () {
  // ── Machine-readable required-keys registry ──────────────────────────
  // One entry per producer. `required` = the keys a VIEW depends on (the
  // contracted surface, not every incidental field). `produce` calls the
  // live builder so the lint validates the real output. `appliesTo` gates
  // per-banco contracts to the bancos that declare the capability. `extra`
  // adds conditional checks (e.g. geo bancos must ship a non-empty ufData).
  const has = (b, cap) => !!(b && b.provides && b.provides.includes(cap));
  window.SNAPSHOT_CONTRACTS = {
    // ── per-banco producers ──────────────────────────────────────────
    perBanco: {
      snapshot: {
        typedef: 'BancoSnapshot',
        required: ['products', 'productTS', 'overviewTS', 'quality'],
        // PEVS serves from data.js globals (snapshotFor returns null) → skipped
        // here; it is the reference shape this contract is modelled on.
        produce: b => window.snapshotFor ? window.snapshotFor(b.id) : null,
        extra: (o, b) => has(b, 'geo') && !(o.ufData && o.ufData.length) ? ['ufData vazio (banco provê `geo`)'] : []
      },
      flow: {
        typedef: 'FlowData',
        required: ['preview', 'unit', 'originLabel', 'destLabel', 'nodes', 'links'],
        appliesTo: b => has(b, 'flow'),
        produce: b => window.flowData ? window.flowData(b.id, {}) : null
      },
      partner: {
        typedef: 'PartnerData',
        required: ['preview', 'flowLabel', 'unit', 'partners'],
        appliesTo: b => has(b, 'partner'),
        produce: b => window.partnerData ? window.partnerData(b.id, {}) : null
      },
      monthly: {
        typedef: 'MonthlyData',
        required: ['preview', 'unit', 'years', 'months', 'matrix', 'monthlyAvg', 'series'],
        appliesTo: b => has(b, 'monthly'),
        produce: b => window.monthlyData ? window.monthlyData(b.id, {}) : null
      },
      productivity: {
        typedef: 'ProductivityData',
        required: ['preview', 'yieldUnit', 'areaUnit', 'crop', 'crops', 'national', 'series', 'byUF'],
        appliesTo: b => has(b, 'yield'),
        produce: b => window.productivityData ? window.productivityData(b.id, null, {}) : null
      }
    },
    // ── global (commodity-level) producers — validated once on a sample ──
    global: {
      crossSeries: {
        typedef: 'SeriesResult',
        required: ['banco', 'metric', 'key', 'label', 'unit', 'family', 'preview', 'coverage', 'points'],
        produce: () => {
          const b = (window.visibleBancos ? window.visibleBancos() : window.BANCOS || []).find(x => x.metrics && x.metrics.length);
          return b && window.crossSeries ? window.crossSeries(b.id, b.metrics[0].id, {}) : null;
        }
      },
      exportCoefficient: {
        typedef: 'ExportCoefficient',
        required: ['preview', 'unit', 'byUf', 'national', 'timeseries'],
        produce: () => window.exportCoefficient ? window.exportCoefficient(null) : null
      },
      marketShare: {
        typedef: 'MarketShare',
        required: ['preview', 'unit', 'series', 'byProduct'],
        produce: () => window.marketShare ? window.marketShare(null) : null
      },
      priceSpread: {
        typedef: 'PriceSpread',
        required: ['preview', 'unit', 'series'],
        produce: () => window.priceSpread ? window.priceSpread(null) : null
      },
      tradeMirror: {
        typedef: 'TradeMirror',
        required: ['preview', 'unit', 'series', 'discrepancy'],
        produce: () => window.tradeMirror ? window.tradeMirror(null) : null
      },
      chainBalance: {
        typedef: 'ChainBalance',
        required: ['preview', 'unit', 'year', 'produced', 'exported', 'internal', 'domestic', 'expFrac', 'intFrac', 'domFrac', 'worldShare', 'worldTotal', 'exportUsd', 'sankey'],
        produce: () => window.chainBalance ? window.chainBalance(null, 2024) : null
      },
      harvestShipmentLag: {
        typedef: 'HarvestShipmentLag',
        required: ['preview', 'months', 'production', 'shipments', 'peakHarvest', 'peakShip', 'lagMonths', 'corrAtLag', 'lagProfile'],
        produce: () => window.harvestShipmentLag ? window.harvestShipmentLag(null) : null
      },
      valueAddedAnalysis: {
        typedef: 'ValueAddedAnalysis',
        required: ['preview', 'years', 'byLevel', 'series'],
        produce: () => window.valueAddedAnalysis ? window.valueAddedAnalysis(null) : null
      },
      marketNatureAnalysis: {
        typedef: 'MarketNatureAnalysis',
        required: ['preview', 'years', 'series', 'latest'],
        produce: () => window.marketNatureAnalysis ? window.marketNatureAnalysis() : null
      }
    }
  };

  // ── Runtime drift LINT ───────────────────────────────────────────────
  // Calls each live producer and collects any CONTRACTED key that is absent
  // from the returned object. Warns ONCE (console only — never touches data),
  // mirroring window.auditBancoCoverage. A null producer result is SKIPPED
  // (the banco doesn't serve that producer yet — e.g. snapshotFor for PEVS,
  // which is the data.js reference). Run it after the data layer has loaded.
  const missingKeys = (obj, required) => required.filter(k => !(k in obj));
  window.auditSnapshotContracts = function () {
    if (window.__contractsAudited) return;
    window.__contractsAudited = true;
    const C = window.SNAPSHOT_CONTRACTS;
    const bancos = window.visibleBancos ? window.visibleBancos() : window.BANCOS || [];
    const problems = [];
    Object.entries(C.perBanco).forEach(([name, spec]) => {
      bancos.forEach(b => {
        if (spec.appliesTo && !spec.appliesTo(b)) return;
        let obj;
        try {
          obj = spec.produce(b);
        } catch (e) {
          problems.push(`${name}(${b.id}) lançou: ${e.message}`);
          return;
        }
        if (obj == null) return; // not served here — skip
        const miss = missingKeys(obj, spec.required);
        const extra = spec.extra ? spec.extra(obj, b) : [];
        if (miss.length || extra.length) {
          problems.push(`${name}(${b.id}) [${spec.typedef}] → ${[...miss.map(k => 'falta `' + k + '`'), ...extra].join(', ')}`);
        }
      });
    });
    Object.entries(C.global).forEach(([name, spec]) => {
      let obj;
      try {
        obj = spec.produce();
      } catch (e) {
        problems.push(`${name} lançou: ${e.message}`);
        return;
      }
      if (obj == null) return;
      const miss = missingKeys(obj, spec.required);
      if (miss.length) problems.push(`${name} [${spec.typedef}] → ${miss.map(k => 'falta `' + k + '`').join(', ')}`);
    });
    if (problems.length) {
      console.warn('[contrato] shape drift detectado em ' + problems.length + ' produtor(es):\n  ' + problems.join('\n  ') + '\n→ alinhe o builder com contracts.js (SNAPSHOT_CONTRACTS + @typedef correspondente), ' + 'a fonte única do shape.');
    }
  };

  // Defer the audit until the full data layer has executed (all sync <script>
  // builders run before window 'load'). The Babel/JSX views run later but the
  // lint only needs the plain-JS producers, all loaded by now.
  if (document.readyState === 'complete') window.auditSnapshotContracts();else window.addEventListener('load', () => window.auditSnapshotContracts());
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "contracts.js", error: String((e && e.message) || e) }); }

// crossAnalytics.js
try { (() => {
// crossAnalytics.js — DATA CONTRACTS for the four analytical multi-source
// perspectives (export coefficient, world market share, farm-gate vs FOB
// price, trade mirror). SHAPES defined once in contracts.js (@typedef
// ExportCoefficient / MarketShare / PriceSpread / TradeMirror). Same handoff
// rule as crossSource.js: views read ONLY through these window functions; to
// go live the backend swaps each body for a real query and keeps the shape.
//
// The preview flag is now DERIVED per call from the source bancos' live
// status (see previewFor): an analytic shows the demo banner only while one of
// its sources isn't live. With MDIC COMEX (estavel) and UN Comtrade
// (beta) live, their analytics render on the representative snapshots
// without the banner; analytics that still touch SEFAZ stay preview until it
// connects. The IBGE side (production) is real.
//
// The product join (PEVS extractive code ↔ NCM/HS in trade bancos) is a
// crosswalk the backend will own; here `productCode` just reseeds/scales
// the synthetic series so the UI exercises the parameter end to end.

(function () {
  // Shared synth helpers (seeded, previewFor, productScale) live in
  // synthUtils.js; use them via window.* — no local copies.

  // Bigger agro/extractive states lean more export-oriented.
  const EXPORT_LEAN = {
    PA: 0.62,
    MT: 0.66,
    PR: 0.58,
    RS: 0.54,
    AM: 0.34,
    AC: 0.30,
    RO: 0.28,
    BA: 0.36,
    SC: 0.44,
    GO: 0.40,
    MA: 0.32,
    SP: 0.5
  };

  // ── (1) Export coefficient — production (PEVS) × export (MDIC) by UF ──
  //   SHAPE: contracts.js @typedef ExportCoefficient.
  window.exportCoefficient = function (productCode) {
    const scale = window.productScale(productCode);
    const rnd = window.seeded('coef:' + (productCode || 'all'));
    const byUf = (window.UF_DATA || []).map(u => {
      const production = u.q_mass * scale; // mil t (real PEVS side)
      const lean = (EXPORT_LEAN[u.uf] ?? 0.22) + (rnd() - 0.5) * 0.12;
      const coef = Math.max(0.03, Math.min(0.92, lean));
      return {
        uf: u.uf,
        name: u.name,
        region: u.region,
        col: u.col,
        row: u.row,
        production,
        exportV: production * coef,
        coefPct: coef * 100
      };
    });
    const production = byUf.reduce((s, d) => s + d.production, 0);
    const exportV = byUf.reduce((s, d) => s + d.exportV, 0);
    const coefNat = production ? exportV / production : 0;
    // National coefficient drifting up over the MDIC coverage (1997→2024).
    const ts = window.seeded('coefts:' + (productCode || 'all'));
    const timeseries = [];
    for (let y = 1997; y <= 2024; y++) {
      const t = (y - 1997) / 27;
      const v = coefNat * (0.72 + t * 0.4) * (1 + (ts() - 0.5) * 0.05);
      timeseries.push({
        y,
        v: Math.min(0.95, v) * 100
      });
    }
    return {
      preview: window.previewFor('ibge_pevs', 'mdic_comex'),
      unit: 'mil t',
      byUf,
      national: {
        production,
        exportV,
        coefPct: coefNat * 100
      },
      timeseries
    };
  };

  // ── (2) World market share — BR exports ÷ world exports (Comtrade) ────
  //   SHAPE: contracts.js @typedef MarketShare.
  window.marketShare = function (productCode) {
    const scale = window.productScale(productCode);
    const br = window.crossSeries('mdic_comex', 'exp_value', {
      y0: 1997,
      y1: 2024
    });
    const world = window.crossSeries('un_comtrade', 'world_exp', {
      y0: 1997,
      y1: 2024
    });
    const series = br.points.map((d, i) => {
      const brV = d.v * scale;
      const worldV = (world.points[i]?.v || 1) * (0.6 + 0.4 * scale); // world also narrows for a single commodity
      return {
        y: d.y,
        br: brV,
        world: worldV,
        share: brV / worldV * 100
      };
    });
    const byProduct = (window.PRODUCTS || []).map(p => {
      const r = window.seeded('share:' + p.code)();
      return {
        code: p.code,
        name: p.name,
        share: 2 + r * 26
      };
    }).sort((a, b) => b.share - a.share);
    return {
      preview: window.previewFor('mdic_comex', 'un_comtrade'),
      unit: 'US$ bi',
      series,
      byProduct
    };
  };

  // ── (3) Farm-gate vs FOB price — PEVS implied price × MDIC export price ─
  //   SHAPE: contracts.js @typedef PriceSpread.
  window.priceSpread = function (productCode) {
    const fobS = window.crossSeries('mdic_comex', 'exp_price', {
      y0: 1997,
      y1: 2024
    });
    const rnd = window.seeded('gate:' + (productCode || 'all'));
    const series = fobS.points.map((d, i) => {
      const t = i / (fobS.points.length - 1 || 1);
      // gate captures a shrinking fraction of FOB over time (widening spread)
      const frac = (0.50 - t * 0.16) * (1 + (rnd() - 0.5) * 0.06);
      const fob = d.v;
      const gate = fob * frac;
      return {
        y: d.y,
        gate,
        fob,
        spread: fob - gate,
        markup: gate ? fob / gate : 0
      };
    });
    return {
      preview: window.previewFor('ibge_pevs', 'mdic_comex'),
      unit: 'US$/kg',
      series
    };
  };

  // ── (4) Trade mirror — same exports reported by different sources ─────
  //   SHAPE: contracts.js @typedef TradeMirror.
  window.tradeMirror = function (productCode) {
    const scale = window.productScale(productCode);
    const base = window.crossSeries('mdic_comex', 'exp_value', {
      y0: 1997,
      y1: 2024
    });
    const rc = window.seeded('mirror_c:' + (productCode || 'all'));
    const rp = window.seeded('mirror_p:' + (productCode || 'all'));
    const series = base.points.map(d => {
      const mdic = d.v * scale;
      const comtrade = mdic * (0.965 + (rc() - 0.5) * 0.05); // slight under-report
      const partners = mdic * (1.045 + (rp() - 0.5) * 0.06); // partners over-report
      return {
        y: d.y,
        mdic,
        comtrade,
        partners
      };
    });
    const discrepancy = series.map(d => {
      const vals = [d.mdic, d.comtrade, d.partners];
      const max = Math.max(...vals),
        min = Math.min(...vals);
      const mean = (d.mdic + d.comtrade + d.partners) / 3 || 1;
      return {
        y: d.y,
        v: (max - min) / mean * 100
      };
    });
    return {
      preview: window.previewFor('mdic_comex', 'un_comtrade'),
      unit: 'US$ bi',
      series,
      discrepancy
    };
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "crossAnalytics.js", error: String((e && e.message) || e) }); }

// crossChain.js
try { (() => {
// crossChain.js — EXTENDED cross-source contracts. SHAPES defined once in
// contracts.js (@typedef ChainBalance / HarvestShipmentLag). These go beyond
// the annual scalar series of crossSource.js, in the two ways flagged as
// "extend the contract, not the layout":
//
//   chainBalance(productCode, year)  → a RECONCILED supply balance:
//       produced = internal + exported + domestic   (mass conserved),
//       plus the export's slice of the world market (value basis).
//       Shape feeds the existing <SankeyChart> (nodes/links) unchanged.
//
//   harvestShipmentLag(productCode)  → MONTHLY profiles + lead-lag:
//       harvest (modeled monthly from annual PEVS) vs shipments (MDIC
//       monthly), with the cross-correlation over ±6 months.
//
// Both are PREVIEW until the trade/internal bancos go live. Real wiring:
// swap the synthetic bodies for queries returning the SAME shapes.
//
// NOTE on resolution: PEVS production is published ANNUALLY, so the
// monthly harvest curve here is a MODEL (a seasonal distribution of the
// annual total), not measured monthly data — the view labels it as such.

(function () {
  // Shared synth helpers (previewFor, seeded, productScale) live in
  // synthUtils.js; used here via window.* — no local copies.

  // ── (5) Chain balance — reconciled mass split + world-market context ──
  window.chainBalance = function (productCode, year) {
    year = year || 2024;
    const scale = window.productScale(productCode);
    const ovTs = window.OVERVIEW_TS || [];
    const row = ovTs.find(d => d.y === year) || ovTs[ovTs.length - 1];
    const produced = (row?.q_mass || 2884) * scale; // mil t (real PEVS side)

    const rnd = window.seeded('chain:' + (productCode || 'all') + ':' + year);
    let expFrac = 0.34 + rnd() * 0.12; // exported share of production
    let intFrac = 0.26 + rnd() * 0.12; // internally traded share
    if (expFrac + intFrac > 0.86) {
      const k = 0.86 / (expFrac + intFrac);
      expFrac *= k;
      intFrac *= k;
    }
    const exported = produced * expFrac;
    const internal = produced * intFrac;
    const domestic = Math.max(0, produced - exported - internal); // consumption / stock residual

    // Export's slice of the world market (value basis, via marketShare).
    const ms = window.marketShare ? window.marketShare(productCode) : null;
    const msRow = ms ? ms.series.find(d => d.y === year) || ms.series[ms.series.length - 1] : null;
    const worldShare = msRow?.share || 0;
    const worldTotal = msRow?.world || 0;
    const exportUsd = msRow?.br || 0;

    // Supply balance as a 2-column flow (Production → destinations) for SankeyChart.
    const nodes = [{
      id: 'prod',
      label: 'Produção',
      side: 'origin',
      value: produced
    }, {
      id: 'exp',
      label: 'Exportação',
      side: 'dest',
      value: exported
    }, {
      id: 'int',
      label: 'Comércio interno',
      side: 'dest',
      value: internal
    }, {
      id: 'dom',
      label: 'Consumo / estoque',
      side: 'dest',
      value: domestic
    }];
    const links = [{
      source: 'prod',
      target: 'exp',
      value: exported
    }, {
      source: 'prod',
      target: 'int',
      value: internal
    }, {
      source: 'prod',
      target: 'dom',
      value: domestic
    }];
    return {
      preview: window.previewFor('ibge_pevs', 'sefaz_nf', 'mdic_comex', 'un_comtrade'),
      unit: 'mil t',
      year,
      produced,
      exported,
      internal,
      domestic,
      expFrac: exported / (produced || 1),
      intFrac: internal / (produced || 1),
      domFrac: domestic / (produced || 1),
      worldShare,
      worldTotal,
      exportUsd,
      sankey: {
        nodes,
        links
      }
    };
  };

  // ── (6) Harvest → shipment lead-lag ───────────────────────────────────
  window.harvestShipmentLag = function (productCode) {
    const rnd = window.seeded('lag:' + (productCode || 'all'));
    const peak = Math.floor(rnd() * 12); // harvest peak month (0–11)
    const lagTrue = 1 + Math.floor(rnd() * 4); // baked-in shipment lag (1–4 months)

    const prod = [],
      ship = [];
    const circDist = (m, c) => Math.min((m - c + 12) % 12, (c - m + 12) % 12);
    const shipPeak = (peak + lagTrue) % 12;
    for (let m = 0; m < 12; m++) {
      prod.push(1 + Math.exp(-Math.pow(circDist(m, peak) / 2.2, 2)) * 2.6 + (rnd() - 0.5) * 0.5);
      ship.push(1 + Math.exp(-Math.pow(circDist(m, shipPeak) / 2.7, 2)) * 2.2 + (rnd() - 0.5) * 0.5);
    }
    const norm = a => {
      const mx = Math.max(...a);
      return a.map(v => v / mx * 100);
    };
    const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
    const mp = mean(prod),
      msh = mean(ship);
    // corr at lag L = corr(production[m], shipments[m+L]); +L ⇒ shipments lag harvest by L.
    const corrAt = lag => {
      let num = 0,
        dp = 0,
        ds = 0;
      for (let m = 0; m < 12; m++) {
        const si = (m + lag + 12) % 12;
        const xp = prod[m] - mp,
          xs = ship[si] - msh;
        num += xp * xs;
        dp += xp * xp;
        ds += xs * xs;
      }
      return dp && ds ? num / Math.sqrt(dp * ds) : 0;
    };
    const lagProfile = [];
    for (let l = -6; l <= 6; l++) lagProfile.push({
      lag: l,
      corr: corrAt(l)
    });
    const best = lagProfile.reduce((b, d) => d.corr > b.corr ? d : b, lagProfile[0]);
    return {
      preview: window.previewFor('ibge_pevs', 'mdic_comex'),
      months: window.MONTH_LABELS || ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
      production: norm(prod),
      shipments: norm(ship),
      peakHarvest: peak,
      peakShip: shipPeak,
      lagMonths: best.lag,
      corrAtLag: best.corr,
      lagProfile
    };
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "crossChain.js", error: String((e && e.message) || e) }); }

// crossSource.js
try { (() => {
// crossSource.js — the DATA CONTRACT behind the "Cruzamento entre fontes"
// perspective. It exposes one comparable ANNUAL time series per
// (banco, metric) pair, so series from DIFFERENT bancos can be charted on
// the same time axis (e.g. IBGE annual production × MDIC annual exports).
//
// ─────────────────────────────────────────────────────────────────────
// WHY THIS FILE EXISTS (handoff note for the backend team)
//   The cross-source VIEW (ViewCrossSource.jsx) and CHARTS (Charts.cross.jsx)
//   never touch raw data — they only consume `window.crossSeries(...)`.
//   To wire a real banco you replace ONE builder body below and keep the
//   returned shape identical. No view/chart/router code changes.
//
// CONTRACT
//   window.crossSeries(bancoId, metricId, { y0, y1 }) → SeriesResult | null
//
//   SHAPE (SeriesResult) is defined once in contracts.js (@typedef
//   SeriesResult) — the single source of truth. Two series share a Y axis /
//   can form a ratio IFF their `unit` strings are identical (see
//   ViewCrossSource); `family` groups them more loosely for labelling.
//
//   When the banco goes live: in SERIES_BUILDERS, swap the synthetic body
//   for `dataStore.get(bancoId)` reads (or a real query) that emit the same
//   { y, v } array, and set preview:false (or derive it from banco.status).
// ─────────────────────────────────────────────────────────────────────

(function () {
  // Deterministic PRNG (window.seeded) and macro-shock curve (window.macroShock)
  // live in synthUtils.js — used here via window.* so the synthetic series stay
  // in lockstep with the other cross-source / preview builders.

  // Build a smooth growing synthetic annual series from v0→vT across the
  // metric's coverage, with mild seeded noise + macro shocks. Returns the
  // FULL native-coverage array; crossSeries() trims it to the request window.
  function synthSeries(seed, [start, end], v0, vT) {
    const rnd = window.seeded(seed);
    const n = end - start;
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const y = start + i;
      const t = i / (n || 1);
      // gentle S-curve so growth accelerates then eases
      const ease = t * t * (3 - 2 * t);
      const base = v0 + (vT - v0) * ease;
      const noise = 1 + (rnd() - 0.5) * 0.07;
      pts.push({
        y,
        v: base * noise * window.macroShock(y)
      });
    }
    return pts;
  }

  // ── Real (live) adapter: IBGE PEVS — derive annual series from the
  //    in-memory Gold mock (window.OVERVIEW_TS). These are REAL numbers in
  //    the mock's native magnitudes; the display units below match them.
  function pevs(metricId) {
    const ts = window.OVERVIEW_TS || [];
    if (metricId === 'prod_value') return ts.map(d => ({
      y: d.y,
      v: d.v
    })); // R$ bi
    if (metricId === 'prod_mass') return ts.map(d => ({
      y: d.y,
      v: d.q_mass
    })); // mil t
    if (metricId === 'prod_volume') return ts.map(d => ({
      y: d.y,
      v: d.q_vol
    })); // mi m³
    return [];
  }

  // ── Display unit per (banco, metric). Conceptual units live in bancos.js
  //    (metric.unit); these add the working magnitude used on the axes.
  const DISPLAY_UNIT = {
    'ibge_pevs:prod_value': 'R$ bi',
    'ibge_pevs:prod_mass': 'mil t',
    'ibge_pevs:prod_volume': 'mi m³',
    'mdic_comex:exp_value': 'US$ bi',
    'mdic_comex:imp_value': 'US$ bi',
    'mdic_comex:exp_weight': 'mil t',
    'mdic_comex:exp_price': 'US$/kg',
    'un_comtrade:exp_value': 'US$ bi',
    'un_comtrade:imp_value': 'US$ bi',
    'un_comtrade:world_exp': 'US$ bi',
    'sefaz_nf:internal_value': 'R$ bi',
    'sefaz_nf:internal_weight': 'mil t',
    'sefaz_nf:icms_total': 'R$ bi',
    'ibge_pam:prod_value': 'R$ bi',
    'ibge_pam:prod_quantity': 'mi t',
    'ibge_pam:area_harvested': 'mi ha',
    'ibge_pam:yield': 'kg/ha'
  };

  // ── SERIES BUILDERS — the ONE place per (banco, metric) where data is
  //    produced. Live banco → real reads. Soon bancos → synthetic preview.
  //    Replace a synthetic body with a real query and the rest is unchanged.
  //    Demo magnitude ranges [v0, vT] live in demoFixture.js (window.DEMO_PARAMS
  //    .crossMagnitudes); edit that file to demo a different chain. The seed
  //    strings stay fixed so the synthetic output is deterministic across runs.
  const MAG = window.DEMO_PARAMS && window.DEMO_PARAMS.crossMagnitudes || {};
  const magSeries = (seed, key, cov) => {
    const [v0, vT] = MAG[key] || [1, 2];
    return synthSeries(seed, cov, v0, vT);
  };
  const SERIES_BUILDERS = {
    // ---- IBGE PEVS (live) ----
    'ibge_pevs:prod_value': () => pevs('prod_value'),
    'ibge_pevs:prod_mass': () => pevs('prod_mass'),
    'ibge_pevs:prod_volume': () => pevs('prod_volume'),
    // ---- MDIC COMEX (representative demo magnitudes — castanha/nut chain) ----
    'mdic_comex:exp_value': cov => magSeries('mdic:exp_value', 'mdic_comex:exp_value', cov),
    'mdic_comex:imp_value': cov => magSeries('mdic:imp_value', 'mdic_comex:imp_value', cov),
    'mdic_comex:exp_weight': cov => magSeries('mdic:exp_weight', 'mdic_comex:exp_weight', cov),
    // price = value(US$) ÷ weight, kept consistent with the two series above.
    'mdic_comex:exp_price': cov => {
      const val = magSeries('mdic:exp_value', 'mdic_comex:exp_value', cov); // US$ bi
      const wt = magSeries('mdic:exp_weight', 'mdic_comex:exp_weight', cov); // mil t
      return val.map((d, i) => ({
        y: d.y,
        v: d.v * 1e9 / ((wt[i].v || 1) * 1e6)
      })); // US$/kg
    },
    // ---- UN COMTRADE (representative demo magnitudes — HS 0801) ----
    'un_comtrade:exp_value': cov => magSeries('comtrade:exp_value', 'un_comtrade:exp_value', cov),
    'un_comtrade:imp_value': cov => magSeries('comtrade:imp_value', 'un_comtrade:imp_value', cov),
    'un_comtrade:world_exp': cov => magSeries('comtrade:world_exp', 'un_comtrade:world_exp', cov),
    // ---- SEFAZ NFe (preview) ----
    'sefaz_nf:internal_value': cov => magSeries('sefaz:internal_value', 'sefaz_nf:internal_value', cov),
    'sefaz_nf:internal_weight': cov => magSeries('sefaz:internal_weight', 'sefaz_nf:internal_weight', cov),
    'sefaz_nf:icms_total': cov => magSeries('sefaz:icms_total', 'sefaz_nf:icms_total', cov),
    // ---- IBGE PAM (representative demo magnitudes — lavouras) ----
    'ibge_pam:prod_value': cov => magSeries('pam:prod_value', 'ibge_pam:prod_value', cov),
    'ibge_pam:prod_quantity': cov => magSeries('pam:prod_quantity', 'ibge_pam:prod_quantity', cov),
    'ibge_pam:area_harvested': cov => magSeries('pam:area_harvested', 'ibge_pam:area_harvested', cov),
    'ibge_pam:yield': cov => magSeries('pam:yield', 'ibge_pam:yield', cov)
  };

  // ── Public: one comparable annual series ─────────────────────────────
  window.crossSeries = function (bancoId, metricId, win) {
    const bancoMeta = window.bancoById ? window.bancoById(bancoId) : null;
    const metricMeta = window.metricById ? window.metricById(bancoId, metricId) : null;
    if (!bancoMeta || !metricMeta) return null;
    const key = bancoId + ':' + metricId;
    const cov = metricMeta.years || [1986, 2024];
    const builder = SERIES_BUILDERS[key];
    const raw = builder ? builder(cov) : [];
    const y0 = win && win.y0 || cov[0];
    const y1 = win && win.y1 || cov[1];
    const points = raw.filter(d => d.y >= y0 && d.y <= y1);
    return {
      banco: bancoId,
      metric: metricId,
      bancoMeta,
      metricMeta,
      key,
      label: metricMeta.label,
      unit: DISPLAY_UNIT[key] || metricMeta.unit || '',
      family: metricMeta.family,
      preview: bancoMeta.status !== 'live',
      coverage: cov,
      points
    };
  };

  // ── Public: the common comparable window across a set of refs ─────────
  //   refs: [{ banco, metric }]. Returns { y0, y1, union:[a,b] }.
  //   y0..y1 is the INTERSECTION (where every series has data); union is the
  //   widest span any series covers (used as the slider bounds).
  window.crossCommonWindow = function (refs) {
    const covs = (refs || []).map(r => window.metricById(r.banco, r.metric)).filter(Boolean).map(m => m.years || [1986, 2024]);
    if (!covs.length) return {
      y0: 1997,
      y1: 2024,
      union: [1986, 2024]
    };
    const y0 = Math.max(...covs.map(c => c[0])); // latest start
    const y1 = Math.min(...covs.map(c => c[1])); // earliest end
    const union = [Math.min(...covs.map(c => c[0])), Math.max(...covs.map(c => c[1]))];
    // If coverages don't overlap, fall back to the union so the chart still draws.
    return y0 <= y1 ? {
      y0,
      y1,
      union
    } : {
      y0: union[0],
      y1: union[1],
      union
    };
  };

  // Coverage lint: every metric of every visible banco needs a series builder
  // (otherwise it appears in the picker but plots an empty line).
  if (window.auditBancoCoverage) {
    window.auditBancoCoverage('cruzamento · series builders (crossSource.js)', b => (b.metrics || []).every(m => SERIES_BUILDERS[b.id + ':' + m.id]));
  }
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "crossSource.js", error: String((e && e.message) || e) }); }

// csvExport.js
try { (() => {
// csvExport.js — exports the data behind the ACTIVE view, honouring the
// active filters (period, basket, states, value range, quality flags).
// "Exactly what the view shows" — e.g. if the period filter excludes
// pre-2002, the file starts at 2002. Builds a CSV string and triggers a
// client-side download. (In the Cloud Run deploy, the same filtered slice
// is what's held in memory; this writes it out verbatim.)

(function () {
  // A view is exportable when its registry entry (views.js) declares
  // `exportable: true` — i.e. it has an applyFilters-backed tabular slice.
  // Selfdata preview views (fluxos, parceiros, sazonalidade), the cross-source
  // perspectives and the docs views omit the flag, so the export button is
  // hidden for them (see window.canExportView). Single source of truth: the
  // registry, not a parallel id list here.
  window.canExportView = view => !!(window.viewById && window.viewById(view)?.exportable);
  function toCSV(headers, rows) {
    const esc = v => {
      if (v == null) return '';
      const s = String(v);
      return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const head = headers.join(';'); // pt-BR friendly delimiter
    const body = rows.map(r => r.map(esc).join(';')).join('\n');
    return '\uFEFF' + head + '\n' + body; // BOM for Excel UTF-8
  }
  function download(filename, csv) {
    const blob = new Blob([csv], {
      type: 'text/csv;charset=utf-8;'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // Build the rows for the active view from the FILTERED datasets.
  function buildRows(ctx) {
    const {
      view,
      summary,
      conventions,
      database
    } = ctx;
    const conv = conventions || window.DEFAULT_CONVENTIONS;
    const f = window.applyFilters(summary || {}, database);
    const sym = (window.CURRENCY_FX[conv.currency] || {
      symbol: 'R$'
    }).symbol;
    const PRODS = f.products;
    const nameOf = c => (PRODS.find(p => p.code === c) || {}).name || c;

    // value/qty display transforms (same as the views use)
    const dispV = vBi => window.applyConv(vBi, conv);
    switch (view) {
      case 'value':
      case 'overview':
        {
          // annual aggregate series (value + qty per family)
          const headers = ['ano', `valor_${conv.currency}`, 'qtd_massa_t', 'qtd_volume_m3'];
          const rows = f.ts.map(d => [d.y, Math.round(dispV(d.v * 1e9)), Math.round(d.q_mass * 1e3), Math.round(d.q_vol * 1e6)]);
          return {
            headers,
            rows,
            subject: 'serie_agregada'
          };
        }
      case 'product_profile':
      case 'product_compare':
        {
          // per-product annual series
          const headers = ['ano', 'codigo', 'produto', `valor_${conv.currency}`, 'quantidade', 'familia'];
          const rows = [];
          Object.entries(f.productTS).forEach(([code, series]) => {
            const fam = (PRODS.find(p => p.code === code) || {}).family;
            series.forEach(d => rows.push([d.y, code, nameOf(code), Math.round(dispV(d.v * 1e6)), Math.round(d.q * 1e3), fam]));
          });
          return {
            headers,
            rows,
            subject: 'series_por_produto'
          };
        }
      case 'geo':
        {
          const headers = ['uf', 'nome', 'regiao', `valor_${conv.currency}`, 'qtd_massa_t', 'qtd_volume_m3'];
          const rows = f.ufData.map(u => [u.uf, u.name, u.region, Math.round(dispV(u.value * 1e6)), Math.round(u.q_mass * 1e3), Math.round(u.q_vol * 1e6)]);
          return {
            headers,
            rows,
            subject: 'distribuicao_geografica'
          };
        }
      case 'concentration':
        {
          const headers = ['uf', 'nome', 'regiao', `valor_${conv.currency}`];
          const rows = f.ufData.slice().sort((a, b) => b.value - a.value).map(u => [u.uf, u.name, u.region, Math.round(dispV(u.value * 1e6))]);
          return {
            headers,
            rows,
            subject: 'concentracao'
          };
        }
      case 'quality':
        {
          const headers = ['flag', 'descricao', 'linhas', 'participacao'];
          const rows = f.qualityFlags.map(q => [q.id, q.label, q.count, (q.share * 100).toFixed(2).replace('.', ',') + '%']);
          return {
            headers,
            rows,
            subject: 'qualidade'
          };
        }
      default:
        return null;
    }
  }

  // Public entry — called by the "Exportar CSV" button.
  window.exportActiveTableCSV = function (ctx) {
    const banco = window.bancoById ? window.bancoById(ctx.database) : null;
    // Only live bancos hold real rows; soon bancos have nothing to export.
    if (!banco || banco.status !== 'live') {
      console.warn('[csv] banco não disponível para exportação:', ctx.database);
      return;
    }
    const built = buildRows(ctx);
    if (!built || !built.rows.length) {
      console.warn('[csv] nada a exportar para a view', ctx.view);
      return;
    }
    const period = ctx.summary && ctx.summary.startDate ? `${ctx.summary.startDate.slice(0, 4)}-${(ctx.summary.endDate || '').slice(0, 4)}` : 'completo';
    const fname = `${banco.short.replace(/\s+/g, '_').toLowerCase()}_${built.subject}_${period}.csv`;
    download(fname, toCSV(built.headers, built.rows));
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "csvExport.js", error: String((e && e.message) || e) }); }

// data.js
try { (() => {
// Synthetic data for the commodity dashboard mock.
// Shape mirrors the gold_pevs_production table (one row per
// ano × UF × município × código_produto in the real pipeline).
//
// IMPORTANT — unit families
//   PEVS measures volume two ways depending on the commodity:
//     · 'mass'   → t / kg            (castanha, açaí, erva-mate, carvão…)
//     · 'volume' → m³ / L            (madeira em tora, lenha)
//   Quantities of different families MUST NOT be aggregated.
//   Value (BRL real) is family-agnostic and always aggregatable.

// ────────────────────────────────────────────────────────────────────
// Products
// ────────────────────────────────────────────────────────────────────
window.PRODUCTS = [{
  code: '49101',
  name: 'Castanha-do-pará',
  unit: 't',
  family: 'mass'
}, {
  code: '49103',
  name: 'Açaí (fruto)',
  unit: 't',
  family: 'mass'
}, {
  code: '49105',
  name: 'Palmito',
  unit: 't',
  family: 'mass'
}, {
  code: '49106',
  name: 'Amêndoa de babaçu',
  unit: 't',
  family: 'mass'
}, {
  code: '49108',
  name: 'Erva-mate',
  unit: 't',
  family: 'mass'
}, {
  code: '49112',
  name: 'Pinhão',
  unit: 't',
  family: 'mass'
}, {
  code: '49215',
  name: 'Madeira em tora',
  unit: 'm³',
  family: 'volume'
}, {
  code: '49216',
  name: 'Lenha',
  unit: 'm³',
  family: 'volume'
}, {
  code: '49218',
  name: 'Carvão vegetal',
  unit: 't',
  family: 'mass'
}, {
  code: '49221',
  name: 'Borracha (látex)',
  unit: 't',
  family: 'mass'
}, {
  code: '49222',
  name: 'Cera de carnaúba',
  unit: 't',
  family: 'mass'
}, {
  code: '49224',
  name: 'Piaçava (fibra)',
  unit: 't',
  family: 'mass'
}];

// Region affinity per PEVS product code — biases the synthetic per-UF
// allocation in ViewProductProfile so each product's UF ranking is plausible
// (castanha/açaí → Norte, erva-mate/pinhão → Sul, etc.). Keyed by the same
// product universe as window.PRODUCTS. Synthetic mock weighting, NOT measured
// data; replaced by a real per-UF aggregate when the Gold table lands. Lives
// HERE (not in the view) so the data layer stays the single source of truth.
window.PRODUCT_REGION_AFFINITY = {
  '49101': {
    N: 3.4
  },
  // castanha → Norte
  '49103': {
    N: 4.0
  },
  // açaí → Norte
  '49105': {
    SE: 1.6,
    S: 1.4
  },
  // palmito
  '49106': {
    NE: 3.2
  },
  // babaçu → Nordeste (MA/PI)
  '49108': {
    S: 4.2
  },
  // erva-mate → Sul
  '49112': {
    S: 5.0
  },
  // pinhão → Sul
  '49215': {
    N: 2.4,
    CO: 1.6
  },
  // madeira tora
  '49216': {
    S: 1.6,
    NE: 1.4
  },
  // lenha
  '49218': {
    CO: 2.2,
    SE: 1.6
  },
  // carvão → MG/MT
  '49221': {
    N: 3.0
  },
  // borracha → Norte (AC)
  '49222': {
    NE: 4.5
  },
  // carnaúba → Nordeste (CE/PI)
  '49224': {
    NE: 3.0
  } // piaçava → Nordeste/Norte
};

// ── Unit families registry ───────────────────────────────────────────
// REGISTRY-DRIVEN: each family is a physical DIMENSION. Quantities of
// different families are incommensurable and MUST NEVER be aggregated
// together (value/currency is the only family-agnostic aggregate).
// Each family declares a `base` unit and member `units` with `toBase`
// (multiply a quantity in that unit by toBase to get the base unit).
// Adding a unit = one entry; adding a family = one block. The data must
// tell each product its `family` + native `unit` (see SNAPSHOT_CONTRACTS).
//
// `unit`/`long` are kept for back-compat with existing views (default
// display unit + long name). Brazilian agribusiness set below.
window.UNIT_FAMILIES = {
  mass: {
    id: 'mass',
    label: 'Massa',
    unit: 't',
    long: 'toneladas',
    base: 't',
    color: 'var(--embrapa-green-darker)',
    units: [{
      id: 'kg',
      label: 'kg',
      long: 'quilograma',
      toBase: 0.001
    }, {
      id: 't',
      label: 't',
      long: 'tonelada',
      toBase: 1
    }, {
      id: '@',
      label: '@',
      long: 'arroba (15 kg)',
      toBase: 0.015
    }, {
      id: 'sc',
      label: 'sc',
      long: 'saca (60 kg)',
      toBase: 0.06,
      note: 'Saca de 60 kg (convenção; varia por commodity).'
    }]
  },
  volume: {
    id: 'volume',
    label: 'Volume',
    unit: 'm³',
    long: 'metros cúbicos',
    base: 'm³',
    color: 'var(--pres-yale-blue)',
    units: [{
      id: 'L',
      label: 'L',
      long: 'litro',
      toBase: 0.001
    }, {
      id: 'hL',
      label: 'hL',
      long: 'hectolitro',
      toBase: 0.1
    }, {
      id: 'm³',
      label: 'm³',
      long: 'metro cúbico',
      toBase: 1
    }]
  },
  energia: {
    id: 'energia',
    label: 'Energia',
    unit: 'MWh',
    long: 'megawatt-hora',
    base: 'MWh',
    color: 'var(--viz-3)',
    units: [{
      id: 'kWh',
      label: 'kWh',
      long: 'quilowatt-hora',
      toBase: 0.001
    }, {
      id: 'MWh',
      label: 'MWh',
      long: 'megawatt-hora',
      toBase: 1
    }, {
      id: 'GJ',
      label: 'GJ',
      long: 'gigajoule',
      toBase: 0.277778
    }, {
      id: 'boe',
      label: 'boe',
      long: 'barril equiv. petróleo',
      toBase: 1.62803
    }]
  },
  contagem: {
    id: 'contagem',
    label: 'Contagem',
    unit: 'un',
    long: 'unidades',
    base: 'un',
    color: 'var(--viz-9)',
    units: [{
      id: 'un',
      label: 'un',
      long: 'unidade',
      toBase: 1
    }, {
      id: 'dz',
      label: 'dz',
      long: 'dúzia',
      toBase: 12
    }, {
      id: 'milheiro',
      label: 'milheiro',
      long: 'milheiro (1.000)',
      toBase: 1000
    }, {
      id: 'cab',
      label: 'cab',
      long: 'cabeça',
      toBase: 1
    }]
  },
  area: {
    id: 'area',
    label: 'Área',
    unit: 'ha',
    long: 'hectares',
    base: 'ha',
    color: 'var(--viz-10)',
    units: [{
      id: 'm²',
      label: 'm²',
      long: 'metro quadrado',
      toBase: 0.0001
    }, {
      id: 'ha',
      label: 'ha',
      long: 'hectare',
      toBase: 1
    }, {
      id: 'alq',
      label: 'alq',
      long: 'alqueire (~2,42 ha)',
      toBase: 2.42,
      note: 'Alqueire paulista; varia por região.'
    }]
  },
  // INTENSITY family (a ratio: production per unit area). Like every other
  // family it is incommensurable with the rest and MUST NEVER be summed — a
  // yield is averaged (area-weighted), never added. Base = kg/ha; t/ha and
  // sc/ha (60 kg sack per hectare) convert by their mass-per-hectare factor.
  rendimento: {
    id: 'rendimento',
    label: 'Rendimento',
    unit: 'kg/ha',
    long: 'quilogramas por hectare',
    base: 'kg/ha',
    color: 'var(--viz-6)',
    intensity: true,
    units: [{
      id: 'kg/ha',
      label: 'kg/ha',
      long: 'quilograma por hectare',
      toBase: 1
    }, {
      id: 't/ha',
      label: 't/ha',
      long: 'tonelada por hectare',
      toBase: 1000
    }, {
      id: 'sc/ha',
      label: 'sc/ha',
      long: 'saca (60 kg) por hectare',
      toBase: 60,
      note: 'Saca de 60 kg/ha (convenção; varia por commodity).'
    }]
  }
};

// Default display unit per family (used to seed conventions).
window.defaultUnitOf = familyId => (window.UNIT_FAMILIES[familyId] || {}).unit || '';
// Lookup a unit's toBase factor within its family.
window.unitToBase = (familyId, unitId) => {
  const fam = window.UNIT_FAMILIES[familyId];
  const u = fam && (fam.units || []).find(x => x.id === unitId);
  return u ? u.toBase : 1;
};
// Convert a quantity from one unit to another WITHIN the same family.
window.convertUnit = (value, familyId, fromUnit, toUnit) => {
  if (value == null) return null;
  const inBase = value * window.unitToBase(familyId, fromUnit);
  return inBase / window.unitToBase(familyId, toUnit);
};
window.familiesInBasket = (productCodes, bancoId) => {
  // Banco-aware: resolve the ACTIVE banco's product list (snapshot first, then
  // the synthetic builder for pre-load, then PEVS globals). This keeps a
  // mass-only banco (COMEX/Comtrade) from showing spurious volume controls.
  const snap = bancoId && window.dataStore && window.dataStore.get && window.dataStore.get(bancoId) || bancoId && window.snapshotFor && window.snapshotFor(bancoId) || null;
  const products = snap && snap.products || window.PRODUCTS || [];
  const famOf = c => {
    const p = products.find(x => x.code === c);
    return p ? p.family : null;
  };
  // null/undefined = "no product filter" → all families present in the banco.
  // An explicit (possibly empty) selection is honoured literally: zero
  // products → zero families (nothing to measure).
  if (productCodes == null) return [...new Set(products.map(p => p.family))];
  return [...new Set(productCodes.map(c => famOf(c)).filter(Boolean))];
};

// ────────────────────────────────────────────────────────────────────
// Time series — annual, 1986…2024 (39 anos)
//   v       → valor real (IPCA · BRL bilhões)
//   q_mass  → quantidade agregada da família 'mass' (mil t)
//   q_vol   → quantidade agregada da família 'volume' (milhão m³)
// ────────────────────────────────────────────────────────────────────
window.OVERVIEW_TS = (() => {
  const seed = [[1986, 0.81, 1320, 58.2], [1987, 0.86, 1418, 60.1], [1988, 0.91, 1502, 61.4], [1989, 0.94, 1567, 62.7], [1990, 0.99, 1612, 61.9], [1991, 1.07, 1684, 62.4], [1992, 1.14, 1748, 63.1], [1993, 1.21, 1791, 62.8], [1994, 1.32, 1812, 61.7], [1995, 1.42, 1832, 60.4], [1996, 1.51, 1894, 59.8], [1997, 1.63, 1980, 59.1], [1998, 1.58, 2031, 58.4], [1999, 1.71, 2120, 57.6], [2000, 1.84, 2247, 56.8], [2001, 1.92, 2356, 55.9], [2002, 2.08, 2401, 55.1], [2003, 2.27, 2389, 54.3], [2004, 2.45, 2478, 53.6], [2005, 2.51, 2502, 52.7], [2006, 2.39, 2456, 51.9], [2007, 2.62, 2531, 51.2], [2008, 2.84, 2580, 50.4], [2009, 2.71, 2492, 49.6], [2010, 3.04, 2640, 48.8], [2011, 3.22, 2698, 48.1], [2012, 3.45, 2745, 47.4], [2013, 3.32, 2701, 46.8], [2014, 3.51, 2810, 46.2], [2015, 3.27, 2658, 45.7], [2016, 3.39, 2701, 45.1], [2017, 3.58, 2780, 44.6], [2018, 3.81, 2842, 44.0], [2019, 3.97, 2901, 43.5], [2020, 3.62, 2734, 42.8], [2021, 4.12, 2980, 42.4], [2022, 4.38, 3041, 42.1], [2023, 4.21, 2952, 41.6], [2024, 4.07, 2884, 41.0]];
  return seed.map(([y, v, q_mass, q_vol]) => ({
    y,
    v,
    q: q_mass,
    q_mass,
    q_vol
  }));
})();

// ────────────────────────────────────────────────────────────────────
// Per-product time series (value, qty) — used for stacked area + product detail
//   value is in R$ milhões, qty in product's native unit (t or m³, ×1000)
// ────────────────────────────────────────────────────────────────────
window.PRODUCT_TS = (() => {
  // Synthetic but plausible trajectories per product
  const profiles = {
    '49215': {
      v0: 1100,
      vT: 1431,
      q0: 28.4,
      qT: 27.1,
      family: 'volume'
    },
    // madeira tora
    '49216': {
      v0: 480,
      vT: 758,
      q0: 18.2,
      qT: 14.1,
      family: 'volume'
    },
    // lenha
    '49103': {
      v0: 80,
      vT: 505,
      q0: 110,
      qT: 1612,
      family: 'mass'
    },
    // açaí (explosivo)
    '49101': {
      v0: 220,
      vT: 379,
      q0: 41,
      qT: 28,
      family: 'mass'
    },
    // castanha
    '49218': {
      v0: 410,
      vT: 337,
      q0: 5800,
      qT: 4120,
      family: 'mass'
    },
    // carvão
    '49108': {
      v0: 180,
      vT: 295,
      q0: 260,
      qT: 412,
      family: 'mass'
    },
    // erva-mate
    '49221': {
      v0: 95,
      vT: 142,
      q0: 28,
      qT: 36,
      family: 'mass'
    },
    // borracha
    '49105': {
      v0: 35,
      vT: 78,
      q0: 22,
      qT: 41,
      family: 'mass'
    },
    // palmito
    '49222': {
      v0: 41,
      vT: 64,
      q0: 19,
      qT: 24,
      family: 'mass'
    },
    // cera carnaúba
    '49112': {
      v0: 18,
      vT: 31,
      q0: 6,
      qT: 11,
      family: 'mass'
    },
    // pinhão
    '49106': {
      v0: 67,
      vT: 22,
      q0: 102,
      qT: 38,
      family: 'mass'
    },
    // babaçu (decline)
    '49224': {
      v0: 12,
      vT: 9,
      q0: 8,
      qT: 6,
      family: 'mass'
    } // piaçava
  };
  const years = window.OVERVIEW_TS.map(d => d.y);
  const out = {};
  Object.entries(profiles).forEach(([code, p]) => {
    const series = years.map((y, i) => {
      const t = i / (years.length - 1);
      // mild noise so series read as real; `n` shifts the phase so value and
      // quantity get distinct (not identical) noise within the same product
      const noise = n => 1 + (Math.sin(i * 1.7 + code.charCodeAt(4) + n * 0.9) * 0.04 + Math.cos(i * 2.3 + n) * 0.03);
      return {
        y,
        v: (p.v0 + (p.vT - p.v0) * t) * noise(0),
        q: (p.q0 + (p.qT - p.q0) * t) * noise(1),
        family: p.family
      };
    });
    out[code] = series;
  });
  return out;
})();

// ────────────────────────────────────────────────────────────────────
// Geography — Brazilian states and regions
// ────────────────────────────────────────────────────────────────────
window.REGIONS = [{
  id: 'N',
  label: 'Norte',
  color: 'var(--viz-1)'
}, {
  id: 'NE',
  label: 'Nordeste',
  color: 'var(--viz-3)'
}, {
  id: 'CO',
  label: 'Centro-Oeste',
  color: 'var(--viz-5)'
}, {
  id: 'SE',
  label: 'Sudeste',
  color: 'var(--viz-2)'
}, {
  id: 'S',
  label: 'Sul',
  color: 'var(--viz-4)'
}];

// 27 UFs · grid position for tile map (col, row), region, totals (2024)
window.UF_DATA = [
// North
{
  uf: 'RR',
  name: 'Roraima',
  region: 'N',
  col: 3,
  row: 0,
  value: 28,
  q_mass: 12,
  q_vol: 0.8
}, {
  uf: 'AP',
  name: 'Amapá',
  region: 'N',
  col: 5,
  row: 0,
  value: 47,
  q_mass: 18,
  q_vol: 1.4
}, {
  uf: 'AM',
  name: 'Amazonas',
  region: 'N',
  col: 2,
  row: 1,
  value: 614,
  q_mass: 287,
  q_vol: 12.4
}, {
  uf: 'PA',
  name: 'Pará',
  region: 'N',
  col: 4,
  row: 1,
  value: 982,
  q_mass: 412,
  q_vol: 14.1
}, {
  uf: 'AC',
  name: 'Acre',
  region: 'N',
  col: 1,
  row: 2,
  value: 392,
  q_mass: 184,
  q_vol: 1.8
}, {
  uf: 'RO',
  name: 'Rondônia',
  region: 'N',
  col: 2,
  row: 2,
  value: 287,
  q_mass: 132,
  q_vol: 2.4
}, {
  uf: 'TO',
  name: 'Tocantins',
  region: 'N',
  col: 4,
  row: 2,
  value: 142,
  q_mass: 65,
  q_vol: 1.1
},
// Northeast
{
  uf: 'MA',
  name: 'Maranhão',
  region: 'NE',
  col: 5,
  row: 1,
  value: 174,
  q_mass: 82,
  q_vol: 2.6
}, {
  uf: 'CE',
  name: 'Ceará',
  region: 'NE',
  col: 6,
  row: 1,
  value: 121,
  q_mass: 58,
  q_vol: 0.9
}, {
  uf: 'RN',
  name: 'Rio Grande do Norte',
  region: 'NE',
  col: 7,
  row: 1,
  value: 38,
  q_mass: 18,
  q_vol: 0.4
}, {
  uf: 'PI',
  name: 'Piauí',
  region: 'NE',
  col: 5,
  row: 2,
  value: 87,
  q_mass: 41,
  q_vol: 1.2
}, {
  uf: 'PB',
  name: 'Paraíba',
  region: 'NE',
  col: 7,
  row: 2,
  value: 31,
  q_mass: 14,
  q_vol: 0.3
}, {
  uf: 'BA',
  name: 'Bahia',
  region: 'NE',
  col: 5,
  row: 3,
  value: 184,
  q_mass: 84,
  q_vol: 1.9
}, {
  uf: 'PE',
  name: 'Pernambuco',
  region: 'NE',
  col: 6,
  row: 3,
  value: 67,
  q_mass: 31,
  q_vol: 0.6
}, {
  uf: 'AL',
  name: 'Alagoas',
  region: 'NE',
  col: 6,
  row: 4,
  value: 21,
  q_mass: 9,
  q_vol: 0.2
}, {
  uf: 'SE',
  name: 'Sergipe',
  region: 'NE',
  col: 5,
  row: 5,
  value: 18,
  q_mass: 8,
  q_vol: 0.2
},
// Center-West
{
  uf: 'MT',
  name: 'Mato Grosso',
  region: 'CO',
  col: 3,
  row: 3,
  value: 538,
  q_mass: 240,
  q_vol: 8.7
}, {
  uf: 'MS',
  name: 'Mato Grosso do Sul',
  region: 'CO',
  col: 3,
  row: 4,
  value: 71,
  q_mass: 32,
  q_vol: 1.3
}, {
  uf: 'GO',
  name: 'Goiás',
  region: 'CO',
  col: 4,
  row: 4,
  value: 124,
  q_mass: 56,
  q_vol: 2.1
}, {
  uf: 'DF',
  name: 'Distrito Federal',
  region: 'CO',
  col: 4,
  row: 5,
  value: 4,
  q_mass: 2,
  q_vol: 0.1
},
// Southeast
{
  uf: 'MG',
  name: 'Minas Gerais',
  region: 'SE',
  col: 5,
  row: 4,
  value: 219,
  q_mass: 98,
  q_vol: 4.2
}, {
  uf: 'ES',
  name: 'Espírito Santo',
  region: 'SE',
  col: 6,
  row: 5,
  value: 48,
  q_mass: 22,
  q_vol: 0.7
}, {
  uf: 'RJ',
  name: 'Rio de Janeiro',
  region: 'SE',
  col: 5,
  row: 6,
  value: 19,
  q_mass: 8,
  q_vol: 0.3
}, {
  uf: 'SP',
  name: 'São Paulo',
  region: 'SE',
  col: 4,
  row: 6,
  value: 81,
  q_mass: 37,
  q_vol: 1.4
},
// South
{
  uf: 'PR',
  name: 'Paraná',
  region: 'S',
  col: 3,
  row: 6,
  value: 178,
  q_mass: 81,
  q_vol: 2.8
}, {
  uf: 'SC',
  name: 'Santa Catarina',
  region: 'S',
  col: 3,
  row: 7,
  value: 102,
  q_mass: 47,
  q_vol: 1.6
}, {
  uf: 'RS',
  name: 'Rio Grande do Sul',
  region: 'S',
  col: 3,
  row: 8,
  value: 156,
  q_mass: 71,
  q_vol: 2.4
}];
window.TOP_UFS = window.UF_DATA.slice().sort((a, b) => b.value - a.value).slice(0, 8);

// Top municípios (2024) — synthesized
window.TOP_MUNICIPIOS = [{
  city: 'Marabá',
  uf: 'PA',
  value: 198,
  q_mass: 84,
  product: 'Castanha-do-pará'
}, {
  city: 'Santarém',
  uf: 'PA',
  value: 167,
  q_mass: 0,
  q_vol: 4.8,
  product: 'Madeira em tora'
}, {
  city: 'Manaus',
  uf: 'AM',
  value: 142,
  q_mass: 61,
  product: 'Castanha-do-pará'
}, {
  city: 'Sinop',
  uf: 'MT',
  value: 128,
  q_mass: 0,
  q_vol: 3.4,
  product: 'Madeira em tora'
}, {
  city: 'Rio Branco',
  uf: 'AC',
  value: 119,
  q_mass: 52,
  product: 'Borracha (látex)'
}, {
  city: 'Curitibanos',
  uf: 'SC',
  value: 87,
  q_mass: 38,
  product: 'Erva-mate'
}, {
  city: 'Belém',
  uf: 'PA',
  value: 82,
  q_mass: 0,
  q_vol: 2.1,
  product: 'Madeira em tora'
}, {
  city: 'Porto Velho',
  uf: 'RO',
  value: 74,
  q_mass: 32,
  product: 'Castanha-do-pará'
}, {
  city: 'Tefé',
  uf: 'AM',
  value: 68,
  q_mass: 28,
  product: 'Açaí (fruto)'
}, {
  city: 'Erechim',
  uf: 'RS',
  value: 61,
  q_mass: 26,
  product: 'Erva-mate'
}];

// Region totals (2024) — sum from UF_DATA
window.REGION_DATA = (() => {
  const map = new Map(window.REGIONS.map(r => [r.id, {
    ...r,
    value: 0,
    q_mass: 0,
    q_vol: 0,
    ufs: 0
  }]));
  window.UF_DATA.forEach(u => {
    const r = map.get(u.region);
    r.value += u.value;
    r.q_mass += u.q_mass;
    r.q_vol += u.q_vol;
    r.ufs += 1;
  });
  return [...map.values()];
})();

// ────────────────────────────────────────────────────────────────────
// Top products composition (2024) for donut
// ────────────────────────────────────────────────────────────────────
window.TOP_PRODUCTS = [{
  name: 'Madeira em tora',
  share: 0.34,
  value: 1431,
  color: 'var(--viz-1)'
}, {
  name: 'Lenha',
  share: 0.18,
  value: 758,
  color: 'var(--viz-2)'
}, {
  name: 'Açaí (fruto)',
  share: 0.12,
  value: 505,
  color: 'var(--viz-3)'
}, {
  name: 'Castanha-do-pará',
  share: 0.09,
  value: 379,
  color: 'var(--viz-4)'
}, {
  name: 'Carvão vegetal',
  share: 0.08,
  value: 337,
  color: 'var(--viz-5)'
}, {
  name: 'Erva-mate',
  share: 0.07,
  value: 295,
  color: 'var(--viz-7)'
}, {
  name: 'Outros',
  share: 0.12,
  value: 506,
  color: 'var(--pres-gray-200)',
  muted: true
}];

// ────────────────────────────────────────────────────────────────────
// Quality dimension — flag distribution
// ────────────────────────────────────────────────────────────────────
window.QUALITY_FLAGS = [{
  id: 'OK',
  label: 'OK',
  color: 'var(--ok)',
  count: 9_421_802,
  share: 0.842
}, {
  id: 'ESTIMATED',
  label: 'Estimado',
  color: 'var(--viz-4)',
  count: 538_104,
  share: 0.048
}, {
  id: 'MISSING_VALUE',
  label: 'Valor ausente',
  color: 'var(--warn)',
  count: 412_730,
  share: 0.037
}, {
  id: 'MISSING_QUANTITY',
  label: 'Quantidade ausente',
  color: 'var(--info)',
  count: 287_412,
  share: 0.026
}, {
  id: 'BOUNDARY_HISTORIC',
  label: 'Limite histórico',
  color: 'var(--viz-7)',
  count: 312_488,
  share: 0.028
}, {
  id: 'OUTLIER',
  label: 'Outlier',
  color: 'var(--err)',
  count: 204_891,
  share: 0.019
}];

// Quality % over years (rate of OK rows)
window.QUALITY_TS = window.OVERVIEW_TS.map((d, i) => {
  // Newer data tends to be cleaner
  const t = i / (window.OVERVIEW_TS.length - 1);
  const ok = 0.71 + t * 0.18 + Math.sin(i * 1.3) * 0.015;
  const missing_value = 0.14 - t * 0.08 + Math.cos(i * 0.9) * 0.01;
  const missing_quantity = 0.07 - t * 0.04 + Math.cos(i * 1.4) * 0.008;
  const estimated = 0.04 + Math.sin(i * 0.7) * 0.008;
  const outlier = 0.02 + Math.cos(i * 2.1) * 0.006;
  const boundary = Math.max(0, 1 - ok - missing_value - missing_quantity - estimated - outlier);
  return {
    y: d.y,
    ok,
    missing_value,
    missing_quantity,
    estimated,
    outlier,
    boundary
  };
});

// Quality by product (2023, share of rows per flag)
window.QUALITY_BY_PRODUCT = [{
  code: '49101',
  name: 'Castanha-do-pará',
  OK: 0.78,
  MISSING_VALUE: 0.09,
  MISSING_QUANTITY: 0.05,
  ESTIMATED: 0.04,
  OUTLIER: 0.02,
  BOUNDARY_HISTORIC: 0.02
}, {
  code: '49103',
  name: 'Açaí (fruto)',
  OK: 0.91,
  MISSING_VALUE: 0.03,
  MISSING_QUANTITY: 0.02,
  ESTIMATED: 0.02,
  OUTLIER: 0.01,
  BOUNDARY_HISTORIC: 0.01
}, {
  code: '49108',
  name: 'Erva-mate',
  OK: 0.94,
  MISSING_VALUE: 0.02,
  MISSING_QUANTITY: 0.01,
  ESTIMATED: 0.02,
  OUTLIER: 0.005,
  BOUNDARY_HISTORIC: 0.005
}, {
  code: '49215',
  name: 'Madeira em tora',
  OK: 0.86,
  MISSING_VALUE: 0.05,
  MISSING_QUANTITY: 0.03,
  ESTIMATED: 0.03,
  OUTLIER: 0.02,
  BOUNDARY_HISTORIC: 0.01
}, {
  code: '49216',
  name: 'Lenha',
  OK: 0.83,
  MISSING_VALUE: 0.07,
  MISSING_QUANTITY: 0.04,
  ESTIMATED: 0.03,
  OUTLIER: 0.02,
  BOUNDARY_HISTORIC: 0.01
}, {
  code: '49218',
  name: 'Carvão vegetal',
  OK: 0.89,
  MISSING_VALUE: 0.04,
  MISSING_QUANTITY: 0.02,
  ESTIMATED: 0.03,
  OUTLIER: 0.01,
  BOUNDARY_HISTORIC: 0.01
}, {
  code: '49221',
  name: 'Borracha (látex)',
  OK: 0.71,
  MISSING_VALUE: 0.12,
  MISSING_QUANTITY: 0.07,
  ESTIMATED: 0.05,
  OUTLIER: 0.03,
  BOUNDARY_HISTORIC: 0.02
}, {
  code: '49105',
  name: 'Palmito',
  OK: 0.68,
  MISSING_VALUE: 0.14,
  MISSING_QUANTITY: 0.09,
  ESTIMATED: 0.05,
  OUTLIER: 0.02,
  BOUNDARY_HISTORIC: 0.02
}, {
  code: '49222',
  name: 'Cera de carnaúba',
  OK: 0.72,
  MISSING_VALUE: 0.11,
  MISSING_QUANTITY: 0.08,
  ESTIMATED: 0.04,
  OUTLIER: 0.03,
  BOUNDARY_HISTORIC: 0.02
}, {
  code: '49106',
  name: 'Amêndoa de babaçu',
  OK: 0.64,
  MISSING_VALUE: 0.17,
  MISSING_QUANTITY: 0.10,
  ESTIMATED: 0.05,
  OUTLIER: 0.02,
  BOUNDARY_HISTORIC: 0.02
}, {
  code: '49112',
  name: 'Pinhão',
  OK: 0.80,
  MISSING_VALUE: 0.08,
  MISSING_QUANTITY: 0.05,
  ESTIMATED: 0.04,
  OUTLIER: 0.02,
  BOUNDARY_HISTORIC: 0.01
}, {
  code: '49224',
  name: 'Piaçava (fibra)',
  OK: 0.66,
  MISSING_VALUE: 0.15,
  MISSING_QUANTITY: 0.09,
  ESTIMATED: 0.05,
  OUTLIER: 0.03,
  BOUNDARY_HISTORIC: 0.02
}];

// Quality issues by UF (2024) — % rows not OK
window.QUALITY_BY_UF = window.UF_DATA.map((u, i) => {
  const base = 0.04 + (u.value < 50 ? 0.15 : 0) + (u.region === 'N' || u.region === 'NE' ? 0.06 : 0);
  return {
    uf: u.uf,
    name: u.name,
    region: u.region,
    col: u.col,
    row: u.row,
    not_ok: Math.min(0.42, base + Math.sin(i * 1.3) * 0.03)
  };
});

// ────────────────────────────────────────────────────────────────────
// Sample table rows (gold_pevs_production recent rows)
// ────────────────────────────────────────────────────────────────────
window.SAMPLE_ROWS = [{
  year: 2023,
  uf: 'PA',
  city: 'Marabá',
  product: 'Castanha-do-pará',
  qty: 14829,
  unit: 't',
  val_ipca: 82471220,
  val_yearfx: 78213900,
  flag: 'OK'
}, {
  year: 2023,
  uf: 'AM',
  city: 'Manaus',
  product: 'Castanha-do-pará',
  qty: 9314,
  unit: 't',
  val_ipca: 51038910,
  val_yearfx: 48910420,
  flag: 'OK'
}, {
  year: 2023,
  uf: 'AC',
  city: 'Rio Branco',
  product: 'Castanha-do-pará',
  qty: 3207,
  unit: 't',
  val_ipca: null,
  val_yearfx: null,
  flag: 'MISSING_VALUE'
}, {
  year: 2023,
  uf: 'RO',
  city: 'Porto Velho',
  product: 'Castanha-do-pará',
  qty: 2118,
  unit: 't',
  val_ipca: 11092480,
  val_yearfx: 10721090,
  flag: 'OK'
}, {
  year: 2023,
  uf: 'PA',
  city: 'Santarém',
  product: 'Madeira em tora',
  qty: 47820,
  unit: 'm³',
  val_ipca: 198470100,
  val_yearfx: 191207800,
  flag: 'OK'
}, {
  year: 2023,
  uf: 'MT',
  city: 'Sinop',
  product: 'Madeira em tora',
  qty: 31204,
  unit: 'm³',
  val_ipca: 128471000,
  val_yearfx: 123092600,
  flag: 'OK'
}, {
  year: 2023,
  uf: 'RR',
  city: 'Caracaraí',
  product: 'Madeira em tora',
  qty: null,
  unit: 'm³',
  val_ipca: 4218900,
  val_yearfx: 4080010,
  flag: 'MISSING_QUANTITY'
}];

// ────────────────────────────────────────────────────────────────────
// Formatters
// ────────────────────────────────────────────────────────────────────
window.fmtBRL = n => {
  if (n == null) return '—';
  if (n >= 1e9) return 'R$ ' + (n / 1e9).toFixed(2).replace('.', ',') + ' bi';
  if (n >= 1e6) return 'R$ ' + (n / 1e6).toFixed(1).replace('.', ',') + ' mi';
  if (n >= 1e3) return 'R$ ' + (n / 1e3).toFixed(0).replace('.', ',') + ' mil';
  return 'R$ ' + n.toLocaleString('pt-BR');
};
window.fmtNum = (n, unit) => {
  if (n == null) return '—';
  return n.toLocaleString('pt-BR') + (unit ? ' ' + unit : '');
};
window.fmtPct = (n, digits = 1) => {
  if (n == null) return '—';
  return (n * 100).toFixed(digits).replace('.', ',') + '%';
};
window.fmtSigned = (n, digits = 1, suffix = '%') => {
  if (n == null) return '—';
  return (n >= 0 ? '+' : '') + n.toFixed(digits).replace('.', ',') + suffix;
};

// pt-BR number with a FIXED number of decimals (min = max), or '—' for null.
// Shared by the multi-source / curated views (was copy-pasted as caNum / msNum
// / chNum). `pctBR` appends '%' to an ALREADY-percentage value — distinct from
// fmtPct above, which multiplies a fraction by 100.
window.numBR = (v, d = 0) => v == null ? '—' : v.toLocaleString('pt-BR', {
  maximumFractionDigits: d,
  minimumFractionDigits: d
});
window.pctBR = (v, d = 1) => window.numBR(v, d) + '%';

// Compact row-counter label (mi / mil) for provenance "Linhas" readouts.
// Shared by MainScreen + ViewHealth (was duplicated verbatim in both).
window.fmtRows = n => {
  if (n >= 1e6) return (n / 1e6).toFixed(1).replace('.', ',') + ' mi';
  if (n >= 1e3) return (n / 1e3).toFixed(0) + ' mil';
  return n.toLocaleString('pt-BR');
};

// Compact axis-TICK formatter (mil/mi/bi/tri). Ticks are scale guides, not
// data: full pt-BR numbers (e.g. "4.534.380.148") overflow the ~30px gutter
// and get clipped. Abbreviating ONLY the ticks fixes the clip without touching
// KPIs/tables. Shared by every hand-rolled SVG chart (was duplicated as
// _fmtAxisNum in Charts.jsx and _csFmtAxis in Charts.cross.jsx).
window.fmtAxisTick = v => {
  if (v == null || isNaN(v)) return '';
  const a = Math.abs(v);
  if (a === 0) return '0';
  if (a < 1) return v.toLocaleString('pt-BR', {
    maximumFractionDigits: 2
  });
  // 1–10: keep one decimal so small-scale axes (e.g. US$/kg, ticks at
  // 0,57 · 1,14 · 1,72) don't collapse to duplicate integers ("2 · 2").
  if (a < 10) return v.toLocaleString('pt-BR', {
    maximumFractionDigits: 1
  });
  if (a < 1000) return v.toLocaleString('pt-BR', {
    maximumFractionDigits: 0
  });
  const U = [[1e12, ' tri'], [1e9, ' bi'], [1e6, ' mi'], [1e3, ' mil']];
  for (const [div, suf] of U) {
    if (a >= div) {
      const n = v / div;
      const s = Math.abs(n) >= 100 || Number.isInteger(n) ? n.toFixed(0) : n.toFixed(1);
      return s.replace('.', ',') + suf;
    }
  }
  return v.toLocaleString('pt-BR', {
    maximumFractionDigits: 0
  });
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "data.js", error: String((e && e.message) || e) }); }

// dataFilters.js
try { (() => {
// dataFilters.js — applies the active filter selection to every dataset
// used by the views, so charts/KPIs ONLY show rows that match.
//
// Input shape (from FilterMenu.onApply):
//   { basket:    string[]  // product codes;  null = all · [] = none
//   , flags:     string[]  // quality flags;   null = all · [] = none
//   , states:    string[]  // UF codes;        null = all · [] = none
//   , munis:     string[]  // município codes (cascade); narrows topMunis
//   , muniNames: string[]  // selected município NAMES — the data keys topMunis
//                          //   by city name, so the engine matches on these
//   , nations, regions     // cascade parents; their effect reaches the data
//                          //   through `states` (deselecting prunes states)
//   , startDate, endDate   // 'YYYY-MM-01'
//   , valueMin, valueMax   // row-level value filter (banco base currency)
//   }
//
// Output: { ts, productTS, ufData, regionData, topMunis, topProducts,
//           qualityFlags, qualityTs, selectedProducts, yearStart, yearEnd, _shares }

(function () {
  const yearOf = iso => iso ? parseInt(iso.slice(0, 4), 10) : null;

  // Heuristic share of rows that pass the row-level value filter.
  // Used only to scale the "Linhas" provenance counter; not data display.
  // The thresholds + shares come from the shared window.VALUE_PRESETS
  // (filtersSchema.js) so the FilterMenu shortcuts and this counter never
  // desync; a custom (non-preset) range falls back to a mid estimate.
  function valueShareForRange(min, max) {
    if (min == null && max == null) return 1.00;
    if (min === 0 && max == null) return 1.00;
    const preset = (window.VALUE_PRESETS || []).find(p => p.min === min && p.max === max);
    if (preset) return preset.rowShare;
    return 0.66; // arbitrary custom range
  }
  window.applyFilters = function (summary, bancoId) {
    summary = summary || {};

    // ── Resolve the in-memory snapshot for the active banco ────────────
    // Banco-aware seam: when a bancoId is given and its snapshot is loaded,
    // read from it; otherwise fall back to the PEVS globals so EVERY existing
    // call site — applyFilters(summary) with no bancoId — behaves EXACTLY as
    // before (zero regression). This is the single function the backend
    // generalizes: in Dash/Python it becomes apply_filters(banco_id, summary)
    // reading dataset_for(banco_id). Missing dimensions degrade to empty.
    const fromStore = bancoId && window.dataStore && window.dataStore.get ? window.dataStore.get(bancoId) : null;
    // If the banco isn't loaded into the store yet, fall back to its OWN
    // synthetic snapshot (banco-aware) — never silently to PEVS. Only when no
    // bancoId / no snapshot exists do we use the PEVS globals (the live mock).
    const fromSynth = !fromStore && bancoId && window.snapshotFor ? window.snapshotFor(bancoId) : null;
    const snap = fromStore || fromSynth || {
      products: window.PRODUCTS,
      productTS: window.PRODUCT_TS,
      overviewTS: window.OVERVIEW_TS,
      ufData: window.UF_DATA,
      quality: window.QUALITY_FLAGS,
      qualityTs: window.QUALITY_TS,
      topMunis: window.TOP_MUNICIPIOS,
      regions: window.REGIONS,
      qualityByProduct: window.QUALITY_BY_PRODUCT,
      qualityByUf: window.QUALITY_BY_UF
    };
    const PRODUCTS_T = snap.products || [];
    const PRODUCT_TS_T = snap.productTS || {};
    const OVERVIEW_T = snap.overviewTS || [];
    const UF_DATA_T = snap.ufData || [];
    const QUALITY_T = snap.quality || [];
    const QUALITY_TS_T = snap.qualityTs || [];
    const TOP_MUNIS_T = snap.topMunis || [];
    const REGIONS_T = snap.regions || window.REGIONS || [];
    const allProducts = PRODUCTS_T.map(p => p.code);
    // Distinguish "no product filter applied" (basket == null → all) from
    // "explicitly cleared" (basket == [] → none). Zero always means none.
    const basket = summary.basket == null ? allProducts : summary.basket;
    const selectedProducts = basket.filter(c => allProducts.includes(c));
    const yearStart = yearOf(summary.startDate) || OVERVIEW_T[0] && OVERVIEW_T[0].y || 1986;
    const yearEnd = yearOf(summary.endDate) || OVERVIEW_T[OVERVIEW_T.length - 1] && OVERVIEW_T[OVERVIEW_T.length - 1].y || 2024;

    // Same null-vs-empty rule as the basket: undefined/null = "no filter"
    // (all); an explicit empty array = "none selected" (zero rows). An empty
    // Set is truthy, so the `!set ||` / `set ?` guards downstream correctly
    // resolve null→all and empty-Set→none.
    const flagSet = summary.flags == null ? null : new Set(summary.flags);
    const stateSet = summary.states == null ? null : new Set(summary.states);

    // ── Aggregated time series (rebuilt from productTS) ───────────────
    const allYears = OVERVIEW_T.map(d => d.y).filter(y => y >= yearStart && y <= yearEnd);
    const ts = allYears.map(y => {
      let v = 0,
        qMass = 0,
        qVol = 0;
      selectedProducts.forEach(code => {
        const series = PRODUCT_TS_T[code];
        if (!series) return;
        const pt = series.find(p => p.y === y);
        if (!pt) return;
        v += pt.v / 1000; // productTS.v is mi → ts.v is bi
        if (pt.family === 'mass') qMass += pt.q;
        if (pt.family === 'volume') qVol += pt.q;
      });
      return {
        y,
        v,
        q: qMass,
        q_mass: qMass,
        q_vol: qVol
      };
    });

    // ── Per-product time series, restricted to basket + window ───────
    const productTS = {};
    selectedProducts.forEach(code => {
      const series = PRODUCT_TS_T[code];
      if (!series) return;
      productTS[code] = series.filter(d => d.y >= yearStart && d.y <= yearEnd);
    });

    // ── UF / region / municipio data — restrict by state filter & basket ──
    // Selected-product share scales the absolute totals so a basket of
    // 2 products doesn't keep the full 12-product UF total.
    const productShare = allProducts.length ? selectedProducts.length / allProducts.length : 0;
    const ufData = UF_DATA_T.filter(u => !stateSet || stateSet.has(u.uf)).map(u => ({
      ...u,
      value: u.value * productShare,
      q_mass: u.q_mass * productShare,
      q_vol: (u.q_vol || 0) * productShare
    }));

    // region totals derived from ufData (so they reflect basket + state filter)
    const regionData = REGIONS_T.map(r => {
      const ufs = ufData.filter(u => u.region === r.id);
      return {
        ...r,
        value: ufs.reduce((s, u) => s + u.value, 0),
        q_mass: ufs.reduce((s, u) => s + u.q_mass, 0),
        q_vol: ufs.reduce((s, u) => s + u.q_vol, 0),
        ufs: ufs.length
      };
    }).filter(r => r.ufs > 0);

    // top municipios — keep ones whose product is in basket AND uf is in stateSet
    // AND that survive the município selection. The município picker is an
    // explicit PARTIAL list of leaders, so matching is by city name (the data
    // has no município code): a city the picker can address passes only when
    // selected; a city outside the picker's universe is governed by the UF
    // filter alone. munis == null (or muniNames absent) ⇒ no município filter.
    const productNamesInBasket = new Set(selectedProducts.map(c => (PRODUCTS_T.find(p => p.code === c) || {}).name).filter(Boolean));
    const muniNameSet = summary.muniNames == null ? null : new Set(summary.muniNames);
    const muniUniverse = window.MUNI_PICKER_NAMES || new Set();
    const topMunis = TOP_MUNIS_T.filter(m => productNamesInBasket.has(m.product)).filter(m => !stateSet || stateSet.has(m.uf)).filter(m => {
      if (!muniNameSet) return true; // no município filter → all
      if (!muniUniverse.has(m.city)) return true; // unlisted leader → UF-governed
      return muniNameSet.has(m.city); // listed → must be selected
    }).map(m => ({
      ...m
    })); // values already at municipality level

    // ── Top products composition (donut / share) ─────────────────────
    // Take last endpoint from per-product TS, keep only basket products.
    const compositionRaw = selectedProducts.map(code => {
      const prod = PRODUCTS_T.find(p => p.code === code);
      const series = PRODUCT_TS_T[code];
      if (!prod || !series) return null;
      const lastInWindow = series.filter(d => d.y >= yearStart && d.y <= yearEnd).slice(-1)[0];
      if (!lastInWindow) return null;
      return {
        name: prod.name,
        value: lastInWindow.v
      };
    }).filter(Boolean).sort((a, b) => b.value - a.value);
    const compTotal = compositionRaw.reduce((s, p) => s + p.value, 0) || 1;
    const COLORS = [...window.VIZ_SCALE, 'var(--pres-gray-300)', 'var(--pres-gray-400)'];
    let topProducts;
    if (compositionRaw.length <= 7) {
      topProducts = compositionRaw.map((p, i) => ({
        ...p,
        share: p.value / compTotal,
        color: COLORS[i % COLORS.length]
      }));
    } else {
      const head = compositionRaw.slice(0, 6);
      const tail = compositionRaw.slice(6);
      const tailVal = tail.reduce((s, p) => s + p.value, 0);
      topProducts = [...head.map((p, i) => ({
        ...p,
        share: p.value / compTotal,
        color: COLORS[i]
      })), {
        name: 'Outros',
        value: tailVal,
        share: tailVal / compTotal,
        color: 'var(--pres-gray-200)',
        muted: true
      }];
    }

    // ── Quality flag distribution ─────────────────────────────────────
    const qualityFlagsAll = QUALITY_T;
    const filteredFlags = flagSet ? qualityFlagsAll.filter(f => flagSet.has(f.id)) : qualityFlagsAll;
    // re-normalize shares to selected flags' world
    const flagTotal = filteredFlags.reduce((s, f) => s + f.count, 0) || 1;
    const qualityFlags = filteredFlags.map(f => ({
      ...f,
      share: f.count / flagTotal
    }));

    // quality time series — pass-through, optionally trim to window
    const qualityTs = QUALITY_TS_T.filter(d => d.y >= yearStart && d.y <= yearEnd);

    // ── Row counter (for hero "SELEÇÃO ATIVA · Linhas") ────────────────
    const valueShare = valueShareForRange(summary.valueMin, summary.valueMax);
    const flagShare = flagSet ? filteredFlags.reduce((s, f) => s + f.share, 0) : 1;
    const yearShare = (yearEnd - yearStart + 1) / (OVERVIEW_T && OVERVIEW_T.length || 39);
    const stateShare = stateSet ? stateSet.size / (UF_DATA_T && UF_DATA_T.length || 27) : 1;
    return {
      ts,
      productTS,
      ufData,
      regionData,
      topMunis,
      topProducts,
      qualityFlags,
      qualityTs,
      selectedProducts,
      yearStart,
      yearEnd,
      // Banco-aware metadata so product/quality views read the ACTIVE banco's
      // dimensions instead of reaching into the PEVS globals (window.PRODUCTS …):
      products: PRODUCTS_T,
      // active banco product list
      productsTotal: allProducts.length,
      allProductTS: PRODUCT_TS_T,
      // full (unfiltered) per-product series
      ufDataFull: UF_DATA_T,
      // full (unfiltered) UF list ([] if no geo)
      qualityByProduct: snap.qualityByProduct || [],
      qualityByUf: snap.qualityByUf || [],
      _shares: {
        productShare,
        valueShare,
        flagShare,
        yearShare,
        stateShare
      }
    };
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "dataFilters.js", error: String((e && e.message) || e) }); }

// dataStore.js
try { (() => {
// dataStore.js — the pushdown query boundary that mirrors the Cloud Run
// deployment model:
//   • The Cloud Run service is STATELESS — no Gold is held in memory.
//   • Each UI interaction becomes a parameterized SQL query pushed down to
//     BigQuery, which returns a small pre-aggregated result (Serving Layer).
//   • flask-caching memoizes those results by params + Gold version; a poll
//     checks whether Gold changed upstream, invalidating the cache ("stale").
//
// All datasets are mock today. IBGE PEVS draws from the window.* globals
// (data.js); MDIC COMEX and UN Comtrade are LIVE on REPRESENTATIVE results
// (window.snapshotFor, previewData.js) generated from the explicit contract
// shape (02_SNAPSHOT_CONTRACTS.md); SEFAZ stays not-connected. When the real
// backend exists, replace
// `datasetFor()` with the pushdown query and `fetchGoldVersion()` with the
// real version poll. The view layer (window.applyFilters / preview adapters)
// does not change.

(function () {
  const store = {}; // bancoId -> { status, version, loadedAt, data }
  const subs = new Set();
  const notify = () => subs.forEach(fn => {
    try {
      fn();
    } catch (e) {}
  });

  // Simulated upstream Gold version per banco. Bumping `v` invalidates the
  // cached result (as if a new Medallion run published new data).
  // The PEVS publish timestamp is sourced from the banco registry
  // (bancos.js · prov.refresh) so it isn't duplicated as a literal here.
  const goldVersion = {
    ibge_pevs: {
      v: 'pevs-2024.1',
      at: window.bancoById && window.bancoById('ibge_pevs')?.prov?.refresh || '28 mai 2026 · 04:30 BRT'
    },
    mdic_comex: {
      v: 'comex-2024.12',
      at: window.bancoById && window.bancoById('mdic_comex')?.prov?.refresh || '29 mai 2026 · 05:10 BRT'
    },
    un_comtrade: {
      v: 'comtrade-2024.1',
      at: window.bancoById && window.bancoById('un_comtrade')?.prov?.refresh || '29 mai 2026 · 05:10 BRT'
    },
    ibge_pam: {
      v: 'pam-2024.1',
      at: window.bancoById && window.bancoById('ibge_pam')?.prov?.refresh || '30 mai 2026 · 04:45 BRT'
    },
    sefaz_nf: {
      v: 'nfe-preview',
      at: '—'
    }
  };

  // Gold table identifiers AS REPORTED BY THE BACKEND (the catalog the service
  // discovers at startup / version poll). This is the source of truth for the
  // table NAME shown in the UI — not a frontend literal — so a rename upstream
  // propagates everywhere via window.bancoTable(). In production, populate this
  // from the backend response; the registry `banco.table` is only a fallback.
  const goldTable = {
    ibge_pevs: 'gold_pevs_production',
    mdic_comex: 'gold_comex_flows',
    un_comtrade: 'gold_comtrade_flows',
    ibge_pam: 'gold_pam_production',
    sefaz_nf: 'gold_nfe_flows'
  };
  const tableOf = id => goldTable[id] || null;

  // The Serving-Layer result a banco exposes (the small pre-aggregated DataFrame
  // a pushdown query would return). IBGE PEVS references the existing
  // global tables (same object = same data). MDIC COMEX & UN Comtrade return a
  // SYNTHETIC, REPRESENTATIVE PEVS-shaped result (window.snapshotFor,
  // previewData.js) built from the explicit contract shape — they are LIVE, so their
  // perspectives render this data. SEFAZ (not connected) returns a result too,
  // but stays gated as a placeholder by its maturity in MainScreen.
  // When a banco gets real Gold, replace its branch with the pushdown query
  // (keep the returned shape — it IS the contract).
  function datasetFor(bancoId) {
    if (bancoId === 'ibge_pevs') {
      return {
        products: window.PRODUCTS,
        productTS: window.PRODUCT_TS,
        overviewTS: window.OVERVIEW_TS,
        ufData: window.UF_DATA,
        quality: window.QUALITY_FLAGS,
        // path-A extras so applyFilters can read EVERYTHING from the snapshot
        // (not from hardcoded globals) — keeps the seam banco-agnostic.
        qualityTs: window.QUALITY_TS,
        topMunis: window.TOP_MUNICIPIOS,
        regions: window.REGIONS,
        qualityByProduct: window.QUALITY_BY_PRODUCT,
        qualityByUf: window.QUALITY_BY_UF,
        table: tableOf('ibge_pevs')
      };
    }
    // Other bancos: representative snapshot from previewData.js (null if none).
    // Attach the backend-reported table name so it flows with the snapshot.
    const snap = window.snapshotFor && window.snapshotFor(bancoId) || null;
    if (snap) snap.table = tableOf(bancoId);
    return snap;
  }

  // Simulated bootstrap latency so the loading state is observable.
  const LOAD_MS = 650;
  window.dataStore = {
    status: id => store[id] && store[id].status || 'idle',
    version: id => store[id] && store[id].version || null,
    loadedAt: id => store[id] && store[id].loadedAt || null,
    get: id => store[id] && store[id].data || null,
    latestVersion: id => goldVersion[id] && goldVersion[id].v || null,
    latestAt: id => goldVersion[id] && goldVersion[id].at || null,
    // Backend-reported Gold table name (source of truth for display).
    table: id => tableOf(id),
    // Per-banco PROVENANCE METADATA as the backend would report it (single
    // payload): table, source, scope/granularity, coverage, refresh, counts,
    // implementation status + expected-completion. In production this is the
    // backend's response; here the authoritative live facts (table, refresh)
    // come from the catalogs above and the remaining descriptive fields fall
    // through to the registry as the stand-in. The UI reads this via
    // window.bancoMeta(id) so a change upstream propagates everywhere; swap
    // this body for the real backend call and nothing in the UI changes.
    meta: id => {
      const b = window.bancoById && window.bancoById(id) || {};
      return {
        table: tableOf(id),
        refresh: goldVersion[id] && goldVersion[id].at || b.prov && b.prov.refresh || null,
        version: goldVersion[id] && goldVersion[id].v || null,
        source: b.source,
        scope: b.scope,
        domain: b.domain,
        cobertura: b.cobertura || null,
        maturity: b.maturity,
        // A conclusion/expected date only applies to NON-estavel bancos; an
        // estavel (production) banco never shows one (ignore any legacy plannedRelease).
        maturityDate: b.maturity === 'estavel' ? null : b.maturityDate || b.plannedRelease || null,
        prov: b.prov || null
      };
    },
    // Is the cached result behind the upstream Gold version?
    isStale: id => !!(store[id] && store[id].status === 'ready' && goldVersion[id] && store[id].version !== goldVersion[id].v),
    subscribe(fn) {
      subs.add(fn);
      return () => subs.delete(fn);
    },
    // Run (or re-run) a banco's pushdown query and cache the result.
    load(id) {
      const fresh = store[id] && store[id].status === 'ready' && !this.isStale(id);
      if (fresh) return Promise.resolve(store[id]);
      store[id] = {
        status: 'loading',
        version: null,
        loadedAt: null,
        data: null,
        error: null
      };
      notify();
      return new Promise(resolve => {
        setTimeout(() => {
          try {
            // Simulated transient failure hook (see failNext below). In prod
            // this is where a query/timeout/auth error would be caught.
            if (this._failNext[id]) {
              this._failNext[id] = false;
              throw new Error('Falha ao consultar a tabela Gold no BigQuery (timeout).');
            }
            store[id] = {
              status: 'ready',
              version: goldVersion[id] && goldVersion[id].v || id + '-preview',
              loadedAt: goldVersion[id] && goldVersion[id].at || 'agora',
              data: datasetFor(id),
              error: null
            };
          } catch (err) {
            store[id] = {
              status: 'error',
              version: null,
              loadedAt: null,
              data: null,
              error: err && err.message || 'Erro desconhecido ao carregar dados.'
            };
          }
          notify();
          resolve(store[id]);
        }, LOAD_MS);
      });
    },
    error: id => store[id] && store[id].error || null,
    // DEMO: arm a one-shot load failure for a banco (to exercise the error UI).
    _failNext: {},
    simulateError(id) {
      this._failNext[id] = true;
      notify();
    },
    // DEMO: simulate Gold being updated upstream (flips loaded snapshot to stale).
    bumpGold(id) {
      const cur = goldVersion[id] || {
        v: id + '-1'
      };
      const m = cur.v.match(/(\d+)$/);
      const next = m ? cur.v.replace(/\d+$/, String(parseInt(m[1], 10) + 1)) : cur.v + '.2';
      const now = new Date();
      goldVersion[id] = {
        v: next,
        at: now.toLocaleDateString('pt-BR', {
          day: '2-digit',
          month: 'short'
        }) + ' · ' + now.toLocaleTimeString('pt-BR', {
          hour: '2-digit',
          minute: '2-digit'
        }) + ' BRT'
      };
      notify();
    }
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "dataStore.js", error: String((e && e.message) || e) }); }

// demoFixture.js
try { (() => {
// demoFixture.js — SINGLE SOURCE OF TRUTH for the prototype's DEMO DATA identity.
//
// The dashboard ships with synthetic, representative data so every perspective
// renders before the real Gold tables exist. Those numbers have to be ABOUT
// something — here that "something" is the Brazil-nut / extractive chain
// (castanha · madeira · açaí, Northern belt). Everything commodity-specific in
// the mock lives HERE, and nowhere else.
//
// ─────────────────────────────────────────────────────────────────────
// TO DEMO A DIFFERENT CHAIN (e.g. soja, café): edit THIS FILE ONLY.
//   • snapshot.products / partners / origins / seasonal  → previewData.js
//   • crossMagnitudes                                    → crossSource.js
//   • enrichment.groups / goldCodes / seedClassifications → enrichment.js
//   • pam.crops / ufProductivity (lavouras · IBGE PAM)   → previewData.js (productivityData)
// No view, chart, adapter or router changes — they read the SHAPE, not the
// values. These are DEMONSTRATION PARAMETERS, never part of the data contract
// (the contract is the shape in 02_SNAPSHOT_CONTRACTS.md).
// ─────────────────────────────────────────────────────────────────────

(function () {
  window.DEMO_PARAMS = {
    // Human label for the chain this fixture represents (shown nowhere critical;
    // handy when swapping so you remember what's loaded).
    chainLabel: 'Castanha & cadeias extrativas do Norte (castanha · madeira · açaí)',
    // ── previewData.js — per-banco representative snapshot universes ──────
    snapshot: {
      // [code, name, priceUsdPerKg, volEndKt] → v(US$ mi)=price×volKt, q(mil t)=volKt.
      // Plausible demo price levels (in-shell ~US$2.5/kg, shelled brazil nut ~US$15/kg).
      products: {
        mdic_comex: [['08012200', 'Castanha-do-pará sem casca', 15.0, 3.6], ['08012100', 'Castanha-do-pará com casca', 2.5, 26], ['08013200', 'Castanha de caju sem casca', 7.0, 34], ['08013100', 'Castanha de caju com casca', 1.4, 41], ['08029900', 'Outras castanhas e nozes', 5.0, 9]],
        un_comtrade: [['080122', 'Brazil nuts, shelled', 14.0, 4.2], ['080121', 'Brazil nuts, in shell', 2.4, 23], ['080132', 'Cashew nuts, shelled', 7.5, 37], ['080131', 'Cashew nuts, in shell', 1.5, 44], ['080119', 'Coconuts, other', 0.6, 28]],
        sefaz_nf: [['08012200', 'Castanha-do-pará sem casca', 70, 6], ['09011110', 'Café não torrado', 22, 130], ['18010000', 'Cacau em amêndoas', 16, 38], ['44011100', 'Lenha', 0.3, 820]],
        // IBGE PAM — lavouras. BRL banco (canonFactor=1), so price is R$/kg.
        // volEndKt = end-year production in thousand tonnes. Product codes are
        // ≥5 chars on purpose (ViewProductProfile seeds its UF ranking on
        // code.charCodeAt(4)). Mass family / tonnes, like the generic views expect.
        ibge_pam: [['54011', 'Soja (grão)', 2.0, 152000], ['54012', 'Milho (grão)', 1.2, 130000], ['54015', 'Cana-de-açúcar', 0.15, 750000], ['54013', 'Café (grão)', 25.0, 3700], ['54014', 'Algodão (pluma)', 8.0, 7000]]
      },
      // Native year coverage per banco.
      coverage: {
        mdic_comex: [1997, 2024],
        un_comtrade: [1988, 2024],
        sefaz_nf: [2010, 2024],
        ibge_pam: [1990, 2024]
      },
      // Fraction of end-year volume reached at the START of coverage (S-curve floor).
      startFrac: {
        mdic_comex: 0.30,
        un_comtrade: 0.26,
        sefaz_nf: 0.42,
        ibge_pam: 0.38
      },
      // Partner ("destino"/"parceiro") universes — typical castanha markets.
      partners: {
        mdic_comex: ['Peru', 'Bolívia', 'Estados Unidos', 'Alemanha', 'Israel', 'Reino Unido', 'Países Baixos', 'Itália', 'Emirados Árabes Unidos', 'Vietnã'],
        un_comtrade: ['China', 'Estados Unidos', 'Alemanha', 'Países Baixos', 'Vietnã', 'Índia', 'Bolívia', 'Peru', 'Itália', 'Reino Unido'],
        sefaz_nf: ['SP', 'RJ', 'MG', 'PR', 'RS', 'PA', 'AM', 'CE', 'BA', 'SC']
      },
      // Origin universes — Brazil-nut belt (North) for MDIC/SEFAZ; reporters for Comtrade.
      origins: {
        mdic_comex: ['AC', 'AM', 'PA', 'RO', 'AP'],
        un_comtrade: ['Brasil', 'Bolívia', 'Peru', 'Costa do Marfim', 'Vietnã'],
        sefaz_nf: ['AC', 'AM', 'PA', 'RO', 'MT'],
        // PAM — grain/fibre belt (Centre-West + South + MG).
        ibge_pam: ['MT', 'PR', 'RS', 'GO', 'MS']
      },
      // Monthly export seasonality (12 weights): castanha harvest Dec–Mar,
      // shipments peak Mar–Jun, trough Sep–Nov.
      seasonal: {
        mdic_comex: [0.85, 0.95, 1.35, 1.40, 1.30, 1.15, 0.95, 0.80, 0.70, 0.75, 0.80, 1.00],
        sefaz_nf: [1.05, 1.00, 1.10, 1.05, 1.00, 0.95, 0.92, 0.95, 1.00, 1.05, 1.00, 0.93]
      }
    },
    // ── crossSource.js — synthetic annual series magnitude ranges [v0, vT] ──
    // Keyed by 'banco:metric'. Magnitudes consistent with the single-banco
    // snapshot above (e.g. MDIC exp ~US$0.1–0.46 bi; ~31–114 mil t).
    crossMagnitudes: {
      'mdic_comex:exp_value': [0.10, 0.46],
      'mdic_comex:imp_value': [0.02, 0.09],
      'mdic_comex:exp_weight': [31, 114],
      'un_comtrade:exp_value': [0.09, 0.42],
      'un_comtrade:imp_value': [0.03, 0.10],
      'un_comtrade:world_exp': [3.2, 9.5],
      'sefaz_nf:internal_value': [42, 181],
      'sefaz_nf:internal_weight': [8100, 26300],
      'sefaz_nf:icms_total': [6.2, 23.7],
      // IBGE PAM (lavouras) — display-unit magnitudes: R$ bi · mi t · mi ha · kg/ha.
      'ibge_pam:prod_value': [165, 715],
      'ibge_pam:prod_quantity': [430, 1060],
      'ibge_pam:area_harvested': [38, 80],
      'ibge_pam:yield': [1900, 3500]
    },
    // ── enrichment.js — curation worklist (LEFT side) + seed classifications ──
    enrichment: {
      groups: [{
        id: 'castanha',
        label: 'Castanha-do-pará'
      }, {
        id: 'madeira',
        label: 'Madeira'
      }, {
        id: 'acai',
        label: 'Açaí'
      }],
      // GOLD codes that EXIST in the data (stand-in for SELECT DISTINCT per banco).
      goldCodes: [
      // ── Castanha-do-pará ──
      {
        id: 'cst-ibge',
        group: 'castanha',
        source: 'ibge_pevs',
        code: '1.3',
        desc: 'Castanha-do-pará'
      }, {
        id: 'cst-mdic-cc',
        group: 'castanha',
        source: 'mdic_comex',
        code: '08012100',
        desc: 'Castanha-do-pará, fresca ou seca, com casca'
      }, {
        id: 'cst-mdic-sc',
        group: 'castanha',
        source: 'mdic_comex',
        code: '08012200',
        desc: 'Castanha-do-pará, fresca ou seca, sem casca'
      }, {
        id: 'cst-un-0801',
        group: 'castanha',
        source: 'un_comtrade',
        code: '0801',
        desc: 'Nuts, edible; coconuts, Brazil & cashew, fresh/dried'
      }, {
        id: 'cst-un-121',
        group: 'castanha',
        source: 'un_comtrade',
        code: '080121',
        desc: 'Brazil nuts, fresh or dried, in shell'
      }, {
        id: 'cst-un-122',
        group: 'castanha',
        source: 'un_comtrade',
        code: '080122',
        desc: 'Brazil nuts, fresh or dried, shelled'
      },
      // ── Madeira ──
      {
        id: 'mad-ibge',
        group: 'madeira',
        source: 'ibge_pevs',
        code: '2.1',
        desc: 'Madeira em tora'
      }, {
        id: 'mad-mdic-tor',
        group: 'madeira',
        source: 'mdic_comex',
        code: '44032100',
        desc: 'Madeira em bruto, conífera'
      }, {
        id: 'mad-mdic-ser',
        group: 'madeira',
        source: 'mdic_comex',
        code: '44071100',
        desc: 'Madeira serrada, conífera'
      }, {
        id: 'mad-un-4403',
        group: 'madeira',
        source: 'un_comtrade',
        code: '4403',
        desc: 'Wood in the rough'
      }, {
        id: 'mad-un-4407',
        group: 'madeira',
        source: 'un_comtrade',
        code: '4407',
        desc: 'Wood sawn or chipped lengthwise'
      },
      // ── Açaí ──
      {
        id: 'aca-ibge',
        group: 'acai',
        source: 'ibge_pevs',
        code: '1.1',
        desc: 'Açaí (fruto)'
      }, {
        id: 'aca-mdic-pol',
        group: 'acai',
        source: 'mdic_comex',
        code: '20079990',
        desc: 'Polpa de açaí (preparada)'
      }, {
        id: 'aca-un-2007',
        group: 'acai',
        source: 'un_comtrade',
        code: '2007',
        desc: 'Jams, fruit jellies, purées & pastes'
      },
      // ── Códigos que apareceram numa carga recente da Gold, ainda SEM linha no
      //    log de classificação (NULL no LEFT JOIN) → entram "a classificar" ──
      {
        id: 'cst-mdic-tor',
        group: 'castanha',
        source: 'mdic_comex',
        code: '20081910',
        desc: 'Castanha-do-pará torrada / em preparações'
      }, {
        id: 'mad-mdic-comp',
        group: 'madeira',
        source: 'mdic_comex',
        code: '44092100',
        desc: 'Madeira perfilada (sarrafos, molduras)'
      }, {
        id: 'aca-mdic-cong',
        group: 'acai',
        source: 'mdic_comex',
        code: '08119000',
        desc: 'Açaí congelado (fruto, sem adição de açúcar)'
      }],
      // Seed slice of the append-only classification log (WHERE is_current):
      // industrialization level per code id. Codes absent here → "a classificar".
      seedClassifications: {
        'cst-ibge': 'misturado',
        'cst-mdic-cc': 'bruta',
        'cst-mdic-sc': 'processada',
        'cst-un-0801': 'misturado',
        'cst-un-121': 'bruta',
        'cst-un-122': 'processada',
        'mad-ibge': 'bruta',
        'mad-mdic-tor': 'bruta',
        'mad-mdic-ser': 'processada',
        'mad-un-4403': 'bruta',
        'mad-un-4407': 'processada',
        'aca-ibge': 'bruta',
        'aca-mdic-pol': 'processada',
        'aca-un-2007': 'processada'
      }
    },
    // ── previewData.js · productivityData() — IBGE PAM yield perspective ──
    // The agricultural-productivity demo universe (lavouras). Consumed ONLY by
    // window.productivityData; the generic views read the snapshot block above.
    // To demo other crops, edit here — the view/adapter shape is unchanged.
    pam: {
      yieldUnit: 'kg/ha',
      areaUnit: 'ha',
      // Per crop: end-year national yield (kg/ha) + harvested area (thousand ha),
      // and the START-of-coverage fraction of each (S-curve floor → end value).
      // `code` matches snapshot.products.ibge_pam so the two stay in lockstep.
      crops: [{
        code: '54011',
        name: 'Soja',
        yieldEnd: 3550,
        areaEndKha: 46000,
        yldStart: 0.60,
        areaStart: 0.28
      }, {
        code: '54012',
        name: 'Milho',
        yieldEnd: 5850,
        areaEndKha: 22000,
        yldStart: 0.52,
        areaStart: 0.46
      }, {
        code: '54015',
        name: 'Cana-de-açúcar',
        yieldEnd: 76000,
        areaEndKha: 8600,
        yldStart: 0.80,
        areaStart: 0.62
      }, {
        code: '54013',
        name: 'Café',
        yieldEnd: 1750,
        areaEndKha: 1850,
        yldStart: 0.68,
        areaStart: 0.94
      }, {
        code: '54014',
        name: 'Algodão',
        yieldEnd: 1850,
        areaEndKha: 1700,
        yldStart: 0.46,
        areaStart: 0.50
      }],
      // UF productivity index relative to the national mean (1.0). High-tech
      // Cerrado/South >1; frontier North/Northeast <1. The adapter joins this
      // onto the canonical UF grid (window.UF_DATA) with seeded per-crop jitter;
      // UFs absent here default to ~0.88. Captures the real yield geography.
      ufProductivity: {
        MT: 1.16,
        GO: 1.09,
        MS: 1.10,
        PR: 1.12,
        SP: 1.06,
        MG: 1.05,
        SC: 1.03,
        RS: 0.84,
        BA: 0.96,
        MA: 0.86,
        PI: 0.83,
        TO: 0.92,
        DF: 1.08
      }
    }
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "demoFixture.js", error: String((e && e.message) || e) }); }

// enrichment.js
try { (() => {
// enrichment.js — the RESEARCHER ENRICHMENT layer: institutional, shared
// annotations laid ON TOP of the raw banco dimensions. Not new rows — extra
// knowledge keyed to existing codes/flows, which unlocks analyses the raw
// data can't express on its own (value-added: bruta vs processada; market
// nature: who imports to consume vs to process & resell at a premium).
//
// ── Model (institutional / shared — one curation for everyone) ─────────
//   codes: [{ id, group, source, code, desc, level }]
//          level ∈ 'bruta' | 'processada' | 'misturado'
//   pairs: pairMarkets[`${regimeId}:${flowId}`] = market
//          the classification unit is the PAIR regime × flow direction —
//          the full cross product of every customs regime with every flow.
//          purpose ∈ 'consumo' | 'processamento' | (unset)
//
// Persisted to localStorage in the prototype (the shared institutional log
// in production). Editing notifies subscribers so curation → analysis is live.
//
// HANDOFF: in production this becomes an append-only SCD2 classification log
// (`gold_enrichment_*`, INSERT-only — never UPDATE), joined to the static
// Serving View at read time via a live LEFT JOIN. Replace load/save with API
// calls; keep the shapes + the analysis adapters (valueAddedAnalysis /
// marketNatureAnalysis) identical.

(function () {
  const LS_KEY = 'embrapa_enrichment_v9'; // bumped: shape split into GOLD_CODES × classifications
  const COMMIT_MS = 1500; // simulated BigQuery write+JOIN latency
  const subs = new Set();
  let committing = false; // true while the SCD2 INSERT + live JOIN runs
  const notify = () => subs.forEach(fn => {
    try {
      fn();
    } catch (e) {}
  });

  // ── LEFT side of the worklist join ──────────────────────────────────
  // The universe of product codes that EXIST in the Gold data — a stand-in
  // for a scoped `SELECT DISTINCT code, description` per banco. Carries NO
  // classification: the industrialization level lives in the append-only
  // classification log (the RIGHT side), joined at read time. A Gold code with
  // no matching log row surfaces as "a classificar" — that is the dynamic
  // worklist: new codes in the data appear automatically, awaiting curation.
  // Commodity-specific worklist (the codes that exist in the data) lives in
  // demoFixture.js → window.DEMO_PARAMS.enrichment. Edit that file to demo a
  // different chain; the join logic below is commodity-agnostic.
  const _ENR = window.DEMO_PARAMS && window.DEMO_PARAMS.enrichment || {};
  const GOLD_CODES = _ENR.goldCodes || [];

  // ── RIGHT side: the institutional seed = the current slice of the
  //    append-only classification log (`WHERE is_current`), seeded here with
  //    representative demo classifications. New Gold codes above have no key
  //    here → unclassified.
  const SEED = {
    classifications: {
      ...(_ENR.seedClassifications || {})
    },
    // Initial deploy seed: binary PURPOSE (Consumption × Processing).
    // Direction (buy/sell) already comes from the flow; only the purpose here.
    // Export pairs whose destination purpose the regime does not determine
    // (e.g. outright exportation, customs warehouse) are left blank — candidates
    // for future inference from the product's industrialization level.
    pairMarkets: {
      // ─ Consumo (final use / consumption) ─
      'desp-consumo:imports': 'consumo',
      'desp-consumo:for-import': 'consumo',
      'desp-consumo:reimport': 'consumo',
      'viajantes:imports': 'consumo',
      'viajantes:for-import': 'consumo',
      'postal:imports': 'consumo',
      'postal:for-import': 'consumo',
      'postal:exports': 'consumo',
      // ─ Processamento (industrial transformation / processing) ─
      'zona-franca:imports': 'processamento',
      'zona-franca:for-import': 'processamento',
      'zona-franca:exports': 'processamento',
      'aperf-ativo:imp-inward': 'processamento',
      'aperf-ativo:imports': 'processamento',
      'aperf-ativo:exp-after-inward': 'processamento',
      'aperf-passivo:exp-for-outward': 'processamento',
      'aperf-passivo:imp-after-outward': 'processamento',
      'aperf-passivo:exports': 'processamento',
      'drawback:exports': 'processamento',
      'drawback:dom-export': 'processamento',
      'drawback:exp-after-inward': 'processamento',
      'transformacao:imports': 'processamento',
      'transformacao:imp-inward': 'processamento',
      'transformacao:for-import': 'processamento'
    }
  };
  const clone = o => JSON.parse(JSON.stringify(o));
  function load() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (raw) {
        const j = JSON.parse(raw);
        if (j && j.classifications && j.pairMarkets) return j;
      }
    } catch (e) {}
    return clone(SEED);
  }
  // Two-stage state: `applied` is the committed institutional truth that
  // FEEDS THE ANALYSES; `draft` holds the researcher's in-progress edits.
  // Edits touch draft; "Aplicar" commits draft → applied. In production that
  // commit does NOT re-materialize a Gold table — it appends a new revision to
  // the SCD2 classification log (INSERT, never UPDATE) and the analyses read it
  // via a live LEFT JOIN (see commit() below). Staging draft separately keeps
  // half-finished classifications out of the shared analyses.
  let applied = load();
  let draft = clone(applied);
  function persist() {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(applied));
    } catch (e) {}
  }

  // ── The worklist IS a LEFT JOIN ───────────────────────────────────────
  // GOLD_CODES (the data, left) ⟕ state.classifications (the log, right).
  // Each Gold code gets its stored level, or null when the log has no row for
  // it ("a classificar"). In production this is the real
  //   SELECT DISTINCT code, description FROM <gold>
  //   LEFT JOIN gold_enrichment_codes USING (code) WHERE is_current
  // resolved at read time — here it is simulated client-side.
  function worklist(state) {
    return GOLD_CODES.map(g => {
      const level = state.classifications && state.classifications[g.id] || null;
      return {
        id: g.id,
        group: g.group,
        source: g.source,
        code: g.code,
        desc: g.desc,
        level,
        status: level ? 'classificado' : 'a-classificar'
      };
    });
  }
  window.ENRICH_LEVELS = [{
    id: 'bruta',
    label: 'Bruta',
    color: 'var(--viz-3)'
  }, {
    id: 'processada',
    label: 'Processada',
    color: 'var(--viz-2)'
  }, {
    id: 'misturado',
    label: 'Misturado',
    color: 'var(--pres-gray-300)'
  }];
  window.ENRICH_MARKETS = [{
    id: 'consumo',
    label: 'Consumo',
    short: 'Consumo',
    color: 'var(--viz-1)'
  }, {
    id: 'processamento',
    label: 'Processamento',
    short: 'Processamento',
    color: 'var(--viz-9)'
  }];
  window.ENRICH_GROUPS = _ENR.groups || [];
  // Customs regimes (rows) × flow types (columns) — the full pair matrix.
  window.ENRICH_REGIMES = [{
    id: 'desp-consumo',
    label: 'Despacho para consumo',
    term: 'Clearance for home use',
    hint: 'Importação nacionalizada: a mercadoria estrangeira é liberada para circular e ser consumida livremente no país após o recolhimento de todos os tributos. É o destino típico de bens que entram para abastecer o mercado interno.'
  }, {
    id: 'reimport-same',
    label: 'Reimportação no mesmo estado',
    term: 'Reimportation in the same state',
    hint: 'Retorno ao país de um bem que havia sido exportado, sem ter sofrido transformação no exterior — por exemplo, mercadoria devolvida ou não vendida. Não representa nova produção nem agregação de valor.'
  }, {
    id: 'exp-definitiva',
    label: 'Exportação definitiva',
    term: 'Outright exportation',
    hint: 'Saída definitiva da mercadoria nacional para o exterior, sem previsão de retorno. É a exportação comum, que escoa a produção do país para mercados estrangeiros.'
  }, {
    id: 'entreposto',
    label: 'Entreposto aduaneiro',
    term: 'Customs warehouses',
    hint: 'Mercadoria armazenada sob controle aduaneiro com tributos suspensos, antes de definir seu destino (consumo interno, reexportação ou industrialização). Funciona como um ponto de espera logístico, não como destino final.'
  }, {
    id: 'zona-franca',
    label: 'Zona Franca',
    term: 'Free zone',
    hint: 'Área delimitada com incentivos fiscais e aduaneiros para atrair indústria e comércio (ex.: Zona Franca de Manaus). A mercadoria entra com tributação reduzida, em geral para transformação industrial.'
  }, {
    id: 'aperf-ativo',
    label: 'Aperfeiçoamento ativo',
    term: 'Inward processing',
    hint: 'Importação temporária de insumos com suspensão de tributos para serem industrializados ou beneficiados no país e depois reexportados. Sinaliza claramente uso industrial, e não consumo final.'
  }, {
    id: 'aperf-passivo',
    label: 'Aperfeiçoamento passivo',
    term: 'Outward processing',
    hint: 'Exportação temporária de um bem para ser beneficiado ou reparado no exterior, com posterior retorno ao país. Aqui o valor é agregado fora do território nacional.'
  }, {
    id: 'drawback',
    label: 'Drawback',
    term: 'Drawback',
    hint: 'Regime de incentivo à exportação que suspende ou restitui os tributos dos insumos importados empregados na fabricação de um produto que será exportado. Indica produção voltada ao mercado externo.'
  }, {
    id: 'transformacao',
    label: 'Transformação sob controle aduaneiro',
    term: 'Processing of goods for home use',
    hint: 'Transformação industrial da mercadoria sob controle aduaneiro, com o produto resultante destinado ao mercado interno. Combina industrialização e consumo doméstico no mesmo regime.'
  }, {
    id: 'cabotagem',
    label: 'Cabotagem',
    term: 'Carriage of goods coastwise',
    hint: 'Transporte de mercadorias por via aquaviária entre portos do próprio país (cabotagem). É movimentação interna, não comércio exterior, e não cruza fronteiras.'
  }, {
    id: 'infracoes',
    label: 'Infrações aduaneiras',
    term: 'Customs offences',
    hint: 'Operações vinculadas a infrações, apreensões ou penalidades aduaneiras. Não representam fluxo comercial regular e costumam ser residuais no total.'
  }, {
    id: 'viajantes',
    label: 'Viajantes',
    term: 'Travellers',
    hint: 'Bens transportados na bagagem de viajantes que entram ou saem do país. Em geral de uso pessoal, com volume e valor pequenos — pouco relevante para análise de commodities.'
  }, {
    id: 'postal',
    label: 'Tráfego postal',
    term: 'Postal traffic',
    hint: 'Mercadorias movimentadas pela via postal e remessas internacionais (correios). Concentra o comércio eletrônico transfronteiriço de pequeno porte.'
  }, {
    id: 'provisoes',
    label: 'Provisões de bordo',
    term: 'Stores',
    hint: 'Provisões de bordo — combustíveis, alimentos e suprimentos embarcados em navios e aeronaves para consumo durante a viagem. Não é mercadoria destinada a um mercado.'
  }, {
    id: 'socorro',
    label: 'Remessas de socorro',
    term: 'Relief consignments',
    hint: 'Remessas de ajuda humanitária e socorro (doações, situações de emergência), normalmente isentas de tributos e fora da lógica comercial de mercado.'
  }, {
    id: 'cpc-nes',
    label: 'CPC não especificado',
    term: 'CPC N.E.S.',
    hint: 'Procedimento aduaneiro não especificado nas demais categorias (Not Elsewhere Specified). Agrupa operações sem classificação própria — interprete com cautela.'
  }, {
    id: 'total-cpc',
    label: 'Total CPC',
    term: 'TOTAL CPC',
    hint: 'Linha de agregação que soma todos os procedimentos aduaneiros. Use com cuidado: evita-se somá-la às categorias específicas para não duplicar valores.'
  }];
  window.ENRICH_FLOWS = [{
    id: 'imports',
    label: 'Importações',
    term: 'Imports',
    hint: 'Entrada de mercadorias estrangeiras no território nacional, qualquer que seja o destino (consumo, estoque ou industrialização). É a contagem mais ampla de importação.'
  }, {
    id: 'exports',
    label: 'Exportações',
    term: 'Exports',
    hint: 'Saída de mercadorias do país para o exterior. Pode englobar tanto a produção nacional quanto reexportações, conforme o nível de detalhamento da fonte.'
  }, {
    id: 'dom-export',
    label: 'Exportação nacional',
    term: 'Domestic Export',
    hint: 'Exportação de mercadoria efetivamente produzida no país (origem nacional), distinguindo-a da simples reexportação de bens importados. É o que mede a competitividade da produção interna.'
  }, {
    id: 'for-import',
    label: 'Importação estrangeira',
    term: 'Foreign Import',
    hint: 'Importação de mercadoria de origem estrangeira que ingressa no país — a contrapartida, no Brasil, da exportação nacional feita pelo país parceiro.'
  }, {
    id: 'imp-inward',
    label: 'Import. p/ aperfeiç. ativo',
    term: 'Import for inward processing',
    hint: 'Importação de insumos destinados a serem industrializados ou beneficiados internamente e depois reexportados. Sinaliza demanda industrial, e não consumo do mercado interno.'
  }, {
    id: 'imp-after-outward',
    label: 'Import. após aperfeiç. passivo',
    term: 'Import after outward processing',
    hint: 'Reentrada da mercadoria que foi enviada ao exterior para beneficiamento e retorna já processada. O ganho de valor ocorreu fora do país.'
  }, {
    id: 'reimport',
    label: 'Reimportação',
    term: 'Re-import',
    hint: 'Reentrada no país de mercadoria que havia sido exportada, sem transformação no exterior (ex.: devoluções). Não caracteriza nova importação para consumo.'
  }, {
    id: 'reexport',
    label: 'Reexportação',
    term: 'Re-export',
    hint: 'Reexportação de mercadoria que havia sido importada, sem ter sido transformada no país. Indica papel de entreposto ou intermediação comercial, não de produção própria.'
  }, {
    id: 'exp-after-inward',
    label: 'Export. após aperfeiç. ativo',
    term: 'Export after inward processing',
    hint: 'Exportação do produto resultante de insumos importados e beneficiados internamente. É a exportação com valor agregado pela indústria nacional — o caso mais relevante de mercado industrial.'
  }, {
    id: 'exp-for-outward',
    label: 'Export. p/ aperfeiç. passivo',
    term: 'Export for outward processing',
    hint: 'Exportação temporária de um bem para ser beneficiado no exterior, com previsão de retorno. O beneficiamento (e a agregação de valor) acontece fora do país.'
  }];
  window.enrichment = {
    // Editor reads the DRAFT (in-progress) worklist; analyses read the APPLIED log.
    codes: () => worklist(draft),
    // the LEFT JOIN result (data ⟕ classification)
    worklist: () => worklist(draft),
    // explicit alias — same join
    regimes: () => window.ENRICH_REGIMES,
    flowTypes: () => window.ENRICH_FLOWS,
    pairMarket: (regimeId, flowId) => draft.pairMarkets[regimeId + ':' + flowId] || null,
    levelLabel: id => (window.ENRICH_LEVELS.find(l => l.id === id) || {}).label || id,
    levelColor: id => (window.ENRICH_LEVELS.find(l => l.id === id) || {}).color || 'var(--fg-3)',
    groupLabel: id => (window.ENRICH_GROUPS.find(g => g.id === id) || {}).label || id,
    // Chapter is DERIVED from the code itself (no stored field, no cross-banco
    // logic): NCM/HS by leading 2 digits, IBGE by its own product group. New
    // codes fall into their chapter automatically by prefix.
    chapterOf(source, code) {
      if (source === 'ibge_pevs') {
        const s = String(code).split('.')[0];
        return {
          '1': 'Produtos alimentícios',
          '2': 'Produtos madeireiros'
        }[s] || 'Grupo ' + s;
      }
      const ch = String(code).slice(0, 2);
      return {
        '08': '08 · Frutas e castanhas',
        '44': '44 · Madeira e carvão',
        '20': '20 · Preparações de frutas'
      }[ch] || ch + ' · Outros';
    },
    // Edit the classification log (the RIGHT side). Setting an empty level
    // removes the log row — the code falls back to "a classificar" in the join.
    setCode(id, patch) {
      if (!patch || !('level' in patch)) return;
      if (patch.level) draft.classifications[id] = patch.level;else delete draft.classifications[id];
      notify();
    },
    setPair(regimeId, flowId, market) {
      const k = regimeId + ':' + flowId;
      if (market) draft.pairMarkets[k] = market;else delete draft.pairMarkets[k];
      notify();
    },
    // ── Draft → Applied commit lifecycle ──────────────────────────────
    pendingCount() {
      let n = 0;
      GOLD_CODES.forEach(g => {
        if ((draft.classifications[g.id] || null) !== (applied.classifications[g.id] || null)) n++;
      });
      const keys = new Set([...Object.keys(draft.pairMarkets), ...Object.keys(applied.pairMarkets)]);
      keys.forEach(k => {
        if ((draft.pairMarkets[k] || null) !== (applied.pairMarkets[k] || null)) n++;
      });
      return n;
    },
    isDirty() {
      return this.pendingCount() > 0;
    },
    isCommitting: () => committing,
    // Commit draft → applied. ASYNC on purpose: simulates the BigQuery
    // round-trip (INSERT into the append-only SCD2 log, then the live LEFT
    // JOIN the analyses read). The button must lock while `committing` is
    // true — a double click would write duplicate revisions to the log.
    // In production: await the API write, then re-resolve the join.
    apply(onDone) {
      if (committing || this.pendingCount() === 0) return;
      committing = true;
      notify(); // UI: disable + show loading
      setTimeout(() => {
        applied = clone(draft);
        persist();
        committing = false;
        notify(); // UI: success + re-render grid/analyses
        if (typeof onDone === 'function') {
          try {
            onDone();
          } catch (e) {}
        }
      }, COMMIT_MS);
    },
    discard() {
      if (committing) return;
      draft = clone(applied);
      notify();
    },
    subscribe(fn) {
      subs.add(fn);
      return () => subs.delete(fn);
    },
    // counts for the curation hero (reflect the DRAFT worklist being edited)
    stats() {
      const wl = worklist(draft);
      const byLevel = {};
      window.ENRICH_LEVELS.forEach(l => {
        byLevel[l.id] = wl.filter(c => c.level === l.id).length;
      });
      return {
        codesTotal: wl.length,
        byLevel,
        unclassified: wl.filter(c => !c.level).length,
        // NULL side of the join
        flowsTotal: window.ENRICH_REGIMES.length * window.ENRICH_FLOWS.length,
        flowsClassified: Object.keys(draft.pairMarkets).length
      };
    }
  };

  // ── Deterministic synth so analyses are stable across reloads ──────────
  // PRNG lives in synthUtils.js (window.seeded) — no local copy.

  // ── Analysis 1: VALUE ADDED — exports split by industrialization level ─
  //   Aggregates synthetic per-code export series by their CURRENT curated
  //   `level`, so re-classifying a code in Curadoria changes the result.
  //   SHAPE: contracts.js @typedef ValueAddedAnalysis.
  window.valueAddedAnalysis = function (groupId) {
    const codes = worklist(applied).filter(c => c.source === 'mdic_comex' && (!groupId || c.group === groupId) && c.level && c.level !== 'misturado');
    const years = [];
    for (let y = 1997; y <= 2024; y++) years.push(y);
    const acc = {
      bruta: years.map(() => ({
        v: 0,
        w: 0
      })),
      processada: years.map(() => ({
        v: 0,
        w: 0
      }))
    };
    codes.forEach(c => {
      const rnd = window.seeded('va:' + c.id);
      const v0 = 0.4 + rnd() * 1.6,
        vT = v0 * (1.6 + rnd());
      const pricePerKg = c.level === 'processada' ? 2.6 + rnd() * 1.8 : 1.0 + rnd() * 0.6;
      years.forEach((y, i) => {
        const t = i / (years.length - 1);
        const val = (v0 + (vT - v0) * (t * t * (3 - 2 * t))) * (1 + (rnd() - 0.5) * 0.06); // US$ bi
        const w = val * 1e9 / pricePerKg / 1e6 / 1000; // → mil t (val_usd ÷ price ÷ kg→mil t)
        acc[c.level][i].v += val;
        acc[c.level][i].w += w;
      });
    });
    const series = years.map((y, i) => {
      const bV = acc.bruta[i].v,
        pV = acc.processada[i].v;
      const bW = acc.bruta[i].w || 1,
        pW = acc.processada[i].w || 1;
      const total = bV + pV || 1;
      const priceB = bV / bW,
        priceP = pV / pW;
      return {
        y,
        brutaV: bV,
        procV: pV,
        procShare: pV / total * 100,
        premium: priceB ? priceP / priceB : 0,
        priceB,
        priceP
      };
    });
    return {
      preview: (window.bancoById && window.bancoById('mdic_comex') || {}).status !== 'live',
      years,
      byLevel: {
        bruta: acc.bruta.map((d, i) => ({
          y: years[i],
          v: d.v
        })),
        processada: acc.processada.map((d, i) => ({
          y: years[i],
          v: d.v
        }))
      },
      series,
      nCodes: codes.length
    };
  };

  // ── Analysis 2: ECONOMIC PURPOSE — trade value by curated purpose ─
  //   SHAPE: contracts.js @typedef MarketNatureAnalysis (markets from ENRICH_MARKETS).
  window.marketNatureAnalysis = function () {
    const years = [];
    for (let y = 1997; y <= 2024; y++) years.push(y);
    const totals = {};
    window.ENRICH_MARKETS.forEach(m => {
      totals[m.id] = years.map(() => 0);
    });
    window.ENRICH_REGIMES.forEach(r => window.ENRICH_FLOWS.forEach(f => {
      const market = applied.pairMarkets[r.id + ':' + f.id];
      if (!market || !totals[market]) return;
      const rnd = window.seeded('mn:' + r.id + ':' + f.id);
      const v0 = 1 + rnd() * 5,
        vT = v0 * (1.4 + rnd());
      years.forEach((y, i) => {
        const t = i / (years.length - 1);
        totals[market][i] += (v0 + (vT - v0) * t) * (1 + (rnd() - 0.5) * 0.08);
      });
    }));
    const series = years.map((y, i) => {
      const o = {
        y
      };
      window.ENRICH_MARKETS.forEach(m => {
        o[m.id] = totals[m.id][i];
      });
      return o;
    });
    const last = series[series.length - 1];
    return {
      preview: ['mdic_comex', 'un_comtrade'].some(id => (window.bancoById && window.bancoById(id) || {}).status !== 'live'),
      years,
      series,
      latest: last
    };
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "enrichment.js", error: String((e && e.message) || e) }); }

// filtersSchema.js
try { (() => {
// filtersSchema.js — declarative per-banco filter dimensions.
//
// The FilterMenu is scoped to the banco selected in the sidebar and
// renders the dimensions declared here. Adding/curating a banco's
// filterable dimensions = editing this file (no FilterMenu rewrite).
//
// tier:
//   'universal' → exists in every banco (e.g. período)
//   'shared'    → exists in several, possibly at different granularity
//   'specific'  → unique to this banco
//
// type: hints how the dimension is rendered / what control it uses.
//   'products' | 'date-range' | 'value-range' | 'geo-cascade'
//   'flags' | 'multi' | 'multi-search' | 'multi-tree' | 'segment'
//
// num: section number shown in the live (PEVS) functional menu.

// ── Value-range quick presets (single source of truth) ───────────────────
// Used BOTH by the FilterMenu "valor mínimo" shortcut buttons AND by the
// row-counter heuristic in dataFilters.js (valueShareForRange). `rowShare` is
// the approximate fraction of rows that clear each threshold — it scales only
// the "Linhas" provenance counter, never the data shown. Keeping the two
// consumers on one list means a preset change can't silently desync the
// counter. `suffix` builds the label as `≥ <symbol> <suffix>` at render time
// (symbol depends on the active currency); `none` has no threshold.
window.VALUE_PRESETS = [{
  id: 'none',
  min: null,
  max: null,
  suffix: null,
  rowShare: 1.00
}, {
  id: '1k',
  min: 1_000,
  max: null,
  suffix: '1 mil',
  rowShare: 0.81
}, {
  id: '10k',
  min: 10_000,
  max: null,
  suffix: '10 mil',
  rowShare: 0.52
}, {
  id: '100k',
  min: 100_000,
  max: null,
  suffix: '100 mil',
  rowShare: 0.18
}, {
  id: '1M',
  min: 1_000_000,
  max: null,
  suffix: '1 mi',
  rowShare: 0.04
}];
window.FILTER_SCHEMAS = {
  ibge_pevs: {
    table: 'gold_pevs_production',
    dims: [{
      id: 'produtos',
      num: '01',
      tier: 'shared',
      type: 'products',
      label: 'Produtos · PEVS',
      column: 'codigo_pevs',
      hint: 'Commodities da extração vegetal e silvicultura.'
    }, {
      id: 'periodo',
      num: '02',
      tier: 'universal',
      type: 'period-value',
      label: 'Período & faixa de valor',
      column: 'ano · val_real_ipca',
      hint: 'Janela temporal e corte por valor monetário da linha.'
    }, {
      id: 'geografia',
      num: '03',
      tier: 'shared',
      type: 'geo-cascade',
      label: 'Geografia',
      column: 'uf · municipio',
      hint: 'Cascata nação ▸ região ▸ estado ▸ município.'
    }, {
      id: 'qualidade',
      num: '04',
      tier: 'specific',
      type: 'flags',
      label: 'Qualidade dos dados',
      column: 'data_quality_flag',
      hint: 'Bandeira de qualidade por linha.'
    }]
  },
  ibge_pam: {
    table: 'gold_pam_production',
    dims: [{
      id: 'produtos',
      num: '01',
      tier: 'shared',
      type: 'products',
      label: 'Lavouras · PAM',
      column: 'produto_pam',
      hint: 'Culturas temporárias e permanentes da Produção Agrícola Municipal.'
    }, {
      id: 'periodo',
      num: '02',
      tier: 'universal',
      type: 'period-value',
      label: 'Período & faixa de valor',
      column: 'ano · valor_producao',
      hint: 'Janela temporal (anual) e corte por valor da produção.'
    }, {
      id: 'geografia',
      num: '03',
      tier: 'shared',
      type: 'geo-cascade',
      label: 'Geografia',
      column: 'uf · municipio',
      hint: 'Cascata nação ▸ região ▸ estado ▸ município.'
    }, {
      id: 'qualidade',
      num: '04',
      tier: 'specific',
      type: 'flags',
      label: 'Qualidade dos dados',
      column: 'data_quality_flag',
      hint: 'Bandeira de qualidade por linha.'
    }]
  },
  mdic_comex: {
    table: 'gold_comex_flows',
    dims: [{
      id: 'periodo',
      tier: 'universal',
      type: 'date-range',
      label: 'Período',
      column: 'ano_mes',
      hint: 'Mensal, de 1997 ao presente.'
    }, {
      id: 'ncm',
      tier: 'shared',
      type: 'multi-tree',
      label: 'Produto · NCM / SH',
      column: 'ncm',
      hint: 'Hierarquia SH2 ▸ SH4 ▸ SH6 ▸ NCM 8 dígitos.'
    }, {
      id: 'uf_origem',
      tier: 'shared',
      type: 'multi',
      label: 'UF de origem',
      column: 'uf_origem',
      hint: 'Unidade da federação do exportador.'
    }, {
      id: 'pais',
      tier: 'specific',
      type: 'multi-search',
      label: 'País parceiro',
      column: 'pais_destino · pais_origem',
      hint: 'Destino (exportação) ou origem (importação).'
    }, {
      id: 'fluxo',
      tier: 'specific',
      type: 'segment',
      label: 'Fluxo',
      column: 'fluxo',
      options: ['Exportação', 'Importação'],
      hint: 'Direção da operação.'
    }, {
      id: 'via',
      tier: 'specific',
      type: 'multi',
      label: 'Via de transporte',
      column: 'via',
      options: ['Marítima', 'Aérea', 'Rodoviária', 'Ferroviária', 'Fluvial', 'Dutos'],
      hint: 'Modalidade logística da operação.'
    }, {
      id: 'valor',
      tier: 'universal',
      type: 'value-range',
      label: 'Faixa de valor (FOB)',
      column: 'val_fob_usd',
      hint: 'Corte por valor FOB em dólares.'
    }]
  },
  un_comtrade: {
    table: 'gold_comtrade_flows',
    dims: [{
      id: 'periodo',
      tier: 'universal',
      type: 'date-range',
      label: 'Período',
      column: 'ano',
      hint: 'Anual, de 1988 ao presente.'
    }, {
      id: 'reporter',
      tier: 'specific',
      type: 'multi-search',
      label: 'País reporter',
      column: 'reporter',
      hint: 'País que declarou a operação à UNSD.'
    }, {
      id: 'partner',
      tier: 'specific',
      type: 'multi-search',
      label: 'País parceiro',
      column: 'partner',
      hint: 'Contraparte do fluxo declarado.'
    }, {
      id: 'hs6',
      tier: 'shared',
      type: 'multi-tree',
      label: 'Produto · HS6',
      column: 'hs6',
      hint: 'Sistema Harmonizado a 6 dígitos.'
    }, {
      id: 'flow',
      tier: 'specific',
      type: 'segment',
      label: 'Fluxo',
      column: 'flow',
      options: ['Export', 'Import', 'Re-export', 'Re-import'],
      hint: 'Direção do fluxo internacional.'
    }, {
      id: 'valor',
      tier: 'universal',
      type: 'value-range',
      label: 'Faixa de valor (US$)',
      column: 'val_usd',
      hint: 'Corte por valor declarado.'
    }]
  },
  sefaz_nf: {
    table: 'gold_nfe_flows',
    dims: [{
      id: 'periodo',
      tier: 'universal',
      type: 'date-range',
      label: 'Período',
      column: 'ano_mes',
      hint: 'Diária (defasagem 24h), de 2010 ao presente.'
    }, {
      id: 'ncm',
      tier: 'shared',
      type: 'multi-tree',
      label: 'Produto · NCM',
      column: 'ncm',
      hint: 'Classificação fiscal da mercadoria.'
    }, {
      id: 'cfop',
      tier: 'specific',
      type: 'multi',
      label: 'Natureza · CFOP',
      column: 'cfop',
      hint: 'Código fiscal de operações e prestações.'
    }, {
      id: 'geo_origem',
      tier: 'shared',
      type: 'geo-cascade',
      label: 'Origem',
      column: 'uf_origem · municipio_origem',
      hint: 'Localização do remetente da NFe.'
    }, {
      id: 'geo_destino',
      tier: 'shared',
      type: 'geo-cascade',
      label: 'Destino',
      column: 'uf_destino · municipio_destino',
      hint: 'Localização do destinatário da NFe.'
    }, {
      id: 'cnae',
      tier: 'specific',
      type: 'multi-search',
      label: 'Setor · CNAE',
      column: 'cnae_remetente · cnae_destino',
      hint: 'Atividade econômica das partes.'
    }, {
      id: 'valor',
      tier: 'universal',
      type: 'value-range',
      label: 'Faixa de valor (R$)',
      column: 'val_operacao',
      hint: 'Corte pelo valor total da operação.'
    }]
  }
};
window.filterSchemaFor = bancoId => window.FILTER_SCHEMAS[bancoId] || window.FILTER_SCHEMAS.ibge_pevs;
window.TIER_LABEL = {
  universal: 'Universal',
  shared: 'Compartilhada',
  specific: 'Específica do banco'
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "filtersSchema.js", error: String((e && e.message) || e) }); }

// glossary.js
try { (() => {
// Glossário data — per-banco terms used across the dashboard.
// Each banco gets a list of terms. Terms have:
//   term  — short name (case as authored)
//   short — one-line definition (institutional voice)
//   tag   — small chip label (column/source/etc.); optional
//   cat   — category for grouping inside the banco; optional
//
// IDs match window.BANCOS in bancos.js.

const GLOSSARY = {
  ibge_pevs: {
    label: 'IBGE PEVS',
    sub: 'Produção da Extração Vegetal e da Silvicultura',
    terms: [{
      term: 'PEVS',
      cat: 'Fonte',
      tag: 'IBGE',
      short: 'Pesquisa da Extração Vegetal e da Silvicultura — apuração anual do IBGE com quantidade produzida e valor da produção de produtos não-madeireiros e madeireiros nativos.'
    }, {
      term: 'SIDRA',
      cat: 'Fonte',
      tag: 'IBGE',
      short: 'Sistema IBGE de Recuperação Automática — portal de tabelas oficiais. Base do ingest Bronze do pipeline.'
    }, {
      term: 'Castanha-do-pará',
      cat: 'Produto',
      tag: '49101',
      short: 'Semente de Bertholletia excelsa, principal produto extrativista da Amazônia. Unidade: toneladas.'
    }, {
      term: 'Açaí (fruto)',
      cat: 'Produto',
      tag: '49103',
      short: 'Fruto da palmeira Euterpe oleracea. Inclui açaí de várzea e plantios manejados como extrativos.'
    }, {
      term: 'Erva-mate',
      cat: 'Produto',
      tag: '49108',
      short: 'Folhas e ramos de Ilex paraguariensis para fabricação de chá e chimarrão. Concentrada no Sul.'
    }, {
      term: 'Madeira em tora',
      cat: 'Produto',
      tag: '49215',
      short: 'Toras de espécies nativas. Unidade: m³. Sujeita a controle de licenciamento ambiental.'
    }, {
      term: 'Lenha',
      cat: 'Produto',
      tag: '49216',
      short: 'Madeira para combustão direta. Unidade: m³. Principal item em volume da PEVS.'
    }, {
      term: 'gold_pevs_production',
      cat: 'Coluna',
      tag: 'BigQuery',
      short: 'Tabela Gold desnormalizada. Uma linha por (ano, UF, município, código_produto). Origem de todo o dashboard.'
    }, {
      term: 'val_yearfx_*',
      cat: 'Coluna',
      tag: 'gold',
      short: 'Valor nominal em moeda corrente convertido pelo câmbio médio do ano. Auditoria histórica — não comparar entre anos.'
    }, {
      term: 'val_real_ipca_*',
      cat: 'Coluna',
      tag: 'gold',
      short: 'Valor projetado para hoje pela cadeia IPCA. Padrão deste dashboard para comparações inter-anuais.'
    }, {
      term: 'val_real_igpm_*',
      cat: 'Coluna',
      tag: 'gold',
      short: 'Idem usando IGP-M. Alternativa institucional ao IPCA; maior aderência a séries de commodities.'
    }, {
      term: 'data_quality_flag',
      cat: 'Coluna',
      tag: 'gold',
      short: 'Flag por linha: OK · MISSING_VALUE · MISSING_QUANTITY · ESTIMATED · BOUNDARY_HISTORIC · OUTLIER.'
    }]
  },
  ibge_pam: {
    label: 'IBGE PAM',
    sub: 'Produção Agrícola Municipal — área, produção e rendimento das lavouras',
    terms: [{
      term: 'PAM',
      cat: 'Fonte',
      tag: 'IBGE',
      short: 'Produção Agrícola Municipal — apuração anual do IBGE com área plantada/colhida, produção e rendimento médio das lavouras temporárias e permanentes.'
    }, {
      term: 'Lavoura temporária',
      cat: 'Conceito',
      short: 'Cultura de ciclo curto, replantada a cada safra (soja, milho, algodão, arroz, feijão).'
    }, {
      term: 'Lavoura permanente',
      cat: 'Conceito',
      short: 'Cultura de ciclo longo, sem replantio anual (café, cana-de-açúcar, laranja, cacau).'
    }, {
      term: 'Soja (grão)',
      cat: 'Produto',
      tag: '54011',
      short: 'Principal lavoura brasileira em área e valor. Concentrada no Centro-Oeste e Sul.'
    }, {
      term: 'Milho (grão)',
      cat: 'Produto',
      tag: '54012',
      short: 'Primeira e segunda safra (milho safrinha). Forte em MT, PR e GO.'
    }, {
      term: 'Café (grão)',
      cat: 'Produto',
      tag: '54013',
      short: 'Lavoura permanente; arábica e conilon. Concentrado em MG, ES e SP.'
    }, {
      term: 'Área colhida',
      cat: 'Coluna',
      short: 'Área efetivamente colhida da lavoura, em hectares (ha). Base do denominador do rendimento.'
    }, {
      term: 'Rendimento médio',
      cat: 'Coluna',
      short: 'Produtividade da lavoura = produção ÷ área colhida, em kg/ha. Média área-ponderada (nunca somada).'
    }, {
      term: 'gold_pam_production',
      cat: 'Coluna',
      tag: 'BigQuery',
      short: 'Tabela Gold. Uma linha por (ano, UF, município, lavoura), com área, produção, rendimento e valor.'
    }, {
      term: 'data_quality_flag',
      cat: 'Coluna',
      tag: 'gold',
      short: 'Flag por linha: OK · MISSING_VALUE · MISSING_QUANTITY · ESTIMATED · BOUNDARY_HISTORIC · OUTLIER.'
    }]
  },
  mdic_comex: {
    label: 'MDIC COMEX',
    sub: 'Comércio Exterior brasileiro — exportações e importações por UF e parceiro',
    terms: [{
      term: 'SECEX',
      cat: 'Fonte',
      tag: 'MDIC',
      short: 'Secretaria de Comércio Exterior do MDIC — divulga as estatísticas mensais de comércio exterior brasileiro.'
    }, {
      term: 'NCM',
      cat: 'Classificação',
      tag: 'OMA',
      short: 'Nomenclatura Comum do Mercosul — código de 8 dígitos derivado do SH para classificar mercadorias em comércio exterior.'
    }, {
      term: 'SH4 · SH6',
      cat: 'Classificação',
      tag: 'OMA',
      short: 'Sistema Harmonizado a 4 ou 6 dígitos. Compatível com classificações internacionais (UN Comtrade).'
    }, {
      term: 'FOB',
      cat: 'Termo',
      tag: 'Incoterm',
      short: 'Free On Board — valor da mercadoria posta a bordo no porto de embarque, base padrão para exportação brasileira.'
    }, {
      term: 'CIF',
      cat: 'Termo',
      tag: 'Incoterm',
      short: 'Cost, Insurance and Freight — valor da mercadoria + custos de frete e seguro até o porto de destino.'
    }, {
      term: 'UF de origem',
      cat: 'Coluna',
      short: 'Unidade da Federação onde está estabelecido o exportador / produtor da mercadoria declarada.'
    }, {
      term: 'Via',
      cat: 'Coluna',
      short: 'Modalidade de transporte utilizada: marítima, aérea, rodoviária, ferroviária, fluvial, dutos.'
    }, {
      term: 'Peso líquido',
      cat: 'Coluna',
      short: 'Peso da mercadoria sem embalagem, em quilogramas. Utilizado em cálculos de preço médio.'
    }, {
      term: 'gold_comex_flows',
      cat: 'Coluna',
      tag: 'BigQuery',
      short: 'Tabela Gold. Uma linha por (ano-mês, UF, NCM, país, via, fluxo).'
    }]
  },
  un_comtrade: {
    label: 'UN COMTRADE',
    sub: 'Estatísticas de Comércio Internacional — UN Statistics Division',
    terms: [{
      term: 'UNSD',
      cat: 'Fonte',
      tag: 'ONU',
      short: 'United Nations Statistics Division — mantém a base UN Comtrade com dados de comércio reportados pelas autoridades aduaneiras dos países.'
    }, {
      term: 'Reporter',
      cat: 'Coluna',
      short: 'País que está reportando a operação à UNSD.'
    }, {
      term: 'Partner',
      cat: 'Coluna',
      short: 'País contraparte da operação reportada.'
    }, {
      term: 'Flow',
      cat: 'Coluna',
      short: 'Direção do fluxo: export, import, re-export ou re-import.'
    }, {
      term: 'HS6',
      cat: 'Classificação',
      tag: 'OMA',
      short: 'Sistema Harmonizado a 6 dígitos — padrão internacional comum a Brasil (NCM) e ao mundo.'
    }, {
      term: 'BEC',
      cat: 'Classificação',
      tag: 'ONU',
      short: 'Broad Economic Categories — agrupamento por uso final (bens de consumo, capital, intermediários).'
    }, {
      term: 'Mirror data',
      cat: 'Método',
      short: 'Comparação entre o que um país declara exportar e o que o parceiro declara importar (e vice-versa). Útil para detectar sub-declaração.'
    }, {
      term: 'gold_comtrade_flows',
      cat: 'Coluna',
      tag: 'BigQuery',
      short: 'Tabela Gold. Uma linha por (ano, reporter, partner, HS6, flow).'
    }]
  },
  sefaz_nf: {
    label: 'SEFAZ NFe',
    sub: 'Fluxos de comércio interno brasileiro reconstruídos a partir de NFe',
    pending: true,
    terms: [{
      term: 'NFe',
      cat: 'Documento',
      tag: 'SEFAZ',
      short: 'Nota Fiscal Eletrônica — documento fiscal autorizado pela SEFAZ que registra cada operação de circulação de mercadoria no Brasil.'
    }, {
      term: 'CFOP',
      cat: 'Classificação',
      tag: 'CONFAZ',
      short: 'Código Fiscal de Operações e Prestações — identifica a natureza da operação (venda, transferência, devolução etc).'
    }, {
      term: 'CNAE',
      cat: 'Classificação',
      tag: 'IBGE',
      short: 'Classificação Nacional de Atividades Econômicas — identifica o setor de atividade do estabelecimento.'
    }, {
      term: 'ICMS',
      cat: 'Tributo',
      tag: 'CONFAZ',
      short: 'Imposto sobre Circulação de Mercadorias e Serviços — base e alíquota constam na NFe.'
    }, {
      term: 'UF origem · destino',
      cat: 'Coluna',
      short: 'Localização do remetente e do destinatário da NFe. Permite reconstruir fluxos inter-estaduais.'
    }, {
      term: 'Município',
      cat: 'Coluna',
      short: 'IBGE 7 dígitos. Identifica origem e destino com granularidade fina.'
    }, {
      term: 'Agregação privada',
      cat: 'Método',
      short: 'Linhas que representariam fluxos com menos de N=5 estabelecimentos são agregadas ou suprimidas para preservar sigilo fiscal.'
    }, {
      term: 'gold_nfe_flows',
      cat: 'Coluna',
      tag: 'BigQuery',
      short: 'Tabela Gold planejada. Uma linha por (ano-mês, par UF/município, CFOP, NCM).'
    }]
  },
  // ── Thematic groups (cross-cutting — not tied to a single banco) ────────
  // DRAFT: definitions to be reviewed by the team during integration/deploy.
  cross_analysis: {
    label: 'Análise cruzada',
    sub: 'Perspectivas multi-fonte — comparam séries de bancos diferentes',
    kind: 'tema',
    terms: [{
      term: 'Cruzamento entre fontes',
      cat: 'Perspectiva',
      short: 'Compara de 2 a 4 séries anuais de bancos diferentes no mesmo eixo de tempo, alternando entre base 100, eixo duplo e painéis.'
    }, {
      term: 'Base 100',
      cat: 'Método',
      short: 'Reindexação de cada série a 100 no ano inicial, para comparar trajetórias independentemente da unidade.'
    }, {
      term: 'Eixo duplo',
      cat: 'Método',
      short: 'Duas unidades em eixos verticais distintos (esquerda/direita) — compara o formato das curvas, não o nível absoluto.'
    }, {
      term: 'Coeficiente de exportação',
      cat: 'Perspectiva',
      tag: 'IBGE × MDIC',
      short: 'Parcela da produção de cada UF (IBGE) que segue para exportação (MDIC). Mede a orientação exportadora por estado.'
    }, {
      term: 'Participação no mercado mundial',
      cat: 'Perspectiva',
      tag: 'MDIC × Comtrade',
      short: 'Exportação brasileira como fração da exportação mundial do produto (UN Comtrade).'
    }, {
      term: 'Espelho comercial',
      cat: 'Perspectiva',
      tag: 'MDIC × Comtrade',
      short: 'A mesma exportação vista por MDIC, Comtrade e parceiros; a divergência ao longo do tempo é um diagnóstico de qualidade entre fontes.'
    }, {
      term: 'Balanço da cadeia',
      cat: 'Perspectiva',
      tag: 'massa',
      short: 'Reconstitui o destino da produção — comércio interno (SEFAZ), exportação (MDIC) e consumo/estoque — com massa conservada, mais a fatia no mercado mundial.'
    }, {
      term: 'Defasagem safra → embarque',
      cat: 'Perspectiva',
      tag: 'lead-lag',
      short: 'Quantos meses os embarques (MDIC, mensal) seguem o pico da safra (IBGE), estimado por correlação cruzada por defasagem.'
    }]
  },
  curadoria: {
    label: 'Curadoria',
    sub: 'Enriquecimento — conhecimento do pesquisador sobre os dados',
    kind: 'tema',
    terms: [{
      term: 'Curadoria (enriquecimento)',
      cat: 'Conceito',
      short: 'Camada de anotações institucionais e compartilhadas sobre as dimensões dos bancos. Alimenta as análises curadas no modo multi-fonte.'
    }, {
      term: 'Nível de industrialização',
      cat: 'Dimensão',
      short: 'Classificação de cada código de produto como Bruta, Processada ou Misturado. Base da análise de valor agregado.'
    }, {
      term: 'Bruta · Processada · Misturado',
      cat: 'Dimensão',
      short: 'Produto sem transformação · produto com beneficiamento industrial · código que agrega os dois (não separável).'
    }, {
      term: 'Finalidade econômica',
      cat: 'Dimensão',
      short: 'Finalidade atribuída ao par regime × fluxo: Consumo ou Processamento. Combinada com a direção (importação = comprar, exportação = vender), classifica cada transação.'
    }, {
      term: 'Consumo · Processamento',
      cat: 'Dimensão',
      short: 'Os dois destinos do bem: consumo final, ou transformação/beneficiamento industrial. É a finalidade que a curadoria atribui a cada par regime × fluxo.'
    }, {
      term: 'Par regime × fluxo',
      cat: 'Conceito',
      short: 'Unidade de classificação da finalidade econômica: um regime aduaneiro cruzado com uma direção de fluxo. Um regime ou fluxo isolado não determina o mercado — só o par.'
    }, {
      term: 'Valor agregado',
      cat: 'Análise',
      short: 'Exportação separada entre bruta e processada, com participação do processado no tempo e prêmio de preço do processado sobre o bruto.'
    }, {
      term: 'Rascunho → aplicado',
      cat: 'Operação',
      short: 'As edições da curadoria ficam em rascunho; "Aplicar à base" grava no log de classificação (SCD2) e o JOIN ao vivo atualiza as análises para todos os pesquisadores.'
    }]
  }
};
window.GLOSSARY = GLOSSARY;

// Coverage lint: every visible banco should have a glossary section.
if (window.auditBancoCoverage) {
  window.auditBancoCoverage('glossário (glossary.js)', b => !!window.GLOSSARY[b.id]);
}
})(); } catch (e) { __ds_ns.__errors.push({ path: "glossary.js", error: String((e && e.message) || e) }); }

// previewData.js
try { (() => {
// previewData.js — banco-keyed SYNTHETIC adapters for the flow / partner /
// monthly perspectives. These implement a stable DATA CONTRACT so the
// views never need rewriting: when a banco goes live, replace the body of
// each adapter with a real query against its Gold table and keep the
// returned shape identical. Every adapter sets `preview: true` so views
// can flag the data as demonstration until the real source exists.
//
// CONTRACTS — flowData / partnerData / monthlyData. SHAPE is defined once in
// contracts.js (@typedef FlowData / PartnerData / MonthlyData) — the single
// source of truth. Keep the returned keys in sync with it (the runtime lint
// window.auditSnapshotContracts warns if a contracted key goes missing).

(function () {
  // Deterministic PRNG (window.seeded) and macro-shock curve (window.macroShock)
  // live in synthUtils.js — used here via window.* so preview snapshots stay in
  // lockstep with the cross-source / cross-chain builders.

  // Partner universes per banco (what "destino"/"parceiro" means).
  const COUNTRIES = ['China', 'Estados Unidos', 'Países Baixos', 'Alemanha', 'Japão', 'Argentina', 'Espanha', 'Itália', 'Reino Unido', 'França'];
  const UFS = ['SP', 'PR', 'RS', 'MG', 'SC', 'MT', 'PA', 'BA', 'GO', 'AM'];
  // Generic fallback universe for a dimension, chosen by its DECLARED kind
  // (bancos.js → dimensions[dim].kind): 'country' → nations, else Brazilian UFs.
  // No bancoId branching — a new banco just declares its dimension kinds.
  const genericUniverse = (id, dim) => (window.bancoDim && window.bancoDim(id, dim).kind) === 'country' ? COUNTRIES : UFS;
  function originsFor(bancoId) {
    // Demo origin universes (window.DEMO_PARAMS via SNAP_ORIGINS); fallback is a
    // generic set chosen by the banco's declared origin kind.
    return window.SNAP_ORIGINS && window.SNAP_ORIGINS[bancoId] || genericUniverse(bancoId, 'origin').slice(0, 5);
  }
  function destsFor(bancoId) {
    const real = window.SNAP_PARTNERS && window.SNAP_PARTNERS[bancoId];
    if (real) return real.slice(0, 6);
    return genericUniverse(bancoId, 'dest').slice(0, 6);
  }
  // Once a banco is live, its adapters serve real(istic) data → no preview banner.
  function previewFor(bancoId) {
    const b = window.bancoById ? window.bancoById(bancoId) : null;
    return !(b && b.status === 'live');
  }

  // Display currency symbol for a banco — derived from its declared
  // baseCurrency (bancos.js) via CURRENCY_FX, not a per-banco literal map.
  const unitFor = bancoId => {
    const ccy = window.canonCurrencyFor ? window.canonCurrencyFor(bancoId) : 'BRL';
    return (window.CURRENCY_FX && window.CURRENCY_FX[ccy] || {
      symbol: 'R$'
    }).symbol;
  };
  function yearWindow(summary) {
    const y0 = summary && summary.startDate ? parseInt(summary.startDate.slice(0, 4), 10) : 2010;
    const y1 = summary && summary.endDate ? parseInt(summary.endDate.slice(0, 4), 10) : 2024;
    return [Math.max(1997, y0), Math.min(2024, y1)];
  }

  // ── FLOW (origin → destination) ──────────────────────────────────────
  window.flowData = function (bancoId, summary) {
    const rnd = window.seeded('flow:' + bancoId);
    const origins = originsFor(bancoId);
    const dests = destsFor(bancoId);
    const unit = unitFor(bancoId);
    const nodes = [...origins.map((o, i) => ({
      id: 'o' + i,
      label: o,
      side: 'origin',
      value: 0
    })), ...dests.map((d, i) => ({
      id: 'd' + i,
      label: d,
      side: 'dest',
      value: 0
    }))];
    const links = [];
    origins.forEach((o, oi) => {
      // each origin sends to 2–3 destinations
      const nLinks = 2 + Math.floor(rnd() * 2);
      const picks = dests.map((d, di) => ({
        di,
        w: rnd()
      })).sort((a, b) => b.w - a.w).slice(0, nLinks);
      picks.forEach(p => {
        const value = Math.round((200 + rnd() * 1800) * (1 - oi * 0.12));
        links.push({
          source: 'o' + oi,
          target: 'd' + p.di,
          value
        });
      });
    });
    // node totals
    links.forEach(l => {
      const s = nodes.find(n => n.id === l.source);
      if (s) s.value += l.value;
      const t = nodes.find(n => n.id === l.target);
      if (t) t.value += l.value;
    });
    return {
      preview: previewFor(bancoId),
      unit,
      originLabel: window.bancoDim(bancoId, 'origin').label || 'origem',
      destLabel: window.bancoDim(bancoId, 'dest').label || 'destino',
      nodes,
      links
    };
  };

  // ── PARTNER (ranking of trading partners) ────────────────────────────
  window.partnerData = function (bancoId, summary) {
    const rnd = window.seeded('partner:' + bancoId);
    const universe = window.SNAP_PARTNERS && window.SNAP_PARTNERS[bancoId] || genericUniverse(bancoId, 'partner');
    const partners = universe.map((name, i) => {
      const base = (3200 - i * 280) * (0.7 + rnd() * 0.6);
      const exp = Math.round(base * (0.5 + rnd() * 0.4));
      const imp = Math.round(base * (0.2 + rnd() * 0.4));
      return {
        name,
        exp,
        imp,
        value: exp + imp
      };
    }).sort((a, b) => b.value - a.value);
    return {
      preview: previewFor(bancoId),
      flowLabel: window.bancoDim(bancoId, 'partner').label || 'parceiro',
      unit: unitFor(bancoId),
      partners
    };
  };

  // ── MONTHLY (seasonality) ────────────────────────────────────────────
  window.monthlyData = function (bancoId, summary) {
    const rnd = window.seeded('monthly:' + bancoId);
    const [y0, y1] = yearWindow(summary);
    const years = [];
    for (let y = y1; y >= Math.max(y0, y1 - 9); y--) years.push(y);
    years.sort((a, b) => a - b);

    // seasonal profile: real per-banco castanha export seasonality when known,
    // else a generic harvest-driven mid-year peak.
    const realSeason = window.SNAP_SEASONAL && window.SNAP_SEASONAL[bancoId];
    const seasonal = realSeason ? realSeason.map(s => s * (1 + (rnd() - 0.5) * 0.05)) : Array.from({
      length: 12
    }, (_, m) => 1 + 0.35 * Math.sin((m - 2) / 12 * Math.PI * 2) + (rnd() - 0.5) * 0.08);
    const matrix = {};
    const series = [];
    years.forEach((y, yi) => {
      const trend = 1 + yi * 0.05;
      const row = seasonal.map((s, m) => {
        const v = Math.round(800 * s * trend * (0.9 + rnd() * 0.2));
        series.push({
          ym: `${y}-${String(m + 1).padStart(2, '0')}`,
          y,
          m: m + 1,
          v
        });
        return v;
      });
      matrix[y] = row;
    });
    const monthlyAvg = Array.from({
      length: 12
    }, (_, m) => {
      const vals = years.map(y => matrix[y][m]);
      return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
    });
    return {
      preview: previewFor(bancoId),
      unit: unitFor(bancoId),
      years,
      months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
      matrix,
      monthlyAvg,
      series
    };
  };
  window.MONTH_LABELS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

  // ── PRODUCTIVITY (área + rendimento por cultura/UF) ──────────────────
  // CONTRACT: productivityData(bancoId, cropCode, summary) — SHAPE defined in
  // contracts.js (@typedef ProductivityData). For a banco with the 'yield'
  // capability (IBGE PAM). Demo crop universe +
  // per-UF productivity index live in demoFixture.js (window.DEMO_PARAMS.pam);
  // swap the body for a real query against the Gold table and keep this shape.
  window.productivityData = function (bancoId, cropCode, summary) {
    const pam = window.DEMO_PARAMS && window.DEMO_PARAMS.pam || {
      crops: [],
      ufProductivity: {}
    };
    const crops = pam.crops || [];
    if (!crops.length) return null;
    const crop = crops.find(c => c.code === cropCode) || crops[0];
    const cov = (window.DEMO_PARAMS && window.DEMO_PARAMS.snapshot && window.DEMO_PARAMS.snapshot.coverage || {})[bancoId] || [1990, 2024];
    const [y0, y1] = cov;
    const years = [];
    for (let y = y0; y <= y1; y++) years.push(y);
    const n = years.length;
    const rnd = window.seeded('prod:' + bancoId + ':' + crop.code);
    const shock = window.macroShock || (() => 1);

    // National annual series — yield & area each grow along an S-curve from
    // their start fraction to the end-year anchor, with mild noise + a damped
    // macro-shock (weather years). prodT = yieldKgHa × areaHa ÷ 1000.
    const series = years.map((y, i) => {
      const t = n > 1 ? i / (n - 1) : 1;
      const ease = t * t * (3 - 2 * t);
      const yGrow = crop.yldStart + (1 - crop.yldStart) * ease;
      const aGrow = crop.areaStart + (1 - crop.areaStart) * ease;
      const wx = 1 + (shock(y) - 1) * 0.5; // weather damped onto yield
      const yieldKgHa = crop.yieldEnd * yGrow * (1 + (rnd() - 0.5) * 0.05) * wx;
      const areaHa = crop.areaEndKha * 1000 * aGrow * (1 + (rnd() - 0.5) * 0.04);
      const prodT = yieldKgHa * areaHa / 1000;
      return {
        y,
        yieldKgHa,
        areaHa,
        prodT
      };
    });
    const last = series[series.length - 1] || {
      yieldKgHa: 0,
      areaHa: 0,
      prodT: 0
    };
    const first = series[0] || last;
    const yieldCagr = first.yieldKgHa > 0 && n > 1 ? (Math.pow(last.yieldKgHa / first.yieldKgHa, 1 / (n - 1)) - 1) * 100 : 0;

    // Per-UF: join the canonical tile grid (window.UF_DATA · col/row) with the
    // crop's productivity index. Yield = national × index × seeded jitter;
    // area allocated proportionally to (index × UF base weight) of national area.
    const idxMap = pam.ufProductivity || {};
    const ufs = Array.isArray(window.UF_DATA) ? window.UF_DATA : [];
    const weighted = ufs.map((u, i) => {
      const idx = idxMap[u.uf] != null ? idxMap[u.uf] : 0.88;
      const jitter = 0.93 + 0.14 * Math.abs(Math.sin(i * 1.7 + crop.code.charCodeAt(4)));
      const yieldKgHa = last.yieldKgHa * idx * (0.97 + (rnd() - 0.5) * 0.06);
      const areaW = idx * (0.4 + u.value / 1000) * jitter;
      return {
        u,
        idx,
        yieldKgHa,
        areaW
      };
    });
    const totW = weighted.reduce((s, x) => s + x.areaW, 0) || 1;
    const byUF = weighted.map(({
      u,
      yieldKgHa,
      areaW
    }) => {
      const areaHa = last.areaHa * (areaW / totW);
      return {
        uf: u.uf,
        name: u.name,
        region: u.region,
        col: u.col,
        row: u.row,
        yieldKgHa,
        areaHa,
        prodT: yieldKgHa * areaHa / 1000
      };
    });
    return {
      preview: previewFor(bancoId),
      yieldUnit: pam.yieldUnit || 'kg/ha',
      areaUnit: pam.areaUnit || 'ha',
      crop: {
        code: crop.code,
        name: crop.name
      },
      crops: crops.map(c => ({
        code: c.code,
        name: c.name
      })),
      national: {
        yieldKgHa: last.yieldKgHa,
        areaHa: last.areaHa,
        prodT: last.prodT,
        yieldCagr
      },
      series,
      byUF
    };
  };

  // ── REPRESENTATIVE PER-BANCO SNAPSHOT ────────────────────────────────
  // Produces a PEVS-SHAPED in-memory snapshot for a banco that has no real
  // Gold yet. MDIC COMEX and UN Comtrade are LIVE on these (representative
  // data generated from the explicit contract shape, 02_SNAPSHOT_CONTRACTS.md);
  // the banco-aware
  // applyFilters(summary, bancoId) consumes them end-to-end. Same keys/shape
  // as dataStore.datasetFor('ibge_pevs'). Deterministic (seeded) → stable
  // across reloads. Replace with the real query when the real Gold lands;
  // THE SHAPE IS THE CONTRACT — defined once in contracts.js (@typedef
  // BancoSnapshot); the handoff doc 02_SNAPSHOT_CONTRACTS.md points there.
  // The commodity-specific demo VALUES (product universes, partners, origins,
  // seasonality, coverage) live in ONE place — demoFixture.js (window.DEMO_PARAMS).
  // To demo a different chain, edit that file; the references below don't change.
  // [code, name, priceUsdPerKg, volEndKt] → v(US$ mi)=price×volKt, q(mil t)=volKt.
  const _SNAP = window.DEMO_PARAMS && window.DEMO_PARAMS.snapshot || {};
  const SNAP_PRODUCTS = _SNAP.products || {};
  const SNAP_COVERAGE = _SNAP.coverage || {};
  const SNAP_START_FRAC = _SNAP.startFrac || {};
  const SNAP_PARTNERS = _SNAP.partners || {};
  const SNAP_ORIGINS = _SNAP.origins || {};
  const SNAP_SEASONAL = _SNAP.seasonal || {};
  window.SNAP_PARTNERS = SNAP_PARTNERS;
  window.SNAP_ORIGINS = SNAP_ORIGINS;
  window.SNAP_SEASONAL = SNAP_SEASONAL;
  window.snapshotFor = function (bancoId) {
    const defs = SNAP_PRODUCTS[bancoId];
    if (!defs) return null;
    const prods = defs.map(([code, name]) => ({
      code,
      name,
      unit: 't',
      family: 'mass'
    }));
    const [y0, y1] = SNAP_COVERAGE[bancoId] || [1997, 2024];
    const startFrac = SNAP_START_FRAC[bancoId] ?? 0.3;
    const years = [];
    for (let y = y0; y <= y1; y++) years.push(y);
    const rnd = window.seeded('snap:' + bancoId);
    const banco = window.bancoById ? window.bancoById(bancoId) : null;
    const hasGeo = !!(banco && banco.provides && banco.provides.includes('geo'));
    // The conventions layer treats every stored value as BRL-canonical and
    // multiplies by the display FX rate. COMEX/Comtrade are priced in USD, so
    // store values in BRL-equivalent (USD ÷ USD-rate); changeDatabase defaults
    // the display currency to USD, which then renders the real US$ figures.
    const baseCcy = window.canonCurrencyFor ? window.canonCurrencyFor(bancoId) : 'BRL';
    const baseRate = (window.CURRENCY_FX && window.CURRENCY_FX[baseCcy] || {
      rate: 1
    }).rate || 1;
    const canonFactor = 1 / baseRate;

    // productTS[code] = [{ y, v(canonical-BRL mi), q(mil t), family }] — grown
    // along an S-curve from startFrac→1 of the end-year anchor, + noise/shocks.
    const productTS = {};
    defs.forEach(([code, name, price, volEnd], pi) => {
      productTS[code] = years.map((y, i) => {
        const t = i / (years.length - 1 || 1);
        const ease = t * t * (3 - 2 * t);
        const grow = startFrac + (1 - startFrac) * ease;
        const noise = 1 + (rnd() - 0.5) * 0.09;
        const q = volEnd * grow * noise * window.macroShock(y); // mil t (thousand tonnes)
        const v = price * q * canonFactor; // canonical mi (price US$/kg × kt × FX)
        return {
          y,
          v,
          q,
          family: 'mass'
        };
      });
    });

    // overviewTS = annual aggregate; v in bi (mi ÷ 1000), q_mass summed. No q_vol.
    const overviewTS = years.map((y, i) => {
      let v = 0,
        qm = 0;
      prods.forEach(p => {
        const pt = productTS[p.code][i];
        v += pt.v / 1000;
        qm += pt.q;
      });
      return {
        y,
        v,
        q: qm,
        q_mass: qm
      };
    });

    // ufData only for bancos with `geo` (COMEX/SEFAZ; NOT Comtrade). Reuses the
    // canonical tile-map grid (col/row) but reweights toward the origin UFs.
    let ufData = [];
    let qualityByUf = [];
    if (hasGeo && Array.isArray(window.UF_DATA)) {
      const last = overviewTS[overviewTS.length - 1] || {
        v: 0,
        q_mass: 0
      };
      const origins = new Set(SNAP_ORIGINS[bancoId] || []);
      const weighted = window.UF_DATA.map(u => ({
        u,
        w: (origins.has(u.uf) ? 6 : 0.25) * (0.6 + u.value / 1000)
      }));
      const tot = weighted.reduce((a, x) => a + x.w, 0) || 1;
      ufData = weighted.map(({
        u,
        w
      }) => {
        const f = w / tot;
        return {
          uf: u.uf,
          name: u.name,
          region: u.region,
          col: u.col,
          row: u.row,
          value: last.v * 1000 * f,
          q_mass: last.q_mass * f,
          q_vol: 0
        };
      });
      qualityByUf = window.UF_DATA.map((u, i) => ({
        uf: u.uf,
        name: u.name,
        region: u.region,
        col: u.col,
        row: u.row,
        not_ok: Math.min(0.4, (origins.has(u.uf) ? 0.06 : 0.16) + Math.abs(Math.sin(i * 1.7)) * 0.05)
      }));
    }

    // quality flag distribution — reuse the canonical flag taxonomy (shared
    // vocabulary across bancos); shares tilted a bit by banco.
    const quality = (window.QUALITY_FLAGS || []).map(q => ({
      ...q
    }));

    // per-product quality (flag shares) — deterministic, plausible.
    const FLAG_IDS = ['OK', 'MISSING_VALUE', 'MISSING_QUANTITY', 'ESTIMATED', 'OUTLIER', 'BOUNDARY_HISTORIC'];
    const qualityByProduct = defs.map(([code, name], pi) => {
      const r = window.seeded('q:' + bancoId + ':' + code);
      const ok = 0.80 + r() * 0.14;
      const rest = 1 - ok;
      const w = [0, r() * 0.4 + 0.25, r() * 0.3 + 0.15, r() * 0.2 + 0.1, r() * 0.12 + 0.05, r() * 0.1 + 0.05];
      const wsum = w.reduce((a, b) => a + b, 0) - w[0] || 1;
      const row = {
        code,
        name
      };
      FLAG_IDS.forEach((id, k) => {
        row[id] = k === 0 ? ok : w[k] / wsum * rest;
      });
      return row;
    });

    // quality over coverage years (rate of OK rises gently over time).
    const qualityTs = years.map((y, i) => {
      const t = i / (years.length - 1 || 1);
      const ok = 0.74 + t * 0.16 + Math.sin(i * 1.3) * 0.012;
      const missing_value = Math.max(0, 0.10 - t * 0.05);
      const missing_quantity = Math.max(0, 0.05 - t * 0.02);
      const estimated = 0.04,
        outlier = 0.02;
      const boundary = Math.max(0, 1 - ok - missing_value - missing_quantity - estimated - outlier);
      return {
        y,
        ok,
        missing_value,
        missing_quantity,
        estimated,
        outlier,
        boundary
      };
    });
    return {
      products: prods,
      productTS,
      overviewTS,
      ufData,
      quality,
      qualityTs,
      qualityByProduct,
      qualityByUf,
      topMunis: [],
      // municipality table not synthesized
      regions: window.REGIONS || [],
      _synthetic: true // marker: representative, not real Gold
    };
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "previewData.js", error: String((e && e.message) || e) }); }

// seriesUtils.js
try { (() => {
// seriesUtils.js — shared series analytics + the categorical viz scale.
//
// Single source of truth for the comparison perspectives (ViewProductCompare,
// ViewCrossSource) and any chart that paints a categorical series. These
// helpers used to be COPY-PASTED verbatim across those views (growth /
// pearson / cagr / corrColor) and the 10-stop color array was duplicated in
// dataFilters.js and ViewValueVolume.jsx. Centralised here so a fix lands in
// one place. Loaded right after data.js (alongside synthUtils).

// ── Categorical color scale (the 10-stop --viz ramp) ───────────────────
// Token references only — never raw hex (see colors_and_type.css · --viz-*).
// Consumers that need overflow stops append their own grays.
window.VIZ_SCALE = ['var(--viz-1)', 'var(--viz-2)', 'var(--viz-3)', 'var(--viz-4)', 'var(--viz-5)', 'var(--viz-6)', 'var(--viz-7)', 'var(--viz-8)', 'var(--viz-9)', 'var(--viz-10)'];
// i-th categorical color, wrapping around the scale.
window.vizColor = i => window.VIZ_SCALE[(i % window.VIZ_SCALE.length + window.VIZ_SCALE.length) % window.VIZ_SCALE.length];

// ── Series statistics ──────────────────────────────────────────────────
// Year-over-year growth array from a list of points (default value key 'v').
window.seriesGrowth = (pts, key = 'v') => (pts || []).slice(1).map((d, i) => pts[i][key] ? (d[key] - pts[i][key]) / pts[i][key] : 0);

// Pearson correlation between two equal-intent arrays (truncated to the
// shorter length). Returns 0 when undefined (n < 2 or zero variance).
window.pearson = (a, b) => {
  const n = Math.min(a.length, b.length);
  if (n < 2) return 0;
  const ma = a.reduce((s, x) => s + x, 0) / n;
  const mb = b.reduce((s, x) => s + x, 0) / n;
  let num = 0,
    da = 0,
    db = 0;
  for (let i = 0; i < n; i++) {
    const xa = a[i] - ma,
      xb = b[i] - mb;
    num += xa * xb;
    da += xa * xa;
    db += xb * xb;
  }
  return da && db ? num / Math.sqrt(da * db) : 0;
};

// Compound annual growth rate, in PERCENT, over `periods` intervals.
window.cagrPct = (v0, vT, periods) => {
  const p = periods || 1;
  return v0 > 0 ? (Math.pow(vT / v0, 1 / p) - 1) * 100 : 0;
};
// Accumulated change from v0 to vT, in PERCENT.
window.accumPct = (v0, vT) => v0 > 0 ? (vT - v0) / v0 * 100 : 0;

// Correlation-cell tint. Positive → institutional green, negative → terracotta
// error token, alpha scaled by |r| (0.12 floor → 0.72 at |r|=1). Token-driven
// via color-mix so it tracks the palette — never a raw rgba() literal.
window.corrColor = r => {
  const token = r >= 0 ? 'var(--ok)' : 'var(--err)';
  const pct = Math.round((0.12 + Math.abs(r) * 0.6) * 100);
  return `color-mix(in srgb, ${token} ${pct}%, transparent)`;
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "seriesUtils.js", error: String((e && e.message) || e) }); }

// slides/deck-stage.js
try { (() => {
/**
 * <deck-stage> — reusable web component for HTML decks.
 *
 * Handles:
 *  (a) speaker notes — reads <script type="application/json" id="speaker-notes">
 *      and posts {slideIndexChanged: N} to the parent window on nav.
 *  (b) keyboard navigation — ←/→, PgUp/PgDn, Space, Home/End, number keys.
 *  (c) press R to reset to slide 0 (with a tasteful keyboard hint).
 *  (d) bottom-center overlay showing slide count + hints, fades out on idle.
 *  (e) auto-scaling — inner canvas is a fixed design size (default 1920×1080)
 *      scaled with `transform: scale()` to fit the viewport, letterboxed.
 *      Set the `noscale` attribute to render at authored size (1:1) — the
 *      PPTX exporter sets this so its DOM capture sees unscaled geometry.
 *  (f) print — `@media print` lays every slide out as its own page at the
 *      design size, so the browser's Print → Save as PDF produces a clean
 *      one-page-per-slide PDF with no extra setup.
 *  (g) thumbnail rail — resizable left-hand column of per-slide thumbnails
 *      (static clones). Click to navigate; ↑/↓ with a thumbnail focused to
 *      step between slides; drag to reorder; right-click for
 *      Skip / Move up / Move down / Delete (opens a Cancel/Delete confirm
 *      dialog). Drag the rail's right edge to resize; width persists to
 *      localStorage. Skipped slides carry `data-deck-skip`, are dimmed in
 *      the rail, omitted from prev/next navigation, and hidden at print.
 *      The rail is suppressed in presenting mode, in the host's Preview
 *      mode (ViewerMode='none'), on `noscale`, and via the `no-rail`
 *      attribute. Rail mutations dispatch a `deckchange`
 *      CustomEvent on the element: detail = {action, from, to, slide}.
 *
 * Slides are HIDDEN, not unmounted. Non-active slides stay in the DOM with
 * `visibility: hidden` + `opacity: 0`, so their state (videos, iframes,
 * form inputs, React trees) is preserved across navigation.
 *
 * Lifecycle event — the component dispatches a `slidechange` CustomEvent on
 * itself whenever the active slide changes (including the initial mount).
 * The event bubbles and composes out of shadow DOM, so you can listen on
 * the <deck-stage> element or on document:
 *
 *   document.querySelector('deck-stage').addEventListener('slidechange', (e) => {
 *     e.detail.index         // new 0-based index
 *     e.detail.previousIndex // previous index, or -1 on init
 *     e.detail.total         // total slide count
 *     e.detail.slide         // the new active slide element
 *     e.detail.previousSlide // the prior slide element, or null on init
 *     e.detail.reason        // 'init' | 'keyboard' | 'click' | 'tap' | 'api'
 *   });
 *
 * Persistence: none at the deck level. The host app keeps the current slide
 * in its own URL (?slide=) and re-delivers it via location.hash on load, so a
 * bare load with no hash always starts at slide 1.
 *
 * Usage:
 *   <style>deck-stage:not(:defined){visibility:hidden}</style>
 *   <deck-stage width="1920" height="1080">
 *     <section data-label="Title">...</section>
 *     <section data-label="Agenda">...</section>
 *   </deck-stage>
 *   <script src="deck-stage.js"></script>
 *
 * The :not(:defined) rule prevents a flash of the first slide at its
 * authored styles before this script runs and attaches the shadow root.
 *
 * Slides are the direct element children of <deck-stage>. Each slide is
 * automatically tagged with:
 *   - data-screen-label="NN Label"   (1-indexed, for comment flow)
 *   - data-om-validate="no_overflowing_text,no_overlapping_text,slide_sized_text"
 */

(() => {
  const DESIGN_W_DEFAULT = 1920;
  const DESIGN_H_DEFAULT = 1080;
  const OVERLAY_HIDE_MS = 1800;
  const VALIDATE_ATTR = 'no_overflowing_text,no_overlapping_text,slide_sized_text';
  const pad2 = n => String(n).padStart(2, '0');

  // Label precedence: data-label → data-screen-label (number stripped) → first heading → "Slide".
  const getSlideLabel = el => {
    const explicit = el.getAttribute('data-label');
    if (explicit) return explicit;
    const existing = el.getAttribute('data-screen-label');
    if (existing) return existing.replace(/^\s*\d+\s*/, '').trim() || existing;
    const h = el.querySelector('h1, h2, h3, [data-title]');
    const t = h && (h.textContent || '').trim().slice(0, 40);
    if (t) return t;
    return 'Slide';
  };
  const stylesheet = `
    :host {
      position: fixed;
      inset: 0;
      display: block;
      background: #000;
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif;
      overflow: hidden;
    }
    /* connectedCallback holds this until document.fonts.ready (capped 2s) so
     * the first visible paint has the deck's real typography + final rail
     * layout. opacity (not visibility) so the active slide can't un-hide
     * itself via the ::slotted([data-deck-active]) visibility:visible rule.
     * Only the stage/rail hide — the black :host background stays, so the
     * iframe doesn't flash the page's default white. */
    :host([data-fonts-pending]) .stage,
    :host([data-fonts-pending]) .rail { opacity: 0; pointer-events: none; }

    .stage {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .canvas {
      position: relative;
      transform-origin: center center;
      flex-shrink: 0;
      background: #fff;
      will-change: transform;
    }

    /* Slides live in light DOM (via <slot>) so authored CSS still applies.
       We absolutely position each slotted child to stack them. */
    ::slotted(*) {
      position: absolute !important;
      inset: 0 !important;
      width: 100% !important;
      height: 100% !important;
      box-sizing: border-box !important;
      overflow: hidden;
      opacity: 0;
      pointer-events: none;
      visibility: hidden;
    }
    ::slotted([data-deck-active]) {
      opacity: 1;
      pointer-events: auto;
      visibility: visible;
    }

    /* Tap zones for mobile — back/forward thirds like Stories.
       Transparent, no visible UI, don't block the overlay. */
    .tapzones {
      position: fixed;
      inset: 0;
      display: flex;
      z-index: 2147482000;
      pointer-events: none;
    }
    .tapzone {
      flex: 1;
      pointer-events: auto;
      -webkit-tap-highlight-color: transparent;
    }
    /* Only activate tap zones on coarse pointers (touch devices). */
    @media (hover: hover) and (pointer: fine) {
      .tapzones { display: none; }
    }

    .overlay {
      position: fixed;
      left: 50%;
      bottom: 22px;
      transform: translate(-50%, 6px) scale(0.92);
      filter: blur(6px);
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 4px;
      background: #000;
      color: #fff;
      border-radius: 999px;
      font-size: 12px;
      font-feature-settings: "tnum" 1;
      letter-spacing: 0.01em;
      opacity: 0;
      pointer-events: none;
      transition: opacity 260ms ease, transform 260ms cubic-bezier(.2,.8,.2,1), filter 260ms ease;
      transform-origin: center bottom;
      z-index: 2147483000;
      user-select: none;
    }
    .overlay[data-visible] {
      opacity: 1;
      pointer-events: auto;
      transform: translate(-50%, 0) scale(1);
      filter: blur(0);
    }

    .btn {
      appearance: none;
      -webkit-appearance: none;
      background: transparent;
      border: 0;
      margin: 0;
      padding: 0;
      color: inherit;
      font: inherit;
      cursor: default;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      height: 28px;
      min-width: 28px;
      border-radius: 999px;
      color: rgba(255,255,255,0.72);
      transition: background 140ms ease, color 140ms ease;
      -webkit-tap-highlight-color: transparent;
    }
    .btn:hover { background: rgba(255,255,255,0.12); color: #fff; }
    .btn:active { background: rgba(255,255,255,0.18); }
    .btn:focus { outline: none; }
    .btn:focus-visible { outline: none; }
    .btn::-moz-focus-inner { border: 0; }
    .btn svg { width: 14px; height: 14px; display: block; }
    .btn.reset {
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.02em;
      padding: 0 10px 0 12px;
      gap: 6px;
      color: rgba(255,255,255,0.72);
    }
    .btn.reset .kbd {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 16px;
      height: 16px;
      padding: 0 4px;
      font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
      font-size: 10px;
      line-height: 1;
      color: rgba(255,255,255,0.88);
      background: rgba(255,255,255,0.12);
      border-radius: 4px;
    }

    .count {
      font-variant-numeric: tabular-nums;
      color: #fff;
      font-weight: 500;
      padding: 0 8px;
      min-width: 42px;
      text-align: center;
      font-size: 12px;
    }
    .count .sep { color: rgba(255,255,255,0.45); margin: 0 3px; font-weight: 400; }
    .count .total { color: rgba(255,255,255,0.55); }

    .divider {
      width: 1px;
      height: 14px;
      background: rgba(255,255,255,0.18);
      margin: 0 2px;
    }

    /* ── Thumbnail rail ──────────────────────────────────────────────────
       Fixed column on the left; each thumbnail is a static deep-clone of
       the light-DOM slide scaled into a 16:9 (or design-aspect) frame. The
       stage re-fits around it (see _fit); hidden during present / noscale
       / print so capture geometry and fullscreen output are unchanged. */
    .rail {
      position: fixed;
      left: 0;
      top: 0;
      bottom: 0;
      width: var(--deck-rail-w, 188px);
      background: #141414;
      border-right: 1px solid rgba(255,255,255,0.08);
      overflow-y: auto;
      overflow-x: hidden;
      padding: 12px 10px;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      gap: 12px;
      z-index: 2147482500;
      scrollbar-width: thin;
      scrollbar-color: rgba(255,255,255,0.18) transparent;
    }
    .rail::-webkit-scrollbar { width: 8px; }
    .rail::-webkit-scrollbar-track { background: transparent; margin: 2px; }
    .rail::-webkit-scrollbar-thumb {
      background: rgba(255,255,255,0.18);
      border-radius: 4px;
      border: 2px solid transparent;
      background-clip: content-box;
    }
    .rail::-webkit-scrollbar-thumb:hover {
      background: rgba(255,255,255,0.28);
      border: 2px solid transparent;
      background-clip: content-box;
    }
    :host([no-rail]) .rail,
    :host([noscale]) .rail { display: none; }
    .rail[data-presenting] { display: none; }
    /* User-driven show/hide (the TweaksPanel toggle) slides instead of
       popping. Transitions are gated on :host([data-rail-anim]) — set only
       for the 200ms around the toggle — so window-resize and rail-width
       drag (which also call _fit) don't lag behind the cursor. */
    .rail[data-user-hidden] { transform: translateX(-100%); }
    :host([data-rail-anim]) .rail { transition: transform 200ms cubic-bezier(.3,.7,.4,1); }
    :host([data-rail-anim]) .stage { transition: left 200ms cubic-bezier(.3,.7,.4,1); }
    :host([data-rail-anim]) .canvas { transition: transform 200ms cubic-bezier(.3,.7,.4,1); }
    /* transition shorthand replaces rather than merges — repeat the base
       .overlay opacity/transform/filter transitions so visibility changes
       during the 200ms toggle window still fade instead of popping. */
    :host([data-rail-anim]) .overlay {
      transition: margin-left 200ms cubic-bezier(.3,.7,.4,1),
                  opacity 260ms ease,
                  transform 260ms cubic-bezier(.2,.8,.2,1),
                  filter 260ms ease;
    }
    :host([data-rail-anim]) .tapzones { transition: left 200ms cubic-bezier(.3,.7,.4,1); }

    .thumb {
      position: relative;
      display: flex;
      align-items: flex-start;
      gap: 8px;
      cursor: pointer;
      user-select: none;
    }
    .thumb .num {
      width: 16px;
      flex-shrink: 0;
      font-size: 11px;
      font-weight: 500;
      text-align: right;
      color: rgba(255,255,255,0.55);
      padding-top: 2px;
      font-variant-numeric: tabular-nums;
    }
    .thumb .frame {
      position: relative;
      flex: 1;
      min-width: 0;
      aspect-ratio: var(--deck-aspect);
      background: #fff;
      border-radius: 4px;
      outline: 2px solid transparent;
      outline-offset: 0;
      overflow: hidden;
      transition: outline-color 120ms ease;
    }
    .thumb:hover .frame { outline-color: rgba(255,255,255,0.25); }
    .thumb { outline: none; }
    .thumb:focus-visible .frame { outline-color: rgba(255,255,255,0.5); }
    .thumb[data-current] .num { color: #fff; }
    .thumb[data-current] .frame { outline-color: #D97757; }
    .thumb[data-dragging] { opacity: 0.35; }
    .thumb::before {
      content: '';
      position: absolute;
      left: 24px;
      right: 0;
      height: 3px;
      border-radius: 2px;
      background: #D97757;
      opacity: 0;
      pointer-events: none;
    }
    .thumb[data-drop="before"]::before { top: -8px; opacity: 1; }
    .thumb[data-drop="after"]::before { bottom: -8px; opacity: 1; }
    .thumb[data-skip] .frame { opacity: 0.35; }
    .thumb[data-skip] .frame::after {
      content: 'Skipped';
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(0,0,0,0.45);
      color: #fff;
      font-size: 10px;
      font-weight: 500;
      letter-spacing: 0.04em;
    }

    .ctxmenu {
      position: fixed;
      min-width: 150px;
      padding: 4px;
      background: #242424;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 7px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.45);
      z-index: 2147483100;
      display: none;
      font-size: 12px;
    }
    .ctxmenu[data-open] { display: block; }
    .ctxmenu button {
      display: block;
      width: 100%;
      appearance: none;
      border: 0;
      background: transparent;
      color: #e8e8e8;
      font: inherit;
      text-align: left;
      padding: 6px 10px;
      border-radius: 4px;
      cursor: pointer;
    }
    .ctxmenu button:hover:not(:disabled) { background: rgba(255,255,255,0.08); }
    .ctxmenu button:disabled { opacity: 0.35; cursor: default; }
    .ctxmenu hr {
      border: 0;
      border-top: 1px solid rgba(255,255,255,0.1);
      margin: 4px 2px;
    }

    .rail-resize {
      position: fixed;
      left: calc(var(--deck-rail-w, 188px) - 3px);
      top: 0;
      bottom: 0;
      width: 6px;
      cursor: col-resize;
      z-index: 2147482600;
      touch-action: none;
    }
    .rail-resize:hover,
    .rail-resize[data-dragging] { background: rgba(255,255,255,0.12); }
    :host([no-rail]) .rail-resize,
    :host([noscale]) .rail-resize,
    .rail[data-presenting] + .rail-resize,
    .rail[data-user-hidden] + .rail-resize { display: none; }

    /* Delete-confirm popup — matches the SPA's ConfirmDialog layout
       (title + message body, depressed footer with Cancel / Delete). */
    .confirm-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.45);
      z-index: 2147483200;
      display: none;
      align-items: center;
      justify-content: center;
    }
    .confirm-backdrop[data-open] { display: flex; }
    .confirm {
      width: 320px;
      max-width: calc(100vw - 32px);
      background: #2a2a2a;
      color: #e8e8e8;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 12px;
      box-shadow: 0 12px 32px rgba(0,0,0,0.5);
      overflow: hidden;
      font-family: inherit;
      animation: deck-confirm-in 0.18s ease;
    }
    @keyframes deck-confirm-in {
      from { opacity: 0; transform: scale(0.96); }
      to { opacity: 1; transform: scale(1); }
    }
    .confirm .body { padding: 20px 20px 16px; }
    .confirm .title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
    .confirm .msg { font-size: 13px; line-height: 1.5; color: rgba(255,255,255,0.65); }
    .confirm .footer {
      padding: 14px 20px;
      background: #1f1f1f;
      border-top: 1px solid rgba(255,255,255,0.08);
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }
    .confirm button {
      appearance: none;
      font: inherit;
      font-size: 13px;
      font-weight: 500;
      padding: 8px 16px;
      border-radius: 8px;
      cursor: pointer;
    }
    .confirm .cancel {
      background: transparent;
      border: 0;
      color: rgba(255,255,255,0.8);
    }
    .confirm .cancel:hover { background: rgba(255,255,255,0.08); }
    .confirm .danger {
      background: #c96442;
      border: 1px solid rgba(0,0,0,0.15);
      color: #fff;
      box-shadow: 0 1px 3px rgba(166,50,68,0.3), 0 2px 6px rgba(166,50,68,0.18);
    }
    .confirm .danger:hover { background: #b5563a; }

    /* ── Print: one page per slide, no chrome ────────────────────────────
       The screen layout stacks every slide at inset:0 inside a scaled
       canvas; for print we want them in document flow at the authored
       design size so the browser paginates one slide per sheet. The
       @page size is set from the width/height attributes via the inline
       <style id="deck-stage-print-page"> that connectedCallback injects
       into <head> (the @page at-rule has no effect inside shadow DOM). */
    @media print {
      :host {
        position: static;
        inset: auto;
        background: none;
        overflow: visible;
        color: inherit;
      }
      .stage { position: static; display: block; }
      .canvas {
        transform: none !important;
        width: auto !important;
        height: auto !important;
        background: none;
        will-change: auto;
      }
      ::slotted(*) {
        position: relative !important;
        inset: auto !important;
        width: var(--deck-design-w) !important;
        height: var(--deck-design-h) !important;
        box-sizing: border-box !important;
        opacity: 1 !important;
        visibility: visible !important;
        pointer-events: auto;
        break-after: page;
        page-break-after: always;
        break-inside: avoid;
        overflow: hidden;
      }
      /* :last-child alone isn't enough once data-deck-skip hides the
         trailing slide(s) — the last *visible* slide still carries
         break-after:page and prints a blank sheet. _markLastVisible()
         maintains data-deck-last-visible on the last non-skipped slide. */
      ::slotted(*:last-child),
      ::slotted([data-deck-last-visible]) {
        break-after: auto;
        page-break-after: auto;
      }
      ::slotted([data-deck-skip]) { display: none !important; }
      .overlay, .tapzones, .rail, .rail-resize, .ctxmenu, .confirm-backdrop { display: none !important; }
    }
  `;
  class DeckStage extends HTMLElement {
    static get observedAttributes() {
      return ['width', 'height', 'noscale', 'no-rail'];
    }
    constructor() {
      super();
      this._root = this.attachShadow({
        mode: 'open'
      });
      this._index = 0;
      this._slides = [];
      this._notes = [];
      this._hideTimer = null;
      this._mouseIdleTimer = null;
      this._menuIndex = -1;
      this._onKey = this._onKey.bind(this);
      this._onResize = this._onResize.bind(this);
      this._onSlotChange = this._onSlotChange.bind(this);
      this._onMouseMove = this._onMouseMove.bind(this);
      this._onTapBack = this._onTapBack.bind(this);
      this._onTapForward = this._onTapForward.bind(this);
      this._onMessage = this._onMessage.bind(this);
      // Capture-phase close so a click anywhere dismisses the menu, but
      // ignore clicks that land inside the menu itself — otherwise the
      // capture handler runs before the menu's own (bubble) handler and
      // clears _menuIndex out from under it.
      this._onDocClick = e => {
        if (this._menu && e.composedPath && e.composedPath().includes(this._menu)) return;
        this._closeMenu();
      };
    }
    get designWidth() {
      return parseInt(this.getAttribute('width'), 10) || DESIGN_W_DEFAULT;
    }
    get designHeight() {
      return parseInt(this.getAttribute('height'), 10) || DESIGN_H_DEFAULT;
    }
    connectedCallback() {
      // Presenter-view popup loads deckUrl?_snthumb=...#N for its prev/cur/
      // next thumbnails — the rail has no business rendering inside those
      // (wrong scale, and it offsets the stage so the thumb shows a gutter).
      if (/[?&]_snthumb=/.test(location.search)) this.setAttribute('no-rail', '');
      this._render();
      this._loadNotes();
      this._syncPrintPageRule();
      window.addEventListener('keydown', this._onKey);
      window.addEventListener('resize', this._onResize);
      window.addEventListener('mousemove', this._onMouseMove, {
        passive: true
      });
      window.addEventListener('message', this._onMessage);
      window.addEventListener('click', this._onDocClick, true);
      // Initial collection + layout happens via slotchange, which fires on mount.
      this._enableRail();
      // Hold the stage hidden until webfonts are ready so the first visible
      // paint has the deck's real typography — the :not(:defined) guard in
      // the page HTML only covers custom-element upgrade, not font load.
      // Capped so a 404'd font URL can't blank the deck indefinitely.
      this.setAttribute('data-fonts-pending', '');
      const reveal = () => this.removeAttribute('data-fonts-pending');
      // rAF first: fonts.ready is a pre-resolved promise until layout has
      // resolved the slotted text's font-family and pushed a FontFace into
      // 'loading'. Reading it here in connectedCallback (parse-time) would
      // settle the race in a microtask before any font fetch starts.
      requestAnimationFrame(() => {
        Promise.race([document.fonts ? document.fonts.ready : Promise.resolve(), new Promise(r => setTimeout(r, 2000))]).then(reveal, reveal);
      });
    }
    _enableRail() {
      // Idempotent — older host builds still post __omelette_rail_enabled.
      // no-rail guard keeps the observers/stylesheet walk off the cheap path
      // for presenter-popup thumbnail iframes (up to 9 per view).
      if (this._railEnabled || this.hasAttribute('no-rail')) return;
      this._railEnabled = true;
      // Per-viewer preference — restored alongside rail width. Default on;
      // only a stored '0' (from the TweaksPanel toggle) hides it.
      this._railVisible = true;
      try {
        if (localStorage.getItem('deck-stage.railVisible') === '0') this._railVisible = false;
      } catch (e) {}
      // Live thumbnail updates: watch the light-DOM slides for content
      // edits and re-clone just the affected thumb(s), debounced. Ignore
      // the data-deck-* / data-screen-label / data-om-validate attributes
      // this component itself writes so nav and skip don't trigger
      // spurious refreshes.
      const OWN_ATTRS = /^data-(deck-|screen-label$|om-validate$)/;
      this._liveDirty = new Set();
      this._liveObserver = new MutationObserver(records => {
        for (const r of records) {
          if (r.type === 'attributes' && OWN_ATTRS.test(r.attributeName || '')) continue;
          let n = r.target;
          while (n && n.parentElement !== this) n = n.parentElement;
          if (n && this._slideSet && this._slideSet.has(n)) this._liveDirty.add(n);
        }
        if (this._liveDirty.size && !this._liveTimer) {
          this._liveTimer = setTimeout(() => {
            this._liveTimer = null;
            this._liveDirty.forEach(s => this._refreshThumb(s));
            this._liveDirty.clear();
          }, 200);
        }
      });
      this._liveObserver.observe(this, {
        subtree: true,
        childList: true,
        characterData: true,
        attributes: true
      });
      // Lazy thumbnail materialization — clone the slide only when its
      // frame scrolls into (or near) the rail viewport. rootMargin gives
      // ~4 thumbs of pre-load so fast scrolling doesn't flash blanks.
      this._railObserver = new IntersectionObserver(entries => {
        entries.forEach(e => {
          if (e.isIntersecting && e.target.__deckThumb) {
            this._materialize(e.target.__deckThumb);
          }
        });
      }, {
        root: this._rail,
        rootMargin: '400px 0px'
      });
      // Tweaks typically change CSS vars / attrs OUTSIDE <deck-stage>
      // (on <html>, <body>, a wrapper div, or a <style> tag), which
      // _liveObserver can't see. Re-snapshot author CSS (constructable
      // sheet is shared by reference, so one replaceSync updates every
      // thumb shadow root) and re-sync each thumb host's attrs + custom
      // properties. In-slide DOM mutations are _liveObserver's job.
      // Debounced so slider drags don't thrash.
      this._onTweakChange = () => {
        clearTimeout(this._tweakTimer);
        this._tweakTimer = setTimeout(() => {
          this._snapshotAuthorCss();
          // One getComputedStyle for the whole batch — each
          // getPropertyValue read below reuses the same computed style
          // as long as nothing invalidates layout between thumbs.
          const cs = getComputedStyle(this);
          (this._thumbs || []).forEach(t => {
            if (t.host) this._syncThumbHostAttrs(t.host, cs);
          });
        }, 120);
      };
      window.addEventListener('tweakchange', this._onTweakChange);
      this._snapshotAuthorCss();
      // Build the rail now that it's enabled — slotchange already fired,
      // so _renderRail's early-return skipped the initial build.
      this._syncRailHidden();
      this._renderRail();
      this._fit();
    }

    /** Snapshot document stylesheets into a constructable sheet that each
     *  thumbnail's nested shadow root adopts — so author CSS styles the
     *  cloned slide content without touching this component's chrome.
     *  Cross-origin sheets throw on .cssRules — skip them. Re-callable:
     *  the existing constructable sheet is reused via replaceSync so every
     *  already-adopted shadow root picks up the fresh CSS without re-adopt. */
    _snapshotAuthorCss() {
      // :root in an adopted sheet inside a shadow root matches nothing
      // (only the document root qualifies), so author rules like
      // `:root[data-voice="modern"] .serif` never reach the clones.
      // Rewrite :root → :host and mirror <html>'s data-*/class/lang onto
      // each thumb host (see _syncThumbHostAttrs) so the same selectors
      // match inside the thumbnail's shadow tree.
      const authorCss = Array.from(document.styleSheets).map(sh => {
        try {
          return Array.from(sh.cssRules).map(r => r.cssText).join('\n');
        } catch (e) {
          return '';
        }
      }).join('\n')
      // The shadow host is featureless outside the functional :host(...)
      // form, so any compound on :root — [attr], .class, #id, :pseudo —
      // must become :host(<compound>) not :host<compound>. Same for the
      // html type selector (Tailwind class-strategy dark mode emits
      // html.dark; Pico uses html[data-theme]), which has nothing to
      // match inside the thumb's shadow tree.
      .replace(/:root((?:\[[^\]]*\]|[.#][-\w]+|:[-\w]+(?:\([^)]*\))?)+)/g, ':host($1)').replace(/:root\b/g, ':host').replace(/(^|[\s,>~+(}])html((?:\[[^\]]*\]|[.#][-\w]+|:[-\w]+(?:\([^)]*\))?)+)(?![-\w])/g, '$1:host($2)').replace(/(^|[\s,>~+(}])html(?![-\w])/g, '$1:host');
      // Every custom property the author references. _syncThumbHostAttrs
      // mirrors each one's *computed* value at <deck-stage> onto the
      // thumb host so the live value wins over the :host default above
      // regardless of which ancestor the tweak wrote to (<html>, <body>,
      // a wrapper div, or the deck-stage element itself all inherit
      // down to getComputedStyle(this)).
      this._authorVars = new Set(authorCss.match(/--[\w-]+/g) || []);
      try {
        if (!this._adoptedSheet) this._adoptedSheet = new CSSStyleSheet();
        this._adoptedSheet.replaceSync(authorCss);
      } catch (e) {
        this._adoptedSheet = null;
        this._authorCss = authorCss;
      }
    }
    _syncThumbHostAttrs(host, cs) {
      const de = document.documentElement;
      // setAttribute overwrites but can't delete — an attr removed from
      // <html> (toggleAttribute off, classList emptied) would linger on
      // the host and :host([data-*]) / :host(.foo) rules would keep
      // matching. Remove stale mirrored attrs first; iterate backward
      // because removeAttribute mutates the live NamedNodeMap.
      for (let i = host.attributes.length - 1; i >= 0; i--) {
        const n = host.attributes[i].name;
        if ((n.startsWith('data-') || n === 'class' || n === 'lang') && !de.hasAttribute(n)) {
          host.removeAttribute(n);
        }
      }
      for (const a of de.attributes) {
        if (a.name.startsWith('data-') || a.name === 'class' || a.name === 'lang') {
          host.setAttribute(a.name, a.value);
        }
      }
      // The :root→:host rewrite in _snapshotAuthorCss pins each custom
      // property to its stylesheet default on the thumb host, shadowing
      // the live value that would otherwise inherit. Tweaks can write the
      // live value on any ancestor — <html>, <body>, a wrapper div, the
      // deck-stage element — so read it as the *computed* value at
      // <deck-stage> (which sees the whole inheritance chain) rather than
      // trying to guess which element the author wrote to. Inline on the
      // host beats the :host{} rule. remove-stale covers vars dropped
      // from the stylesheet between snapshots.
      const vars = this._authorVars || new Set();
      for (let i = host.style.length - 1; i >= 0; i--) {
        const p = host.style[i];
        if (p.startsWith('--') && !vars.has(p)) host.style.removeProperty(p);
      }
      const live = cs || getComputedStyle(this);
      vars.forEach(p => {
        const v = live.getPropertyValue(p);
        if (v) host.style.setProperty(p, v.trim());else host.style.removeProperty(p);
      });
    }
    disconnectedCallback() {
      window.removeEventListener('keydown', this._onKey);
      window.removeEventListener('resize', this._onResize);
      window.removeEventListener('mousemove', this._onMouseMove);
      window.removeEventListener('message', this._onMessage);
      window.removeEventListener('click', this._onDocClick, true);
      if (this._hideTimer) clearTimeout(this._hideTimer);
      if (this._mouseIdleTimer) clearTimeout(this._mouseIdleTimer);
      if (this._liveTimer) clearTimeout(this._liveTimer);
      if (this._tweakTimer) clearTimeout(this._tweakTimer);
      if (this._railAnimTimer) clearTimeout(this._railAnimTimer);
      if (this._scaleRaf) cancelAnimationFrame(this._scaleRaf);
      if (this._liveObserver) this._liveObserver.disconnect();
      if (this._railObserver) this._railObserver.disconnect();
      if (this._onTweakChange) window.removeEventListener('tweakchange', this._onTweakChange);
    }
    attributeChangedCallback() {
      if (this._canvas) {
        this._canvas.style.width = this.designWidth + 'px';
        this._canvas.style.height = this.designHeight + 'px';
        this._canvas.style.setProperty('--deck-design-w', this.designWidth + 'px');
        this._canvas.style.setProperty('--deck-design-h', this.designHeight + 'px');
        if (this._rail) {
          this._rail.style.setProperty('--deck-aspect', this.designWidth + '/' + this.designHeight);
        }
        this._fit();
        this._scaleThumbs();
        this._syncPrintPageRule();
      }
    }
    _render() {
      const style = document.createElement('style');
      style.textContent = stylesheet;
      const stage = document.createElement('div');
      stage.className = 'stage';
      const canvas = document.createElement('div');
      canvas.className = 'canvas';
      canvas.style.width = this.designWidth + 'px';
      canvas.style.height = this.designHeight + 'px';
      canvas.style.setProperty('--deck-design-w', this.designWidth + 'px');
      canvas.style.setProperty('--deck-design-h', this.designHeight + 'px');
      const slot = document.createElement('slot');
      slot.addEventListener('slotchange', this._onSlotChange);
      canvas.appendChild(slot);
      stage.appendChild(canvas);

      // Tap zones (mobile): left third = back, right third = forward.
      const tapzones = document.createElement('div');
      tapzones.className = 'tapzones export-hidden';
      tapzones.setAttribute('aria-hidden', 'true');
      tapzones.setAttribute('data-noncommentable', '');
      const tzBack = document.createElement('div');
      tzBack.className = 'tapzone tapzone--back';
      const tzMid = document.createElement('div');
      tzMid.className = 'tapzone tapzone--mid';
      tzMid.style.pointerEvents = 'none';
      const tzFwd = document.createElement('div');
      tzFwd.className = 'tapzone tapzone--fwd';
      tzBack.addEventListener('click', this._onTapBack);
      tzFwd.addEventListener('click', this._onTapForward);
      tapzones.append(tzBack, tzMid, tzFwd);

      // Overlay: compact, solid black, with clickable controls.
      const overlay = document.createElement('div');
      overlay.className = 'overlay export-hidden';
      overlay.setAttribute('role', 'toolbar');
      overlay.setAttribute('aria-label', 'Deck controls');
      overlay.setAttribute('data-noncommentable', '');
      overlay.innerHTML = `
        <button class="btn prev" type="button" aria-label="Previous slide" title="Previous (←)">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 3L5 8l5 5"/></svg>
        </button>
        <span class="count" aria-live="polite"><span class="current">1</span><span class="sep">/</span><span class="total">1</span></span>
        <button class="btn next" type="button" aria-label="Next slide" title="Next (→)">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3l5 5-5 5"/></svg>
        </button>
        <span class="divider"></span>
        <button class="btn reset" type="button" aria-label="Reset to first slide" title="Reset (R)">Reset<span class="kbd">R</span></button>
      `;
      overlay.querySelector('.prev').addEventListener('click', () => this._advance(-1, 'click'));
      overlay.querySelector('.next').addEventListener('click', () => this._advance(1, 'click'));
      overlay.querySelector('.reset').addEventListener('click', () => this._go(0, 'click'));

      // Thumbnail rail + context menu. Thumbnails are populated in
      // _renderRail() after _collectSlides().
      const rail = document.createElement('div');
      rail.className = 'rail export-hidden';
      rail.setAttribute('data-noncommentable', '');
      rail.style.setProperty('--deck-aspect', this.designWidth + '/' + this.designHeight);
      // Edge auto-scroll while dragging a thumb near the rail's top/bottom
      // so off-screen drop targets are reachable. Native dragover fires
      // continuously while the pointer is stationary, so a per-event nudge
      // (ramped by edge proximity) is enough — no rAF loop needed.
      rail.addEventListener('dragover', e => {
        if (this._dragFrom == null) return;
        const r = rail.getBoundingClientRect();
        const EDGE = 40;
        const dt = e.clientY - r.top;
        const db = r.bottom - e.clientY;
        if (dt < EDGE) rail.scrollTop -= Math.ceil((EDGE - dt) / 3);else if (db < EDGE) rail.scrollTop += Math.ceil((EDGE - db) / 3);
      });
      const menu = document.createElement('div');
      menu.className = 'ctxmenu export-hidden';
      menu.setAttribute('data-noncommentable', '');
      menu.innerHTML = `
        <button type="button" data-act="skip">Skip slide</button>
        <button type="button" data-act="up">Move up</button>
        <button type="button" data-act="down">Move down</button>
        <hr>
        <button type="button" data-act="delete">Delete slide</button>
      `;
      menu.addEventListener('click', e => {
        const act = e.target && e.target.getAttribute && e.target.getAttribute('data-act');
        if (!act) return;
        const i = this._menuIndex;
        this._closeMenu();
        if (act === 'skip') this._toggleSkip(i);else if (act === 'up') this._moveSlide(i, i - 1);else if (act === 'down') this._moveSlide(i, i + 1);else if (act === 'delete') this._openConfirm(i);
      });
      menu.addEventListener('contextmenu', e => e.preventDefault());

      // Rail resize handle — drag to set --deck-rail-w, persisted to
      // localStorage so the width survives reloads.
      const resize = document.createElement('div');
      resize.className = 'rail-resize export-hidden';
      resize.setAttribute('data-noncommentable', '');
      resize.addEventListener('pointerdown', e => {
        e.preventDefault();
        resize.setPointerCapture(e.pointerId);
        resize.setAttribute('data-dragging', '');
        const move = ev => this._setRailWidth(ev.clientX);
        const up = () => {
          resize.removeEventListener('pointermove', move);
          resize.removeEventListener('pointerup', up);
          resize.removeEventListener('pointercancel', up);
          resize.removeAttribute('data-dragging');
          try {
            localStorage.setItem('deck-stage.railWidth', String(this._railPx));
          } catch (err) {}
        };
        resize.addEventListener('pointermove', move);
        resize.addEventListener('pointerup', up);
        resize.addEventListener('pointercancel', up);
      });

      // Delete-confirm dialog — mirrors the SPA's ConfirmDialog layout.
      const confirm = document.createElement('div');
      confirm.className = 'confirm-backdrop export-hidden';
      confirm.setAttribute('data-noncommentable', '');
      confirm.innerHTML = `
        <div class="confirm" role="dialog" aria-modal="true">
          <div class="body">
            <div class="title">Delete slide?</div>
            <div class="msg">This slide will be removed from the deck.</div>
          </div>
          <div class="footer">
            <button type="button" class="cancel">Cancel</button>
            <button type="button" class="danger">Delete</button>
          </div>
        </div>
      `;
      confirm.addEventListener('click', e => {
        if (e.target === confirm) this._closeConfirm();
      });
      confirm.querySelector('.cancel').addEventListener('click', () => this._closeConfirm());
      confirm.querySelector('.danger').addEventListener('click', () => {
        const i = this._confirmIndex;
        this._closeConfirm();
        this._deleteSlide(i);
      });
      this._root.append(style, rail, resize, stage, tapzones, overlay, menu, confirm);
      this._canvas = canvas;
      this._slot = slot;
      this._overlay = overlay;
      this._tapzones = tapzones;
      this._rail = rail;
      this._resize = resize;
      this._menu = menu;
      this._confirm = confirm;
      this._countEl = overlay.querySelector('.current');
      this._totalEl = overlay.querySelector('.total');

      // Restore persisted rail width.
      let rw = 188;
      try {
        const s = localStorage.getItem('deck-stage.railWidth');
        if (s) rw = parseInt(s, 10) || rw;
      } catch (err) {}
      this._setRailWidth(rw);
      this._syncRailHidden();
    }
    _setRailWidth(px) {
      const w = Math.max(120, Math.min(360, Math.round(px)));
      this._railPx = w;
      this.style.setProperty('--deck-rail-w', w + 'px');
      this._fit();
      // _scaleThumbs forces a sync layout (frame.offsetWidth) then writes
      // N transforms. During a resize drag this runs per-pointermove;
      // coalesce to one per frame.
      if (!this._scaleRaf) {
        this._scaleRaf = requestAnimationFrame(() => {
          this._scaleRaf = null;
          this._scaleThumbs();
        });
      }
    }

    /** @page must live in the document stylesheet — it's a no-op inside
     *  shadow DOM. Inject/update a single <head> style tag so the print
     *  sheet matches the design size and Save-as-PDF yields one slide per
     *  page with no margins. */
    _syncPrintPageRule() {
      const id = 'deck-stage-print-page';
      let tag = document.getElementById(id);
      if (!tag) {
        tag = document.createElement('style');
        tag.id = id;
        document.head.appendChild(tag);
      }
      tag.textContent = '@page { size: ' + this.designWidth + 'px ' + this.designHeight + 'px; margin: 0; } ' + '@media print { html, body { margin: 0 !important; padding: 0 !important; background: none !important; overflow: visible !important; height: auto !important; } ' + '* { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }';
    }
    _onSlotChange() {
      // Rail mutations (delete/move) already reconcile synchronously and
      // emit slidechange with reason 'api'; skip the async slotchange that
      // would otherwise re-broadcast with reason 'init'.
      if (this._squelchSlotChange) {
        this._squelchSlotChange = false;
        return;
      }
      this._collectSlides();
      this._restoreIndex();
      this._applyIndex({
        showOverlay: false,
        broadcast: true,
        reason: 'init'
      });
      this._fit();
    }
    _collectSlides() {
      const assigned = this._slot.assignedElements({
        flatten: true
      });
      this._slides = assigned.filter(el => {
        // Skip template/style/script nodes even if someone slots them.
        const tag = el.tagName;
        return tag !== 'TEMPLATE' && tag !== 'SCRIPT' && tag !== 'STYLE';
      });
      this._slideSet = new Set(this._slides);
      this._slides.forEach((slide, i) => {
        const n = i + 1;
        slide.setAttribute('data-screen-label', `${pad2(n)} ${getSlideLabel(slide)}`);

        // Validation attribute for comment flow / auto-checks.
        if (!slide.hasAttribute('data-om-validate')) {
          slide.setAttribute('data-om-validate', VALIDATE_ATTR);
        }
        slide.setAttribute('data-deck-slide', String(i));
      });
      if (this._totalEl) this._totalEl.textContent = String(this._slides.length || 1);
      if (this._index >= this._slides.length) this._index = Math.max(0, this._slides.length - 1);
      this._markLastVisible();
      this._renderRail();
    }

    /** Tag the last non-skipped slide so print CSS can drop its
     *  break-after (see the @media print comment above — :last-child
     *  alone matches a hidden skipped slide). */
    _markLastVisible() {
      let last = null;
      this._slides.forEach(s => {
        s.removeAttribute('data-deck-last-visible');
        if (!s.hasAttribute('data-deck-skip')) last = s;
      });
      if (last) last.setAttribute('data-deck-last-visible', '');
    }
    _loadNotes() {
      const tag = document.getElementById('speaker-notes');
      if (!tag) {
        this._notes = [];
        return;
      }
      try {
        const parsed = JSON.parse(tag.textContent || '[]');
        if (Array.isArray(parsed)) this._notes = parsed;
      } catch (e) {
        console.warn('[deck-stage] Failed to parse #speaker-notes JSON:', e);
        this._notes = [];
      }
    }
    _restoreIndex() {
      // The host's ?slide= param is delivered as a #<int> hash (1-indexed) on
      // the iframe src. No hash → slide 1; the deck itself keeps no position
      // state across loads.
      const h = (location.hash || '').match(/^#(\d+)$/);
      if (h) {
        const n = parseInt(h[1], 10) - 1;
        if (n >= 0 && n < this._slides.length) this._index = n;
      }
    }
    _applyIndex({
      showOverlay = true,
      broadcast = true,
      reason = 'init'
    } = {}) {
      if (!this._slides.length) return;
      const prev = this._prevIndex == null ? -1 : this._prevIndex;
      const curr = this._index;
      // Keep the iframe's own hash in sync so an in-iframe location.reload()
      // (reload banner path in viewer-handle.ts) lands on the current slide,
      // not the stale deep-link hash from initial load.
      try {
        history.replaceState(null, '', '#' + (curr + 1));
      } catch (e) {}
      this._slides.forEach((s, i) => {
        if (i === curr) s.setAttribute('data-deck-active', '');else s.removeAttribute('data-deck-active');
      });
      if (this._countEl) this._countEl.textContent = String(curr + 1);
      // Follow-scroll on every navigation (init deep-link, keyboard, click,
      // tap, external goTo) — the only time we *don't* want the rail to
      // track current is after a rail-internal mutation, where _renderRail
      // has already restored the user's scroll position and yanking back to
      // current would undo it.
      this._syncRail(reason !== 'mutation');
      if (broadcast) {
        // (1) Legacy: host-window postMessage for speaker-notes renderers.
        try {
          window.postMessage({
            slideIndexChanged: curr,
            deckTotal: this._slides.length,
            deckSkipped: this._skippedIndices()
          }, '*');
        } catch (e) {}

        // (2) In-page CustomEvent on the <deck-stage> element itself.
        //     Bubbles and composes out of shadow DOM so slide code can listen:
        //       document.querySelector('deck-stage').addEventListener('slidechange', e => {
        //         e.detail.index, e.detail.previousIndex, e.detail.total, e.detail.slide, e.detail.reason
        //       });
        const detail = {
          index: curr,
          previousIndex: prev,
          total: this._slides.length,
          slide: this._slides[curr] || null,
          previousSlide: prev >= 0 ? this._slides[prev] || null : null,
          reason: reason // 'init' | 'keyboard' | 'click' | 'tap' | 'api'
        };
        this.dispatchEvent(new CustomEvent('slidechange', {
          detail,
          bubbles: true,
          composed: true
        }));
      }
      this._prevIndex = curr;
      if (showOverlay) this._flashOverlay();
    }
    _flashOverlay() {
      // Host posts __omelette_presenting while in fullscreen/tab presentation
      // mode — suppress the nav footer entirely (both hover and slide-change
      // flash) so the audience sees clean slides.
      if (!this._overlay || this._presenting) return;
      this._overlay.setAttribute('data-visible', '');
      if (this._hideTimer) clearTimeout(this._hideTimer);
      this._hideTimer = setTimeout(() => {
        this._overlay.removeAttribute('data-visible');
      }, OVERLAY_HIDE_MS);
    }
    _railWidth() {
      // State-based, no offsetWidth: the first _fit() can run before the
      // rail has had layout on some load paths, and a 0 there paints the
      // slide full-width for one frame before the post-slotchange _fit()
      // corrects it.
      if (!this._railEnabled || !this._railVisible || this.hasAttribute('no-rail') || this.hasAttribute('noscale') || this._presenting || this._previewMode) return 0;
      return this._railPx || 0;
    }
    _fit() {
      if (!this._canvas) return;
      const stage = this._canvas.parentElement;
      // PPTX export sets noscale so the DOM capture sees authored-size
      // geometry — the scaled canvas is in shadow DOM, so the exporter's
      // resetTransformSelector can't reach .canvas.style.transform directly.
      if (this.hasAttribute('noscale')) {
        this._canvas.style.transform = 'none';
        if (stage) stage.style.left = '0';
        if (this._overlay) this._overlay.style.marginLeft = '0';
        if (this._tapzones) this._tapzones.style.left = '0';
        return;
      }
      const rw = this._railWidth();
      if (stage) stage.style.left = rw + 'px';
      // Overlay is centred on the viewport via left:50% + translate(-50%);
      // marginLeft shifts the centre by rw/2 so it lands in the middle of
      // the [rw, innerWidth] stage region. Tapzones just inset from rw.
      if (this._overlay) this._overlay.style.marginLeft = rw / 2 + 'px';
      if (this._tapzones) this._tapzones.style.left = rw + 'px';
      const vw = window.innerWidth - rw;
      const vh = window.innerHeight;
      const s = Math.min(vw / this.designWidth, vh / this.designHeight);
      this._canvas.style.transform = `scale(${s})`;
    }
    _onResize() {
      this._fit();
    }
    _onMouseMove() {
      // Keep overlay visible while mouse moves; hide after idle.
      this._flashOverlay();
    }
    _onMessage(e) {
      const d = e.data;
      if (d && typeof d.__omelette_presenting === 'boolean') {
        this._presenting = d.__omelette_presenting;
        if (this._presenting && this._overlay) {
          this._overlay.removeAttribute('data-visible');
          if (this._hideTimer) clearTimeout(this._hideTimer);
        }
        this._syncRailHidden();
        this._closeMenu();
        this._closeConfirm();
        this._fit();
        this._scaleThumbs();
      }
      // Host's Preview segment (ViewerMode='none'): the rail's drag-reorder /
      // right-click skip-delete affordances are editing chrome, so hide it
      // while the user is just looking at the deck. Same hard-hide path as
      // presenting; independent of the user's _railVisible preference so
      // returning to Edit restores whatever they had.
      if (d && typeof d.__omelette_preview_mode === 'boolean') {
        if (d.__omelette_preview_mode === this._previewMode) return;
        this._previewMode = d.__omelette_preview_mode;
        this._syncRailHidden();
        this._closeMenu();
        this._closeConfirm();
        this._fit();
        this._scaleThumbs();
      }
      // Per-viewer show/hide, driven by the TweaksPanel's auto-injected
      // "Thumbnail rail" toggle (or any author script). Independent of
      // whether the Tweaks panel itself is open — closing the panel
      // doesn't change rail visibility. Persists alongside rail width.
      if (d && d.type === '__deck_rail_visible' && typeof d.on === 'boolean') {
        if (d.on === this._railVisible) return;
        this._railVisible = d.on;
        try {
          localStorage.setItem('deck-stage.railVisible', d.on ? '1' : '0');
        } catch (e) {}
        // Arm the transition, commit it, then flip state — otherwise the
        // browser coalesces both writes and nothing animates on show.
        this.setAttribute('data-rail-anim', '');
        void (this._rail && this._rail.offsetHeight);
        this._syncRailHidden();
        this._fit();
        this._scaleThumbs();
        clearTimeout(this._railAnimTimer);
        this._railAnimTimer = setTimeout(() => this.removeAttribute('data-rail-anim'), 220);
      }
      if (d && d.type === '__omelette_rail_enabled') this._enableRail();
    }
    _syncRailHidden() {
      if (!this._rail) return;
      // data-presenting is the hard hide (display:none) for flag-off,
      // presentation mode, and the host's Preview segment — instant, no
      // transition. data-user-hidden is the soft hide (translateX(-100%))
      // for the viewer's rail toggle, so show/hide slides under
      // :host([data-rail-anim]).
      const hard = !this._railEnabled || this._presenting || this._previewMode;
      if (hard) this._rail.setAttribute('data-presenting', '');else this._rail.removeAttribute('data-presenting');
      if (!this._railVisible) this._rail.setAttribute('data-user-hidden', '');else this._rail.removeAttribute('data-user-hidden');
      // translateX hide leaves thumbs (tabIndex=0) in the tab order —
      // inert keeps them unfocusable while the rail is off-screen.
      this._rail.inert = hard || !this._railVisible;
    }
    _onTapBack(e) {
      e.preventDefault();
      this._advance(-1, 'tap');
    }
    _onTapForward(e) {
      e.preventDefault();
      this._advance(1, 'tap');
    }
    _onKey(e) {
      // Ignore when the user is typing.
      const t = e.target;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      // Confirm dialog swallows nav keys while open; Escape cancels. Enter
      // is left to the focused button's native activation so Tab→Cancel
      // →Enter activates Cancel, not the window-level confirm path.
      if (this._confirm && this._confirm.hasAttribute('data-open')) {
        if (e.key === 'Escape') {
          this._closeConfirm();
          e.preventDefault();
        }
        return;
      }
      if (e.key === 'Escape' && this._menu && this._menu.hasAttribute('data-open')) {
        this._closeMenu();
        e.preventDefault();
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const key = e.key;
      let handled = true;
      if (key === 'ArrowRight' || key === 'PageDown' || key === ' ' || key === 'Spacebar') {
        this._advance(1, 'keyboard');
      } else if (key === 'ArrowLeft' || key === 'PageUp') {
        this._advance(-1, 'keyboard');
      } else if (key === 'Home') {
        this._go(0, 'keyboard');
      } else if (key === 'End') {
        this._go(this._slides.length - 1, 'keyboard');
      } else if (key === 'r' || key === 'R') {
        this._go(0, 'keyboard');
      } else if (/^[0-9]$/.test(key)) {
        // 1..9 jump to that slide; 0 jumps to 10.
        const n = key === '0' ? 9 : parseInt(key, 10) - 1;
        if (n < this._slides.length) this._go(n, 'keyboard');
      } else {
        handled = false;
      }
      if (handled) {
        e.preventDefault();
        this._flashOverlay();
      }
    }
    _go(i, reason = 'api') {
      if (!this._slides.length) return;
      const clamped = Math.max(0, Math.min(this._slides.length - 1, i));
      if (clamped === this._index) {
        this._flashOverlay();
        return;
      }
      this._index = clamped;
      this._applyIndex({
        showOverlay: true,
        broadcast: true,
        reason
      });
    }

    /** Step forward/back skipping any slide marked data-deck-skip. Falls
     *  back to _go's clamp-at-ends behaviour (flash overlay) when there's
     *  nothing further in that direction. */
    _advance(dir, reason) {
      if (!this._slides.length) return;
      let i = this._index + dir;
      while (i >= 0 && i < this._slides.length && this._slides[i].hasAttribute('data-deck-skip')) {
        i += dir;
      }
      if (i < 0 || i >= this._slides.length) {
        this._flashOverlay();
        return;
      }
      this._go(i, reason);
    }

    // ── Thumbnail rail ────────────────────────────────────────────────────
    //
    // Thumbs are keyed by slide element and reused across _renderRail()
    // calls, so a reorder/delete is an O(changed) DOM shuffle instead of an
    // O(N) teardown-and-re-clone. Each thumb starts as a lightweight shell
    // (num + empty frame); the clone is materialized lazily by an
    // IntersectionObserver when the frame scrolls into (or near) view, so
    // only visible-ish slides pay the clone + image-decode cost.

    _renderRail() {
      if (!this._rail || !this._railEnabled) {
        this._thumbs = [];
        return;
      }
      // FLIP: record each *materialized* thumb's top before the reconcile.
      // Off-screen (non-materialized) thumbs don't need the animation and
      // skipping their getBoundingClientRect saves a forced layout per
      // off-screen thumb on large decks.
      const prevTops = new Map();
      (this._thumbs || []).forEach(({
        thumb,
        slide,
        host
      }) => {
        if (host) prevTops.set(slide, thumb.getBoundingClientRect().top);
      });
      const st = this._rail.scrollTop;

      // Reconcile: reuse thumbs that already exist for a slide, create
      // shells for new slides, drop thumbs for removed slides.
      const bySlide = new Map();
      (this._thumbs || []).forEach(t => bySlide.set(t.slide, t));
      const next = [];
      this._slides.forEach(slide => {
        let t = bySlide.get(slide);
        if (t) bySlide.delete(slide);else t = this._makeThumb(slide);
        next.push(t);
      });
      // Orphans — slides removed since last render.
      bySlide.forEach(t => {
        if (this._railObserver) this._railObserver.unobserve(t.frame);
        t.thumb.remove();
      });
      // Put thumbs into document order to match _slides. insertBefore on
      // an already-correctly-placed node is a no-op, so this is cheap
      // when nothing moved.
      next.forEach((t, i) => {
        const want = t.thumb;
        const at = this._rail.children[i];
        if (at !== want) this._rail.insertBefore(want, at || null);
        t.i = i;
        t.num.textContent = String(i + 1);
        if (t.slide.hasAttribute('data-deck-skip')) t.thumb.setAttribute('data-skip', '');else t.thumb.removeAttribute('data-skip');
      });
      this._thumbs = next;
      this._rail.scrollTop = st;
      if (prevTops.size) {
        const moved = [];
        this._thumbs.forEach(({
          thumb,
          slide
        }) => {
          const old = prevTops.get(slide);
          if (old == null) return;
          const dy = old - thumb.getBoundingClientRect().top;
          if (Math.abs(dy) < 1) return;
          thumb.style.transition = 'none';
          thumb.style.transform = `translateY(${dy}px)`;
          moved.push(thumb);
        });
        if (moved.length) {
          // Commit the inverted positions before flipping the transition
          // on — otherwise the browser coalesces both style writes and
          // nothing animates.
          void this._rail.offsetHeight;
          moved.forEach(t => {
            t.style.transition = 'transform 180ms cubic-bezier(.2,.7,.3,1)';
            t.style.transform = '';
          });
          setTimeout(() => moved.forEach(t => {
            t.style.transition = '';
          }), 220);
        }
      }
      requestAnimationFrame(() => this._scaleThumbs());
      this._syncRail(false);
    }

    /** Create a lightweight thumb shell for one slide. The clone is
     *  materialized later by the IntersectionObserver. Event handlers
     *  look up the thumb's *current* index (via _thumbs.indexOf) so the
     *  same element can be reused across reorders. */
    _makeThumb(slide) {
      const thumb = document.createElement('div');
      thumb.className = 'thumb';
      thumb.tabIndex = 0;
      const num = document.createElement('div');
      num.className = 'num';
      const frame = document.createElement('div');
      frame.className = 'frame';
      thumb.append(num, frame);
      const entry = {
        thumb,
        num,
        frame,
        slide,
        clone: null,
        host: null,
        i: -1
      };
      // entry.i is refreshed on every _renderRail reconcile pass, so
      // handlers read the thumb's current position without an O(N) scan.
      const idx = () => entry.i;
      thumb.addEventListener('click', () => this._go(idx(), 'click'));
      // ↑/↓ step through the rail when a thumb has focus. _go clamps at the
      // ends and _applyIndex→_syncRail scrolls the new current thumb into
      // view; we move focus to it (preventScroll — _syncRail already
      // scrolled) so a held key walks the whole list. stopPropagation keeps
      // this out of the window-level _onKey nav handler.
      thumb.addEventListener('keydown', e => {
        if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        e.preventDefault();
        e.stopPropagation();
        this._go(idx() + (e.key === 'ArrowDown' ? 1 : -1), 'keyboard');
        const cur = this._thumbs && this._thumbs[this._index];
        if (cur) cur.thumb.focus({
          preventScroll: true
        });
      });
      thumb.addEventListener('contextmenu', e => {
        e.preventDefault();
        this._openMenu(idx(), e.clientX, e.clientY);
      });
      thumb.draggable = true;
      thumb.addEventListener('dragstart', e => {
        this._dragFrom = idx();
        thumb.setAttribute('data-dragging', '');
        e.dataTransfer.effectAllowed = 'move';
        try {
          e.dataTransfer.setData('text/plain', String(this._dragFrom));
        } catch (err) {}
      });
      thumb.addEventListener('dragend', () => {
        thumb.removeAttribute('data-dragging');
        this._clearDrop();
        this._dragFrom = null;
      });
      thumb.addEventListener('dragover', e => {
        if (this._dragFrom == null) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const r = thumb.getBoundingClientRect();
        this._setDrop(idx(), e.clientY < r.top + r.height / 2 ? 'before' : 'after');
      });
      thumb.addEventListener('drop', e => {
        if (this._dragFrom == null) return;
        e.preventDefault();
        const i = idx();
        const r = thumb.getBoundingClientRect();
        let to = e.clientY >= r.top + r.height / 2 ? i + 1 : i;
        if (this._dragFrom < to) to--;
        const from = this._dragFrom;
        this._clearDrop();
        this._dragFrom = null;
        if (to !== from) this._moveSlide(from, to);
      });
      if (this._railObserver) this._railObserver.observe(frame);
      frame.__deckThumb = entry;
      return entry;
    }

    /** Lazily build the clone for a thumb that has scrolled into view. */
    _materialize(entry) {
      if (entry.host) return;
      const dw = this.designWidth,
        dh = this.designHeight;
      let clone = entry.slide.cloneNode(true);
      clone.removeAttribute('id');
      clone.removeAttribute('data-deck-active');
      clone.querySelectorAll('[id]').forEach(el => el.removeAttribute('id'));
      // Neuter heavy media; replace <video> with its poster so the box
      // keeps a visual. <iframe>/<audio> become empty placeholders.
      clone.querySelectorAll('iframe, audio, object, embed').forEach(el => {
        el.removeAttribute('src');
        el.removeAttribute('srcdoc');
        el.removeAttribute('data');
        el.innerHTML = '';
      });
      clone.querySelectorAll('video').forEach(el => {
        if (!el.poster) {
          el.removeAttribute('src');
          el.innerHTML = '';
          return;
        }
        const img = document.createElement('img');
        img.src = el.poster;
        img.alt = '';
        img.style.cssText = el.style.cssText + ';object-fit:cover;width:100%;height:100%;';
        img.className = el.className;
        el.replaceWith(img);
      });
      // Images: defer decode and let the browser pick the smallest
      // srcset candidate for the ~140px thumb. Same-URL clones reuse the
      // slide's decoded bitmap (URL-keyed cache), so the remaining cost
      // is paint/composite — lazy+async keeps that off the main thread.
      clone.querySelectorAll('img').forEach(el => {
        el.loading = 'lazy';
        el.decoding = 'async';
        if (el.srcset) el.sizes = (this._railPx || 188) + 'px';
      });
      // Custom elements inside the slide would have their
      // connectedCallback fire when the clone is appended. Replace them
      // with inert boxes so a component-heavy deck doesn't run N copies
      // of each component's mount logic in the rail. Children are
      // preserved so layout-wrapper elements (<my-column><h2>…</h2>)
      // still show their authored content; the querySelectorAll NodeList
      // is static, so nested custom elements in the moved subtree are
      // still visited on later iterations.
      const neuter = el => {
        const box = document.createElement('div');
        box.style.cssText = (el.getAttribute('style') || '') + ';background:rgba(0,0,0,0.06);border:1px dashed rgba(0,0,0,0.15);';
        box.className = el.className;
        // Preserve theming/i18n hooks so [data-*] / :lang() / [dir]
        // descendant selectors still match the neutered root.
        for (const a of el.attributes) {
          const n = a.name;
          if (n.startsWith('data-') || n.startsWith('aria-') || n === 'lang' || n === 'dir' || n === 'role' || n === 'title') {
            box.setAttribute(n, a.value);
          }
        }
        while (el.firstChild) box.appendChild(el.firstChild);
        return box;
      };
      // querySelectorAll('*') returns descendants only — a custom-element
      // slide root (<my-slide>…</my-slide>) would slip through and upgrade
      // on append. Swap the root first.
      if (clone.tagName.includes('-')) clone = neuter(clone);
      clone.querySelectorAll('*').forEach(el => {
        if (el.tagName.includes('-')) el.replaceWith(neuter(el));
      });
      clone.style.cssText += ';position:absolute;top:0;left:0;transform-origin:0 0;' + 'pointer-events:none;width:' + dw + 'px;height:' + dh + 'px;' + 'box-sizing:border-box;overflow:hidden;visibility:visible;opacity:1;';
      const host = document.createElement('div');
      host.style.cssText = 'position:absolute;inset:0;';
      this._syncThumbHostAttrs(host);
      const sr = host.attachShadow({
        mode: 'open'
      });
      if (this._adoptedSheet) sr.adoptedStyleSheets = [this._adoptedSheet];else {
        const st = document.createElement('style');
        st.textContent = this._authorCss || '';
        sr.appendChild(st);
      }
      sr.appendChild(clone);
      entry.frame.appendChild(host);
      entry.host = host;
      entry.clone = clone;
      if (this._thumbScale) clone.style.transform = 'scale(' + this._thumbScale + ')';
      // Once materialized the IO callback is a no-op early-return —
      // unobserve so scroll doesn't keep firing it.
      if (this._railObserver) this._railObserver.unobserve(entry.frame);
    }

    /** Re-clone a single thumb (live-update path). No-op if the thumb
     *  hasn't been materialized yet — it'll pick up current content when
     *  it scrolls into view. */
    _refreshThumb(slide) {
      const entry = (this._thumbs || []).find(t => t.slide === slide);
      if (!entry || !entry.host) return;
      entry.host.remove();
      entry.host = entry.clone = null;
      this._materialize(entry);
    }
    _scaleThumbs() {
      if (!this._thumbs || !this._thumbs.length) return;
      // Every frame is the same width; if it reads 0 the rail is
      // display:none (noscale / no-rail / presenting / print) — leave the
      // clones as-is and re-run when the rail is revealed.
      const fw = this._thumbs[0].frame.offsetWidth;
      if (!fw) return;
      this._thumbScale = fw / this.designWidth;
      this._thumbs.forEach(({
        clone
      }) => {
        if (clone) clone.style.transform = 'scale(' + this._thumbScale + ')';
      });
    }
    _setDrop(i, where) {
      // dragover fires at pointer-event rate; touch only the previous
      // and new target rather than sweeping all N thumbs.
      const t = this._thumbs && this._thumbs[i];
      if (this._dropOn && this._dropOn !== t) {
        this._dropOn.thumb.removeAttribute('data-drop');
      }
      if (t) t.thumb.setAttribute('data-drop', where);
      this._dropOn = t || null;
    }
    _clearDrop() {
      if (this._dropOn) this._dropOn.thumb.removeAttribute('data-drop');
      this._dropOn = null;
    }
    _syncRail(follow) {
      if (!this._thumbs) return;
      this._thumbs.forEach(({
        thumb
      }, i) => {
        if (i === this._index) {
          thumb.setAttribute('data-current', '');
          if (follow && typeof thumb.scrollIntoView === 'function') {
            thumb.scrollIntoView({
              block: 'nearest'
            });
          }
        } else {
          thumb.removeAttribute('data-current');
        }
      });
    }
    _openMenu(i, x, y) {
      if (!this._menu) return;
      this._menuIndex = i;
      const slide = this._slides[i];
      const skip = slide && slide.hasAttribute('data-deck-skip');
      this._menu.querySelector('[data-act="skip"]').textContent = skip ? 'Unskip slide' : 'Skip slide';
      this._menu.querySelector('[data-act="up"]').disabled = i <= 0;
      this._menu.querySelector('[data-act="down"]').disabled = i >= this._slides.length - 1;
      this._menu.querySelector('[data-act="delete"]').disabled = this._slides.length <= 1;
      // Place, then clamp to viewport after it's measurable.
      this._menu.style.left = x + 'px';
      this._menu.style.top = y + 'px';
      this._menu.setAttribute('data-open', '');
      const r = this._menu.getBoundingClientRect();
      const nx = Math.min(x, window.innerWidth - r.width - 4);
      const ny = Math.min(y, window.innerHeight - r.height - 4);
      this._menu.style.left = Math.max(4, nx) + 'px';
      this._menu.style.top = Math.max(4, ny) + 'px';
    }
    _closeMenu() {
      if (this._menu) this._menu.removeAttribute('data-open');
      this._menuIndex = -1;
    }
    _openConfirm(i) {
      if (!this._confirm) return;
      this._confirmIndex = i;
      this._confirm.querySelector('.title').textContent = 'Delete slide ' + (i + 1) + '?';
      this._confirm.setAttribute('data-open', '');
      const btn = this._confirm.querySelector('.danger');
      if (btn && btn.focus) btn.focus();
    }
    _closeConfirm() {
      if (this._confirm) this._confirm.removeAttribute('data-open');
      this._confirmIndex = -1;
    }
    _emitDeckChange(detail) {
      this.dispatchEvent(new CustomEvent('deckchange', {
        detail,
        bubbles: true,
        composed: true
      }));
    }
    _deleteSlide(i) {
      const slide = this._slides[i];
      if (!slide || this._slides.length <= 1) return;
      const wasCurrent = i === this._index;
      if (i < this._index || wasCurrent && i === this._slides.length - 1) this._index--;
      this._squelchSlotChange = true;
      slide.remove();
      this._emitDeckChange({
        action: 'delete',
        from: i,
        slide
      });
      this._collectSlides();
      this._applyIndex({
        showOverlay: true,
        broadcast: true,
        reason: 'mutation'
      });
    }
    _toggleSkip(i) {
      const slide = this._slides[i];
      if (!slide) return;
      const on = !slide.hasAttribute('data-deck-skip');
      if (on) slide.setAttribute('data-deck-skip', '');else slide.removeAttribute('data-deck-skip');
      if (this._thumbs && this._thumbs[i]) {
        if (on) this._thumbs[i].thumb.setAttribute('data-skip', '');else this._thumbs[i].thumb.removeAttribute('data-skip');
      }
      this._markLastVisible();
      this._emitDeckChange({
        action: on ? 'skip' : 'unskip',
        from: i,
        slide
      });
      // Re-broadcast so the presenter popup's prev/next thumbnails re-pick
      // the nearest non-skipped slide without waiting for a nav event.
      try {
        window.postMessage({
          slideIndexChanged: this._index,
          deckTotal: this._slides.length,
          deckSkipped: this._skippedIndices()
        }, '*');
      } catch (e) {}
    }
    _skippedIndices() {
      const out = [];
      for (let i = 0; i < this._slides.length; i++) {
        if (this._slides[i].hasAttribute('data-deck-skip')) out.push(i);
      }
      return out;
    }
    _moveSlide(i, j) {
      if (j < 0 || j >= this._slides.length || j === i) return;
      const slide = this._slides[i];
      const ref = j < i ? this._slides[j] : this._slides[j].nextSibling;
      // Track the active slide across the reorder so the same content
      // stays on screen.
      const cur = this._index;
      if (cur === i) this._index = j;else if (i < cur && j >= cur) this._index = cur - 1;else if (i > cur && j <= cur) this._index = cur + 1;
      this._squelchSlotChange = true;
      this.insertBefore(slide, ref);
      this._emitDeckChange({
        action: 'move',
        from: i,
        to: j,
        slide
      });
      this._collectSlides();
      this._applyIndex({
        showOverlay: false,
        broadcast: true,
        reason: 'mutation'
      });
    }

    // Public API ------------------------------------------------------------

    /** Current slide index (0-based). */
    get index() {
      return this._index;
    }
    /** Total slide count. */
    get length() {
      return this._slides.length;
    }
    /** Programmatically navigate. */
    goTo(i) {
      this._go(i, 'api');
    }
    next() {
      this._advance(1, 'api');
    }
    prev() {
      this._advance(-1, 'api');
    }
    reset() {
      this._go(0, 'api');
    }
  }
  if (!customElements.get('deck-stage')) {
    customElements.define('deck-stage', DeckStage);
  }
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "slides/deck-stage.js", error: String((e && e.message) || e) }); }

// slides/image-slot.js
try { (() => {
/**
 * <image-slot> — user-fillable image placeholder.
 *
 * Drop this into a deck, mockup, or page wherever you want the user to
 * supply an image. You control the slot's shape and size; the user fills it
 * by dragging an image file onto it (or clicking to browse). The dropped
 * image persists across reloads via a .image-slots.state.json sidecar —
 * same read-via-fetch / write-via-window.omelette pattern as
 * design_canvas.jsx, so the filled slot shows on share links, downloaded
 * zips, and PPTX export. Outside the omelette runtime the slot is read-only.
 *
 * The host bridge only allows sidecar writes at the project root, so the
 * HTML that uses this component is assumed to live at the project root too
 * (same constraint as design_canvas.jsx).
 *
 * Attributes:
 *   id           Persistence key. REQUIRED for the drop to survive reload —
 *                every slot on the page needs a distinct id.
 *   shape        'rect' | 'rounded' | 'circle' | 'pill'   (default 'rounded')
 *                'circle' applies 50% border-radius; on a non-square slot
 *                that's an ellipse — set equal width and height for a true
 *                circle.
 *   radius       Corner radius in px for 'rounded'.       (default 12)
 *   mask         Any CSS clip-path value. Overrides `shape` — use this for
 *                hexagons, blobs, arbitrary polygons.
 *   fit          object-fit: cover | contain | fill.       (default 'cover')
 *                With cover (the default) double-clicking the filled slot
 *                enters a reframe mode: the whole image spills past the mask
 *                (translucent outside, opaque inside), drag to reposition,
 *                corner-drag to scale. The crop persists alongside the image
 *                in the sidecar. contain/fill stay static.
 *   position     object-position for fit=contain|fill.     (default '50% 50%')
 *   placeholder  Empty-state caption.                      (default 'Drop an image')
 *   src          Optional initial/fallback image URL. A user drop overrides
 *                it; clearing the drop reveals src again.
 *
 * Size and layout come from ordinary CSS on the element — width/height
 * inline or from a parent grid — so it composes with any layout.
 *
 * Usage:
 *   <script src="image-slot.js"></script>
 *   <image-slot id="hero"   style="width:800px;height:450px" shape="rounded" radius="20"
 *               placeholder="Drop a hero image"></image-slot>
 *   <image-slot id="avatar" style="width:120px;height:120px" shape="circle"></image-slot>
 *   <image-slot id="kite"   style="width:300px;height:300px"
 *               mask="polygon(50% 0, 100% 50%, 50% 100%, 0 50%)"></image-slot>
 */

(() => {
  const STATE_FILE = '.image-slots.state.json';
  // 2× a ~600px slot in a 1920-wide deck — retina-sharp without making the
  // sidecar enormous. A 1200px WebP at q=0.85 is ~150-300KB.
  const MAX_DIM = 1200;
  // Raster formats only. SVG is excluded (can carry script; createImageBitmap
  // on SVG blobs is inconsistent). GIF is excluded because the canvas
  // re-encode keeps only the first frame, so an animated GIF would silently
  // go still — better to reject than surprise.
  const ACCEPT = ['image/png', 'image/jpeg', 'image/webp', 'image/avif'];

  // ── Shared sidecar store ────────────────────────────────────────────────
  // One fetch + immediate write-on-change for every <image-slot> on the
  // page. Reads via fetch() so viewing works anywhere the HTML and sidecar
  // are served together; writes go through window.omelette.writeFile, which
  // the host allowlists to *.state.json basenames only.
  const subs = new Set();
  let slots = {};
  // ids explicitly cleared before the sidecar fetch resolved — otherwise
  // the merge below can't tell "never set" from "just deleted" and would
  // resurrect the sidecar's stale value.
  const tombstones = new Set();
  let loaded = false;
  let loadP = null;
  function load() {
    if (loadP) return loadP;
    loadP = fetch(STATE_FILE).then(r => r.ok ? r.json() : null).then(j => {
      // Merge: sidecar loses to any in-memory change that raced ahead of
      // the fetch (drop or clear) so neither is clobbered by hydration.
      if (j && typeof j === 'object') {
        const merged = Object.assign({}, j, slots);
        // A framing-only write that raced ahead of hydration must not
        // drop a user image that's only on disk — inherit u from the
        // sidecar for any in-memory entry that lacks one.
        for (const k in slots) {
          if (merged[k] && !merged[k].u && j[k]) {
            merged[k].u = typeof j[k] === 'string' ? j[k] : j[k].u;
          }
        }
        for (const id of tombstones) delete merged[id];
        slots = merged;
      }
      tombstones.clear();
    }).catch(() => {}).then(() => {
      loaded = true;
      subs.forEach(fn => fn());
    });
    return loadP;
  }

  // Serialize writes so two near-simultaneous drops on different slots
  // can't reorder at the backend and leave the sidecar with only the
  // first. A save requested mid-flight just marks dirty and re-fires on
  // completion with the then-current slots.
  let saving = false;
  let saveDirty = false;
  function save() {
    if (saving) {
      saveDirty = true;
      return;
    }
    const w = window.omelette && window.omelette.writeFile;
    if (!w) return;
    saving = true;
    Promise.resolve(w(STATE_FILE, JSON.stringify(slots))).catch(() => {}).then(() => {
      saving = false;
      if (saveDirty) {
        saveDirty = false;
        save();
      }
    });
  }
  const S_MAX = 5;
  const clampS = s => Math.max(1, Math.min(S_MAX, s));

  // Normalize a stored slot value. Pre-reframe sidecars stored a bare
  // data-URL string; newer ones store {u, s, x, y}. Either shape is valid.
  function getSlot(id) {
    const v = slots[id];
    if (!v) return null;
    return typeof v === 'string' ? {
      u: v,
      s: 1,
      x: 0,
      y: 0
    } : v;
  }
  function setSlot(id, val) {
    if (!id) return;
    if (val) {
      slots[id] = val;
      tombstones.delete(id);
    } else {
      delete slots[id];
      if (!loaded) tombstones.add(id);
    }
    subs.forEach(fn => fn());
    // A drop is rare + high-value — write immediately so nav-away can't lose
    // it. Gate on the initial read so we don't overwrite a sidecar we haven't
    // merged yet; the merge in load() keeps this change once the read lands.
    if (loaded) save();else load().then(save);
  }

  // ── Image downscale ─────────────────────────────────────────────────────
  // Encode through a canvas so the sidecar carries resized bytes, not the
  // raw upload. Longest side is capped at 2× the slot's rendered width
  // (retina) and at MAX_DIM. WebP keeps alpha and is ~10× smaller than PNG
  // for photos, so there's no need for per-image format picking.
  async function toDataUrl(file, targetW) {
    const bitmap = await createImageBitmap(file);
    try {
      const cap = Math.min(MAX_DIM, Math.max(1, Math.round(targetW * 2)) || MAX_DIM);
      const scale = Math.min(1, cap / Math.max(bitmap.width, bitmap.height));
      const w = Math.max(1, Math.round(bitmap.width * scale));
      const h = Math.max(1, Math.round(bitmap.height * scale));
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      canvas.getContext('2d').drawImage(bitmap, 0, 0, w, h);
      return canvas.toDataURL('image/webp', 0.85);
    } finally {
      bitmap.close && bitmap.close();
    }
  }

  // ── Custom element ──────────────────────────────────────────────────────
  const stylesheet = ':host{display:inline-block;position:relative;vertical-align:top;' + '  font:13px/1.3 system-ui,-apple-system,sans-serif;color:rgba(0,0,0,.55);width:240px;height:160px}' + '.frame{position:absolute;inset:0;overflow:hidden;background:rgba(0,0,0,.04)}' +
  // .frame img (clipped) and .spill (unclipped ghost + handles) share the
  // same left/top/width/height in frame-%, computed by _applyView(), so the
  // inside-mask crop and the outside-mask spill stay pixel-aligned.
  '.frame img{position:absolute;max-width:none;transform:translate(-50%,-50%);' + '  -webkit-user-drag:none;user-select:none;touch-action:none}' +
  // Reframe mode (double-click): the full image spills past the mask. The
  // spill layer is sized to the IMAGE bounds so its corners are where the
  // resize handles belong. The ghost <img> inside is translucent; the real
  // clipped <img> underneath shows the opaque in-mask crop.
  '.spill{position:absolute;transform:translate(-50%,-50%);display:none;z-index:1;' + '  cursor:grab;touch-action:none}' + ':host([data-panning]) .spill{cursor:grabbing}' + '.spill .ghost{position:absolute;inset:0;width:100%;height:100%;opacity:.35;' + '  pointer-events:none;-webkit-user-drag:none;user-select:none;' + '  box-shadow:0 0 0 1px rgba(0,0,0,.2),0 12px 32px rgba(0,0,0,.2)}' + '.spill .handle{position:absolute;width:12px;height:12px;border-radius:50%;' + '  background:#fff;box-shadow:0 0 0 1.5px #c96442,0 1px 3px rgba(0,0,0,.3);' + '  transform:translate(-50%,-50%)}' + '.spill .handle[data-c=nw]{left:0;top:0;cursor:nwse-resize}' + '.spill .handle[data-c=ne]{left:100%;top:0;cursor:nesw-resize}' + '.spill .handle[data-c=sw]{left:0;top:100%;cursor:nesw-resize}' + '.spill .handle[data-c=se]{left:100%;top:100%;cursor:nwse-resize}' + ':host([data-reframe]){z-index:10}' + ':host([data-reframe]) .spill{display:block}' + ':host([data-reframe]) .frame{box-shadow:0 0 0 2px #c96442}' + '.empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;' + '  justify-content:center;gap:6px;text-align:center;padding:12px;box-sizing:border-box;' + '  cursor:pointer;user-select:none}' + '.empty svg{opacity:.45}' + '.empty .cap{max-width:90%;font-weight:500;letter-spacing:.01em}' + '.empty .sub{font-size:11px}' + '.empty .sub u{text-underline-offset:2px;text-decoration-color:rgba(0,0,0,.25)}' + '.empty:hover .sub u{color:rgba(0,0,0,.75);text-decoration-color:currentColor}' + ':host([data-over]) .frame{outline:2px solid #c96442;outline-offset:-2px;' + '  background:rgba(201,100,66,.10)}' + '.ring{position:absolute;inset:0;pointer-events:none;border:1.5px dashed rgba(0,0,0,.25);' + '  transition:border-color .12s}' + ':host([data-over]) .ring{border-color:#c96442}' + ':host([data-filled]) .ring{display:none}' +
  // Controls sit BELOW the mask (top:100%), absolutely positioned so the
  // author-declared slot height is unaffected. The gap is padding, not a
  // top offset, so the hover target stays contiguous with the frame.
  '.ctl{position:absolute;top:100%;left:50%;transform:translateX(-50%);padding-top:8px;' + '  display:flex;gap:6px;opacity:0;pointer-events:none;transition:opacity .12s;z-index:2;' + '  white-space:nowrap}' + ':host([data-filled][data-editable]:hover) .ctl,:host([data-reframe]) .ctl' + '  {opacity:1;pointer-events:auto}' + '.ctl button{appearance:none;border:0;border-radius:6px;padding:5px 10px;cursor:pointer;' + '  background:rgba(0,0,0,.65);color:#fff;font:11px/1 system-ui,-apple-system,sans-serif;' + '  backdrop-filter:blur(6px)}' + '.ctl button:hover{background:rgba(0,0,0,.8)}' + '.err{position:absolute;left:8px;bottom:8px;right:8px;color:#b3261e;font-size:11px;' + '  background:rgba(255,255,255,.85);padding:4px 6px;border-radius:5px;pointer-events:none}';
  const icon = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' + 'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>' + '<path d="m21 15-5-5L5 21"/></svg>';
  class ImageSlot extends HTMLElement {
    static get observedAttributes() {
      return ['shape', 'radius', 'mask', 'fit', 'position', 'placeholder', 'src', 'id'];
    }
    constructor() {
      super();
      const root = this.attachShadow({
        mode: 'open'
      });
      // .spill and .ctl sit OUTSIDE .frame so overflow:hidden + border-radius
      // on the frame (circle, pill, rounded) can't clip them.
      root.innerHTML = '<style>' + stylesheet + '</style>' + '<div class="frame" part="frame">' + '  <img part="image" alt="" draggable="false" style="display:none">' + '  <div class="empty" part="empty">' + icon + '    <div class="cap"></div>' + '    <div class="sub">or <u>browse files</u></div></div>' + '  <div class="ring" part="ring"></div>' + '</div>' + '<div class="spill">' + '  <img class="ghost" alt="" draggable="false">' + '  <div class="handle" data-c="nw"></div><div class="handle" data-c="ne"></div>' + '  <div class="handle" data-c="sw"></div><div class="handle" data-c="se"></div>' + '</div>' + '<div class="ctl"><button data-act="replace" title="Replace image">Replace</button>' + '  <button data-act="clear" title="Remove image">Remove</button></div>' + '<input type="file" accept="' + ACCEPT.join(',') + '" hidden>';
      this._frame = root.querySelector('.frame');
      this._ring = root.querySelector('.ring');
      this._img = root.querySelector('.frame img');
      this._empty = root.querySelector('.empty');
      this._cap = root.querySelector('.cap');
      this._sub = root.querySelector('.sub');
      this._spill = root.querySelector('.spill');
      this._ghost = root.querySelector('.ghost');
      this._err = null;
      this._input = root.querySelector('input');
      this._depth = 0;
      this._gen = 0;
      this._view = {
        s: 1,
        x: 0,
        y: 0
      };
      this._subFn = () => this._render();
      // Shadow-DOM listeners live with the shadow DOM — bound once here so
      // disconnect/reconnect (e.g. React remount) doesn't stack handlers.
      this._empty.addEventListener('click', () => this._input.click());
      root.addEventListener('click', e => {
        const act = e.target && e.target.getAttribute && e.target.getAttribute('data-act');
        if (act === 'replace') {
          this._exitReframe(true);
          this._input.click();
        }
        if (act === 'clear') {
          this._exitReframe(false);
          this._gen++;
          this._local = null;
          if (this.id) setSlot(this.id, null);else this._render();
        }
      });
      this._input.addEventListener('change', () => {
        const f = this._input.files && this._input.files[0];
        if (f) this._ingest(f);
        this._input.value = '';
      });
      // naturalWidth/Height aren't known until load — re-apply so the cover
      // baseline is computed from real dimensions, not the 100%×100% fallback.
      this._img.addEventListener('load', () => this._applyView());
      // Gated on editable + fit=cover so share links and contain/fill slots
      // stay static.
      this.addEventListener('dblclick', e => {
        if (!this.hasAttribute('data-editable') || !this._reframes()) return;
        e.preventDefault();
        if (this.hasAttribute('data-reframe')) this._exitReframe(true);else this._enterReframe();
      });
      // Pan + resize both originate on the spill layer. A handle pointerdown
      // drives an aspect-locked resize anchored at the opposite corner; any
      // other pointerdown on the spill pans. Offsets are frame-% so a
      // reframed slot survives responsive resize / PPTX export.
      this._spill.addEventListener('pointerdown', e => {
        if (e.button !== 0 || !this.hasAttribute('data-reframe')) return;
        e.preventDefault();
        e.stopPropagation();
        this._spill.setPointerCapture(e.pointerId);
        const rect = this.getBoundingClientRect();
        const fw = rect.width || 1,
          fh = rect.height || 1;
        const corner = e.target.getAttribute && e.target.getAttribute('data-c');
        let move;
        if (corner) {
          // Resize about the OPPOSITE corner. Viewport-px throughout (rect
          // fw/fh, not clientWidth) so the math survives a transform:scale()
          // ancestor — deck_stage renders slides scaled-to-fit.
          const iw = this._img.naturalWidth || 1,
            ih = this._img.naturalHeight || 1;
          const base = Math.max(fw / iw, fh / ih);
          const sx = corner.includes('e') ? 1 : -1;
          const sy = corner.includes('s') ? 1 : -1;
          const s0 = this._view.s;
          const w0 = iw * base * s0,
            h0 = ih * base * s0;
          const cx0 = (50 + this._view.x) / 100 * fw;
          const cy0 = (50 + this._view.y) / 100 * fh;
          const ox = cx0 - sx * w0 / 2,
            oy = cy0 - sy * h0 / 2;
          const diag0 = Math.hypot(w0, h0);
          const ux = sx * w0 / diag0,
            uy = sy * h0 / diag0;
          move = ev => {
            const proj = (ev.clientX - rect.left - ox) * ux + (ev.clientY - rect.top - oy) * uy;
            const s = clampS(s0 * proj / diag0);
            const d = diag0 * s / s0;
            this._view.s = s;
            this._view.x = (ox + ux * d / 2) / fw * 100 - 50;
            this._view.y = (oy + uy * d / 2) / fh * 100 - 50;
            this._clampView();
            this._applyView();
          };
        } else {
          this.setAttribute('data-panning', '');
          const start = {
            px: e.clientX,
            py: e.clientY,
            x: this._view.x,
            y: this._view.y
          };
          move = ev => {
            this._view.x = start.x + (ev.clientX - start.px) / fw * 100;
            this._view.y = start.y + (ev.clientY - start.py) / fh * 100;
            this._clampView();
            this._applyView();
          };
        }
        const up = () => {
          try {
            this._spill.releasePointerCapture(e.pointerId);
          } catch {}
          this._spill.removeEventListener('pointermove', move);
          this._spill.removeEventListener('pointerup', up);
          this._spill.removeEventListener('pointercancel', up);
          this.removeAttribute('data-panning');
          this._dragUp = null;
        };
        // Stashed so _exitReframe (Escape / outside-click mid-drag) can
        // tear the capture + listeners down synchronously.
        this._dragUp = up;
        this._spill.addEventListener('pointermove', move);
        this._spill.addEventListener('pointerup', up);
        this._spill.addEventListener('pointercancel', up);
      });
      // Wheel zoom stays available inside reframe mode as a trackpad nicety —
      // zooms toward the cursor (offset' = cursor·(1-k) + offset·k).
      this.addEventListener('wheel', e => {
        if (!this.hasAttribute('data-reframe')) return;
        e.preventDefault();
        const r = this.getBoundingClientRect();
        const cx = (e.clientX - r.left) / r.width * 100 - 50;
        const cy = (e.clientY - r.top) / r.height * 100 - 50;
        const prev = this._view.s;
        const next = clampS(prev * Math.pow(1.0015, -e.deltaY));
        if (next === prev) return;
        const k = next / prev;
        this._view.s = next;
        this._view.x = cx * (1 - k) + this._view.x * k;
        this._view.y = cy * (1 - k) + this._view.y * k;
        this._clampView();
        this._applyView();
      }, {
        passive: false
      });
    }
    connectedCallback() {
      // Warn once per page — an id-less slot works for the session but
      // cannot persist, and two id-less slots would share nothing.
      if (!this.id && !ImageSlot._warned) {
        ImageSlot._warned = true;
        console.warn('<image-slot> without an id will not persist its dropped image.');
      }
      this.addEventListener('dragenter', this);
      this.addEventListener('dragover', this);
      this.addEventListener('dragleave', this);
      this.addEventListener('drop', this);
      subs.add(this._subFn);
      // width%/height% in _applyView encode the frame aspect at call time —
      // a host resize (responsive grid, pane divider) would stretch the
      // image until the next _render. Re-render on size change: _render()
      // re-seeds _view from stored before clamp/apply, so a shrink→grow
      // cycle round-trips instead of ratcheting x/y toward the narrower
      // frame's clamp range.
      this._ro = new ResizeObserver(() => this._render());
      this._ro.observe(this);
      load();
      this._render();
    }
    disconnectedCallback() {
      subs.delete(this._subFn);
      this.removeEventListener('dragenter', this);
      this.removeEventListener('dragover', this);
      this.removeEventListener('dragleave', this);
      this.removeEventListener('drop', this);
      if (this._ro) {
        this._ro.disconnect();
        this._ro = null;
      }
      this._exitReframe(false);
    }
    _enterReframe() {
      if (this.hasAttribute('data-reframe')) return;
      this.setAttribute('data-reframe', '');
      this._applyView();
      // Close on click outside (the spill handler stopPropagation()s so
      // in-image drags don't reach this) and on Escape. Listeners are held
      // on the instance so _exitReframe / disconnectedCallback can detach
      // exactly what was attached.
      this._outside = e => {
        if (e.composedPath && e.composedPath().includes(this)) return;
        this._exitReframe(true);
      };
      this._esc = e => {
        if (e.key === 'Escape') this._exitReframe(true);
      };
      document.addEventListener('pointerdown', this._outside, true);
      document.addEventListener('keydown', this._esc, true);
    }
    _exitReframe(commit) {
      if (!this.hasAttribute('data-reframe')) return;
      if (this._dragUp) this._dragUp();
      this.removeAttribute('data-reframe');
      this.removeAttribute('data-panning');
      if (this._outside) document.removeEventListener('pointerdown', this._outside, true);
      if (this._esc) document.removeEventListener('keydown', this._esc, true);
      this._outside = this._esc = null;
      if (commit) this._commitView();
    }
    attributeChangedCallback() {
      if (this.shadowRoot) this._render();
    }

    // handleEvent — one listener object for all four drag events keeps the
    // add/remove symmetric and the depth counter correct.
    handleEvent(e) {
      if (e.type === 'dragenter' || e.type === 'dragover') {
        // Without preventDefault the browser never fires 'drop'.
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
        if (e.type === 'dragenter') this._depth++;
        this.setAttribute('data-over', '');
      } else if (e.type === 'dragleave') {
        // dragenter/leave fire for every descendant crossing — count depth
        // so hovering the icon inside the empty state doesn't flicker.
        if (--this._depth <= 0) {
          this._depth = 0;
          this.removeAttribute('data-over');
        }
      } else if (e.type === 'drop') {
        e.preventDefault();
        e.stopPropagation();
        this._depth = 0;
        this.removeAttribute('data-over');
        const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) this._ingest(f);
      }
    }
    async _ingest(file) {
      this._setError(null);
      if (!file || ACCEPT.indexOf(file.type) < 0) {
        this._setError('Drop a PNG, JPEG, WebP, or AVIF image.');
        return;
      }
      // toDataUrl can take hundreds of ms on a large photo. A Clear or a
      // newer drop during that window would be clobbered when this await
      // resumes — bump + capture a generation so stale encodes bail.
      const gen = ++this._gen;
      try {
        const w = this.clientWidth || this.offsetWidth || MAX_DIM;
        const url = await toDataUrl(file, w);
        if (gen !== this._gen) return;
        // Only exit reframe once the new image is in hand — a rejected type
        // or decode failure leaves the in-progress crop untouched.
        this._exitReframe(false);
        const val = {
          u: url,
          s: 1,
          x: 0,
          y: 0
        };
        setSlot(this.id || '', val);
        // Keep a session-local copy for id-less slots so the drop still
        // shows, even though it cannot persist.
        if (!this.id) {
          this._local = val;
          this._render();
        }
      } catch (err) {
        if (gen !== this._gen) return;
        this._setError('Could not read that image.');
        console.warn('<image-slot> ingest failed:', err);
      }
    }
    _setError(msg) {
      if (this._err) {
        this._err.remove();
        this._err = null;
      }
      if (!msg) return;
      const d = document.createElement('div');
      d.className = 'err';
      d.textContent = msg;
      this.shadowRoot.appendChild(d);
      this._err = d;
      setTimeout(() => {
        if (this._err === d) {
          d.remove();
          this._err = null;
        }
      }, 3000);
    }

    // Reframing (pan/resize) is only meaningful for fit=cover — contain/fill
    // keep the old object-fit path and double-click is a no-op.
    _reframes() {
      return this.hasAttribute('data-filled') && (this.getAttribute('fit') || 'cover') === 'cover';
    }

    // Cover-baseline geometry, shared by clamp/apply/resize. Null until the
    // img has loaded (naturalWidth is 0 before that) or when the slot has no
    // layout box — ResizeObserver fires with a 0×0 rect under display:none,
    // and clamping against a degenerate 1×1 frame would silently pull the
    // stored pan toward zero.
    _geom() {
      const iw = this._img.naturalWidth,
        ih = this._img.naturalHeight;
      const fw = this.clientWidth,
        fh = this.clientHeight;
      if (!iw || !ih || !fw || !fh) return null;
      return {
        iw,
        ih,
        fw,
        fh,
        base: Math.max(fw / iw, fh / ih)
      };
    }
    _clampView() {
      // Pan range on each axis is half the overflow past the frame edge.
      const g = this._geom();
      if (!g) return;
      const mx = Math.max(0, (g.iw * g.base * this._view.s / g.fw - 1) * 50);
      const my = Math.max(0, (g.ih * g.base * this._view.s / g.fh - 1) * 50);
      this._view.x = Math.max(-mx, Math.min(mx, this._view.x));
      this._view.y = Math.max(-my, Math.min(my, this._view.y));
    }
    _applyView() {
      const g = this._geom();
      const fit = this.getAttribute('fit') || 'cover';
      if (fit !== 'cover' || !g) {
        // Non-cover, or dimensions not known yet (before img load).
        this._img.style.width = '100%';
        this._img.style.height = '100%';
        this._img.style.left = '50%';
        this._img.style.top = '50%';
        this._img.style.objectFit = fit;
        this._img.style.objectPosition = this.getAttribute('position') || '50% 50%';
        return;
      }
      // Cover baseline: img fills the frame on its tighter axis at s=1, so
      // pan works immediately on the overflowing axis without zooming first.
      // Width/height and left/top are all frame-% — depends only on the
      // frame aspect ratio, so a responsive resize keeps the same crop. The
      // spill layer mirrors the same box so its corners = image corners.
      const k = g.base * this._view.s;
      const w = g.iw * k / g.fw * 100 + '%';
      const h = g.ih * k / g.fh * 100 + '%';
      const l = 50 + this._view.x + '%';
      const t = 50 + this._view.y + '%';
      this._img.style.width = w;
      this._img.style.height = h;
      this._img.style.left = l;
      this._img.style.top = t;
      this._img.style.objectFit = '';
      this._spill.style.width = w;
      this._spill.style.height = h;
      this._spill.style.left = l;
      this._spill.style.top = t;
    }
    _commitView() {
      const v = {
        s: this._view.s,
        x: this._view.x,
        y: this._view.y
      };
      if (this._userUrl) v.u = this._userUrl;
      // Framing-only (no u) persists too so an author-src slot remembers its
      // crop; clearing the sidecar still falls through to src=.
      if (this.id) setSlot(this.id, v);else {
        this._local = v;
      }
    }
    _render() {
      // Shape / mask. Presets use border-radius so the dashed ring can
      // follow the rounded outline; clip-path is only applied for an
      // explicit `mask` (the ring is hidden there since a rectangle
      // dashed border chopped by an arbitrary polygon looks broken).
      const mask = this.getAttribute('mask');
      const shape = (this.getAttribute('shape') || 'rounded').toLowerCase();
      let radius = '';
      if (shape === 'circle') radius = '50%';else if (shape === 'pill') radius = '9999px';else if (shape === 'rounded') {
        const n = parseFloat(this.getAttribute('radius'));
        radius = (Number.isFinite(n) ? n : 12) + 'px';
      }
      this._frame.style.borderRadius = mask ? '' : radius;
      this._frame.style.clipPath = mask || '';
      this._ring.style.borderRadius = mask ? '' : radius;
      this._ring.style.display = mask ? 'none' : '';

      // Controls and reframe entry gate on this so share links stay read-only.
      const editable = !!(window.omelette && window.omelette.writeFile);
      this.toggleAttribute('data-editable', editable);
      this._sub.style.display = editable ? '' : 'none';

      // Content. The sidecar is also writable by the agent's write_file
      // tool, so its value isn't guaranteed canvas-originated — only accept
      // data:image/ URLs from it. The `src` attribute is author-controlled
      // (Claude wrote it into the HTML) so it passes through unchanged.
      let stored = this.id ? getSlot(this.id) : this._local;
      if (stored && stored.u && !/^data:image\//i.test(stored.u)) stored = null;
      const srcAttr = this.getAttribute('src') || '';
      this._userUrl = stored && stored.u || null;
      const url = this._userUrl || srcAttr;
      // Don't clobber an in-flight reframe with a store-triggered re-render.
      if (!this.hasAttribute('data-reframe')) {
        this._view = {
          s: stored && Number.isFinite(stored.s) ? clampS(stored.s) : 1,
          x: stored && Number.isFinite(stored.x) ? stored.x : 0,
          y: stored && Number.isFinite(stored.y) ? stored.y : 0
        };
      }
      this._cap.textContent = this.getAttribute('placeholder') || 'Drop an image';
      // Toggle via style.display — the [hidden] attribute alone loses to
      // the display:flex / display:block rules in the stylesheet above.
      if (url) {
        if (this._img.getAttribute('src') !== url) {
          this._img.src = url;
          this._ghost.src = url;
        }
        this._img.style.display = 'block';
        this._empty.style.display = 'none';
        this.setAttribute('data-filled', '');
        this._clampView();
        this._applyView();
      } else {
        this._img.style.display = 'none';
        this._img.removeAttribute('src');
        this._ghost.removeAttribute('src');
        this._empty.style.display = 'flex';
        this.removeAttribute('data-filled');
      }
    }
  }
  if (!customElements.get('image-slot')) {
    customElements.define('image-slot', ImageSlot);
  }
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "slides/image-slot.js", error: String((e && e.message) || e) }); }

// synthUtils.js
try { (() => {
// synthUtils.js — shared helpers for the synthetic/preview data layer.
//
// These were copy-pasted, byte-for-byte, across crossAnalytics.js,
// crossSource.js, crossChain.js, previewData.js and enrichment.js. Centralized
// here so the deterministic seed sequence, macro-shock curve and preview/scale
// rules have a SINGLE definition — change once, every synthetic series follows.
//
// Pure + dependency-light: only `previewFor`/`productScale` touch window.* (the
// banco registry / PEVS globals), and only at call time. Load this BEFORE any
// file that builds synthetic data.

(function () {
  // Deterministic pseudo-random from a string seed (FNV-1a hash → mix), stable
  // across reloads so synthetic numbers never jump between loads. Returns a
  // function producing successive floats in [0, 1).
  function seeded(seed) {
    let h = 2166136261;
    for (let i = 0; i < seed.length; i++) {
      h ^= seed.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return () => {
      h += 0x6D2B79F5;
      let t = Math.imul(h ^ h >>> 15, 1 | h);
      t ^= t + Math.imul(t ^ t >>> 7, 61 | t);
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  // Macro shocks shared by every synthetic series so the curves read as real:
  // 2009 global financial crisis dip, 2015–16 recession, 2020 COVID dip.
  // Returns a multiplier (1 = no shock) for a given year.
  function macroShock(year) {
    if (year === 2009) return 0.90;
    if (year === 2015 || year === 2016) return 0.94;
    if (year === 2020) return 0.92;
    return 1;
  }

  // Preview flag for a cross-banco analytic: true iff ANY source banco isn't
  // live yet (so the view shows the synthetic-demo banner).
  function previewFor(...ids) {
    return ids.some(id => (window.bancoById && window.bancoById(id) || {}).status !== 'live');
  }

  // Product weight: a single commodity's share of the latest-year basket value
  // (window.PRODUCT_TS), used to scale aggregates when one product is selected.
  // null/absent code = whole basket → scale 1. Floored at 0.02 so a tiny
  // commodity still draws a visible series.
  function productScale(code) {
    if (!code) return 1;
    const series = (window.PRODUCT_TS || {})[code];
    if (!series) return 1;
    const last = series[series.length - 1]?.v || 0;
    const total = Object.values(window.PRODUCT_TS || {}).reduce((s, ser) => s + (ser[ser.length - 1]?.v || 0), 0) || 1;
    return Math.max(0.02, last / total);
  }
  Object.assign(window, {
    seeded,
    macroShock,
    previewFor,
    productScale
  });
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "synthUtils.js", error: String((e && e.message) || e) }); }

// urlState.js
try { (() => {
// urlState.js — the shared deep-link codec contract.
//
// The app state travels in the share URL. The ENCODER lives in
// AppShell.onShare and the DECODER in Dashboard.readStateFromURL — two halves
// of the same wire format. The param-key list and the array sentinel rules
// were duplicated as literals on both sides; a typo on one half silently
// breaks shared links. This module is the single source of truth for the keys
// and the array encode/decode, so the two halves can't drift.

// Every query param the dashboard owns. Used by the encoder (to know what to
// emit) and by the decoder (to detect whether a URL carries OUR state at all,
// so unrelated params like ?t=… stay inert).
window.URL_STATE_KEYS = ['v', 'b', 'ip', 'cur', 'corr', 'mu', 'vu', 'as', 'pb', 'fl', 'st', 'vmn', 'vmx', 'sd', 'ed', 'xs', 'xm', 'xy0', 'xy1'];

// Array dimension → param. null = "no filter" (omitted → all on restore); an
// explicit empty selection travels as the sentinel "-" so "Nenhum"/"Nenhuma"
// survives the round-trip instead of silently restoring as "all".
window.urlEncodeArr = a => a == null ? '' : a.length ? a.join(',') : '-';

// Inverse of urlEncodeArr, reading from a URLSearchParams.
//   absent/'' → null (no filter, all) · '-' → [] (explicit none) · csv → array
window.urlDecodeArr = (q, key) => {
  const v = q.get(key);
  if (v === null || v === '') return null;
  if (v === '-') return [];
  return v.split(',').filter(Boolean);
};

// Numeric param: absent/'' → null, else Number.
window.urlDecodeNum = (q, key) => {
  const v = q.get(key);
  return v === null || v === '' ? null : Number(v);
};

// Does this query string carry any of OUR keys? (Decoder gate.)
window.urlHasOwnState = q => window.URL_STATE_KEYS.some(k => q.has(k));

// Build the share query string from the flat state object the encoder
// assembles (keys = URL_STATE_KEYS). Drops empty/undefined/null values.
window.urlEncodeState = state => Object.entries(state).filter(([, v]) => v !== '' && v !== undefined && v !== null).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
})(); } catch (e) { __ds_ns.__errors.push({ path: "urlState.js", error: String((e && e.message) || e) }); }

// views.js
try { (() => {
// views.js — registry of analytical perspectives, grouped into formal
// categories. Single source of truth for the topnav and the router.
//
// status: 'live' → component exists and renders real data.
//         'soon' → planned; router shows a perspective placeholder.
//
// Adding a perspective = add an entry here (+ its component when live).

window.VIEW_GROUPS = [{
  id: 'aggregate',
  label: 'Análise agregada',
  hint: 'cesta de commodities',
  views: [{
    id: 'overview',
    label: 'Visão geral',
    status: 'live',
    exportable: true,
    requires: [],
    desc: 'Resumo consolidado: KPIs, série de valor, composição e distribuição geográfica resumida.'
  }, {
    id: 'value',
    label: 'Valor e volume',
    status: 'live',
    exportable: true,
    requires: [],
    desc: 'Séries históricas de valor e quantidade da cesta, segregadas por família de unidades.'
  }]
}, {
  id: 'product',
  label: 'Análise por produto',
  hint: 'commodity individual',
  views: [{
    id: 'product_profile',
    label: 'Perfil do produto',
    status: 'live',
    exportable: true,
    requires: ['product'],
    desc: 'Mergulho em uma única commodity: série de valor e quantidade, preço médio implícito (valor ÷ quantidade), evolução da participação na cesta e ranking histórico de UFs produtoras.',
    planned: ['Preço médio implícito por ano', 'Participação da commodity na cesta', 'Ranking de UFs produtoras ao longo do tempo', 'Ficha técnica (código, unidade, espécie, cobertura)']
  }, {
    id: 'product_compare',
    label: 'Comparativo entre produtos',
    status: 'live',
    exportable: true,
    requires: ['product'],
    desc: 'Selecione 2 a 4 commodities e compare lado a lado: séries normalizadas (base 100), variação acumulada, CAGR e correlação cruzada.',
    planned: ['Séries normalizadas base 100', 'CAGR por produto', 'Correlação cruzada entre commodities', 'Tabela comparativa de métricas']
  }, {
    id: 'productivity',
    label: 'Produtividade',
    status: 'live',
    exportable: true,
    requires: ['yield'],
    selfData: true,
    desc: 'Rendimento (kg/ha) e área colhida por lavoura: trajetória nacional de produtividade e a geografia do rendimento por UF. Disponível para bancos de produção agrícola (IBGE PAM).',
    planned: ['Série de rendimento médio (kg/ha)', 'Série de área colhida', 'Mapa de produtividade por UF', 'Ranking de UFs mais produtivas']
  }]
}, {
  id: 'flows',
  label: 'Análise de fluxos',
  hint: 'origem → destino',
  views: [{
    id: 'flows_territorial',
    label: 'Fluxos territoriais',
    status: 'live',
    requires: ['flow'],
    selfData: true,
    desc: 'Reconstituição da cadeia: extração (PEVS) → comércio interno (SEFAZ) → exportação (MDIC) → comércio internacional (UN Comtrade). Diagrama Sankey origem → destino.',
    planned: ['Diagrama Sankey origem → destino', 'Cadeia extração → interno → externo', 'Saldo líquido por UF', 'Filtro por elo da cadeia']
  }, {
    id: 'flows_partners',
    label: 'Parceiros comerciais',
    status: 'live',
    requires: ['partner'],
    selfData: true,
    desc: 'Rankings de UFs e países de origem/destino, fluxos bilaterais e participação de cada parceiro no total comercializado.',
    planned: ['Top parceiros (país / UF)', 'Fluxos bilaterais', 'Evolução de participação por parceiro', 'Mapa de fluxos internacionais']
  }]
}, {
  id: 'distribution',
  label: 'Análise de distribuição',
  hint: 'espacial',
  views: [{
    id: 'geo',
    label: 'Geografia',
    status: 'live',
    exportable: true,
    requires: ['geo'],
    desc: 'Distribuição territorial por valor, massa e volume, em região, UF ou município. Mapas, mapas de calor e rankings.'
  }, {
    id: 'concentration',
    label: 'Concentração e desigualdade',
    status: 'live',
    exportable: true,
    requires: [],
    desc: 'Quão concentrada é a produção: curva de Lorenz, índice de Gini e HHI (Herfindahl-Hirschman) por geografia e por produto.',
    planned: ['Curva de Lorenz', 'Índice de Gini ao longo do tempo', 'HHI por UF e por produto', 'Participação dos top-5 produtores']
  }]
}, {
  id: 'temporal',
  label: 'Análise temporal',
  hint: 'ciclos',
  views: [{
    id: 'seasonality',
    label: 'Sazonalidade e tendências',
    status: 'live',
    requires: ['monthly'],
    selfData: true,
    desc: 'Padrões temporais além da tendência: mapa de calor mês × ano, decomposição tendência/sazonalidade/ruído e detecção de quebras estruturais. Mais informativa com dados mensais (MDIC, SEFAZ).',
    planned: ['Mapa de calor mês × ano', 'Decomposição tendência + sazonal + ruído', 'Detecção de quebras estruturais', 'Box-plot por mês']
  }]
}, {
  id: 'crosssource',
  label: 'Análise cruzada',
  hint: 'entre bancos',
  views: [{
    id: 'cross_source',
    label: 'Cruzamento entre fontes',
    status: 'live',
    requires: [],
    crossBanco: true,
    align: 'eixo temporal (ano)',
    desc: 'Compare séries anuais de bancos DIFERENTES no mesmo eixo de tempo — ex.: produção (IBGE) × exportação (MDIC). Escolha de 2 a 4 séries, alinhe pela janela comum e alterne entre base 100, eixo duplo e painéis.',
    planned: ['Sobreposição base 100 / eixo duplo / painéis', 'Varição acumulada e CAGR por série', 'Correlação interanual entre fontes', 'Razão entre séries (ex.: coeficiente de exportação)']
  }, {
    id: 'cross_export_coef',
    label: 'Coeficiente de exportação',
    status: 'live',
    requires: [],
    crossBanco: true,
    align: 'UF × ano',
    sources: ['ibge_pevs', 'mdic_comex'],
    desc: 'Quanto do que cada UF produz (IBGE) segue para exportação (MDIC). Mapa de orientação exportadora por estado e evolução do coeficiente nacional.'
  }, {
    id: 'cross_market_share',
    label: 'Brasil no mercado mundial',
    status: 'live',
    requires: [],
    crossBanco: true,
    align: 'eixo temporal (ano)',
    sources: ['mdic_comex', 'un_comtrade'],
    desc: 'Exportação brasileira como fração da exportação mundial do produto (UN Comtrade). Trajetória de participação e quebra por commodity.'
  }, {
    id: 'cross_price_spread',
    label: 'Preço: porteira vs. FOB',
    status: 'live',
    requires: [],
    crossBanco: true,
    align: 'eixo temporal (ano)',
    sources: ['ibge_pevs', 'mdic_comex'],
    desc: 'Preço implícito na produção (IBGE) contra o preço de exportação FOB (MDIC). O spread entre porteira e porto mede a agregação de valor.'
  }, {
    id: 'cross_mirror',
    label: 'Espelho comercial',
    status: 'live',
    requires: [],
    crossBanco: true,
    align: 'eixo temporal (ano)',
    sources: ['mdic_comex', 'un_comtrade'],
    desc: 'A mesma exportação vista por fontes distintas — MDIC, Comtrade e parceiros. A divergência ao longo do tempo é um diagnóstico de qualidade entre bases.'
  }, {
    id: 'cross_chain',
    label: 'Balanço da cadeia',
    status: 'live',
    requires: [],
    crossBanco: true,
    align: 'balanço físico (massa)',
    sources: ['ibge_pevs', 'sefaz_nf', 'mdic_comex', 'un_comtrade'],
    desc: 'O caminho do que se produz: produção (IBGE) → comércio interno (SEFAZ) → exportação (MDIC) → fatia do mercado mundial (Comtrade). Balanço de oferta reconciliado em massa.'
  }, {
    id: 'cross_lag',
    label: 'Defasagem safra → embarque',
    status: 'live',
    requires: [],
    crossBanco: true,
    align: 'mês (intra-anual)',
    sources: ['ibge_pevs', 'mdic_comex'],
    desc: 'Quantos meses os embarques (MDIC, mensal) seguem o pico da safra (IBGE). Perfis mensais sobrepostos e correlação cruzada por defasagem.'
  }]
}, {
  id: 'curated',
  label: 'Análises curadas',
  hint: 'enriquecidas',
  views: [{
    id: 'curated_value_added',
    label: 'Valor agregado',
    status: 'live',
    requires: [],
    crossBanco: true,
    curated: true,
    align: 'nível de industrialização',
    sources: ['mdic_comex', 'un_comtrade'],
    desc: 'Exportação separada entre bruta e processada, a partir da classificação curada dos códigos. Participação do processado e prêmio de preço.'
  }, {
    id: 'curated_market_nature',
    label: 'Finalidade econômica',
    status: 'live',
    requires: [],
    crossBanco: true,
    curated: true,
    align: 'finalidade (consumo/processamento)',
    sources: ['mdic_comex', 'un_comtrade'],
    desc: 'Valor comercializado por finalidade econômica (consumo × processamento), a partir da classificação curada do par regime × fluxo. Cruzada com a direção, separa comprar/vender para consumir ou processar.'
  }]
}, {
  id: 'documentation',
  label: 'Documentação do banco',
  hint: 'metadados',
  views: [{
    id: 'quality',
    label: 'Qualidade dos dados',
    status: 'live',
    exportable: true,
    requires: ['quality'],
    desc: 'Diagnóstico da dimensão data_quality_flag: distribuição de flags, integridade temporal e qualidade por produto e UF.'
  }, {
    id: 'glossary',
    label: 'Glossário',
    status: 'live',
    requires: [],
    desc: 'Termos, códigos e colunas do banco selecionado.'
  }]
}];

// Flattened lookup helpers ------------------------------------------------
window.VIEW_BY_ID = (() => {
  const map = {};
  window.VIEW_GROUPS.forEach(g => g.views.forEach(v => {
    map[v.id] = {
      ...v,
      group: g
    };
  }));
  return map;
})();
window.viewById = id => window.VIEW_BY_ID[id] || null;
window.viewLabel = id => window.VIEW_BY_ID[id]?.label || id;
window.isViewLive = id => window.VIEW_BY_ID[id]?.status === 'live';

// View → component registry. The component globals (window.ViewXxx) are
// defined by each perspective's JSX file and resolved LAZILY via window[name]
// at render time (views.js loads before those files). This is the single
// source of truth for routing a view id to its React component — adding a
// perspective = one entry here + its component file. Replaces the per-view
// ternary chains that used to live (scattered) inside MainScreen.
window.VIEW_COMPONENTS = {
  overview: 'ViewOverview',
  value: 'ViewValueVolume',
  product_profile: 'ViewProductProfile',
  product_compare: 'ViewProductCompare',
  productivity: 'ViewProductivity',
  flows_territorial: 'ViewFlows',
  flows_partners: 'ViewPartners',
  geo: 'ViewGeography',
  concentration: 'ViewConcentration',
  seasonality: 'ViewSeasonality',
  quality: 'ViewQuality',
  glossary: 'Glossary',
  cross_source: 'ViewCrossSource',
  cross_export_coef: 'ViewExportCoef',
  cross_market_share: 'ViewMarketShare',
  cross_price_spread: 'ViewPriceSpread',
  cross_mirror: 'ViewMirror',
  cross_chain: 'ViewChainBalance',
  cross_lag: 'ViewHarvestLag',
  curated_value_added: 'ViewValueAdded',
  curated_market_nature: 'ViewMarketNature'
};

// Resolve a view's React component (or null). Dev guard: a LIVE view with no
// mapping / missing global warns loudly instead of silently rendering the
// wrong screen — the failure mode of the old `: window.ViewOverview` default.
window.viewComponent = id => {
  const name = window.VIEW_COMPONENTS[id];
  const comp = name ? window[name] : null;
  if (!comp && window.isViewLive && window.isViewLive(id)) {
    console.warn(`[views] sem componente para a perspectiva live "${id}" (mapeada para ${name || 'nada'})`);
  }
  return comp;
};

// The source banco whose maturity gates a cross-perspective into PREVIEW mode —
// i.e. the LEAST-MATURE source among the view's `sources` (ties broken toward the
// downstream source = later array position). Single-sourced from the view
// registry so a PreviewBanner never re-literals a banco id; if a view's `sources`
// change, the banner follows automatically. Returns null for non-cross views.
window.crossPreviewBanco = viewId => {
  const v = window.viewById ? window.viewById(viewId) : null;
  const srcs = v && v.sources || [];
  if (!srcs.length) return null;
  let bestId = null,
    bestOrder = Infinity;
  srcs.forEach(id => {
    const b = window.bancoById ? window.bancoById(id) : null;
    const order = b && window.MATURITY[b.maturity] && window.MATURITY[b.maturity].order || 0;
    if (order <= bestOrder) {
      bestOrder = order;
      bestId = id;
    } // <= → ties prefer later index
  });
  return window.bancoById ? window.bancoById(bestId) : null;
};

// ── Capability system ───────────────────────────────────────────────────
// A view declares which data capabilities it `requires`; each banco
// declares which it `provides` (in bancos.js). Crossing the two tells us
// whether a perspective is even meaningful for the active banco — distinct
// from whether the component has been built yet (status live/soon).
window.CAPABILITIES = {
  product: {
    label: 'dimensão de produto'
  },
  geo: {
    label: 'dimensão geográfica (UF/município)'
  },
  flow: {
    label: 'fluxo origem → destino'
  },
  partner: {
    label: 'dimensão de parceiro comercial'
  },
  monthly: {
    label: 'granularidade temporal mensal/diária'
  },
  quality: {
    label: 'dimensão de qualidade'
  },
  // Agricultural-production capabilities (IBGE PAM and any future crop banco).
  area: {
    label: 'área plantada / colhida'
  },
  yield: {
    label: 'rendimento (produtividade kg/ha)'
  }
};

// { applies: bool, missing: ['flow', ...] } — does view work for banco?
window.viewAppliesTo = (viewId, bancoId) => {
  const v = window.VIEW_BY_ID[viewId];
  const b = window.bancoById ? window.bancoById(bancoId) : null;
  if (!v || !b) return {
    applies: true,
    missing: []
  };
  // Cross-source perspectives operate ACROSS bancos, not against the active
  // one — they always apply regardless of which banco is selected.
  if (v.crossBanco) return {
    applies: true,
    missing: []
  };
  const provides = b.provides || [];
  const requires = v.requires || [];
  const missing = requires.filter(r => !provides.includes(r));
  return {
    applies: missing.length === 0,
    missing
  };
};

// Which bancos DO support a given view (inverse indicator).
window.bancosSupporting = viewId => {
  const v = window.VIEW_BY_ID[viewId];
  if (!v) return [];
  const requires = v.requires || [];
  return (window.visibleBancos ? window.visibleBancos() : window.BANCOS || []).filter(b => requires.every(r => (b.provides || []).includes(r)));
};

// Human phrase for a list of missing capabilities.
window.missingCapsLabel = missing => (missing || []).map(c => window.CAPABILITIES[c]?.label || c).join(' · ');
})(); } catch (e) { __ds_ns.__errors.push({ path: "views.js", error: String((e && e.message) || e) }); }

})();
