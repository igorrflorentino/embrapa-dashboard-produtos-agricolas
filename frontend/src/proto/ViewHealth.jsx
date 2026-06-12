// ViewHealth — institutional "Saúde do sistema" page.
// Operational status: data freshness, Gold provenance, alerts. Every fact here
// is read from the LIVE backend seam (window.dataStore.meta — overlaid from
// /api/source-meta) or the per-banco snapshot. Where no backend source exists
// for an operational metric (run history, run duration, SLA windows, row deltas),
// the page honestly empty-states ('—' / 'não monitorado') instead of inventing.

const { useState: useHsState, useEffect: useHsEffect } = React;

function ViewHealth() {
  const bancos = window.visibleBancos ? window.visibleBancos() : (window.BANCOS || []);

  // ── Live provenance bootstrap ───────────────────────────────────────────
  // Saúde is an info-page: reached via ?ip=health it renders OUTSIDE the data
  // boundary, so no banco snapshot loads first and /api/source-meta is never
  // fetched — meta() would fall back to the frozen registry literal (stale Gold
  // stamp). Proactively fetch the meta for every live banco on mount, and
  // subscribe so the page re-renders to the REAL Gold metadata once it resolves.
  const [, forceHs] = useHsState(0);
  useHsEffect(() => window.dataStore.subscribe(() => forceHs(n => n + 1)), []);
  useHsEffect(() => {
    if (!(window.dataStore && window.dataStore.loadMeta)) return;
    bancos.filter(b => b.status === 'live').forEach(b => window.dataStore.loadMeta(b.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Per-banco OPERATIONAL facts — read from the LIVE provenance seam ─────
  // window.dataStore.meta(id) returns the registry declaration OVERLAID with the
  // real Gold metadata (/api/source-meta): last refresh, coverage counters, table.
  // Until a banco's snapshot has loaded, meta() falls back to the registry prov —
  // the honest pre-resolution value, never a fabricated one.
  const metaOf = (id) => (window.dataStore && window.dataStore.meta ? window.dataStore.meta(id) : {}) || {};
  const provFacts = (id) => {
    const m = metaOf(id);
    const cov = m.coverage || {};
    const prov = m.prov || {};
    return {
      lastRun: m.refresh || '—',
      goldRows: cov.totalRows != null ? cov.totalRows : prov.totalRows,
      sourcePublished: prov.lastCropDate || '—',
    };
  };
  const STATE = {};
  bancos.forEach(b => { STATE[b.id] = provFacts(b.id); });

  // ── Active alerts — DERIVED from real signals only ──────────────────────
  // The only operational signal this repo actually has is the per-banco quality
  // timeseries (snapshot.qualityTs). If the most recent year's OUTLIER share is
  // materially above its historical mean, that is a genuine alert. Provenance
  // (última safra publicada) is a factual coverage note read from real meta().
  // There is NO incident/ticket backend — we never fabricate one.
  const buildAlerts = () => {
    const out = [];

    // Factual coverage note: the latest published crop, read from live provenance.
    const pevMeta = metaOf('ibge_pevs');
    const pevProv = pevMeta.prov || {};
    if (pevProv.lastCrop) {
      out.push({
        level: 'info',
        title: `Última safra publicada: ${pevProv.lastCrop}`,
        desc: `O banco IBGE PEVS reflete a safra mais recente divulgada pelo IBGE${pevProv.lastCropDate ? ` (${pevProv.lastCropDate})` : ''}. Edições mais recentes só aparecem após a publicação oficial.`,
        since: pevProv.lastCropDate || pevMeta.refresh || null,
      });
    }

    // Real outlier signal from the loaded snapshot, when available.
    const snap = (window.dataStore && window.dataStore.get) ? window.dataStore.get('ibge_pevs') : null;
    const qts = (snap && Array.isArray(snap.qualityTs)) ? snap.qualityTs : null;
    if (qts && qts.length >= 2) {
      const latest = qts[qts.length - 1];
      const hist = qts.slice(0, -1);
      const histMean = hist.reduce((s, d) => s + (d.outlier || 0), 0) / hist.length;
      // Flag only a meaningful jump (>50% above the historical mean) to avoid noise.
      if (latest && latest.outlier != null && histMean > 0 && latest.outlier > histMean * 1.5) {
        out.push({
          level: 'warn',
          banco: 'ibge_pevs',
          title: `OUTLIER acima da média histórica · ${latest.y}`,
          desc: `O detector estatístico marcou ${window.fmtPct(latest.outlier)} das linhas em ${latest.y} (média histórica: ${window.fmtPct(histMean)}).`,
          since: pevMeta.refresh || null,
        });
      }
    }

    return out;
  };
  const ALERTS = buildAlerts();

  // Coverage lint: every visible banco should have a provenance seam (STATE).
  if (window.auditBancoCoverage) {
    window.auditBancoCoverage('saúde · execução por banco (ViewHealth.jsx)',
      (b) => STATE[b.id] && STATE[b.id].lastRun, { onlyLive: true });
  }

  // ── Operational HEALTH — DERIVED FROM REAL SIGNALS, not from maturity ────
  // Answers "is it operating well RIGHT NOW?" from the signals we actually have:
  // load failure, stale cache, an active (real) banco alert. "Source down" is
  // HEALTH ("Falha"), never a maturity stage. No fabricated run-status feeds this.
  const operationalStatus = (b) => {
    const m = window.maturityMeta(b);
    if (!m.hasData) return b.maturity === 'planejado' ? 'planned' : 'pending'; // nothing operating yet
    if (window.dataStore && window.dataStore.error(b.id)) return 'fail';        // source down / load failure
    const al = ALERTS.find(a => a.banco === b.id && (a.level === 'warn' || a.level === 'fail'));
    if (al) return al.level;                                                    // active (real) banco alert
    if (window.dataStore && window.dataStore.isStale(b.id)) return 'warn';      // stale snapshot
    return 'ok';
  };
  bancos.forEach(b => { STATE[b.id] = STATE[b.id] || {}; STATE[b.id].status = operationalStatus(b); });

  // ── KPI strip aggregates ────────────────────────────────────────────────
  const liveDefined  = bancos.filter(b => b.status === 'live');
  const liveBancos   = liveDefined.filter(b => STATE[b.id]?.status === 'ok');
  const pendingCount = bancos.filter(b => b.status === 'soon').length;
  const activeAlerts = ALERTS.filter(a => a.level === 'warn' || a.level === 'fail').length;

  // Last Gold refresh = the live provenance stamp (real /api/source-meta value,
  // registry fallback before it resolves). No synthetic duration/error counters.
  const liveBanco = bancos.find(b => b.id === 'ibge_pevs');
  const liveRefresh = metaOf('ibge_pevs').refresh || '—';

  // Overall system status = worst of the live bancos + any active (real) warn alert.
  const liveStatuses = liveDefined.map(b => STATE[b.id]?.status).filter(Boolean);
  const overall = liveStatuses.includes('fail') ? 'fail'
    : (liveStatuses.includes('warn') || ALERTS.some(a => a.level === 'warn')) ? 'warn'
    : 'ok';
  const OVERALL = {
    ok:   { color: 'var(--ok)',   label: 'Operacional', note: 'todos os bancos em produção respondendo às consultas' },
    warn: { color: 'var(--warn)', label: 'Em atenção',  note: `${ALERTS.filter(a => a.level === 'warn').length} alerta(s) de atenção em aberto` },
    fail: { color: 'var(--err)',  label: 'Falha',       note: 'há banco com falha de consulta — verifique a tabela por banco' },
  }[overall];

  const STATUS_LABEL = {
    ok:      { label: 'Saudável',          color: 'var(--ok)'   },
    warn:    { label: 'Em atenção',        color: 'var(--warn)' },
    fail:    { label: 'Falha',             color: 'var(--err)'  },
    pending: { label: 'Aguardando ingestão', color: 'var(--fg-3)' },
    planned: { label: 'Planejado',         color: 'var(--pres-gray-400)' },
    info:    { label: 'Informativo',       color: 'var(--info)' },
  };

  const fmtRows = window.fmtRows;  // shared compact mi/mil counter (data.js)

  return (
    <div className="ab-stack">
      {/* KPI strip */}
      <div className="kpi-row hs-kpi-row">
        <window.KpiCardSpark
          label="Status geral do sistema"
          value={
            <span className="hs-status-pill" style={{ '--st-color': OVERALL.color }}>
              <span className="hs-dot" style={{ background: OVERALL.color }}></span>
              {OVERALL.label}
            </span>
          }
          sub={OVERALL.note}
        />
        <window.KpiCardSpark
          label="Bancos saudáveis"
          value={`${liveBancos.length} / ${liveDefined.length}`}
          sub={`${pendingCount} aguardando ingestão`}
          spark={window.QUALITY_TS.slice(-12)}
          sparkKey="ok"
          sparkColor="var(--ok)"
        />
        <window.KpiCardSpark
          label="Última atualização da Gold"
          value={liveRefresh}
          sub={`${liveBanco?.id || '—'} · ${window.bancoTable('ibge_pevs') || '—'}`}
        />
        <window.KpiCardSpark
          label="Alertas ativos"
          value={activeAlerts.toString()}
          sub={activeAlerts === 0 ? 'nenhum alerta em aberto' : `${activeAlerts} aviso(s) de atenção`}
        />
      </div>

      {/* Gold provenance (real metadata via /api/source-meta) */}
      <div className="card">
        <window.SectionHeader
          overline="Pushdown · Cloud Run stateless"
          title="Consultas ao BigQuery e proveniência da Gold"
        />
        <div className="hs-snap">
          <div className="hs-snap-row">
            <span className="meta-label">Tabela Gold (IBGE PEVS)</span>
            <span className="meta-val tnum"><code>{window.bancoTable('ibge_pevs') || '—'}</code></span>
          </div>
          <div className="hs-snap-row">
            <span className="meta-label">Versão da Gold</span>
            <span className="meta-val tnum">{metaOf('ibge_pevs').version || '—'}</span>
          </div>
          <div className="hs-snap-row">
            <span className="meta-label">Última atualização</span>
            <span className="meta-val tnum">{metaOf('ibge_pevs').refresh || '—'}</span>
          </div>
          <p className="caption hs-snap-note">
            No deploy, o Cloud Run é stateless: cada interação vira uma consulta SQL parametrizada
            empurrada ao BigQuery, e o <strong>flask-caching</strong> memoiza os resultados pequenos por
            parâmetro + versão da Gold. Os valores acima vêm da própria tabela de metadados da Gold
            (<code>/api/source-meta</code>); antes de resolverem, exibem a declaração do registro como
            fallback honesto.
          </p>
        </div>
      </div>

      {/* Per-banco status table */}
      <div className="card">
        <window.SectionHeader
          overline="Saúde por banco de dados"
          title="Estado atual da pipeline em cada fonte"
          action={<span className="caption">{bancos.length} bancos monitorados</span>}
        />
        <div className="hs-table-wrap">
          <table className="hs-table">
            <thead>
              <tr>
                <th>Banco</th>
                <th>Maturidade</th>
                <th>Operação</th>
                <th>Última atualização Gold</th>
                <th>Linhas Gold</th>
                <th>Fonte publicada</th>
              </tr>
            </thead>
            <tbody>
              {bancos.map(b => {
                const s = STATE[b.id] || { status: 'pending' };
                const meta = STATUS_LABEL[s.status];
                return (
                  <tr key={b.id}>
                    <td>
                      <div className="hs-banco">
                        <span className="hs-banco-short">{b.short}</span>
                        <span className="hs-banco-table"><code>{window.bancoTable(b.id)}</code></span>
                      </div>
                    </td>
                    <td>
                      <window.MaturityTag banco={b} size="sm" />
                    </td>
                    <td>
                      <span className="hs-status-pill" style={{ '--st-color': meta.color }}>
                        <span className="hs-dot" style={{ background: meta.color }}></span>
                        {meta.label}
                      </span>
                    </td>
                    <td className="tnum">{s.lastRun || '—'}</td>
                    <td className="tnum">
                      {s.goldRows != null ? fmtRows(s.goldRows) : '—'}
                    </td>
                    <td className="tnum">{s.sourcePublished || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Maturity legend */}
      <div className="card">
        <window.SectionHeader
          overline="Maturidade"
          title="O que cada estágio significa"
          action={<span className="caption">eixo de ciclo de vida do banco</span>}
        />
        <window.MaturityLegend />
      </div>

      {/* Run history — NOT MONITORED (no run-history backend) */}
      <div className="card">
        <window.SectionHeader
          overline="Execuções recentes"
          title="Histórico de execuções da pipeline"
          action={<span className="caption">não monitorado</span>}
        />
        <p className="caption" style={{ padding: '12px 4px' }}>
          O histórico diário de execuções (sucesso/aviso/falha por dia) ainda não é coletado por este
          painel — não há fonte de telemetria de runs exposta ao frontend. Quando essa instrumentação
          existir, a faixa de execuções aparecerá aqui. Até lá, a saúde por banco acima reflete o estado
          real das consultas à Gold.
        </p>
      </div>

      {/* Sources freshness — real provenance per live banco */}
      <div className="card">
        <window.SectionHeader
          overline="Frescor das fontes"
          title="Quando cada fonte publicou pela última vez"
          action={<span className="caption">{liveDefined.length} fonte(s) em produção</span>}
        />
        <div className="hs-sources">
          {bancos.map(b => {
            const m = metaOf(b.id);
            const prov = m.prov || {};
            const isLive = b.status === 'live';
            const lastPub = isLive ? (prov.lastCropDate || prov.lastCrop || '—') : '—';
            return (
              <div key={b.id} className={'hs-source ' + (isLive ? 'live' : 'pending')}>
                <div className="hs-source-l">
                  <div className="hs-source-name">{b.short}</div>
                  <div className="hs-source-meta">
                    <code>{window.bancoTable(b.id) || '—'}</code>
                    {b.source ? <> · {b.source}</> : null}
                  </div>
                </div>
                <div className="hs-source-r">
                  <span className="meta-label">Última publicação</span>
                  <span className="meta-val tnum">{lastPub}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Active alerts */}
      <div className="card">
        <window.SectionHeader
          overline="Alertas ativos"
          // Count only warn/fail as "avisos" (matching the KPI strip); info items
          // are factual coverage notes, not open alerts.
          title={`${ALERTS.filter(a => a.level !== 'info').length} aviso(s) em aberto`}
        />
        <div className="hs-alerts">
          {ALERTS.length === 0 ? (
            <p className="caption" style={{ padding: '12px 4px' }}>Nenhum alerta ativo no momento.</p>
          ) : ALERTS.map((a, i) => {
            const meta = STATUS_LABEL[a.level];
            return (
              <div key={i} className={'hs-alert hs-alert-' + a.level}>
                <div className="hs-alert-head">
                  <span className="hs-status-pill" style={{ '--st-color': meta.color }}>
                    <span className="hs-dot" style={{ background: meta.color }}></span>
                    {meta.label}
                  </span>
                  <span className="hs-alert-title">{a.title}</span>
                  {a.since && <span className="hs-alert-since caption">desde {a.since}</span>}
                </div>
                <p className="hs-alert-desc">{a.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Quality trend cross-link */}
      <div className="card">
        <window.SectionHeader
          overline="Qualidade dos dados · histórico"
          title="% de linhas íntegras (flag = OK) · IBGE PEVS"
          action={<span className="caption">Para diagnóstico completo, veja Qualidade dos dados</span>}
        />
        <window.LineChart
          data={window.QUALITY_TS.map(d => ({ y: d.y, v: d.ok * 100 }))}
          label="% OK"
          valueKey="v"
          color="var(--ok)"
          height={220}
        />
      </div>
    </div>
  );
}

window.ViewHealth = ViewHealth;
