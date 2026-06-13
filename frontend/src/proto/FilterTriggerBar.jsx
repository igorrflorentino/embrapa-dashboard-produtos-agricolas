// FilterTriggerBar — active-filter chip row that opens the FilterMenu modal.
// Replaces the legacy <FilterBar> dropdown row.

function FilterTriggerBar({ summary, onOpen, onExport, live = true, banco = null, view = null }) {
  // Soon banco → slim preview trigger (no real filters/data to export yet).
  if (!live) {
    return (
      <div className="fm-trigger-bar preview">
        <span className="fm-tb-label">Filtros</span>
        <span className="fm-tb-preview-note">
          Disponíveis quando <strong>{banco ? banco.short : 'o banco'}</strong> for liberado
          {banco?.maturityDate ? ` · previsão ${banco.maturityDate}` : ''}
        </span>
        <span className="fm-spacer"></span>
        <button className="fm-edit-btn" onClick={onOpen}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>
          </svg>
          Ver dimensões previstas
        </button>
      </div>
    );
  }

  const chips = [
    { k: 'Produtos',       v: summary.products   },
    { k: 'Período',        v: summary.period     },
    { k: 'Faixa de valor', v: summary.valueRange },
    { k: 'Geografia',      v: summary.geo        },
    { k: 'Qualidade',      v: summary.quality    },
  ];

  const canExport = !window.canExportView || window.canExportView(view);

  return (
    <div className="fm-trigger-bar">
      <span className="fm-tb-label">Filtros ativos</span>
      {chips.map((c, i) => (
        <span key={i} className="fm-chip-filter">
          <span className="fm-chip-k">{c.k}</span>{c.v}
        </span>
      ))}
      <span className="fm-spacer"></span>
      <button className="fm-edit-btn" onClick={onOpen}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 20h4l10-10-4-4L4 16zM14 6l4 4"/>
        </svg>
        Editar filtros
      </button>
      {canExport && (
      <button className="fm-export-btn" onClick={onExport} title="Baixar dados filtrados em CSV">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        Exportar CSV
      </button>
      )}
    </div>
  );
}

window.FilterTriggerBar = FilterTriggerBar;
