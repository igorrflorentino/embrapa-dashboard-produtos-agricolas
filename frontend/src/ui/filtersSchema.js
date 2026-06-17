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
// row-counter heuristic in dataFilters.js (valueShareForRange, which reads
// `rowShare`). `suffix` builds the label as `≥ <symbol> <suffix>` at render
// time (symbol depends on the active currency); `none` has no threshold.
//
// HONESTY (#7): the per-threshold `rowShare` fractions used to be 0.81 / 0.52 /
// 0.18 / 0.04 — fabricated guesses, since there is NO real COUNT of rows that
// clear a value threshold (no backend aggregate exists for it). They scaled the
// "Linhas X de Y" hero counter, making it assert a made-up filtered count. They
// are now all 1.00, so a value-threshold preset leaves the counter at the
// UNFILTERED total rather than parading an invented number. `rowShare` stays on
// each preset (kept at 1.00) so dataFilters.js's `preset.rowShare` lookup keeps
// returning a valid number — never undefined/NaN — and the real, snapshot-derived
// share dimensions (product/flag/year/state) are untouched.
window.VALUE_PRESETS = [
  { id: 'none', min: null,      max: null, suffix: null,      rowShare: 1.00 },
  { id: '1k',   min: 1_000,     max: null, suffix: '1 mil',   rowShare: 1.00 },
  { id: '10k',  min: 10_000,    max: null, suffix: '10 mil',  rowShare: 1.00 },
  { id: '100k', min: 100_000,   max: null, suffix: '100 mil', rowShare: 1.00 },
  { id: '1M',   min: 1_000_000, max: null, suffix: '1 mi',    rowShare: 1.00 },
];

window.FILTER_SCHEMAS = {
  ibge_pevs: {
    table: 'gold_pevs_production',
    dims: [
      { id: 'produtos',  num: '01', tier: 'shared',    type: 'products',
        label: 'Produtos · PEVS',          column: 'codigo_pevs',
        hint: 'Commodities da extração vegetal e silvicultura.' },
      { id: 'periodo',   num: '02', tier: 'universal', type: 'period-value',
        label: 'Período & faixa de valor', column: 'ano · val_real_ipca',
        hint: 'Janela temporal e corte por valor monetário da linha.' },
      { id: 'geografia', num: '03', tier: 'shared',    type: 'geo-cascade',
        label: 'Geografia',                column: 'uf · municipio',
        hint: 'Cascata nação ▸ região ▸ estado ▸ município.' },
      { id: 'qualidade', num: '04', tier: 'specific',  type: 'flags',
        label: 'Qualidade dos dados',      column: 'data_quality_flag',
        hint: 'Bandeira de qualidade por linha.' },
    ],
  },

  ibge_pam: {
    table: 'gold_pam_production',
    dims: [
      { id: 'produtos',  num: '01', tier: 'shared',    type: 'products',
        label: 'Lavouras · PAM',           column: 'produto_pam',
        hint: 'Culturas temporárias e permanentes da Produção Agrícola Municipal.' },
      { id: 'periodo',   num: '02', tier: 'universal', type: 'period-value',
        label: 'Período & faixa de valor', column: 'ano · valor_producao',
        hint: 'Janela temporal (anual) e corte por valor da produção.' },
      { id: 'geografia', num: '03', tier: 'shared',    type: 'geo-cascade',
        label: 'Geografia',                column: 'uf · municipio',
        hint: 'Cascata nação ▸ região ▸ estado ▸ município.' },
      { id: 'qualidade', num: '04', tier: 'specific',  type: 'flags',
        label: 'Qualidade dos dados',      column: 'data_quality_flag',
        hint: 'Bandeira de qualidade por linha.' },
    ],
  },

  mdic_comex: {
    table: 'gold_comex_flows',
    dims: [
      { id: 'periodo',   tier: 'universal', type: 'date-range',
        label: 'Período',                  column: 'ano_mes',
        hint: 'Mensal, de 1997 ao presente.' },
      { id: 'ncm',       tier: 'shared',    type: 'multi-tree',
        label: 'Produto · NCM / SH',       column: 'ncm',
        hint: 'Hierarquia SH2 ▸ SH4 ▸ SH6 ▸ NCM 8 dígitos.' },
      { id: 'uf_origem', tier: 'shared',    type: 'multi',
        label: 'UF de origem',             column: 'uf_origem',
        hint: 'Unidade da federação do exportador.' },
      { id: 'pais',      tier: 'specific',  type: 'multi-search',
        label: 'País parceiro',            column: 'pais_destino · pais_origem',
        hint: 'Destino (exportação) ou origem (importação).' },
      { id: 'fluxo',     tier: 'specific',  type: 'segment',
        label: 'Fluxo',                    column: 'fluxo',
        options: ['Exportação', 'Importação'],
        hint: 'Direção da operação.' },
      { id: 'via',       tier: 'specific',  type: 'multi',
        label: 'Via de transporte',        column: 'via',
        options: ['Marítima', 'Aérea', 'Rodoviária', 'Ferroviária', 'Fluvial', 'Dutos'],
        hint: 'Modalidade logística da operação.' },
      { id: 'valor',     tier: 'universal', type: 'value-range',
        label: 'Faixa de valor (FOB)',     column: 'val_fob_usd',
        hint: 'Corte por valor FOB em dólares.' },
    ],
  },

  un_comtrade: {
    table: 'gold_comtrade_flows',
    dims: [
      { id: 'periodo',  tier: 'universal', type: 'date-range',
        label: 'Período',                  column: 'ano',
        hint: 'Anual, de 1988 ao presente.' },
      { id: 'reporter', tier: 'specific',  type: 'multi-search',
        label: 'País reporter',            column: 'reporter',
        hint: 'País que declarou a operação à UNSD.' },
      { id: 'partner',  tier: 'specific',  type: 'multi-search',
        label: 'País parceiro',            column: 'partner',
        hint: 'Contraparte do fluxo declarado.' },
      { id: 'hs6',      tier: 'shared',    type: 'multi-tree',
        label: 'Produto · HS6',            column: 'hs6',
        hint: 'Sistema Harmonizado a 6 dígitos.' },
      { id: 'flow',     tier: 'specific',  type: 'segment',
        label: 'Fluxo',                    column: 'flow',
        options: ['Export', 'Import', 'Re-export', 'Re-import'],
        hint: 'Direção do fluxo internacional.' },
      { id: 'valor',    tier: 'universal', type: 'value-range',
        label: 'Faixa de valor (US$)',     column: 'val_usd',
        hint: 'Corte por valor declarado.' },
    ],
  },

  sefaz_nf: {
    table: 'gold_nfe_flows',
    dims: [
      { id: 'periodo',     tier: 'universal', type: 'date-range',
        label: 'Período',                column: 'ano_mes',
        hint: 'Diária (defasagem 24h), de 2010 ao presente.' },
      { id: 'ncm',         tier: 'shared',    type: 'multi-tree',
        label: 'Produto · NCM',          column: 'ncm',
        hint: 'Classificação fiscal da mercadoria.' },
      { id: 'cfop',        tier: 'specific',  type: 'multi',
        label: 'Natureza · CFOP',        column: 'cfop',
        hint: 'Código fiscal de operações e prestações.' },
      { id: 'geo_origem',  tier: 'shared',    type: 'geo-cascade',
        label: 'Origem',                 column: 'uf_origem · municipio_origem',
        hint: 'Localização do remetente da NFe.' },
      { id: 'geo_destino', tier: 'shared',    type: 'geo-cascade',
        label: 'Destino',                column: 'uf_destino · municipio_destino',
        hint: 'Localização do destinatário da NFe.' },
      { id: 'cnae',        tier: 'specific',  type: 'multi-search',
        label: 'Setor · CNAE',           column: 'cnae_remetente · cnae_destino',
        hint: 'Atividade econômica das partes.' },
      { id: 'valor',       tier: 'universal', type: 'value-range',
        label: 'Faixa de valor (R$)',    column: 'val_operacao',
        hint: 'Corte pelo valor total da operação.' },
    ],
  },
};

window.filterSchemaFor = (bancoId) =>
  window.FILTER_SCHEMAS[bancoId] || window.FILTER_SCHEMAS.ibge_pevs;

window.TIER_LABEL = {
  universal: 'Universal',
  shared:    'Compartilhada',
  specific:  'Específica do banco',
};
