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
window.PRODUCTS = [
  { code: '49101', name: 'Castanha-do-pará',  unit: 't',  family: 'mass'   },
  { code: '49103', name: 'Açaí (fruto)',      unit: 't',  family: 'mass'   },
  { code: '49105', name: 'Palmito',           unit: 't',  family: 'mass'   },
  { code: '49106', name: 'Amêndoa de babaçu', unit: 't',  family: 'mass'   },
  { code: '49108', name: 'Erva-mate',         unit: 't',  family: 'mass'   },
  { code: '49112', name: 'Pinhão',            unit: 't',  family: 'mass'   },
  { code: '49215', name: 'Madeira em tora',   unit: 'm³', family: 'volume' },
  { code: '49216', name: 'Lenha',             unit: 'm³', family: 'volume' },
  { code: '49218', name: 'Carvão vegetal',    unit: 't',  family: 'mass'   },
  { code: '49221', name: 'Borracha (látex)',  unit: 't',  family: 'mass'   },
  { code: '49222', name: 'Cera de carnaúba',  unit: 't',  family: 'mass'   },
  { code: '49224', name: 'Piaçava (fibra)',   unit: 't',  family: 'mass'   },
];

// Region affinity per PEVS product code — biases the synthetic per-UF
// allocation in ViewProductProfile so each product's UF ranking is plausible
// (castanha/açaí → Norte, erva-mate/pinhão → Sul, etc.). Keyed by the same
// product universe as window.PRODUCTS. Synthetic mock weighting, NOT measured
// data; replaced by a real per-UF aggregate when the Gold table lands. Lives
// HERE (not in the view) so the data layer stays the single source of truth.
window.PRODUCT_REGION_AFFINITY = {
  '49101': { N: 3.4 },              // castanha → Norte
  '49103': { N: 4.0 },              // açaí → Norte
  '49105': { SE: 1.6, S: 1.4 },     // palmito
  '49106': { NE: 3.2 },             // babaçu → Nordeste (MA/PI)
  '49108': { S: 4.2 },              // erva-mate → Sul
  '49112': { S: 5.0 },              // pinhão → Sul
  '49215': { N: 2.4, CO: 1.6 },     // madeira tora
  '49216': { S: 1.6, NE: 1.4 },     // lenha
  '49218': { CO: 2.2, SE: 1.6 },    // carvão → MG/MT
  '49221': { N: 3.0 },              // borracha → Norte (AC)
  '49222': { NE: 4.5 },             // carnaúba → Nordeste (CE/PI)
  '49224': { NE: 3.0 },             // piaçava → Nordeste/Norte
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
    id: 'mass', label: 'Massa', unit: 't', long: 'toneladas', base: 't', color: 'var(--embrapa-green-darker)',
    units: [
      { id: 'kg', label: 'kg',  long: 'quilograma', toBase: 0.001 },
      { id: 't',  label: 't',   long: 'tonelada',   toBase: 1 },
      { id: '@',  label: '@',   long: 'arroba (15 kg)', toBase: 0.015 },
      { id: 'sc', label: 'sc',  long: 'saca (60 kg)',   toBase: 0.06, note: 'Saca de 60 kg (convenção; varia por commodity).' },
    ],
  },
  volume: {
    id: 'volume', label: 'Volume', unit: 'm³', long: 'metros cúbicos', base: 'm³', color: 'var(--pres-yale-blue)',
    units: [
      { id: 'L',  label: 'L',  long: 'litro',       toBase: 0.001 },
      { id: 'hL', label: 'hL', long: 'hectolitro',  toBase: 0.1 },
      { id: 'm³', label: 'm³', long: 'metro cúbico', toBase: 1 },
    ],
  },
  energia: {
    id: 'energia', label: 'Energia', unit: 'MWh', long: 'megawatt-hora', base: 'MWh', color: 'var(--viz-3)',
    units: [
      { id: 'kWh', label: 'kWh', long: 'quilowatt-hora', toBase: 0.001 },
      { id: 'MWh', label: 'MWh', long: 'megawatt-hora',  toBase: 1 },
      { id: 'GJ',  label: 'GJ',  long: 'gigajoule',      toBase: 0.277778 },
      { id: 'boe', label: 'boe', long: 'barril equiv. petróleo', toBase: 1.62803 },
    ],
  },
  contagem: {
    id: 'contagem', label: 'Contagem', unit: 'un', long: 'unidades', base: 'un', color: 'var(--viz-9)',
    units: [
      { id: 'un',       label: 'un',       long: 'unidade',          toBase: 1 },
      { id: 'dz',       label: 'dz',       long: 'dúzia',            toBase: 12 },
      { id: 'milheiro', label: 'milheiro', long: 'milheiro (1.000)', toBase: 1000 },
      { id: 'cab',      label: 'cab',      long: 'cabeça',           toBase: 1 },
    ],
  },
  area: {
    id: 'area', label: 'Área', unit: 'ha', long: 'hectares', base: 'ha', color: 'var(--viz-10)',
    units: [
      { id: 'm²',  label: 'm²',  long: 'metro quadrado',     toBase: 0.0001 },
      { id: 'ha',  label: 'ha',  long: 'hectare',            toBase: 1 },
      { id: 'alq', label: 'alq', long: 'alqueire (~2,42 ha)', toBase: 2.42, note: 'Alqueire paulista; varia por região.' },
    ],
  },
  // INTENSITY family (a ratio: production per unit area). Like every other
  // family it is incommensurable with the rest and MUST NEVER be summed — a
  // yield is averaged (area-weighted), never added. Base = kg/ha; t/ha and
  // sc/ha (60 kg sack per hectare) convert by their mass-per-hectare factor.
  rendimento: {
    id: 'rendimento', label: 'Rendimento', unit: 'kg/ha', long: 'quilogramas por hectare', base: 'kg/ha', color: 'var(--viz-6)',
    intensity: true,
    units: [
      { id: 'kg/ha', label: 'kg/ha', long: 'quilograma por hectare', toBase: 1 },
      { id: 't/ha',  label: 't/ha',  long: 'tonelada por hectare',   toBase: 1000 },
      { id: 'sc/ha', label: 'sc/ha', long: 'saca (60 kg) por hectare', toBase: 60, note: 'Saca de 60 kg/ha (convenção; varia por commodity).' },
    ],
  },
};

// Default display unit per family (used to seed conventions).
window.defaultUnitOf = (familyId) => (window.UNIT_FAMILIES[familyId] || {}).unit || '';
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
  const snap = (bancoId && window.dataStore && window.dataStore.get && window.dataStore.get(bancoId))
            || (bancoId && window.snapshotFor && window.snapshotFor(bancoId))
            || null;
  const products = (snap && snap.products) || window.PRODUCTS || [];
  const famOf = (c) => { const p = products.find(x => x.code === c); return p ? p.family : null; };
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
  const seed = [
    [1986, 0.81, 1320, 58.2], [1987, 0.86, 1418, 60.1],
    [1988, 0.91, 1502, 61.4], [1989, 0.94, 1567, 62.7],
    [1990, 0.99, 1612, 61.9], [1991, 1.07, 1684, 62.4],
    [1992, 1.14, 1748, 63.1], [1993, 1.21, 1791, 62.8],
    [1994, 1.32, 1812, 61.7], [1995, 1.42, 1832, 60.4],
    [1996, 1.51, 1894, 59.8], [1997, 1.63, 1980, 59.1],
    [1998, 1.58, 2031, 58.4], [1999, 1.71, 2120, 57.6],
    [2000, 1.84, 2247, 56.8], [2001, 1.92, 2356, 55.9],
    [2002, 2.08, 2401, 55.1], [2003, 2.27, 2389, 54.3],
    [2004, 2.45, 2478, 53.6], [2005, 2.51, 2502, 52.7],
    [2006, 2.39, 2456, 51.9], [2007, 2.62, 2531, 51.2],
    [2008, 2.84, 2580, 50.4], [2009, 2.71, 2492, 49.6],
    [2010, 3.04, 2640, 48.8], [2011, 3.22, 2698, 48.1],
    [2012, 3.45, 2745, 47.4], [2013, 3.32, 2701, 46.8],
    [2014, 3.51, 2810, 46.2], [2015, 3.27, 2658, 45.7],
    [2016, 3.39, 2701, 45.1], [2017, 3.58, 2780, 44.6],
    [2018, 3.81, 2842, 44.0], [2019, 3.97, 2901, 43.5],
    [2020, 3.62, 2734, 42.8], [2021, 4.12, 2980, 42.4],
    [2022, 4.38, 3041, 42.1], [2023, 4.21, 2952, 41.6],
    [2024, 4.07, 2884, 41.0],
  ];
  return seed.map(([y, v, q_mass, q_vol]) => ({ y, v, q: q_mass, q_mass, q_vol }));
})();

// ────────────────────────────────────────────────────────────────────
// Per-product time series (value, qty) — used for stacked area + product detail
//   value is in R$ milhões, qty in product's native unit (t or m³, ×1000)
// ────────────────────────────────────────────────────────────────────
window.PRODUCT_TS = (() => {
  // Synthetic but plausible trajectories per product
  const profiles = {
    '49215': { v0: 1100, vT: 1431, q0: 28.4, qT: 27.1, family: 'volume' }, // madeira tora
    '49216': { v0: 480,  vT: 758,  q0: 18.2, qT: 14.1, family: 'volume' }, // lenha
    '49103': { v0: 80,   vT: 505,  q0: 110,  qT: 1612, family: 'mass'   }, // açaí (explosivo)
    '49101': { v0: 220,  vT: 379,  q0: 41,   qT: 28,   family: 'mass'   }, // castanha
    '49218': { v0: 410,  vT: 337,  q0: 5800, qT: 4120, family: 'mass'   }, // carvão
    '49108': { v0: 180,  vT: 295,  q0: 260,  qT: 412,  family: 'mass'   }, // erva-mate
    '49221': { v0: 95,   vT: 142,  q0: 28,   qT: 36,   family: 'mass'   }, // borracha
    '49105': { v0: 35,   vT: 78,   q0: 22,   qT: 41,   family: 'mass'   }, // palmito
    '49222': { v0: 41,   vT: 64,   q0: 19,   qT: 24,   family: 'mass'   }, // cera carnaúba
    '49112': { v0: 18,   vT: 31,   q0: 6,    qT: 11,   family: 'mass'   }, // pinhão
    '49106': { v0: 67,   vT: 22,   q0: 102,  qT: 38,   family: 'mass'   }, // babaçu (decline)
    '49224': { v0: 12,   vT: 9,    q0: 8,    qT: 6,    family: 'mass'   }, // piaçava
  };
  const years = window.OVERVIEW_TS.map(d => d.y);
  const out = {};
  Object.entries(profiles).forEach(([code, p]) => {
    const series = years.map((y, i) => {
      const t = i / (years.length - 1);
      // mild noise so series read as real; `n` shifts the phase so value and
      // quantity get distinct (not identical) noise within the same product
      const noise = (n) => 1 + ((Math.sin(i * 1.7 + code.charCodeAt(4) + n * 0.9) * 0.04) + (Math.cos(i * 2.3 + n) * 0.03));
      return {
        y,
        v:   (p.v0 + (p.vT - p.v0) * t) * noise(0),
        q:   (p.q0 + (p.qT - p.q0) * t) * noise(1),
        family: p.family,
      };
    });
    out[code] = series;
  });
  return out;
})();

// ────────────────────────────────────────────────────────────────────
// Geography — Brazilian states and regions
// ────────────────────────────────────────────────────────────────────
window.REGIONS = [
  { id: 'N',  label: 'Norte',         color: 'var(--viz-1)' },
  { id: 'NE', label: 'Nordeste',      color: 'var(--viz-3)' },
  { id: 'CO', label: 'Centro-Oeste',  color: 'var(--viz-5)' },
  { id: 'SE', label: 'Sudeste',       color: 'var(--viz-2)' },
  { id: 'S',  label: 'Sul',           color: 'var(--viz-4)' },
];

// 27 UFs · grid position for tile map (col, row), region, totals (2024)
window.UF_DATA = [
  // North
  { uf: 'RR', name: 'Roraima',       region: 'N',  col: 3, row: 0, value: 28,  q_mass: 12,  q_vol: 0.8 },
  { uf: 'AP', name: 'Amapá',         region: 'N',  col: 5, row: 0, value: 47,  q_mass: 18,  q_vol: 1.4 },
  { uf: 'AM', name: 'Amazonas',      region: 'N',  col: 2, row: 1, value: 614, q_mass: 287, q_vol: 12.4 },
  { uf: 'PA', name: 'Pará',          region: 'N',  col: 4, row: 1, value: 982, q_mass: 412, q_vol: 14.1 },
  { uf: 'AC', name: 'Acre',          region: 'N',  col: 1, row: 2, value: 392, q_mass: 184, q_vol: 1.8 },
  { uf: 'RO', name: 'Rondônia',      region: 'N',  col: 2, row: 2, value: 287, q_mass: 132, q_vol: 2.4 },
  { uf: 'TO', name: 'Tocantins',     region: 'N',  col: 4, row: 2, value: 142, q_mass: 65,  q_vol: 1.1 },
  // Northeast
  { uf: 'MA', name: 'Maranhão',      region: 'NE', col: 5, row: 1, value: 174, q_mass: 82,  q_vol: 2.6 },
  { uf: 'CE', name: 'Ceará',         region: 'NE', col: 6, row: 1, value: 121, q_mass: 58,  q_vol: 0.9 },
  { uf: 'RN', name: 'Rio Grande do Norte', region: 'NE', col: 7, row: 1, value: 38, q_mass: 18, q_vol: 0.4 },
  { uf: 'PI', name: 'Piauí',         region: 'NE', col: 5, row: 2, value: 87,  q_mass: 41,  q_vol: 1.2 },
  { uf: 'PB', name: 'Paraíba',       region: 'NE', col: 7, row: 2, value: 31,  q_mass: 14,  q_vol: 0.3 },
  { uf: 'BA', name: 'Bahia',         region: 'NE', col: 5, row: 3, value: 184, q_mass: 84,  q_vol: 1.9 },
  { uf: 'PE', name: 'Pernambuco',    region: 'NE', col: 6, row: 3, value: 67,  q_mass: 31,  q_vol: 0.6 },
  { uf: 'AL', name: 'Alagoas',       region: 'NE', col: 6, row: 4, value: 21,  q_mass: 9,   q_vol: 0.2 },
  { uf: 'SE', name: 'Sergipe',       region: 'NE', col: 5, row: 5, value: 18,  q_mass: 8,   q_vol: 0.2 },
  // Center-West
  { uf: 'MT', name: 'Mato Grosso',   region: 'CO', col: 3, row: 3, value: 538, q_mass: 240, q_vol: 8.7 },
  { uf: 'MS', name: 'Mato Grosso do Sul', region: 'CO', col: 3, row: 4, value: 71, q_mass: 32, q_vol: 1.3 },
  { uf: 'GO', name: 'Goiás',         region: 'CO', col: 4, row: 4, value: 124, q_mass: 56,  q_vol: 2.1 },
  { uf: 'DF', name: 'Distrito Federal', region: 'CO', col: 4, row: 5, value: 4, q_mass: 2, q_vol: 0.1 },
  // Southeast
  { uf: 'MG', name: 'Minas Gerais',  region: 'SE', col: 5, row: 4, value: 219, q_mass: 98,  q_vol: 4.2 },
  { uf: 'ES', name: 'Espírito Santo', region: 'SE', col: 6, row: 5, value: 48, q_mass: 22, q_vol: 0.7 },
  { uf: 'RJ', name: 'Rio de Janeiro', region: 'SE', col: 5, row: 6, value: 19, q_mass: 8,  q_vol: 0.3 },
  { uf: 'SP', name: 'São Paulo',     region: 'SE', col: 4, row: 6, value: 81,  q_mass: 37,  q_vol: 1.4 },
  // South
  { uf: 'PR', name: 'Paraná',        region: 'S',  col: 3, row: 6, value: 178, q_mass: 81,  q_vol: 2.8 },
  { uf: 'SC', name: 'Santa Catarina', region: 'S', col: 3, row: 7, value: 102, q_mass: 47, q_vol: 1.6 },
  { uf: 'RS', name: 'Rio Grande do Sul', region: 'S', col: 3, row: 8, value: 156, q_mass: 71, q_vol: 2.4 },
];

window.TOP_UFS = window.UF_DATA
  .slice()
  .sort((a, b) => b.value - a.value)
  .slice(0, 8);

// Top municípios (2024) — synthesized
window.TOP_MUNICIPIOS = [
  { city: 'Marabá',       uf: 'PA', value: 198, q_mass: 84, product: 'Castanha-do-pará' },
  { city: 'Santarém',     uf: 'PA', value: 167, q_mass: 0,  q_vol: 4.8, product: 'Madeira em tora' },
  { city: 'Manaus',       uf: 'AM', value: 142, q_mass: 61, product: 'Castanha-do-pará' },
  { city: 'Sinop',        uf: 'MT', value: 128, q_mass: 0,  q_vol: 3.4, product: 'Madeira em tora' },
  { city: 'Rio Branco',   uf: 'AC', value: 119, q_mass: 52, product: 'Borracha (látex)' },
  { city: 'Curitibanos',  uf: 'SC', value:  87, q_mass: 38, product: 'Erva-mate' },
  { city: 'Belém',        uf: 'PA', value:  82, q_mass: 0,  q_vol: 2.1, product: 'Madeira em tora' },
  { city: 'Porto Velho',  uf: 'RO', value:  74, q_mass: 32, product: 'Castanha-do-pará' },
  { city: 'Tefé',         uf: 'AM', value:  68, q_mass: 28, product: 'Açaí (fruto)' },
  { city: 'Erechim',      uf: 'RS', value:  61, q_mass: 26, product: 'Erva-mate' },
];

// Region totals (2024) — sum from UF_DATA
window.REGION_DATA = (() => {
  const map = new Map(window.REGIONS.map(r => [r.id, { ...r, value: 0, q_mass: 0, q_vol: 0, ufs: 0 }]));
  window.UF_DATA.forEach(u => {
    const r = map.get(u.region);
    r.value += u.value; r.q_mass += u.q_mass; r.q_vol += u.q_vol; r.ufs += 1;
  });
  return [...map.values()];
})();

// ────────────────────────────────────────────────────────────────────
// Top products composition (2024) for donut
// ────────────────────────────────────────────────────────────────────
window.TOP_PRODUCTS = [
  { name: 'Madeira em tora',  share: 0.34, value: 1431, color: 'var(--viz-1)' },
  { name: 'Lenha',            share: 0.18, value: 758,  color: 'var(--viz-2)' },
  { name: 'Açaí (fruto)',     share: 0.12, value: 505,  color: 'var(--viz-3)' },
  { name: 'Castanha-do-pará', share: 0.09, value: 379,  color: 'var(--viz-4)' },
  { name: 'Carvão vegetal',   share: 0.08, value: 337,  color: 'var(--viz-5)' },
  { name: 'Erva-mate',        share: 0.07, value: 295,  color: 'var(--viz-7)' },
  { name: 'Outros',           share: 0.12, value: 506,  color: 'var(--pres-gray-200)', muted: true },
];

// ────────────────────────────────────────────────────────────────────
// Quality dimension — flag distribution
// ────────────────────────────────────────────────────────────────────
window.QUALITY_FLAGS = [
  { id: 'OK',                 label: 'OK',                  color: 'var(--ok)',     count: 9_421_802, share: 0.842 },
  { id: 'ESTIMATED',          label: 'Estimado',            color: 'var(--viz-4)',  count: 538_104,   share: 0.048 },
  { id: 'MISSING_VALUE',      label: 'Valor ausente',       color: 'var(--warn)',   count: 412_730,   share: 0.037 },
  { id: 'MISSING_QUANTITY',   label: 'Quantidade ausente',  color: 'var(--info)',   count: 287_412,   share: 0.026 },
  { id: 'BOUNDARY_HISTORIC',  label: 'Limite histórico',    color: 'var(--viz-7)',  count: 312_488,   share: 0.028 },
  { id: 'OUTLIER',            label: 'Outlier',             color: 'var(--err)',    count: 204_891,   share: 0.019 },
];

// Quality % over years (rate of OK rows)
window.QUALITY_TS = window.OVERVIEW_TS.map((d, i) => {
  // Newer data tends to be cleaner
  const t = i / (window.OVERVIEW_TS.length - 1);
  const ok = 0.71 + t * 0.18 + Math.sin(i * 1.3) * 0.015;
  const missing_value     = (0.14 - t * 0.08) + Math.cos(i * 0.9) * 0.01;
  const missing_quantity  = (0.07 - t * 0.04) + Math.cos(i * 1.4) * 0.008;
  const estimated         = 0.04 + Math.sin(i * 0.7) * 0.008;
  const outlier           = 0.02 + Math.cos(i * 2.1) * 0.006;
  const boundary          = Math.max(0, 1 - ok - missing_value - missing_quantity - estimated - outlier);
  return { y: d.y, ok, missing_value, missing_quantity, estimated, outlier, boundary };
});

// Quality by product (2023, share of rows per flag)
window.QUALITY_BY_PRODUCT = [
  { code: '49101', name: 'Castanha-do-pará',  OK: 0.78, MISSING_VALUE: 0.09, MISSING_QUANTITY: 0.05, ESTIMATED: 0.04, OUTLIER: 0.02, BOUNDARY_HISTORIC: 0.02 },
  { code: '49103', name: 'Açaí (fruto)',      OK: 0.91, MISSING_VALUE: 0.03, MISSING_QUANTITY: 0.02, ESTIMATED: 0.02, OUTLIER: 0.01, BOUNDARY_HISTORIC: 0.01 },
  { code: '49108', name: 'Erva-mate',         OK: 0.94, MISSING_VALUE: 0.02, MISSING_QUANTITY: 0.01, ESTIMATED: 0.02, OUTLIER: 0.005, BOUNDARY_HISTORIC: 0.005 },
  { code: '49215', name: 'Madeira em tora',   OK: 0.86, MISSING_VALUE: 0.05, MISSING_QUANTITY: 0.03, ESTIMATED: 0.03, OUTLIER: 0.02, BOUNDARY_HISTORIC: 0.01 },
  { code: '49216', name: 'Lenha',             OK: 0.83, MISSING_VALUE: 0.07, MISSING_QUANTITY: 0.04, ESTIMATED: 0.03, OUTLIER: 0.02, BOUNDARY_HISTORIC: 0.01 },
  { code: '49218', name: 'Carvão vegetal',    OK: 0.89, MISSING_VALUE: 0.04, MISSING_QUANTITY: 0.02, ESTIMATED: 0.03, OUTLIER: 0.01, BOUNDARY_HISTORIC: 0.01 },
  { code: '49221', name: 'Borracha (látex)',  OK: 0.71, MISSING_VALUE: 0.12, MISSING_QUANTITY: 0.07, ESTIMATED: 0.05, OUTLIER: 0.03, BOUNDARY_HISTORIC: 0.02 },
  { code: '49105', name: 'Palmito',           OK: 0.68, MISSING_VALUE: 0.14, MISSING_QUANTITY: 0.09, ESTIMATED: 0.05, OUTLIER: 0.02, BOUNDARY_HISTORIC: 0.02 },
  { code: '49222', name: 'Cera de carnaúba',  OK: 0.72, MISSING_VALUE: 0.11, MISSING_QUANTITY: 0.08, ESTIMATED: 0.04, OUTLIER: 0.03, BOUNDARY_HISTORIC: 0.02 },
  { code: '49106', name: 'Amêndoa de babaçu', OK: 0.64, MISSING_VALUE: 0.17, MISSING_QUANTITY: 0.10, ESTIMATED: 0.05, OUTLIER: 0.02, BOUNDARY_HISTORIC: 0.02 },
  { code: '49112', name: 'Pinhão',            OK: 0.80, MISSING_VALUE: 0.08, MISSING_QUANTITY: 0.05, ESTIMATED: 0.04, OUTLIER: 0.02, BOUNDARY_HISTORIC: 0.01 },
  { code: '49224', name: 'Piaçava (fibra)',   OK: 0.66, MISSING_VALUE: 0.15, MISSING_QUANTITY: 0.09, ESTIMATED: 0.05, OUTLIER: 0.03, BOUNDARY_HISTORIC: 0.02 },
];

// Quality issues by UF (2024) — % rows not OK
window.QUALITY_BY_UF = window.UF_DATA.map((u, i) => {
  const base = 0.04 + ((u.value < 50) ? 0.15 : 0) + ((u.region === 'N' || u.region === 'NE') ? 0.06 : 0);
  return {
    uf: u.uf,
    name: u.name,
    region: u.region,
    col: u.col, row: u.row,
    not_ok: Math.min(0.42, base + Math.sin(i * 1.3) * 0.03),
  };
});

// ────────────────────────────────────────────────────────────────────
// Sample table rows (gold_pevs_production recent rows)
// ────────────────────────────────────────────────────────────────────
window.SAMPLE_ROWS = [
  { year: 2023, uf: 'PA', city: 'Marabá',     product: 'Castanha-do-pará', qty: 14829, unit: 't',  val_ipca: 82471220,  val_yearfx: 78213900,  flag: 'OK' },
  { year: 2023, uf: 'AM', city: 'Manaus',     product: 'Castanha-do-pará', qty: 9314,  unit: 't',  val_ipca: 51038910,  val_yearfx: 48910420,  flag: 'OK' },
  { year: 2023, uf: 'AC', city: 'Rio Branco', product: 'Castanha-do-pará', qty: 3207,  unit: 't',  val_ipca: null,      val_yearfx: null,      flag: 'MISSING_VALUE' },
  { year: 2023, uf: 'RO', city: 'Porto Velho', product: 'Castanha-do-pará', qty: 2118, unit: 't',  val_ipca: 11092480,  val_yearfx: 10721090,  flag: 'OK' },
  { year: 2023, uf: 'PA', city: 'Santarém',   product: 'Madeira em tora',  qty: 47820, unit: 'm³', val_ipca: 198470100, val_yearfx: 191207800, flag: 'OK' },
  { year: 2023, uf: 'MT', city: 'Sinop',      product: 'Madeira em tora',  qty: 31204, unit: 'm³', val_ipca: 128471000, val_yearfx: 123092600, flag: 'OK' },
  { year: 2023, uf: 'RR', city: 'Caracaraí',  product: 'Madeira em tora',  qty: null,  unit: 'm³', val_ipca: 4218900,   val_yearfx: 4080010,   flag: 'MISSING_QUANTITY' },
];

// ────────────────────────────────────────────────────────────────────
// Formatters
// ────────────────────────────────────────────────────────────────────
window.fmtBRL = (n) => {
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
window.numBR = (v, d = 0) =>
  (v == null ? '—' : v.toLocaleString('pt-BR', { maximumFractionDigits: d, minimumFractionDigits: d }));
window.pctBR = (v, d = 1) => window.numBR(v, d) + '%';

// Compact row-counter label (mi / mil) for provenance "Linhas" readouts.
// Shared by MainScreen + ViewHealth (was duplicated verbatim in both).
window.fmtRows = (n) => {
  if (n >= 1e6) return (n / 1e6).toFixed(1).replace('.', ',') + ' mi';
  if (n >= 1e3) return (n / 1e3).toFixed(0) + ' mil';
  return n.toLocaleString('pt-BR');
};

// Compact axis-TICK formatter (mil/mi/bi/tri). Ticks are scale guides, not
// data: full pt-BR numbers (e.g. "4.534.380.148") overflow the ~30px gutter
// and get clipped. Abbreviating ONLY the ticks fixes the clip without touching
// KPIs/tables. Shared by every hand-rolled SVG chart (was duplicated as
// _fmtAxisNum in Charts.jsx and _csFmtAxis in Charts.cross.jsx).
window.fmtAxisTick = (v) => {
  if (v == null || isNaN(v)) return '';
  const a = Math.abs(v);
  if (a === 0) return '0';
  if (a < 1) return v.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  // 1–10: keep one decimal so small-scale axes (e.g. US$/kg, ticks at
  // 0,57 · 1,14 · 1,72) don't collapse to duplicate integers ("2 · 2").
  if (a < 10) return v.toLocaleString('pt-BR', { maximumFractionDigits: 1 });
  if (a < 1000) return v.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
  const U = [[1e12, ' tri'], [1e9, ' bi'], [1e6, ' mi'], [1e3, ' mil']];
  for (const [div, suf] of U) {
    if (a >= div) {
      const n = v / div;
      const s = (Math.abs(n) >= 100 || Number.isInteger(n)) ? n.toFixed(0) : n.toFixed(1);
      return s.replace('.', ',') + suf;
    }
  }
  return v.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
};
