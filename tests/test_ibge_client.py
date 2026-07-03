"""Tests for the IBGE SIDRA client and discovery helpers (HTTP fully mocked)."""

from __future__ import annotations

import json
import re

import pytest
import responses

from embrapa_dashboard import discover
from embrapa_dashboard.ibge import client


@pytest.fixture
def sidra_payload() -> list[dict]:
    # SIDRA returns a list whose first dict is the human header row.
    return [
        {
            "NC": "Nível Territorial (Código)",
            "NN": "Nível Territorial",
            "MC": "Município (Código)",
            "MN": "Município",
            "V": "Valor",
            "D2C": "Variável (Código)",
            "D2N": "Variável",
            "D4C": "Tipo de produto extrativo (Código)",
            "D4N": "Tipo de produto extrativo",
            "MD": "Unidade de Medida",
            "AC": "Ano (Código)",
            "AN": "Ano",
        },
        {
            "NC": "6",
            "NN": "Município",
            "MC": "1100015",
            "MN": "Alta Floresta D'Oeste - RO",
            "V": "10",
            "D2C": "144",
            "D2N": "Quantidade produzida",
            "D4C": "3405",
            "D4N": "3405 - Castanha-do-pará",
            "MD": "Toneladas",
            "AC": "1990",
            "AN": "1990",
        },
    ]


@responses.activate
def test_n6_fetch_slices_by_state_in_parallel(sidra_payload: list[dict]) -> None:
    """At n6 we always slice by state: one HTTP call per UF, parallelized."""
    responses.add(
        method=responses.GET,
        url=re.compile(r"https://apisidra\.ibge\.gov\.br/values/t/289/.*"),
        json=sidra_payload,
        status=200,
    )

    df = client.fetch_sidra_dataframe(
        table_id="289",
        start_year=2023,
        end_year=2025,
        classification="193",
        products=["3405"],
        geo_level="n6",
    )

    state_calls = [c for c in responses.calls if "/in n3 " in c.request.url.replace("%20", " ")]
    assert len(state_calls) == len(client.BRAZIL_STATES)
    assert len(df) == len(client.BRAZIL_STATES)


@responses.activate
def test_period_halving_handles_multi_year_limit(sidra_payload: list[dict]) -> None:
    """If `all` for 2 years exceeds the limit but a single year fits, halve the period."""

    def callback(request):  # type: ignore[no-untyped-def]
        url = request.url
        if re.search(r"/p/1990-1991/", url):
            return (400, {}, "Limite de valores excedido")
        return (200, {}, json.dumps(sidra_payload))

    responses.add_callback(
        method=responses.GET,
        url=re.compile(r"https://apisidra\.ibge\.gov\.br/values/t/289/.*"),
        callback=callback,
    )

    df = client.fetch_sidra_dataframe(
        table_id="289",
        start_year=1990,
        end_year=1991,
        classification="193",
        products=["3405"],
        geo_level="n3",  # avoids state-slicing fallback so we exercise the halver
    )
    assert not df.empty


@responses.activate
def test_search_ibge_products_returns_keyword_matches() -> None:
    responses.add(
        method=responses.GET,
        url="https://servicodados.ibge.gov.br/api/v3/agregados/289/metadados",
        json={
            "classificacoes": [
                {
                    "id": 193,
                    "nome": "Tipo de produto extrativo vegetal",
                    "categorias": [
                        {"id": "3405", "nome": "Castanha-do-pará"},
                        {"id": "3435", "nome": "Madeira em tora"},
                        {"id": "3450", "nome": "Pinheiro brasileiro (em tora)"},
                        {"id": "9999", "nome": "Açaí (fruto)"},
                    ],
                }
            ]
        },
        status=200,
    )

    matches = discover.search_ibge_products("289", ["castanha", "madeira", "pinheiro"])
    assert {m.code for m in matches} == {"3405", "3435", "3450"}
    assert all(m.classification_id == "193" for m in matches)


@pytest.mark.parametrize(
    ("n_products", "expected_min"),
    [
        (1, 27),  # 100k * 0.7 / (853 * 3 * 1) = ~27
        (3, 9),  # 100k * 0.7 / (853 * 3 * 3) = ~9
        (6, 4),  # 100k * 0.7 / (853 * 3 * 6) = ~4
        (9, 3),  # 100k * 0.7 / (853 * 3 * 9) = ~3
        (50, 1),  # never goes below 1
    ],
)
def test_recommended_chunk_years_scales_inversely_with_product_count(
    n_products: int, expected_min: int
) -> None:
    """As products grow, the safe chunk shrinks proportionally."""
    chunk = client.recommended_chunk_years(n_products)
    assert chunk >= 1
    assert chunk == expected_min, f"n_products={n_products} → got {chunk}, expected {expected_min}"


def test_recommended_chunk_years_rejects_zero_or_negative() -> None:
    with pytest.raises(ValueError):
        client.recommended_chunk_years(0)
    with pytest.raises(ValueError):
        client.recommended_chunk_years(-1)


def test_http_get_once_delegates_to_core_drained(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_http_get_once`` (the undecorated drain) must call ``core_http.get_drained``
    with the SIDRA-specific transient class and the given deadline. Slow-byte deadline
    semantics themselves are covered in ``test_core_http.py`` — this is a wiring guard
    against accidentally swapping ``SidraTransientError`` for some other transient class.
    """
    captured: dict[str, object] = {}

    class _FakeResponse:
        status_code = 200

        def close(self) -> None:
            pass

    def fake_get_drained(url: str, **kwargs: object) -> _FakeResponse:
        captured["url"] = url
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(client.core_http, "get_drained", fake_get_drained)

    url = "https://apisidra.ibge.gov.br/values/t/289/p/2020/v/all/n6/all/c193/3405"
    result = client._http_get_once(url)
    assert isinstance(result, _FakeResponse)

    assert captured["url"] == url
    assert captured["transient_exc"] is client.SidraTransientError
    # The default (floor) drain budget when the caller doesn't scale.
    assert captured["total_deadline_s"] == client.REQUEST_TOTAL_DEADLINE_S
    assert captured["context"] == url[:200]


def test_request_deadlines_scale_with_volume() -> None:
    """A bigger request (more periods × products × variables) gets a longer drain +
    retry budget than the flat 75s/180s floor; a small one keeps the floor; both are
    clamped to a ceiling. This is the fix for the slow-SIDRA backfill failure."""
    # Small request → the lean drain floor; retry budget = drain × MULT (clamped).
    drain_small, retry_small = client._request_deadlines(1, 1, "105")
    assert drain_small == client.REQUEST_TOTAL_DEADLINE_S
    assert retry_small == pytest.approx(drain_small * client._RETRY_BUDGET_MULT)
    assert retry_small >= client.PER_CALL_RETRY_BUDGET_S

    # The PPM herd block that died: 13 years × 8 products × 1 variable → well above floor.
    drain_big, retry_big = client._request_deadlines(13, 8, "105")
    assert drain_big > client.REQUEST_TOTAL_DEADLINE_S
    assert retry_big > retry_small
    assert retry_big == pytest.approx(drain_big * client._RETRY_BUDGET_MULT)

    # 'all' counts as several variables, so it scales faster than one explicit code.
    drain_all, _ = client._request_deadlines(13, 8, "all")
    assert drain_all > drain_big

    # geo_units (an n6 per-state slice's município count) folds into the volume, so a
    # dense-state municipal request gets a strictly longer drain than the same request
    # at an aggregated level (geo_units=1) — the IBGE-1 fix.
    drain_geo, _ = client._request_deadlines(1, 1, "105", client.LARGEST_STATE_MUNICIPALITY_COUNT)
    assert drain_geo > drain_small

    # A pathological request is clamped to the drain ceiling, never unbounded; the
    # retry budget follows as ceiling × MULT (within _RETRY_BUDGET_MAX_S).
    drain_huge, retry_huge = client._request_deadlines(60, 60, "all")
    assert drain_huge == client._DEADLINE_MAX_S
    assert retry_huge == pytest.approx(client._DEADLINE_MAX_S * client._RETRY_BUDGET_MULT)
    assert retry_huge <= client._RETRY_BUDGET_MAX_S

    # IBGE-1 regression guard: geo_units saturates the n6 DRAIN to the 600s cap, but the
    # RETRY budget must stay volume-proportional — otherwise a sparse single-year state
    # inherits the saturated ceiling × MULT (1500s) and one stalled state can eat the
    # whole nightly task window. A single-year n6 slice gets a strictly SMALLER retry
    # budget than a wide one (and the SAME lean budget as a small aggregated request),
    # even though both n6 slices share the saturated drain cap.
    drain_n6_1y, retry_n6_1y = client._request_deadlines(
        1, 1, "105", client.LARGEST_STATE_MUNICIPALITY_COUNT
    )
    drain_n6_big, retry_n6_big = client._request_deadlines(
        13, 8, "105", client.LARGEST_STATE_MUNICIPALITY_COUNT
    )
    assert drain_n6_1y == client._DEADLINE_MAX_S  # both saturate the drain cap …
    assert drain_n6_big == client._DEADLINE_MAX_S
    assert retry_n6_1y < retry_n6_big  # … but the retry budget is volume-proportional
    assert retry_n6_1y == pytest.approx(retry_small)  # sparse single-year n6 keeps the lean budget


def test_fetch_block_forwards_volume_scaled_deadlines(
    monkeypatch: pytest.MonkeyPatch, sidra_payload: list[dict]
) -> None:
    """_fetch_block derives the per-request deadlines from THIS block's volume and
    forwards them to _http_get — so the PPM herd block (13y × 8 products) that died
    at the flat 75s now gets the scaled budget."""
    captured: dict[str, float] = {}

    class _R:
        def json(self) -> list[dict]:
            return sidra_payload

    def fake_http_get(url: str, *, total_deadline_s: float, retry_budget_s: float) -> _R:
        captured["total_deadline_s"] = total_deadline_s
        captured["retry_budget_s"] = retry_budget_s
        return _R()

    monkeypatch.setattr(client, "_http_get", fake_http_get)
    periods = list(range(1974, 1987))  # 13 years
    products = ["2670", "2675", "2672", "32794", "2681", "2677", "32796", "2680"]  # 8
    client._fetch_block("3939", periods, "n6", "in n3 41", "79", products, variables="105")

    # The n6 per-state path folds in the worst-case município count (IBGE-1), so the
    # forwarded deadlines must match _request_deadlines WITH that geo factor.
    expected_drain, expected_retry = client._request_deadlines(
        len(periods), len(products), "105", client.LARGEST_STATE_MUNICIPALITY_COUNT
    )
    assert captured["total_deadline_s"] == expected_drain
    assert captured["retry_budget_s"] == expected_retry
    assert captured["total_deadline_s"] > client.REQUEST_TOTAL_DEADLINE_S  # the fix


# ─── empty period window (task 5 defensiveness) ──────────────────────────────
def test_periods_string_rejects_empty_list() -> None:
    """An empty period list has no SIDRA range — raise rather than index [0]."""
    with pytest.raises(ValueError, match="empty"):
        client._periods_string([])


def test_fetch_sidra_dataframe_empty_window_returns_empty_frame() -> None:
    """An inverted window (start > end → no periods) is treated as 'no rows', not
    an IndexError. The delta path can hand us such a window."""
    df = client.fetch_sidra_dataframe(
        table_id="289",
        start_year=2025,
        end_year=2024,  # start > end → empty period list
        classification="193",
        products=["3405"],
        geo_level="n6",
    )
    assert df.empty


# ─── single state alone exceeds the cell limit (task 12) ─────────────────────
def test_single_state_over_cell_limit_raises_actionable_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If one state's single-year request still busts the SIDRA cell cap, the
    parallel fetch must raise a clear, actionable RuntimeError (not a bare 400)."""

    def boom(*_a, **_k):
        raise client.SidraLimitExceeded("limite de valores excedido")

    monkeypatch.setattr(client, "_fetch_block", boom)
    with pytest.raises(RuntimeError, match=r"exceeds.*SIDRA cell limit"):
        client._fetch_by_state_parallel("289", [2020], "193", ["3405", "3406", "3407"])


def test_fetch_one_state_emits_state_error_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing state emits a `state_error` event (with the UF) before propagating,
    so `embrapa monitor` shows which state broke."""
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        client.observability, "emit", lambda event, **fields: events.append((event, fields))
    )
    monkeypatch.setattr(
        client, "_fetch_block", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("kaboom"))
    )
    with pytest.raises(RuntimeError, match="kaboom"):
        client._fetch_one_state(29, "289", [2020], "193", ["3405"])  # 29 = BA

    error_events = [f for ev, f in events if ev == "state_error"]
    assert len(error_events) == 1
    assert error_events[0]["state"] == "BA"  # UF acronym, not the numeric code
    assert error_events[0]["state_code"] == 29


def test_fetch_one_state_emits_start_and_end_on_success(
    monkeypatch: pytest.MonkeyPatch, sidra_payload: list[dict]
) -> None:
    """A successful state emits state_start then state_end with a row count."""
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        client.observability, "emit", lambda event, **fields: events.append((event, fields))
    )
    # One payload with a header row + one data row → rows == 1.
    monkeypatch.setattr(client, "_fetch_block", lambda *_a, **_k: [sidra_payload])
    client._fetch_one_state(29, "289", [2020], "193", ["3405"])

    names = [ev for ev, _ in events]
    assert names == ["state_start", "state_end"]
    assert dict(events[1][1])["rows"] == 1  # header row excluded from the count


@responses.activate
def test_list_ibge_periods_sorts_and_dedups() -> None:
    responses.add(
        method=responses.GET,
        url="https://servicodados.ibge.gov.br/api/v3/agregados/289/periodos",
        json=[{"id": "1990"}, {"id": "1986"}, {"id": "2020"}, {"id": "1986"}],
        status=200,
    )
    years = discover.list_ibge_periods("289")
    assert years == [1986, 1990, 2020]
