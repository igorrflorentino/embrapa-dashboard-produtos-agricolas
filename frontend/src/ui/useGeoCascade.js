// useGeoCascade.js — the geographic selection + cascade for FilterMenu.
//
// Models Brazil's geography as a spine (nação ▸ região ▸ UF) plus, UNDER the UF,
// the TWO PARALLEL IBGE sub-UF divisions that converge on the município:
//
//   nações ▸ regiões ▸ estados ┬▸ mesorregiões ▸ microrregiões ─┐
//                              └▸ reg. intermediárias ▸ reg. imediatas ─┴▸ municípios
//
// The two divisions do NOT nest into each other (a microrregião and a região
// imediata are independent partitions of the UF), so they are independent FACETS:
// a município is in the selection iff it passes EVERY active facet (its UF is
// selected AND its meso/micro/intermediária/imediata are each selected) — an
// intersection, not a single chain.
//
// Each level is a (selection Set, eligibility memo, prune effect) triple: a child
// is eligible only while its parents are selected, and deselecting a parent prunes
// its now-ineligible children so the APPLIED filter always matches the visible
// cascade. Extracted from FilterMenu so this state machine is unit-testable on its
// own (useGeoCascade.test.js drives it via renderHook).
//
// Universes (passed in, so the hook is pure w.r.t. its inputs):
//   regionsUniverse [{id, nation}]
//   statesUniverse  [{uf, region}]
//   munisUniverse   [{code, uf, meso, micro, intermediaria, imediata}]  ← the
//     /geo-mesh payload. The four sub-UF codes are '' for a município with no
//     grouping at that level (e.g. a post-classic município has no meso/micro);
//     a BLANK code means "not constrained by that facet", so such a município is
//     never wrongly dropped — it stays filterable by the levels it DOES have.
//   Older callers passing munis as [{code, uf}] keep working: the absent facet
//   fields read as '' (unconstrained), so the new levels are inert.

function useGeoCascade({ regionsUniverse, statesUniverse, munisUniverse }) {
  const { useState, useMemo, useEffect, useRef } = React;

  // Distinct NON-BLANK facet codes across a set of município rows.
  const distinctFacet = (rows, key) => {
    const s = new Set();
    rows.forEach((m) => {
      const v = m[key] || '';
      if (v) s.add(v);
    });
    return [...s];
  };
  // A município passes a facet iff it has no code there ('' = unconstrained) or its
  // code is currently selected. NOTE the deliberate asymmetry with dataFilters.js
  // `muniPassesFacets` (GEO-3): here a BLANK-code município stays ELIGIBLE in the
  // cascade (lenient), but the DATA rollup EXCLUDES it once that facet narrows (strict
  // — a city belonging to no mesorregião shouldn't appear under a meso filter). The
  // two encode opposite blank-code policies ON PURPOSE; don't "reconcile" them.
  const passes = (m, set, key) => {
    const v = m[key] || '';
    return v === '' || set.has(v);
  };

  const [nations, setNations] = useState(() => new Set(['BR']));
  const [regions, setRegions] = useState(() => new Set(regionsUniverse.map((r) => r.id)));
  const [states, setStates] = useState(() => new Set(statesUniverse.map((s) => s.uf)));
  const [mesos, setMesos] = useState(() => new Set(distinctFacet(munisUniverse, 'meso')));
  const [micros, setMicros] = useState(() => new Set(distinctFacet(munisUniverse, 'micro')));
  const [inters, setInters] = useState(() => new Set(distinctFacet(munisUniverse, 'intermediaria')));
  const [imediatas, setImediatas] = useState(
    () => new Set(distinctFacet(munisUniverse, 'imediata')),
  );
  const [munis, setMunis] = useState(() => new Set(munisUniverse.map((m) => m.code)));

  // ── Eligibility (down the spine, then the two parallel branches) ──────────────
  const eligibleRegions = useMemo(
    () => regionsUniverse.filter((r) => nations.has(r.nation)),
    [nations, regionsUniverse],
  );
  const eligibleStates = useMemo(
    () =>
      statesUniverse.filter(
        (s) => regions.has(s.region) && eligibleRegions.some((r) => r.id === s.region),
      ),
    [regions, eligibleRegions, statesUniverse],
  );
  // Municípios under the currently-selected UFs — the common pool the sub-UF facet
  // option lists are derived from (and the município leaf is filtered from).
  const munisInStates = useMemo(
    () =>
      munisUniverse.filter(
        (m) => states.has(m.uf) && eligibleStates.some((s) => s.uf === m.uf),
      ),
    [states, eligibleStates, munisUniverse],
  );
  // Classic branch: meso (under UFs) → micro (under selected mesos).
  const eligibleMesos = useMemo(() => distinctFacet(munisInStates, 'meso'), [munisInStates]);
  const eligibleMicros = useMemo(
    () => distinctFacet(munisInStates.filter((m) => passes(m, mesos, 'meso')), 'micro'),
    [munisInStates, mesos],
  );
  // 2017 branch: intermediária (under UFs) → imediata (under selected intermediárias).
  const eligibleInters = useMemo(
    () => distinctFacet(munisInStates, 'intermediaria'),
    [munisInStates],
  );
  const eligibleImediatas = useMemo(
    () =>
      distinctFacet(
        munisInStates.filter((m) => passes(m, inters, 'intermediaria')),
        'imediata',
      ),
    [munisInStates, inters],
  );
  // The município leaf = the INTERSECTION of every active facet.
  const eligibleMunis = useMemo(
    () =>
      munisInStates.filter(
        (m) =>
          passes(m, mesos, 'meso') &&
          passes(m, micros, 'micro') &&
          passes(m, inters, 'intermediaria') &&
          passes(m, imediatas, 'imediata'),
      ),
    [munisInStates, mesos, micros, inters, imediatas],
  );

  // ── Reconcile each level's selection with its eligibility on a parent change ──
  // A level is "FOLLOWING" its parents while its selection still covers everything
  // that was eligible at the last reconcile (the default, and after a bulk select).
  //   • A following level REFILLS to the new eligible set — so deselecting a parent
  //     drops its children AND re-selecting the parent restores them (the "Limpar a
  //     coluna-pai, depois escolher um" fix). Because "following" is judged against
  //     the PREVIOUS eligible (a ref), it survives the cascade settling across
  //     levels — the multi-parent município leaf refills correctly once its meso/
  //     micro parents land, instead of sticking on a stale intermediate value.
  //   • A user-NARROWED subset (selection ⊊ previous eligible) is pruned only — the
  //     user's explicit choice stands; new siblings are not auto-added.
  // Each effect returns the same Set reference when nothing changed → never loops.
  const prevEligible = useRef({});
  const reconcile = (level, setFn, okList, keyOf) =>
    setFn((prev) => {
      const ok = okList.map(keyOf);
      const prior = prevEligible.current[level];
      prevEligible.current[level] = ok;
      const following = prior == null || (prior.length === prev.size && prior.every((k) => prev.has(k)));
      if (following) {
        if (ok.length === prev.size && ok.every((k) => prev.has(k))) return prev;
        return new Set(ok);
      }
      const okSet = new Set(ok);
      const next = new Set([...prev].filter((v) => okSet.has(v)));
      return next.size === prev.size ? prev : next;
    });
  useEffect(() => reconcile('regions', setRegions, eligibleRegions, (r) => r.id), [eligibleRegions]);
  useEffect(() => reconcile('states', setStates, eligibleStates, (s) => s.uf), [eligibleStates]);
  useEffect(() => reconcile('mesos', setMesos, eligibleMesos, (v) => v), [eligibleMesos]);
  useEffect(() => reconcile('micros', setMicros, eligibleMicros, (v) => v), [eligibleMicros]);
  useEffect(() => reconcile('inters', setInters, eligibleInters, (v) => v), [eligibleInters]);
  useEffect(() => reconcile('imediatas', setImediatas, eligibleImediatas, (v) => v), [eligibleImediatas]);
  useEffect(() => reconcile('munis', setMunis, eligibleMunis, (m) => m.code), [eligibleMunis]);

  return {
    nations,
    setNations,
    regions,
    setRegions,
    states,
    setStates,
    mesos,
    setMesos,
    micros,
    setMicros,
    inters,
    setInters,
    imediatas,
    setImediatas,
    munis,
    setMunis,
    eligibleRegions,
    eligibleStates,
    eligibleMesos,
    eligibleMicros,
    eligibleInters,
    eligibleImediatas,
    eligibleMunis,
  };
}

window.useGeoCascade = useGeoCascade;
export default useGeoCascade;
