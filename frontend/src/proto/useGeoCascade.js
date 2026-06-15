// useGeoCascade.js — the geographic selection + cascade for FilterMenu.
//
// Owns the four geo selection Sets (nations / regions / states / municípios),
// their eligibility memos (a child is eligible only while its parent is
// selected), and the cascade-pruning effects (deselecting a parent drops its
// now-ineligible children, so the APPLIED filter always matches the visible
// cascade — counts never read "27/23"). Extracted out of FilterMenu's 1100-line
// body so this self-contained state machine is unit-testable on its own
// (useGeoCascade.test.js drives it via renderHook).
//
// Universes are passed in (not read from module constants) so the hook is pure
// w.r.t. its inputs and testable with plain fixtures: regionsUniverse [{id,nation}],
// statesUniverse [{uf,region}], munisUniverse [{code,uf}]. Defaults mirror the
// original FilterMenu state: nations = {BR} only; regions/states/municípios = all.

function useGeoCascade({ regionsUniverse, statesUniverse, munisUniverse }) {
  const { useState, useMemo, useEffect } = React;

  const [nations, setNations] = useState(() => new Set(['BR']));
  const [regions, setRegions] = useState(() => new Set(regionsUniverse.map((r) => r.id)));
  const [states, setStates] = useState(() => new Set(statesUniverse.map((s) => s.uf)));
  const [munis, setMunis] = useState(() => new Set(munisUniverse.map((m) => m.code)));

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
  const eligibleMunis = useMemo(
    () =>
      munisUniverse.filter(
        (m) => states.has(m.uf) && eligibleStates.some((s) => s.uf === m.uf),
      ),
    [states, eligibleStates, munisUniverse],
  );

  // Prune children that are no longer eligible (parent deselected). Each effect
  // returns the same Set reference when nothing changed, so it never loops.
  useEffect(() => {
    const ok = new Set(eligibleRegions.map((r) => r.id));
    setRegions((prev) => {
      const next = new Set([...prev].filter((id) => ok.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [eligibleRegions]);
  useEffect(() => {
    const ok = new Set(eligibleStates.map((s) => s.uf));
    setStates((prev) => {
      const next = new Set([...prev].filter((uf) => ok.has(uf)));
      return next.size === prev.size ? prev : next;
    });
  }, [eligibleStates]);
  useEffect(() => {
    const ok = new Set(eligibleMunis.map((m) => m.code));
    setMunis((prev) => {
      const next = new Set([...prev].filter((c) => ok.has(c)));
      return next.size === prev.size ? prev : next;
    });
  }, [eligibleMunis]);

  return {
    nations,
    setNations,
    regions,
    setRegions,
    states,
    setStates,
    munis,
    setMunis,
    eligibleRegions,
    eligibleStates,
    eligibleMunis,
  };
}

window.useGeoCascade = useGeoCascade;
export default useGeoCascade;
