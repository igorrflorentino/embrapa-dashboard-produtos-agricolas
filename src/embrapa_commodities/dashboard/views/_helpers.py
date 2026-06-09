"""Shared computations for the perspectives (concentration, CAGR, composition)."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pandas as pd

from ..theme import VIZ_SCALE


def gini(values: Sequence[float]) -> float:
    """Gini coefficient (0 = perfect equality, →1 = concentrated)."""
    xs = sorted(float(v) for v in values if v is not None and v > 0)
    n = len(xs)
    if n == 0:
        return 0.0
    total = sum(xs)
    if total == 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(xs, start=1):
        cum += i * x
    return (2 * cum) / (n * total) - (n + 1) / n


def hhi(values: Sequence[float]) -> float:
    """Herfindahl-Hirschman index on 0–10000 scale (sum of squared % shares)."""
    xs = [float(v) for v in values if v is not None and v > 0]
    total = sum(xs)
    if total == 0:
        return 0.0
    return sum((x / total * 100) ** 2 for x in xs)


def lorenz_points(values: Sequence[float]) -> list[float]:
    """Cumulative-share curve (leading 0) for a Lorenz chart."""
    xs = sorted(float(v) for v in values if v is not None and v > 0)
    total = sum(xs)
    if total == 0:
        return [0.0, 1.0]
    out = [0.0]
    acc = 0.0
    for x in xs:
        acc += x
        out.append(acc / total)
    return out


def top_n_share(values: Sequence[float], n: int = 5) -> float:
    """Share held by the top-n entries (0–1)."""
    xs = sorted((float(v) for v in values if v is not None and v > 0), reverse=True)
    total = sum(xs)
    if total == 0:
        return 0.0
    return sum(xs[:n]) / total


def cagr(first: float, last: float, years: int) -> float | None:
    """Compound annual growth rate (%) over ``years`` periods."""
    if not first or first <= 0 or last is None or last <= 0 or years <= 0:
        return None
    return ((last / first) ** (1 / years) - 1) * 100


def composition_latest(
    product_ts: pd.DataFrame, products: pd.DataFrame, *, top: int = 6
) -> tuple[list[str], list[float], list[str]]:
    """Top-N product composition for the latest year (labels, values, colors)."""
    if product_ts is None or product_ts.empty:
        return [], [], []
    last_year = int(product_ts["reference_year"].max())
    cut = product_ts[product_ts["reference_year"] == last_year]
    grouped = cut.groupby("code")["total_value"].sum().sort_values(ascending=False)
    name_by_code = {}
    if products is not None and not products.empty:
        name_by_code = dict(zip(products["code"], products["name"], strict=False))
    labels, values = [], []
    for code, val in grouped.head(top).items():
        labels.append(name_by_code.get(code, str(code)))
        values.append(float(val))
    rest = float(grouped.iloc[top:].sum()) if len(grouped) > top else 0.0
    if rest > 0:
        labels.append("Outros")
        values.append(rest)
    colors = VIZ_SCALE[: len(labels)]
    if labels and labels[-1] == "Outros":
        colors = [*VIZ_SCALE[: len(labels) - 1], "#ECECEC"]
    return labels, values, colors


def base_100(values: Sequence[float]) -> list[float]:
    """Normalize a series to its first non-null value = 100."""
    base = next((v for v in values if v), None)
    if not base:
        return [0.0 for _ in values]
    return [(v / base * 100) if v is not None else None for v in values]


def pearson(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Pearson correlation of two equal-length series."""
    pairs = [(x, y) for x, y in zip(a, b, strict=False) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None
    ax = sum(x for x, _ in pairs) / n
    ay = sum(y for _, y in pairs) / n
    num = sum((x - ax) * (y - ay) for x, y in pairs)
    dx = math.sqrt(sum((x - ax) ** 2 for x, _ in pairs))
    dy = math.sqrt(sum((y - ay) ** 2 for _, y in pairs))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def accum_pct(first: float, last: float) -> float | None:
    """Accumulated change (%) from first to last."""
    if not first:
        return None
    return (last - first) / first * 100
