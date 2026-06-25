// ViewCadastroCommodities — the Curadoria (catalog) editor: what ENTERS and EXITS the
// dashboard. Lists the commodity catalog grouped by Agrupamento (the cross-source
// concept), and lets an AUTHORIZED researcher edit the lifecycle (Ciclo de Vida = in/out)
// + attributes, add a commodity, or remove one — through /api/catalog/* (the append-only,
// IAP-attributed writer; removal is a non-destructive tombstone). The editable successor
// to the commodity_crosswalk seed. Self-contained (its own fetch + state), like ViewDados.
//
// Authorization is enforced server-side (the per-catalog allowlist → 403); a 400 means a
// bad key / over-length / overlapping prefix. We surface both honestly rather than hiding
// the failure.

const { useState: useCcState, useEffect: useCcEffect } = React;

const _CC_CICLO = [
  { v: 'Fazer Ingestão e deixar disponível', label: 'Ingerir e exibir' },
  { v: 'Fazer Ingestão mas deixar indisponível', label: 'Ingerir, mas ocultar' },
];
// Catalog `banco` is the cross-source SOURCE TOKEN; show the friendly banco name.
const _CC_BANCOS = [
  { v: 'pevs', label: 'IBGE PEVS' },
  { v: 'pam', label: 'IBGE PAM' },
  { v: 'ppm', label: 'IBGE PPM' },
  { v: 'comex', label: 'MDIC COMEX' },
  { v: 'comtrade', label: 'UN COMTRADE' },
];
const _CC_BANCO_LABEL = Object.fromEntries(_CC_BANCOS.map((b) => [b.v, b.label]));
// The Níveis de Industrialização vocabulary (datalist suggestions; the field is free text).
const _CC_INDUST = [
  'Commodity Pura', 'Commodity Higienizada', 'Commodity Acondicionada',
  'Commodity Consumivel', 'Commodity Subproduto', 'Manufaturado Artesanal',
  'Manufaturado Industrial', 'Manufaturado Especializado',
];

const _CC_EMPTY_DRAFT = {
  codigo_commodity: '', banco: 'comex', agrupamento: '', code_prefix: '',
  industrializacao: '', descricao_commodity: '', ciclo_de_vida: _CC_CICLO[0].v,
};

function _ccCicloShort(v) {
  const hit = _CC_CICLO.find((c) => c.v === v);
  return hit ? hit.label : (v || '—');
}

function ViewCadastroCommodities() {
  const [data, setData] = useCcState({ entries: [], by_agrupamento: [], loading: true, error: null });
  const [status, setStatus] = useCcState(null); // { kind: 'ok' | 'err', msg }
  const [busy, setBusy] = useCcState(false);
  const [draft, setDraft] = useCcState({ ..._CC_EMPTY_DRAFT });
  const [showAdd, setShowAdd] = useCcState(false);
  const [orphans, setOrphans] = useCcState([]);

  const load = () => {
    setData((d) => ({ ...d, loading: true, error: null }));
    fetch('/api/catalog/entries')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setData({ entries: d.entries || [], by_agrupamento: d.by_agrupamento || [], loading: false, error: null }))
      .catch((e) => setData({ entries: [], by_agrupamento: [], loading: false, error: String(e.message || e) }));
    // Orphans (removed from the catalog, Gold data lingering) — shown as Descontinuados.
    fetch('/api/catalog/orphans')
      .then((r) => (r.ok ? r.json() : { orphans: [] }))
      .then((d) => setOrphans(d.orphans || []))
      .catch(() => setOrphans([]));
  };
  useCcEffect(load, []);

  // POST a write; throw the server's pt-BR error on a non-2xx so callers can surface it.
  const post = async (path, body) => {
    const r = await fetch(path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (!r.ok) {
      const b = await r.json().catch(() => null);
      throw new Error((b && b.error) || `HTTP ${r.status}`);
    }
    return r.json();
  };

  const run = async (fn, okMsg) => {
    setBusy(true); setStatus(null);
    try {
      await fn();
      setStatus({ kind: 'ok', msg: okMsg });
      load();
    } catch (e) {
      setStatus({ kind: 'err', msg: String(e.message || e) });
    } finally {
      setBusy(false);
    }
  };

  const saveEntry = (entry) =>
    run(() => post('/api/catalog/entry', entry), `Commodity ${entry.codigo_commodity} salva.`);

  const removeEntry = (e) => {
    if (!window.confirm(`Remover ${e.codigo_commodity} (${_CC_BANCO_LABEL[e.banco] || e.banco}) do cadastro? Os dados já baixados ficam órfãos (não são apagados automaticamente).`)) return;
    run(() => post('/api/catalog/entry/remove', { codigo_commodity: e.codigo_commodity, banco: e.banco }),
      `Commodity ${e.codigo_commodity} marcada como descontinuada.`);
  };

  // Per-Agrupamento lifecycle (the lead's edit grain): set Ciclo de Vida for every member.
  const setCicloForAgrupamento = (agrupamento, ciclo) => {
    const members = data.entries.filter((e) => (e.agrupamento || '—') === agrupamento);
    run(async () => {
      for (const m of members) {
        await post('/api/catalog/entry', { ...m, ciclo_de_vida: ciclo });
      }
    }, `Ciclo de vida de "${agrupamento}" atualizado (${members.length}).`);
  };

  const submitAdd = () => {
    if (!draft.codigo_commodity || !draft.banco) {
      setStatus({ kind: 'err', msg: 'Código da commodity e banco são obrigatórios (formam a chave).' });
      return;
    }
    saveEntry({ ...draft });
    setDraft({ ..._CC_EMPTY_DRAFT });
    setShowAdd(false);
  };

  // Group entries by agrupamento for the per-concept editing grain.
  const groups = {};
  for (const e of data.entries) (groups[e.agrupamento || '—'] = groups[e.agrupamento || '—'] || []).push(e);
  const groupNames = Object.keys(groups).sort((a, b) => a.localeCompare(b, 'pt-BR'));
  const agrupamentos = [...new Set(data.entries.map((e) => e.agrupamento).filter(Boolean))].sort();

  return (
    <>
      <div className="card subtle" style={{ marginBottom: 12 }}>
        <p className="caption" style={{ margin: 0 }}>
          Este é o <strong>cadastro de commodities</strong> — a fonte única de verdade do que entra
          e sai do dashboard. Cada commodity é identificada pelo par <code>(código, banco)</code>.
          O <strong>Ciclo de Vida</strong> controla se a commodity é exibida; <strong>remover</strong> uma
          commodity a marca como descontinuada (os dados já baixados ficam órfãos e só são apagados por
          um humano, nunca automaticamente). Edições exigem autorização e ficam registradas com seu e-mail.
        </p>
      </div>

      {status && (
        <p className="caption" role="status"
           style={{ padding: '8px 10px', borderRadius: 6, marginBottom: 10,
                    background: status.kind === 'ok' ? 'var(--ok-bg, #e8f5e9)' : 'var(--err-bg, #fdecea)',
                    color: status.kind === 'ok' ? 'var(--ok, #1b7f3b)' : 'var(--err, #b71c1c)' }}>
          {status.msg}
        </p>
      )}

      {orphans.length > 0 && (
        <div className="card" style={{ marginBottom: 12, borderLeft: '4px solid var(--err, #b71c1c)' }}>
          <window.SectionHeader
            overline="Descontinuados"
            title={`${orphans.length.toLocaleString('pt-BR')} órfã(s) — aguardando remoção`}
          />
          <p className="caption" style={{ margin: '0 2px 8px' }}>
            Removidas do cadastro, mas os dados já baixados continuam no Gold. Serão removidos
            por um operador (com backup), <strong>nunca automaticamente</strong>.
          </p>
          <div className="dt-wrap">
            <table className="dt-table">
              <thead>
                <tr><th>Agrupamento</th><th>Banco</th><th>Código</th><th>Marcado em</th></tr>
              </thead>
              <tbody>
                {orphans.map((o) => (
                  <tr key={o.banco + '|' + o.codigo_commodity}>
                    <td>{o.agrupamento || '—'}</td>
                    <td>{_CC_BANCO_LABEL[o.banco] || o.banco}</td>
                    <td className="tnum">{o.codigo_commodity}</td>
                    <td className="caption">{o.flagged_at ? String(o.flagged_at).slice(0, 10) : 'detectado agora'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="pp-selector" style={{ marginBottom: 8 }}>
        <span className="pp-selector-label">
          {data.entries.length.toLocaleString('pt-BR')} commodities · {groupNames.length} agrupamentos
        </span>
        <button type="button" className="seg-opt" onClick={() => setShowAdd((v) => !v)} disabled={busy}>
          {showAdd ? 'Cancelar' : '+ Adicionar commodity'}
        </button>
      </div>

      {showAdd && (
        <div className="card" style={{ marginBottom: 12 }}>
          <window.SectionHeader overline="Cadastro" title="Adicionar commodity" />
          <div className="cc-form" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            <label className="cc-field">Código da commodity (ou prefixo)
              <input type="text" value={draft.codigo_commodity}
                     onChange={(e) => setDraft((d) => ({ ...d, codigo_commodity: e.target.value }))} />
            </label>
            <label className="cc-field">Banco (fonte)
              <select value={draft.banco} onChange={(e) => setDraft((d) => ({ ...d, banco: e.target.value }))}>
                {_CC_BANCOS.map((b) => <option key={b.v} value={b.v}>{b.label}</option>)}
              </select>
            </label>
            <label className="cc-field">Agrupamento (conceito)
              <input type="text" list="cc-agrupamentos" value={draft.agrupamento}
                     onChange={(e) => setDraft((d) => ({ ...d, agrupamento: e.target.value }))} />
              <datalist id="cc-agrupamentos">{agrupamentos.map((a) => <option key={a} value={a} />)}</datalist>
            </label>
            <label className="cc-field">Prefixo de código <small className="pc-cap">(vazio = o próprio código)</small>
              <input type="text" value={draft.code_prefix} placeholder={draft.codigo_commodity}
                     onChange={(e) => setDraft((d) => ({ ...d, code_prefix: e.target.value }))} />
            </label>
            <label className="cc-field">Industrialização
              <input type="text" list="cc-indust" value={draft.industrializacao}
                     onChange={(e) => setDraft((d) => ({ ...d, industrializacao: e.target.value }))} />
              <datalist id="cc-indust">{_CC_INDUST.map((i) => <option key={i} value={i} />)}</datalist>
            </label>
            <label className="cc-field">Ciclo de vida
              <select value={draft.ciclo_de_vida} onChange={(e) => setDraft((d) => ({ ...d, ciclo_de_vida: e.target.value }))}>
                {_CC_CICLO.map((c) => <option key={c.v} value={c.v}>{c.label}</option>)}
              </select>
            </label>
          </div>
          <div style={{ marginTop: 10 }}>
            <button type="button" className="btn-primary" onClick={submitAdd} disabled={busy}>
              {busy ? 'Salvando…' : 'Salvar commodity'}
            </button>
          </div>
        </div>
      )}

      {data.error ? (
        <p className="caption" style={{ padding: '20px 4px', color: 'var(--err)' }}>Erro ao carregar: {data.error}</p>
      ) : data.loading ? (
        <p className="caption" style={{ padding: '40px 4px', textAlign: 'center' }}>Carregando cadastro…</p>
      ) : !data.entries.length ? (
        <p className="caption" style={{ padding: '40px 4px', textAlign: 'center' }}>
          Nenhuma commodity cadastrada ainda. Use “+ Adicionar commodity”.
        </p>
      ) : (
        groupNames.map((g) => (
          <div className="card" key={g} style={{ marginBottom: 10 }}>
            <div className="cc-group-head" style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <strong style={{ flex: 1 }}>{g} <small className="pc-cap">({groups[g].length})</small></strong>
              <label className="caption" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                Ciclo de vida do agrupamento:
                <select disabled={busy} defaultValue=""
                        onChange={(e) => { if (e.target.value) setCicloForAgrupamento(g, e.target.value); e.target.value = ''; }}>
                  <option value="">aplicar a todos…</option>
                  {_CC_CICLO.map((c) => <option key={c.v} value={c.v}>{c.label}</option>)}
                </select>
              </label>
            </div>
            <div className="dt-wrap">
              <table className="dt-table">
                <thead>
                  <tr>
                    <th>Banco</th><th>Código</th><th>Prefixo</th><th>Industrialização</th><th>Ciclo de vida</th><th aria-label="ações"></th>
                  </tr>
                </thead>
                <tbody>
                  {groups[g].map((e) => (
                    <tr key={e.banco + '|' + e.codigo_commodity}>
                      <td>{_CC_BANCO_LABEL[e.banco] || e.banco}</td>
                      <td className="tnum">{e.codigo_commodity}</td>
                      <td className="tnum">{e.code_prefix}</td>
                      <td>{e.industrializacao || <span className="dt-null">—</span>}</td>
                      <td>
                        <select disabled={busy} value={e.ciclo_de_vida || ''}
                                title={e.ciclo_de_vida || ''}
                                onChange={(ev) => saveEntry({ ...e, ciclo_de_vida: ev.target.value })}>
                          {!_CC_CICLO.some((c) => c.v === e.ciclo_de_vida) && (
                            <option value={e.ciclo_de_vida || ''}>{_ccCicloShort(e.ciclo_de_vida)}</option>
                          )}
                          {_CC_CICLO.map((c) => <option key={c.v} value={c.v}>{c.label}</option>)}
                        </select>
                      </td>
                      <td>
                        <button type="button" className="cc-remove" disabled={busy}
                                title="Remover (marca como descontinuada)" aria-label={`Remover ${e.codigo_commodity}`}
                                onClick={() => removeEntry(e)}
                                style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--err, #b71c1c)' }}>
                          🗑
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </>
  );
}

window.ViewCadastroCommodities = ViewCadastroCommodities;
