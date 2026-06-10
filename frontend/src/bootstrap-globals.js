// bootstrap-globals.js — MUST be the FIRST import in main.jsx.
//
// The vendored prototype modules read React as a *bare global* (`const { useState
// } = React`) and reference components as `window.X` (`<window.LineChart/>`). In
// strict-mode ESM a bare identifier resolves only if it exists as a globalThis
// property — so `window.React` has to be set BEFORE any proto/ module evaluates.
// ESM runs a module's imports before its body, so this can't live in main.jsx's
// body; it lives here and is imported first (its own imports — react — resolve
// before this body runs, which is exactly what we need).

import React from 'react';
import * as ReactDOMClient from 'react-dom/client';

// Plotly.js (and some of its deps) reference the Node global `global` and
// `process`. The browser has neither, so polyfill them BEFORE any chart module
// imports Plotly (this file is imported first). Without this, plotly.js throws
// "global is not defined" at module-eval and halts the whole boot.
if (typeof globalThis.global === 'undefined') globalThis.global = globalThis;
if (typeof globalThis.process === 'undefined') globalThis.process = { env: {} };

window.React = React;
window.ReactDOM = ReactDOMClient; // proto/boot uses window.ReactDOM.createRoot
