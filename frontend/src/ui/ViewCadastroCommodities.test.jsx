// ViewCadastroCommodities.test.jsx — render + write coverage for the Curadoria editor.
// Agrupamentos are a FIRST-CLASS registry: the view fetches /api/catalog/entries +
// /api/catalog/groups (GET), writes entries via /api/catalog/entry and groups via
// /api/catalog/group (POST) — all mocked. Uses the GLOBAL React (main.jsx sets window.React).

import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';

let ViewCadastroCommodities;
let postBody;
let postUrl;

const ENTRIES = {
  entries: [
    {
      codigo_commodity: '4403', banco: 'comex', agrupamento: 'Madeira', code_prefix: '4403',
      ciclo_de_vida: 'Fazer Ingestão e deixar disponível', commodity_id: 'madeira',
      descricao_fonte: 'Madeira em toras (NCM)',
    },
    {
      codigo_commodity: '4407', banco: 'comtrade', agrupamento: 'Madeira', code_prefix: '4407',
      ciclo_de_vida: 'Fazer Ingestão e deixar disponível', commodity_id: 'madeira',
      descricao_fonte: null,
    },
  ],
  total: 2,
};
const GROUPS = {
  groups: [
    { group_id: 'madeira', group_name: 'Madeira', n_members: 2 },
    { group_id: 'castanha', group_name: 'Castanha', n_members: 0 }, // an EMPTY group
  ],
  total: 2,
};

function mockFetch(entries = ENTRIES, groups = GROUPS, orphans = { orphans: [], total: 0 }) {
  global.fetch = vi.fn((url, opts) => {
    if (opts && opts.method === 'POST') {
      postBody = JSON.parse(opts.body);
      postUrl = String(url);
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
    }
    const u = String(url);
    const body = u.includes('/api/catalog/orphans')
      ? orphans
      : u.includes('/api/catalog/groups')
        ? groups
        : entries;
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body), text: () => Promise.resolve('') });
  });
}

beforeEach(async () => {
  globalThis.React = React;
  window.React = React;
  window.SectionHeader = ({ overline, title }) => (
    <div className="sh"><span>{overline}</span><span>{title}</span></div>
  );
  postBody = null;
  postUrl = null;
  mockFetch();
  await import('./ViewCadastroCommodities.jsx');
  ViewCadastroCommodities = window.ViewCadastroCommodities;
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('ViewCadastroCommodities — the Curadoria catalog editor', () => {
  it('renders each first-class agrupamento with its members, source description + friendly bancos', async () => {
    const { container } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    // The Madeira group header + member count, and the EMPTY Castanha group card too.
    expect(container.textContent).toContain('Madeira');
    expect(container.textContent).toContain('(2)');
    expect(container.textContent).toContain('Castanha');
    expect(container.textContent).toContain('Agrupamento vazio');
    // Friendly banco labels + the source's original description.
    expect(container.textContent).toContain('MDIC COMEX');
    expect(container.textContent).toContain('UN COMTRADE');
    expect(container.textContent).toContain('Madeira em toras (NCM)');
    const codes = [...container.querySelectorAll('.dt-table tbody td')].map((e) => e.textContent);
    expect(codes).toContain('4403');
    expect(codes).toContain('4407');
  });

  it('creates a new agrupamento via /api/catalog/group', async () => {
    const { container, getByText } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    const newGroupInput = [...container.querySelectorAll('input[type="text"]')].find(
      (i) => i.getAttribute('placeholder') === 'Ex.: Castanha',
    );
    fireEvent.change(newGroupInput, { target: { value: 'Açaí' } });
    fireEvent.click(getByText('+ Criar'));
    await waitFor(() => expect(postBody).toBeTruthy());
    expect(postUrl).toContain('/api/catalog/group');
    expect(postBody.group_name).toBe('Açaí');
  });

  it('adds a commodity into a chosen agrupamento (commodity_id + name threaded)', async () => {
    const { container, getByText } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    fireEvent.click(getByText('+ Adicionar commodity'));
    fireEvent.change(container.querySelector('.cc-form input[type="text"]'), { target: { value: '0801' } });
    fireEvent.change(container.querySelector('.cc-form .cc-group-select'), { target: { value: 'castanha' } });
    fireEvent.click(getByText('Salvar commodity'));
    await waitFor(() => expect(postBody).toBeTruthy());
    expect(postUrl).toContain('/api/catalog/entry');
    expect(postBody.codigo_commodity).toBe('0801');
    expect(postBody.commodity_id).toBe('castanha');
    expect(postBody.agrupamento).toBe('Castanha');
    expect(postBody.banco).toBe('comex');
  });

  it('requires an agrupamento when adding (no POST fired)', async () => {
    const { container, getByText } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    fireEvent.click(getByText('+ Adicionar commodity'));
    fireEvent.change(container.querySelector('.cc-form input[type="text"]'), { target: { value: '0801' } });
    fireEvent.click(getByText('Salvar commodity'));
    await waitFor(() => expect(container.textContent).toContain('Escolha um agrupamento'));
    expect(postBody).toBeNull();
  });

  it('moves a commodity to another agrupamento via the row group dropdown', async () => {
    const { container } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.querySelector('.dt-table')).toBeTruthy());
    // The first member row's Agrupamento <select> (a .cc-group-select inside the table).
    fireEvent.change(container.querySelector('.dt-table .cc-group-select'), { target: { value: 'castanha' } });
    await waitFor(() => expect(postBody).toBeTruthy());
    expect(postUrl).toContain('/api/catalog/entry');
    expect(postBody.commodity_id).toBe('castanha');
    expect(postBody.agrupamento).toBe('Castanha');
  });

  it('removes a commodity via the tombstone endpoint (after confirm)', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { container } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.querySelector('.cc-remove')).toBeTruthy());
    fireEvent.click(container.querySelector('.cc-remove'));
    await waitFor(() => expect(postBody).toBeTruthy());
    expect(postUrl).toContain('/api/catalog/entry/remove');
    expect(postBody.codigo_commodity).toBe('4403');
    confirmSpy.mockRestore();
  });

  it('surfaces orphans as Descontinuados with the human-only deletion warning', async () => {
    mockFetch(ENTRIES, GROUPS, {
      orphans: [{
        codigo_commodity: '20079926', banco: 'comex', agrupamento: 'Cupuaçu',
        code_prefix: '20079926', status: 'descontinuado', flagged_at: null,
        warning: 'será removida por um operador',
      }],
      total: 1,
    });
    const { container } = render(<ViewCadastroCommodities />);
    await waitFor(() => expect(container.textContent).toContain('Descontinuados'));
    expect(container.textContent).toContain('Cupuaçu');
    expect(container.textContent).toContain('20079926');
    expect(container.textContent).toContain('nunca automaticamente');
  });
});
