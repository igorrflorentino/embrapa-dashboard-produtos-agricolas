// ViewHealth — institutional "Saúde do sistema" page.
// Pure operational status: pipeline runs, data freshness, SLAs, alerts.
// Live datasets read from window.QUALITY_TS for the OK trend; everything
// else is synthetic but kept inside the file so it stays auditable.

function ViewHealth() {
  const bancos = window.visibleBancos ? window.visibleBancos() : (window.BANCOS || []);
  // lastRun / goldRows are NOT re-typed here — they track the registry.
  const PEV_PROV = (window.bancoById && window.bancoById('ibge_pevs')?.prov) || {};

  // ── Per-banco OPERATIONAL facts (independent of maturity) ────────────
  // These describe how the pipeline is RUNNING (not how mature it is):
  // last run health, errors, freshness. Synthetic but distinct so the
  // operational column doesn't merely echo the maturity tag.
  const provFacts = (id) => {
    const p = (window.bancoById && window.bancoById(id)?.prov) || {};
    return { lastRun: p.refresh || '—', goldRows: p.totalRows, sourcePublished: p.lastCropDate || '—' };
  };
  const STATE = {
    ibge_pevs: {
      lastRun: PEV_PROV.refresh || '—',
      durationSec: 184,
      goldRows: PEV_PROV.totalRows || 0,
      goldRowsDelta: +42_109,
      sourcePublished: '27 set 2024',
      freshness: 'pré-anual',  // annual-harvest banco
      slaPct: 99.6,
      runOk: true,
      lastRunErrors: 0,
    },
    mdic_comex:  { ...provFacts('mdic_comex'),  durationSec: 96,  goldRowsDelta: +8_240, slaPct: 99.1, runOk: true, lastRunErrors: 0 },
    un_comtrade: { ...provFacts('un_comtrade'), durationSec: 410, goldRowsDelta: +3_110, slaPct: 96.8, runOk: true, lastRunErrors: 0 },
    ibge_pam:    { ...provFacts('ibge_pam'),    durationSec: 152, goldRowsDelta: +12_400, slaPct: 98.3, runOk: true, lastRunErrors: 0 },
    sefaz_nf:    {},
  };

  // ── 14-day pipeline run history ─────────────────────────────────────
  // Recent date list (D-13 → D-0); status per day. Anchored to the real
  // current date so "hoje" and the 14-day window actually advance.
  const today = new Date();
  const RUN_HISTORY = Array.from({ length: 14 }, (_, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() - (13 - i));
    // synthetic but plausible — most OK, one warn, one fail spread out
    const seed = i;
    let status = 'ok';
    if (seed === 4)  status = 'warn';
    if (seed === 9)  status = 'fail';
    return {
      date: d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }),
      iso:  d.toISOString().slice(0, 10),
      status,
      runs: (window.visibleBancos ? window.visibleBancos() : (window.BANCOS || [])).filter(b => b.status === 'live').length,  // connected bancos on the daily calendar
    };
  });

  // ── Sources & freshness ─────────────────────────────────────────────
  const SOURCES = [
    {
      name: 'IBGE SIDRA',
      banco: 'ibge_pevs',
      lastPublished: '27 set 2024',
      lastPublishedIso: '2024-09-27',
      cadence: 'anual',
      url: 'sidra.ibge.gov.br/pesquisa/pevs',
      status: 'live',
    },
    {
      name: 'IBGE SIDRA (PAM)',
      banco: 'ibge_pam',
      lastPublished: 'set 2025',
      lastPublishedIso: '2025-09-15',
      cadence: 'anual',
      url: 'sidra.ibge.gov.br/pesquisa/pam',
      status: 'live',
    },
    {
      name: 'MDIC SECEX',
      banco: 'mdic_comex',
      lastPublished: '—',
      cadence: 'mensal (D+30)',
      url: 'comexstat.mdic.gov.br',
      status: 'pending',
    },
    {
      name: 'UN Comtrade',
      banco: 'un_comtrade',
      lastPublished: '—',
      cadence: 'anual + revisões trimestrais',
      url: 'comtradeplus.un.org',
      status: 'pending',
    },
    {
      name: 'SEFAZ NFe',
      banco: 'sefaz_nf',
      lastPublished: '—',
      cadence: 'diária (D+1)',
      url: 'nfe.fazenda.gov.br',
      status: 'pending',
    },
  ];

  // ── Active alerts ────────────────────────────────────────────────────
  // Coverage lint: live bancos need an operational seed (STATE) and every
  // visible banco an upstream source (SOURCES) — both are curated here.
  if (window.auditBancoCoverage) {
    window.auditBancoCoverage('saúde · execução por banco (ViewHealth.jsx)',
      (b) => STATE[b.id] && STATE[b.id].lastRun, { onlyLive: true });
    window.auditBancoCoverage('saúde · frescor das fontes (ViewHealth.jsx)',
      (b) => SOURCES.some(s => s.banco === b.id));
  }

  const ALERTS = [
    {
      level: 'info',
      title: 'PEVS 2025 em apuração pelo IBGE',
      desc:  'A safra mais recente publicada é a PEVS 2024 (27 set 2024). A edição ano-base 2025 está em apuração, com divulgação prevista para set/2026. Até lá, o banco reflete a safra 2024.',
      since: '27 set 2024',
    },
    {
      level: 'warn',
      banco: 'ibge_pevs',
      title: 'Aumento de OUTLIER em borracha (látex) · 2023',
      desc:  'Detector estatístico marcou 3,2% das linhas (média histórica: 1,8%). Investigação registrada em #DAT-2026-118.',
      since: '14 mai 2026',
    },
  ];

  // ── Operational HEALTH — DERIVED FROM OPERATIONS, not from maturity ───
  // Answers "is it operating well RIGHT NOW?" (runs, freshness, errors,
  // alerts), a distinct axis from "how mature/implemented is it?". That is
  // why an estavel banco can be "Em atenção" (active alert or stale Gold) and
  // a beta banco can be "Saudável" (pipeline running normally). "Source down"
  // is HEALTH ("Falha"), never a maturity stage.
  const operationalStatus = (b) => {
    const m = window.maturityMeta(b);
    if (!m.hasData) return b.maturity === 'planejado' ? 'planned' : 'pending'; // nothing operating yet
    if (window.dataStore && window.dataStore.error(b.id)) return 'fail';      // source down / load failure
    const o = STATE[b.id] || {};
    if (o.runOk === false || (o.lastRunErrors || 0) > 0) return 'fail';       // run failed
    const al = ALERTS.find(a => a.banco === b.id && (a.level === 'warn' || a.level === 'fail'));
    if (al) return al.level;                                                  // active banco alert
    if (window.dataStore && window.dataStore.isStale(b.id)) return 'warn';    // stale snapshot
    if (o.overdue) return 'warn';                                             // freshness overdue
    return 'ok';
  };
  bancos.forEach(b => { STATE[b.id] = STATE[b.id] || {}; STATE[b.id].status = operationalStatus(b); });

  // ── KPI strip aggregates ────────────────────────────────────────────
  const liveDefined  = bancos.filter(b => b.status === 'live');
  const liveBancos   = liveDefined.filter(b => STATE[b.id]?.status === 'ok');
  const pendingCount = bancos.filter(b => b.status === 'soon').length;
  const failsRecent  = RUN_HISTORY.filter(r => r.status === 'fail').length;
  const totalRuns    = RUN_HISTORY.length;
  const slaWindow    = totalRuns ? ((totalRuns - failsRecent) / totalRuns) * 100 : 100;

  // Last pipeline run = the live banco's snapshot facts (no hardcoded KPI).
  const liveBanco = bancos.find(b => b.id === 'ibge_pevs');
  const liveState = STATE.ibge_pevs;
  const fmtDur = (s) => `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`;
  const MONTH_IDX = { jan:0, fev:1, mar:2, abr:3, mai:4, jun:5, jul:6, ago:7, set:8, out:9, nov:10, dez:11 };
  const runDatePart = (liveState.lastRun || '').split(' · ')[0];           // "28 mai 2026"
  const runTimePart = ((liveState.lastRun || '').split(' · ')[1] || '').replace(/\s*BRT/i, ''); // "04:30"
  const rdp = runDatePart.split(/\s+/);                                    // ["28","mai","2026"]
  const runDate = rdp.length >= 3 ? new Date(+rdp[2], MONTH_IDX[rdp[1]?.toLowerCase()] ?? 0, +rdp[0]) : null;
  const runIsToday = runDate && runDate.toDateString() === today.toDateString();
  const lastRunLabel = (runIsToday ? 'hoje' : rdp.slice(0, 2).join(' ')) + (runTimePart ? ' · ' + runTimePart : '');

  // Overall system status = worst of the live bancos + any active warn alert.
  const liveStatuses = liveDefined.map(b => STATE[b.id]?.status).filter(Boolean);
  const overall = liveStatuses.includes('fail') ? 'fail'
    : (liveStatuses.includes('warn') || ALERTS.some(a => a.level === 'warn')) ? 'warn'
    : 'ok';
  const OVERALL = {
    ok:   { color: 'var(--ok)',   label: 'Operacional', note: 'todas as execuções planejadas concluíram nas últimas 24h' },
    warn: { color: 'var(--warn)', label: 'Em atenção',  note: `${ALERTS.filter(a => a.level === 'warn').length} alerta(s) de atenção em aberto` },
    fail: { color: 'var(--err)',  label: 'Falha',       note: 'há execução com falha — verifique a tabela por banco' },
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
          label="Última execução do pipeline"
          value={lastRunLabel}
          sub={`${liveBanco?.id || '—'} · ${fmtDur(liveState.durationSec)} · ${liveState.lastRunErrors} erros`}
        />
        <window.KpiCardSpark
          label="Falhas nos últimos 14 dias"
          value={failsRecent.toString()}
          sub={failsRecent === 0
            ? 'série limpa'
            : `${failsRecent} ${failsRecent === 1 ? 'falha' : 'falhas'} em ${totalRuns} execuções · ${slaWindow.toFixed(1).replace('.', ',')}% SLA`}
        />
      </div>

      {/* Pushdown query cache (Cloud Run stateless model) */}
      <div className="card">
        <window.SectionHeader
          overline="Pushdown · Cloud Run stateless"
          title="Consultas ao BigQuery e cache do serviço"
          action={
            <div className="hdr-actions">
              <button className="btn-ghost" onClick={() => { window.dataStore.simulateError('ibge_pevs'); }}>
                <window.Icon name="warning" size={14} /> Simular falha de consulta
              </button>
              <button className="btn-secondary" onClick={() => window.dataStore.bumpGold('ibge_pevs')}>
                <window.Icon name="refresh" size={14} /> Simular atualização da Gold
              </button>
            </div>
          }
        />
        <div className="hs-snap">
          <div className="hs-snap-row">
            <span className="meta-label">Versão em cache (IBGE PEVS)</span>
            <span className="meta-val tnum">{window.dataStore.version('ibge_pevs') || '—'}</span>
          </div>
          <div className="hs-snap-row">
            <span className="meta-label">Versão upstream na Gold</span>
            <span className="meta-val tnum">{window.dataStore.latestVersion('ibge_pevs') || '—'}</span>
          </div>
          <div className="hs-snap-row">
            <span className="meta-label">Estado do cache</span>
            <span className="meta-val">
              {window.dataStore.isStale('ibge_pevs')
                ? <span style={{ color: 'var(--warn)', fontWeight: 600 }}>Desatualizado · invalidação pendente</span>
                : <span style={{ color: 'var(--ok)', fontWeight: 600 }}>Sincronizado</span>}
            </span>
          </div>
          <p className="caption hs-snap-note">
            No deploy, o Cloud Run é stateless: cada interação vira uma consulta SQL parametrizada
            empurrada ao BigQuery, e o <strong>flask-caching</strong> memoiza os resultados pequenos por
            parâmetro + versão da Gold. "Simular atualização" muda a versão upstream (invalida o cache e
            dispara o aviso de recarga ao voltar para uma view de dados); "Simular falha de consulta"
            arma um erro na próxima consulta do banco, exibindo a tela de erro com opção de tentar novamente.
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
                <th>Última execução Gold</th>
                <th>Linhas Gold</th>
                <th>Fonte publicada</th>
                <th className="num">SLA 30d</th>
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
                    <td className="tnum">
                      {s.lastRun || '—'}
                      {s.durationSec != null && (
                        <small className="hs-dur"> · {Math.floor(s.durationSec/60)}m {s.durationSec%60}s</small>
                      )}
                    </td>
                    <td className="tnum">
                      {s.goldRows != null ? fmtRows(s.goldRows) : '—'}
                      {s.goldRowsDelta != null && (
                        <small className="hs-delta">
                          {s.goldRowsDelta >= 0 ? '+' : ''}{fmtRows(s.goldRowsDelta)}
                        </small>
                      )}
                    </td>
                    <td className="tnum">{s.sourcePublished || '—'}</td>
                    <td className="num tnum">
                      {s.slaPct != null ? s.slaPct.toFixed(1).replace('.', ',') + '%' : '—'}
                    </td>
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

      {/* Run history */}
      <div className="card">
        <window.SectionHeader
          overline="Execuções recentes"
          title="Últimos 14 dias · todas as bancas"
          action={<span className="caption">{RUN_HISTORY.length} execuções diárias</span>}
        />
        <div className="hs-runs">
          {RUN_HISTORY.map((r, i) => {
            const meta = STATUS_LABEL[r.status];
            return (
              <div key={r.iso} className={'hs-run hs-run-' + r.status}
                   title={`${r.date} · ${meta.label}`}>
                <span className="hs-run-bar" style={{ background: meta.color }}></span>
                <span className="hs-run-date">{r.date}</span>
              </div>
            );
          })}
        </div>
        <div className="hs-runs-legend">
          {['ok', 'warn', 'fail'].map(s => (
            <span key={s} className="qa-legend-item">
              <span className="qa-dot" style={{ background: STATUS_LABEL[s].color }}></span>
              {STATUS_LABEL[s].label}
            </span>
          ))}
        </div>
      </div>

      {/* Sources freshness */}
      <div className="card">
        <window.SectionHeader
          overline="Frescor das fontes"
          title="Quando cada fonte publicou pela última vez"
          action={<span className="caption">{SOURCES.length} fontes oficiais</span>}
        />
        <div className="hs-sources">
          {SOURCES.filter(src => window.isBancoVisible(src.banco)).map(src => (
            <div key={src.name} className={'hs-source ' + src.status}>
              <div className="hs-source-l">
                <div className="hs-source-name">{src.name}</div>
                <div className="hs-source-meta">
                  <code>{src.url}</code> · cadência {src.cadence}
                </div>
              </div>
              <div className="hs-source-r">
                <span className="meta-label">Última publicação</span>
                <span className="meta-val tnum">{src.lastPublished}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Active alerts */}
      <div className="card">
        <window.SectionHeader
          overline="Alertas ativos"
          title={`${ALERTS.length} aviso(s) em aberto`}
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
                  <span className="hs-alert-since caption">desde {a.since}</span>
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
