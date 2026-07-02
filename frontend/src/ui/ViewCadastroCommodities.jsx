// ViewCadastroCommodities — the Curadoria (catalog) editor: what ENTERS and EXITS the
// dashboard. AGRUPAMENTOS (groups) are now a FIRST-CLASS registry — create (incl. empty),
// rename and delete (only when empty) — and each commodity (código+banco, code_prefix,
// ciclo de vida = in/out) points at one group and can be MOVED between them. Each code
// also shows its ORIGINAL source description. Writes go through /api/catalog/* (append-only,
// IAP-attributed; removal is a non-destructive tombstone). Self-contained (own fetch+state).
//
// Authorization is enforced server-side (403); a 400 = bad key / overlapping prefix /
// duplicate or non-empty group. We surface both honestly rather than hiding the failure.

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
const _CC_EMPTY_DRAFT = {
  codigo_commodity: '', banco: 'comex', commodity_id: '', code_prefix: '',
  descricao_commodity: '', ciclo_de_vida: _CC_CICLO[0].v,
};

function _ccCicloShort(v) {
  const hit = _CC_CICLO.find((c) => c.v === v);
  return hit ? hit.label : (v || '—');
}

function ViewCadastroCommodities() {
  const [data, setData] = useCcState({ entries: [], groups: [], loading: true, error: null });
  const [status, setStatus] = useCcState(null); // { kind: 'ok' | 'err', msg }
  const [busy, setBusy] = useCcState(false);
  const [draft, setDraft] = useCcState({ ..._CC_EMPTY_DRAFT });
  const [showAdd, setShowAdd] = useCcState(false);
  const [orphans, setOrphans] = useCcState([]);
  const [newGroup, setNewGroup] = useCcState('');

  const load = () => {
    setData((d) => ({ ...d, loading: true, error: null }));
    Promise.all([
      fetch('/api/catalog/entries').then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))),
      fetch('/api/catalog/groups').then((r) => (r.ok ? r.json() : { groups: [] })),
    ])
      .then(([e, g]) => setData({ entries: e.entries || [], groups: g.groups || [], loading: false, error: null }))
      .catch((err) => setData({ entries: [], groups: [], loading: false, error: String(err.message || err) }));
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
    } catch (e) {
      setStatus({ kind: 'err', msg: String(e.message || e) });
    } finally {
      // Always re-sync to the PERSISTED state — a multi-write op that fails midway has
      // already committed some rows; reloading only on success would show stale values.
      load();
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

  // Move a commodity to a DIFFERENT agrupamento (membership change) — re-upserts with the
  // target group's id + name, so it re-groups on reload.
  const moveEntry = (e, groupId) => {
    const g = data.groups.find((x) => x.group_id === groupId);
    if (!g || g.group_id === e.commodity_id) return;
    saveEntry({ ...e, commodity_id: g.group_id, agrupamento: g.group_name });
  };

  // ── Agrupamento (group) management — the first-class registry ──────────────────
  const createGroup = () => {
    const name = newGroup.trim();
    if (!name) { setStatus({ kind: 'err', msg: 'Informe o nome do novo agrupamento.' }); return; }
    run(() => post('/api/catalog/group', { group_name: name }), `Agrupamento "${name}" criado.`);
    setNewGroup('');
  };
  const renameGroup = (g) => {
    const name = window.prompt(`Renomear o agrupamento "${g.group_name}":`, g.group_name);
    if (name == null) return;
    const trimmed = name.trim();
    if (!trimmed || trimmed === g.group_name) return;
    run(() => post('/api/catalog/group', { group_id: g.group_id, group_name: trimmed }),
      `Agrupamento renomeado para "${trimmed}".`);
  };
  const deleteGroup = (g) => {
    if (g.n_members > 0) return; // the button is disabled; guard anyway
    if (!window.confirm(`Excluir o agrupamento vazio "${g.group_name}"?`)) return;
    run(() => post('/api/catalog/group/remove', { group_id: g.group_id }),
      `Agrupamento "${g.group_name}" excluído.`);
  };

  // Per-Agrupamento lifecycle (the lead's edit grain): set Ciclo de Vida for every member.
  const setCicloForGroup = (g, ciclo) => {
    const members = data.entries.filter((e) => e.commodity_id === g.group_id);
    run(async () => {
      let done = 0;
      try {
        for (const m of members) {
          await post('/api/catalog/entry', { ...m, ciclo_de_vida: ciclo });
          done += 1;
        }
      } catch (e) {
        throw new Error(`${String(e.message || e)} — aplicado a ${done}/${members.length} antes da falha.`);
      }
    }, `Ciclo de vida de "${g.group_name}" atualizado (${members.length}).`);
  };

  const submitAdd = () => {
    if (!draft.codigo_commodity || !draft.banco) {
      setStatus({ kind: 'err', msg: 'Código da commodity e banco são obrigatórios (formam a chave).' });
      return;
    }
    const g = data.groups.find((x) => x.group_id === draft.commodity_id);
    if (!g) {
      setStatus({ kind: 'err', msg: 'Escolha um agrupamento (ou crie um novo acima).' });
      return;
    }
    saveEntry({ ...draft, agrupamento: g.group_name });
    setDraft({ ..._CC_EMPTY_DRAFT });
    setShowAdd(false);
  };

  // Registry groups, sorted; each rendered as a card with its members.
  const groupsSorted = [...data.groups].sort((a, b) => a.group_name.localeCompare(b.group_name, 'pt-BR'));
  const membersOf = (gid) => data.entries.filter((e) => e.commodity_id === gid);
  // Entries pointing at a group not in the registry (legacy / pre-migration) → a fallback
  // bucket so nothing is hidden. After the seed migration this is empty.
  const knownIds = new Set(data.groups.map((g) => g.group_id));
  const strayEntries = data.entries.filter((e) => !knownIds.has(e.commodity_id));

  const GroupSelect = ({ value, onChange, placeholder }) => (
    <select value={value || ''} disabled={busy}
            onChange={(ev) => onChange(ev.target.value)} className="cc-group-select">
      {placeholder && <option value="">{placeholder}</option>}
      {groupsSorted.map((g) => <option key={g.group_id} value={g.group_id}>{g.group_name}</option>)}
    </select>
  );

  const memberRows = (members) => (
    <div className="dt-wrap">
      <table className="dt-table">
        <thead>
          <tr>
            <th>Banco</th><th>Código</th><th>Prefixo</th><th>Descrição (fonte)</th>
            <th>Agrupamento</th><th>Ciclo de vida</th><th aria-label="ações"></th>
          </tr>
        </thead>
        <tbody>
          {members.map((e) => (
            <tr key={e.banco + '|' + e.codigo_commodity}>
              <td>{_CC_BANCO_LABEL[e.banco] || e.banco}</td>
              <td className="tnum">{e.codigo_commodity}</td>
              <td className="tnum">{e.code_prefix}</td>
              <td>{e.descricao_fonte || <span className="dt-null">—</span>}</td>
              <td>
                <GroupSelect value={e.commodity_id} onChange={(gid) => moveEntry(e, gid)} />
              </td>
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
  );

  return (
    <>
      <div className="card subtle" style={{ marginBottom: 12 }}>
        <p className="caption" style={{ margin: 0 }}>
          Este é o <strong>cadastro de commodities</strong> — a fonte única de verdade do que entra
          e sai do dashboard. Cada commodity é identificada por <code>(código, banco)</code> e pertence a
          um <strong>agrupamento</strong> (o conceito que a unifica entre fontes). Agrupamentos são criados,
          renomeados e excluídos aqui; o <strong>Ciclo de Vida</strong> controla a exibição; <strong>remover</strong> uma
          commodity a marca como descontinuada (os dados já baixados ficam órfãos, apagados só por um humano).
          Edições exigem autorização e ficam registradas com seu e-mail.
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

      <div className="pp-selector" style={{ marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
        <span className="pp-selector-label">
          {data.entries.length.toLocaleString('pt-BR')} commodities · {data.groups.length} agrupamentos
        </span>
        <label className="caption" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          Novo agrupamento:
          <input type="text" value={newGroup} placeholder="Ex.: Castanha"
                 onChange={(e) => setNewGroup(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') createGroup(); }} />
          <button type="button" className="seg-opt" onClick={createGroup} disabled={busy || !newGroup.trim()}>
            + Criar
          </button>
        </label>
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
            <label className="cc-field">Agrupamento
              <GroupSelect value={draft.commodity_id}
                           onChange={(gid) => setDraft((d) => ({ ...d, commodity_id: gid }))}
                           placeholder={data.groups.length ? 'Escolha um agrupamento…' : 'Crie um agrupamento primeiro'} />
            </label>
            <label className="cc-field">Prefixo de código <small className="pc-cap">(vazio = o próprio código)</small>
              <input type="text" value={draft.code_prefix} placeholder={draft.codigo_commodity}
                     onChange={(e) => setDraft((d) => ({ ...d, code_prefix: e.target.value }))} />
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
      ) : !data.groups.length && !data.entries.length ? (
        <p className="caption" style={{ padding: '40px 4px', textAlign: 'center' }}>
          Nenhum agrupamento ainda. Crie um em “Novo agrupamento”, depois use “+ Adicionar commodity”.
        </p>
      ) : (
        <>
          {groupsSorted.map((g) => {
            const members = membersOf(g.group_id);
            return (
              <div className="card" key={g.group_id} style={{ marginBottom: 10 }}>
                <div className="cc-group-head" style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
                  <strong style={{ flex: 1, minWidth: 160 }}>{g.group_name} <small className="pc-cap">({g.n_members})</small></strong>
                  <button type="button" className="seg-opt" disabled={busy}
                          onClick={() => renameGroup(g)} title="Renomear agrupamento">✎ Renomear</button>
                  <button type="button" className="seg-opt" disabled={busy || g.n_members > 0}
                          onClick={() => deleteGroup(g)}
                          title={g.n_members > 0 ? 'Reatribua ou remova as commodities antes de excluir' : 'Excluir agrupamento vazio'}>
                    🗑 Excluir
                  </button>
                  {g.n_members > 0 && (
                    <label className="caption" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      Ciclo de vida:
                      <select disabled={busy} defaultValue=""
                              onChange={(e) => { if (e.target.value) setCicloForGroup(g, e.target.value); e.target.value = ''; }}>
                        <option value="">aplicar a todos…</option>
                        {_CC_CICLO.map((c) => <option key={c.v} value={c.v}>{c.label}</option>)}
                      </select>
                    </label>
                  )}
                </div>
                {members.length ? memberRows(members) : (
                  <p className="caption" style={{ margin: '0 2px' }}>Agrupamento vazio — adicione commodities ou exclua-o.</p>
                )}
              </div>
            );
          })}

          {strayEntries.length > 0 && (
            <div className="card" style={{ marginBottom: 10, borderLeft: '4px solid var(--warn, #b8860b)' }}>
              <div className="cc-group-head" style={{ marginBottom: 8 }}>
                <strong>Sem agrupamento registrado <small className="pc-cap">({strayEntries.length})</small></strong>
                <p className="caption" style={{ margin: '4px 0 0' }}>
                  Reatribua cada uma a um agrupamento existente na coluna “Agrupamento”.
                </p>
              </div>
              {memberRows(strayEntries)}
            </div>
          )}
        </>
      )}
    </>
  );
}

window.ViewCadastroCommodities = ViewCadastroCommodities;
