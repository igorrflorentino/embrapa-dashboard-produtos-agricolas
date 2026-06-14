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
  planejado:       { id: 'planejado',       label: 'Planejado',          color: 'var(--pres-gray-400)', hasData: false, future: true, order: 1,
                     desc: 'No roadmap, mas sem implementação iniciada nem prazo definido.' },
  desenvolvimento: { id: 'desenvolvimento', label: 'Em desenvolvimento',  color: 'var(--status-mat-dev)', hasData: false, future: true, order: 2,
                     desc: 'Implementação em andamento, com data prevista de conclusão.' },
  beta:            { id: 'beta',            label: 'Beta',               color: 'var(--info)',          hasData: true,  caveat: true, order: 3,
                     desc: 'Disponível para uso, mas com cobertura ainda parcial e sujeita a mudanças.' },
  estavel:         { id: 'estavel',         label: 'Estável',            color: 'var(--ok)',            hasData: true,  order: 4,
                     desc: 'Banco em produção — 100% pronto para consumo e análise.' },
  manutencao:      { id: 'manutencao',      label: 'Em manutenção',      color: 'var(--warn)',          hasData: true,  caveat: true, order: 5,
                     desc: 'Em produção, porém em correção de cálculo/tabela ou atualização programada.' },
  descontinuado:   { id: 'descontinuado',   label: 'Descontinuado',      color: 'var(--status-mat-sunset)', hasData: true,  caveat: true, sunset: true, order: 6,
                     desc: 'Banco obsoleto — não recebe mais manutenção e será removido em breve.' },
};
window.maturityMeta = (b) =>
  window.MATURITY[(b && b.maturity) || 'planejado'] || window.MATURITY.planejado;

// Short availability label for banco pickers/tags, derived from maturity.
// 'Disponível' once the banco has data; otherwise it mirrors the no-data
// stage so a planned-but-undated banco doesn't over-promise with "Em breve":
//   desenvolvimento (committed, has a date) → "Em breve"
//   planejado       (no ETA)                → "Sem previsão"
window.bancoAvailability = (b) => {
  if (window.maturityMeta(b).hasData) return 'Disponível';
  return (b && b.maturity === 'desenvolvimento') ? 'Em breve' : 'Sem previsão';
};

window.BANCOS = [
  // ─── Live ────────────────────────────────────────────────────────────
  {
    id:     'ibge_pevs',
    short:  'IBGE PEVS',
    label:  'IBGE · Produção da Extração Vegetal e da Silvicultura',
    sub:    'Produção e exploração de commodities no território brasileiro',
    domain: 'Produção interna',
    scope:  'Brasil · UF · município',
    source: 'IBGE',
    table:  'gold_pevs_production',
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
      origin:  { label: 'UF de origem',  kind: 'uf' },
      dest:    { label: 'UF de destino', kind: 'uf' },
      partner: { label: 'UF parceira',   kind: 'uf' },
      product: { codeLabel: 'Código PEVS' },
    },
    // Comparable ANNUAL series this banco can contribute to the cross-source
    // perspective (see crossSource.js). Each metric is a single time series
    // keyed by year. `family` groups metrics that share a physical/value
    // dimension (currency / mass / volume / ratio) so the cross view knows
    // which series can share an axis or form a ratio. `years` is the native
    // coverage; the cross view intersects coverages across selected series.
    metrics: [
      { id: 'prod_value',  label: 'Valor da produção', family: 'currency', unit: 'R$',  agg: 'Valor real (IPCA) da extração vegetal', years: [1986, 2024] },
      { id: 'prod_mass',   label: 'Quantidade produzida (massa)',  family: 'mass',   unit: 't',  agg: 'Massa colhida das espécies de família massa', years: [1986, 2024] },
      { id: 'prod_volume', label: 'Quantidade produzida (volume)', family: 'volume', unit: 'm³', agg: 'Volume das espécies de família volume',     years: [1986, 2024] },
    ],
    // Derive product/UF/year totals from the live datasets instead of
    // hardcoding them in the registry — keeps everything in sync if
    // data.js changes (e.g. a new PEVS product or extra year of data).
    prov: {
      lastCrop:     'PEVS 2024',
      lastCropDate: 'publ. 27 set 2024',
      refresh:      '28 mai 2026 · 04:30 BRT',
      totalRows:    11_177_427,
      get productsTotal() { return (window.PRODUCTS || []).length; },
      get ufsTotal()      { return (window.UF_DATA   || []).length; },
      get yearsTotal()    {
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
      },
    },
  },

  // ─── Connected (representative snapshots) ─────────────────────────────
  // COMEX = estavel, Comtrade = beta (partial coverage). Both have data
  // (hasData) and render real perspectives. SEFAZ stays 'planejado'.
  {
    id:     'ibge_pam',
    short:  'IBGE PAM',
    label:  'IBGE · Produção Agrícola Municipal',
    sub:    'Área, produção e rendimento das lavouras temporárias e permanentes',
    domain: 'Produção agrícola',
    scope:  'Brasil · UF · município',
    source: 'IBGE',
    table:  'gold_pam_production',
    // Beta: live first cut — 5 principais lavouras (soja, milho, café, cana,
    // arroz) a partir de 2010, com QUANTIDADE e VALOR da produção. Renderiza as
    // perspectivas de produção/geo/qualidade com banner de cobertura parcial.
    maturity: 'beta',
    maturityNote: 'Primeira fração: 5 principais lavouras a partir de 2010, com quantidade, valor, área e rendimento (a produtividade já está no painel). Demais lavouras e o histórico completo na sequência.',
    maturityDate: '1º trimestre/2027',
    // LEAN surface: product + geography + quality + yield. The PEVS-shaped views
    // AND the PAM-only Produtividade (área × rendimento) view are wired end-to-end:
    // gold_pam_production carries area_planted/harvested_ha + production, surfaced
    // via /api/productivity (rendimento = produção ÷ área colhida, server-side).
    provides: ['product', 'geo', 'quality', 'yield'],
    baseCurrency: 'BRL',
    geoLevel: 'municipio',
    dimensions: {
      origin:  { label: 'UF produtora', kind: 'uf' },
      dest:    { label: 'UF produtora', kind: 'uf' },
      partner: { label: 'UF produtora', kind: 'uf' },
      product: { codeLabel: 'Código PAM' },
    },
    // Cross-source comparador: not yet wired for PAM (the BFF cross seam serves
    // PEVS/COMEX/COMTRADE only). Empty → PAM doesn't appear in the comparator
    // picker (would return null) until its cross series builders land. PAM's own
    // production/geo/quality views are fully live regardless.
    metrics: [],
    // Provenance shown ONLY as a pre-load fallback — the live app overrides every
    // counter from gold_source_metadata (dataStore.meta('ibge_pam')). Kept honest
    // to the lean window so even the fallback never overstates coverage.
    prov: {
      lastCrop:     'PAM 2024',
      lastCropDate: 'publ. set 2025',
      refresh:      '—',
      totalRows:    null,
      productsTotal: 5,
      ufsTotal:      27,
      yearStart:     2010,
      yearEnd:       2024,
      yearsTotal:    15,
    },
    plannedScope: [
      { col: 'produto (lavoura)',            desc: 'Cultura agrícola — temporária ou permanente.' },
      { col: 'uf · município',               desc: 'Localização da lavoura (até o nível municipal).' },
      { col: 'area_plantada · area_colhida', desc: 'Área destinada e efetivamente colhida (ha) — no Gold; painel em seguida.' },
      { col: 'quantidade_produzida',         desc: 'Produção colhida (t) — disponível.' },
      { col: 'rendimento_medio',             desc: 'Produtividade = produção ÷ área colhida (kg/ha) — no Gold; painel em seguida.' },
      { col: 'valor_producao',               desc: 'Valor da produção (R$) — disponível.' },
    ],
    cobertura: {
      years:      '2010 → presente',
      atualizacao:'anual (atualização manual)',
      granularidade: 'lavoura × município × ano',
    },
  },
  {
    id:     'mdic_comex',
    short:  'MDIC COMEX',
    label:  'MDIC · Comércio Exterior',
    sub:    'Exportação e importação brasileiras por estado de origem, produto e parceiro comercial',
    domain: 'Comércio exterior',
    scope:  'UF de origem ↔ países parceiros',
    source: 'MDIC · SECEX',
    table:  'gold_comex_flows',
    maturity: 'estavel',
    // Exports by UF of origin → partner country, monthly, with product
    // (NCM) and quality. Has flow + partner + monthly.
    provides: ['product', 'geo', 'flow', 'partner', 'monthly', 'quality'],
    // Values in USD (FOB/CIF); geography at origin-state (UF) level (no
    // municipal breakdown).
    baseCurrency: 'USD',
    geoLevel: 'uf',
    dimensions: {
      origin:  { label: 'UF de origem',  kind: 'uf' },
      dest:    { label: 'país parceiro', kind: 'country' },
      partner: { label: 'país parceiro', kind: 'country' },
      product: { codeLabel: 'Código NCM' },
    },
    metrics: [
      { id: 'exp_value',  label: 'Valor exportado (FOB)', family: 'currency', unit: 'US$', agg: 'Soma do valor FOB das exportações', years: [1997, 2024] },
      { id: 'imp_value',  label: 'Valor importado (CIF)', family: 'currency', unit: 'US$', agg: 'Soma do valor das importações',     years: [1997, 2024] },
      { id: 'exp_weight', label: 'Peso exportado',        family: 'mass',     unit: 'kg',  agg: 'Soma do peso líquido exportado',       years: [1997, 2024] },
      { id: 'exp_price',  label: 'Preço médio (US$/kg)',   family: 'ratio',    unit: 'US$/kg', agg: 'Valor FOB ÷ peso líquido', years: [1997, 2024] },
    ],
    // Provenance (live). Representative snapshot generated from the explicit
    // contract shape (02_SNAPSHOT_CONTRACTS.md), castanha/nut chain demo
    // parameters, until the real Gold is wired.
    prov: {
      lastCrop:     'COMEX 2024 · M12',
      lastCropDate: 'publ. jan 2025',
      refresh:      '29 mai 2026 · 05:10 BRT',
      totalRows:    1_284_530,
      productsTotal: 5,
      ufsTotal:      27,
      yearStart:     1997,
      yearEnd:       2024,
      yearsTotal:    28,
    },
    plannedScope: [
      { col: 'NCM · SH4 · SH6',                 desc: 'Classificação harmonizada do produto exportado.' },
      { col: 'uf_origem',                       desc: 'UF onde a mercadoria foi produzida ou está estabelecido o exportador.' },
      { col: 'pais_destino · pais_origem',      desc: 'Parceiro comercial na operação.' },
      { col: 'via',                             desc: 'Modalidade de transporte (marítima · aérea · rodoviária).' },
      { col: 'val_fob_usd · peso_kg · qtd_est', desc: 'Valor FOB em USD, peso líquido e quantidade estatística.' },
    ],
    cobertura: {
      years:      '1997 → presente',
      atualizacao:'mensal (D+30)',
      granularidade: 'NCM × UF × país × via × ano-mês',
    },
  },
  {
    id:     'un_comtrade',
    short:  'UN COMTRADE',
    label:  'UN Comtrade · Estatísticas de Comércio Internacional',
    sub:    'Fluxos de comércio entre nações reportados à Divisão de Estatística da ONU',
    domain: 'Comércio internacional',
    scope:  'País → país (com ou sem filtro Brasil)',
    source: 'UN Statistics Division',
    table:  'gold_comtrade_flows',
    maturity: 'beta',
    // Connected & loaded, but the ingestion window is intentionally capped at
    // 2022–2023 today (the dev window — see project memory "COMTRADE dev window").
    // Bronze/Gold hold only those two years, so the registry must NOT overstate
    // coverage: the cross-source comparable-window math reads THIS registry and
    // would otherwise intersect to a window Gold does not contain. The historical
    // backfill (older years) lands after the frontend handoff is verified.
    maturityNote: 'Cobertura inicial 2022–2023; backfill histórico (anos anteriores) em andamento — limite de requisições da API UN Comtrade.',
    maturityDate: '4º trimestre/2026',
    // Country → country flows. Product (HS6), flow, partner, quality.
    // Geography is country-level only (no Brazilian UF/município).
    provides: ['product', 'flow', 'partner', 'quality'],
    // Values in USD; country↔country trade, no national geographic dimension.
    baseCurrency: 'USD',
    geoLevel: null,
    dimensions: {
      origin:  { label: 'país reporter', kind: 'country' },
      dest:    { label: 'país parceiro', kind: 'country' },
      partner: { label: 'país parceiro', kind: 'country' },
      product: { codeLabel: 'Código HS6' },
    },
    metrics: [
      { id: 'exp_value', label: 'Valor exportado (BR)', family: 'currency', unit: 'US$', agg: 'Exportações brasileiras declaradas à ONU', years: [2022, 2023] },
      { id: 'imp_value', label: 'Valor importado (BR)', family: 'currency', unit: 'US$', agg: 'Importações brasileiras declaradas à ONU', years: [2022, 2023] },
      { id: 'world_exp', label: 'Exportação mundial',    family: 'currency', unit: 'US$', agg: 'Total mundial do produto (todos reporters)', years: [2022, 2023] },
    ],
    // Provenance (live). Representative snapshot generated from the explicit
    // contract shape (02_SNAPSHOT_CONTRACTS.md), HS 0801 nut-trade demo
    // parameters, until the real Gold is wired.
    // Country-level only → no UF dimension (ufsTotal = 0).
    prov: {
      lastCrop:     'Comtrade 2023',
      lastCropDate: 'rev. 2024T1',
      refresh:      '29 mai 2026 · 05:10 BRT',
      totalRows:    642_180,
      productsTotal: 5,
      ufsTotal:      0,
      yearStart:     2022,
      yearEnd:       2023,
      yearsTotal:    2,
    },
    plannedScope: [
      { col: 'reporter · partner',          desc: 'Países envolvidos no fluxo declarado.' },
      { col: 'flow',                        desc: 'Direção do fluxo (export · import · re-export).' },
      { col: 'HS6',                         desc: 'Sistema Harmonizado a 6 dígitos.' },
      { col: 'val_usd · qty · qty_unit',    desc: 'Valor FOB/CIF, quantidade líquida e unidade estatística.' },
      { col: 'data_quality',                desc: 'Bandeira (final · preliminar · estimado · mirror).' },
    ],
    cobertura: {
      years:      '2022 → 2023 (janela inicial)',
      atualizacao:'anual + revisões',
      granularidade: 'HS6 × par de países × ano',
    },
  },
  {
    id:     'sefaz_nf',
    short:  'SEFAZ NFe',
    label:  'SEFAZ · Fluxos de Notas Fiscais Eletrônicas',
    sub:    'Comércio interno brasileiro reconstruído a partir de NFe inter-estaduais e intermunicipais',
    domain: 'Comércio interno',
    scope:  'UF ↔ UF · município ↔ município',
    source: 'Receita · SEFAZ',
    table:  'gold_nfe_flows',
    maturity: 'planejado',
    // Internal trade: UF↔UF / município↔município flows, daily, with
    // product (NCM), partner (the counterpart UF), monthly+ and quality.
    provides: ['product', 'geo', 'flow', 'partner', 'monthly', 'quality'],
    // Values in BRL; geography down to municipality level (origin/destination).
    baseCurrency: 'BRL',
    geoLevel: 'municipio',
    dimensions: {
      origin:  { label: 'UF de origem',  kind: 'uf' },
      dest:    { label: 'UF de destino', kind: 'uf' },
      partner: { label: 'UF parceira',   kind: 'uf' },
      product: { codeLabel: 'Código NCM' },
    },
    metrics: [
      { id: 'internal_value',  label: 'Valor das operações', family: 'currency', unit: 'R$', agg: 'Soma do valor das NFe inter/intraestaduais', years: [2010, 2024] },
      { id: 'internal_weight', label: 'Peso movimentado',    family: 'mass',     unit: 'kg', agg: 'Soma do peso transportado',               years: [2010, 2024] },
      { id: 'icms_total',      label: 'ICMS recolhido',      family: 'currency', unit: 'R$', agg: 'Soma do ICMS das operações',              years: [2010, 2024] },
    ],
    plannedScope: [
      { col: 'cfop',                         desc: 'Natureza da operação fiscal.' },
      { col: 'uf_origem · municipio_origem', desc: 'Localização do remetente.' },
      { col: 'uf_destino · municipio_destino', desc: 'Localização do destinatário.' },
      { col: 'ncm',                          desc: 'Classificação do produto.' },
      { col: 'val_operacao · val_icms',      desc: 'Valor total da operação e do imposto recolhido.' },
      { col: 'cnae_remetente · cnae_destino',desc: 'Setor de atividade econômica das partes.' },
    ],
    cobertura: {
      years:      '2010 → presente',
      atualizacao:'diária (defasagem 24h)',
      granularidade: 'NCM × CFOP × par UF/município × dia',
      restricoes:  'Agregação com preservação de sigilo abaixo de N=5 estabelecimentos.',
    },
  },
];

window.bancoById = (id) => window.BANCOS.find(b => b.id === id) || window.BANCOS[0];

// Canonical / default DISPLAY currency for a banco. COMEX/Comtrade snapshots
// store BRL-equivalent values (see previewData.js) and default their display
// to USD so the real US$ figures render. Used to reset the display currency on
// banco switch and to label the value filter. Falls back to BRL.
window.canonCurrencyFor = (id) => {
  const b = window.bancoById ? window.bancoById(id) : null;
  return (b && b.baseCurrency) || 'BRL';
};
// Business-semantic descriptor for a banco DIMENSION (origin/dest/partner geo
// + product code scheme). Declared per banco in `dimensions` — adapters/views
// read labels & universe kind from HERE instead of branching on bancoId.
window.bancoDim = (id, dim) => {
  const b = window.bancoById ? window.bancoById(id) : null;
  return (b && b.dimensions && b.dimensions[dim]) || {};
};
// Finest geographic granularity a banco exposes ('municipio' | 'uf' | null).
window.geoLevelFor = (id) => {
  const b = window.bancoById ? window.bancoById(id) : null;
  if (!b) return null;
  if (b.geoLevel !== undefined) return b.geoLevel;
  return (b.provides || []).includes('geo') ? 'municipio' : null;
};

// Visibility axis (backend-controlled). `visible: false` hides a banco from the
// whole UI; default (undefined/true) shows it. UI enumerations use this helper;
// bancoById stays over the full list so an id can always be resolved.
window.isBancoVisible = (b) => {
  const banco = (typeof b === 'string') ? window.bancoById(b) : b;
  return !!banco && banco.visible !== false;
};
window.visibleBancos = () => (window.BANCOS || []).filter(b => b.visible !== false);

// Gold table name to DISPLAY: prefer the backend-reported name (dataStore),
// fall back to the registry literal (declared/planned, e.g. for not-connected
// bancos). One resolver so a backend rename propagates to the whole UI.
window.bancoTable = (id) => {
  const fromBackend = (window.dataStore && window.dataStore.table) ? window.dataStore.table(id) : null;
  return fromBackend || ((window.bancoById && window.bancoById(id)) || {}).table || null;
};

// Provenance metadata resolver: the registry banco (UI declaration + fallback)
// OVERLAID with whatever the backend reports (dataStore.meta). The UI reads
// provenance through this — never registry literals directly — so any field
// the backend reports (table, source, granularity, coverage, refresh, counts,
// expected-completion) is authoritative and can't diverge from reality.
window.bancoMeta = (id) => {
  const b = (window.bancoById && window.bancoById(id)) || {};
  const back = (window.dataStore && window.dataStore.meta) ? (window.dataStore.meta(id) || {}) : {};
  const clean = {}; Object.keys(back).forEach(k => { if (back[k] != null) clean[k] = back[k]; });
  return { ...b, ...clean };
};

// Derive the legacy `status` ('live'|'soon') from maturity.hasData so all
// existing routing / CSV gating / cross-source preview logic keeps working
// while the UI reads the richer maturity stage. Single source of truth.
window.BANCOS.forEach(b => {
  if (!('maturity' in b)) b.maturity = 'planejado';
  Object.defineProperty(b, 'status', {
    get() { return (window.MATURITY[b.maturity] || {}).hasData ? 'live' : 'soon'; },
    enumerable: true, configurable: true,
  });
});

// Cross-source helpers: every (banco, metric) pair the dashboard can plot
// side by side. `metricById` resolves one pair; `allMetricRefs` enumerates
// them for the series picker.
window.metricById = (bancoId, metricId) => {
  const b = window.bancoById(bancoId);
  return (b && b.metrics) ? b.metrics.find(m => m.id === metricId) || null : null;
};
window.allMetricRefs = () =>
  (window.visibleBancos ? window.visibleBancos() : (window.BANCOS || [])).flatMap(b =>
    (b.metrics || []).map(m => ({ banco: b.id, metric: m.id, bancoMeta: b, metricMeta: m })));

// Family display labels shared by the cross-source view.
window.METRIC_FAMILIES = {
  currency:   { label: 'valor monetário' },
  mass:       { label: 'massa' },
  volume:     { label: 'volume' },
  ratio:      { label: 'razão / índice' },
  area:       { label: 'área' },
  rendimento: { label: 'rendimento / produtividade' },
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
  if (window.__bancoCoverageWarned[mapLabel]) return;        // once per map
  window.__bancoCoverageWarned[mapLabel] = true;
  const list = window.visibleBancos ? window.visibleBancos() : (window.BANCOS || []);
  const missing = list
    .filter(b => !opts.onlyLive || b.status === 'live')
    .filter(b => { try { return !hasEntry(b); } catch (e) { return true; } })
    .map(b => b.id);
  if (missing.length) {
    console.warn(
      `[coverage] ${mapLabel}: visible banco(s) with no entry → ${missing.join(', ')}. ` +
      `Add the matching entry (see CLAUDE.md · "plug in a banco from a new domain").`
    );
  }
};
