// FilterMenu.jsx — v2
// Expanded filter modal adapted from the updated sketch to the
// Embrapa Commodities Design System.
//
// v2 adds, per the new sketch:
//   • Inline search input inside every multi-select header
//   • New "Geografia" section with 4 cascading columns
//     (Nações → Regiões → Estados → Municípios)
//   • Scrollable lists (260px max-height) for long enumerations
//   • Each multi-select has its own bulk actions row
//
// Selection cascades downward: e.g. unchecking "Norte" removes the
// 7 northern states from the Estados list; checking "Pará" makes
// Pará's municipalities the only ones eligible in Municípios.
// Going upward, child selections are preserved when the parent is
// re-checked (typical Looker/Tableau filter behavior).

const { useState, useMemo } = React;

// --- Domain data ---------------------------------------------------
const PEVS = [
  { code: '49101', name: 'Castanha-do-pará',    unit: 't' },
  { code: '49103', name: 'Açaí (fruto)',        unit: 't' },
  { code: '49108', name: 'Erva-mate',           unit: 't' },
  { code: '49112', name: 'Pinhão',              unit: 't' },
  { code: '49215', name: 'Madeira em tora',     unit: 'm³' },
  { code: '49216', name: 'Lenha',               unit: 'm³' },
  { code: '49218', name: 'Carvão vegetal',      unit: 't' },
  { code: '49221', name: 'Borracha (látex)',    unit: 't' },
  { code: '49105', name: 'Babaçu (amêndoa)',    unit: 't' },
  { code: '49107', name: 'Carnaúba (cera)',     unit: 't' },
  { code: '49110', name: 'Palmito',             unit: 't' },
  { code: '49113', name: 'Pequi (fruto)',       unit: 't' },
];

const QUALITY = [
  { flag: 'OK',                 label: 'Registro completo',          chip: 'ok'    },
  { flag: 'MISSING_VALUE',      label: 'Valor monetário ausente',    chip: 'warn'  },
  { flag: 'MISSING_QUANTITY',   label: 'Quantidade ausente',         chip: 'warn'  },
  { flag: 'ESTIMATED',          label: 'Valor estimado pelo IBGE',   chip: 'info'  },
  { flag: 'BOUNDARY_HISTORIC',  label: 'Limite municipal histórico', chip: 'muted' },
  { flag: 'OUTLIER',            label: 'Possível outlier',           chip: 'err'   },
];

const QUICK_RANGES = [
  { id: 'all',  label: 'Tudo',           start: '1986-01', end: '2024-12' },
  { id: '30a',  label: '30 anos',        start: '1995-01', end: '2024-12' },
  { id: '20a',  label: '20 anos',        start: '2005-01', end: '2024-12' },
  { id: '10a',  label: '10 anos',        start: '2015-01', end: '2024-12' },
  { id: '5a',   label: '5 anos',         start: '2020-01', end: '2024-12' },
];

// Nações — produtor + principais destinos de exportação dos PEVS.
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

// 5 macrorregiões do Brasil. Linked to BR nation.
const REGIONS = [
  { id: 'N',  name: 'Norte',        nation: 'BR' },
  { id: 'NE', name: 'Nordeste',     nation: 'BR' },
  { id: 'CO', name: 'Centro-Oeste', nation: 'BR' },
  { id: 'SE', name: 'Sudeste',      nation: 'BR' },
  { id: 'S',  name: 'Sul',          nation: 'BR' },
];

// 27 UFs do Brasil, ligadas à sua região.
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
  disabledReason,
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

  const allKeys  = items.map(x => x[keyAttr]);
  const allSet   = new Set(allKeys);
  const allOn    = () => setSelected(new Set(allKeys));
  const allOff   = () => setSelected(new Set());
  const allInv   = () => setSelected(new Set(allKeys.filter(k => !selected.has(k))));

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
        selectedCount={selected.size}
        totalCount={items.length}
        compact={true}
      />
    </div>
  );
}

// ==================================================================
function FilterMenu() {
  const [open, setOpen] = useState(true);

  // multi-selects (Sets)
  const [products, setProducts] = useState(new Set(PEVS.map(p => p.code)));
  const [flags,    setFlags]    = useState(new Set(['OK', 'ESTIMATED']));
  const [nations,  setNations]  = useState(new Set(['BR']));
  const [regions,  setRegions]  = useState(new Set(REGIONS.map(r => r.id)));
  const [states,   setStates]   = useState(new Set(STATES.map(s => s.uf)));
  const [munis,    setMunis]    = useState(new Set()); // none = "todos" by default

  // search strings, one per multi-select
  const [qProducts, setQProducts] = useState('');
  const [qFlags,    setQFlags]    = useState('');
  const [qNations,  setQNations]  = useState('');
  const [qRegions,  setQRegions]  = useState('');
  const [qStates,   setQStates]   = useState('');
  const [qMunis,    setQMunis]    = useState('');

  // period
  const [quickRange, setQuickRange] = useState('all');
  const [startDate,  setStartDate]  = useState('1986-01');
  const [endDate,    setEndDate]    = useState('2024-12');

  // financeiro
  const [currency,   setCurrency]   = useState('BRL');
  const [correction, setCorrection] = useState('IPCA');

  // ----- cascade-aware lists (children gated by parent selection)
  const eligibleRegions = useMemo(
    () => REGIONS.filter(r => nations.has(r.nation)),
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

  // products / flags filtered by search
  const filteredProducts = useMemo(() => {
    if (!qProducts) return PEVS;
    const q = qProducts.toLowerCase();
    return PEVS.filter(p =>
      p.name.toLowerCase().includes(q) || p.code.includes(q)
    );
  }, [qProducts]);
  const filteredFlags = useMemo(() => {
    if (!qFlags) return QUALITY;
    const q = qFlags.toLowerCase();
    return QUALITY.filter(f =>
      f.label.toLowerCase().includes(q) || f.flag.toLowerCase().includes(q)
    );
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
    if (which === 'start') setStartDate(v); else setEndDate(v);
    setQuickRange(null);
  };

  // summary
  const summary = useMemo(() => {
    const prodTxt = products.size === PEVS.length
      ? `${PEVS.length} produtos (todos)`
      : `${products.size} de ${PEVS.length} produtos`;
    const period = `${formatMonth(startDate)}–${formatMonth(endDate)}`;
    const geoTxt =
      nations.size === NATIONS.length && regions.size === REGIONS.length && states.size === STATES.length && munis.size === 0
        ? 'todo o território'
        : nations.size === 1 && nations.has('BR') && states.size === STATES.length && munis.size === 0
        ? 'Brasil · todos os estados'
        : `${nations.size} nação(ões), ${states.size} UF, ${munis.size || 'todos'} municípios`;
    return { prodTxt, period, geoTxt };
  }, [products, startDate, endDate, nations, regions, states, munis]);

  // restore defaults
  const restoreDefaults = () => {
    setProducts(new Set(PEVS.map(p => p.code)));
    setFlags(new Set(['OK', 'ESTIMATED']));
    setNations(new Set(['BR']));
    setRegions(new Set(REGIONS.map(r => r.id)));
    setStates(new Set(STATES.map(s => s.uf)));
    setMunis(new Set());
    applyQuick('all');
    setCurrency('BRL');
    setCorrection('IPCA');
    [setQProducts, setQFlags, setQNations, setQRegions, setQStates, setQMunis].forEach(fn => fn(''));
  };

  return (
    <div className="fm-page">
      <BackdropContext />

      {open && (
        <div className="fm-backdrop" onClick={() => setOpen(false)}>
          <div className="fm-note">Clique fora para fechar</div>
          <div className="fm-modal wide" onClick={(e) => e.stopPropagation()} role="dialog" aria-labelledby="fm-title">
            {/* HEADER */}
            <header className="fm-head">
              <div className="fm-head-text">
                <span className="fm-head-over">Inteligência de mercado · Commodities</span>
                <span id="fm-title" className="fm-title">Filtros</span>
                <span className="fm-summary">
                  <strong>{summary.prodTxt}</strong> · {summary.period} ·{' '}
                  <strong>{currency}</strong> em <strong>{correction}</strong> · {summary.geoTxt}
                </span>
              </div>
              <button className="fm-close" onClick={() => setOpen(false)} aria-label="Fechar">
                {I.close}
              </button>
            </header>

            <div className="fm-body">

            {/* ─── 01 · COMMODITIES ─────────────────────────── */}
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">01</span>Produtos · PEVS</span>
                  <SearchInput value={qProducts} onChange={setQProducts} placeholder="Buscar produto ou código…"/>
                </div>
                <span className="fm-section-meta">
                  <strong>{products.size}</strong> de {PEVS.length} selecionados
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
                  all={()    => setProducts(new Set(PEVS.map(p => p.code)))}
                  none={()   => setProducts(new Set())}
                  invert={() => setProducts(new Set(PEVS.filter(p => !products.has(p.code)).map(p => p.code)))}
                  selectedCount={products.size}
                  totalCount={PEVS.length}
                />
              </div>
            </section>

            {/* ─── 02 · PERÍODO + FINANCEIRO ────────────────── */}
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">02</span>Período &amp; conversão monetária</span>
                </div>
                <span className="fm-section-meta">
                  {formatMonth(startDate)}–{formatMonth(endDate)} · {currency} em {correction}
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
                           value={startDate} min="1986-01" max={endDate}
                           onChange={(e) => onDateChange('start', e.target.value)}/>
                  </div>
                  <div className="fm-arrow">{I.arrow}</div>
                  <div className="fm-date-field">
                    <label htmlFor="fm-end">Fim</label>
                    <input id="fm-end" className="fm-date" type="month"
                           value={endDate} min={startDate} max="2024-12"
                           onChange={(e) => onDateChange('end', e.target.value)}/>
                  </div>
                </div>
              </div>

              <div className="fm-divider" aria-hidden="true"></div>

              {/* FINANCEIRO */}
              <div className="fm-col">
                <div className="fm-col-head">
                  <span className="fm-section-label">Convenção monetária</span>
                  <span className="fm-section-meta">
                    val_real_{correction.toLowerCase().replace('-','_')}_{currency.toLowerCase()}
                  </span>
                </div>

                <div className="fm-sub">
                  <span className="fm-sub-label">Moeda</span>
                  <div className="seg">
                    {['BRL', 'USD', 'EUR', 'CNY'].map(c => (
                      <button key={c} type="button"
                              className={'seg-opt ' + (currency === c ? 'on' : '')}
                              onClick={() => setCurrency(c)}>
                        {c}
                        <small>
                          {c === 'BRL' ? 'R$' : c === 'USD' ? 'US$' : c === 'EUR' ? '€' : '¥'}
                        </small>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="fm-sub">
                  <span className="fm-sub-label">Correção monetária</span>
                  <div className="seg">
                    {[
                      { id: 'IPCA',    sub: 'IBGE' },
                      { id: 'IGP-M',   sub: 'FGV' },
                      { id: 'IGP-DI',  sub: 'FGV' },
                      { id: 'Nominal', sub: 'sem correção' },
                    ].map(o => (
                      <button key={o.id} type="button"
                              className={'seg-opt ' + (correction === o.id ? 'on' : '')}
                              onClick={() => setCorrection(o.id)}>
                        {o.id}
                        <small>{o.sub}</small>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
            </section>

            {/* ─── 03 · GEOGRAFIA (4 cascading columns) ────── */}
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">03</span>Geografia</span>
                  <span className="fm-cascade-hint">
                    {I.cascade} Seleção em cascata · nação ▸ região ▸ estado ▸ município
                  </span>
                </div>
                <span className="fm-section-meta">
                  <strong>{nations.size}</strong> nações ·{' '}
                  <strong>{regions.size}</strong> regiões ·{' '}
                  <strong>{states.size}</strong> UFs ·{' '}
                  <strong>{munis.size || 'todos'}</strong> municípios
                </span>
              </div>

              <div className="fm-section-inner">
              <div className="fm-geo-grid">
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
              </div>

              <div className="fm-geo-foot">
                <span className="fm-section-meta">
                  Lista parcial: {MUNICIPALITIES.length} municípios líderes em PEVS.{' '}
                  <a href="#" onClick={(e) => e.preventDefault()}>Carregar todos os 5 570</a>
                </span>
              </div>
              </div>
            </section>

            {/* ─── 04 · CONFIANÇA DOS DADOS ─────────────────── */}
            <section className="fm-section">
              <div className="fm-section-head">
                <div className="fm-section-head-l">
                  <span className="fm-section-label"><span className="fm-section-num">04</span>Confiança dos dados · <span className="mono lowercase">data_quality_flag</span></span>
                  <SearchInput value={qFlags} onChange={setQFlags} placeholder="Buscar tag…"/>
                </div>
                <span className="fm-section-meta">
                  <strong>{flags.size}</strong> de {QUALITY.length} selecionadas
                </span>
              </div>

              <div className="fm-section-inner">
                <div className="fm-grid-scroll">
                  <div className="fm-grid">
                    {filteredFlags.length === 0 ? (
                      <div className="fm-empty-grid">Nenhuma tag corresponde a “{qFlags}”.</div>
                    ) : filteredFlags.map(q => {
                      const on = flags.has(q.flag);
                      return (
                        <label key={q.flag} className={'fm-check' + (on ? ' is-on' : '')}>
                          <input type="checkbox" checked={on}
                                 onChange={() => setFlags(s => toggleIn(s, q.flag))}/>
                          <span className="fm-name">{q.label}</span>
                          <span className={'chip ' + q.chip}>{q.flag}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                <BulkActions
                  all={()    => setFlags(new Set(QUALITY.map(q => q.flag)))}
                  none={()   => setFlags(new Set())}
                  invert={() => setFlags(new Set(QUALITY.filter(q => !flags.has(q.flag)).map(q => q.flag)))}
                  selectedCount={flags.size}
                  totalCount={QUALITY.length}
                />
              </div>
            </section>

            </div>

            {/* FOOTER */}
            <footer className="fm-foot">
              <div className="fm-foot-info">
                Os filtros serão aplicados sobre <strong>gold_commodity_matrix</strong>
                <span className="fm-dot"></span>
                Atualização diária às 06h00 BRT
              </div>
              <button className="btn-ghost" onClick={restoreDefaults}>Restaurar padrão</button>
              <button className="btn-secondary" onClick={() => setOpen(false)}>Cancelar</button>
              <button className="btn-primary" onClick={() => setOpen(false)}>Aplicar filtros</button>
            </footer>
          </div>
        </div>
      )}

      {!open && (
        <div style={{position:'fixed', inset:0, display:'grid', placeItems:'center', zIndex: 41}}>
          <button className="btn-primary" onClick={() => setOpen(true)}>
            {I.filter}
            <span style={{marginLeft:6}}>Abrir filtros</span>
          </button>
        </div>
      )}
    </div>
  );
}

// ----- backdrop context (dashboard chrome behind the modal) ------
function BackdropContext() {
  return (
    <>
      <header className="topbar">
        <div className="brand" style={{color:'#fff', fontFamily:'var(--font-display)', fontWeight:900, fontStyle:'italic', fontSize:17, letterSpacing:'-0.01em'}}>
          Embrapa
        </div>
        <div className="sep" aria-hidden="true"></div>
        <div className="product-name">Inteligência de Mercado · Commodities</div>
        <nav className="topnav">
          <a className="topnav-item active">Visão geral</a>
          <a className="topnav-item">Produtos</a>
          <a className="topnav-item">Geografia</a>
          <a className="topnav-item">Tabela</a>
        </nav>
        <div className="util">
          <span className="util-chip">PEVS 2024 · atualizado 27/05</span>
          <div className="avatar">JS</div>
        </div>
      </header>

      <div className="fm-page-hero">
        <div className="overline">Painel · Visão geral</div>
        <h1>Produção extrativa vegetal — séries históricas</h1>
        <p>Volume e valor por produto, estado e ano, corrigidos por convenção monetária. Use os filtros para refinar a série exibida.</p>
      </div>

      <div className="fm-stage">
        <div className="fm-trigger-bar">
          <span className="fm-tb-label">Filtros ativos</span>
          <span className="fm-chip-filter"><span className="fm-chip-k">Produtos</span> Todos (12)</span>
          <span className="fm-chip-filter"><span className="fm-chip-k">Período</span> 1986–2024</span>
          <span className="fm-chip-filter"><span className="fm-chip-k">Moeda</span> BRL · IPCA</span>
          <span className="fm-chip-filter"><span className="fm-chip-k">Geografia</span> Brasil · 27 UFs</span>
          <span className="fm-chip-filter"><span className="fm-chip-k">Qualidade</span> OK · Estimated</span>
          <span className="fm-spacer"></span>
          <button className="fm-edit-btn">{I.pencil} Editar filtros</button>
        </div>
      </div>
    </>
  );
}

function formatMonth(iso) {
  if (!iso) return '—';
  const [y, m] = iso.split('-');
  return `${m}/${y}`;
}

window.FilterMenu = FilterMenu;
