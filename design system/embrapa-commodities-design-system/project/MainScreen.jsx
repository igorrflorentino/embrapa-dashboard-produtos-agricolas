// MainScreen — the "tela principal" of the commodities dashboard.
// Anchors: institutional brand chrome (AppShell), filter bar, KPI strip with
// sparklines, year-over-year highlights, time-series + product mix, geo
// ranking + recent rows, and the monetary-convention legend.

function Sparkline({ data, color = 'var(--viz-1)', valueKey = 'v', width = 120, height = 32 }) {
  const ys = data.map(d => d[valueKey]);
  const min = Math.min(...ys), max = Math.max(...ys);
  const span = max - min || 1;
  const x = i => (i / (data.length - 1)) * (width - 2) + 1;
  const y = v => height - 2 - ((v - min) / span) * (height - 4);
  const pts = data.map((d, i) => `${x(i)},${y(d[valueKey])}`).join(' ');
  const area = `1,${height - 1} ${pts} ${width - 1},${height - 1}`;
  const last = data[data.length - 1];
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} style={{ display: 'block' }}>
      <polygon points={area} fill={color} opacity="0.10" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={x(data.length - 1)} cy={y(last[valueKey])} r="2.2" fill={color} />
    </svg>
  );
}

function KpiCardSpark({ label, value, sub, delta, deltaPositive, spark, sparkColor, sparkKey = 'v' }) {
  return (
    <div className="kpi-card spark">
      <div className="kpi-top">
        <div className="kpi-ov">{label}</div>
        {spark && <Sparkline data={spark} color={sparkColor} valueKey={sparkKey} />}
      </div>
      <div className="kpi-val tnum">{value}</div>
      <div className="kpi-sub">
        {delta != null && (
          <span className={'kpi-delta ' + (deltaPositive ? 'up' : 'down')}>
            <window.Icon name={deltaPositive ? 'arrow_upward' : 'arrow_downward'} size={12} />
            {delta}
          </span>
        )}
        <span>{sub}</span>
      </div>
    </div>
  );
}

function HighlightCard({ overline, title, body, badge, badgeTone }) {
  return (
    <div className="highlight">
      <div className="highlight-head">
        <span className="overline">{overline}</span>
        {badge && <span className={'chip ' + (badgeTone || 'info')}>{badge}</span>}
      </div>
      <div className="highlight-title">{title}</div>
      <div className="highlight-body">{body}</div>
    </div>
  );
}

function MainScreen({ filters }) {
  const ts = window.OVERVIEW_TS;
  const last = ts[ts.length - 1], prev = ts[ts.length - 2];
  const deltaV = ((last.v - prev.v) / prev.v) * 100;
  const deltaQ = ((last.q - prev.q) / prev.q) * 100;
  const spark = ts.slice(-12);

  return (
    <div className="screen">
      {/* Hero / page header */}
      <div className="page-hero">
        <div>
          <div className="overline">Dashboard de Inteligência de Mercado · Commodities</div>
          <h1 className="page-title">Visão geral · Produção extrativa vegetal</h1>
          <p className="page-sub">
            Pipeline Bronze → Silver → Gold sobre IBGE PEVS, com correção
            monetária por IPCA, IGP-M e câmbio do ano. Cobertura: <strong>1995–2023</strong>,
            26 das 27 unidades federativas.
          </p>
        </div>
        <div className="hero-meta">
          <div className="meta-row">
            <span className="meta-label">Convenção ativa</span>
            <span className="meta-val">IPCA · BRL</span>
          </div>
          <div className="meta-row">
            <span className="meta-label">Última atualização</span>
            <span className="meta-val tnum">28 jun 2024 · 04:30 BRT</span>
          </div>
          <div className="meta-row">
            <span className="meta-label">Próxima execução</span>
            <span className="meta-val tnum">29 jun 2024 · 04:30 BRT</span>
          </div>
          <div className="meta-actions">
            <button className="btn-secondary">
              <window.Icon name="refresh" size={14} /> Atualizar
            </button>
            <button className="btn-primary">
              <window.Icon name="download" size={14} /> Exportar
            </button>
          </div>
        </div>
      </div>

      {/* KPI strip with sparklines */}
      <div className="kpi-row">
        <KpiCardSpark
          label="Valor real (IPCA) · BRL"
          value={'R$ ' + last.v.toFixed(2).replace('.', ',') + ' bi'}
          delta={(deltaV >= 0 ? '+' : '') + deltaV.toFixed(1).replace('.', ',') + '%'}
          deltaPositive={deltaV >= 0}
          sub="vs. 2022"
          spark={spark}
          sparkKey="v"
          sparkColor="var(--viz-1)"
        />
        <KpiCardSpark
          label="Quantidade total"
          value={last.q.toLocaleString('pt-BR') + ' kt'}
          delta={(deltaQ >= 0 ? '+' : '') + deltaQ.toFixed(1).replace('.', ',') + '%'}
          deltaPositive={deltaQ >= 0}
          sub="vs. 2022"
          spark={spark}
          sparkKey="q"
          sparkColor="var(--viz-2)"
        />
        <KpiCardSpark
          label="Cobertura geográfica"
          value="26 / 27"
          sub="UFs com dados · 2023"
          spark={[
            { v: 22 }, { v: 23 }, { v: 23 }, { v: 24 },
            { v: 25 }, { v: 25 }, { v: 26 }, { v: 26 },
            { v: 26 }, { v: 26 }, { v: 26 }, { v: 26 },
          ]}
          sparkColor="var(--viz-4)"
        />
        <KpiCardSpark
          label="Qualidade dos dados"
          value="94,2%"
          delta="+1,8 pp"
          deltaPositive={true}
          sub="linhas com flag OK"
          spark={[
            { v: 86 }, { v: 87 }, { v: 88 }, { v: 88 },
            { v: 89 }, { v: 90 }, { v: 91 }, { v: 92 },
            { v: 92 }, { v: 93 }, { v: 93 }, { v: 94.2 },
          ]}
          sparkColor="var(--embrapa-green)"
        />
      </div>

      {/* Highlights / insights row */}
      <div className="highlights">
        <window.SectionHeader
          overline="Destaques · 2023"
          title="O que mudou no último ciclo"
          action={<a className="link" href="#">Ver todas as análises →</a>}
        />
        <div className="highlights-grid">
          <HighlightCard
            overline="Líder regional"
            badge="Norte"
            badgeTone="info"
            title="Pará concentra 23% do valor real"
            body="Castanha-do-pará e madeira em tora respondem por R$ 982 mi — alta de 6,1% sobre 2022 em IPCA chain."
          />
          <HighlightCard
            overline="Atenção"
            badge="−1,4%"
            badgeTone="err"
            title="Castanha-do-pará recua em volume"
            body="Queda concentrada no Acre (−9% t) e Amazonas (−3% t); valor real sobe pela alta de preço médio."
          />
          <HighlightCard
            overline="Qualidade"
            badge="+1,8 pp"
            badgeTone="ok"
            title="Cobertura de flags OK avança"
            body="Roraima e Tocantins reduzem MISSING_VALUE após ajustes no SIDRA — 1.030 linhas reconciliadas."
          />
        </div>
      </div>

      {/* Time series + product mix */}
      <div className="grid-2">
        <div className="card">
          <window.SectionHeader
            overline="Série histórica · IPCA · BRL"
            title="Valor real total — 1995 a 2023"
            action={
              <div className="seg">
                <button className="seg-opt on">Valor</button>
                <button className="seg-opt">Quantidade</button>
              </div>
            }
          />
          <window.LineChart data={ts} label="R$ bi" valueKey="v" color="var(--viz-1)" height={240} />
          <div className="chart-foot">
            <span className="caption">
              Pico em <strong>2022</strong> (R$ 4,38 bi) · base 1995 normalizada via cadeia IPCA mensal.
            </span>
          </div>
        </div>

        <div className="card">
          <window.SectionHeader
            overline="Composição · 2023"
            title="Participação por produto"
            action={<a className="link" href="#">Detalhar →</a>}
          />
          <window.Donut data={window.TOP_PRODUCTS} size={180} valueKey="share" />
          <div className="chart-foot">
            <span className="caption">Madeira + lenha somam <strong>52%</strong> do valor real total.</span>
          </div>
        </div>
      </div>

      {/* UF ranking + recent rows */}
      <div className="grid-2">
        <div className="card">
          <window.SectionHeader
            overline="Top 8 · 2023"
            title="Maiores estados produtores"
            action={<span className="caption">Valor real (IPCA), R$ mi</span>}
          />
          <window.BarChart data={window.TOP_UFS} valueKey="value" color="var(--viz-2)" height={280} />
        </div>

        <div className="card">
          <window.SectionHeader
            overline="Tabela bruta · gold_commodity_matrix"
            title="Amostras recentes"
            action={<a className="link" href="#">Abrir tabela →</a>}
          />
          <window.DataTable rows={window.SAMPLE_ROWS.slice(0, 6)} />
        </div>
      </div>

      {/* Monetary convention legend */}
      <div className="card subtle">
        <window.SectionHeader
          overline="Convenções monetárias"
          title="Como ler os valores no Gold"
          action={<a className="link" href="#">Ver glossário completo →</a>}
        />
        <div className="conv-grid">
          <div className="conv">
            <div className="conv-tag" style={{ background: 'rgba(29,77,126,0.10)', color: 'var(--pres-yale-blue)' }}>
              val_real_ipca_*
            </div>
            <p>
              Valor projetado para hoje pela cadeia IPCA — usar para <strong>comparações entre anos</strong>.
              Padrão deste dashboard.
            </p>
          </div>
          <div className="conv">
            <div className="conv-tag" style={{ background: 'rgba(0,111,53,0.10)', color: 'var(--embrapa-green-darker)' }}>
              val_real_igpm_*
            </div>
            <p>
              Idem, usando IGP-M como índice. Alternativa institucional ao IPCA;
              maior aderência a séries de commodities.
            </p>
          </div>
          <div className="conv">
            <div className="conv-tag" style={{ background: 'rgba(102,102,102,0.10)', color: 'var(--fg-2)' }}>
              val_yearfx_*
            </div>
            <p>
              Valor nominal (R$ corrente) convertido pelo FX médio do ano.
              <strong> Auditoria histórica apenas</strong> — não compare entre anos.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Sparkline, KpiCardSpark, HighlightCard, MainScreen });
