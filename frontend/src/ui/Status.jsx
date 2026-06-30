// Status.jsx — shared indicators for the TWO banco status axes:
//   • maturity (dataset lifecycle) — build-time readiness, from the registry
//     window.MATURITY (bancos.js). Frontend only displays it.
//   • usage status — ativo/inativo, derived from the active selection.
// All components read the registry so adding/retuning a stage = one edit there.

// ── Maturity tag: colored dot + label. ─────────────────────────────
function MaturityTag({ banco, status, size, withIcon }) {
  const m = status ? (window.MATURITY[status] || window.MATURITY.planejado)
                    : window.maturityMeta(banco);
  return (
    <span className={'mat-tag mat-' + m.id + (size === 'sm' ? ' sm' : '')}
          title={m.desc}>
      <span className="mat-tag-dot" style={{ background: m.color }}></span>
      {m.label}
    </span>
  );
}

// ── Usage dot: filled = ativo (feeds the current view), hollow = inativo. ─
function UsageDot({ active }) {
  return (
    <span className={'use-dot ' + (active ? 'on' : 'off')}
          title={active ? 'Ativo · fonte dos dados em tela' : 'Inativo'}
          aria-label={active ? 'Ativo' : 'Inativo'}></span>
  );
}

// ── Usage tag: explicit ativo/inativo pill (hero / about). ──────────────
// Shares the maturity-tag chip styling (.mat-tag: border + flat dot + neutral
// uppercase label) so the TWO status axes — maturity and usage — read as one
// visual family in the hero; only the dot colour + faint tint differ. The
// caller passes size="sm" to match the small maturity tag beside it.
function UsageTag({ active, size }) {
  return (
    <span className={'mat-tag ' + (active ? 'use-on' : 'use-off') + (size === 'sm' ? ' sm' : '')}
          title={active ? 'Ativo · fonte dos dados em tela' : 'Inativo'}>
      <span className="mat-tag-dot" style={{ background: active ? 'var(--ok)' : 'var(--pres-gray-400)' }}></span>
      {active ? 'Ativo' : 'Inativo'}
    </span>
  );
}

// ── Caveat banner shown atop data views for beta / manutencao /
//    descontinuado (the caveat:true stages). ─────────────────────────
// The caveat text is the registry's MATURITY[stage].desc — the SAME string the
// "Sobre o dashboard" maturity legend shows (MaturityLegend below) — so the beta
// (and every stage's) description reads identically in both places (audit HERO-2).
// An operator-set banco.maturityNote still overrides it per banco.
function MaturityBanner({ banco }) {
  if (!banco) return null;
  const m = window.maturityMeta(banco);
  if (!m.caveat) return null;
  return (
    <div className={'mat-banner mat-banner-' + m.id} style={{ '--st-color': m.color }} role="status">
      <span className="mat-banner-dot" style={{ background: m.color }}></span>
      <div className="mat-banner-body">
        <strong>{m.label}.</strong>{' '}
        <span>{banco.maturityNote || m.desc}</span>
        {banco.maturityDate ? <span className="mat-banner-date tnum"> · {banco.maturityDate}</span> : null}
      </div>
    </div>
  );
}

// ── Legend documenting every maturity stage (window.MATURITY). ─────────
function MaturityLegend({ compact }) {
  const rows = Object.values(window.MATURITY).sort((a, b) => a.order - b.order);
  return (
    <div className={'mat-legend' + (compact ? ' compact' : '')}>
      {rows.map(m => (
        <div key={m.id} className="mat-legend-row">
          <span className={'mat-tag mat-' + m.id}>
            <span className="mat-tag-dot" style={{ background: m.color }}></span>
            {m.label}
          </span>
          <span className="mat-legend-desc">{m.desc}</span>
        </div>
      ))}
    </div>
  );
}

Object.assign(window, { MaturityTag, UsageDot, UsageTag, MaturityBanner, MaturityLegend });
