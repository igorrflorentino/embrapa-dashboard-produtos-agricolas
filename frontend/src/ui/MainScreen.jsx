// MainScreen — thin router that picks the right view component
// for the active perspective (topnav) or info page (sidebar).

function MainScreen({ filters, view = 'overview', database = 'ibge_pevs', infoPage = null, basket = null, conventions = null, setDatabase = null, crossState = null, setCrossState = null }) {
  const VIEW_LABEL = Object.fromEntries(
    (window.VIEW_GROUPS || []).flatMap(g => g.views.map(v => [v.id, v.label]))
  );
  const BANCO_LABEL = Object.fromEntries((window.BANCOS || []).map(b => [b.id, b.short]));
  const BANCO_SUB   = Object.fromEntries((window.BANCOS || []).map(b => [b.id, b.sub]));
  const BANCO_PROV  = Object.fromEntries(
    (window.BANCOS || [])
      .filter(b => b.status === 'live')
      .map(b => [b.id, { source: b.short, table: window.bancoTable(b.id), ...b.prov }])
  );

  // Compute active unit families from the basket
  const families = window.familiesInBasket(basket, database);

  // ---- Info pages (sidebar) ----
  if (infoPage === 'glossary') {
    return (
      <div className="screen">
        <div className="page-hero">
          <div>
            <div className="overline">Informações</div>
            <h1 className="page-title">Glossário global</h1>
            <p className="page-sub">
              Pesquise termos, códigos e colunas em todos os bancos do dashboard.
              Filtre por categoria ou banco de origem.
            </p>
          </div>
        </div>
        <window.Glossary scope="global" />
      </div>
    );
  }

  // Enriquecimento — one screen per tool (the old combined ?ip=curation aliases to
  // the industrialization screen so existing deep links still resolve).
  if (infoPage === 'enrich_industrial' || infoPage === 'curation') {
    return (
      <div className="screen" data-screen-label="Engenharia de atributos · Nível de industrialização">
        <div className="page-hero">
          <div>
            <div className="overline">Engenharia de atributos · conhecimento do pesquisador</div>
            <h1 className="page-title">Nível de industrialização</h1>
            <p className="page-sub">
              Aqui você classifica cada produto em um nível: <strong>Bruta</strong> (in natura, sem
              transformação), <strong>Processada</strong> (beneficiada pela indústria) ou
              <strong> Misturado</strong> (quando o código junta os dois e não dá para separar).
              Basta escolher na tabela abaixo e clicar em <strong>Aplicar à base</strong>.
              Com essa marcação, o painel consegue separar quanto de cada commodity sai do país
              ainda bruta e quanto sai já industrializada — e acompanhar, ano a ano, se a produção
              brasileira está <strong>agregando mais valor</strong>. O que você define fica salvo e
              passa a valer para todos os pesquisadores.
            </p>
          </div>
        </div>
        <window.ViewEnrichmentIndustrialization />
      </div>
    );
  }

  if (infoPage === 'enrich_market') {
    return (
      <div className="screen" data-screen-label="Engenharia de atributos · Tipo de Mercado">
        <div className="page-hero">
          <div>
            <div className="overline">Engenharia de atributos · conhecimento do pesquisador</div>
            <h1 className="page-title">Tipo de Mercado</h1>
            <p className="page-sub">
              Cada operação de comércio exterior combina um <strong>regime aduaneiro</strong> (a
              forma como a mercadoria entra ou sai do país — exportação definitiva, drawback,
              entreposto, etc.) com um <strong>fluxo</strong> (importação, exportação,
              reexportação…). Aqui você indica, para cada combinação, se ela atende ao
              <strong> consumo</strong> final ou ao <strong>processamento</strong> industrial.
              A matriz mostra o valor em dólar de cada combinação — comece pelas que mais pesam.
              Assim o painel revela se a commodity é negociada para uso final ou como insumo da
              indústria. O que você define fica salvo e passa a valer para todos os pesquisadores.
            </p>
          </div>
        </div>
        <window.ViewEnrichmentMarketNature />
      </div>
    );
  }

  if (infoPage) {
    return (
      <div className="screen">
        <div className="page-hero">
          <div>
            <div className="overline">Informações</div>
            <h1 className="page-title">
              {infoPage === 'about' ? 'Sobre o dashboard' : 'Saúde do sistema'}
            </h1>
            <p className="page-sub">
              {infoPage === 'about'
                ? 'O que é o dashboard, quais bancos compõem a base, como os dados são processados e como interpretar cada perspectiva.'
                : 'Status das execuções de pipeline, frescor dos dados e qualidade das tabelas Gold.'}
            </p>
          </div>
        </div>
        {infoPage === 'about' ? (
          <window.ViewAbout />
        ) : infoPage === 'health' ? (
          <window.ViewHealth />
        ) : (
          <div className="card subtle">
            <window.SectionHeader
              overline="Em construção"
              title="Conteúdo em preparação"
            />
            <p className="caption" style={{ padding: '8px 4px 4px' }}>
              Conteúdo desta página será detalhado em próxima iteração.
            </p>
          </div>
        )}
      </div>
    );
  }

  // ---- Per-banco glossary (topnav) ----
  if (view === 'glossary') {
    const banco = window.GLOSSARY[database];
    if (!banco) {
      return (
        <div className="screen">
          <div className="page-hero">
            <div>
              <div className="overline">Glossário</div>
              <h1 className="page-title">Glossário do banco em preparação</h1>
              <p className="page-sub">
                O glossário específico deste banco será publicado junto da liberação dos dados.
                Use o glossário global na barra lateral para buscar termos compartilhados.
              </p>
            </div>
          </div>
        </div>
      );
    }
    return (
      <div className="screen">
        <div className="page-hero">
          <div>
            <div className="overline">Glossário · {banco.label}</div>
            <h1 className="page-title">Termos e colunas · {banco.label}</h1>
            <p className="page-sub">
              {banco.sub}. Definições dos termos, fontes e colunas usados nesta perspectiva.
              Use o glossário global na barra lateral para buscar em todos os bancos.
            </p>
          </div>
        </div>
        <window.Glossary scope={database} />
      </div>
    );
  }

  // ---- Cross-source perspectives (operate ACROSS bancos) --------------
  // Meta-perspectives: they don't read the active banco's snapshot, so they
  // render before banco resolution / soon / capability gating. cross_source
  // is the picker-driven one (its selection lives in crossState); the others
  // are self-contained analytical views with fixed `sources`.
  const _cvm = window.viewById ? window.viewById(view) : null;
  if (_cvm && _cvm.crossBanco) {
    const isPicker = _cvm.id === 'cross_source';
    const baseSeries = (crossState && crossState.series) || window.DEFAULT_CROSS_STATE.series;
    const srcIds = isPicker ? [...new Set(baseSeries.map(s => s.b))] : (_cvm.sources || []);
    const srcShorts = srcIds.map(id => window.bancoById(id)?.short).filter(Boolean).join(' · ');
    const Comp = window.viewComponent(_cvm.id);
    return (
      <div className="screen" data-screen-label={`Perspectiva · ${VIEW_LABEL[view]}`}>
        <div className="page-hero">
          <div>
            <div className="overline">Análise cruzada · multi-fonte</div>
            <h1 className="page-title">{VIEW_LABEL[view]}</h1>
            <p className="page-sub">
              {isPicker
                ? 'Compare séries históricas anuais de bancos diferentes no mesmo eixo de tempo — a evolução não é mais limitada a um banco ativo por vez.'
                : _cvm.desc}
            </p>
          </div>
          <div className="hero-meta">
            <div className="meta-group">
              <div className="meta-group-head">Cruzamento ativo</div>
              <div className="meta-row">
                <span className="meta-label">Fontes</span>
                <span className="meta-val">{srcShorts || '—'}</span>
              </div>
              {isPicker && (
                <div className="meta-row">
                  <span className="meta-label">Séries</span>
                  <span className="meta-val tnum"><strong>{baseSeries.length}</strong> <small>de 4</small></span>
                </div>
              )}
              <div className="meta-row">
                <span className="meta-label">Alinhamento</span>
                <span className="meta-val">{_cvm.align || 'eixo temporal (ano)'}</span>
              </div>
            </div>
          </div>
        </div>
        {isPicker
          ? <window.ViewCrossSource value={crossState || window.DEFAULT_CROSS_STATE} onChange={setCrossState} />
          : (Comp ? <Comp view={_cvm.id} /> : null)}
      </div>
    );
  }

  // ---- Resolve banco from the registry ----------
  const banco = window.bancoById(database);
  const isSoon = banco && banco.status === 'soon';

  // Preview perspectives bring their own banco-keyed (synthetic) data, so
  // they render even while the banco itself is 'soon'. They take precedence
  // over the banco-level coming-soon — but ONLY when the view applies.
  const _vm = window.viewById ? window.viewById(view) : null;
  const _compat = window.viewAppliesTo ? window.viewAppliesTo(view, database) : { applies: true, missing: [] };
  if (_vm && _vm.selfData && _compat.applies) {
    const PreviewComp = window.viewComponent(view);
    if (PreviewComp) {
      return (
        <div className="screen">
          <div className="page-hero">
            <div>
              <div className="overline">{banco.short} · {_vm.group?.label}</div>
              <h1 className="page-title">{VIEW_LABEL[view]}</h1>
              <p className="page-sub">{banco.sub}</p>
            </div>
          </div>
          <PreviewComp summary={filters} conventions={conventions} database={database} />
        </div>
      );
    }
  }

  // ---- Perspective not applicable to this banco (capability mismatch) --
  // A permanent incompatibility outranks the temporary 'Em breve' of a
  // soon banco — so this check runs BEFORE the isSoon block. (selfData
  // preview views already returned above.)
  if (_vm && !_compat.applies) {
    const supporters = window.bancosSupporting ? window.bancosSupporting(view) : [];
    return (
      <div className="screen">
        <div className="page-hero">
          <div>
            <div className="overline">{BANCO_LABEL[database]} · {_vm.group?.label}</div>
            <h1 className="page-title">{_vm.label}</h1>
            <p className="page-sub">{BANCO_SUB[database]}</p>
          </div>
          <div className="hero-meta">
            <div className="meta-group">
              <div className="meta-group-head">Compatibilidade</div>
              <div className="meta-row">
                <span className="meta-label">Disponibilidade</span>
                <span className="meta-val"><strong>Não se aplica</strong></span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Requer</span>
                <span className="meta-val">{window.missingCapsLabel(_compat.missing)}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Banco ativo</span>
                <span className="meta-val">{banco.short}</span>
              </div>
            </div>
          </div>
        </div>
        <window.ViewNotApplicable
          viewMeta={_vm}
          banco={banco}
          missing={_compat.missing}
          supporters={supporters}
          onPickBanco={(id) => { if (setDatabase) setDatabase(id); }}
        />
      </div>
    );
  }

  // ---- Em breve placeholder for non-live bancos -----------------------
  if (isSoon) {
    const bm = window.bancoMeta(database);
    return (
      <div className="screen">
        <div className="page-hero">
          <div>
            <div className="overline">{banco.short} · {bm.domain}</div>
            <h1 className="page-title">{VIEW_LABEL[view]}</h1>
            <p className="page-sub">{banco.sub}</p>
          </div>
          <div className="hero-meta">
            <div className="meta-group">
              <div className="meta-group-head">Status do banco</div>
              <div className="meta-row">
                <span className="meta-label">Maturidade</span>
                <span className="meta-val" style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <window.MaturityTag banco={banco} size="sm" />
                </span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Uso</span>
                <span className="meta-val" style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <window.UsageTag active={true} />
                </span>
              </div>
              {bm.maturityDate && (
                <div className="meta-row">
                  <span className="meta-label">Previsão</span>
                  <span className="meta-val tnum">{bm.maturityDate}</span>
                </div>
              )}
              <div className="meta-row">
                <span className="meta-label">Tabela Gold</span>
                <span className="meta-val"><code>{window.bancoTable(database)}</code></span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Fonte</span>
                <span className="meta-val">{bm.source}</span>
              </div>
            </div>
          </div>
        </div>

        <window.ViewComingSoon banco={banco} view={view} />
      </div>
    );
  }

  // ---- Provenance + selection block (live banco) ----
  // BANCO_PROV is the registry (synthetic) fallback; the LIVE provenance comes
  // from window.dataStore.meta(database) — read at RENDER time so the async
  // /api/source-meta overlay wins once it resolves. meta.prov.* carries the REAL
  // refresh / última-safra year / ufsTotal / yearsTotal / counts; the registry
  // prov stays as the pre-resolution fallback inside meta() itself.
  const prov = BANCO_PROV[database];
  const _meta = window.dataStore && window.dataStore.meta ? window.dataStore.meta(database) : null;
  const metaProv = (_meta && _meta.prov) || prov;

  // ---- Perspective not applicable to this banco (capability mismatch) --
  // Distinct from 'soon': even when built, this view won't apply here.
  // (The actual not-applicable gating already ran above via _compat; here we
  // only need the view meta to detect a built-but-'soon' perspective.)
  const viewMeta = window.viewById ? window.viewById(view) : null;

  // ---- Perspective not yet built (banco live, view 'soon') ------------
  if (viewMeta && viewMeta.status === 'soon') {
    return (
      <div className="screen">
        <div className="page-hero">
          <div>
            <div className="overline">{BANCO_LABEL[database]} · {viewMeta.group?.label}</div>
            <h1 className="page-title">{viewMeta.label}</h1>
            <p className="page-sub">{BANCO_SUB[database]}</p>
          </div>
          <div className="hero-meta">
            <div className="meta-group">
              <div className="meta-group-head">Status da perspectiva</div>
              <div className="meta-row">
                <span className="meta-label">Disponibilidade</span>
                <span className="meta-val"><strong>Em breve</strong></span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Categoria</span>
                <span className="meta-val">{viewMeta.group?.label}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Banco ativo</span>
                <span className="meta-val">{prov.source}</span>
              </div>
            </div>
          </div>
        </div>
        <window.ViewPerspectiveSoon viewMeta={viewMeta} />
      </div>
    );
  }

  // Derive selection effects from the SAME filter engine the views use,
  // so the hero counters reflect EVERY active dimension (products, value,
  // period, UF, quality) — not just products × value.
  const _f = window.applyFilters ? window.applyFilters(filters || {}, database) : null;
  // Unfiltered snapshot pass — gives the LIVE totals for the hero denominators
  // (products / rows). The prov.* registry values are synthetic prototype
  // leftovers (e.g. PEVS shows 12 products / 11,2 mi rows when the live Gold has
  // 3 products / ~95 mil rows); the live snapshot is the source of truth.
  const _fAll = window.applyFilters ? window.applyFilters({}, database) : null;
  const _shares = (_f && _f._shares) || {};
  // UFs that survive the state filter AND still carry production — REAL Brazilian
  // states only. A trade banco's ufData includes non-state pseudo-origins
  // (ND/EX/ZN…) that must not inflate the "UFs cobertas" tally past 27 (the live
  // audit caught COMEX showing 32/27). Prefer the backend's per-row `real` flag,
  // else canonical-registry membership (FINDING #4).
  const _isRealUf = (u) => (u.real != null ? u.real : (window.isCanonicalUf ? window.isCanonicalUf(u.uf) : true));
  const ufsCovered = _f
    ? _f.ufData.filter(u => _isRealUf(u) && u.value > 0).length
    : (window.UF_DATA || []).filter(u => u.value > 0).length;
  // Denominator: real UFs in the banco's universe, capped at the canonical 27.
  const ufsTotalReal = _f
    ? Math.min(27, _f.ufDataFull.filter(_isRealUf).length || 27)
    : 27;
  // Years inside the active period window.
  const yearsCovered = _f ? _f.ts.length : prov.yearsTotal;
  // Approximate selection counts from current filters. basket == null means
  // "no filter" (all); an explicit (possibly empty) basket counts literally —
  // zero selected products must read 0, never fall back to the total.
  // Product universe = the ACTIVE banco's live snapshot products (3 for PEVS),
  // not the synthetic window.PRODUCTS the prov getter reads (12). Fallback to
  // prov only when the snapshot hasn't loaded.
  const productsTotal = (_f && _f.productsTotal != null) ? _f.productsTotal : prov.productsTotal;
  const productsSelected = basket == null ? productsTotal : basket.length;
  // Total rows = sum of the snapshot's quality-flag counts (every Gold row carries
  // exactly one quality flag, so the sum IS the row count). Live ⇒ matches the real
  // table (~95 mil for PEVS) instead of prov.totalRows' synthetic 11,2 mi. Fallback
  // to the registry estimate only if quality counts are unavailable.
  const _liveRows = _fAll && Array.isArray(_fAll.qualityFlags)
    ? _fAll.qualityFlags.reduce((s, f) => s + (f.count || 0), 0)
    : 0;
  // The registry prov no longer fabricates a row count, so the only source is the
  // live snapshot's quality-flag sum; show "—" until it resolves (never a fake total).
  const totalRows = _liveRows || prov.totalRows;
  const rowsAfter = totalRows ? Math.round(
    totalRows *
    (_shares.productShare ?? 1) *
    (_shares.valueShare   ?? 1) *
    (_shares.yearShare    ?? 1) *
    (_shares.flagShare    ?? 1) *
    (_shares.stateShare   ?? 1)
  ) : null;
  const fmtRows = window.fmtRows;  // shared compact mi/mil counter (data.js)
  const rowsTotalLabel = totalRows ? fmtRows(totalRows) : '—';
  const rowsAfterLabel = rowsAfter != null ? fmtRows(rowsAfter) : '—';

  // ---- Data views ----
  const ViewComponent = window.viewComponent(view) || window.ViewOverview;

  return (
    <div className="screen">
      <window.MaturityBanner banco={banco} />
      <div className="page-hero">
        <div>
          <div className="overline">Pesquisa histórica · {BANCO_LABEL[database]}</div>
          <h1 className="page-title">{VIEW_LABEL[view]}</h1>
          <p className="page-sub">
            {BANCO_SUB[database]} · séries históricas para análise da evolução
            temporal de produção e exploração de cada commodity.
          </p>
        </div>
        <div className="hero-meta">
          <div className="meta-group">
            <div className="meta-group-head">Proveniência</div>
            <div className="meta-row">
              <span className="meta-label">Banco</span>
              <span className="meta-val">{prov.source} · <code>{prov.table}</code></span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Status</span>
              <span className="meta-val" style={{ display: 'flex', gap: '6px', alignItems: 'center', justifyContent: 'flex-end' }}>
                <window.MaturityTag banco={banco} size="sm" />
                <window.UsageTag active={true} />
              </span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Última safra</span>
              <span className="meta-val tnum">{metaProv.lastCrop || '—'}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Refresh Gold</span>
              <span className="meta-val tnum">{metaProv.refresh || '—'}</span>
            </div>
          </div>

          <div className="meta-group">
            <div className="meta-group-head">Seleção ativa</div>
            <div className="meta-row">
              <span className="meta-label">Linhas</span>
              <span className="meta-val tnum">
                <strong>{rowsAfterLabel}</strong> <small>de {rowsTotalLabel}</small>
              </span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Produtos</span>
              <span className="meta-val tnum">{productsSelected ?? '—'} / {productsTotal ?? '—'}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">UFs cobertas</span>
              <span className="meta-val tnum">{ufsCovered} / {ufsTotalReal}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Anos cobertos</span>
              <span className="meta-val tnum">{yearsCovered ?? '—'} / {metaProv.yearsTotal ?? '—'}</span>
            </div>
          </div>
        </div>
      </div>

      <ViewComponent
        families={families}
        summary={filters}
        database={database}
        conventions={conventions || window.DEFAULT_CONVENTIONS}
      />
    </div>
  );
}

Object.assign(window, { MainScreen });
