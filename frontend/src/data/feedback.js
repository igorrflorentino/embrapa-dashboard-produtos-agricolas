// feedback.js — data layer for the "Reportar problema" channel. A single POST to
// /api/feedback; the author is captured server-side from the IAP identity (no login
// field), so the payload carries only the report + auto-collected repro context
// (current permalink, view, banco, app version, optional user-agent). Exposes
// window.postFeedback so the ui/ FeedbackModal (a window-global component) can call it.

const API = '/api';

// App version for feedback diagnostics. Kept in sync with package.json (read at
// build time would need a Vite define; a constant is fine for a diagnostic field).
window.APP_VERSION = window.APP_VERSION || '0.1.0';

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
