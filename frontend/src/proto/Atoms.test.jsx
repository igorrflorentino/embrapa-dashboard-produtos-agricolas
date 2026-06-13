// Atoms.test.jsx — the NotApplicableNote inline notice. The data producers withhold
// a filter param a view's grain cannot honour and surface WHY via a `notApplicable`
// object (e.g. { states: '…' } for the origin-UF filter on a country-origin banco,
// { basket: '…' } for the product basket on the crop-picker productivity view). This
// atom makes that refusal VISIBLE on screen — the audit gap was that the note existed
// only in the API payload and no .jsx view ever rendered it. Renders nothing when
// there is no applicable note, so a view can place it unconditionally.

import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import React from 'react';

// The proto modules read React as a bare global and components as window.X — install
// both BEFORE importing Atoms.jsx (mirrors bootstrap-globals.js in the real boot).
beforeAll(async () => {
  globalThis.React = React;
  window.React = React;
  // NotApplicableNote renders a <window.Icon>; a minimal stub is enough here.
  window.Icon = ({ name }) => React.createElement('span', { 'data-icon': name });
  await import('./Atoms.jsx');
});

afterEach(cleanup);

describe('NotApplicableNote', () => {
  it('renders the message for a single not-applicable dimension', () => {
    const note = { states: 'O filtro de UF de origem não se aplica a este banco.' };
    render(React.createElement(window.NotApplicableNote, { note }));
    expect(screen.getByText(note.states)).toBeTruthy();
  });

  it('renders one line per dimension when several filters do not apply', () => {
    const note = {
      states: 'O filtro de UF de origem não se aplica.',
      basket: 'A cesta de produtos não se aplica aqui.',
    };
    const { container } = render(React.createElement(window.NotApplicableNote, { note }));
    expect(screen.getByText(note.states)).toBeTruthy();
    expect(screen.getByText(note.basket)).toBeTruthy();
    expect(container.querySelectorAll('p.cs-note')).toHaveLength(2);
  });

  it('renders nothing when there is no note (the common, unfiltered case)', () => {
    for (const empty of [undefined, null, {}]) {
      const { container } = render(React.createElement(window.NotApplicableNote, { note: empty }));
      expect(container.querySelector('.na-note')).toBeNull();
      cleanup();
    }
  });

  it('ignores falsy values inside the note object', () => {
    const note = { states: '', basket: 'Só esta aparece.' };
    const { container } = render(React.createElement(window.NotApplicableNote, { note }));
    expect(container.querySelectorAll('p.cs-note')).toHaveLength(1);
    expect(screen.getByText('Só esta aparece.')).toBeTruthy();
  });
});
