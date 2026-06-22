// ViewDados — raw tabular inspection of a banco's tables (the researcher's "olhar para a
// tabela de dados" perspective). Lists the banco's Gold table + the serving marts that
// feed its charts; for the selected table it browses the RAW rows with server-side
// pagination, ORDER BY and per-column filters. The column allowlist is the table's OWN
// schema, enforced server-side (a bad column/table → 400). Self-contained (its own fetch
// + state, like ViewProductProfile) — no chart, no rescaling: a faithful window onto the
// data so a researcher can verify line-by-line or hunt a value they suspect is wrong.

const { useState: useDtState, useEffect: useDtEffect } = React;

// Filter operators the UI offers → the server's op ids (validated + bound server-side).
const _DT_OPS = [
  { id: 'eq', label: '=' }, { id: 'ne', label: '≠' },
  { id: 'gt', label: '>' }, { id: 'ge', label: '≥' },
  { id: 'lt', label: '<' }, { id: 'le', label: '≤' },
  { id: 'contains', label: 'contém' },
  { id: 'is_null', label: 'é nulo' }, { id: 'not_null', label: 'não nulo' },
];
const _DT_VALUELESS = new Set(['is_null', 'not_null']);
const _DT_PAGE = 100;       // rows per page
const _DT_EXPORT_CAP = 500; // server's RAW_TABLE_MAX_LIMIT — the most one fetch returns

function _dtCsv(columns, rows) {
  const esc = (v) => {
    if (v == null) return '';
    const s = String(v);
    return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const head = columns.map((c) => esc(c.name)).join(';');
  const body = rows.map((r) => r.map(esc).join(';')).join('\n');
  return '﻿' + head + '\n' + body; // BOM for Excel UTF-8; pt-BR-friendly ';'
}

function _dtDownload(name, csv) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function _dtTableQs(database, table, { limit, offset, order, filters }) {
  const qs = new URLSearchParams({ banco: database, table, limit, offset });
  if (order && order.by) { qs.set('order_by', order.by); qs.set('order_dir', order.dir); }
  if (filters && filters.length) qs.set('filters', JSON.stringify(filters));
  return qs;
}

function ViewDados({ database }) {
  const [tables, setTables] = useDtState([]);
  const [table, setTable] = useDtState(null);
  const [page, setPage] = useDtState({ columns: [], rows: [], total: 0, loading: true, error: null });
  const [offset, setOffset] = useDtState(0);
  const [order, setOrder] = useDtState({ by: null, dir: 'asc' });
  const [filters, setFilters] = useDtState([]);
  const [draft, setDraft] = useDtState({ col: '', op: 'eq', val: '' });

  // Reset the per-table state (offset/order/filters) — used on banco or table change.
  const resetView = () => { setOffset(0); setOrder({ by: null, dir: 'asc' }); setFilters([]); setDraft({ col: '', op: 'eq', val: '' }); };

  // 1) the allowlisted table list for the banco
  useDtEffect(() => {
    let alive = true;
    resetView();
    fetch(`/api/tables?banco=${encodeURIComponent(database)}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((list) => {
        if (!alive) return;
        setTables(Array.isArray(list) ? list : []);
        setTable(list && list[0] ? list[0].id : null);
      })
      .catch(() => { if (alive) { setTables([]); setTable(null); } });
    return () => { alive = false; };
  }, [database]);

  // 2) one page of rows for the selected table + pagination/sort/filter
  useDtEffect(() => {
    if (!table) { setPage({ columns: [], rows: [], total: 0, loading: false, error: null }); return undefined; }
    let alive = true;
    setPage((p) => ({ ...p, loading: true, error: null }));
    const qs = _dtTableQs(database, table, { limit: _DT_PAGE, offset, order, filters });
    fetch(`/api/table?${qs}`)
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => null);
          throw new Error((body && body.error) || `HTTP ${r.status}`);
        }
        return r.json();
      })
      .then((d) => { if (alive) setPage({ columns: d.columns || [], rows: d.rows || [], total: d.total || 0, label: d.label, grain: d.grain, loading: false, error: null }); })
      .catch((e) => { if (alive) setPage({ columns: [], rows: [], total: 0, loading: false, error: String(e.message || e) }); });
    return () => { alive = false; };
  }, [database, table, offset, order, filters]);

  const meta = tables.find((t) => t.id === table) || {};
  const cols = page.columns;
  const total = page.total;
  const pageNum = Math.floor(offset / _DT_PAGE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / _DT_PAGE));

  const toggleSort = (name) => {
    setOffset(0);
    setOrder((o) =>
      o.by !== name ? { by: name, dir: 'asc' }
        : o.dir === 'asc' ? { by: name, dir: 'desc' }
          : { by: null, dir: 'asc' }); // third click clears the sort
  };
  const addFilter = () => {
    if (!draft.col) return;
    setOffset(0);
    setFilters((fs) => [
      ...fs.filter((f) => !(f.col === draft.col && f.op === draft.op)),
      { col: draft.col, op: draft.op, val: draft.val },
    ]);
    setDraft((d) => ({ ...d, val: '' }));
  };
  const removeFilter = (i) => { setOffset(0); setFilters((fs) => fs.filter((_, j) => j !== i)); };

  const exportCsv = () => {
    // Export the CURRENT filter/sort (not just the visible page) up to the server cap.
    const qs = _dtTableQs(database, table, { limit: _DT_EXPORT_CAP, offset: 0, order, filters });
    fetch(`/api/table?${qs}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) _dtDownload(`${database}_${table}.csv`, _dtCsv(d.columns || [], d.rows || [])); })
      .catch(() => {});
  };

  return (
    <>
      {/* Table picker — the banco's principal (Gold) + the marts that feed its charts */}
      <div className="pp-selector">
        <span className="pp-selector-label">
          Tabela do banco <small className="pc-cap">(principal + derivadas dos gráficos)</small>
        </span>
        <div className="pp-chips">
          {tables.map((t) => (
            <button key={t.id} type="button" title={t.grain}
                    className={'pp-chip ' + (t.id === table ? 'on' : '')}
                    onClick={() => { setTable(t.id); resetView(); }}>
              {t.label}
            </button>
          ))}
          {!tables.length && <span className="caption">Nenhuma tabela inspecionável para este banco.</span>}
        </div>
      </div>

      {table && (
        <div className="card">
          <window.SectionHeader
            overline={`Inspeção tabular · ${meta.label || table}`}
            title={`${(total || 0).toLocaleString('pt-BR')} linhas · ${cols.length} colunas`}
            action={
              <button type="button" className="seg-opt" onClick={exportCsv} disabled={!cols.length}>
                Exportar CSV (até {_DT_EXPORT_CAP})
              </button>
            }
          />
          {meta.grain && <p className="caption" style={{ margin: '0 2px 8px' }}>{meta.grain}</p>}

          {/* Filter builder */}
          <div className="dt-filterbar">
            <select value={draft.col} onChange={(e) => setDraft((d) => ({ ...d, col: e.target.value }))}>
              <option value="">coluna…</option>
              {cols.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            <select value={draft.op} onChange={(e) => setDraft((d) => ({ ...d, op: e.target.value }))}>
              {_DT_OPS.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
            </select>
            {!_DT_VALUELESS.has(draft.op) && (
              <input type="text" placeholder="valor" value={draft.val}
                     onChange={(e) => setDraft((d) => ({ ...d, val: e.target.value }))}
                     onKeyDown={(e) => e.key === 'Enter' && addFilter()} />
            )}
            <button type="button" className="seg-opt" onClick={addFilter} disabled={!draft.col}>Filtrar</button>
          </div>
          {filters.length > 0 && (
            <div className="dt-chips">
              {filters.map((f, i) => (
                <span key={i} className="dt-chip">
                  {f.col} {(_DT_OPS.find((o) => o.id === f.op) || {}).label} {!_DT_VALUELESS.has(f.op) ? f.val : ''}
                  <button type="button" onClick={() => removeFilter(i)} aria-label="remover filtro">×</button>
                </span>
              ))}
            </div>
          )}

          {/* Grid */}
          {page.error ? (
            <p className="caption" style={{ padding: '20px 4px', color: 'var(--err)' }}>
              Erro ao carregar: {page.error}
            </p>
          ) : page.loading ? (
            <p className="caption" style={{ padding: '40px 4px', textAlign: 'center' }}>Carregando linhas…</p>
          ) : !page.rows.length ? (
            <p className="caption" style={{ padding: '40px 4px', textAlign: 'center' }}>
              Nenhuma linha para os filtros atuais.
            </p>
          ) : (
            <div className="dt-wrap">
              <table className="dt-table">
                <thead>
                  <tr>
                    {cols.map((c) => (
                      <th key={c.name} onClick={() => toggleSort(c.name)} title={`${c.type} · clique para ordenar`}>
                        {c.name}{order.by === c.name ? (order.dir === 'asc' ? ' ▲' : ' ▼') : ''}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {page.rows.map((row, ri) => (
                    <tr key={ri}>
                      {row.map((v, ci) => (
                        <td key={ci} className={typeof v === 'number' ? 'num tnum' : ''}>
                          {v == null ? <span className="dt-null">∅</span> : String(v)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {!page.loading && !page.error && total > 0 && (
            <div className="dt-pager">
              <button type="button" className="seg-opt" disabled={offset === 0}
                      onClick={() => setOffset(Math.max(0, offset - _DT_PAGE))}>‹ Anterior</button>
              <span className="caption tnum">
                Página {pageNum.toLocaleString('pt-BR')} de {pageCount.toLocaleString('pt-BR')} ·
                {' '}linhas {(offset + 1).toLocaleString('pt-BR')}–{Math.min(offset + _DT_PAGE, total).toLocaleString('pt-BR')}
                {' '}de {total.toLocaleString('pt-BR')}
              </span>
              <button type="button" className="seg-opt" disabled={offset + _DT_PAGE >= total}
                      onClick={() => setOffset(offset + _DT_PAGE)}>Próxima ›</button>
            </div>
          )}
        </div>
      )}
    </>
  );
}

window.ViewDados = ViewDados;
