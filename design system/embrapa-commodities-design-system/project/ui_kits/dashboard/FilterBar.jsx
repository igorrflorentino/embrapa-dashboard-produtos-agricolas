// Filter bar — the top "controls" row of any Looker-style dashboard view.
// Mirrors the filters the user would set on gold_commodity_matrix.

function FilterBar({ filters, setFilters }) {
  const set = (k, v) => setFilters({ ...filters, [k]: v });
  return (
    <div className="filterbar">
      <div className="filter">
        <label>Período</label>
        <div className="seg">
          {['10a', '20a', 'Tudo'].map(opt => (
            <button key={opt}
                    className={'seg-opt ' + (filters.period === opt ? 'on' : '')}
                    onClick={() => set('period', opt)}>{opt}</button>
          ))}
        </div>
      </div>

      <div className="filter">
        <label>Produto</label>
        <select value={filters.product} onChange={e => set('product', e.target.value)}>
          <option value="all">Todos os produtos</option>
          {window.PRODUCTS.map(p => <option key={p.code} value={p.code}>{p.name}</option>)}
        </select>
      </div>

      <div className="filter">
        <label>Estado (UF)</label>
        <select value={filters.uf} onChange={e => set('uf', e.target.value)}>
          <option value="all">Todos</option>
          <option>PA</option><option>AM</option><option>MT</option><option>AC</option>
          <option>RO</option><option>MG</option><option>BA</option><option>TO</option>
        </select>
      </div>

      <div className="filter">
        <label>Convenção monetária</label>
        <div className="seg">
          <button className={'seg-opt ' + (filters.conv === 'ipca' ? 'on' : '')} onClick={() => set('conv', 'ipca')}>IPCA</button>
          <button className={'seg-opt ' + (filters.conv === 'igpm' ? 'on' : '')} onClick={() => set('conv', 'igpm')}>IGP-M</button>
          <button className={'seg-opt ' + (filters.conv === 'yearfx' ? 'on' : '')} onClick={() => set('conv', 'yearfx')}>FX do ano</button>
        </div>
      </div>

      <div className="filter">
        <label>Moeda</label>
        <div className="seg">
          {['BRL', 'USD', 'EUR', 'CNY'].map(c => (
            <button key={c}
                    className={'seg-opt ' + (filters.ccy === c ? 'on' : '')}
                    onClick={() => set('ccy', c)}>{c}</button>
          ))}
        </div>
      </div>

      <div className="filter check-inline">
        <label className="checkbox-row">
          <input type="checkbox" checked={filters.onlyOK}
                 onChange={e => set('onlyOK', e.target.checked)}/>
          <span>Apenas <code className="mono">data_quality_flag = OK</code></span>
        </label>
      </div>

      <div className="filter actions">
        <button className="btn-ghost">Limpar</button>
        <button className="btn-primary">Aplicar</button>
      </div>
    </div>
  );
}

window.FilterBar = FilterBar;
