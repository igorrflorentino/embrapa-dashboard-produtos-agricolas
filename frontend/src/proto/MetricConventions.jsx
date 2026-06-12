// MetricConventions — display-time metric configuration strip.
// Sits BELOW the active-filter chips, ABOVE the dashboard views.
//
// Filters reduce *which rows* enter the visualization.
// Conventions decide *how those rows are displayed*: which currency,
// whether values are nominal or inflation-adjusted, and which units
// are used for mass / volume readouts.
//
// Controlled component:
//   <MetricConventions value={...} onChange={fn(next)} />
// where value is:
//   { currency: 'BRL'|'USD'|'EUR'|'CNY',
//     correction: 'Nominal'|'IPCA'|'IGP-M'|'IGP-DI',
//     units: { mass: 't', volume: 'm³', … }  // display unit per family }

function MetricConventions({ value, onChange, families }) {
  const set = (patch) => onChange({ ...value, ...patch });

  // Physical-unit groups are REGISTRY-DRIVEN: one group per family present
  // in the data (familiesInBasket). Mass/volume keep their dedicated conv
  // fields for back-compat; any other family stores its unit in value.units.
  const physFams = ((families && families.length ? families : ['mass', 'volume']))
    .filter(f => window.UNIT_FAMILIES[f]);
  const unitFor = (fid) => (value.units && value.units[fid]) || window.defaultUnitOf(fid);
  const setUnitFor = (fid, id) => set({ units: { ...(value.units || {}), [fid]: id } });

  const Group = ({ label, options, active, onPick, mono }) => (
    <div className="mc-group">
      <span className="mc-label">{label}</span>
      <div className="seg">
        {options.map(o => (
          <button key={o.id}
                  type="button"
                  className={'seg-opt ' + (active === o.id ? 'on' : '')}
                  onClick={() => onPick(o.id)}>
            <span className={mono ? 'tnum' : ''}>{o.id}</span>
            {o.sub && <small>{o.sub}</small>}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="mc-bar">
      <div className="mc-head">
        <span className="mc-overline">Convenções métricas</span>
        <span className="mc-caption">
          Como os valores e quantidades são exibidos — não altera quais linhas entram na visualização.
        </span>
        <label className="mc-check" title="Reescala automaticamente entre mil/mi/bi para evitar números longos">
          <input type="checkbox"
                 checked={!!value.autoScale}
                 onChange={(e) => set({ autoScale: e.target.checked })} />
          <span>Auto-escala (mil/mi/bi)</span>
        </label>
      </div>

      <div className="mc-groups">
        <Group
          label="Moeda"
          mono
          options={[
            // BRL/USD/EUR are real Gold columns (BCB PTAX series). CNY is omitted:
            // the BCB publishes no BRL/CNY series, so a CNY value would have to be
            // fabricated — better not to offer it than to show a made-up rate.
            { id: 'BRL', sub: 'R$'  },
            { id: 'USD', sub: 'US$' },
            { id: 'EUR', sub: '€'   },
          ]}
          active={value.currency}
          onPick={(id) => set({ currency: id })}
        />

        <Group
          label="Correção monetária"
          options={[
            { id: 'Nominal', sub: 'sem corr.' },
            { id: 'IPCA',    sub: 'IBGE' },
            { id: 'IGP-M',   sub: 'FGV'  },
            { id: 'IGP-DI',  sub: 'FGV'  },
          ]}
          active={value.correction}
          onPick={(id) => set({ correction: id })}
        />

        {physFams.map(fid => {
          const fam = window.UNIT_FAMILIES[fid];
          return (
            <Group key={fid}
              label={fam.label}
              mono
              options={(fam.units || []).map(u => ({ id: u.id, sub: u.long }))}
              active={unitFor(fid)}
              onPick={(id) => setUnitFor(fid, id)}
            />
          );
        })}
      </div>
    </div>
  );
}

// Helpers — exported on window for use by views ----------------------

window.DEFAULT_CONVENTIONS = {
  currency:   'BRL',
  correction: 'IPCA',
  units:      { mass: 't', volume: 'm³' },
  autoScale:  false,
};
// Display unit chosen for a family (falls back to the registry default).
window.unitOf = (conv, fam) => (conv && conv.units && conv.units[fam]) || window.defaultUnitOf(fam);

// Auto-scale helper — picks a (factor, suffix) so the number sits in a
// readable magnitude. Used only when conv.autoScale === true.
window.autoScaleNum = (v) => {
  const a = Math.abs(v);
  if (a >= 1e9) return { factor: 1e9, suffix: 'bi' };
  if (a >= 1e6) return { factor: 1e6, suffix: 'mi' };
  if (a >= 1e3) return { factor: 1e3, suffix: 'mil' };
  return { factor: 1, suffix: '' };
};

function _fmtRescaled(v, conv, unitSuffix) {
  if (conv.autoScale) {
    const { factor, suffix } = window.autoScaleNum(v);
    const scaled = v / factor;
    const txt = scaled.toLocaleString('pt-BR', {
      maximumFractionDigits: scaled < 10 ? 2 : scaled < 100 ? 1 : 0,
    });
    return suffix
      ? `${txt} ${suffix} ${unitSuffix}`.trim()
      : `${txt} ${unitSuffix}`.trim();
  }
  return v.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) + ' ' + unitSuffix;
}

// Currency display symbols + BRL-pivot FX rates. The rates are NOT used by the
// BRL-native path (convFactor: BRL/USD/EUR are server-native real Gold columns →
// factor 1); they ARE still used by convFactorFor to cross-convert a USD-NATIVE
// trade banco (COMEX/Comtrade) to a non-default display currency (the
// cross-contract #5 base-aware path). CNY is intentionally absent — the BCB
// publishes no BRL/CNY series, so it is not an offerable currency.
window.CURRENCY_FX = {
  BRL: { rate: 1,     symbol: 'R$',  long: 'Real'  },
  USD: { rate: 0.205, symbol: 'US$', long: 'Dólar' },
  EUR: { rate: 0.187, symbol: '€',   long: 'Euro'  },
};

// Mock nominal-deflation factor: when Nominal correction is picked we
// scale the *real* values down to a plausible "as-paid-then" figure.
// Real pipeline: real = nominal × cumulative_inflation; reversing here.
window.CORRECTION_FACTOR = {
  IPCA:    1.00,
  'IGP-M': 1.06,
  'IGP-DI':1.04,
  Nominal: 0.22,  // illustrative — shrinks 2024 real values back to ~nominal
};

// Multiplicative display factor for a *value* (correction factor × display FX
// rate). Stored values are BRL-CANONICAL: PEVS/SEFAZ are already in R$, and
// the COMEX/Comtrade snapshots store BRL-EQUIVALENT figures (USD ÷ USD-rate,
// see previewData.js) on purpose — so this single BRL-based factor renders the
// real US$ amounts once changeDatabase defaults their display currency to USD.
// Every manual value-scaling site (views building chart series by hand) MUST
// use this so they agree with applyConv / formatValue.
window.convFactor = (conv) => {
  // REACT MIGRATION: currency × correction now select the REAL deflated value
  // column SERVER-side (val_real_{ipca,igpm,igpdi}_brl, val_yearfx_* for Nominal,
  // *_usd for USD) — the scientific core — instead of this flat client multiplier.
  // So: correction is fully server-applied (factor 1); BRL/USD AND EUR are now
  // server-native columns (val_*_brl / val_*_usd / val_*_eur — the serving marts
  // carry real BCB PTAX EUR), so all three are factor 1 (a EUR snapshot is already
  // EUR-valued and must NOT be re-multiplied). CNY is not offered (no BCB BRL/CNY
  // series). The FX fallback below is now defensive only — no selectable currency
  // hits it. (Edge: USD + IGP-M/IGP-DI has no _usd column → BFF falls back to BRL;
  // the value_label flags "moeda indisponível → R$".)
  const serverNative =
    conv.currency === 'BRL' || conv.currency === 'USD' || conv.currency === 'EUR';
  return serverNative ? 1 : (window.CURRENCY_FX[conv.currency] || { rate: 1 }).rate;
};

// Base-aware value multiplier — for a value stored in a banco's OWN base
// currency (bancos.js `baseCurrency`), returns the multiplier that converts it
// to the active display currency. The plain convFactor above assumes every value
// is BRL-canonical; that holds for PEVS/SEFAZ (base=BRL) and for the synthetic
// snapshots (previewData.js stores BRL-equivalent on purpose). It does NOT hold
// for the live API path of a USD-native trade banco (COMEX/Comtrade), whose
// ufData arrives in US$: there convFactor('USD')=1 is correct only at the default
// USD display — switching to R$ (convFactor('BRL')=1) would leave a US$ magnitude
// under R$. This helper closes that gap WITHOUT changing the BRL-base path:
//   • base=BRL → delegates to convFactor verbatim (PEVS/SEFAZ unchanged, every
//     currency, default and not — server-native BRL/USD stay factor 1).
//   • base=foreign (USD) → identity when display==base (default view unchanged),
//     else the base→display cross-rate via the BRL-pivot CURRENCY_FX rates.
window.convFactorFor = (base, conv) => {
  base = base || 'BRL';
  if (base === 'BRL') return window.convFactor(conv);     // BRL-canonical path, untouched
  if (conv.currency === base) return 1;                   // default display → identity
  const fx = window.CURRENCY_FX;
  const rDisp = (fx[conv.currency] || { rate: 1 }).rate;
  const rBase = (fx[base] || { rate: 1 }).rate || 1;
  return rDisp / rBase;                                   // base → display via BRL pivot
};

// Convert a BRL-canonical value through the active currency + correction.
window.applyConv = (val, conv) => {
  if (val == null) return null;
  return val * window.convFactor(conv);
};

// Format a BRL-canonical value through the active convention.
// Auto-scale (mil/mi/bi) only when conv.autoScale === true.
window.formatValue = (brl, conv) => {
  if (brl == null) return '—';
  const sym = window.CURRENCY_FX[conv.currency].symbol;
  const v = window.applyConv(brl, conv);
  if (conv.autoScale) {
    const { factor, suffix } = window.autoScaleNum(v);
    const scaled = v / factor;
    const txt = scaled.toLocaleString('pt-BR', {
      maximumFractionDigits: scaled < 10 ? 2 : scaled < 100 ? 1 : 0,
    });
    return suffix ? `${sym} ${txt} ${suffix}` : `${sym} ${txt}`;
  }
  return sym + ' ' + v.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
};

// Axis label — when auto-scale is ON, append the picked suffix for the
// passed reference magnitude; otherwise just the currency symbol.
window.valueAxisLabel = (conv, refMagnitude) => {
  const sym = window.CURRENCY_FX[conv.currency].symbol;
  if (conv.autoScale && refMagnitude != null) {
    const { suffix } = window.autoScaleNum(refMagnitude);
    return suffix ? `${sym} ${suffix}` : sym;
  }
  return sym;
};

// Convert a series {y, v: value in banco base currency} to displayed currency.
window.convertSeries = (series, conv, key = 'v') => {
  const factor = window.convFactor(conv);
  return series.map(d => ({ ...d, [key]: d[key] * factor }));
};

// Mass / volume: native data is in t (mass) and m³ (volume) at internal scale.
// OVERVIEW_TS.q_mass holds *thousands of tonnes*; PRODUCT_TS.q (mass) same.
// OVERVIEW_TS.q_vol holds *millions of m³*; PRODUCT_TS.q (volume) same.
//
// Display rule (per user request): never auto-rescale to abbreviated units.
// The user picks t or kg → we render in t or kg. Same for m³ vs L.

window.formatMassQty = (milT, conv) => {
  if (milT == null) return '—';
  const v = milT * window.massQtyMul(conv);
  return _fmtRescaled(v, conv, window.unitOf(conv, 'mass'));
};
window.formatVolumeQty = (miM3, conv) => {
  if (miM3 == null) return '—';
  const v = miM3 * window.volumeQtyMul(conv);
  return _fmtRescaled(v, conv, window.unitOf(conv, 'volume'));
};

// Multipliers: internal dataset units (mil t / mi m³) → selected display
// unit, via the registry factors so any member unit (kg/t/@/sc, L/m³/hL…)
// converts correctly. internal mass = mil t (×1000 t); internal vol = mi m³.
window.massQtyMul    = (conv) => 1000 / window.unitToBase('mass', window.unitOf(conv, 'mass'));
window.volumeQtyMul  = (conv) => 1e6  / window.unitToBase('volume', window.unitOf(conv, 'volume'));
window.massAxisLabel   = (conv) => window.unitOf(conv, 'mass');
window.volumeAxisLabel = (conv) => window.unitOf(conv, 'volume');

// Human label for the active monetary convention (e.g. "USD · IPCA").
window.conventionMonetaryLabel = (conv) =>
  conv.currency + (conv.correction === 'Nominal' ? ' · nominal' : ' · ' + conv.correction);

// scaleSeries — rescales a series + returns the matching axis label.
// When conv.autoScale is OFF, returns the data as-is and unitSuffix only.
// When ON, divides every value by autoScale(refMagnitude).factor and
// builds the label respecting unit grammar:
//   currency → "R$ bi"  (symbol before suffix)
//   physical → "bi t"   (suffix before unit)
window.scaleSeries = (series, refMag, conv, valueKey, unitSuffix) => {
  if (!conv.autoScale) {
    return { data: series, label: unitSuffix };
  }
  const { factor, suffix } = window.autoScaleNum(refMag);
  if (!suffix) return { data: series, label: unitSuffix };
  const data = series.map(d => ({ ...d, [valueKey]: d[valueKey] / factor }));
  // Currency symbols sit BEFORE the magnitude suffix ("R$ bi"),
  // physical units sit AFTER ("bi t").
  const CURRENCY_SYMS = ['R$', 'US$', '€'];
  const label = CURRENCY_SYMS.includes(unitSuffix)
    ? `${unitSuffix} ${suffix}`
    : `${suffix} ${unitSuffix}`.trim();
  return { data, label };
};

window.MetricConventions = MetricConventions;
