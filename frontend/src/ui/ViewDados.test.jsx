// ViewDados.test.jsx — render coverage for the raw tabular-inspection view. It fetches
// the banco's table list (/api/tables) then a page of rows (/api/table); both are mocked.
// Like ViewRebanho, the view uses the GLOBAL React (main.jsx sets window.React in the app),
// so we set it before importing the view (the top-level `const { useState } = React`).

import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';

let ViewDados;

const TABLES = [
  { id: 'gold_ppm_production', label: 'Gold · pecuária PPM', grain: 'linha por (ano, UF, município)', dataset: 'bq_gold_dataset' },
  { id: 'serving_ppm_annual', label: 'Serving · mart anual', grain: 'ano × UF × produto × família', dataset: 'bq_serving_dataset' },
];
const PAGE = {
  columns: [
    { name: 'reference_year', type: 'INTEGER' },
    { name: 'product_code', type: 'STRING' },
    { name: 'qty_native', type: 'FLOAT' },
  ],
  rows: [[2024, '2670', 238180757], [2023, '2670', null]],
  total: 2400000,
  table: 'gold_ppm_production',
  label: 'Gold · pecuária PPM',
  grain: 'linha por (ano, UF, município)',
};

function mockFetch(tablesBody = TABLES, pageBody = PAGE) {
  global.fetch = vi.fn((url) => {
    // "/api/tables?…" vs "/api/table?…" — the latter never contains the trailing 's'.
    const body = String(url).includes('/api/tables') ? tablesBody : pageBody;
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
  await import('./ViewDados.jsx');
  ViewDados = window.ViewDados;
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('ViewDados — raw table inspection', () => {
  it('lists the banco tables and renders the grid columns + rows', async () => {
    const { container } = render(<ViewDados database="ibge_ppm" />);
    // table picker chips appear once /api/tables resolves
    await waitFor(() => expect(container.querySelectorAll('.pp-chip').length).toBe(2));
    const chips = [...container.querySelectorAll('.pp-chip')].map((e) => e.textContent);
    expect(chips.some((t) => /Gold/.test(t))).toBe(true);
    expect(chips.some((t) => /Serving/.test(t))).toBe(true);
    // grid headers + a row appear once /api/table resolves
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    const headers = [...container.querySelectorAll('.dt-table thead th')].map((e) =>
      e.textContent.replace(/[▲▼\s]/g, '')
    );
    expect(headers).toEqual(['reference_year', 'product_code', 'qty_native']);
    expect(container.querySelector('.dt-table tbody tr')).toBeTruthy();
    expect(container.querySelector('.dt-null')).toBeTruthy(); // the null cell renders ∅
    expect(container.textContent).toContain('2.400.000'); // pt-BR total row count
  });

  it('shows an honest empty state when the banco has no inspectable tables', async () => {
    mockFetch([], PAGE); // /api/tables → []
    const { container } = render(<ViewDados database="sefaz_nf" />);
    await waitFor(() => expect(container.textContent).toContain('Nenhuma tabela inspecionável'));
    expect(container.querySelector('.dt-table')).toBeNull(); // no grid without a table
  });
});
