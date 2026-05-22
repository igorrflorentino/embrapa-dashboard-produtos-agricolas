/* ============================================================
 * Page-level loading state coordinator.
 *
 * Adds `is-loading` to <body> whenever any Dash callback is pending
 * (detected via dcc.Loading spinner elements and Dash's own
 * `data-dash-is-loading` attribute). Removes the class once no
 * loading indicator is present in the DOM.
 *
 * Implementation: pure polling at 4 Hz. A previous version used a
 * MutationObserver with subtree=true, which Plotly's animation
 * mutations triggered thousands of times per second — that froze
 * the browser tab. Polling is bounded and predictable; the 250ms
 * lag is invisible compared to typical callback durations.
 *
 * The CSS in 02-dashboard.css then:
 *   - shows the top progress bar
 *   - enables pointer-events on .page-loading-block so the user
 *     can't interact with half-loaded content
 * ============================================================ */
(function () {
  "use strict";

  var POLL_MS = 250;
  var INITIAL_GRACE_MS = 800; // stay in loading state for the first frame regardless

  var startedAt = Date.now();
  var lastLoadingState = null; // tracks last applied state so we avoid no-op class writes

  function anyPendingCallback() {
    // querySelector is O(1) hash lookup on the matching first node; even on
    // huge DOMs this is microseconds, and we only run it 4x/sec.
    if (document.querySelector("._dash-loading-callback")) return true;
    if (document.querySelector('[data-dash-is-loading="true"]')) return true;
    return false;
  }

  function refresh() {
    var inGrace = Date.now() - startedAt < INITIAL_GRACE_MS;
    var loading = inGrace || anyPendingCallback();
    if (loading === lastLoadingState) return; // nothing to do
    lastLoadingState = loading;
    if (loading) {
      document.body.classList.add("is-loading");
    } else {
      document.body.classList.remove("is-loading");
    }
  }

  function init() {
    // Start in loading state immediately.
    document.body.classList.add("is-loading");
    lastLoadingState = true;
    setInterval(refresh, POLL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
