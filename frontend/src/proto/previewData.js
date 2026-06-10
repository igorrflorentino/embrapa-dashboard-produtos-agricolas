// previewData.js — banco-keyed SYNTHETIC adapters for the flow / partner /
// monthly perspectives. These implement a stable DATA CONTRACT so the
// views never need rewriting: when a banco goes live, replace the body of
// each adapter with a real query against its Gold table and keep the
// returned shape identical. Every adapter sets `preview: true` so views
// can flag the data as demonstration until the real source exists.
//
// CONTRACTS — flowData / partnerData / monthlyData. SHAPE is defined once in
// contracts.js (@typedef FlowData / PartnerData / MonthlyData) — the single
// source of truth. Keep the returned keys in sync with it (the runtime lint
// window.auditSnapshotContracts warns if a contracted key goes missing).

(function () {
  // Deterministic PRNG (window.seeded) and macro-shock curve (window.macroShock)
  // live in synthUtils.js — used here via window.* so preview snapshots stay in
  // lockstep with the cross-source / cross-chain builders.

  // Partner universes per banco (what "destino"/"parceiro" means).
  const COUNTRIES = ['China', 'Estados Unidos', 'Países Baixos', 'Alemanha', 'Japão', 'Argentina', 'Espanha', 'Itália', 'Reino Unido', 'França'];
  const UFS = ['SP', 'PR', 'RS', 'MG', 'SC', 'MT', 'PA', 'BA', 'GO', 'AM'];
  // Generic fallback universe for a dimension, chosen by its DECLARED kind
  // (bancos.js → dimensions[dim].kind): 'country' → nations, else Brazilian UFs.
  // No bancoId branching — a new banco just declares its dimension kinds.
  const genericUniverse = (id, dim) =>
    ((window.bancoDim && window.bancoDim(id, dim).kind) === 'country') ? COUNTRIES : UFS;

  function originsFor(bancoId) {
    // Demo origin universes (window.DEMO_PARAMS via SNAP_ORIGINS); fallback is a
    // generic set chosen by the banco's declared origin kind.
    return (window.SNAP_ORIGINS && window.SNAP_ORIGINS[bancoId])
        || genericUniverse(bancoId, 'origin').slice(0, 5);
  }
  function destsFor(bancoId) {
    const real = window.SNAP_PARTNERS && window.SNAP_PARTNERS[bancoId];
    if (real) return real.slice(0, 6);
    return genericUniverse(bancoId, 'dest').slice(0, 6);
  }
  // Once a banco is live, its adapters serve real(istic) data → no preview banner.
  function previewFor(bancoId) {
    const b = window.bancoById ? window.bancoById(bancoId) : null;
    return !(b && b.status === 'live');
  }

  // Display currency symbol for a banco — derived from its declared
  // baseCurrency (bancos.js) via CURRENCY_FX, not a per-banco literal map.
  const unitFor = (bancoId) => {
    const ccy = window.canonCurrencyFor ? window.canonCurrencyFor(bancoId) : 'BRL';
    return ((window.CURRENCY_FX && window.CURRENCY_FX[ccy]) || { symbol: 'R$' }).symbol;
  };

  function yearWindow(summary) {
    const y0 = summary && summary.startDate ? parseInt(summary.startDate.slice(0, 4), 10) : 2010;
    const y1 = summary && summary.endDate ? parseInt(summary.endDate.slice(0, 4), 10) : 2024;
    return [Math.max(1997, y0), Math.min(2024, y1)];
  }

  // ── FLOW (origin → destination) ──────────────────────────────────────
  window.flowData = function (bancoId, summary) {
    const rnd = window.seeded('flow:' + bancoId);
    const origins = originsFor(bancoId);
    const dests = destsFor(bancoId);
    const unit = unitFor(bancoId);

    const nodes = [
      ...origins.map((o, i) => ({ id: 'o' + i, label: o, side: 'origin', value: 0 })),
      ...dests.map((d, i) => ({ id: 'd' + i, label: d, side: 'dest', value: 0 })),
    ];
    const links = [];
    origins.forEach((o, oi) => {
      // each origin sends to 2–3 destinations
      const nLinks = 2 + Math.floor(rnd() * 2);
      const picks = dests
        .map((d, di) => ({ di, w: rnd() }))
        .sort((a, b) => b.w - a.w)
        .slice(0, nLinks);
      picks.forEach(p => {
        const value = Math.round((200 + rnd() * 1800) * (1 - oi * 0.12));
        links.push({ source: 'o' + oi, target: 'd' + p.di, value });
      });
    });
    // node totals
    links.forEach(l => {
      const s = nodes.find(n => n.id === l.source); if (s) s.value += l.value;
      const t = nodes.find(n => n.id === l.target); if (t) t.value += l.value;
    });

    return {
      preview: previewFor(bancoId),
      unit,
      originLabel: window.bancoDim(bancoId, 'origin').label || 'origem',
      destLabel: window.bancoDim(bancoId, 'dest').label || 'destino',
      nodes, links,
    };
  };

  // ── PARTNER (ranking of trading partners) ────────────────────────────
  window.partnerData = function (bancoId, summary) {
    const rnd = window.seeded('partner:' + bancoId);
    const universe = (window.SNAP_PARTNERS && window.SNAP_PARTNERS[bancoId])
        || genericUniverse(bancoId, 'partner');
    const partners = universe.map((name, i) => {
      const base = (3200 - i * 280) * (0.7 + rnd() * 0.6);
      const exp = Math.round(base * (0.5 + rnd() * 0.4));
      const imp = Math.round(base * (0.2 + rnd() * 0.4));
      return { name, exp, imp, value: exp + imp };
    }).sort((a, b) => b.value - a.value);

    return {
      preview: previewFor(bancoId),
      flowLabel: window.bancoDim(bancoId, 'partner').label || 'parceiro',
      unit: unitFor(bancoId),
      partners,
    };
  };

  // ── MONTHLY (seasonality) ────────────────────────────────────────────
  window.monthlyData = function (bancoId, summary) {
    const rnd = window.seeded('monthly:' + bancoId);
    const [y0, y1] = yearWindow(summary);
    const years = [];
    for (let y = y1; y >= Math.max(y0, y1 - 9); y--) years.push(y);
    years.sort((a, b) => a - b);

    // seasonal profile: real per-banco castanha export seasonality when known,
    // else a generic harvest-driven mid-year peak.
    const realSeason = window.SNAP_SEASONAL && window.SNAP_SEASONAL[bancoId];
    const seasonal = realSeason
      ? realSeason.map(s => s * (1 + (rnd() - 0.5) * 0.05))
      : Array.from({ length: 12 }, (_, m) =>
          1 + 0.35 * Math.sin(((m - 2) / 12) * Math.PI * 2) + (rnd() - 0.5) * 0.08);

    const matrix = {};
    const series = [];
    years.forEach((y, yi) => {
      const trend = 1 + yi * 0.05;
      const row = seasonal.map((s, m) => {
        const v = Math.round(800 * s * trend * (0.9 + rnd() * 0.2));
        series.push({ ym: `${y}-${String(m + 1).padStart(2, '0')}`, y, m: m + 1, v });
        return v;
      });
      matrix[y] = row;
    });
    const monthlyAvg = Array.from({ length: 12 }, (_, m) => {
      const vals = years.map(y => matrix[y][m]);
      return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
    });

    return {
      preview: previewFor(bancoId),
      unit: unitFor(bancoId),
      years, months: [1,2,3,4,5,6,7,8,9,10,11,12],
      matrix, monthlyAvg, series,
    };
  };

  window.MONTH_LABELS = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];

  // ── PRODUCTIVITY (área + rendimento por cultura/UF) ──────────────────
  // CONTRACT: productivityData(bancoId, cropCode, summary) — SHAPE defined in
  // contracts.js (@typedef ProductivityData). For a banco with the 'yield'
  // capability (IBGE PAM). Demo crop universe +
  // per-UF productivity index live in demoFixture.js (window.DEMO_PARAMS.pam);
  // swap the body for a real query against the Gold table and keep this shape.
  window.productivityData = function (bancoId, cropCode, summary) {
    const pam = (window.DEMO_PARAMS && window.DEMO_PARAMS.pam) || { crops: [], ufProductivity: {} };
    const crops = pam.crops || [];
    if (!crops.length) return null;
    const crop = crops.find(c => c.code === cropCode) || crops[0];

    const cov = ((window.DEMO_PARAMS && window.DEMO_PARAMS.snapshot && window.DEMO_PARAMS.snapshot.coverage) || {})[bancoId] || [1990, 2024];
    const [y0, y1] = cov;
    const years = [];
    for (let y = y0; y <= y1; y++) years.push(y);
    const n = years.length;
    const rnd = window.seeded('prod:' + bancoId + ':' + crop.code);
    const shock = window.macroShock || (() => 1);

    // National annual series — yield & area each grow along an S-curve from
    // their start fraction to the end-year anchor, with mild noise + a damped
    // macro-shock (weather years). prodT = yieldKgHa × areaHa ÷ 1000.
    const series = years.map((y, i) => {
      const t    = n > 1 ? i / (n - 1) : 1;
      const ease = t * t * (3 - 2 * t);
      const yGrow = crop.yldStart  + (1 - crop.yldStart)  * ease;
      const aGrow = crop.areaStart + (1 - crop.areaStart) * ease;
      const wx = 1 + (shock(y) - 1) * 0.5;                 // weather damped onto yield
      const yieldKgHa = crop.yieldEnd * yGrow * (1 + (rnd() - 0.5) * 0.05) * wx;
      const areaHa    = crop.areaEndKha * 1000 * aGrow * (1 + (rnd() - 0.5) * 0.04);
      const prodT     = (yieldKgHa * areaHa) / 1000;
      return { y, yieldKgHa, areaHa, prodT };
    });

    const last  = series[series.length - 1] || { yieldKgHa: 0, areaHa: 0, prodT: 0 };
    const first = series[0] || last;
    const yieldCagr = (first.yieldKgHa > 0 && n > 1)
      ? (Math.pow(last.yieldKgHa / first.yieldKgHa, 1 / (n - 1)) - 1) * 100
      : 0;

    // Per-UF: join the canonical tile grid (window.UF_DATA · col/row) with the
    // crop's productivity index. Yield = national × index × seeded jitter;
    // area allocated proportionally to (index × UF base weight) of national area.
    const idxMap = pam.ufProductivity || {};
    const ufs = Array.isArray(window.UF_DATA) ? window.UF_DATA : [];
    const weighted = ufs.map((u, i) => {
      const idx = idxMap[u.uf] != null ? idxMap[u.uf] : 0.88;
      const jitter = 0.93 + 0.14 * Math.abs(Math.sin(i * 1.7 + crop.code.charCodeAt(4)));
      const yieldKgHa = last.yieldKgHa * idx * (0.97 + (rnd() - 0.5) * 0.06);
      const areaW = idx * (0.4 + u.value / 1000) * jitter;
      return { u, idx, yieldKgHa, areaW };
    });
    const totW = weighted.reduce((s, x) => s + x.areaW, 0) || 1;
    const byUF = weighted.map(({ u, yieldKgHa, areaW }) => {
      const areaHa = last.areaHa * (areaW / totW);
      return { uf: u.uf, name: u.name, region: u.region, col: u.col, row: u.row,
               yieldKgHa, areaHa, prodT: (yieldKgHa * areaHa) / 1000 };
    });

    return {
      preview: previewFor(bancoId),
      yieldUnit: pam.yieldUnit || 'kg/ha',
      areaUnit:  pam.areaUnit  || 'ha',
      crop:  { code: crop.code, name: crop.name },
      crops: crops.map(c => ({ code: c.code, name: c.name })),
      national: { yieldKgHa: last.yieldKgHa, areaHa: last.areaHa, prodT: last.prodT, yieldCagr },
      series,
      byUF,
    };
  };

  // ── REPRESENTATIVE PER-BANCO SNAPSHOT ────────────────────────────────
  // Produces a PEVS-SHAPED in-memory snapshot for a banco that has no real
  // Gold yet. MDIC COMEX and UN Comtrade are LIVE on these (representative
  // data generated from the explicit contract shape, 02_SNAPSHOT_CONTRACTS.md);
  // the banco-aware
  // applyFilters(summary, bancoId) consumes them end-to-end. Same keys/shape
  // as dataStore.datasetFor('ibge_pevs'). Deterministic (seeded) → stable
  // across reloads. Replace with the real query when the real Gold lands;
  // THE SHAPE IS THE CONTRACT — defined once in contracts.js (@typedef
  // BancoSnapshot); the handoff doc 02_SNAPSHOT_CONTRACTS.md points there.
  // The commodity-specific demo VALUES (product universes, partners, origins,
  // seasonality, coverage) live in ONE place — demoFixture.js (window.DEMO_PARAMS).
  // To demo a different chain, edit that file; the references below don't change.
  // [code, name, priceUsdPerKg, volEndKt] → v(US$ mi)=price×volKt, q(mil t)=volKt.
  const _SNAP = (window.DEMO_PARAMS && window.DEMO_PARAMS.snapshot) || {};
  const SNAP_PRODUCTS   = _SNAP.products  || {};
  const SNAP_COVERAGE   = _SNAP.coverage  || {};
  const SNAP_START_FRAC = _SNAP.startFrac || {};
  const SNAP_PARTNERS   = _SNAP.partners  || {};
  const SNAP_ORIGINS    = _SNAP.origins   || {};
  const SNAP_SEASONAL   = _SNAP.seasonal  || {};
  window.SNAP_PARTNERS = SNAP_PARTNERS;
  window.SNAP_ORIGINS  = SNAP_ORIGINS;
  window.SNAP_SEASONAL = SNAP_SEASONAL;

  window.snapshotFor = function (bancoId) {
    const defs = SNAP_PRODUCTS[bancoId];
    if (!defs) return null;
    const prods = defs.map(([code, name]) => ({ code, name, unit: 't', family: 'mass' }));
    const [y0, y1] = SNAP_COVERAGE[bancoId] || [1997, 2024];
    const startFrac = SNAP_START_FRAC[bancoId] ?? 0.3;
    const years = [];
    for (let y = y0; y <= y1; y++) years.push(y);
    const rnd = window.seeded('snap:' + bancoId);
    const banco = window.bancoById ? window.bancoById(bancoId) : null;
    const hasGeo = !!(banco && banco.provides && banco.provides.includes('geo'));
    // The conventions layer treats every stored value as BRL-canonical and
    // multiplies by the display FX rate. COMEX/Comtrade are priced in USD, so
    // store values in BRL-equivalent (USD ÷ USD-rate); changeDatabase defaults
    // the display currency to USD, which then renders the real US$ figures.
    const baseCcy = window.canonCurrencyFor ? window.canonCurrencyFor(bancoId) : 'BRL';
    const baseRate = ((window.CURRENCY_FX && window.CURRENCY_FX[baseCcy]) || { rate: 1 }).rate || 1;
    const canonFactor = 1 / baseRate;

    // productTS[code] = [{ y, v(canonical-BRL mi), q(mil t), family }] — grown
    // along an S-curve from startFrac→1 of the end-year anchor, + noise/shocks.
    const productTS = {};
    defs.forEach(([code, name, price, volEnd], pi) => {
      productTS[code] = years.map((y, i) => {
        const t    = i / (years.length - 1 || 1);
        const ease = t * t * (3 - 2 * t);
        const grow = startFrac + (1 - startFrac) * ease;
        const noise = 1 + (rnd() - 0.5) * 0.09;
        const q = volEnd * grow * noise * window.macroShock(y);       // mil t (thousand tonnes)
        const v = price * q * canonFactor;                    // canonical mi (price US$/kg × kt × FX)
        return { y, v, q, family: 'mass' };
      });
    });

    // overviewTS = annual aggregate; v in bi (mi ÷ 1000), q_mass summed. No q_vol.
    const overviewTS = years.map((y, i) => {
      let v = 0, qm = 0;
      prods.forEach(p => { const pt = productTS[p.code][i]; v += pt.v / 1000; qm += pt.q; });
      return { y, v, q: qm, q_mass: qm };
    });

    // ufData only for bancos with `geo` (COMEX/SEFAZ; NOT Comtrade). Reuses the
    // canonical tile-map grid (col/row) but reweights toward the origin UFs.
    let ufData = [];
    let qualityByUf = [];
    if (hasGeo && Array.isArray(window.UF_DATA)) {
      const last = overviewTS[overviewTS.length - 1] || { v: 0, q_mass: 0 };
      const origins = new Set(SNAP_ORIGINS[bancoId] || []);
      const weighted = window.UF_DATA.map(u => ({
        u, w: (origins.has(u.uf) ? 6 : 0.25) * (0.6 + u.value / 1000),
      }));
      const tot = weighted.reduce((a, x) => a + x.w, 0) || 1;
      ufData = weighted.map(({ u, w }) => {
        const f = w / tot;
        return { uf: u.uf, name: u.name, region: u.region, col: u.col, row: u.row,
                 value: last.v * 1000 * f, q_mass: last.q_mass * f, q_vol: 0 };
      });
      qualityByUf = window.UF_DATA.map((u, i) => ({
        uf: u.uf, name: u.name, region: u.region, col: u.col, row: u.row,
        not_ok: Math.min(0.4, (origins.has(u.uf) ? 0.06 : 0.16) + Math.abs(Math.sin(i * 1.7)) * 0.05),
      }));
    }

    // quality flag distribution — reuse the canonical flag taxonomy (shared
    // vocabulary across bancos); shares tilted a bit by banco.
    const quality = (window.QUALITY_FLAGS || []).map(q => ({ ...q }));

    // per-product quality (flag shares) — deterministic, plausible.
    const FLAG_IDS = ['OK', 'MISSING_VALUE', 'MISSING_QUANTITY', 'ESTIMATED', 'OUTLIER', 'BOUNDARY_HISTORIC'];
    const qualityByProduct = defs.map(([code, name], pi) => {
      const r = window.seeded('q:' + bancoId + ':' + code);
      const ok = 0.80 + r() * 0.14;
      const rest = 1 - ok;
      const w = [0, r() * 0.4 + 0.25, r() * 0.3 + 0.15, r() * 0.2 + 0.1, r() * 0.12 + 0.05, r() * 0.1 + 0.05];
      const wsum = w.reduce((a, b) => a + b, 0) - w[0] || 1;
      const row = { code, name };
      FLAG_IDS.forEach((id, k) => { row[id] = k === 0 ? ok : (w[k] / wsum) * rest; });
      return row;
    });

    // quality over coverage years (rate of OK rises gently over time).
    const qualityTs = years.map((y, i) => {
      const t = i / (years.length - 1 || 1);
      const ok = 0.74 + t * 0.16 + Math.sin(i * 1.3) * 0.012;
      const missing_value    = Math.max(0, 0.10 - t * 0.05);
      const missing_quantity = Math.max(0, 0.05 - t * 0.02);
      const estimated = 0.04, outlier = 0.02;
      const boundary = Math.max(0, 1 - ok - missing_value - missing_quantity - estimated - outlier);
      return { y, ok, missing_value, missing_quantity, estimated, outlier, boundary };
    });

    return {
      products:   prods,
      productTS,
      overviewTS,
      ufData,
      quality,
      qualityTs,
      qualityByProduct,
      qualityByUf,
      topMunis:   [],                          // municipality table not synthesized
      regions:    window.REGIONS || [],
      _synthetic: true,                        // marker: representative, not real Gold
    };
  };
})();
