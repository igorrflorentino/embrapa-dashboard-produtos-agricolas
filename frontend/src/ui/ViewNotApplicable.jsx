// ViewNotApplicable — shown when a perspective is selected that doesn't
// apply to the active banco (the banco lacks the data capability the view
// requires). Distinct from ViewComingSoon (whole banco awaiting ingest)
// and ViewPerspectiveSoon (view applies but not yet built).
//
// Acts as the inverse indicator: tells the researcher WHICH bancos do
// support this perspective, and lets them switch directly.

function ViewNotApplicable({ viewMeta, banco, missing, supporters, onPickBanco }) {
  if (!viewMeta) return null;

  return (
    <div className="cs-stack">
      <div className="card na-hero">
        <div className="na-hero-l">
          <div className="cs-eyebrow">
            <span className="na-badge">Não se aplica</span>
            {viewMeta.group && <span className="caption">{viewMeta.group.label} · {viewMeta.group.hint}</span>}
          </div>
          <h2 className="cs-title">{viewMeta.label}</h2>
          <p className="cs-sub">
            Esta perspectiva não está disponível para <strong>{banco?.short || 'este banco'}</strong>,
            que não possui {missing && missing.length
              ? <strong>{window.missingCapsLabel(missing)}</strong>
              : 'a dimensão necessária'}.
          </p>
          <p className="cs-sub na-desc">{viewMeta.desc}</p>
        </div>
      </div>

      {supporters && supporters.length > 0 ? (
        <div className="card">
          <window.SectionHeader
            overline="Onde usar esta perspectiva"
            title="Bancos compatíveis"
            action={<span className="caption">{supporters.length} de {(window.visibleBancos ? window.visibleBancos() : (window.BANCOS || [])).length} bancos</span>}
          />
          <div className="na-bancos">
            {supporters.map(b => (
              <button
                key={b.id}
                className={'na-banco ' + (b.status === 'live' ? 'live' : 'soon')}
                onClick={() => onPickBanco && onPickBanco(b.id)}
                title={b.status === 'live' ? `Trocar para ${b.short}` : `${b.short} · ${window.bancoAvailability(b).toLowerCase()}`}>
                <div className="na-banco-head">
                  <span className="na-banco-short">{b.short}</span>
                  <span className={'na-banco-tag ' + b.status}>
                    {window.bancoAvailability(b)}
                  </span>
                </div>
                <div className="na-banco-domain">{b.domain}</div>
                <p className="na-banco-sub">{b.sub}</p>
                {b.status === 'live' && (
                  <span className="na-banco-cta">Trocar para este banco →</span>
                )}
              </button>
            ))}
          </div>
          <div className="cs-note">
            <window.Icon name="info" size={14} />
            <span>
              A seleção de banco fica na barra lateral. Trocar de banco mantém
              os filtros compatíveis e redefine apenas os que não existem na nova fonte.
            </span>
          </div>
        </div>
      ) : (
        <div className="card subtle">
          <p className="caption" style={{ padding: '16px 4px' }}>
            Nenhum banco disponível oferece esta perspectiva no momento.
          </p>
        </div>
      )}
    </div>
  );
}

window.ViewNotApplicable = ViewNotApplicable;
