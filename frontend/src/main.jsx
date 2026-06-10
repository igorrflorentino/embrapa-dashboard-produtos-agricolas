// Entry point — replaces the prototype's Dashboard.html inline script.
//
// The prototype's ~45 JSX/JS modules use the window-global pattern (each file
// assigns window.X and reads window.Y lazily at render time). We preserve that
// contract: this entry sets window.React/ReactDOM, then side-effect-imports the
// modules in the same order Dashboard.html loaded them. The SYNTHETIC data-layer
// modules (dataStore/crossSource/crossAnalytics/crossChain/enrichment/demoFixture/
// synthUtils/previewData) are NOT imported from proto/ — they are replaced by
// API-backed implementations in src/data/ that keep identical window.* interfaces.
// The hand-rolled SVG chart modules are likewise replaced by Plotly.js-backed
// components in src/charts/ with identical names+props.
//
// MIGRATION STATUS: scaffold only — the ordered imports + boot port land with the
// data-layer/charts tasks (see PLANS/react_migration_contract_map.md).

import React from 'react'
import ReactDOM from 'react-dom/client'

window.React = React
window.ReactDOM = ReactDOM

// TODO(react-migration): side-effect imports (registries → data layer → charts →
// shell → views), then the boot gate + readStateFromURL port from Dashboard.html.

function ScaffoldNotice() {
  return (
    <div style={{ fontFamily: 'sans-serif', padding: '48px', color: '#1a3a2a' }}>
      <h1>Embrapa · Dashboard</h1>
      <p>Migração React em andamento — scaffold do Vite funcionando.</p>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(<ScaffoldNotice />)
