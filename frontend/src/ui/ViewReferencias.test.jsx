// ViewReferencias.test.jsx — render coverage for the read-only seed-consultation view.
// It fetches the seed catalog (/api/seeds) then a page of rows (/api/seed); both mocked.
// Uses the GLOBAL React (main.jsx sets window.React), set before importing the view.

import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';

let ViewReferencias;

// NOTE: the first seed is a SYNTHETIC fixture (editable: true) that only exercises the
// "editable" badge branch of the generic grid. No PRODUCTION seed is editable — every real
// gateway._SEED_CATALOG entry is editable:false (locked by the backend tests). Do not read
// this as a real consultable seed; it's a rendering fixture, deliberately not a retired
// real table name.
const SEEDS = [
  {
    id: 'demo_editable_seed',
    label: 'Seed editável (demonstração)',
    editable: true,
    description: 'Fixture sintética para exercitar o selo de editável.',
  },
  {
    id: 'historical_currency_factors',
    label: 'Fatores de reforma monetária',
    editable: false,
    description: 'Multiplicadores que convertem valores históricos para o Real atual.',
  },
];
const SEED_PAGE = {
  columns: [
    { name: 'commodity_id', type: 'STRING' },
    { name: 'source', type: 'STRING' },
    { name: 'codigo_commodity', type: 'STRING' },
  ],
  rows: [['acai', 'pevs', '3403'], ['acai', 'comex', null]],
  total: 46,
  table: 'demo_editable_seed',
  label: 'Seed editável (demonstração)',
  grain: 'Fixture sintética para exercitar o selo de editável.',
  editable: true,
};

function mockFetch(seedsBody = SEEDS, pageBody = SEED_PAGE) {
  global.fetch = vi.fn((url) => {
    // "/api/seeds" (the catalog) vs "/api/seed?…" (one table) — the latter never has the 's'.
    const body = String(url).includes('/api/seeds') ? seedsBody : pageBody;
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(body),
      text: () => Promise.resolve(''),
    });
  });
}

beforeEach(async () => {
  globalThis.React = React;
  window.React = React;
  window.SectionHeader = ({ overline, title, action }) => (
    <div className="sh">
      <span className="sh-ov">{overline}</span>
      <span className="sh-title">{title}</span>
      <span className="sh-action">{action}</span>
    </div>
  );
  mockFetch();
  await import('./ViewReferencias.jsx');
  ViewReferencias = window.ViewReferencias;
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); delete window.openFeedback; });

describe('ViewReferencias — read-only seed consultation', () => {
  it('lists the seed catalog and renders the grid columns + rows + editable badge', async () => {
    const { container } = render(<ViewReferencias />);
    // seed picker chips appear once /api/seeds resolves
    await waitFor(() => expect(container.querySelectorAll('.pp-chip').length).toBe(2));
    const chips = [...container.querySelectorAll('.pp-chip')].map((e) => e.textContent);
    expect(chips.some((t) => /Seed editável/.test(t))).toBe(true);
    expect(chips.some((t) => /reforma monetária/.test(t))).toBe(true);
    // grid headers + rows appear once /api/seed resolves
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    const headers = [...container.querySelectorAll('.dt-table thead th')]
      .map((e) => e.textContent.replace(/[▲▼\s]/g, ''))
      .filter(Boolean); // drop the empty leading "report" column header
    expect(headers).toEqual(['commodity_id', 'source', 'codigo_commodity']);
    expect(container.querySelector('.dt-null')).toBeTruthy(); // the null cell renders ∅
    expect(container.textContent).toContain('46'); // total row count
    // the first (synthetic) seed is editable → the catalog badge says so
    expect(container.textContent).toContain('Editável pelo cadastro de commodities');
  });

  it('reports a suspect row through the feedback loop, prefilled with the seed + row', async () => {
    window.openFeedback = vi.fn();
    const { container } = render(<ViewReferencias />);
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    const reportBtn = container.querySelector('.rf-report');
    expect(reportBtn).toBeTruthy();
    fireEvent.click(reportBtn);
    expect(window.openFeedback).toHaveBeenCalledTimes(1);
    const arg = window.openFeedback.mock.calls[0][0];
    expect(arg.view).toBe('referencias');
    expect(arg.category).toBe('bug');
    // the prefilled message names the seed + carries the suspect row's values
    expect(arg.message).toContain('Seed editável (demonstração) (demo_editable_seed)');
    expect(arg.message).toContain('commodity_id: acai');
  });
});
