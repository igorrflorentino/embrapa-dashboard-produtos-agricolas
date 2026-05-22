/* ============================================================
 * Page-level loading state coordinator.
 *
 * Adds `is-loading` to <body> whenever any Dash callback is pending
 * (detected via dcc.Loading spinner elements and Dash's own
 * `data-dash-is-loading` attribute). Removes the class as soon as no
 * loading indicator is present in the DOM.
 *
 * The CSS in 02-dashboard.css then:
 *   - shows the top progress bar
 *   - enables pointer-events on .page-loading-block so the user
 *     can't interact with half-loaded content
 *
 * We intentionally start in loading state — at boot, before Dash
 * even mounts the layout, there are no spinners yet to detect, but
 * we know the dashboard is still loading. The observer takes over
 * once the layout hydrates.
 * ============================================================ */
(function () {
  "use strict";

  var LOADING_SELECTORS = [
    "._dash-loading-callback",
    '[data-dash-is-loading="true"]',
  ];

  function anyPendingCallbacks() {
    for (var i = 0; i < LOADING_SELECTORS.length; i++) {
      if (document.querySelector(LOADING_SELECTORS[i])) {
        return true;
      }
    }
    return false;
  }

  // Debounce removals so a brief gap between callbacks (e.g. one
  // finishing the same tick the next starts) doesn't flicker the bar.
  var clearTimer = null;
  var IDLE_DELAY_MS = 180;

  function refresh() {
    var loading = anyPendingCallbacks();
    if (loading) {
      if (clearTimer) {
        clearTimeout(clearTimer);
        clearTimer = null;
      }
      document.body.classList.add("is-loading");
      return;
    }
    if (clearTimer) return;
    clearTimer = setTimeout(function () {
      clearTimer = null;
      if (!anyPendingCallbacks()) {
        document.body.classList.remove("is-loading");
      }
    }, IDLE_DELAY_MS);
  }

  function init() {
    // Start in loading state. The first refresh() after Dash hydrates
    // will either keep it (if callbacks are pending) or clear it.
    document.body.classList.add("is-loading");

    var observer = new MutationObserver(refresh);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-dash-is-loading", "class"],
    });

    // Safety net: poll once a second in case a mutation slips through
    // (rare, but cheap to do — no DOM access if class is unchanged).
    setInterval(refresh, 1000);

    // Initial check after Dash has had a tick to mount.
    setTimeout(refresh, 250);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
