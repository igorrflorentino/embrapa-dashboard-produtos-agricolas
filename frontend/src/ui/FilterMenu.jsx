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
  OK: 'ok', MISSING_VALUE: 'warn', MISSING_QUANTITY: 'info',
  MISSING_WEIGHT: 'warn', INCOMPLETE: 'muted',
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

// Nations — the geo-cascade is consumed ONLY by domestic datasets (ibge_pevs,
// ibge_pam, sefaz_nf): PEVS/PAM are Brazilian *production* (Gold carries only
// uf/municipio — no destination country) and NFe is internal inter-UF flow. So
// the only real nação is Brasil. The earlier list also carried 11 foreign
// "export destinations" (China, EUA, …) — a prototype fabrication that mapped to
// NO column in any geo-cascade banco: adding one was a silent no-op, selecting
// only one zeroed the whole map. International partners are a REAL dimension only
// for COMEX/COMTRADE, which expose them via their own `pais`/`partner`
// multi-search dims, not this cascade. Kept as a list so the cascade rendering
// and "all selected" checks stay unchanged.
const NATIONS = [
  { iso: 'BR', name: 'Brasil', role: 'produtor' },
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

// The município universe is now the IBGE territorial mesh (/api/geo-mesh, via
// window.geoMesh) — real, code-keyed, ~5570 municípios with their full sub-UF
// ancestry — resolved inside the component (see `MUNIS`). The old frozen 40-row
// MUNI_SAMPLE and the name-keyed window.MUNI_PICKER_NAMES path were removed with
// the gated, snapshot-topMunis approach they served.

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
        {!disabledReason && filtered.slice(0, GEO_RENDER_CAP).map(item => {
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
        {!disabledReason && filtered.length > GEO_RENDER_CAP && (
          <div className="fm-geo-allnote">
            Mostrando {GEO_RENDER_CAP} de {filtered.length} — refine a busca para ver os demais
            (as ações em massa abaixo afetam todos os {filtered.length}).
          </div>
        )}
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
// A sub-UF facet narrows the data only as a PROPER subset of its universe; a full
// selection means "no narrowing" → emit null so dataFilters skips it and the share
// URL omits it (instead of serializing every código). namesObj is the per-level
// {code: name} map whose key count IS the universe size.
const _geoArr = (set, namesObj) =>
  set.size >= Object.keys(namesObj).length ? null : [...set];

// Cap how many geo checkboxes render at once. The município column's universe is ~5570;
// rendering them all on first open is jank/memory the list rarely needs (RVC-5). Bulk
// actions still operate on the full search-filtered set — only the visible DOM is capped,
// and a note nudges the user to search to narrow further.
const GEO_RENDER_CAP = 300;

// onApply receives a display-summary object the trigger row can render as
// chips. `value` is the currently-APPLIED raw filter (basket/flags/states/…);
// the panel seeds itself from it each time it opens, so it always mirrors
// what's live (incl. a shared deep-link) instead of silently resetting to all.
function FilterMenu({ open = false, banco = 'ibge_pevs', value, onClose, onApply }) {
  const close = () => { if (typeof onClose === 'function') onClose(); };
  // a11y: Escape closes the modal (mirrors the backdrop click). Listener is bound
  // only while the modal is open and torn down on close/unmount.
  React.useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape' && typeof onClose === 'function') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const bancoMeta = window.bancoById ? window.bancoById(banco) : null;
  const schema    = window.filterSchemaFor ? window.filterSchemaFor(banco) : null;
  const isLive    = bancoMeta ? bancoMeta.status === 'live' : true;
  const hasGeo    = !!(bancoMeta && bancoMeta.provides && bancoMeta.provides.includes('geo'));
  // Capability gates — every section is now dynamic: it renders ONLY when the active
  // banco provides the dimension (so the user never sees an option it can't use).
  const provides    = (bancoMeta && bancoMeta.provides) || [];
  const hasProduct  = provides.includes('product');
  const hasQuality  = provides.includes('quality');
  const hasFlow     = provides.includes('flow');
  const flowOptions = (hasFlow && window.flowOptionsFor) ? window.flowOptionsFor(banco) : null;

  // ── Per-banco descriptors so the live menu is CORRECT for each banco
  // (no longer always PEVS): currency symbol/column, geo granularity, the
  // product dimension's label, and the banco-specific dimensions not yet
  // covered by the functional sections (surfaced read-only below).
  const geoLevel  = window.geoLevelFor ? window.geoLevelFor(banco) : (hasGeo ? 'municipio' : null);
  const showMunis = geoLevel === 'municipio';
  const baseCcy   = (bancoMeta && bancoMeta.baseCurrency) || 'BRL';
  const sym       = (window.CURRENCY_FX && window.CURRENCY_FX[baseCcy] && window.CURRENCY_FX[baseCcy].symbol) || 'R$';
  const dims      = (schema && schema.dims) || [];
  const prodDim   = dims.find(d => d.type === 'products' || d.type === 'multi-tree');
  const prodLabel = (prodDim && prodDim.label) || `Produtos · ${bancoMeta ? bancoMeta.short : 'PEVS'}`;
  // The menu renders ONLY what the active banco can filter on: each section below is
  // capability-gated (hasProduct/hasGeo/hasQuality/hasFlow), so a dim the banco
  // doesn't provide, or one declared-but-not-backed (via/CFOP/CNAE/partner — summed
  // away in Silver), simply never appears. `fluxo` is the one banco-specific dim
  // wired functional (server-side); see window.bancoFilterDims for the contract.

  // Active banco's product universe (NOT the hardcoded PEVS list) so the picker
  // shows the right commodities/codes per banco (NCM for COMEX, HS6 for
  // Comtrade, …). For PEVS this equals window.PRODUCTS → behavior unchanged.
  const PRODS = useMemo(() => {
    const snap = (window.dataStore && window.dataStore.get && window.dataStore.get(banco))
              || (window.snapshotFor && window.snapshotFor(banco)) || null;
    return ((snap && snap.products) || window.PRODUCTS || [])
      .map(p => ({ code: p.code, name: p.name, unit: p.unit, family: p.family }));
  }, [banco]);

  // Município + sub-UF universe — the IBGE territorial mesh (/api/geo-mesh, via
  // window.geoMesh). Every município → its 7-digit city_code + UF + grande região +
  // BOTH sub-UF divisions (classic mesorregião/microrregião, 2017 região
  // intermediária/imediata). This makes município a REAL, code-keyed filter (the old
  // path was name-keyed off the snapshot's topMunis and gated off in prod) and feeds
  // the four sub-UF cascade levels. A UF-origin banco (geoLevel !== 'municipio', e.g.
  // COMEX) has no city_code, so the mesh is not loaded and only nação ▸ região ▸ UF
  // render. The mesh is static + cached; main.jsx's resource subscription re-renders
  // this menu once it lands, so the first open may briefly show empty sub-UF columns.
  const mesh = (showMunis && window.geoMesh) ? window.geoMesh() : null;
  const { MUNIS, mesoNames, microNames, interNames, imediataNames } = useMemo(() => {
    const meso = {}, micro = {}, inter = {}, imediata = {};
    const list = (mesh || []).map(m => {
      const mc = (m.meso && m.meso.code) || '';
      const cc = (m.micro && m.micro.code) || '';
      const ic = (m.intermediaria && m.intermediaria.code) || '';
      const ec = (m.imediata && m.imediata.code) || '';
      if (mc) meso[mc] = m.meso.name;
      if (cc) micro[cc] = m.micro.name;
      if (ic) inter[ic] = m.intermediaria.name;
      if (ec) imediata[ec] = m.imediata.name;
      return { code: m.cityCode, name: m.cityName, uf: m.uf,
               meso: mc, micro: cc, intermediaria: ic, imediata: ec };
    });
    return { MUNIS: list, mesoNames: meso, microNames: micro, interNames: inter, imediataNames: imediata };
  }, [mesh]);

  // município is LIVE once the mesh has loaded (it carries the full ~5570 universe);
  // until then (or for a UF-origin banco) the columns are gated.
  const muniUniverseLive = MUNIS.length > 0;
  const muniSliceable = showMunis && muniUniverseLive;

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
  // Geo selection (nations → regions → states → municípios) + cascade pruning +
  // eligibility live in a dedicated, unit-tested hook (useGeoCascade.js). Defaults:
  // nations = {BR} only; regions/states/municípios = all of the banco's universe.
  const {
    nations,  setNations,
    regions,  setRegions,
    states,   setStates,
    mesos,    setMesos,
    micros,   setMicros,
    inters,   setInters,
    imediatas, setImediatas,
    munis,    setMunis,
    eligibleRegions, eligibleStates,
    eligibleMesos, eligibleMicros, eligibleInters, eligibleImediatas,
    eligibleMunis,
  } = window.useGeoCascade({ regionsUniverse: FM_REGIONS, statesUniverse: STATES, munisUniverse: MUNIS });

  // The four sub-UF levels arrive from the engine as arrays of CODES; GeoColumn
  // wants {code, name} items, so decorate each with its mesh name (falling back to
  // the code). Memoized on the eligible list + the name map.
  const mesoItems = useMemo(
    () => eligibleMesos.map(c => ({ code: c, name: mesoNames[c] || c })), [eligibleMesos, mesoNames]);
  const microItems = useMemo(
    () => eligibleMicros.map(c => ({ code: c, name: microNames[c] || c })), [eligibleMicros, microNames]);
  const interItems = useMemo(
    () => eligibleInters.map(c => ({ code: c, name: interNames[c] || c })), [eligibleInters, interNames]);
  const imediataItems = useMemo(
    () => eligibleImediatas.map(c => ({ code: c, name: imediataNames[c] || c })), [eligibleImediatas, imediataNames]);

  // search strings, one per multi-select
  const [qProducts, setQProducts] = useState('');
  const [qFlags,    setQFlags]    = useState('');
  const [qNations,  setQNations]  = useState('');
  const [qRegions,  setQRegions]  = useState('');
  const [qStates,   setQStates]   = useState('');
  const [qMesos,    setQMesos]    = useState('');
  const [qMicros,   setQMicros]   = useState('');
  const [qInters,   setQInters]   = useState('');
  const [qImediatas, setQImediatas] = useState('');
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

  // Fluxo (export/import) — a SERVER-SIDE filter: the trade snapshot is pre-aggregated
  // over flow, so picking a direction re-fetches (the data layer's setFlow bridge).
  // 'all' = every flow. Only trade bancos (hasFlow) render the control.
  const [flow, setFlow] = useState((value && value.flow) || 'all');

  // (eligibility memos + cascade-pruning effects now live in useGeoCascade above)

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
      setMesos(    v.mesos     != null ? new Set(v.mesos)     : new Set(Object.keys(mesoNames)));
      setMicros(   v.micros    != null ? new Set(v.micros)    : new Set(Object.keys(microNames)));
      setInters(   v.inters    != null ? new Set(v.inters)    : new Set(Object.keys(interNames)));
      setImediatas(v.imediatas != null ? new Set(v.imediatas) : new Set(Object.keys(imediataNames)));
      setMunis(   v.munis   != null ? new Set(v.munis)   : new Set(MUNIS.map(m => m.code)));
      const sd = v.startDate || `${yearStart}-01`;
      const ed = v.endDate   || `${yearEnd}-12`;
      setStartDate(sd); setEndDate(ed);
      setQuickRange((sd === `${yearStart}-01` && ed === `${yearEnd}-12`) ? 'all' : null);
      // Value-range filter is disabled (no backend row-level path yet) — force the
      // limits to null even if a bookmarked URL restored a value, so the chip never
      // claims an active filter that changes nothing.
      setValueMin(null);
      setValueMax(null);
      setFlow(v.flow || 'all');
    }
    wasOpen.current = open;
    // Intentionally keyed ONLY on `open`: this re-syncs the DRAFT filter state from
    // props each time the menu opens, so the user's in-progress edits are not
    // clobbered by unrelated prop changes (value/year/basket) while it is open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    const geoTxt = window.filterSummary.geoHeaderText({
      hasGeo,
      nationsSize: nations.size,
      nationsTotal: NATIONS.length,
      hasOnlyBR: nations.size === 1 && nations.has('BR'),
      regionsSize: regions.size,
      regionsTotal: FM_REGIONS.length,
      statesSize: states.size,
      statesTotal: STATES.length,
      munisSize: munis.size,
      munisTotal: MUNIS.length,
      muniSliceable,
    });
    return { prodTxt, period, geoTxt };
  }, [products, startDate, endDate, nations, regions, states, munis, hasGeo, muniSliceable, MUNIS, PRODS.length]);

  // chip-bar summary published on apply (display strings only)
  const buildChipSummary = (vMin = valueMin, vMax = valueMax) => {
    const prodChip = window.chipFmt.products(
      products.size, PRODS.length, (PRODS.find(p => products.has(p.code)) || {}).name);
    const periodChip =
      quickRange === 'all' ? `${yearStart}–${yearEnd}`
      : `${formatMonth(startDate)}–${formatMonth(endDate)}`;
    const valueChip = window.chipFmt.valueRange(vMin, vMax, sym);
    const geoChip = window.filterSummary.geoChipText({
      hasGeo,
      nationsSize: nations.size,
      nationsTotal: NATIONS.length,
      hasOnlyBR: nations.size === 1 && nations.has('BR'),
      regionsSize: regions.size,
      regionsTotal: FM_REGIONS.length,
      statesSize: states.size,
      statesTotal: STATES.length,
      munisSize: munis.size,
      munisTotal: MUNIS.length,
      muniSliceable,
    });
    const qualityChip = window.chipFmt.quality([...flags], QUALITY.length, qualityLabelOf);
    const fluxoChip = hasFlow
      ? (flow === 'all' ? 'Todos os fluxos' : ((flowOptions.find(o => o.value === flow) || {}).label || flow))
      : null;
    return { products: prodChip, period: periodChip, valueRange: valueChip, geo: geoChip, quality: qualityChip, fluxo: fluxoChip };
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
        // The four sub-UF levels (two parallel IBGE divisions) + município, all
        // CODE-keyed off the mesh — dataFilters rolls the município cube up to the
        // active level via /api/geo-mesh. A FULL selection emits null = "all" (no
        // narrowing): dataFilters treats null and the full set identically, and the
        // share-URL codec then omits it instead of serializing every código (which
        // for the ~5570-município universe would rebuild the very long URL the
        // POST /api/municipio-yearly path was created to avoid).
        mesos:     _geoArr(mesos, mesoNames),
        micros:    _geoArr(micros, microNames),
        inters:    _geoArr(inters, interNames),
        imediatas: _geoArr(imediatas, imediataNames),
        munis:     munis.size >= MUNIS.length ? null : [...munis],
        startDate, endDate,
        valueMin:  vMin,  valueMax: vMax,
        // Fluxo (server-side): omitted when 'all' so the summary/URL stay clean and
        // the data-layer bridge reads it as "every flow" (the default).
        flow: flow !== 'all' ? flow : undefined,
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
    setMesos(new Set(Object.keys(mesoNames)));
    setMicros(new Set(Object.keys(microNames)));
    setInters(new Set(Object.keys(interNames)));
    setImediatas(new Set(Object.keys(imediataNames)));
    setMunis(new Set(MUNIS.map(m => m.code)));
    applyQuick('all');
    setValueMin(null);
    setValueMax(null);
    setFlow('all');
    [setQProducts, setQFlags, setQNations, setQRegions, setQStates,
     setQMesos, setQMicros, setQInters, setQImediatas, setQMunis].forEach(fn => fn(''));
  };

  if (!open) return null;

  return (
    <div className="fm-backdrop" onClick={close}>
      <div className="fm-modal wide" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="fm-title">
        {/* HEADER */}
            <header className="fm-head">
              <div className="fm-head-text">
                <span className="fm-head-over">
                  Filtros · {bancoMeta ? bancoMeta.short : 'Banco'}
                  {schema && <span className="fm-head-table"> · <code>{(window.dataStore && window.dataStore.meta(bancoMeta?.id || banco).table) || window.bancoTable(banco)}</code></span>}
                </span>
                <span id="fm-title" className="fm-title">
                  {isLive ? 'Editar filtros' : 'Dimensões filtráveis'}
                </span>
                <span className="fm-summary">
                  {isLive
                    ? <><strong>{summary.prodTxt}</strong> · {summary.period} · {summary.geoTxt}</>
                    : <>Pré-visualização · este banco será habilitado em <strong>{bancoMeta?.maturityDate || 'breve'}</strong></>}
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

            {/* ─── 01 · COMMODITIES (gated on the `product` capability) ─────── */}
            {hasProduct && (
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
            )}

            {/* ─── FLUXO (export/import) — FUNCTIONAL, server-side filter; trade bancos only.
                 Picking a direction re-fetches the flow-aggregated snapshot (the only
                 server-side filter; everything else narrows the loaded snapshot). ─── */}
            {hasFlow && flowOptions && (
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label">Fluxo</span>
                </div>
                <span className="fm-section-meta">
                  {flow === 'all'
                    ? 'todos os fluxos'
                    : ((flowOptions.find(o => o.value === flow) || {}).label || '')}
                </span>
              </div>
              <div className="fm-section-inner">
                <div className="seg">
                  {flowOptions.map(o => (
                    <button key={o.value} type="button"
                            className={'seg-opt ' + (flow === o.value ? 'on' : '')}
                            aria-pressed={flow === o.value}
                            onClick={() => setFlow(o.value)}>
                      {o.label}
                    </button>
                  ))}
                </div>
              </div>
            </section>
            )}

            {/* ─── 02 · PERÍODO + FINANCEIRO ────────────────── */}
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">02</span>Período</span>
                </div>
                <span className="fm-section-meta">
                  {formatMonth(startDate)}–{formatMonth(endDate)}
                </span>
              </div>
            <div className="fm-row-2 fm-row-solo">
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
            </div>
            </section>

            {/* ─── 03 · GEOGRAFIA (4 cascading columns) ────── */}
            {hasGeo && (
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">03</span>Geografia</span>
                  <span className="fm-cascade-hint">
                    {I.cascade} Seleção em cascata · nação ▸ região ▸ estado{showMunis ? ' ▸ meso/microrregião · inter/imediata ▸ município' : ''}
                  </span>
                </div>
                <span className="fm-section-meta">
                  <strong>{nations.size}</strong> {nations.size === 1 ? 'nação' : 'nações'} ·{' '}
                  <strong>{regions.size}</strong> {regions.size === 1 ? 'região' : 'regiões'} ·{' '}
                  <strong>{states.size}</strong> {states.size === 1 ? 'UF' : 'UFs'}
                  {showMunis && (muniUniverseLive
                    ? <>{' '}·{' '}<strong>{munis.size}</strong> {munis.size === 1 ? 'município' : 'municípios'}</>
                    : <>{' '}·{' '}<span className="fm-soon-inline">municípios em breve</span></>)}
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
                {/* Sub-UF: the TWO parallel IBGE divisions (classic meso/micro,
                    2017 intermediária/imediata). They refine the UF independently;
                    a município passes the cascade iff it clears every active facet.
                    Only the município-grained bancos (PEVS/PAM/PPM) render them. */}
                {showMunis && (<>
                <GeoColumn
                  title="Mesorregiões"
                  items={mesoItems}
                  keyAttr="code"
                  displayAttr="name"
                  getMeta={(x) => x.code}
                  selected={mesos}
                  setSelected={setMesos}
                  search={qMesos}
                  setSearch={setQMesos}
                  disabledReason={
                    !muniUniverseLive ? 'Carregando malha do IBGE…'
                      : states.size === 0 ? 'Selecione ao menos um estado.' : null
                  }
                />
                <GeoColumn
                  title="Microrregiões"
                  items={microItems}
                  keyAttr="code"
                  displayAttr="name"
                  getMeta={(x) => x.code}
                  selected={micros}
                  setSelected={setMicros}
                  search={qMicros}
                  setSearch={setQMicros}
                  disabledReason={
                    !muniUniverseLive ? 'Carregando malha do IBGE…'
                      : mesos.size === 0 ? 'Selecione ao menos uma mesorregião.' : null
                  }
                />
                <GeoColumn
                  title="Reg. intermediárias"
                  items={interItems}
                  keyAttr="code"
                  displayAttr="name"
                  getMeta={(x) => x.code}
                  selected={inters}
                  setSelected={setInters}
                  search={qInters}
                  setSearch={setQInters}
                  disabledReason={
                    !muniUniverseLive ? 'Carregando malha do IBGE…'
                      : states.size === 0 ? 'Selecione ao menos um estado.' : null
                  }
                />
                <GeoColumn
                  title="Reg. imediatas"
                  items={imediataItems}
                  keyAttr="code"
                  displayAttr="name"
                  getMeta={(x) => x.code}
                  selected={imediatas}
                  setSelected={setImediatas}
                  search={qImediatas}
                  setSearch={setQImediatas}
                  disabledReason={
                    !muniUniverseLive ? 'Carregando malha do IBGE…'
                      : inters.size === 0 ? 'Selecione ao menos uma região intermediária.' : null
                  }
                />
                </>)}
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
                  // Município is LIVE via the IBGE mesh (code-keyed). Gate only while
                  // the mesh loads, or when its parent UF level is empty.
                  disabledReason={
                    !muniUniverseLive
                      ? 'Carregando malha do IBGE…'
                      : eligibleStates.length === 0 || states.size === 0
                        ? 'Selecione ao menos um estado.'
                        : null
                  }
                />
                )}
              </div>

              {showMunis && (
              <div className="fm-geo-foot">
                <span className="fm-section-meta">
                  {/* Footer: the IBGE mesh universe (full ~5570), driving the
                      município + the two parallel sub-UF divisions. */}
                  {muniUniverseLive
                    ? `Malha IBGE: ${MUNIS.length} municípios · mesorregião/microrregião + região intermediária/imediata.`
                    : 'Carregando a malha municipal do IBGE…'}
                </span>
              </div>
              )}
              </div>
            </section>
            )}

            {/* ─── 04 · QUALIDADE DOS DADOS (gated on the `quality` capability) ─── */}
            {hasQuality && (
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
            )}

            </div>

            {/* FOOTER */}
            <footer className="fm-foot">
              <div className="fm-foot-info">
                {/* Read the Gold table from the LIVE provenance (dataStore.meta →
                    /api/source-meta overlay), not the static bancoTable/registry
                    literal — so a backend rename of the served table propagates here. */}
                Os filtros serão aplicados sobre <strong>{window.dataStore.meta(bancoMeta?.id || banco).table || 'gold_pevs_production'}</strong>
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
          tabela <code>{window.bancoTable(banco?.id)}</code> for publicada
          {banco?.maturityDate ? ` (previsão ${banco.maturityDate})` : ''}.
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
          {dims.length} dimensões previstas · scoped a <strong>{window.bancoTable(banco?.id)}</strong>
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
