// ViewAbout — institutional "Sobre o dashboard" page.
// Pure structured content: purpose, datasets, perspectives, pipeline,
// usage tips, credits. No insights, no live data — just what the
// dashboard is and how to use it.

function ViewAbout() {
  const bancos = window.visibleBancos ? window.visibleBancos() : (window.BANCOS || []);
  const livePev = window.bancoById ? window.bancoById('ibge_pevs') : null;
  const yearStart = livePev?.prov?.yearStart || 1986;

  // Perspectives derived from the single registry (views.js · VIEW_GROUPS) so
  // this page never goes stale when a view is added/removed. The glossary is a
  // reference tool (not an analytical perspective), so it stays out of this
  // list — but its group still counts toward the categories.
  const VIEWS = (window.VIEW_GROUPS || [])
    .flatMap(g => g.views.map(v => ({ id: v.id, title: v.label, desc: v.desc, group: g.label })))
    .filter(v => v.id !== 'glossary' && v.desc);
  const viewGroupCount = (window.VIEW_GROUPS || []).length;

  // Gold table names derived from the banco registry (bancos.js), rather than
  // repeated in the pipeline text.
  const goldTables = bancos.map(b => window.bancoTable(b.id)).join(', ');

  // App version is config; the date follows the snapshot refresh (bancos.js).
  const APP_VERSION = 'v0.4.2';
  const refreshDate = (livePev?.prov?.refresh || '').split(' · ')[0] || '—';

  const PIPELINE = [
    {
      stage: 'Bronze',
      hint:  'Raw',
      desc:  'Ingestão direta das fontes oficiais sem transformação: tabelas SIDRA, arquivos do COMEX, downloads UN Comtrade, extrações SEFAZ. Auditoria por hash de arquivo e timestamp de ingestão.',
    },
    {
      stage: 'Silver',
      hint:  'Conformed',
      desc:  'Normalização de esquemas, conciliação de códigos (NCM ↔ SH6, IBGE ↔ TOM/SIAFI), reconstrução de séries históricas e marcação da dimensão data_quality_flag.',
    },
    {
      stage: 'Gold',
      hint:  'Analytics',
      desc:  `Tabelas desnormalizadas e enriquecidas por banco (${goldTables}). Convenções monetárias e cobertura temporal aplicadas. Fonte direta do dashboard.`,
    },
  ];

  const TIPS = [
    {
      title: 'Filtros não são iguais a convenções métricas',
      desc:  'Filtros reduzem quais linhas entram na visualização (produtos, período, UFs e municípios, flags, faixa de valor). Convenções métricas decidem como essas linhas são exibidas (moeda, correção monetária, unidade de massa e volume). Os dois são independentes.',
    },
    {
      title: 'Famílias de unidades nunca se misturam',
      desc:  'Quantidades em massa (t/kg) e em volume (m³/L) jamais são somadas. Quando a cesta selecionada contém produtos de famílias diferentes, o dashboard mostra uma métrica de quantidade por família. Valor monetário (BRL) permanece agregável.',
    },
    {
      title: 'Citação e compartilhamento',
      desc:  'Use “Citar painel” no canto superior direito para gerar uma referência ABNT do estado atual (banco, perspectiva, recorte e convenções). “Compartilhar” copia uma URL que reproduz toda a seleção atual.',
    },
    {
      title: 'Exportação',
      desc:  'O botão “Exportar CSV”, ao lado de “Editar filtros”, baixa a fatia atual de dados — com todos os filtros aplicados, na resolução máxima disponível na tabela Gold.',
    },
  ];

  const CREDITS = [
    { role: 'Coordenação científica', who: 'Embrapa — Empresa Brasileira de Pesquisa Agropecuária' },
    { role: 'Vinculação institucional', who: 'Ministério da Agricultura e Pecuária · Governo Federal' },
    { role: 'Fontes de dados',         who: 'IBGE · MDIC SECEX · UN Statistics Division · SEFAZ estaduais' },
    { role: 'Engenharia de dados',     who: 'Pipeline Medalhão sobre BigQuery — ingestão, conformação e enriquecimento' },
    { role: 'Apresentação',            who: 'Dashboard interativo HTML + visualizações SVG próprias' },
  ];

  return (
    <div className="ab-stack">
      {/* Purpose */}
      <div className="card ab-purpose">
        <window.SectionHeader
          overline="Propósito"
          title="Análise histórica de commodities brasileiras"
        />
        <p className="ab-lead">
          Esta é uma ferramenta científica desenvolvida pela <strong>Embrapa</strong> para
          permitir que pesquisadores acompanhem a evolução temporal da produção,
          exploração, comercialização e exportação de commodities brasileiras. O foco
          é exclusivamente analítico — não há recomendações automatizadas, projeções ou
          opiniões. Todos os números visíveis vêm diretamente das tabelas Gold do pipeline.
        </p>
        <p className="ab-lead">
          O recorte temporal disponível depende da fonte: a base IBGE PEVS cobre
          desde <strong>{yearStart}</strong>; comércio exterior (MDIC, UN Comtrade) já
          está disponível com cobertura própria, e o comércio interno (SEFAZ) será
          liberado em seguida.
        </p>
      </div>

      {/* Datasets */}
      <div className="card">
        <window.SectionHeader
          overline="Bancos de dados"
          title="O que você encontra aqui"
          action={<span className="caption">{bancos.length} bancos · {bancos.filter(b => b.status === 'live').length} disponível(is)</span>}
        />
        <div className="ab-banco-grid">
          {bancos.map(b => { const bm = window.bancoMeta(b.id); return (
            <div key={b.id} className={'ab-banco mat-' + b.maturity}>
              <div className="ab-banco-head">
                <span className="ab-banco-short">{b.short}</span>
                <window.MaturityTag banco={b} />
              </div>
              <div className="ab-banco-domain">{bm.domain}</div>
              <p className="ab-banco-sub">{b.sub}</p>
              <dl className="ab-banco-meta">
                <dt>Granularidade</dt><dd>{bm.scope}</dd>
                <dt>Fonte</dt><dd>{bm.source}</dd>
                <dt>Tabela</dt><dd><code>{bm.table}</code></dd>
                {bm.maturityDate && (
                  <>
                    <dt>Conclusão prevista</dt><dd className="tnum">{bm.maturityDate}</dd>
                  </>
                )}
              </dl>
            </div>
          ); })}
        </div>
        <div className="ab-mat-legend">
          <div className="ab-mat-legend-head">Maturidade dos bancos</div>
          <window.MaturityLegend />
        </div>
      </div>

      {/* Perspectives */}
      <div className="card">
        <window.SectionHeader
          overline="Perspectivas analíticas"
          title={`${VIEWS.length} perspectivas em ${viewGroupCount} categorias`}
        />
        <div className="ab-view-grid">
          {VIEWS.map((v, i) => (
            <div key={v.id} className="ab-view">
              <span className="ab-view-num tnum">{String(i + 1).padStart(2, '0')}</span>
              <h3 className="ab-view-title">
                {v.title}
                <span style={{ fontWeight: 400, color: 'var(--fg-3)' }}> · {v.group}</span>
              </h3>
              <p className="ab-view-desc">{v.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Data pipeline */}
      <div className="card">
        <window.SectionHeader
          overline="Como os dados são processados"
          title="Arquitetura Medalhão · Bronze → Silver → Gold"
        />
        <div className="ab-pipeline">
          {PIPELINE.map((s, i) => (
            <React.Fragment key={s.stage}>
              <div className={'ab-stage ab-stage-' + s.stage.toLowerCase()}>
                <div className="ab-stage-head">
                  <span className="ab-stage-name">{s.stage}</span>
                  <span className="ab-stage-hint">{s.hint}</span>
                </div>
                <p className="ab-stage-desc">{s.desc}</p>
              </div>
              {i < PIPELINE.length - 1 && (
                <div className="ab-stage-arrow" aria-hidden="true">→</div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Usage tips */}
      <div className="card">
        <window.SectionHeader
          overline="Como usar"
          title="Convenções importantes antes de interpretar"
        />
        <div className="ab-tips">
          {TIPS.map((t, i) => (
            <div key={i} className="ab-tip">
              <h3 className="ab-tip-title">{t.title}</h3>
              <p className="ab-tip-desc">{t.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Credits */}
      <div className="card">
        <window.SectionHeader
          overline="Créditos e proveniência"
          title="Quem mantém o dashboard"
        />
        <dl className="ab-credits">
          {CREDITS.map((c, i) => (
            <React.Fragment key={i}>
              <dt>{c.role}</dt>
              <dd>{c.who}</dd>
            </React.Fragment>
          ))}
        </dl>
        <div className="ab-version">
          <div>
            <span className="meta-label">Versão</span>
            <span className="meta-val tnum">{APP_VERSION} · {refreshDate}</span>
          </div>
          <div>
            <span className="meta-label">Contato técnico</span>
            <span className="meta-val">igor.lopes@embrapa.br</span>
          </div>
          <div>
            <span className="meta-label">Licença dos dados</span>
            <span className="meta-val">Atribuição obrigatória (Embrapa + fonte original)</span>
          </div>
        </div>
      </div>
    </div>
  );
}

window.ViewAbout = ViewAbout;
