// _base.jsx — shared Plotly theme + lifecycle wrapper for every chart.
//
// Charts build their traces, then render <Plot traces=… layout=… />. The Plot
// component owns the imperative Plotly lifecycle (react/resize/purge) so each
// chart stays declarative. Theme colors come from the design-system CSS vars
// (resolved at runtime via getComputedStyle) so charts match the rest of the UI
// and follow any theme change. Researchers get zoom/pan/hover for free (Plotly).

import { useRef, useEffect, useState } from 'react';
import Plotly from './plotlyBundle';

const root = () => document.documentElement;

/** Resolve a CSS custom property to its computed value (with a fallback). */
export function cssVar(name, fallback = '') {
  if (typeof window === 'undefined') return fallback;
  const v = getComputedStyle(root()).getPropertyValue(name);
  return (v && v.trim()) || fallback;
}

/** Resolve a `var(--x)` reference (the registries store colors as `var(--viz-1)`)
 *  to a concrete color Plotly can use. Passes through literal colors. */
export function resolveColor(c, fallback = cssVar('--viz-1', '#1D4D7E')) {
  if (!c) return fallback;
  const m = /var\(\s*(--[\w-]+)\s*\)/.exec(c);
  return m ? cssVar(m[1], fallback) : c;
}

/** The categorical viz palette (--viz-1…--viz-8), resolved. */
export function vizPalette() {
  return Array.from({ length: 8 }, (_, i) => cssVar(`--viz-${i + 1}`, '#1D4D7E'));
}

/** Add an alpha channel to a color (for area fills). Handles #RGB/#RRGGBB and
 *  passes through rgb()/named colors by wrapping unsupported inputs as-is. */
export function withAlpha(color, alpha = 0.12) {
  const c = resolveColor(color);
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(c);
  if (hex) {
    let h = hex[1];
    if (h.length === 3) h = h.split('').map((d) => d + d).join('');
    const n = parseInt(h, 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
  }
  const rgb = /^rgb\((.+)\)$/i.exec(c);
  if (rgb) return `rgba(${rgb[1]}, ${alpha})`;
  return c;
}

/** Base layout shared by all charts — transparent bg, DS fonts/colors, light
 *  grid, tight margins. Pass overrides (axis titles, legend, height handled by
 *  the wrapper div). */
export function baseLayout(over = {}) {
  const ink = cssVar('--pres-gray-700', '#3D3D3D');
  const grid = cssVar('--pres-gray-200', '#ECECEC');
  const family = cssVar('--font-body', "system-ui, -apple-system, sans-serif");
  const axis = {
    gridcolor: grid,
    linecolor: grid,
    zeroline: false,
    tickfont: { size: 11 },
    automargin: true,
  };
  return {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family, size: 12, color: ink },
    margin: { l: 56, r: 16, t: 8, b: 36 },
    hovermode: 'x unified',
    showlegend: false,
    colorway: vizPalette(),
    ...over,
    xaxis: { ...axis, ...(over.xaxis || {}) },
    yaxis: { ...axis, ...(over.yaxis || {}) },
  };
}

/** Interaction defaults — pt-BR number locale, slim modebar on hover, pan/zoom
 *  enabled (the whole point of moving to Plotly). */
export const baseConfig = {
  displaylogo: false,
  responsive: true,
  locale: 'pt-BR',
  displayModeBar: 'hover',
  modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'toggleSpikelines'],
};

/** Declarative Plotly host: draws on every render (Plotly.react diffs cheaply),
 *  resizes with its container, purges on unmount. */
export function Plot({ traces, layout, config, height = 240, style, className, onClick }) {
  const ref = useRef(null);
  const [failed, setFailed] = useState(false);

  // Keep the latest onClick in a ref so the once-bound plotly_click listener
  // always calls the CURRENT handler (which closes over the current data),
  // never the stale first-render one. Updated on every render — cheap, and
  // avoids re-attaching the Plotly listener when onClick/data change.
  const onClickRef = useRef(onClick);
  onClickRef.current = onClick;

  // No dep array ON PURPOSE: this effect redraws on every render so Plotly.react
  // diffs against the latest traces/layout/config (see the doc comment above).
  // Listing deps would be redundant with the every-render contract, not a fix.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    try {
      Plotly.react(el, traces || [], layout || baseLayout(), { ...baseConfig, ...config });
      if (failed) setFailed(false); // a good render recovers from a prior failure
    } catch (err) {
      // A malformed trace/layout must NOT crash the whole view (it would bubble to
      // ViewErrorBoundary and blank the screen). Degrade THIS chart to an inline
      // fallback; the rest of the perspective stays alive and interactive.
      console.error('[chart] Plotly render failed:', err);
      try {
        Plotly.purge(el);
      } catch {
        /* best effort — the element may already be unusable */
      }
      setFailed(true);
    }
  });

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    // Bind once with a stable trampoline that reads the LATEST handler from the
    // ref, so changing onClick/data never leaves a stale closure bound (and we
    // don't re-attach on every render). A no-op when no onClick is set.
    const handler = (e) => { const fn = onClickRef.current; if (fn) fn(e); };
    el.on?.('plotly_click', handler);
    const ro = new ResizeObserver(() => {
      try {
        Plotly.Plots.resize(el);
      } catch {
        /* element detached mid-resize — ignore */
      }
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      el.removeListener?.('plotly_click', handler);
      Plotly.purge(el);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={className} style={{ position: 'relative', width: '100%', height, ...style }}>
      <div ref={ref} style={{ width: '100%', height: '100%' }} />
      {failed && (
        <div
          role="status"
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            padding: '0 12px',
          }}
        >
          <span className="caption" style={{ color: 'var(--fg-3)' }}>
            Não foi possível renderizar este gráfico.
          </span>
        </div>
      )}
    </div>
  );
}
