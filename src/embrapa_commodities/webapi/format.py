"""pt-BR number/currency formatting and the metric-conventions model.

Ports the prototype's ``data.js`` formatters and ``MetricConventions.jsx`` helpers
to Python. Two responsibilities:

  1. **Formatting** — pt-BR locale output (``R$ 1.234.567,89``; ``1,2 bi``) without
     relying on the platform ``locale`` (unreliable on Windows/Cloud Run). All
     user-facing, so the strings here are Portuguese by project rule.
  2. **Conventions** — the display configuration (currency × inflation correction ×
     unit-per-family). Unlike the prototype (which multiplies one value by demo FX
     rates), we map a (currency, correction) pair to the **real** Gold/serving
     value column, so the dashboard deflates with actual data. ``monetary_column``
     returns the canonical column; the seam validates it against what the mart has.
"""

from __future__ import annotations

# ── pt-BR number formatting ──────────────────────────────────────────────────


def _ptbr(value: float, decimals: int = 0) -> str:
    """Format a number with pt-BR grouping (``.`` thousands, ``,`` decimal)."""
    s = f"{value:,.{decimals}f}"  # en-US: "1,234,567.89"
    return s.replace(",", "·").replace(".", ",").replace("·", ".")


def fmt_brl(n: float | None) -> str:
    """Compact BRL — bi/mi/mil thresholds (matches the prototype's fmtBRL).

    Thresholds compare ``abs(n)`` so a large NEGATIVE value (e.g. a -5 bi
    spread/delta) is still compacted; without it a negative fell through to the
    full-digit branch, diverging from the sibling ``fmt_money``.
    """
    if n is None:
        return "—"
    if abs(n) >= 1e9:
        return "R$ " + _ptbr(n / 1e9, 2) + " bi"
    if abs(n) >= 1e6:
        return "R$ " + _ptbr(n / 1e6, 1) + " mi"
    if abs(n) >= 1e3:
        return "R$ " + _ptbr(n / 1e3, 0) + " mil"
    return "R$ " + _ptbr(n, 0)


def fmt_money(n: float | None, symbol: str = "R$", *, compact: bool = True) -> str:
    """Compact currency in any symbol (US$, €, R$)."""
    if n is None:
        return "—"
    if compact:
        if abs(n) >= 1e9:
            return f"{symbol} " + _ptbr(n / 1e9, 2) + " bi"
        if abs(n) >= 1e6:
            return f"{symbol} " + _ptbr(n / 1e6, 1) + " mi"
        if abs(n) >= 1e3:
            return f"{symbol} " + _ptbr(n / 1e3, 0) + " mil"
    return f"{symbol} " + _ptbr(n, 0)


def fmt_num(n: float | None, unit: str | None = None, decimals: int = 0) -> str:
    if n is None:
        return "—"
    out = _ptbr(n, decimals)
    return out + (" " + unit if unit else "")


def fmt_pct(frac: float | None, decimals: int = 1) -> str:
    """Format a 0–1 fraction as a percentage."""
    if frac is None:
        return "—"
    return _ptbr(frac * 100, decimals) + "%"


def fmt_signed(n: float | None, decimals: int = 1, suffix: str = "%") -> str:
    if n is None:
        return "—"
    sign = "+" if n >= 0 else "−"
    return sign + _ptbr(abs(n), decimals) + suffix


def fmt_rows(n: float | None) -> str:
    """Compact row counter (mi / mil) for provenance readouts."""
    if n is None:
        return "—"
    if n >= 1e6:
        return _ptbr(n / 1e6, 1) + " mi"
    if n >= 1e3:
        return _ptbr(n / 1e3, 0) + " mil"
    return _ptbr(n, 0)


def fmt_axis_tick(v: float | None) -> str:
    """Compact axis tick (mil/mi/bi/tri) — keeps gutters from clipping."""
    if v is None:
        return ""
    a = abs(v)
    if a == 0:
        return "0"
    if a < 1:
        return _ptbr(v, 2)
    if a < 10:
        return _ptbr(v, 1)
    if a < 1000:
        return _ptbr(v, 0)
    for div, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if a >= div:
            n = v / div
            decimals = 0 if (abs(n) >= 100 or float(n).is_integer()) else 1
            return _ptbr(n, decimals) + suf
    return _ptbr(v, 0)


# ── Metric conventions ───────────────────────────────────────────────────────

DEFAULT_CONVENTIONS: dict = {
    "currency": "BRL",
    "correction": "IPCA",
    "units": {"mass": "t", "volume": "m³"},
    "auto_scale": False,
}

CURRENCY_SYMBOL = {"BRL": "R$", "USD": "US$", "EUR": "€"}
CURRENCY_LONG = {"BRL": "Real", "USD": "Dólar", "EUR": "Euro"}

# Correction id → the Gold/serving column infix. 'Nominal' uses the year-FX
# (un-deflated) value; the others use the IPCA/IGP-M/IGP-DI real columns.
_CORRECTION_INFIX = {
    "Nominal": "yearfx",
    "IPCA": "real_ipca",
    "IGP-M": "real_igpm",
    "IGP-DI": "real_igpdi",
}
_CURRENCY_SUFFIX = {"BRL": "brl", "USD": "usd", "EUR": "eur"}


def monetary_column(currency: str, correction: str) -> str:
    """Canonical serving value column for a (currency, correction) pair.

    e.g. (BRL, IPCA) → ``val_real_ipca_brl``; (USD, Nominal) → ``val_yearfx_usd``.
    The seam validates the result against the columns the banco's mart actually
    carries and falls back to the banco default when a combo is unavailable.
    """
    infix = _CORRECTION_INFIX.get(correction, "real_ipca")
    suffix = _CURRENCY_SUFFIX.get(currency, "brl")
    return f"val_{infix}_{suffix}"


def convention_value_label(conv: dict) -> str:
    """Human label for the active monetary convention, e.g. 'Valor real (IPCA) — R$'."""
    sym = CURRENCY_SYMBOL.get(conv.get("currency", "BRL"), "R$")
    corr = conv.get("correction", "IPCA")
    if corr == "Nominal":
        return f"Valor nominal — {sym}"
    return f"Valor real ({corr}) — {sym}"


def convention_monetary_label(conv: dict) -> str:
    """Compact label for chips/citation, e.g. 'BRL · IPCA'."""
    corr = conv.get("correction", "IPCA")
    tail = "nominal" if corr == "Nominal" else corr
    return f"{conv.get('currency', 'BRL')} · {tail}"


def currency_symbol(conv: dict) -> str:
    return CURRENCY_SYMBOL.get(conv.get("currency", "BRL"), "R$")


def symbol_for_column(column: str | None) -> str:
    """Currency symbol implied by a resolved value column's suffix."""
    if not column:
        return "R$"
    for suffix, sym in (("_usd", "US$"), ("_eur", "€"), ("_brl", "R$")):
        if column.endswith(suffix):
            return sym
    return "R$"


# pt-BR month abbreviations (index 0 → January), for seasonality axes/labels.
MONTH_ABBR_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
