// KPI cards + small components

function KpiCard({ label, value, sub, delta, deltaPositive, accent }) {
  return (
    <div className="kpi-card">
      <div className="kpi-ov">{label}</div>
      <div className="kpi-val tnum" style={accent ? { color: accent } : null}>{value}</div>
      <div className="kpi-sub">
        {delta != null && (
          <span className={'kpi-delta ' + (deltaPositive ? 'up' : 'down')}>
            <window.Icon name={deltaPositive ? 'arrow_upward' : 'arrow_downward'} size={12}/>
            {delta}
          </span>
        )}
        <span>{sub}</span>
      </div>
    </div>
  );
}

function SectionHeader({ overline, title, action }) {
  return (
    <div className="section-head">
      <div>
        <div className="overline">{overline}</div>
        <h3 className="section-title">{title}</h3>
      </div>
      {action && <div className="section-action">{action}</div>}
    </div>
  );
}

function StatusChip({ flag }) {
  const map = {
    OK: 'ok', MISSING_VALUE: 'warn', MISSING_QUANTITY: 'info', INCOMPLETE: 'err',
  };
  return <span className={'chip ' + (map[flag] || 'muted')}>{flag}</span>;
}

Object.assign(window, { KpiCard, SectionHeader, StatusChip });
