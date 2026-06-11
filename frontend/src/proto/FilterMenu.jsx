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

const { useState, useMemo } = React;

// --- Domain data ---------------------------------------------------
// The product list is now resolved PER BANCO inside the component (see `PRODS`),
// from the active banco's snapshot — so there is no module-level PEVS copy.

// Quality flags derive from the single source of truth (window.QUALITY_FLAGS
// in data.js) so the labels shown here, in the chip bar and in the Qualidade
// view never drift apart. The raw flag token (data_quality_flag) is still
// surfaced verbatim alongside each pt-BR label.
// Period bounds derive from the ACTIVE banco's live time series — resolved
// PER BANCO inside the component (see `yearBounds`/`quickRanges` below), never
// from a module-level snapshot read at import time (which froze to whichever
// banco loaded first and to the synthetic 1986/2024 fallback). Switching banco
// now shifts the date bounds + quick-ranges. The pair below is only the
// last-resort fallback used when no snapshot exists yet for the banco.
const YEAR_START_FALLBACK = 1986;
const YEAR_END_FALLBACK   = 2024;

// Compute the [start, end] year span from a banco snapshot's overview series,
// falling back to the synthetic span when the snapshot is absent/empty.
function bancoYearBounds(snap) {
  const ts = (snap && snap.overviewTS) || null;
  if (!ts || ts.length === 0) return [YEAR_START_FALLBACK, YEAR_END_FALLBACK];
  return [ts[0]?.y || YEAR_START_FALLBACK, ts[ts.length - 1]?.y || YEAR_END_FALLBACK];
}

// Derive the quick-range presets from a [start, end] span (never hardcode the
// span) so changing the source dataset shifts the chips + date bounds with it.
function buildQuickRanges(yearStart, yearEnd) {
  return [
    { id: 'all',  label: 'Tudo',    start: `${yearStart}-01`,   end: `${yearEnd}-12` },
    { id: '30a',  label: '30 anos', start: `${yearEnd - 29}-01`, end: `${yearEnd}-12` },
    { id: '20a',  label: '20 anos', start: `${yearEnd - 19}-01`, end: `${yearEnd}-12` },
    { id: '10a',  label: '10 anos', start: `${yearEnd - 9}-01`,  end: `${yearEnd}-12` },
    { id: '5a',   label: '5 anos',  start: `${yearEnd - 4}-01`,  end: `${yearEnd}-12` },
  ];
}

const QUALITY_CHIP = {
  OK: 'ok', ESTIMATED: 'info', MISSING_VALUE: 'warn',
  MISSING_QUANTITY: 'info', BOUNDARY_HISTORIC: 'muted', OUTLIER: 'err',
};
const QUALITY = (window.QUALITY_FLAGS || []).map(f => ({
  flag: f.id,
  label: f.label,
  chip: QUALITY_CHIP[f.id] || 'muted',
}));
const qualityLabelOf = (id) => {
  const f = QUALITY.find(x => x.flag === id);
  return f ? f.label : id;
};

// Nations — producer + main PEVS export destinations.
const NATIONS = [
  { iso: 'BR', name: 'Brasil',        role: 'produtor' },
  { iso: 'CN', name: 'China',         role: 'destino'  },
  { iso: 'US', name: 'Estados Unidos',role: 'destino'  },
  { iso: 'DE', name: 'Alemanha',      role: 'destino'  },
  { iso: 'NL', name: 'Países Baixos', role: 'destino'  },
  { iso: 'FR', name: 'França',        role: 'destino'  },
  { iso: 'IT', name: 'Itália',        role: 'destino'  },
  { iso: 'GB', name: 'Reino Unido',   role: 'destino'  },
  { iso: 'ES', name: 'Espanha',       role: 'destino'  },
  { iso: 'JP', name: 'Japão',         role: 'destino'  },
  { iso: 'AR', name: 'Argentina',     role: 'destino'  },
  { iso: 'CL', name: 'Chile',         role: 'destino'  },
];

// Brazil's 5 macro-regions. Linked to BR nation.
const FM_REGIONS = [
  { id: 'N',  name: 'Norte',        nation: 'BR' },
  { id: 'NE', name: 'Nordeste',     nation: 'BR' },
  { id: 'CO', name: 'Centro-Oeste', nation: 'BR' },
  { id: 'SE', name: 'Sudeste',      nation: 'BR' },
  { id: 'S',  name: 'Sul',          nation: 'BR' },
];

// Brazil's 27 states (UFs), linked to their region.
const STATES = [
  { uf: 'AC', name: 'Acre',                region: 'N'  },
  { uf: 'AP', name: 'Amapá',               region: 'N'  },
  { uf: 'AM', name: 'Amazonas',            region: 'N'  },
  { uf: 'PA', name: 'Pará',                region: 'N'  },
  { uf: 'RO', name: 'Rondônia',            region: 'N'  },
  { uf: 'RR', name: 'Roraima',             region: 'N'  },
  { uf: 'TO', name: 'Tocantins',           region: 'N'  },
  { uf: 'AL', name: 'Alagoas',             region: 'NE' },
  { uf: 'BA', name: 'Bahia',               region: 'NE' },
  { uf: 'CE', name: 'Ceará',               region: 'NE' },
  { uf: 'MA', name: 'Maranhão',            region: 'NE' },
  { uf: 'PB', name: 'Paraíba',             region: 'NE' },
  { uf: 'PE', name: 'Pernambuco',          region: 'NE' },
  { uf: 'PI', name: 'Piauí',               region: 'NE' },
  { uf: 'RN', name: 'Rio Grande do Norte', region: 'NE' },
  { uf: 'SE', name: 'Sergipe',             region: 'NE' },
  { uf: 'DF', name: 'Distrito Federal',    region: 'CO' },
  { uf: 'GO', name: 'Goiás',               region: 'CO' },
  { uf: 'MT', name: 'Mato Grosso',         region: 'CO' },
  { uf: 'MS', name: 'Mato Grosso do Sul',  region: 'CO' },
  { uf: 'ES', name: 'Espírito Santo',      region: 'SE' },
  { uf: 'MG', name: 'Minas Gerais',        region: 'SE' },
  { uf: 'RJ', name: 'Rio de Janeiro',      region: 'SE' },
  { uf: 'SP', name: 'São Paulo',           region: 'SE' },
  { uf: 'PR', name: 'Paraná',              region: 'S'  },
  { uf: 'RS', name: 'Rio Grande do Sul',   region: 'S'  },
  { uf: 'SC', name: 'Santa Catarina',      region: 'S'  },
];

// Sample of leading PEVS-producing municipalities. (~40 from real PEVS data.)
const MUNICIPALITIES = [
  // Norte
  { code: '1302603', name: 'Manaus',         uf: 'AM' },
  { code: '1501402', name: 'Belém',          uf: 'PA' },
  { code: '1503606', name: 'Itacoatiara',    uf: 'AM' },
  { code: '1507300', name: 'Marabá',         uf: 'PA' },
  { code: '1506807', name: 'Santarém',       uf: 'PA' },
  { code: '1504208', name: 'Parintins',      uf: 'AM' },
  { code: '1100205', name: 'Porto Velho',    uf: 'RO' },
  { code: '1100122', name: 'Cacoal',         uf: 'RO' },
  { code: '1200401', name: 'Rio Branco',     uf: 'AC' },
  { code: '1600303', name: 'Macapá',         uf: 'AP' },
  { code: '1400100', name: 'Boa Vista',      uf: 'RR' },
  { code: '1721000', name: 'Palmas',         uf: 'TO' },
  { code: '1505031', name: 'Oriximiná',      uf: 'PA' },
  // Nordeste
  { code: '2111300', name: 'São Luís',       uf: 'MA' },
  { code: '2105302', name: 'Imperatriz',     uf: 'MA' },
  { code: '2101400', name: 'Bacabal',        uf: 'MA' },
  { code: '2211001', name: 'Teresina',       uf: 'PI' },
  { code: '2927408', name: 'Salvador',       uf: 'BA' },
  { code: '2304400', name: 'Fortaleza',      uf: 'CE' },
  { code: '2611606', name: 'Recife',         uf: 'PE' },
  { code: '2102309', name: 'Caxias',         uf: 'MA' },
  // Centro-Oeste
  { code: '5103403', name: 'Cuiabá',         uf: 'MT' },
  { code: '5108402', name: 'Sinop',          uf: 'MT' },
  { code: '5002704', name: 'Campo Grande',   uf: 'MS' },
  { code: '5208707', name: 'Goiânia',        uf: 'GO' },
  { code: '5300108', name: 'Brasília',       uf: 'DF' },
  // Sudeste
  { code: '3550308', name: 'São Paulo',      uf: 'SP' },
  { code: '3304557', name: 'Rio de Janeiro', uf: 'RJ' },
  { code: '3106200', name: 'Belo Horizonte', uf: 'MG' },
  { code: '3205309', name: 'Vitória',        uf: 'ES' },
  { code: '3157807', name: 'Uberlândia',     uf: 'MG' },
  // Sul
  { code: '4106902', name: 'Curitiba',       uf: 'PR' },
  { code: '4314902', name: 'Porto Alegre',   uf: 'RS' },
  { code: '4205407', name: 'Florianópolis',  uf: 'SC' },
  { code: '4106407', name: 'Cascavel',       uf: 'PR' },
  { code: '4307005', name: 'Erechim',        uf: 'RS' },
  { code: '4304572', name: 'Caxias do Sul',  uf: 'RS' },
  { code: '4209102', name: 'Lages',          uf: 'SC' },
];

// Name universe the município picker can address — read by dataFilters so a
// município the picker can't address (data leader outside this partial list)
// stays governed by the UF filter alone instead of being wrongly excluded.
window.MUNI_PICKER_NAMES = new Set(MUNICIPALITIES.map(m => m.name));

// ----- icons ------------------------------------------------------
const I = {
  filter: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 5h18l-7 9v6l-4-2v-4z"/>
    </svg>
  ),
  close: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 6l12 12M18 6L6 18"/>
    </svg>
  ),
  arrow: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M13 6l6 6-6 6"/>
    </svg>
  ),
  pencil: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 20h4l10-10-4-4L4 16zM14 6l4 4"/>
    </svg>
  ),
  search: (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="6"/><path d="M20 20l-4-4"/>
    </svg>
  ),
  cascade: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 6h8M8 12h6M8 18h4M4 6v.01M4 12v.01M4 18v.01"/>
    </svg>
  ),
};

// ----- inline search input ----------------------------------------
function SearchInput({ value, onChange, placeholder }) {
  return (
    <span className="fm-search">
      <span className="fm-search-icn">{I.search}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || 'Buscar…'}
      />
      {value && (
        <button className="fm-search-clear" onClick={() => onChange('')} aria-label="Limpar busca">
          ×
        </button>
      )}
    </span>
  );
}

// ----- bulk actions row -------------------------------------------
function BulkActions({ all, none, invert, selectedCount, totalCount, compact }) {
  return (
    <div className={'fm-bulk' + (compact ? ' compact' : '')}>
      <button type="button" onClick={all} disabled={selectedCount === totalCount}>
        Selecionar tudo
      </button>
      <span className="sep-dot" aria-hidden="true"></span>
      <button type="button" onClick={none} disabled={selectedCount === 0}>
        Limpar
      </button>
      <span className="sep-dot" aria-hidden="true"></span>
      <button type="button" onClick={invert}>
        Inverter
      </button>
    </div>
  );
}

// ----- reusable column for the geography cascade -----------------
function GeoColumn({
  title, items, keyAttr, displayAttr, getMeta,
  selected, setSelected,
  search, setSearch,
  disabledReason, emptyAllNote,
}) {
  const filtered = useMemo(() => {
    if (!search) return items;
    const q = search.toLowerCase();
    return items.filter(x =>
      x[displayAttr].toLowerCase().includes(q) ||
      (x[keyAttr] && String(x[keyAttr]).toLowerCase().includes(q))
    );
  }, [items, search, displayAttr, keyAttr]);

  const toggle = (val) => {
    const next = new Set(selected);
    next.has(val) ? next.delete(val) : next.add(val);
    setSelected(next);
  };

  // Bulk actions operate on the SEARCH-FILTERED ("visible") items, so e.g.
  // searching "Pa" then "Limpar" only clears matches — never the whole Set.
  // With no search, `filtered` === items, so behaviour is unchanged.
  const visKeys = filtered.map(x => x[keyAttr]);
  const visSet  = new Set(visKeys);
  const allOn   = () => setSelected(new Set([...selected, ...visKeys]));
  const allOff  = () => setSelected(new Set([...selected].filter(k => !visSet.has(k))));
  const allInv  = () => { const n = new Set(selected); visKeys.forEach(k => n.has(k) ? n.delete(k) : n.add(k)); setSelected(n); };

  return (
    <div className="fm-geo-col">
      <div className="fm-geo-col-head">
        <span className="fm-geo-title">{title}</span>
        <span className="fm-geo-count">
          <strong>{selected.size}</strong>/{items.length}
        </span>
      </div>

      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder={`Buscar em ${title.toLowerCase()}…`}
      />

      <div className="fm-geo-list">
        {disabledReason && (
          <div className="fm-geo-empty">
            <span className="fm-cascade-icn">{I.cascade}</span>
            {disabledReason}
          </div>
        )}
        {!disabledReason && emptyAllNote && selected.size === 0 && (
          <div className="fm-geo-allnote">{emptyAllNote}</div>
        )}
        {!disabledReason && filtered.length === 0 && (
          <div className="fm-geo-empty">Nenhum resultado.</div>
        )}
        {!disabledReason && filtered.map(item => {
          const on = selected.has(item[keyAttr]);
          const meta = getMeta ? getMeta(item) : null;
          return (
            <label key={item[keyAttr]} className={'fm-check geo' + (on ? ' is-on' : '')}>
              <input type="checkbox" checked={on}
                     onChange={() => toggle(item[keyAttr])}/>
              <span className="fm-name">{item[displayAttr]}</span>
              {meta && <span className="fm-code">{meta}</span>}
            </label>
          );
        })}
      </div>

      <BulkActions
        all={allOn}
        none={allOff}
        invert={allInv}
        selectedCount={visKeys.filter(k => selected.has(k)).length}
        totalCount={filtered.length}
        compact={true}
      />
    </div>
  );
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
function FilterMenu({ open = false, banco = 'ibge_pevs', value, onClose, onApply }) {
  const close = () => { if (typeof onClose === 'function') onClose(); };

  const bancoMeta = window.bancoById ? window.bancoById(banco) : null;
  const schema    = window.filterSchemaFor ? window.filterSchemaFor(banco) : null;
  const isLive    = bancoMeta ? bancoMeta.status === 'live' : true;
  const hasGeo    = !!(bancoMeta && bancoMeta.provides && bancoMeta.provides.includes('geo'));

  // ── Per-banco descriptors so the live menu is CORRECT for each banco
  // (no longer always PEVS): currency symbol/column, geo granularity, the
  // product dimension's label, and the banco-specific dimensions not yet
  // covered by the functional sections (surfaced read-only below).
  const geoLevel  = window.geoLevelFor ? window.geoLevelFor(banco) : (hasGeo ? 'municipio' : null);
  const showMunis = geoLevel === 'municipio';
  const baseCcy   = (bancoMeta && bancoMeta.baseCurrency) || 'BRL';
  const sym       = (window.CURRENCY_FX && window.CURRENCY_FX[baseCcy] && window.CURRENCY_FX[baseCcy].symbol) || 'R$';
  const fmtVal    = (v) => window.fmtCompactValue(v, sym);
  const dims      = (schema && schema.dims) || [];
  const prodDim   = dims.find(d => d.type === 'products' || d.type === 'multi-tree');
  const prodLabel = (prodDim && prodDim.label) || `Produtos · ${bancoMeta ? bancoMeta.short : 'PEVS'}`;
  const valDim    = dims.find(d => d.type === 'value-range' || d.type === 'period-value');
  const valColumn = (valDim && valDim.column ? valDim.column.split('·').pop().trim() : null) || 'val_real_ipca_brl';
  // Dimensions declared for this banco that the functional sections above do
  // not yet expose (e.g. fluxo, via, país, reporter). Shown read-only so the
  // schema is never silently ignored on a live banco.
  const COVERED_TYPES = ['products','multi-tree','date-range','period-value','value-range','geo-cascade','flags'];
  const COVERED_IDS   = ['uf_origem'];
  const extraDims = dims.filter(d => !COVERED_TYPES.includes(d.type) && !COVERED_IDS.includes(d.id));

  // Active banco's product universe (NOT the hardcoded PEVS list) so the picker
  // shows the right commodities/codes per banco (NCM for COMEX, HS6 for
  // Comtrade, …). For PEVS this equals window.PRODUCTS → behavior unchanged.
  const PRODS = useMemo(() => {
    const snap = (window.dataStore && window.dataStore.get && window.dataStore.get(banco))
              || (window.snapshotFor && window.snapshotFor(banco)) || null;
    return ((snap && snap.products) || window.PRODUCTS || [])
      .map(p => ({ code: p.code, name: p.name, unit: p.unit, family: p.family }));
  }, [banco]);

  // Period bounds + quick-ranges from the ACTIVE banco's snapshot (same source as
  // PRODS), so switching banco shifts the date min/max and the quick-range chips
  // instead of staying frozen to whichever banco loaded first at import time.
  const [yearStart, yearEnd] = useMemo(() => {
    const snap = (window.dataStore && window.dataStore.get && window.dataStore.get(banco))
              || (window.snapshotFor && window.snapshotFor(banco)) || null;
    return bancoYearBounds(snap);
  }, [banco]);
  const QUICK_RANGES = useMemo(() => buildQuickRanges(yearStart, yearEnd), [yearStart, yearEnd]);

  // multi-selects (Sets)
  const [products, setProducts] = useState(new Set(PRODS.map(p => p.code)));
  const [flags,    setFlags]    = useState(new Set(QUALITY.map(f => f.flag)));
  const [nations,  setNations]  = useState(new Set(['BR']));
  const [regions,  setRegions]  = useState(new Set(FM_REGIONS.map(r => r.id)));
  const [states,   setStates]   = useState(new Set(STATES.map(s => s.uf)));
  const [munis,    setMunis]    = useState(new Set(MUNICIPALITIES.map(m => m.code))); // all by default (0 = none, same as the other dimensions)

  // search strings, one per multi-select
  const [qProducts, setQProducts] = useState('');
  const [qFlags,    setQFlags]    = useState('');
  const [qNations,  setQNations]  = useState('');
  const [qRegions,  setQRegions]  = useState('');
  const [qStates,   setQStates]   = useState('');
  const [qMunis,    setQMunis]    = useState('');

  // period — seeded from the active banco's bounds (the open-effect below
  // re-seeds from the applied filter / banco bounds each time the panel opens).
  const [quickRange, setQuickRange] = useState('all');
  const [startDate,  setStartDate]  = useState(`${yearStart}-01`);
  const [endDate,    setEndDate]    = useState(`${yearEnd}-12`);

  // per-row value (filter range — in BRL, no conversion)
  // null = no limit
  const [valueMin, setValueMin] = useState(null);
  const [valueMax, setValueMax] = useState(null);

  // ----- cascade-aware lists (children gated by parent selection)
  const eligibleRegions = useMemo(
    () => FM_REGIONS.filter(r => nations.has(r.nation)),
    [nations]
  );
  const eligibleStates = useMemo(
    () => STATES.filter(s => regions.has(s.region) && eligibleRegions.some(r => r.id === s.region)),
    [regions, eligibleRegions]
  );
  const eligibleMunis = useMemo(
    () => MUNICIPALITIES.filter(m => states.has(m.uf) && eligibleStates.some(s => s.uf === m.uf)),
    [states, eligibleStates]
  );

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
      setProducts(v.basket  != null ? new Set(v.basket)  : new Set(PRODS.map(p => p.code)));
      setFlags(   v.flags   != null ? new Set(v.flags)   : new Set(QUALITY.map(f => f.flag)));
      setNations( v.nations != null ? new Set(v.nations) : new Set(['BR']));
      setRegions( v.regions != null ? new Set(v.regions) : new Set(FM_REGIONS.map(r => r.id)));
      setStates(  v.states  != null ? new Set(v.states)  : new Set(STATES.map(s => s.uf)));
      setMunis(   v.munis   != null ? new Set(v.munis)   : new Set(MUNICIPALITIES.map(m => m.code)));
      const sd = v.startDate || `${yearStart}-01`;
      const ed = v.endDate   || `${yearEnd}-12`;
      setStartDate(sd); setEndDate(ed);
      setQuickRange((sd === `${yearStart}-01` && ed === `${yearEnd}-12`) ? 'all' : null);
      setValueMin(v.valueMin ?? null);
      setValueMax(v.valueMax ?? null);
    }
    wasOpen.current = open;
  }, [open]);

  // products / flags filtered by search
  const filteredProducts = useMemo(() => {
    if (!qProducts) return PRODS;
    const q = qProducts.toLowerCase();
    return PRODS.filter(p =>
      p.name.toLowerCase().includes(q) || p.code.includes(q)
    );
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
  const applyQuick = (id) => {
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
    const prodTxt = products.size === PRODS.length
      ? `${PRODS.length} produtos (todos)`
      : `${products.size} de ${PRODS.length} produtos`;
    const period = `${formatMonth(startDate)}–${formatMonth(endDate)}`;
    const geoTxt =
      !hasGeo
        ? 'sem recorte geográfico'
      : nations.size === NATIONS.length && regions.size === FM_REGIONS.length && states.size === STATES.length && (!showMunis || munis.size === MUNICIPALITIES.length)
        ? 'todo o território'
      : nations.size === 1 && nations.has('BR') && states.size === STATES.length && (!showMunis || munis.size === MUNICIPALITIES.length)
        ? 'Brasil · todos os estados'
      : showMunis
        ? `${nations.size} nação(ões), ${states.size} UF, ${munis.size === MUNICIPALITIES.length ? 'todos os' : munis.size} municípios`
        : `${nations.size} nação(ões), ${states.size} UF`;
    return { prodTxt, period, geoTxt };
  }, [products, startDate, endDate, nations, regions, states, munis, hasGeo, showMunis]);

  // chip-bar summary published on apply (display strings only)
  const buildChipSummary = (vMin = valueMin, vMax = valueMax) => {
    const prodChip = window.chipFmt.products(
      products.size, PRODS.length, (PRODS.find(p => products.has(p.code)) || {}).name);
    const periodChip =
      quickRange === 'all' ? `${yearStart}–${yearEnd}`
      : `${formatMonth(startDate)}–${formatMonth(endDate)}`;
    const valueChip = window.chipFmt.valueRange(vMin, vMax, sym);
    const muniFull = !showMunis || munis.size === MUNICIPALITIES.length; // all listed (or no municipal level) = no municipal slice
    const geoChip = !hasGeo
      ? 'Não se aplica'
      : nations.size === 1 && nations.has('BR') && states.size === STATES.length && muniFull
        ? `Brasil · ${STATES.length} UFs`
      : nations.size === NATIONS.length && regions.size === FM_REGIONS.length && states.size === STATES.length && muniFull
        ? 'Todo o território'
      : !muniFull
        ? `${states.size} ${states.size === 1 ? 'UF' : 'UFs'} · ${munis.size} ${munis.size === 1 ? 'município' : 'municípios'}`
      : `${nations.size} ${nations.size === 1 ? 'nação' : 'nações'} · ${states.size} ${states.size === 1 ? 'UF' : 'UFs'}`;
    const qualityChip = window.chipFmt.quality([...flags], QUALITY.length, qualityLabelOf);
    return { products: prodChip, period: periodChip, valueRange: valueChip, geo: geoChip, quality: qualityChip };
  };

  const applyAndClose = () => {
    // Normalize an inverted value range (min > max) before publishing, so the
    // chip and stored filter never show a backwards "R$ 1 mi – R$ 1 mil".
    let vMin = valueMin, vMax = valueMax;
    if (vMin != null && vMax != null && vMin > vMax) { const t = vMin; vMin = vMax; vMax = t; }
    if (typeof onApply === 'function') {
      onApply({
        ...buildChipSummary(vMin, vMax),
        basket:    [...products],
        flags:     [...flags],
        nations:   [...nations],
        regions:   [...regions],
        states:    [...states],
        munis:     [...munis],
        // Selected município NAMES (the data keys by city name, not code) so
        // the engine can actually narrow topMunis by the município selection.
        muniNames: [...munis].map(c => (MUNICIPALITIES.find(m => m.code === c) || {}).name).filter(Boolean),
        startDate, endDate,
        valueMin:  vMin,  valueMax: vMax,
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

  return (
    <div className="fm-backdrop" onClick={close}>
      <div className="fm-modal wide" onClick={(e) => e.stopPropagation()} role="dialog" aria-labelledby="fm-title">
        {/* HEADER */}
            <header className="fm-head">
              <div className="fm-head-text">
                <span className="fm-head-over">
                  Filtros · {bancoMeta ? bancoMeta.short : 'Banco'}
                  {schema && <span className="fm-head-table"> · <code>{window.bancoTable(banco)}</code></span>}
                </span>
                <span id="fm-title" className="fm-title">
                  {isLive ? 'Editar filtros' : 'Dimensões filtráveis'}
                </span>
                <span className="fm-summary">
                  {isLive
                    ? <><strong>{summary.prodTxt}</strong> · {summary.period} · {summary.geoTxt}</>
                    : <>Pré-visualização · este banco será habilitado em <strong>{bancoMeta?.plannedRelease || 'breve'}</strong></>}
                </span>
              </div>
              <button className="fm-close" onClick={close} aria-label="Fechar">
                {I.close}
              </button>
            </header>

            {!isLive ? (
              <FilterPreview schema={schema} banco={bancoMeta} onClose={close} />
            ) : (
            <>
            <div className="fm-body">

            {/* ─── 01 · COMMODITIES ─────────────────────────── */}
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">01</span>{prodLabel}</span>
                  <SearchInput value={qProducts} onChange={setQProducts} placeholder="Buscar produto ou código…"/>
                </div>
                <span className="fm-section-meta">
                  <strong>{products.size}</strong> de {PRODS.length} selecionados
                </span>
              </div>

              <div className="fm-section-inner">
                <div className="fm-grid-scroll">
                  <div className="fm-grid">
                    {filteredProducts.length === 0 ? (
                      <div className="fm-empty-grid">Nenhum produto corresponde a “{qProducts}”.</div>
                    ) : filteredProducts.map(p => {
                      const on = products.has(p.code);
                      return (
                        <label key={p.code} className={'fm-check' + (on ? ' is-on' : '')}>
                          <input type="checkbox" checked={on}
                                 onChange={() => setProducts(s => toggleIn(s, p.code))}/>
                          <span className="fm-name">{p.name}</span>
                          <span className="fm-code">{p.code}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                <BulkActions
                  all={()    => setProducts(prev => new Set([...prev, ...filteredProducts.map(p => p.code)]))}
                  none={()   => { const vis = new Set(filteredProducts.map(p => p.code)); setProducts(prev => new Set([...prev].filter(c => !vis.has(c)))); }}
                  invert={() => setProducts(prev => { const n = new Set(prev); filteredProducts.forEach(p => n.has(p.code) ? n.delete(p.code) : n.add(p.code)); return n; })}
                  selectedCount={filteredProducts.filter(p => products.has(p.code)).length}
                  totalCount={filteredProducts.length}
                />
              </div>
            </section>

            {/* ─── 02 · PERÍODO + FINANCEIRO ────────────────── */}
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">02</span>Período &amp; faixa de valor</span>
                </div>
                <span className="fm-section-meta">
                  {formatMonth(startDate)}–{formatMonth(endDate)} ·{' '}
                  {valueMin == null && valueMax == null
                    ? 'sem limite por linha'
                    : 'valor por linha: ' +
                      (valueMin != null ? fmtVal(valueMin) : '—') + ' – ' +
                      (valueMax != null ? fmtVal(valueMax) : '—')}
                </span>
              </div>
            <div className="fm-row-2">
              {/* PERÍODO */}
              <div className="fm-col">
                <div className="fm-col-head">
                  <span className="fm-section-label">Período de referência</span>
                  <span className="fm-section-meta">
                    {quickRange ? <strong>{QUICK_RANGES.find(r => r.id === quickRange).label}</strong> : 'Intervalo personalizado'}
                  </span>
                </div>

                <div className="fm-quick">
                  {QUICK_RANGES.map(r => (
                    <button key={r.id}
                            className={quickRange === r.id ? 'on' : ''}
                            onClick={() => applyQuick(r.id)}
                            type="button">
                      {r.id === 'all' ? 'Tudo' : 'Últimos ' + r.label}
                    </button>
                  ))}
                </div>

                <div className="fm-date-row">
                  <div className="fm-date-field">
                    <label htmlFor="fm-start">Início</label>
                    <input id="fm-start" className="fm-date" type="month"
                           value={startDate} min={`${yearStart}-01`} max={endDate}
                           onChange={(e) => onDateChange('start', e.target.value)}/>
                  </div>
                  <div className="fm-arrow">{I.arrow}</div>
                  <div className="fm-date-field">
                    <label htmlFor="fm-end">Fim</label>
                    <input id="fm-end" className="fm-date" type="month"
                           value={endDate} min={startDate} max={`${yearEnd}-12`}
                           onChange={(e) => onDateChange('end', e.target.value)}/>
                  </div>
                </div>
              </div>

              <div className="fm-divider" aria-hidden="true"></div>

              {/* FAIXA DE VALOR (filtro por linha) */}
              <div className="fm-col">
                <div className="fm-col-head">
                  <span className="fm-section-label">Faixa de valor por linha</span>
                  <span className="fm-section-meta">
                    {valColumn}
                  </span>
                </div>

                <p className="fm-col-help">
                  Inclua apenas linhas cujo valor monetário esteja dentro da faixa.
                  Os limites são aplicados sobre o valor em <strong>{sym}</strong>;
                  a moeda e correção de exibição são definidas em <strong>Convenções métricas</strong>.
                </p>

                <div className="fm-sub">
                  <span className="fm-sub-label">Limites</span>
                  <div className="fm-range-row">
                    <div className="fm-range-field">
                      <label htmlFor="fm-vmin">Mínimo ({sym})</label>
                      <input
                        id="fm-vmin"
                        type="number"
                        inputMode="numeric"
                        min="0"
                        step="1000"
                        placeholder="sem limite"
                        value={valueMin == null ? '' : valueMin}
                        onChange={(e) => {
                          const v = e.target.value;
                          setValueMin(v === '' ? null : Math.max(0, Number(v)));
                        }}
                      />
                    </div>
                    <div className="fm-arrow">{I.arrow}</div>
                    <div className="fm-range-field">
                      <label htmlFor="fm-vmax">Máximo ({sym})</label>
                      <input
                        id="fm-vmax"
                        type="number"
                        inputMode="numeric"
                        min="0"
                        step="1000"
                        placeholder="sem limite"
                        value={valueMax == null ? '' : valueMax}
                        onChange={(e) => {
                          const v = e.target.value;
                          setValueMax(v === '' ? null : Math.max(0, Number(v)));
                        }}
                      />
                    </div>
                  </div>
                </div>

                <div className="fm-sub">
                  <span className="fm-sub-label">Atalhos · valor mínimo</span>
                  <div className="fm-quick">
                    {(window.VALUE_PRESETS || []).map(p => ({
                      ...p,
                      label: p.suffix ? `≥ ${sym} ${p.suffix}` : 'Sem limite',
                    })).map(p => {
                      const on = valueMin === p.min && valueMax === p.max;
                      return (
                        <button key={p.id}
                                type="button"
                                className={on ? 'on' : ''}
                                onClick={() => { setValueMin(p.min); setValueMax(p.max); }}>
                          {p.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
            </section>

            {/* ─── 03 · GEOGRAFIA (4 cascading columns) ────── */}
            {hasGeo && (
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">03</span>Geografia</span>
                  <span className="fm-cascade-hint">
                    {I.cascade} Seleção em cascata · nação ▸ região ▸ estado{showMunis ? ' ▸ município' : ''}
                  </span>
                </div>
                <span className="fm-section-meta">
                  <strong>{nations.size}</strong> {nations.size === 1 ? 'nação' : 'nações'} ·{' '}
                  <strong>{regions.size}</strong> {regions.size === 1 ? 'região' : 'regiões'} ·{' '}
                  <strong>{states.size}</strong> {states.size === 1 ? 'UF' : 'UFs'}
                  {showMunis && <>{' '}·{' '}<strong>{munis.size}</strong> {munis.size === 1 ? 'município' : 'municípios'}</>}
                </span>
              </div>

              <div className="fm-section-inner">
              <div className={'fm-geo-grid' + (showMunis ? '' : ' cols-3')}>
                <GeoColumn
                  title="Nações"
                  items={NATIONS}
                  keyAttr="iso"
                  displayAttr="name"
                  getMeta={(x) => x.iso}
                  selected={nations}
                  setSelected={setNations}
                  search={qNations}
                  setSearch={setQNations}
                />
                <GeoColumn
                  title="Regiões"
                  items={eligibleRegions}
                  keyAttr="id"
                  displayAttr="name"
                  getMeta={(x) => x.id}
                  selected={regions}
                  setSelected={setRegions}
                  search={qRegions}
                  setSearch={setQRegions}
                  disabledReason={nations.size === 0 ? 'Selecione ao menos uma nação.' : null}
                />
                <GeoColumn
                  title="Estados"
                  items={eligibleStates}
                  keyAttr="uf"
                  displayAttr="name"
                  getMeta={(x) => x.uf}
                  selected={states}
                  setSelected={setStates}
                  search={qStates}
                  setSearch={setQStates}
                  disabledReason={eligibleRegions.length === 0 || regions.size === 0 ? 'Selecione ao menos uma região.' : null}
                />
                {showMunis && (
                <GeoColumn
                  title="Municípios"
                  items={eligibleMunis}
                  keyAttr="code"
                  displayAttr="name"
                  getMeta={(x) => x.uf}
                  selected={munis}
                  setSelected={setMunis}
                  search={qMunis}
                  setSearch={setQMunis}
                  disabledReason={eligibleStates.length === 0 || states.size === 0 ? 'Selecione ao menos um estado.' : null}
                />
                )}
              </div>

              {showMunis && (
              <div className="fm-geo-foot">
                <span className="fm-section-meta">
                  Lista parcial: {MUNICIPALITIES.length} municípios líderes.{' '}
                  <a href="#" onClick={(e) => e.preventDefault()}>Carregar todos os 5 570</a>
                </span>
              </div>
              )}
              </div>
            </section>
            )}

            {/* ─── 04 · QUALIDADE DOS DADOS ─────────────────── */}
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">{hasGeo ? '04' : '03'}</span>Qualidade dos dados · <span className="mono lowercase">data_quality_flag</span></span>
                  <SearchInput value={qFlags} onChange={setQFlags} placeholder="Buscar flag…"/>
                </div>
                <span className="fm-section-meta">
                  <strong>{flags.size}</strong> de {QUALITY.length} selecionadas
                </span>
              </div>

              <div className="fm-section-inner">
                <div className="fm-grid-scroll">
                  <div className="fm-grid">
                    {filteredFlags.length === 0 ? (
                      <div className="fm-empty-grid">Nenhuma flag corresponde a “{qFlags}”.</div>
                    ) : filteredFlags.map(q => {
                      const on = flags.has(q.flag);
                      return (
                        <label key={q.flag} className={'fm-check' + (on ? ' is-on' : '')}>
                          <input type="checkbox" checked={on}
                                 onChange={() => setFlags(s => toggleIn(s, q.flag))}/>
                          <span className="fm-name">{q.label}</span>
                          <span className="fm-code mono">{q.flag}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                <BulkActions
                  all={()    => setFlags(prev => new Set([...prev, ...filteredFlags.map(q => q.flag)]))}
                  none={()   => { const vis = new Set(filteredFlags.map(q => q.flag)); setFlags(prev => new Set([...prev].filter(f => !vis.has(f)))); }}
                  invert={() => setFlags(prev => { const n = new Set(prev); filteredFlags.forEach(q => n.has(q.flag) ? n.delete(q.flag) : n.add(q.flag)); return n; })}
                  selectedCount={filteredFlags.filter(q => flags.has(q.flag)).length}
                  totalCount={filteredFlags.length}
                />
              </div>
            </section>

            {/* ─── BANCO-SPECIFIC DIMENSIONS (read-only) ─────── */}
            {extraDims.length > 0 && (
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">+</span>Dimensões específicas · {bancoMeta ? bancoMeta.short : ''}</span>
                </div>
                <span className="fm-section-meta">{extraDims.length} {extraDims.length === 1 ? 'dimensão' : 'dimensões'} · em breve filtráveis</span>
              </div>
              <div className="fm-section-inner">
                <div className="fm-extra-note">
                  <span className="fm-extra-badge">Em breve</span>
                  <span>Dimensões próprias deste banco. Já declaradas no schema e ficarão filtráveis quando a Gold completa for publicada.</span>
                </div>
                <div className="fm-extra-grid">
                  {extraDims.map(d => (
                    <div key={d.id} className="fm-extra-dim">
                      <div className="fm-extra-dim-head">
                        <span className="fm-extra-dim-label">{d.label}</span>
                        <span className="fm-extra-dim-type">{d.type}</span>
                      </div>
                      <code className="fm-extra-dim-col">{d.column}</code>
                      {d.options && (
                        <div className="fm-extra-opts">
                          {d.options.map(o => <span key={o} className="fm-extra-opt">{o}</span>)}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </section>
            )}

            </div>

            {/* FOOTER */}
            <footer className="fm-foot">
              <div className="fm-foot-info">
                Os filtros serão aplicados sobre <strong>{window.bancoTable(banco) || 'gold_pevs_production'}</strong>
                <span className="fm-dot"></span>
                {bancoMeta?.prov?.refresh ? `Refresh ${bancoMeta.prov.refresh}` : 'Atualização diária às 06h00 BRT'}
              </div>
              <button className="btn-ghost" onClick={restoreDefaults}>Restaurar padrão</button>
              <button className="btn-secondary" onClick={close}>Cancelar</button>
              <button className="btn-primary" onClick={applyAndClose}>Aplicar filtros</button>
            </footer>
            </>
            )}
      </div>
    </div>
  );
}

// ----- Preview body for soon bancos -------------------------------
// Renders the planned filter dimensions read-only, grouped by tier,
// so the researcher sees what they'll be able to filter once live.
function FilterPreview({ schema, banco, onClose }) {
  const TIER = window.TIER_LABEL || {};
  const dims = (schema && schema.dims) || [];
  const tiers = ['universal', 'shared', 'specific'];
  const byTier = tiers
    .map(t => ({ tier: t, items: dims.filter(d => d.tier === t) }))
    .filter(g => g.items.length > 0);

  return (
    <div className="fm-body fm-preview">
      <div className="fm-preview-banner">
        <span className="fm-preview-badge">Em breve</span>
        <span>
          Este banco ainda não foi liberado no backend. Abaixo estão as
          dimensões que estarão disponíveis para filtragem assim que a
          tabela <code>{window.bancoTable(banco)}</code> for publicada
          {banco?.plannedRelease ? ` (previsão ${banco.plannedRelease})` : ''}.
        </span>
      </div>

      {byTier.map(g => (
        <section key={g.tier} className="fm-preview-group">
          <div className="fm-preview-group-head">
            <span className="fm-preview-tier">{TIER[g.tier] || g.tier}</span>
            <span className="fm-preview-tier-meta">{g.items.length} dimensão(ões)</span>
          </div>
          <div className="fm-preview-grid">
            {g.items.map(d => (
              <div key={d.id} className="fm-preview-dim">
                <div className="fm-preview-dim-head">
                  <span className="fm-preview-dim-label">{d.label}</span>
                  <span className="fm-preview-dim-type">{d.type}</span>
                </div>
                <code className="fm-preview-dim-col">{d.column}</code>
                <p className="fm-preview-dim-hint">{d.hint}</p>
                {d.options && (
                  <div className="fm-preview-opts">
                    {d.options.map(o => <span key={o} className="fm-preview-opt">{o}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      ))}

      <footer className="fm-foot">
        <div className="fm-foot-info">
          {dims.length} dimensões previstas · scoped a <strong>{window.bancoTable(banco)}</strong>
        </div>
        <button className="btn-primary" onClick={onClose}>Entendi</button>
      </footer>
    </div>
  );
}



function formatMonth(iso) {
  if (!iso) return '—';
  const [y, m] = iso.split('-');
  return `${m}/${y}`;
}

window.FilterMenu = FilterMenu;
