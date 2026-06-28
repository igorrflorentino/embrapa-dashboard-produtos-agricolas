// FilterMenu.cov.test.jsx — render + interaction coverage for the big filter modal
// (FilterMenu.jsx, ~1100 lines, the produtos/fluxo/período/geografia/qualidade
// sections). FilterMenu is a side-effect module that reads window.QUALITY_FLAGS at
// IMPORT time (the module-level `QUALITY` array), so we seed that BEFORE importing it.
//
// Rather than re-implement the cascade/summary/chip logic, we import the REAL data-
// layer modules it leans on (useGeoCascade.js, filterSummary.js, chipFmt.js) and stub
// only the thin registry globals (bancoById/filterSchemaFor/flowOptionsFor/geoLevelFor/
// bancoTable/dataStore/geoMesh/CURRENCY_FX/TIER_LABEL) with the same minimal shapes the
// sibling tests (FilterTriggerBar.test.jsx, csvExport.cov.test.js) use.
//
// We assert: the closed gate (null), the open render (every gated section + the footer
// buttons), a product + a quality checkbox toggle, a período quick-range chip, the
// Fluxo segment for a trade banco, the apply/clear footer wiring, the Escape-to-close
// listener, and the "soon" banco read-only preview body.

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';

// ── REAL quality registry (the 9 Gold flags) — set BEFORE importing FilterMenu so the
//    module-level QUALITY array is populated, matching data.js verbatim. ──────────────
const QUALITY_FLAGS = [
  { id: 'OK', label: 'Normais', color: 'var(--ok)' },
  { id: 'MISSING_VALUE', label: 'Valor financeiro ausente', color: 'var(--warn)' },
  { id: 'MISSING_QUANTITY', label: 'Quantidade ausente', color: 'var(--info)' },
  { id: 'MISSING_WEIGHT', label: 'Peso ausente', color: 'var(--viz-4)' },
  { id: 'INCOMPLETE', label: 'Incompleto', color: 'var(--viz-7)' },
  { id: 'OUTLIER_QUANTITY', label: 'Quantidade atípica (válida)', color: 'var(--viz-3)' },
  { id: 'PROBLEMATIC_QUANTITY', label: 'Quantidade problemática (provável erro)', color: 'var(--viz-9)' },
  { id: 'OUTLIER_VALUE', label: 'Valor atípico (válido)', color: 'var(--viz-5)' },
  { id: 'PROBLEMATIC_VALUE', label: 'Valor problemático (provável erro)', color: 'var(--err)' },
];

const PRODUCTS = [
  { code: '001', name: 'Açaí', unit: 't', family: 'mass' },
  { code: '002', name: 'Castanha-do-pará', unit: 't', family: 'mass' },
  { code: '003', name: 'Madeira em tora', unit: 'm³', family: 'volume' },
];

// A tiny 2-município IBGE mesh so the geografia cascade lights up the sub-UF columns
// (both parallel divisions) and the município leaf for a municipio-level banco.
const MESH = [
  {
    cityCode: '1501402', cityName: 'Belém', uf: 'PA',
    meso: { code: '1506', name: 'Metropolitana de Belém' },
    micro: { code: '15014', name: 'Belém' },
    intermediaria: { code: '1501', name: 'Belém (int.)' },
    imediata: { code: '150001', name: 'Belém (imed.)' },
  },
  {
    cityCode: '3550308', cityName: 'São Paulo', uf: 'SP',
    meso: { code: '3515', name: 'Metropolitana de São Paulo' },
    micro: { code: '35061', name: 'São Paulo' },
    intermediaria: { code: '3501', name: 'São Paulo (int.)' },
    imediata: { code: '350001', name: 'São Paulo (imed.)' },
  },
];

// Banco registry shapes (mirrors FilterTriggerBar.test.jsx / csvExport.cov.test.js).
const BANCOS = {
  ibge_pevs: {
    id: 'ibge_pevs', short: 'IBGE PEVS', status: 'live', baseCurrency: 'BRL',
    provides: ['product', 'geo', 'quality'], maturityDate: null,
  },
  mdic_comex: {
    id: 'mdic_comex', short: 'MDIC COMEX', status: 'live', baseCurrency: 'USD',
    provides: ['product', 'flow', 'geo', 'quality'], maturityDate: null,
  },
  sefaz_nf: {
    id: 'sefaz_nf', short: 'SEFAZ NF-e', status: 'pending', baseCurrency: 'BRL',
    provides: ['product', 'geo'], maturityDate: '2026-12',
  },
};

const SCHEMA = {
  ibge_pevs: {
    dims: [{ id: 'prod', type: 'products', label: 'Produtos · PEVS', tier: 'shared' }],
  },
  sefaz_nf: {
    dims: [
      { id: 'prod', type: 'products', label: 'Produtos · NF-e', tier: 'shared',
        column: 'product_code', hint: 'Produtos da nota', type2: 'x' },
      { id: 'uf', type: 'multi', label: 'UF de origem', tier: 'universal',
        column: 'uf_origem', hint: 'Estado emissor', options: ['SP', 'MG'] },
    ],
  },
};

function stubRegistry(opts = {}) {
  const { geoLevel = 'municipio', mesh = MESH } = opts;
  window.QUALITY_FLAGS = QUALITY_FLAGS;
  window.PRODUCTS = PRODUCTS;
  window.bancoById = (id) => BANCOS[id] || BANCOS.ibge_pevs;
  window.filterSchemaFor = (id) => SCHEMA[id] || SCHEMA.ibge_pevs;
  window.geoLevelFor = (id) => (id === 'mdic_comex' ? 'uf' : geoLevel);
  window.bancoTable = (id) => `gold_${id}_production`;
  window.flowOptionsFor = (id) =>
    id === 'mdic_comex'
      ? [{ value: 'export', label: 'Exportação' }, { value: 'import', label: 'Importação' }]
      : null;
  window.geoMesh = () => mesh;
  window.snapshotFor = () => ({
    products: PRODUCTS,
    overviewTS: [{ y: 1997 }, { y: 2024 }],
  });
  window.dataStore = {
    get: () => ({ products: PRODUCTS, overviewTS: [{ y: 1997 }, { y: 2024 }] }),
    meta: () => ({ table: 'gold_pevs_production' }),
  };
  window.CURRENCY_FX = { BRL: { symbol: 'R$' }, USD: { symbol: 'US$' } };
  window.TIER_LABEL = { universal: 'Universal', shared: 'Compartilhada', specific: 'Específica do banco' };
}

let FilterMenu;

beforeAll(async () => {
  // QUALITY_FLAGS must exist before the module body runs (line 68 reads it once).
  window.QUALITY_FLAGS = QUALITY_FLAGS;
  await import('./chipFmt.js'); // window.chipFmt + window.fmtCompactValue
  await import('./filterSummary.js'); // window.filterSummary
  await import('./useGeoCascade.js'); // window.useGeoCascade
  await import('./FilterMenu.jsx'); // window.FilterMenu
  FilterMenu = window.FilterMenu;
});

beforeEach(() => {
  stubRegistry();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('FilterMenu — visibility gate', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <FilterMenu open={false} banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    expect(container.querySelector('.fm-backdrop')).toBeNull();
  });
});

describe('FilterMenu — live render (ibge_pevs: product + geo + quality)', () => {
  it('renders the header, every gated section and the three footer buttons', () => {
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    // Modal chrome.
    expect(container.querySelector('.fm-modal')).toBeTruthy();
    expect(container.querySelector('#fm-title').textContent).toBe('Editar filtros');
    expect(container.textContent).toContain('IBGE PEVS');

    // Sections: produtos (01), período (02), geografia (03), qualidade (04).
    const labels = [...container.querySelectorAll('.fm-section-label')].map((n) => n.textContent);
    expect(labels.some((l) => l.includes('Produtos'))).toBe(true);
    expect(labels.some((l) => l.includes('Período'))).toBe(true);
    expect(labels.some((l) => l.includes('Geografia'))).toBe(true);
    expect(labels.some((l) => l.includes('Qualidade'))).toBe(true);

    // Production banco → NO Fluxo section.
    expect(container.textContent).not.toContain('todos os fluxos');

    // The footer's three actions.
    expect(container.querySelector('.btn-ghost').textContent).toContain('Restaurar padrão');
    expect(container.querySelector('.btn-secondary').textContent).toContain('Cancelar');
    expect(container.querySelector('.btn-primary').textContent).toContain('Aplicar filtros');
  });

  it('lists every product as a checkbox, defaulting all selected', () => {
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    expect(container.textContent).toContain('Açaí');
    expect(container.textContent).toContain('Castanha-do-pará');
    // "3 de 3 selecionados" in the produtos section header.
    expect(container.textContent).toContain('de 3 selecionados');
  });

  it('renders the geografia cascade columns (nação ▸ região ▸ UF ▸ sub-UF ▸ município)', () => {
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    const titles = [...container.querySelectorAll('.fm-geo-title')].map((n) => n.textContent);
    expect(titles).toContain('Nações');
    expect(titles).toContain('Regiões');
    expect(titles).toContain('Estados');
    expect(titles).toContain('Mesorregiões');
    expect(titles).toContain('Municípios');
    // The mesh footer reports the município universe (2 in the fixture).
    expect(container.textContent).toContain('Malha IBGE: 2 municípios');
  });

  it('renders the 9 quality flags with their pt-BR labels', () => {
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    expect(container.textContent).toContain('Normais');
    expect(container.textContent).toContain('Incompleto');
    expect(container.textContent).toContain('Quantidade problemática (provável erro)');
    expect(container.textContent).toContain('de 9 selecionadas');
  });
});

describe('FilterMenu — checkbox toggles', () => {
  it('unchecks a product → the selected count drops, and apply emits the narrowed basket', () => {
    const onApply = vi.fn();
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={onApply} />
    );
    // The first checkbox inside the produtos grid.
    const grid = container.querySelector('.fm-grid');
    const firstBox = grid.querySelector('input[type="checkbox"]');
    expect(firstBox.checked).toBe(true);
    fireEvent.click(firstBox);
    expect(firstBox.checked).toBe(false);
    expect(container.textContent).toContain('2 de 3 selecionados');

    fireEvent.click(container.querySelector('.btn-primary'));
    expect(onApply).toHaveBeenCalledTimes(1);
    const payload = onApply.mock.calls[0][0];
    expect(payload.basket).toHaveLength(2); // one product dropped
    expect(payload.flags).toHaveLength(9); // quality untouched → all flags
  });

  it('"Limpar" in the produtos bulk row clears the (search-filtered) selection', () => {
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    // The produtos section is the first .fm-section with a .fm-grid.
    const prodSection = container.querySelector('.fm-section');
    const limpar = [...prodSection.querySelectorAll('.fm-bulk button')].find(
      (b) => b.textContent === 'Limpar'
    );
    fireEvent.click(limpar);
    expect(container.textContent).toContain('0 de 3 selecionados');
  });

  it('toggles a quality flag off', () => {
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    // The quality section is the one mentioning data_quality_flag.
    const qualSection = [...container.querySelectorAll('.fm-section')].find((s) =>
      s.textContent.includes('data_quality_flag')
    );
    const box = qualSection.querySelector('.fm-grid input[type="checkbox"]');
    expect(box.checked).toBe(true);
    fireEvent.click(box);
    expect(box.checked).toBe(false);
    expect(qualSection.textContent).toContain('de 9 selecionadas');
  });
});

describe('FilterMenu — período', () => {
  it('clicking a quick-range chip activates it and updates the dates', () => {
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    const quick = container.querySelector('.fm-quick');
    const tenYears = [...quick.querySelectorAll('button')].find((b) =>
      b.textContent.includes('10 anos')
    );
    expect(tenYears).toBeTruthy();
    fireEvent.click(tenYears);
    expect(tenYears.classList.contains('on')).toBe(true);
    // 10-year window off the 2024 upper bound → 2015-01 in the start input.
    const start = container.querySelector('#fm-start');
    expect(start.value).toBe('2015-01');
  });

  it('typing a start date later than the end clamps the end forward', () => {
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    const start = container.querySelector('#fm-start');
    const end = container.querySelector('#fm-end');
    fireEvent.change(start, { target: { value: '2030-06' } });
    expect(end.value).toBe('2030-06'); // clamped to keep start ≤ end
  });
});

describe('FilterMenu — fluxo (trade banco)', () => {
  it('renders the Fluxo segment for a trade banco and lets the user pick a direction', () => {
    const onApply = vi.fn();
    const { container } = render(
      <FilterMenu open banco="mdic_comex" value={null} onClose={() => {}} onApply={onApply} />
    );
    // COMEX provides flow → the segmented control is present.
    const seg = container.querySelector('.seg');
    expect(seg).toBeTruthy();
    const exportBtn = [...seg.querySelectorAll('.seg-opt')].find((b) => b.textContent === 'Exportação');
    expect(exportBtn).toBeTruthy();
    fireEvent.click(exportBtn);
    expect(exportBtn.classList.contains('on')).toBe(true);

    // COMEX is a UF-level banco (geoLevel='uf') → no Municípios column.
    const titles = [...container.querySelectorAll('.fm-geo-title')].map((n) => n.textContent);
    expect(titles).not.toContain('Municípios');

    fireEvent.click(container.querySelector('.btn-primary'));
    expect(onApply.mock.calls[0][0].flow).toBe('export');
  });
});

describe('FilterMenu — footer actions', () => {
  it('"Aplicar filtros" emits a chip summary + raw filter and closes', () => {
    const onApply = vi.fn();
    const onClose = vi.fn();
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={onClose} onApply={onApply} />
    );
    fireEvent.click(container.querySelector('.btn-primary'));
    expect(onApply).toHaveBeenCalledTimes(1);
    const payload = onApply.mock.calls[0][0];
    // Display chips.
    expect(payload.products).toContain('Todos (3)');
    expect(payload.quality).toContain('Todas (9)');
    expect(payload.period).toBe('1997–2024');
    // Raw filter dims present.
    expect(Array.isArray(payload.basket)).toBe(true);
    expect(payload.startDate).toBeTruthy();
    expect(onClose).toHaveBeenCalled();
  });

  it('"Cancelar" closes without applying', () => {
    const onApply = vi.fn();
    const onClose = vi.fn();
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={onClose} onApply={onApply} />
    );
    fireEvent.click(container.querySelector('.btn-secondary'));
    expect(onClose).toHaveBeenCalled();
    expect(onApply).not.toHaveBeenCalled();
  });

  it('"Restaurar padrão" resets a narrowed selection back to all-selected', () => {
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={() => {}} onApply={() => {}} />
    );
    // Narrow the basket first.
    const firstBox = container.querySelector('.fm-grid input[type="checkbox"]');
    fireEvent.click(firstBox);
    expect(container.textContent).toContain('2 de 3 selecionados');
    // Restore.
    fireEvent.click(container.querySelector('.btn-ghost'));
    expect(container.textContent).toContain('3 de 3 selecionados');
  });

  it('clicking the backdrop and the × close the modal', () => {
    const onClose = vi.fn();
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={onClose} onApply={() => {}} />
    );
    fireEvent.click(container.querySelector('.fm-close'));
    fireEvent.click(container.querySelector('.fm-backdrop'));
    expect(onClose.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('does NOT close when the modal body itself is clicked (stopPropagation)', () => {
    const onClose = vi.fn();
    const { container } = render(
      <FilterMenu open banco="ibge_pevs" value={null} onClose={onClose} onApply={() => {}} />
    );
    fireEvent.click(container.querySelector('.fm-modal'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('closes on the Escape key', () => {
    const onClose = vi.fn();
    render(<FilterMenu open banco="ibge_pevs" value={null} onClose={onClose} onApply={() => {}} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });
});

describe('FilterMenu — seeding from an applied value (deep link / prior apply)', () => {
  it('seeds the draft from value.basket / value.flags so it mirrors the live filter', () => {
    const { container } = render(
      <FilterMenu
        open
        banco="ibge_pevs"
        value={{ basket: ['001'], flags: ['OK', 'INCOMPLETE'], startDate: '2010-01', endDate: '2020-12' }}
        onClose={() => {}}
        onApply={() => {}}
      />
    );
    // Only one product pre-selected.
    expect(container.textContent).toContain('1 de 3 selecionados');
    // Two flags pre-selected.
    expect(container.textContent).toContain('2 de 9 selecionadas');
    // Custom date range restored.
    expect(container.querySelector('#fm-start').value).toBe('2010-01');
    expect(container.querySelector('#fm-end').value).toBe('2020-12');
  });
});

describe('FilterMenu — "soon" banco preview', () => {
  it('renders the read-only dimension preview (no functional filter sections)', () => {
    const { container } = render(
      <FilterMenu open banco="sefaz_nf" value={null} onClose={() => {}} onApply={() => {}} />
    );
    expect(container.querySelector('#fm-title').textContent).toBe('Dimensões filtráveis');
    expect(container.querySelector('.fm-preview')).toBeTruthy();
    expect(container.textContent).toContain('Em breve');
    // The schema dims surface read-only (label + column).
    expect(container.textContent).toContain('UF de origem');
    expect(container.textContent).toContain('uf_origem');
    // The preview footer has a single "Entendi" action, not the apply/cancel trio.
    expect(container.querySelector('.fm-preview .btn-primary').textContent).toContain('Entendi');
    expect(container.querySelector('.fm-foot .btn-ghost')).toBeNull();
  });

  it('the "Entendi" button closes the preview', () => {
    const onClose = vi.fn();
    const { container } = render(
      <FilterMenu open banco="sefaz_nf" value={null} onClose={onClose} onApply={() => {}} />
    );
    fireEvent.click(container.querySelector('.fm-preview .btn-primary'));
    expect(onClose).toHaveBeenCalled();
  });
});
