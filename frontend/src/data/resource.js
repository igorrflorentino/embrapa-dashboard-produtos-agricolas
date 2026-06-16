// resource.js — generic async resource cache for the sync-over-async gate.
//
// The reused views call data producers SYNCHRONOUSLY during render and use the
// result immediately. API calls are async. This bridges the gap without touching
// the views (see PLANS/react_migration_contract_map.md §3.1):
//   • producers read get(key) synchronously (null until loaded);
//   • ensure(key, urlFactory) fires the fetch once and notify()s subscribers when
//     it resolves; a boundary component subscribes + re-renders → cache is hot →
//     the view's next synchronous get(key) returns real data.

const cache = new Map(); // key -> { state:'pending'|'ready'|'error', data?, error?, attempts? }
const subs = new Set();

// Per-key monotonic fetch generation. A reload/invalidate can start a NEWER fetch
// for the same key while an older one is still in flight; without this token the
// older response (resolving last) could overwrite the newer one. We capture the
// generation at fetch start and ignore a resolution whose token is stale.
const gen = new Map(); // key -> number (latest started generation)

// Producers call ensure() SYNCHRONOUSLY on every render, and each failure
// notify()s subscribers → another render → another ensure(). If ensure() always
// re-fetched on 'error', a persistently-failing endpoint would become an
// unbounded request storm (and, against an uncapped warehouse, a self-inflicted
// cost/DoS). Cap auto-retries: after MAX_ATTEMPTS the key stays errored until a
// user action calls invalidate(key) to reset and retry.
const MAX_ATTEMPTS = 3;

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
  // Stop auto-retrying a key that has already failed MAX_ATTEMPTS times — a
  // persistent backend failure must not loop the dashboard into a request storm.
  // invalidate(key) clears the entry (resetting attempts) for an explicit retry.
  if (e && e.state === 'error' && (e.attempts || 0) >= MAX_ATTEMPTS) return;
  const attempts = (e?.attempts || 0) + 1;
  // Stamp this fetch with a fresh generation; a later ensure() for the same key
  // bumps it, marking any in-flight older fetch's resolution stale.
  const myGen = (gen.get(key) || 0) + 1;
  gen.set(key, myGen);
  cache.set(key, { state: 'pending', attempts });
  fetch(urlFactory())
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => {
      if (gen.get(key) !== myGen) return; // a newer fetch superseded this one — drop it
      cache.set(key, { state: 'ready', data });
      notify();
    })
    .catch((error) => {
      if (gen.get(key) !== myGen) return; // stale failure — don't clobber a newer fetch
      cache.set(key, { state: 'error', error: error.message || String(error), attempts });
      notify();
    });
}

/** Drop a cached entry (e.g. after a curation write) so the next ensure refetches.
 *  Bumps the generation too, so a fetch already in flight for this key cannot
 *  repopulate it after the invalidation (its resolution is now stale). */
export function invalidate(key) {
  cache.delete(key);
  gen.set(key, (gen.get(key) || 0) + 1);
}

/** Subscribe to cache changes; returns an unsubscribe fn. */
export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}
