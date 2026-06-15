// DataBoundary.jsx — React glue for the pushdown query boundary:
//   • useBancoData(bancoId)  — query lifecycle + freshness polling
//   • FreshnessBanner        — "dados atualizados disponíveis · Recarregar"
//   • DataLoading            — skeleton shown while the pushdown query runs

const { useState: useDBState, useEffect: useDBEffect } = React;

function useBancoData(bancoId) {
  const [, force] = useDBState(0);

  useDBEffect(() => {
    const unsub = window.dataStore.subscribe(() => force(n => n + 1));
    window.dataStore.load(bancoId);
    return unsub;
  }, [bancoId]);

  // NOTE: no periodic freshness poll. dataStore.isStale() is intentionally always
  // false (there is no live Gold-version signal yet — see dataStore.js), so the
  // FreshnessBanner can never fire; a setInterval(force) here only re-ran
  // applyFilters + every chart trace build on a fixed cadence for nothing. The
  // subscribe() above already re-renders on real store changes. Re-introduce a
  // poll here ONLY alongside a real version check (poll /api/source-meta and
  // compare lastRefresh to the load time), so the re-render does actual work.

  return {
    status:   window.dataStore.status(bancoId),
    stale:    window.dataStore.isStale(bancoId),
    error:    window.dataStore.error(bancoId),
    loadedAt: window.dataStore.loadedAt(bancoId),
    version:  window.dataStore.version(bancoId),
    latestAt: window.dataStore.latestAt(bancoId),
    reload:   () => window.dataStore.load(bancoId),
  };
}

function FreshnessBanner({ banco, latestAt, onReload }) {
  const [reloading, setReloading] = useDBState(false);
  const handle = () => {
    setReloading(true);
    Promise.resolve(onReload()).then(() => setReloading(false));
  };
  return (
    <div className="fresh-banner">
      <span className="fresh-dot"></span>
      <span className="fresh-text">
        Nova versão da Gold publicada{latestAt && latestAt !== '—' ? ` · ${latestAt}` : ''}.
        Os resultados em cache estão desatualizados.
      </span>
      <button className="fresh-btn" onClick={handle} disabled={reloading}>
        <window.Icon name="refresh" size={14} />
        {reloading ? 'Recarregando…' : 'Recarregar dados'}
      </button>
    </div>
  );
}

function DataLoading({ banco }) {
  return (
    <div className="dl-wrap">
      <div className="dl-head">
        <span className="dl-spinner"></span>
        <div>
          <div className="dl-title">Consultando {banco ? banco.short : 'dados'}…</div>
          <div className="dl-sub">Executando consulta no BigQuery (Serving Layer · pré-agregada)</div>
        </div>
      </div>
      <div className="dl-skel-row">
        <div className="dl-skel kpi"></div><div className="dl-skel kpi"></div>
        <div className="dl-skel kpi"></div><div className="dl-skel kpi"></div>
      </div>
      <div className="dl-skel-row">
        <div className="dl-skel card"></div><div className="dl-skel card"></div>
      </div>
    </div>
  );
}

function DataError({ banco, message, onRetry }) {
  const [retrying, setRetrying] = useDBState(false);
  const handle = () => {
    setRetrying(true);
    Promise.resolve(onRetry()).then(() => setRetrying(false));
  };
  return (
    <div className="derr-wrap">
      <div className="derr-card">
        <div className="derr-icon">
          <window.Icon name="warning" size={28} />
        </div>
        <h2 className="derr-title">Não foi possível carregar {banco ? banco.short : 'os dados'}</h2>
        <p className="derr-msg">{message || 'Ocorreu um erro ao consultar a tabela Gold no BigQuery.'}</p>
        <p className="derr-hint">
          As consultas são enviadas ao BigQuery sob demanda. Se a falha persistir,
          verifique a disponibilidade da fonte Gold e tente novamente.
        </p>
        <button className="derr-btn" onClick={handle} disabled={retrying}>
          <window.Icon name="refresh" size={14} />
          {retrying ? 'Tentando novamente…' : 'Tentar novamente'}
        </button>
      </div>
    </div>
  );
}

Object.assign(window, { useBancoData, FreshnessBanner, DataLoading, DataError });
