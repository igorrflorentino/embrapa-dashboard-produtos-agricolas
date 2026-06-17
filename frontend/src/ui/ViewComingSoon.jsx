// ViewComingSoon — structured placeholder shown when the active banco
// (selected in the sidebar) is not yet wired to the backend.
// Renders the planned schema + scope so the researcher knows what to
// expect when the dataset goes live, instead of an empty dashboard.

function ViewComingSoon({ banco, view }) {
  if (!banco) return null;
  const bm = window.bancoMeta ? window.bancoMeta(banco.id) : banco;  // provenance via backend seam
  const captionTxt = banco.maturity === 'planejado'
    ? 'sem prazo definido'
    : ('previsão · ' + (bm.maturityDate || '—'));

  return (
    <div className="cs-stack">
      <div className="cs-hero">
        <div className="cs-hero-l">
          <div className="cs-eyebrow">
            <window.MaturityTag banco={banco} />
            <span className="caption">{captionTxt}</span>
          </div>
          <h2 className="cs-title">
            {banco.label}
          </h2>
          <p className="cs-sub">{banco.sub}</p>
        </div>
        <div className="cs-hero-r">
          <div className="cs-meta-row">
            <span className="meta-label">Domínio</span>
            <span className="meta-val">{bm.domain}</span>
          </div>
          <div className="cs-meta-row">
            <span className="meta-label">Granularidade</span>
            <span className="meta-val">{bm.scope}</span>
          </div>
          <div className="cs-meta-row">
            <span className="meta-label">Fonte</span>
            <span className="meta-val">{bm.source}</span>
          </div>
          <div className="cs-meta-row">
            <span className="meta-label">Tabela Gold</span>
            <span className="meta-val"><code>{window.bancoTable(banco.id)}</code></span>
          </div>
        </div>
      </div>

      <div className="grid-2 cs-grid">
        <div className="card">
          <window.SectionHeader
            overline="Esquema planejado"
            title="Colunas que o banco vai expor"
            action={<span className="caption">{banco.plannedScope?.length || 0} colunas</span>}
          />
          <div className="cs-cols">
            {(banco.plannedScope || []).map((c, i) => (
              <div key={i} className="cs-col-row">
                <code className="cs-col-name">{c.col}</code>
                <p className="cs-col-desc">{c.desc}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <window.SectionHeader
            overline="Cobertura prevista"
            title="O que esperar quando o banco for liberado"
          />
          <dl className="cs-cov">
            {bm.cobertura?.years && (
              <>
                <dt>Cobertura temporal</dt>
                <dd>{bm.cobertura.years}</dd>
              </>
            )}
            {bm.cobertura?.atualizacao && (
              <>
                <dt>Cadência de atualização</dt>
                <dd>{bm.cobertura.atualizacao}</dd>
              </>
            )}
            {bm.cobertura?.granularidade && (
              <>
                <dt>Granularidade da Gold</dt>
                <dd className="mono">{bm.cobertura.granularidade}</dd>
              </>
            )}
            {bm.cobertura?.restricoes && (
              <>
                <dt>Restrições</dt>
                <dd>{bm.cobertura.restricoes}</dd>
              </>
            )}
          </dl>

          <div className="cs-note">
            <window.Icon name="info" size={14} />
            <span>
              Esta perspectiva (<strong>{labelOf(view)}</strong>) será habilitada
              automaticamente assim que o backend expor a tabela <code>{window.bancoTable(banco.id)}</code>.
              Os componentes de visualização já existem e serão reaproveitados.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Resolve the perspective label from the single source of truth (views.js),
// so every registered view — not just a hardcoded subset — shows its proper
// name when a soon banco renders this placeholder.
function labelOf(view) {
  return (window.viewLabel && window.viewLabel(view)) || view;
}

window.ViewComingSoon = ViewComingSoon;
