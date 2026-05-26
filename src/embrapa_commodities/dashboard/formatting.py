"""pt-BR number / currency / date helpers.

Port of `fmtBRL` / `fmtNum` from the design system's `data.js`, with broader
unit support (USD, EUR, CNY) and abbreviations matching the brand voice
("1,2 mi", "1,2 bi" — lowercase, comma decimal, non-breaking space).
"""

from __future__ import annotations

from datetime import datetime

NBSP = " "

_MONTH_PT = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
]

_CURRENCY_SYMBOL = {
    "BRL": "R$",
    "USD": "US$",
    "EUR": "€",
    "CNY": "¥",
}


def _ptbr_decimal(n: float, decimals: int = 2) -> str:
    return f"{n:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_currency(value: float | int | None, currency: str = "BRL") -> str:
    """Format a monetary amount in pt-BR locale with brand-style abbreviations.

    ``fmt_currency(4_380_000_000)`` → ``"R$ 4,38 bi"``
    ``fmt_currency(1234.56, "USD")`` → ``"US$ 1.234,56"``
    """
    if value is None:
        return "—"
    sym = _CURRENCY_SYMBOL.get(currency, currency)
    abs_v = abs(value)
    if abs_v >= 1e9:
        return f"{sym} {_ptbr_decimal(value / 1e9, 2)}{NBSP}bi"
    if abs_v >= 1e6:
        return f"{sym} {_ptbr_decimal(value / 1e6, 1)}{NBSP}mi"
    # Per the design system: keep absolute values up to 6 digits before
    # abbreviating. Drop fractional cents above R$ 100 to reduce noise.
    decimals = 0 if abs_v >= 100 else 2
    return f"{sym} {_ptbr_decimal(value, decimals)}"


def fmt_number(value: float | int | None, unit: str | None = None, decimals: int = 0) -> str:
    """Format a plain number with pt-BR thousands separators and optional unit."""
    if value is None:
        return "—"
    rendered = _ptbr_decimal(value, decimals)
    return f"{rendered}{NBSP}{unit}" if unit else rendered



def fmt_delta(value: float | None, suffix: str = "%") -> str:
    """Format a signed delta with explicit + on positives."""
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{_ptbr_decimal(value, 1)}{suffix}"


def fmt_date(value: datetime) -> str:
    """28 jun 2024 — pt-BR inline date."""
    return f"{value.day} {_MONTH_PT[value.month - 1]} {value.year}"


def fmt_datetime(value: datetime) -> str:
    """28 jun 2024 · 04:30 BRT."""
    return f"{fmt_date(value)} · {value.strftime('%H:%M')} BRT"


def value_column(convention: str, currency: str) -> str:
    """Map (convention, currency) → column name in gold_commodity_matrix.

    Convention is one of "ipca", "igpm", "yearfx". Currency is "BRL", "USD",
    "EUR", "CNY".
    """
    conv_map = {
        "ipca": "val_real_ipca",
        "igpm": "val_real_igpm",
        "yearfx": "val_yearfx",
    }
    if convention not in conv_map:
        raise ValueError(f"unknown convention: {convention!r}")
    if currency not in _CURRENCY_SYMBOL:
        raise ValueError(f"unknown currency: {currency!r}")
    return f"{conv_map[convention]}_{currency.lower()}"


def convention_label(convention: str) -> str:
    return {"ipca": "IPCA", "igpm": "IGP-M", "yearfx": "FX do ano"}[convention]


def period_to_years(
    year_range: tuple[int, int],
    period: str | None,
) -> tuple[int, int] | None:
    """Translate a UI period selector ("10", "20", "all") into a year range.

    Returns ``None`` for ``period="all"`` (meaning "no filter").
    Used by every page that offers a period radio button.
    """
    lo, hi = year_range
    if period == "10":
        return (max(lo, hi - 9), hi)
    if period == "20":
        return (max(lo, hi - 19), hi)
    return None
