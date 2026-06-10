// resource.js — generic async resource cache for the sync-over-async gate.
//
// The reused views call data producers SYNCHRONOUSLY during render and use the
// result immediately. API calls are async. This bridges the gap without touching
// the views (see PLANS/react_migration_contract_map.md §3.1):
//   • producers read get(key) synchronously (null until loaded);
//   • ensure(key, urlFactory) fires the fetch once and notify()s subscribers when
//     it resolves; a boundary component subscribes + re-renders → cache is hot →
//     the view's next synchronous get(key) returns real data.

const cache = new Map(); // key -> { state:'pending'|'ready'|'error', data?, error? }
const subs = new Set();

const notify = () => {
  for (const fn of subs) {
    try {
      fn();
    } catch {
      /* a subscriber threw — don't let it break the others */
    }
  }
};

/** The loaded data for a key, or null if not ready (pending/error/absent). */
export function get(key) {
  const e = cache.get(key);
  return e && e.state === 'ready' ? e.data : null;
}

/** 'idle' | 'pending' | 'ready' | 'error'. */
export function stateOf(key) {
  return cache.get(key)?.state || 'idle';
}

export function errorOf(key) {
  const e = cache.get(key);
  return e && e.state === 'error' ? e.error : null;
}

/** Kick off a fetch for key (idempotent — no-op if already pending/ready).
 *  urlFactory is a function so the URL is only built when actually fetching. */
export function ensure(key, urlFactory) {
  const e = cache.get(key);
  if (e && (e.state === 'pending' || e.state === 'ready')) return;
  cache.set(key, { state: 'pending' });
  fetch(urlFactory())
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => {
      cache.set(key, { state: 'ready', data });
      notify();
    })
    .catch((error) => {
      cache.set(key, { state: 'error', error: error.message || String(error) });
      notify();
    });
}

/** Drop a cached entry (e.g. after a curation write) so the next ensure refetches. */
export function invalidate(key) {
  cache.delete(key);
}

/** Subscribe to cache changes; returns an unsubscribe fn. */
export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}
