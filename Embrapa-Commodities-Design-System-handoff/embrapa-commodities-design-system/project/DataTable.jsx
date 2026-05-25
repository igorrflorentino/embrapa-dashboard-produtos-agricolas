// Data table — for the "Tabela bruta" view of gold_commodity_matrix

function DataTable({ rows }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Ano</th>
            <th>UF</th>
            <th>Município</th>
            <th>Produto</th>
            <th className="num">Quantidade</th>
            <th className="num">val_real_ipca</th>
            <th className="num">val_yearfx</th>
            <th>Flag</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="tnum">{r.year}</td>
              <td>{r.uf}</td>
              <td>{r.city}</td>
              <td>{r.product}</td>
              <td className="num tnum">{r.qty == null ? '—' : r.qty.toLocaleString('pt-BR') + ' ' + r.unit}</td>
              <td className="num tnum">{window.fmtBRL(r.val_ipca)}</td>
              <td className="num tnum">{window.fmtBRL(r.val_yearfx)}</td>
              <td><window.StatusChip flag={r.flag} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

window.DataTable = DataTable;
