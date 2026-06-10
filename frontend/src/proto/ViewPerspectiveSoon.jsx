// ViewPerspectiveSoon — placeholder for analytical perspectives that
// are planned but not yet built (the banco IS live, but this view isn't).
// Distinct from ViewComingSoon, which covers a whole banco awaiting ingest.

function ViewPerspectiveSoon({ viewMeta }) {
  if (!viewMeta) return null;
  const group = viewMeta.group;

  return (
    <div className="cs-stack">
      <div className="card ps-hero">
        <div className="ps-hero-l">
          <div className="cs-eyebrow">
            <span className="cs-badge">Em breve</span>
            {group && <span className="caption">{group.label} · {group.hint}</span>}
          </div>
          <h2 className="cs-title">{viewMeta.label}</h2>
          <p className="cs-sub">{viewMeta.desc}</p>
        </div>
      </div>

      <div className="card">
        <window.SectionHeader
          overline="O que esta perspectiva vai trazer"
          title="Elementos planejados"
          action={<span className="caption">{viewMeta.planned?.length || 0} blocos</span>}
        />
        <div className="ps-planned">
          {(viewMeta.planned || []).map((p, i) => (
            <div key={i} className="ps-planned-row">
              <span className="ps-planned-num tnum">{String(i + 1).padStart(2, '0')}</span>
              <span className="ps-planned-text">{p}</span>
            </div>
          ))}
        </div>
        <div className="cs-note">
          <window.Icon name="info" size={14} />
          <span>
            Esta perspectiva já está prevista na arquitetura. Os filtros e convenções
            métricas selecionados serão aplicados automaticamente assim que ela for
            publicada — sem necessidade de reconfigurar a análise.
          </span>
        </div>
      </div>
    </div>
  );
}

window.ViewPerspectiveSoon = ViewPerspectiveSoon;
