// ViewCadastroCommodities — the Curadoria (catalog) editor: what ENTERS and EXITS the
// dashboard. Each commodity is registered by its EXACT source code (código+banco; no
// prefixes), points at one AGRUPAMENTO (first-class registry — create/rename/delete +
// inline move) and carries a Ciclo de Vida (in/out). The add form validates that the code
// REALLY EXISTS in the source (autocomplete from the source's product list; a code that
// doesn't exist is rejected). The catalog table also shows each commodity's current STATE
// in the dashboard (linhas na Gold, período coberto, se tem dados). Writes go through
// /api/catalog/* (append-only, IAP-attributed; removal is a non-destructive tombstone).
//
// Authorization is enforced server-side (403); a 400 = bad key / a code that doesn't exist
// / duplicate or non-empty group. We surface both honestly rather than hiding the failure.

const { useState: useCcState, useEffect: useCcEffect, useMemo: useCcMemo } = React;

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
  codigo_commodity: '', banco: 'comex', commodity_id: '',
  descricao_commodity: '', ciclo_de_vida: _CC_CICLO[0].v,
};

function _ccCicloShort(v) {
  const hit = _CC_CICLO.find((c) => c.v === v);
  return hit ? hit.label : (v || '—');
}
const _ccInt = (n) => (n == null ? '—' : Number(n).toLocaleString('pt-BR'));

// Agrupamento <select>. MODULE-level (stable identity) so React reconciles it across the
// parent's frequent re-renders (every keystroke in "Novo agrupamento", every busy toggle)
// instead of unmounting/remounting the whole subtree. When `value` matches no known group
// (a stray / unassigned entry, or the empty add-form draft) it shows an explicit empty
// option instead of silently defaulting to whatever group sorts first.
function CcGroupSelect({ value, onChange, placeholder, groups, busy }) {
  const known = groups.some((g) => g.group_id === value);
  const empty = placeholder || (known ? null : 'Sem agrupamento — reatribua…');
  return (
    <select value={known ? value : ''} disabled={busy}
            onChange={(ev) => onChange(ev.target.value)} className="cc-group-select">
      {empty != null && <option value="">{empty}</option>}
      {groups.map((g) => <option key={g.group_id} value={g.group_id}>{g.group_name}</option>)}
    </select>
  );
}

function ViewCadastroCommodities() {
  const [data, setData] = useCcState({ entries: [], groups: [], loading: true, error: null });
  const [statusMap, setStatusMap] = useCcState({}); // "banco:code" -> {n_rows, year_start, year_end, has_data}
  const [status, setStatus] = useCcState(null); // { kind: 'ok' | 'err', msg }
  const [busy, setBusy] = useCcState(false);
  const [draft, setDraft] = useCcState({ ..._CC_EMPTY_DRAFT });
  const [showAdd, setShowAdd] = useCcState(false);
  const [orphans, setOrphans] = useCcState([]);
  const [newGroup, setNewGroup] = useCcState('');
  // The source's REAL codes for the add form's banco (autocomplete + existence check).
  const [srcCodes, setSrcCodes] = useCcState({ banco: null, codes: [], loading: false });

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
    // Per-commodity Gold state (linhas + período) — a separate, cheap lazy read.
    fetch('/api/catalog/status')
      .then((r) => (r.ok ? r.json() : { status: {} }))
      .then((d) => setStatusMap(d.status || {}))
      .catch(() => setStatusMap({}));
  };
  useCcEffect(load, []);

  // Fetch the source's real codes whenever the add form is open on a banco (backs the
  // <datalist> autocomplete + the "código existe?" check). Skip if already loaded.
  useCcEffect(() => {
    if (!showAdd || !draft.banco) return;
    if (srcCodes.banco === draft.banco) return;
    setSrcCodes({ banco: draft.banco, codes: [], loading: true });
    fetch('/api/catalog/source-codes?banco=' + encodeURIComponent(draft.banco))
      .then((r) => (r.ok ? r.json() : { codes: [] }))
      .then((d) => setSrcCodes({ banco: draft.banco, codes: d.codes || [], loading: false }))
      .catch(() => setSrcCodes({ banco: draft.banco, codes: [], loading: false }));
  }, [showAdd, draft.banco]);

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
    let ok = false;
    try {
      await fn();
      ok = true;
      setStatus({ kind: 'ok', msg: okMsg });
    } catch (e) {
      setStatus({ kind: 'err', msg: String(e.message || e) });
    } finally {
      // Always re-sync to the PERSISTED state — a multi-write op that fails midway has
      // already committed some rows; reloading only on success would show stale values.
      load();
      setBusy(false);
    }
    return ok; // callers (e.g. the add form) reset/close only on success
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

  // ── Add form: derived validation state ────────────────────────────────────────
  const codeIndex = useCcMemo(() => {
    const m = new Map();
    (srcCodes.codes || []).forEach((c) => m.set(c.code, c.name));
    return m;
  }, [srcCodes]);
  const codeLoadedForBanco = srcCodes.banco === draft.banco && !srcCodes.loading;
  // Only judge the code against the CURRENTLY-loaded banco's codes — otherwise, in the
  // paint right after a banco switch (before the codes reload), a code from the previous
  // banco could flash a false ✓ / enable Salvar.
  const codeMatch = (draft.codigo_commodity && codeLoadedForBanco)
    ? codeIndex.has(draft.codigo_commodity) : null;
  const groupChosen = !!data.groups.find((x) => x.group_id === draft.commodity_id);
  const canSubmit = !!draft.codigo_commodity && groupChosen && codeMatch === true && !busy;

  const submitAdd = async () => {
    if (!draft.codigo_commodity || !draft.banco) {
      setStatus({ kind: 'err', msg: 'Código da commodity e banco são obrigatórios (formam a chave).' });
      return;
    }
    const g = data.groups.find((x) => x.group_id === draft.commodity_id);
    if (!g) {
      setStatus({ kind: 'err', msg: 'Escolha um agrupamento (ou crie um novo acima).' });
      return;
    }
    // Existence guard (the server enforces this too — belt and suspenders).
    if (codeLoadedForBanco && !codeIndex.has(draft.codigo_commodity)) {
      setStatus({ kind: 'err', msg: `O código ${draft.codigo_commodity} não existe em ${_CC_BANCO_LABEL[draft.banco]}. Use um código real da fonte.` });
      return;
    }
    // Reset + close ONLY on a successful write; a 400/403 keeps the form open with the
    // user's input intact so they can correct it.
    const ok = await saveEntry({ ...draft, agrupamento: g.group_name });
    if (ok) {
      setDraft({ ..._CC_EMPTY_DRAFT });
      setShowAdd(false);
    }
  };

  // Registry groups, sorted; each rendered as a card with its members.
  const groupsSorted = [...data.groups].sort((a, b) => a.group_name.localeCompare(b.group_name, 'pt-BR'));
  const membersOf = (gid) => data.entries.filter((e) => e.commodity_id === gid);
  // Entries pointing at a group not in the registry (legacy / pre-migration) → a fallback
  // bucket so nothing is hidden. After the seed migration this is empty.
  const knownIds = new Set(data.groups.map((g) => g.group_id));
  const strayEntries = data.entries.filter((e) => !knownIds.has(e.commodity_id));

  const memberRows = (members) => (
    <div className="dt-wrap cc-dt-wrap">
      <table className="dt-table cc-table">
        <thead>
          <tr>
            <th>Banco</th><th>Código</th><th>Descrição (fonte)</th>
            <th className="num">Linhas</th><th>Período</th><th>Dados</th>
            <th>Agrupamento</th><th>Ciclo de vida</th><th aria-label="ações"></th>
          </tr>
        </thead>
        <tbody>
          {members.map((e) => {
            const st = statusMap[e.banco + ':' + e.codigo_commodity];
            return (
              <tr key={e.banco + '|' + e.codigo_commodity}>
                <td className="cc-cell-title">{_CC_BANCO_LABEL[e.banco] || e.banco}</td>
                <td className="tnum" data-label="Código">{e.codigo_commodity}</td>
                <td data-label="Descrição">{e.descricao_fonte || <span className="dt-null">—</span>}</td>
                <td className="num tnum" data-label="Linhas">{st ? _ccInt(st.n_rows) : '…'}</td>
                <td className="tnum" data-label="Período">{st && st.year_start != null ? `${st.year_start}–${st.year_end}` : '—'}</td>
                <td data-label="Dados">
                  {!st ? <span className="dt-null">…</span>
                    : st.has_data ? <span className="cc-has-data" title="Tem dados na Gold">✓</span>
                    : <span className="cc-no-data" title="Cadastrada, mas sem dados na Gold">sem dados</span>}
                </td>
                <td data-label="Agrupamento">
                  <CcGroupSelect value={e.commodity_id} onChange={(gid) => moveEntry(e, gid)}
                                 groups={groupsSorted} busy={busy} />
                </td>
                <td data-label="Ciclo de vida">
                  <select disabled={busy} value={e.ciclo_de_vida || ''}
                          title={e.ciclo_de_vida || ''}
                          onChange={(ev) => saveEntry({ ...e, ciclo_de_vida: ev.target.value })}>
                    {!_CC_CICLO.some((c) => c.v === e.ciclo_de_vida) && (
                      <option value={e.ciclo_de_vida || ''}>{_ccCicloShort(e.ciclo_de_vida)}</option>
                    )}
                    {_CC_CICLO.map((c) => <option key={c.v} value={c.v}>{c.label}</option>)}
                  </select>
                </td>
                <td className="cc-cell-actions" data-label="Ações">
                  <button type="button" className="cc-remove" disabled={busy}
                          title="Remover (marca como descontinuada)" aria-label={`Remover ${e.codigo_commodity}`}
                          onClick={() => removeEntry(e)}
                          style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--err, #b71c1c)' }}>
                    🗑
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <>
      <div className="card subtle" style={{ marginBottom: 12 }}>
        <p className="caption" style={{ margin: 0 }}>
          Este é o <strong>cadastro de produtos</strong> — a fonte única de verdade do que entra
          e sai do dashboard. Cada produto é identificado por <code>(código, banco)</code> — o
          <strong> código real da fonte</strong>, uma a uma — e pertence a um <strong>agrupamento</strong> (o
          conceito que a unifica entre fontes). Agrupamentos são criados, renomeados e excluídos aqui;
          o <strong>Ciclo de Vida</strong> controla a exibição; <strong>remover</strong> uma commodity a marca
          como descontinuada (os dados já baixados ficam órfãos, apagados só por um humano). Edições
          exigem autorização e ficam registradas com seu e-mail.
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
          {data.entries.length.toLocaleString('pt-BR')} produtos · {data.groups.length} agrupamentos
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
        <div className="card cc-add-card" style={{ marginBottom: 12 }}>
          <window.SectionHeader overline="Cadastro" title="Adicionar commodity"
            action={<span className="caption">informe o código real da fonte</span>} />
          <div className="cc-add-grid">
            <label className="cc-field">
              <span className="cc-field-label">Banco (fonte)</span>
              <select value={draft.banco} onChange={(e) => setDraft((d) => ({ ...d, banco: e.target.value, codigo_commodity: '' }))}>
                {_CC_BANCOS.map((b) => <option key={b.v} value={b.v}>{b.label}</option>)}
              </select>
            </label>

            <label className="cc-field">
              <span className="cc-field-label">Código da commodity</span>
              <input type="text" list="cc-code-options" value={draft.codigo_commodity}
                     placeholder={srcCodes.loading && srcCodes.banco === draft.banco ? 'carregando códigos…' : 'digite ou escolha um código real'}
                     autoComplete="off"
                     onChange={(e) => setDraft((d) => ({ ...d, codigo_commodity: e.target.value.trim() }))} />
              <datalist id="cc-code-options">
                {(srcCodes.banco === draft.banco ? srcCodes.codes : []).slice(0, 3000).map((c) => (
                  <option key={c.code} value={c.code}>{c.name}</option>
                ))}
              </datalist>
              {draft.codigo_commodity ? (
                codeMatch === true ? (
                  <small className="cc-hint cc-hint-ok">✓ {codeIndex.get(draft.codigo_commodity) || 'código válido'}</small>
                ) : codeLoadedForBanco ? (
                  <small className="cc-hint cc-hint-bad">✗ este código não existe em {_CC_BANCO_LABEL[draft.banco]}</small>
                ) : (
                  <small className="cc-hint">verificando…</small>
                )
              ) : (
                <small className="cc-hint">
                  {srcCodes.banco === draft.banco && !srcCodes.loading
                    ? `${srcCodes.codes.length.toLocaleString('pt-BR')} códigos reais nesta fonte`
                    : ' '}
                </small>
              )}
            </label>

            <label className="cc-field">
              <span className="cc-field-label">Agrupamento</span>
              <CcGroupSelect value={draft.commodity_id} groups={groupsSorted} busy={busy}
                           onChange={(gid) => setDraft((d) => ({ ...d, commodity_id: gid }))}
                           placeholder={data.groups.length ? 'Escolha um agrupamento…' : 'Crie um agrupamento primeiro'} />
            </label>

            <label className="cc-field">
              <span className="cc-field-label">Ciclo de vida</span>
              <select value={draft.ciclo_de_vida} onChange={(e) => setDraft((d) => ({ ...d, ciclo_de_vida: e.target.value }))}>
                {_CC_CICLO.map((c) => <option key={c.v} value={c.v}>{c.label}</option>)}
              </select>
            </label>

            <label className="cc-field cc-field-wide">
              <span className="cc-field-label">Descrição <small className="pc-cap">(opcional — anotação sua)</small></span>
              <input type="text" value={draft.descricao_commodity} placeholder="ex.: Castanha-do-pará com casca"
                     onChange={(e) => setDraft((d) => ({ ...d, descricao_commodity: e.target.value }))} />
            </label>
          </div>
          <div className="cc-add-actions">
            <button type="button" className="btn-primary" onClick={submitAdd} disabled={!canSubmit}>
              {busy ? 'Salvando…' : 'Salvar commodity'}
            </button>
            <button type="button" className="btn-secondary" onClick={() => { setShowAdd(false); setDraft({ ..._CC_EMPTY_DRAFT }); }} disabled={busy}>
              Cancelar
            </button>
            {!canSubmit && draft.codigo_commodity && codeMatch !== true && codeLoadedForBanco && (
              <span className="caption" style={{ color: 'var(--err, #b71c1c)' }}>código inexistente</span>
            )}
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
                          title={g.n_members > 0 ? 'Reatribua ou remova os produtos antes de excluir' : 'Excluir agrupamento vazio'}>
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
                  <p className="caption" style={{ margin: '0 2px' }}>Agrupamento vazio — adicione produtos ou exclua-o.</p>
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
