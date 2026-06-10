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
        mdic_comex: [
          ['08012200', 'Castanha-do-pará sem casca', 15.0, 3.6],
          ['08012100', 'Castanha-do-pará com casca',  2.5, 26],
          ['08013200', 'Castanha de caju sem casca',  7.0, 34],
          ['08013100', 'Castanha de caju com casca',  1.4, 41],
          ['08029900', 'Outras castanhas e nozes',    5.0, 9],
        ],
        un_comtrade: [
          ['080122', 'Brazil nuts, shelled',   14.0, 4.2],
          ['080121', 'Brazil nuts, in shell',   2.4, 23],
          ['080132', 'Cashew nuts, shelled',    7.5, 37],
          ['080131', 'Cashew nuts, in shell',   1.5, 44],
          ['080119', 'Coconuts, other',         0.6, 28],
        ],
        sefaz_nf: [
          ['08012200', 'Castanha-do-pará sem casca', 70, 6],
          ['09011110', 'Café não torrado',           22, 130],
          ['18010000', 'Cacau em amêndoas',          16, 38],
          ['44011100', 'Lenha',                      0.3, 820],
        ],
        // IBGE PAM — lavouras. BRL banco (canonFactor=1), so price is R$/kg.
        // volEndKt = end-year production in thousand tonnes. Product codes are
        // ≥5 chars on purpose (ViewProductProfile seeds its UF ranking on
        // code.charCodeAt(4)). Mass family / tonnes, like the generic views expect.
        ibge_pam: [
          ['54011', 'Soja (grão)',       2.0,  152000],
          ['54012', 'Milho (grão)',      1.2,  130000],
          ['54015', 'Cana-de-açúcar',     0.15, 750000],
          ['54013', 'Café (grão)',       25.0,   3700],
          ['54014', 'Algodão (pluma)',    8.0,    7000],
        ],
      },
      // Native year coverage per banco.
      coverage: { mdic_comex: [1997, 2024], un_comtrade: [1988, 2024], sefaz_nf: [2010, 2024], ibge_pam: [1990, 2024] },
      // Fraction of end-year volume reached at the START of coverage (S-curve floor).
      startFrac: { mdic_comex: 0.30, un_comtrade: 0.26, sefaz_nf: 0.42, ibge_pam: 0.38 },
      // Partner ("destino"/"parceiro") universes — typical castanha markets.
      partners: {
        mdic_comex:  ['Peru', 'Bolívia', 'Estados Unidos', 'Alemanha', 'Israel', 'Reino Unido', 'Países Baixos', 'Itália', 'Emirados Árabes Unidos', 'Vietnã'],
        un_comtrade: ['China', 'Estados Unidos', 'Alemanha', 'Países Baixos', 'Vietnã', 'Índia', 'Bolívia', 'Peru', 'Itália', 'Reino Unido'],
        sefaz_nf:    ['SP', 'RJ', 'MG', 'PR', 'RS', 'PA', 'AM', 'CE', 'BA', 'SC'],
      },
      // Origin universes — Brazil-nut belt (North) for MDIC/SEFAZ; reporters for Comtrade.
      origins: {
        mdic_comex:  ['AC', 'AM', 'PA', 'RO', 'AP'],
        un_comtrade: ['Brasil', 'Bolívia', 'Peru', 'Costa do Marfim', 'Vietnã'],
        sefaz_nf:    ['AC', 'AM', 'PA', 'RO', 'MT'],
        // PAM — grain/fibre belt (Centre-West + South + MG).
        ibge_pam:    ['MT', 'PR', 'RS', 'GO', 'MS'],
      },
      // Monthly export seasonality (12 weights): castanha harvest Dec–Mar,
      // shipments peak Mar–Jun, trough Sep–Nov.
      seasonal: {
        mdic_comex: [0.85, 0.95, 1.35, 1.40, 1.30, 1.15, 0.95, 0.80, 0.70, 0.75, 0.80, 1.00],
        sefaz_nf:   [1.05, 1.00, 1.10, 1.05, 1.00, 0.95, 0.92, 0.95, 1.00, 1.05, 1.00, 0.93],
      },
    },

    // ── crossSource.js — synthetic annual series magnitude ranges [v0, vT] ──
    // Keyed by 'banco:metric'. Magnitudes consistent with the single-banco
    // snapshot above (e.g. MDIC exp ~US$0.1–0.46 bi; ~31–114 mil t).
    crossMagnitudes: {
      'mdic_comex:exp_value':     [0.10, 0.46],
      'mdic_comex:imp_value':     [0.02, 0.09],
      'mdic_comex:exp_weight':    [31, 114],
      'un_comtrade:exp_value':    [0.09, 0.42],
      'un_comtrade:imp_value':    [0.03, 0.10],
      'un_comtrade:world_exp':    [3.2, 9.5],
      'sefaz_nf:internal_value':  [42, 181],
      'sefaz_nf:internal_weight': [8100, 26300],
      'sefaz_nf:icms_total':      [6.2, 23.7],
      // IBGE PAM (lavouras) — display-unit magnitudes: R$ bi · mi t · mi ha · kg/ha.
      'ibge_pam:prod_value':      [165, 715],
      'ibge_pam:prod_quantity':   [430, 1060],
      'ibge_pam:area_harvested':  [38, 80],
      'ibge_pam:yield':           [1900, 3500],
    },

    // ── enrichment.js — curation worklist (LEFT side) + seed classifications ──
    enrichment: {
      groups: [
        { id: 'castanha', label: 'Castanha-do-pará' },
        { id: 'madeira',  label: 'Madeira' },
        { id: 'acai',     label: 'Açaí' },
      ],
      // GOLD codes that EXIST in the data (stand-in for SELECT DISTINCT per banco).
      goldCodes: [
        // ── Castanha-do-pará ──
        { id: 'cst-ibge',     group: 'castanha', source: 'ibge_pevs',   code: '1.3',      desc: 'Castanha-do-pará' },
        { id: 'cst-mdic-cc',  group: 'castanha', source: 'mdic_comex',  code: '08012100', desc: 'Castanha-do-pará, fresca ou seca, com casca' },
        { id: 'cst-mdic-sc',  group: 'castanha', source: 'mdic_comex',  code: '08012200', desc: 'Castanha-do-pará, fresca ou seca, sem casca' },
        { id: 'cst-un-0801',  group: 'castanha', source: 'un_comtrade', code: '0801',     desc: 'Nuts, edible; coconuts, Brazil & cashew, fresh/dried' },
        { id: 'cst-un-121',   group: 'castanha', source: 'un_comtrade', code: '080121',   desc: 'Brazil nuts, fresh or dried, in shell' },
        { id: 'cst-un-122',   group: 'castanha', source: 'un_comtrade', code: '080122',   desc: 'Brazil nuts, fresh or dried, shelled' },
        // ── Madeira ──
        { id: 'mad-ibge',     group: 'madeira',  source: 'ibge_pevs',   code: '2.1',      desc: 'Madeira em tora' },
        { id: 'mad-mdic-tor', group: 'madeira',  source: 'mdic_comex',  code: '44032100', desc: 'Madeira em bruto, conífera' },
        { id: 'mad-mdic-ser', group: 'madeira',  source: 'mdic_comex',  code: '44071100', desc: 'Madeira serrada, conífera' },
        { id: 'mad-un-4403',  group: 'madeira',  source: 'un_comtrade', code: '4403',     desc: 'Wood in the rough' },
        { id: 'mad-un-4407',  group: 'madeira',  source: 'un_comtrade', code: '4407',     desc: 'Wood sawn or chipped lengthwise' },
        // ── Açaí ──
        { id: 'aca-ibge',     group: 'acai',     source: 'ibge_pevs',   code: '1.1',      desc: 'Açaí (fruto)' },
        { id: 'aca-mdic-pol', group: 'acai',     source: 'mdic_comex',  code: '20079990', desc: 'Polpa de açaí (preparada)' },
        { id: 'aca-un-2007',  group: 'acai',     source: 'un_comtrade', code: '2007',     desc: 'Jams, fruit jellies, purées & pastes' },
        // ── Códigos que apareceram numa carga recente da Gold, ainda SEM linha no
        //    log de classificação (NULL no LEFT JOIN) → entram "a classificar" ──
        { id: 'cst-mdic-tor', group: 'castanha', source: 'mdic_comex',  code: '20081910', desc: 'Castanha-do-pará torrada / em preparações' },
        { id: 'mad-mdic-comp',group: 'madeira',  source: 'mdic_comex',  code: '44092100', desc: 'Madeira perfilada (sarrafos, molduras)' },
        { id: 'aca-mdic-cong',group: 'acai',     source: 'mdic_comex',  code: '08119000', desc: 'Açaí congelado (fruto, sem adição de açúcar)' },
      ],
      // Seed slice of the append-only classification log (WHERE is_current):
      // industrialization level per code id. Codes absent here → "a classificar".
      seedClassifications: {
        'cst-ibge': 'misturado', 'cst-mdic-cc': 'bruta', 'cst-mdic-sc': 'processada',
        'cst-un-0801': 'misturado', 'cst-un-121': 'bruta', 'cst-un-122': 'processada',
        'mad-ibge': 'bruta', 'mad-mdic-tor': 'bruta', 'mad-mdic-ser': 'processada',
        'mad-un-4403': 'bruta', 'mad-un-4407': 'processada',
        'aca-ibge': 'bruta', 'aca-mdic-pol': 'processada', 'aca-un-2007': 'processada',
      },
    },

    // ── previewData.js · productivityData() — IBGE PAM yield perspective ──
    // The agricultural-productivity demo universe (lavouras). Consumed ONLY by
    // window.productivityData; the generic views read the snapshot block above.
    // To demo other crops, edit here — the view/adapter shape is unchanged.
    pam: {
      yieldUnit: 'kg/ha', areaUnit: 'ha',
      // Per crop: end-year national yield (kg/ha) + harvested area (thousand ha),
      // and the START-of-coverage fraction of each (S-curve floor → end value).
      // `code` matches snapshot.products.ibge_pam so the two stay in lockstep.
      crops: [
        { code: '54011', name: 'Soja',           yieldEnd: 3550,  areaEndKha: 46000, yldStart: 0.60, areaStart: 0.28 },
        { code: '54012', name: 'Milho',          yieldEnd: 5850,  areaEndKha: 22000, yldStart: 0.52, areaStart: 0.46 },
        { code: '54015', name: 'Cana-de-açúcar', yieldEnd: 76000, areaEndKha:  8600, yldStart: 0.80, areaStart: 0.62 },
        { code: '54013', name: 'Café',           yieldEnd: 1750,  areaEndKha:  1850, yldStart: 0.68, areaStart: 0.94 },
        { code: '54014', name: 'Algodão',        yieldEnd: 1850,  areaEndKha:  1700, yldStart: 0.46, areaStart: 0.50 },
      ],
      // UF productivity index relative to the national mean (1.0). High-tech
      // Cerrado/South >1; frontier North/Northeast <1. The adapter joins this
      // onto the canonical UF grid (window.UF_DATA) with seeded per-crop jitter;
      // UFs absent here default to ~0.88. Captures the real yield geography.
      ufProductivity: {
        MT: 1.16, GO: 1.09, MS: 1.10, PR: 1.12, SP: 1.06, MG: 1.05, SC: 1.03, RS: 0.84,
        BA: 0.96, MA: 0.86, PI: 0.83, TO: 0.92, DF: 1.08,
      },
    },
  };
})();
