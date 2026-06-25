// ViewCadastroCommodities.test.jsx — render + write coverage for the Curadoria (catalog)
// editor. It fetches /api/catalog/entries (GET) and writes via /api/catalog/entry (POST);
// both mocked. Uses the GLOBAL React (main.jsx sets window.React).

import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';

let ViewCadastroCommodities;
let postBody;

const ENTRIES = {
  entries: [
    {
      codigo_commodity: '4403', banco: 'comex', agrupamento: 'Madeira', code_prefix: '4403',
      industrializacao: 'Commodity Pura', ciclo_de_vida: 'Fazer Ingestão e deixar disponível',
      commodity_id: 'madeira',
    },
    {
      codigo_commodity: '4407', banco: 'comtrade', agrupamento: 'Madeira', code_prefix: '4407',
      industrializacao: null, ciclo_de_vida: 'Fazer Ingestão e deixar disponível',
      commodity_id: 'madeira',
    },
  ],
  total: 2,
  by_agrupamento: [{ agrupamento: 'Madeira', n: 2, bancos: ['comex', 'comtrade'] }],
};

function mockFetch(entries = ENTRIES) {
  global.fetch = vi.fn((url, opts) => {
    if (opts && opts.method === 'POST') {
      postBody = JSON.parse(opts.body);
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(entries), text: () => Promise.resolve('') });
  });
}

beforeEach(async () => {
  globalThis.React = React;
  window.React = React;
  window.SectionHeader = ({ overline, title }) => (
    <div className="sh"><span>{overline}</span><span>{title}</span></div>
  );
  postBody = null;
  mockFetch();
  await import('./ViewCadastroCommodities.jsx');
  ViewCadastroCommodities = window.ViewCadastroCommodities;
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('ViewCadastroCommodities — the Curadoria catalog editor', () => {
  it('lists the catalog grouped by Agrupamento with friendly banco names', async () => {
    const { container } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    // the agrupamento group header + member count
    expect(container.textContent).toContain('Madeira');
    expect(container.textContent).toContain('(2)');
    // friendly banco labels (not the raw source tokens) + the codes
    expect(container.textContent).toContain('MDIC COMEX');
    expect(container.textContent).toContain('UN COMTRADE');
    const codes = [...container.querySelectorAll('.dt-table tbody td')].map((e) => e.textContent);
    expect(codes).toContain('4403');
    expect(codes).toContain('4407');
  });

  it('adds a commodity through the catalog API (key + defaults threaded)', async () => {
    const { container, getByText } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    fireEvent.click(getByText('+ Adicionar commodity'));
    const textInputs = container.querySelectorAll('.cc-form input[type="text"]');
    fireEvent.change(textInputs[0], { target: { value: '0801' } }); // codigo_commodity
    fireEvent.change(textInputs[1], { target: { value: 'Castanha' } }); // agrupamento
    fireEvent.click(getByText('Salvar commodity'));
    await waitFor(() => expect(postBody).toBeTruthy());
    expect(postBody.codigo_commodity).toBe('0801');
    expect(postBody.agrupamento).toBe('Castanha');
    expect(postBody.banco).toBe('comex'); // the default banco
    expect(postBody.ciclo_de_vida).toBe('Fazer Ingestão e deixar disponível');
  });

  it('removes a commodity via the tombstone endpoint (after confirm)', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { container } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.querySelector('.cc-remove')).toBeTruthy());
    fireEvent.click(container.querySelector('.cc-remove'));
    await waitFor(() => expect(postBody).toBeTruthy());
    expect(postBody.codigo_commodity).toBe('4403');
    expect(postBody.banco).toBe('comex');
    confirmSpy.mockRestore();
  });
});
