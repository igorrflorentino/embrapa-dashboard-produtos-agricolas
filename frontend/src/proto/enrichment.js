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
  const LS_KEY = 'embrapa_enrichment_v9';   // bumped: shape split into GOLD_CODES × classifications
  const COMMIT_MS = 1500;                    // simulated BigQuery write+JOIN latency
  const subs = new Set();
  let committing = false;                     // true while the SCD2 INSERT + live JOIN runs
  const notify = () => subs.forEach(fn => { try { fn(); } catch (e) {} });

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
  const _ENR = (window.DEMO_PARAMS && window.DEMO_PARAMS.enrichment) || {};
  const GOLD_CODES = _ENR.goldCodes || [];

  // ── RIGHT side: the institutional seed = the current slice of the
  //    append-only classification log (`WHERE is_current`), seeded here with
  //    representative demo classifications. New Gold codes above have no key
  //    here → unclassified.
  const SEED = {
    classifications: { ...(_ENR.seedClassifications || {}) },
    // Initial deploy seed: binary PURPOSE (Consumption × Processing).
    // Direction (buy/sell) already comes from the flow; only the purpose here.
    // Export pairs whose destination purpose the regime does not determine
    // (e.g. outright exportation, customs warehouse) are left blank — candidates
    // for future inference from the product's industrialization level.
    pairMarkets: {
      // ─ Consumo (final use / consumption) ─
      'desp-consumo:imports':            'consumo',
      'desp-consumo:for-import':         'consumo',
      'desp-consumo:reimport':           'consumo',
      'viajantes:imports':               'consumo',
      'viajantes:for-import':            'consumo',
      'postal:imports':                  'consumo',
      'postal:for-import':               'consumo',
      'postal:exports':                  'consumo',
      // ─ Processamento (industrial transformation / processing) ─
      'zona-franca:imports':             'processamento',
      'zona-franca:for-import':          'processamento',
      'zona-franca:exports':             'processamento',
      'aperf-ativo:imp-inward':          'processamento',
      'aperf-ativo:imports':             'processamento',
      'aperf-ativo:exp-after-inward':    'processamento',
      'aperf-passivo:exp-for-outward':   'processamento',
      'aperf-passivo:imp-after-outward': 'processamento',
      'aperf-passivo:exports':           'processamento',
      'drawback:exports':                'processamento',
      'drawback:dom-export':             'processamento',
      'drawback:exp-after-inward':       'processamento',
      'transformacao:imports':           'processamento',
      'transformacao:imp-inward':        'processamento',
      'transformacao:for-import':        'processamento',
    },
  };

  const clone = (o) => JSON.parse(JSON.stringify(o));
  function load() {
    try { const raw = localStorage.getItem(LS_KEY); if (raw) { const j = JSON.parse(raw); if (j && j.classifications && j.pairMarkets) return j; } } catch (e) {}
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
    try { localStorage.setItem(LS_KEY, JSON.stringify(applied)); } catch (e) {}
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
      const level = (state.classifications && state.classifications[g.id]) || null;
      return {
        id: g.id, group: g.group, source: g.source, code: g.code, desc: g.desc,
        level, status: level ? 'classificado' : 'a-classificar',
      };
    });
  }

  window.ENRICH_LEVELS = [
    { id: 'bruta',      label: 'Bruta',      color: 'var(--viz-3)' },
    { id: 'processada', label: 'Processada', color: 'var(--viz-2)' },
    { id: 'misturado',  label: 'Misturado',  color: 'var(--pres-gray-300)' },
  ];
  window.ENRICH_MARKETS = [
    { id: 'consumo',       label: 'Consumo',       short: 'Consumo',       color: 'var(--viz-1)' },
    { id: 'processamento', label: 'Processamento', short: 'Processamento', color: 'var(--viz-9)' },
  ];
  window.ENRICH_GROUPS = _ENR.groups || [];
  // Customs regimes (rows) × flow types (columns) — the full pair matrix.
  window.ENRICH_REGIMES = [
    { id: 'desp-consumo',   label: 'Despacho para consumo',                term: 'Clearance for home use',          hint: 'Importação nacionalizada: a mercadoria estrangeira é liberada para circular e ser consumida livremente no país após o recolhimento de todos os tributos. É o destino típico de bens que entram para abastecer o mercado interno.' },
    { id: 'reimport-same',  label: 'Reimportação no mesmo estado',         term: 'Reimportation in the same state', hint: 'Retorno ao país de um bem que havia sido exportado, sem ter sofrido transformação no exterior — por exemplo, mercadoria devolvida ou não vendida. Não representa nova produção nem agregação de valor.' },
    { id: 'exp-definitiva', label: 'Exportação definitiva',                 term: 'Outright exportation',            hint: 'Saída definitiva da mercadoria nacional para o exterior, sem previsão de retorno. É a exportação comum, que escoa a produção do país para mercados estrangeiros.' },
    { id: 'entreposto',     label: 'Entreposto aduaneiro',                 term: 'Customs warehouses',              hint: 'Mercadoria armazenada sob controle aduaneiro com tributos suspensos, antes de definir seu destino (consumo interno, reexportação ou industrialização). Funciona como um ponto de espera logístico, não como destino final.' },
    { id: 'zona-franca',    label: 'Zona Franca',                          term: 'Free zone',                       hint: 'Área delimitada com incentivos fiscais e aduaneiros para atrair indústria e comércio (ex.: Zona Franca de Manaus). A mercadoria entra com tributação reduzida, em geral para transformação industrial.' },
    { id: 'aperf-ativo',    label: 'Aperfeiçoamento ativo',                term: 'Inward processing',               hint: 'Importação temporária de insumos com suspensão de tributos para serem industrializados ou beneficiados no país e depois reexportados. Sinaliza claramente uso industrial, e não consumo final.' },
    { id: 'aperf-passivo',  label: 'Aperfeiçoamento passivo',              term: 'Outward processing',              hint: 'Exportação temporária de um bem para ser beneficiado ou reparado no exterior, com posterior retorno ao país. Aqui o valor é agregado fora do território nacional.' },
    { id: 'drawback',       label: 'Drawback',                             term: 'Drawback',                        hint: 'Regime de incentivo à exportação que suspende ou restitui os tributos dos insumos importados empregados na fabricação de um produto que será exportado. Indica produção voltada ao mercado externo.' },
    { id: 'transformacao',  label: 'Transformação sob controle aduaneiro', term: 'Processing of goods for home use', hint: 'Transformação industrial da mercadoria sob controle aduaneiro, com o produto resultante destinado ao mercado interno. Combina industrialização e consumo doméstico no mesmo regime.' },
    { id: 'cabotagem',      label: 'Cabotagem',                            term: 'Carriage of goods coastwise',     hint: 'Transporte de mercadorias por via aquaviária entre portos do próprio país (cabotagem). É movimentação interna, não comércio exterior, e não cruza fronteiras.' },
    { id: 'infracoes',      label: 'Infrações aduaneiras',                 term: 'Customs offences',                hint: 'Operações vinculadas a infrações, apreensões ou penalidades aduaneiras. Não representam fluxo comercial regular e costumam ser residuais no total.' },
    { id: 'viajantes',      label: 'Viajantes',                            term: 'Travellers',                      hint: 'Bens transportados na bagagem de viajantes que entram ou saem do país. Em geral de uso pessoal, com volume e valor pequenos — pouco relevante para análise de commodities.' },
    { id: 'postal',         label: 'Tráfego postal',                       term: 'Postal traffic',                  hint: 'Mercadorias movimentadas pela via postal e remessas internacionais (correios). Concentra o comércio eletrônico transfronteiriço de pequeno porte.' },
    { id: 'provisoes',      label: 'Provisões de bordo',                   term: 'Stores',                          hint: 'Provisões de bordo — combustíveis, alimentos e suprimentos embarcados em navios e aeronaves para consumo durante a viagem. Não é mercadoria destinada a um mercado.' },
    { id: 'socorro',        label: 'Remessas de socorro',                  term: 'Relief consignments',             hint: 'Remessas de ajuda humanitária e socorro (doações, situações de emergência), normalmente isentas de tributos e fora da lógica comercial de mercado.' },
    { id: 'cpc-nes',        label: 'CPC não especificado',                 term: 'CPC N.E.S.',                      hint: 'Procedimento aduaneiro não especificado nas demais categorias (Not Elsewhere Specified). Agrupa operações sem classificação própria — interprete com cautela.' },
    { id: 'total-cpc',      label: 'Total CPC',                            term: 'TOTAL CPC',                       hint: 'Linha de agregação que soma todos os procedimentos aduaneiros. Use com cuidado: evita-se somá-la às categorias específicas para não duplicar valores.' },
  ];
  window.ENRICH_FLOWS = [
    { id: 'imports',          label: 'Importações',                          term: 'Imports',                              hint: 'Entrada de mercadorias estrangeiras no território nacional, qualquer que seja o destino (consumo, estoque ou industrialização). É a contagem mais ampla de importação.' },
    { id: 'exports',          label: 'Exportações',                          term: 'Exports',                              hint: 'Saída de mercadorias do país para o exterior. Pode englobar tanto a produção nacional quanto reexportações, conforme o nível de detalhamento da fonte.' },
    { id: 'dom-export',       label: 'Exportação nacional',                  term: 'Domestic Export',                      hint: 'Exportação de mercadoria efetivamente produzida no país (origem nacional), distinguindo-a da simples reexportação de bens importados. É o que mede a competitividade da produção interna.' },
    { id: 'for-import',       label: 'Importação estrangeira',               term: 'Foreign Import',                       hint: 'Importação de mercadoria de origem estrangeira que ingressa no país — a contrapartida, no Brasil, da exportação nacional feita pelo país parceiro.' },
    { id: 'imp-inward',       label: 'Import. p/ aperfeiç. ativo',           term: 'Import for inward processing',         hint: 'Importação de insumos destinados a serem industrializados ou beneficiados internamente e depois reexportados. Sinaliza demanda industrial, e não consumo do mercado interno.' },
    { id: 'imp-after-outward',label: 'Import. após aperfeiç. passivo',       term: 'Import after outward processing',      hint: 'Reentrada da mercadoria que foi enviada ao exterior para beneficiamento e retorna já processada. O ganho de valor ocorreu fora do país.' },
    { id: 'reimport',         label: 'Reimportação',                        term: 'Re-import',                            hint: 'Reentrada no país de mercadoria que havia sido exportada, sem transformação no exterior (ex.: devoluções). Não caracteriza nova importação para consumo.' },
    { id: 'reexport',         label: 'Reexportação',                        term: 'Re-export',                            hint: 'Reexportação de mercadoria que havia sido importada, sem ter sido transformada no país. Indica papel de entreposto ou intermediação comercial, não de produção própria.' },
    { id: 'exp-after-inward', label: 'Export. após aperfeiç. ativo',         term: 'Export after inward processing',       hint: 'Exportação do produto resultante de insumos importados e beneficiados internamente. É a exportação com valor agregado pela indústria nacional — o caso mais relevante de mercado industrial.' },
    { id: 'exp-for-outward',  label: 'Export. p/ aperfeiç. passivo',         term: 'Export for outward processing',        hint: 'Exportação temporária de um bem para ser beneficiado no exterior, com previsão de retorno. O beneficiamento (e a agregação de valor) acontece fora do país.' },
  ];

  window.enrichment = {
    // Editor reads the DRAFT (in-progress) worklist; analyses read the APPLIED log.
    codes: () => worklist(draft),       // the LEFT JOIN result (data ⟕ classification)
    worklist: () => worklist(draft),    // explicit alias — same join
    regimes: () => window.ENRICH_REGIMES,
    flowTypes: () => window.ENRICH_FLOWS,
    pairMarket: (regimeId, flowId) => draft.pairMarkets[regimeId + ':' + flowId] || null,
    levelLabel: (id) => (window.ENRICH_LEVELS.find(l => l.id === id) || {}).label || id,
    levelColor: (id) => (window.ENRICH_LEVELS.find(l => l.id === id) || {}).color || 'var(--fg-3)',
    groupLabel: (id) => (window.ENRICH_GROUPS.find(g => g.id === id) || {}).label || id,
    // Chapter is DERIVED from the code itself (no stored field, no cross-banco
    // logic): NCM/HS by leading 2 digits, IBGE by its own product group. New
    // codes fall into their chapter automatically by prefix.
    chapterOf(source, code) {
      if (source === 'ibge_pevs') {
        const s = String(code).split('.')[0];
        return ({ '1': 'Produtos alimentícios', '2': 'Produtos madeireiros' })[s] || ('Grupo ' + s);
      }
      const ch = String(code).slice(0, 2);
      return ({ '08': '08 · Frutas e castanhas', '44': '44 · Madeira e carvão', '20': '20 · Preparações de frutas' })[ch] || (ch + ' · Outros');
    },

    // Edit the classification log (the RIGHT side). Setting an empty level
    // removes the log row — the code falls back to "a classificar" in the join.
    setCode(id, patch) {
      if (!patch || !('level' in patch)) return;
      if (patch.level) draft.classifications[id] = patch.level;
      else delete draft.classifications[id];
      notify();
    },
    setPair(regimeId, flowId, market) {
      const k = regimeId + ':' + flowId;
      if (market) draft.pairMarkets[k] = market; else delete draft.pairMarkets[k];
      notify();
    },

    // ── Draft → Applied commit lifecycle ──────────────────────────────
    pendingCount() {
      let n = 0;
      GOLD_CODES.forEach(g => { if ((draft.classifications[g.id] || null) !== (applied.classifications[g.id] || null)) n++; });
      const keys = new Set([...Object.keys(draft.pairMarkets), ...Object.keys(applied.pairMarkets)]);
      keys.forEach(k => { if ((draft.pairMarkets[k] || null) !== (applied.pairMarkets[k] || null)) n++; });
      return n;
    },
    isDirty() { return this.pendingCount() > 0; },
    isCommitting: () => committing,
    // Commit draft → applied. ASYNC on purpose: simulates the BigQuery
    // round-trip (INSERT into the append-only SCD2 log, then the live LEFT
    // JOIN the analyses read). The button must lock while `committing` is
    // true — a double click would write duplicate revisions to the log.
    // In production: await the API write, then re-resolve the join.
    apply(onDone) {
      if (committing || this.pendingCount() === 0) return;
      committing = true;
      notify();                                  // UI: disable + show loading
      setTimeout(() => {
        applied = clone(draft);
        persist();
        committing = false;
        notify();                                // UI: success + re-render grid/analyses
        if (typeof onDone === 'function') { try { onDone(); } catch (e) {} }
      }, COMMIT_MS);
    },
    discard() { if (committing) return; draft = clone(applied); notify(); },

    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },

    // counts for the curation hero (reflect the DRAFT worklist being edited)
    stats() {
      const wl = worklist(draft);
      const byLevel = {};
      window.ENRICH_LEVELS.forEach(l => { byLevel[l.id] = wl.filter(c => c.level === l.id).length; });
      return {
        codesTotal: wl.length,
        byLevel,
        unclassified: wl.filter(c => !c.level).length,   // NULL side of the join
        flowsTotal: window.ENRICH_REGIMES.length * window.ENRICH_FLOWS.length,
        flowsClassified: Object.keys(draft.pairMarkets).length,
      };
    },
  };

  // ── Deterministic synth so analyses are stable across reloads ──────────
  // PRNG lives in synthUtils.js (window.seeded) — no local copy.

  // ── Analysis 1: VALUE ADDED — exports split by industrialization level ─
  //   Aggregates synthetic per-code export series by their CURRENT curated
  //   `level`, so re-classifying a code in Curadoria changes the result.
  //   SHAPE: contracts.js @typedef ValueAddedAnalysis.
  window.valueAddedAnalysis = function (groupId) {
    const codes = worklist(applied).filter(c => c.source === 'mdic_comex' && (!groupId || c.group === groupId) && c.level && c.level !== 'misturado');
    const years = []; for (let y = 1997; y <= 2024; y++) years.push(y);
    const acc = { bruta: years.map(() => ({ v: 0, w: 0 })), processada: years.map(() => ({ v: 0, w: 0 })) };
    codes.forEach(c => {
      const rnd = window.seeded('va:' + c.id);
      const v0 = 0.4 + rnd() * 1.6, vT = v0 * (1.6 + rnd());
      const pricePerKg = c.level === 'processada' ? (2.6 + rnd() * 1.8) : (1.0 + rnd() * 0.6);
      years.forEach((y, i) => {
        const t = i / (years.length - 1);
        const val = (v0 + (vT - v0) * (t * t * (3 - 2 * t))) * (1 + (rnd() - 0.5) * 0.06);  // US$ bi
        const w = (val * 1e9) / pricePerKg / 1e6 / 1000;  // → mil t (val_usd ÷ price ÷ kg→mil t)
        acc[c.level][i].v += val;
        acc[c.level][i].w += w;
      });
    });
    const series = years.map((y, i) => {
      const bV = acc.bruta[i].v, pV = acc.processada[i].v;
      const bW = acc.bruta[i].w || 1, pW = acc.processada[i].w || 1;
      const total = bV + pV || 1;
      const priceB = bV / bW, priceP = pV / pW;
      return { y, brutaV: bV, procV: pV, procShare: (pV / total) * 100, premium: priceB ? priceP / priceB : 0, priceB, priceP };
    });
    return {
      preview: (((window.bancoById && window.bancoById('mdic_comex')) || {}).status !== 'live'), years,
      byLevel: { bruta: acc.bruta.map((d, i) => ({ y: years[i], v: d.v })), processada: acc.processada.map((d, i) => ({ y: years[i], v: d.v })) },
      series,
      nCodes: codes.length,
    };
  };

  // ── Analysis 2: ECONOMIC PURPOSE — trade value by curated purpose ─
  //   SHAPE: contracts.js @typedef MarketNatureAnalysis (markets from ENRICH_MARKETS).
  window.marketNatureAnalysis = function () {
    const years = []; for (let y = 1997; y <= 2024; y++) years.push(y);
    const totals = {}; window.ENRICH_MARKETS.forEach(m => { totals[m.id] = years.map(() => 0); });
    window.ENRICH_REGIMES.forEach(r => window.ENRICH_FLOWS.forEach(f => {
      const market = applied.pairMarkets[r.id + ':' + f.id];
      if (!market || !totals[market]) return;
      const rnd = window.seeded('mn:' + r.id + ':' + f.id);
      const v0 = 1 + rnd() * 5, vT = v0 * (1.4 + rnd());
      years.forEach((y, i) => {
        const t = i / (years.length - 1);
        totals[market][i] += (v0 + (vT - v0) * t) * (1 + (rnd() - 0.5) * 0.08);
      });
    }));
    const series = years.map((y, i) => {
      const o = { y }; window.ENRICH_MARKETS.forEach(m => { o[m.id] = totals[m.id][i]; }); return o;
    });
    const last = series[series.length - 1];
    return { preview: [ 'mdic_comex','un_comtrade' ].some(id => ((window.bancoById && window.bancoById(id)) || {}).status !== 'live'), years, series, latest: last };
  };
})();
