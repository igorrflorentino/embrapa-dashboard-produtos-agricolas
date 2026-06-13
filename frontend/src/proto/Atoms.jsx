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

// NotApplicableNote — an inline, honest "este filtro não se aplica" notice that a
// view renders ABOVE its (still-real) charts when the active filter summary carries
// a dimension this view's grain cannot honour. The data producers surface that as
// a `notApplicable` object keyed by dimension (e.g. { states: '…', basket: '…' }):
// the param is withheld at the data layer (no silent drop), and this atom makes the
// refusal visible to the researcher instead of leaving an unchanged chart unexplained.
// Renders nothing when there is no applicable note (the common case), so a view can
// place it unconditionally above its charts.
function NotApplicableNote({ note }) {
  const messages = note ? Object.values(note).filter(Boolean) : [];
  if (!messages.length) return null;
  return (
    <div className="card subtle na-note">
      {messages.map((msg, i) => (
        <p key={i} className="cs-note" style={{ margin: 0 }}>
          <window.Icon name="info" size={14} />
          <span>{msg}</span>
        </p>
      ))}
    </div>
  );
}

Object.assign(window, { SectionHeader, NotApplicableNote });
