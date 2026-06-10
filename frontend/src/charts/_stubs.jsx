// _stubs.jsx — TEMPORARY placeholders for chart components not yet ported to
// Plotly. Imported AFTER the real charts so it never overrides a built one
// (guarded by `if (!window[name]`). Each real port (Workflow fan-out, task #5)
// adds its own file + removes the name from PENDING here. When PENDING is empty,
// delete this file.

// All charts are ported (see ./*.jsx). This list is now empty — kept as a
// safety net + documentation. Delete this file in the final cleanup.
const PENDING = [];

function makeStub(name) {
  return function ChartStub() {
    return (
      <div
        className="chart-stub"
        style={{
          padding: '32px 16px',
          textAlign: 'center',
          color: 'var(--pres-gray-500)',
          border: '1px dashed var(--pres-gray-300)',
          borderRadius: 8,
        }}
      >
        <div className="caption">{name}</div>
        <div className="caption" style={{ opacity: 0.65 }}>
          porta Plotly em desenvolvimento
        </div>
      </div>
    );
  };
}

PENDING.forEach((name) => {
  if (!window[name]) window[name] = makeStub(name);
});
