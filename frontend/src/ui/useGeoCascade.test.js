// useGeoCascade.test.js — the geo cascade extracted from FilterMenu. Drives the
// hook via renderHook with plain fixtures (no window globals): deselecting a
// parent must prune its now-ineligible children from the selection Sets, so the
// applied filter always matches the visible cascade.

import { act, renderHook } from '@testing-library/react';
import { beforeAll, describe, expect, it } from 'vitest';

import React from 'react';

import useGeoCascade from './useGeoCascade.js';

// The ui hook reads React as a bare global (window.React in the real boot).
beforeAll(() => {
  globalThis.React = React;
});

// Two BR regions (N, SE) + one foreign region (EU/nation XX), with a state +
// município under each, so we can exercise nation→region→state→município pruning.
const UNIVERSES = {
  regionsUniverse: [
    { id: 'N', nation: 'BR' },
    { id: 'SE', nation: 'BR' },
    { id: 'EU', nation: 'XX' },
  ],
  statesUniverse: [
    { uf: 'PA', region: 'N' },
    { uf: 'SP', region: 'SE' },
    { uf: 'XX', region: 'EU' },
  ],
  munisUniverse: [
    { code: '1', uf: 'PA' },
    { code: '2', uf: 'SP' },
    { code: '3', uf: 'XX' },
  ],
};

const sorted = (set) => [...set].sort();

describe('useGeoCascade', () => {
  it('defaults to nations={BR} and prunes the foreign branch on mount', () => {
    const { result } = renderHook(() => useGeoCascade(UNIVERSES));
    // nations default = BR only.
    expect(sorted(result.current.nations)).toEqual(['BR']);
    // The EU region (nation XX) and its state/município are pruned because their
    // nation isn't selected — the cascade settles after the mount effects.
    expect(sorted(result.current.regions)).toEqual(['N', 'SE']);
    expect(sorted(result.current.states)).toEqual(['PA', 'SP']);
    expect(sorted(result.current.munis)).toEqual(['1', '2']);
  });

  it('deselecting all nations cascades to empty regions/states/municípios', () => {
    const { result } = renderHook(() => useGeoCascade(UNIVERSES));
    act(() => result.current.setNations(new Set()));
    expect(sorted(result.current.regions)).toEqual([]);
    expect(sorted(result.current.states)).toEqual([]);
    expect(sorted(result.current.munis)).toEqual([]);
  });

  it('deselecting a region prunes only that region’s states + municípios', () => {
    const { result } = renderHook(() => useGeoCascade(UNIVERSES));
    // From the settled {N, SE}, drop SE → only N's state (PA) + município (1) remain.
    act(() => result.current.setRegions(new Set(['N'])));
    expect(sorted(result.current.regions)).toEqual(['N']);
    expect(sorted(result.current.states)).toEqual(['PA']);
    expect(sorted(result.current.munis)).toEqual(['1']);
  });

  it('eligibility lists reflect the current selection (gating children by parent)', () => {
    const { result } = renderHook(() => useGeoCascade(UNIVERSES));
    expect(result.current.eligibleRegions.map((r) => r.id).sort()).toEqual(['N', 'SE']);
    act(() => result.current.setRegions(new Set(['N'])));
    expect(result.current.eligibleStates.map((s) => s.uf)).toEqual(['PA']);
    expect(result.current.eligibleMunis.map((m) => m.code)).toEqual(['1']);
  });
});
