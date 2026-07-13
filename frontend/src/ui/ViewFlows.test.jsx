// ViewFlows.test.jsx — the flow KPI magnitude formatter (M9). ViewFlows.fmt used
// to hardcode a ÷1000 + " mi"/" bi" heuristic that ASSUMED the value already came
// in millions; against a real API magnitude (raw US$) that mislabels everything.
// The fix drives magnitude + pt-BR suffix off the shared window.autoScaleNum
// helper keyed on the REAL value. We render ViewFlows with stubbed window.*
// dependencies and read the formatted KPI text.

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';

// The ui-side shared magnitude helper the migrated views use (same words as
// the charts' ptBrMagnitude). The real implementation under test.
function autoScaleNum(v) {
  const a = Math.abs(v);
  if (a >= 1e9) return { factor: 1e9, suffix: 'bi' };
  if (a >= 1e6) return { factor: 1e6, suffix: 'mi' };
  if (a >= 1e3) return { factor: 1e3, suffix: 'mil' };
  return { factor: 1, suffix: '' };
}

// Minimal stand-ins for the window.* components ViewFlows composes. KpiCardSpark
// renders its `value` (the fmt output) into the DOM so we can assert on it.
function stubProtoGlobals(flow) {
  window.autoScaleNum = autoScaleNum;
  window.bancoById = () => ({ scope: 'País', domain: 'Comércio' });
  window.flowData = () => flow;
  window.NotApplicableNote = () => null;
  window.LoadErrorNote = ({ error }) => (error ? <div className="load-err">{error}</div> : null);
  window.SankeyChart = () => null;
  window.SectionHeader = () => null;
  window.KpiCardSpark = ({ label, value, sub }) => (
    <div className="kpi" data-label={label}>
      <span className="kpi-value">{value}</span>
      <span className="kpi-sub">{sub}</span>
    </div>
  );
}

let ViewFlows;

beforeEach(async () => {
  await import('./ViewFlows.jsx'); // registers window.ViewFlows
  ViewFlows = window.ViewFlows;
});

afterEach(() => cleanup());

describe('ViewFlows fmt — magnitude from the real value, not a ÷1000 heuristic (M9)', () => {
  it('labels a billions-scale US$ flow as "bi" (not the old "mi")', () => {
    // Two origins → one dest; total = 3.4e9 US$ (a realistic raw API magnitude).
    stubProtoGlobals({
      unit: 'US$',
      originLabel: 'UF de origem',
      destLabel: 'País de destino',
      nodes: [
        { id: 'o0', label: 'PA', side: 'origin', value: 2.4e9 },
        { id: 'o1', label: 'SP', side: 'origin', value: 1e9 },
        { id: 'd0', label: 'China', side: 'dest', value: 3.4e9 },
      ],
      links: [
        { source: 'o0', target: 'd0', value: 2.4e9 },
        { source: 'o1', target: 'd0', value: 1e9 },
      ],
    });
    const { container } = render(<ViewFlows summary={{}} conventions={{}} database="mdic_comex" />);
    const total = container.querySelector('.kpi[data-label="Fluxo total"] .kpi-value');
    // 3.4e9 → "US$ 3,4 bi" (pt-BR), NOT the old "US$ 3400000.0 bi" or "… mi".
    expect(total.textContent).toBe('US$ 3,4 bi');
    expect(total.textContent).toContain('bi');
    expect(total.textContent).not.toMatch(/mi$/);
  });

  it('labels a millions-scale flow as "mi" driven by the real value', () => {
    stubProtoGlobals({
      unit: 'US$',
      originLabel: 'UF',
      destLabel: 'País',
      nodes: [{ id: 'o0', label: 'BA', side: 'origin', value: 5e6 },
        { id: 'd0', label: 'EUA', side: 'dest', value: 5e6 }],
      links: [{ source: 'o0', target: 'd0', value: 5e6 }],
    });
    const { container } = render(<ViewFlows summary={{}} conventions={{}} database="mdic_comex" />);
    const total = container.querySelector('.kpi[data-label="Fluxo total"] .kpi-value');
    expect(total.textContent).toBe('US$ 5 mi');
  });

  it('a small value carries no magnitude suffix (no fabricated " mi")', () => {
    stubProtoGlobals({
      unit: 'US$',
      originLabel: 'UF',
      destLabel: 'País',
      nodes: [{ id: 'o0', label: 'AC', side: 'origin', value: 42 },
        { id: 'd0', label: 'Peru', side: 'dest', value: 42 }],
      links: [{ source: 'o0', target: 'd0', value: 42 }],
    });
    const { container } = render(<ViewFlows summary={{}} conventions={{}} database="mdic_comex" />);
    const total = container.querySelector('.kpi[data-label="Fluxo total"] .kpi-value');
    expect(total.textContent).toBe('US$ 42'); // no " mi" / " bi" tacked on
  });
});
