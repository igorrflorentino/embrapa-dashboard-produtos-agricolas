// vitest.setup.js — jsdom has no bootstrap-globals.js, so replicate the globals the UI
// modules rely on. The CLASSIC JSX runtime (pinned in vite.config.js for dev, build AND
// Vitest — audit DEV-1) compiles JSX to `React.createElement(...)` against the global
// `window.React`, and the ui/ modules read React as a bare global; both need it set here.
import React from 'react';
import * as ReactDOMClient from 'react-dom/client';

if (typeof globalThis.global === 'undefined') globalThis.global = globalThis;
if (typeof globalThis.process === 'undefined') globalThis.process = { env: {} };
window.React = React;
window.ReactDOM = ReactDOMClient;
