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
  // Resolve the live maturity (/api/source-meta) for EVERY banco — even on a cold
  // deep link straight to ?ip=health, where no data view loaded first. main.jsx also
  // eager-loads this; loadMeta dedupes, so the duplicate is free.
  useHsEffect(() => {
    if (!(window.dataStore && window.dataStore.loadMeta)) return;
    bancos.forEach(b => window.dataStore.loadMeta(b.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // ACTUALLY query each in-production banco's Gold (not just its metadata), so the
  // per-banco "Operação" is a REAL query result: a banco reads "Saudável" only once
  // its snapshot resolved, "Falha" if the query errored, and "Verificando…" while in
  // flight — instead of assuming health from the maturity flag alone. Re-runs as
  // bancos flip to live once maturity resolves (status derives from it). load()
  // dedupes + caches, and also seeds qualityTs for the quality-history card below.
  const liveIds = bancos.filter(b => b.status === 'live').map(b => b.id);
  useHsEffect(() => {
    if (!(window.dataStore && window.dataStore.load)) return;
    liveIds.forEach(id => window.dataStore.load(id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveIds.join(',')]);

  // Real quality-over-time series for IBGE PEVS (snapshot.qualityTs: per-year OK
  // share, 0-1). NEVER the synthetic window.QUALITY_TS the prototype generated —
  // this is an institutional health page; every fact must come from the live seam.
  const pevSnap = (window.dataStore && window.dataStore.get)
    ? window.dataStore.get('ibge_pevs') : null;
  const qualityTs = (pevSnap && Array.isArray(pevSnap.qualityTs)) ? pevSnap.qualityTs : [];

  // ── Per-banco OPERATIONAL facts — read from the LIVE provenance seam ─────
  // window.dataStore.meta(id) returns the registry declaration OVERLAID with the
  // real Gold metadata (/api/source-meta): last refresh, coverage counters, table.
  // Until a banco's snapshot has loaded, meta() falls back to the registry prov —
  // the honest pre-resolution value, never a fabricated one.
  const metaOf = (id) => (window.dataStore && window.dataStore.meta ? window.dataStore.meta(id) : {});
  const provFacts = (id) => {
    const m = metaOf(id);
    const cov = m.coverage || {};
    const prov = m.prov || {};
    return {
      lastRun: m.refresh || '—',
      goldRows: cov.totalRows ?? null,
      // The latest edition/period in the Gold (e.g. "PEVS 2024", "COMEX 2026 · M05").
      // Its YEAR/months are overlaid live from gold_source_metadata — NOT a frozen
      // publication date (the seam exposes none, so the page never invents one).
      lastEdition: prov.lastCrop || '—',
    };
  };
  const STATE = {};
  bancos.forEach(b => { STATE[b.id] = provFacts(b.id); });

  // ── Active alerts — DERIVED from real signals only ──────────────────────
  // The only operational signal this repo actually has is the per-banco quality
  // timeseries (snapshot.qualityTs: per-year flag SHARES from real Gold). If the
  // most recent year's NON-OK (problem-row) share is materially above its
  // historical mean, that is a genuine integrity alert. Provenance (última safra
  // publicada) is a factual coverage note read from real meta(). There is NO
  // incident/ticket backend — we never fabricate one.
  const buildAlerts = () => {
    const out = [];

    // Factual coverage note: the latest edition in the Gold, read from live
    // provenance (lastCrop year is overlaid from gold_source_metadata). No fabricated
    // publication date — the seam exposes none; the since-stamp is the real refresh.
    const pevMeta = metaOf('ibge_pevs');
    const pevProv = pevMeta.prov || {};
    if (pevProv.lastCrop) {
      out.push({
        level: 'info',
        title: `Última safra na Gold: ${pevProv.lastCrop}`,
        desc: 'O banco IBGE PEVS reflete a safra mais recente já divulgada pelo IBGE. Edições mais recentes só aparecem após a publicação oficial.',
        since: pevMeta.refresh || null,
      });
    }

    // Real integrity signal from the loaded snapshot, when available. The real Gold
    // flags carry OK (=integral); the problem share is 1 − OK. We flag only a
    // MATERIAL jump above the RECENT baseline (the last few years), NOT the all-time
    // mean: PEVS revises its newest years (CLAUDE.md · delta/reconcile), so the share
    // of not-yet-settled rows drifts up gently every year and an all-history mean
    // would breach 1.5× perpetually — painting the system "Em atenção" on normal
    // data. Require enough history + both a relative jump AND an absolute increase.
    const qts = qualityTs.length ? qualityTs : null;
    if (qts && qts.length >= 6) {
      const issueShare = (d) => 1 - (d.ok || 0);
      const latest = qts[qts.length - 1];
      const recent = qts.slice(-6, -1); // the 5 years before the latest = the baseline
      const recentMean = recent.reduce((s, d) => s + issueShare(d), 0) / recent.length;
      const latestIssue = latest ? issueShare(latest) : 0;
      if (latest && latestIssue > recentMean * 1.5 && latestIssue - recentMean >= 0.02) {
        out.push({
          level: 'warn',
          banco: 'ibge_pevs',
          title: `Integridade abaixo do padrão recente · ${latest.y}`,
          desc: `${window.fmtPct(latestIssue)} das linhas em ${latest.y} não estão íntegras (flag ≠ OK); média dos últimos ${recent.length} anos: ${window.fmtPct(recentMean)}.`,
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

  // ── Operational HEALTH — DERIVED FROM THE REAL GOLD QUERY, not from maturity ──
  // Answers "is it operating well RIGHT NOW?" from the actual pushdown query the
  // mount effect fires against each live banco's Gold: 'ready' (responded) → ok,
  // 'error' → Falha, in-flight → Verificando…, plus any active (real) integrity
  // alert → Em atenção. "Source down" is HEALTH ("Falha"), never a maturity stage.
  // No fabricated run-status, and no never-stale guess (staleness isn't monitored).
  const operationalStatus = (b) => {
    const m = window.maturityMeta(b);
    if (!m.hasData) return b.maturity === 'planejado' ? 'planned' : 'pending'; // nothing operating yet
    const st = window.dataStore ? window.dataStore.status(b.id) : 'idle';
    if (st === 'error' || (window.dataStore && window.dataStore.error(b.id))) return 'fail'; // query failed
    if (ALERTS.find(a => a.banco === b.id && a.level === 'warn')) return 'warn'; // active (real) banco alert
    if (st === 'ready') return 'ok';                                            // Gold query succeeded
    return 'checking';            // queried, snapshot still in flight — not yet verified
  };
  bancos.forEach(b => { STATE[b.id] = STATE[b.id] || {}; STATE[b.id].status = operationalStatus(b); });

  // ── KPI strip aggregates ────────────────────────────────────────────────
  const liveDefined  = bancos.filter(b => b.status === 'live');
  const liveBancos   = liveDefined.filter(b => STATE[b.id]?.status === 'ok'); // queried & responded
  const checkingCount = liveDefined.filter(b => STATE[b.id]?.status === 'checking').length;
  const pendingCount = bancos.filter(b => b.status === 'soon').length;
  const activeAlerts = ALERTS.filter(a => a.level === 'warn').length; // buildAlerts emits info/warn only

  // Last Gold refresh of IBGE PEVS specifically (the KPI is scoped to it, mirroring
  // the quality card). Real /api/source-meta value; "—" before it resolves. The
  // OTHER bancos' refresh stamps are in the per-banco table — different tables
  // refresh at different times, so there is no single system-wide "last update".
  const liveRefresh = metaOf('ibge_pevs').refresh || '—';

  // Overall system status = worst of the live bancos' REAL query results. 'checking'
  // (snapshots still in flight) is reported honestly rather than as a premature OK.
  const liveStatuses = liveDefined.map(b => STATE[b.id]?.status).filter(Boolean);
  const overall = liveStatuses.includes('fail') ? 'fail'
    : liveStatuses.includes('warn') ? 'warn'
    : liveStatuses.includes('checking') ? 'checking'
    : 'ok';
  const OVERALL = {
    ok:   { color: 'var(--ok)',   label: 'Operacional', note: `os ${liveBancos.length} bancos em produção responderam às consultas` },
    warn: { color: 'var(--warn)', label: 'Em atenção',  note: `${ALERTS.filter(a => a.level === 'warn').length} alerta(s) de atenção em aberto` },
    fail: { color: 'var(--err)',  label: 'Falha',       note: 'há banco com falha de consulta — verifique a tabela por banco' },
    checking: { color: 'var(--fg-3)', label: 'Verificando…', note: 'consultando as tabelas Gold em produção…' },
  }[overall];

  const STATUS_LABEL = {
    ok:      { label: 'Saudável',          color: 'var(--ok)'   },
    checking:{ label: 'Verificando…',      color: 'var(--fg-3)' },
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
          label="Bancos saudáveis (em produção)"
          value={`${liveBancos.length} / ${liveDefined.length}`}
          sub={`${checkingCount > 0 ? `${checkingCount} verificando · ` : ''}${pendingCount} aguardando ingestão · ${bancos.length} no total`}
        />
        <window.KpiCardSpark
          label="Última atualização da Gold · IBGE PEVS"
          value={liveRefresh}
          sub={`gold_pevs_production · refresh por tabela na lista abaixo`}
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
            <span className="meta-label">Última atualização</span>
            <span className="meta-val tnum">{metaOf('ibge_pevs').refresh || '—'}</span>
          </div>
          <p className="caption hs-snap-note">
            No deploy, o Cloud Run é stateless: cada interação vira uma consulta SQL parametrizada
            empurrada ao BigQuery, e o <strong>flask-caching</strong> memoiza os resultados pequenos por
            parâmetro de consulta. Os valores acima vêm da própria tabela de metadados da Gold
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
          action={<span className="caption">{bancos.length} bancos monitorados · {liveDefined.length} em produção</span>}
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
                <th>Última edição</th>
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
                    <td className="tnum">{s.lastEdition || '—'}</td>
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

      {/* Sources freshness — real provenance per live banco (edition + Gold refresh,
          both live from /api/source-meta; no fabricated publication date). */}
      <div className="card">
        <window.SectionHeader
          overline="Frescor das fontes"
          title="Edição e atualização mais recentes por fonte"
          action={<span className="caption">{liveDefined.length} fonte(s) em produção</span>}
        />
        <div className="hs-sources">
          {bancos.map(b => {
            const m = metaOf(b.id);
            const prov = m.prov || {};
            const isLive = b.status === 'live';
            const lastEd = isLive ? (prov.lastCrop || '—') : '—';
            const refresh = isLive ? (m.refresh || '—') : '—';
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
                  <span className="meta-label">Edição mais recente</span>
                  <span className="meta-val tnum">{lastEd}</span>
                  <span className="meta-label" style={{ marginTop: 4 }}>Atualização da Gold</span>
                  <span className="meta-val tnum">{refresh}</span>
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

      {/* Quality trend cross-link — REAL per-year OK share from the live snapshot
          (snapshot.qualityTs), never the synthetic prototype series. */}
      <div className="card">
        <window.SectionHeader
          overline="Qualidade dos dados · histórico"
          title="% de linhas íntegras (flag = OK) · IBGE PEVS"
          action={<span className="caption">Para diagnóstico completo, veja Qualidade dos dados</span>}
        />
        {qualityTs.length ? (
          <window.LineChart
            data={qualityTs.map(d => ({ y: d.y, v: (d.ok || 0) * 100 }))}
            label="% OK"
            valueKey="v"
            color="var(--ok)"
            height={220}
          />
        ) : (
          <p className="caption" style={{ padding: '12px 4px' }}>
            Carregando a série de qualidade da Gold (IBGE PEVS)…
          </p>
        )}
      </div>
    </div>
  );
}

window.ViewHealth = ViewHealth;
