// useGeoCascade.cov.test.js — closes the reconcile prune path (lines 142-144):
// the branch where a level is NOT "following" its parents (the user has explicitly
// narrowed it to a proper subset) and a later parent change shrinks the eligible
// set, so the level is PRUNED (intersection with the new eligible) rather than
// refilled. The existing useGeoCascade.test.js only covers the "following" refill
// path and the no-op direct-clear; this drives the user-narrowed-then-pruned case.

import { act, renderHook } from '@testing-library/react';
import { beforeAll, describe, expect, it } from 'vitest';

import React from 'react';

import useGeoCascade from './useGeoCascade.js';

beforeAll(() => {
  globalThis.React = React;
});

const sorted = (set) => [...set].sort();

// Two regions under BR, each with one state; PA carries two municípios so a
// user-narrowed município selection can survive (or be pruned) on a state change.
const UNIVERSES = {
  regionsUniverse: [
    { id: 'N', nation: 'BR' },
    { id: 'SE', nation: 'BR' },
  ],
  statesUniverse: [
    { uf: 'PA', region: 'N' },
    { uf: 'SP', region: 'SE' },
  ],
  munisUniverse: [
    { code: '1', uf: 'PA' },
    { code: '2', uf: 'PA' },
    { code: '3', uf: 'SP' },
  ],
};

describe('useGeoCascade — reconcile PRUNE path (user-narrowed, not following)', () => {
  it('a user-narrowed município subset is PRUNED (not refilled) when a parent UF is dropped', () => {
    const { result } = renderHook(() => useGeoCascade(UNIVERSES));
    // Settled default: all of {1,2,3} selected (following).
    expect(sorted(result.current.munis)).toEqual(['1', '2', '3']);

    // The user NARROWS the município selection to a proper subset spanning PA + SP.
    // Now munis is NOT "following" (selection ⊊ eligible) — the user's choice stands.
    act(() => result.current.setMunis(new Set(['1', '3'])));
    expect(sorted(result.current.munis)).toEqual(['1', '3']);

    // Drop region N → its state PA (and municípios 1,2) become ineligible. munis is
    // user-narrowed, so the reconcile takes the ELSE branch (lines 142-144): it prunes
    // '1' (now ineligible) but KEEPS the explicit '3', never auto-adding siblings.
    act(() => result.current.setRegions(new Set(['SE'])));
    expect(sorted(result.current.states)).toEqual(['SP']);
    expect(sorted(result.current.munis)).toEqual(['3']); // pruned to the still-eligible subset
  });

  it('a user-narrowed subset that stays fully eligible is returned UNCHANGED (size guard, line 144)', () => {
    const { result } = renderHook(() => useGeoCascade(UNIVERSES));
    // Narrow munis to {1,2} (both under PA) — a proper subset → not following.
    act(() => result.current.setMunis(new Set(['1', '2'])));
    expect(sorted(result.current.munis)).toEqual(['1', '2']);
    const before = result.current.munis;

    // Drop SP's region (SE). PA + its municípios 1,2 stay eligible, so the prune leaves
    // {1,2} intact → next.size === prev.size → returns the SAME Set reference (no churn).
    act(() => result.current.setRegions(new Set(['N'])));
    expect(sorted(result.current.munis)).toEqual(['1', '2']);
    expect(result.current.munis).toBe(before); // identical reference: the no-change guard
  });
});
