// UnitFamily — surfaces the active unit families (mass/volume) for the current
// basket so the researcher never accidentally compares incompatible quantities.

function UnitFamilyBanner({ families }) {
  const F = window.UNIT_FAMILIES;
  // Nothing selected → no quantity families → no banner (zero means none).
  if (!families || families.length === 0) return null;
  const mixed = families.length > 1;

  if (!mixed) {
    const f = F[families[0]];
    return (
      <div className="ufam-banner single">
        <span className="ufam-dot" style={{ background: 'var(--embrapa-green)' }}></span>
        <span className="ufam-label">Família de unidades</span>
        <strong>{f.label} · {f.unit}</strong>
        <span className="ufam-note">
          Todos os produtos da cesta são medidos em {f.long}; quantidades são somáveis.
        </span>
      </div>
    );
  }

  return (
    <div className="ufam-banner mixed">
      <span className="ufam-dot warn"></span>
      <span className="ufam-label">Cesta mista</span>
      <strong>
        {families.map(id => `${F[id].label} (${F[id].unit})`).join(' + ')}
      </strong>
      <span className="ufam-note">
        Quantidades de famílias diferentes <u>não</u> são agregadas: cada métrica
        de quantidade aparece separada por família e unidade. Valor monetário
        permanece agregável e somável.
      </span>
    </div>
  );
}

// Tag for inline use inside chart titles / KPI labels.
// When `conv` is provided, the displayed unit reflects the active
// metric-conventions selection (kg/t for mass · L/m³ for volume).
function UnitFamilyTag({ family, conv }) {
  const f = window.UNIT_FAMILIES[family];
  const unit = !conv ? f.unit
    : ((conv.units && conv.units[family]) || f.unit);
  return <span className="ufam-tag" style={{ color: f.color || 'var(--fg-2)' }}>{f.label} · {unit}</span>;
}

Object.assign(window, { UnitFamilyBanner, UnitFamilyTag });
