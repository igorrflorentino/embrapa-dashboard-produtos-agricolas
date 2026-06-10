// SectionHeader + small shared components

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

Object.assign(window, { SectionHeader });
