// Overview screen — the main dashboard view.

function Overview({ filters }) {
  const ts = window.OVERVIEW_TS;
  const last = ts[ts.length - 1], prev = ts[ts.length - 2];
  const deltaV = ((last.v - prev.v) / prev.v * 100);
  const deltaQ = ((last.q - prev.q) / prev.q * 100);

  return (
    <div className="screen">
      <window.SectionHeader
        overline="2023 · cobertura nacional"
        title="Visão geral · Produção extrativa vegetal"
        action={<span className="overline" style={{color:'var(--fg-3)'}}>Última atualização: 28 jun 2024, 04:30 BRT</span>}
      />

      <div className="kpi-row">
        <window.KpiCard
          label="Valor real (IPCA) · BRL"
          value={'R$ ' + last.v.toFixed(2).replace('.',',') + ' bi'}
          delta={(deltaV >= 0 ? '+' : '') + deltaV.toFixed(1).replace('.',',') + '%'}
          deltaPositive={deltaV >= 0}
          sub="vs. 2022"
        />
        <window.KpiCard
          label="Quantidade total"
          value={(last.q).toLocaleString('pt-BR') + ' kt'}
          delta={(deltaQ >= 0 ? '+' : '') + deltaQ.toFixed(1).replace('.',',') + '%'}
          deltaPositive={deltaQ >= 0}
          sub="vs. 2022"
        />
        <window.KpiCard
          label="Cobertura geográfica"
          value="26 / 27"
          sub="UFs com dados · 2023"
        />
        <window.KpiCard
          label="Qualidade dos dados"
          value="94,2%"
          delta="+1,8 pp"
          deltaPositive={true}
          sub="linhas com flag OK"
        />
      </div>

      <div className="grid-2">
        <div className="card">
          <window.SectionHeader
            overline="Série histórica · IPCA · BRL"
            title="Valor real total — 1995 a 2023"
            action={<a className="link" href="#">Detalhar →</a>}
          />
          <window.LineChart data={ts} label="R$ bi" valueKey="v" color="var(--viz-1)" height={220} />
        </div>

        <div className="card">
          <window.SectionHeader
            overline="Composição · 2023"
            title="Participação por produto"
          />
          <window.Donut data={window.TOP_PRODUCTS} size={170} valueKey="share" />
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <window.SectionHeader
            overline="Top 8 · 2023"
            title="Maiores estados produtores"
            action={<span className="caption">Valor real (IPCA), R$ mi</span>}
          />
          <window.BarChart data={window.TOP_UFS} valueKey="value" color="var(--viz-2)" height={260} />
        </div>

        <div className="card">
          <window.SectionHeader
            overline="Tabela bruta · gold_commodity_matrix"
            title="Amostras recentes"
            action={<a className="link" href="#">Abrir tabela →</a>}
          />
          <window.DataTable rows={window.SAMPLE_ROWS.slice(0, 5)} />
        </div>
      </div>

      <div className="card subtle">
        <window.SectionHeader
          overline="Convenções monetárias"
          title="Como ler os valores"
        />
        <div className="conv-grid">
          <div className="conv">
            <div className="conv-tag" style={{background:'rgba(29,77,126,0.10)', color:'var(--pres-yale-blue)'}}>val_real_ipca_*</div>
            <p>Valor projetado para hoje pela cadeia IPCA — usar para <strong>comparações entre anos</strong>.</p>
          </div>
          <div className="conv">
            <div className="conv-tag" style={{background:'rgba(0,111,53,0.10)', color:'var(--embrapa-green-darker)'}}>val_real_igpm_*</div>
            <p>Idem, usando IGP-M como índice. Alternativa institucional ao IPCA.</p>
          </div>
          <div className="conv">
            <div className="conv-tag" style={{background:'rgba(102,102,102,0.10)', color:'var(--fg-2)'}}>val_yearfx_*</div>
            <p>Valor nominal (R$ atual) convertido pelo FX médio do ano. <strong>Auditoria histórica apenas.</strong></p>
          </div>
        </div>
      </div>
    </div>
  );
}

window.Overview = Overview;
