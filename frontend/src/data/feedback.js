// feedback.js — data layer for the "Enviar feedback" channel. A single POST to
// /api/feedback; the author is captured server-side from the IAP identity (no login
// field), so the payload carries only the report + auto-collected repro context
// (current permalink, view, banco, app version, optional user-agent). Exposes
// window.postFeedback so the ui/ FeedbackModal (a window-global component) can call it.

const API = '/api';

// App version for feedback diagnostics. The LIVE value is hydrated from the backend
// (pyproject → /api/source-meta.appVersion → window.APP_VERSION, set in dataStore) — the
// single source of truth. This literal is only the pre-hydration fallback; keep it at the
// current release so a report sent before any source-meta resolves isn't mistagged.
window.APP_VERSION = window.APP_VERSION || '1.7.0';

// POST one feedback report. Resolves with the echoed row (incl. issue_url when the
// backend forwarded it to GitHub); rejects with an Error carrying the server message.
window.postFeedback = async function postFeedback(payload) {
  const resp = await fetch(`${API}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${resp.status}`);
  }
  return resp.json();
};
