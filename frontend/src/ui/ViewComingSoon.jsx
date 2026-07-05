// ViewComingSoon — a GENERIC, minimal placeholder shown when the active banco
// (selected in the sidebar) is not yet wired to the backend (maturity 'planejado'
// / any non-live stage). Deliberately says little: just that the banco will be
// implemented later — no per-banco schema/coverage detail, so the SAME window
// serves any future planned banco. Rendered identically for every perspective
// (MainScreen short-circuits on the banco being 'soon' before any view logic).

function ViewComingSoon({ banco }) {
  if (!banco) return null;
  return (
    <div className="card cs-simple">
      <window.Icon name="schedule" size={32} />
      <h2 className="cs-simple-title">Em breve</h2>
      <p className="cs-simple-msg">
        Este banco de dados ainda não foi implementado. Quando estiver disponível, todas as
        perspectivas serão habilitadas automaticamente por aqui.
      </p>
    </div>
  );
}

window.ViewComingSoon = ViewComingSoon;
