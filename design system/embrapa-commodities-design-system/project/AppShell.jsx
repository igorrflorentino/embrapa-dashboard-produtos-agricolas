// AppShell — institutional chrome: header band, sidebar, breadcrumb, footer tríade.

function AppShell({ children, route, setRoute }) {
  const nav = [
    { id: 'overview', label: 'Visão geral', icon: 'dashboard' },
    { id: 'product',  label: 'Produto',     icon: 'eco' },
    { id: 'geo',      label: 'Geografia',   icon: 'map' },
    { id: 'quality',  label: 'Qualidade',   icon: 'fact_check' },
  ];

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-italic" style={{ fontSize: 22, color: '#fff' }}>Embrapa</span>
        </div>
        <div className="sep"></div>
        <div className="product-name">Inteligência de Mercado — Commodities</div>

        <nav className="topnav">
          {nav.map(n => (
            <a key={n.id}
               className={'topnav-item ' + (route === n.id ? 'active' : '')}
               onClick={() => setRoute(n.id)}>
              {n.label}
            </a>
          ))}
        </nav>

        <div className="util">
          <span className="util-chip"><window.Icon name="schedule" size={14}/>04:30 BRT</span>
          <span className="util-chip">BRL · IPCA</span>
          <button className="icon-btn" title="Notificações"><window.Icon name="notifications" size={18}/></button>
          <div className="avatar">IF</div>
        </div>
      </header>

      <div className="body">
        <aside className="sidebar">
          <div className="side-section">Dashboards</div>
          {nav.map(n => (
            <div key={n.id}
                 className={'side-item ' + (route === n.id ? 'active' : '')}
                 onClick={() => setRoute(n.id)}>
              <window.Icon name={n.icon}/>
              {n.label}
            </div>
          ))}
          <div className="side-section">Dados</div>
          <div className="side-item"><window.Icon name="database"/>Tabela bruta</div>
          <div className="side-item"><window.Icon name="download"/>Exportar CSV</div>
          <div className="side-item"><window.Icon name="api"/>Conectar API</div>

          <div className="side-section">Sobre</div>
          <div className="side-item"><window.Icon name="help"/>Glossário</div>
          <div className="side-item"><window.Icon name="info"/>Sobre os dados</div>

          <div className="side-foot">
            <div className="pill-emp">Acesso restrito · Empregados</div>
          </div>
        </aside>

        <main className="content">
          {children}
        </main>
      </div>

      <footer className="footer">
        <img src="assets/triade-horizontal-black.png" alt="Embrapa · Ministério da Agricultura e Pecuária · Governo do Brasil" className="triade"/>
        <div className="foot-meta">
          <div>© Empresa Brasileira de Pesquisa Agropecuária</div>
          <div className="caption">Ministério da Agricultura e Pecuária · Pipeline Bronze → Silver → Gold · BigQuery + Looker Studio</div>
          <div className="caption"><a href="#">www.embrapa.br</a> &nbsp;·&nbsp; <a href="#">Serviço de Atendimento ao Cidadão (SAC)</a></div>
        </div>
      </footer>
    </div>
  );
}

window.AppShell = AppShell;
