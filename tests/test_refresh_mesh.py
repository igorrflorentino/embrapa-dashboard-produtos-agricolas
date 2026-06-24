"""Unit tests for the IBGE municipal mesh-seed generator
(``scripts/refresh_ibge_municipio_mesh.py``).

The generated seed (``ibge_municipio_mesh.csv``) underpins the ENTIRE sub-UF geography
cascade, yet ``scripts/`` otherwise has no automated coverage — a column swap or a
per-level dropout in ``_row()`` would pass the seed's dbt not_null/unique tests
silently. This loads the generator by path (``scripts/`` is not an importable package)
and exercises ``_row()`` against recorded-shape fixtures: both-branch, 2017-only, and
classic-only municípios, plus a bare record (TEST-3). No network — ``main()`` is
``__main__``-guarded, so importing the module never fetches.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MESH_PATH = Path(__file__).resolve().parents[1] / "scripts" / "refresh_ibge_municipio_mesh.py"
_spec = importlib.util.spec_from_file_location("refresh_ibge_municipio_mesh", _MESH_PATH)
assert _spec and _spec.loader
mesh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mesh)


def _municipio_both_branches() -> dict:
    """A município carrying BOTH the classic meso/micro and the 2017 inter/imediata
    branches (the normal case), shaped like the Localidades API response."""
    uf = {
        "id": 35,
        "sigla": "SP",
        "nome": "São Paulo",
        "regiao": {"id": 3, "sigla": "SE", "nome": "Sudeste"},
    }
    return {
        "id": 3550308,
        "nome": "São Paulo",
        "microrregiao": {
            "id": 35061,
            "nome": "São Paulo",
            "mesorregiao": {"id": 3515, "nome": "Metropolitana de São Paulo", "UF": uf},
        },
        "regiao-imediata": {
            "id": 350001,
            "nome": "São Paulo",
            "regiao-intermediaria": {"id": 3501, "nome": "São Paulo", "UF": uf},
        },
    }


def test_row_maps_all_sixteen_columns_for_a_both_branch_municipio():
    row = mesh._row(_municipio_both_branches())
    assert set(row.keys()) == set(mesh.FIELDNAMES)  # no column drift / dropout
    assert row["city_code"] == "3550308"
    assert row["city_name"] == "São Paulo"
    assert row["uf_code"] == "35"
    assert row["state_acronym"] == "SP"
    assert row["region_abbrev"] == "SE"
    assert row["meso_code"] == "3515"
    assert row["micro_code"] == "35061"
    assert row["intermediaria_code"] == "3501"
    assert row["imediata_code"] == "350001"


def test_row_falls_back_to_the_2017_branch_for_uf_when_classic_is_absent():
    """A município created after the classic meso/micro division froze (e.g. Boa
    Esperança do Norte/MT, 2023) has ONLY the 2017 branch; UF/região must still come
    out populated (from intermediária), with meso/micro left blank, not crashed."""
    m = {
        "id": 5101837,
        "nome": "Boa Esperança do Norte",
        # no 'microrregiao'
        "regiao-imediata": {
            "id": 510006,
            "nome": "Sorriso",
            "regiao-intermediaria": {
                "id": 5102,
                "nome": "Sinop",
                "UF": {
                    "id": 51,
                    "sigla": "MT",
                    "nome": "Mato Grosso",
                    "regiao": {"id": 5, "sigla": "CO", "nome": "Centro-Oeste"},
                },
            },
        },
    }
    row = mesh._row(m)
    assert row["state_acronym"] == "MT"  # UF resolved from the 2017 branch
    assert row["region_abbrev"] == "CO"
    assert row["meso_code"] == "" and row["micro_code"] == ""  # classic blank, not a crash
    assert row["imediata_code"] == "510006"
    assert row["intermediaria_code"] == "5102"


def test_row_handles_a_classic_only_municipio_without_the_2017_branch():
    m = {
        "id": 1234567,
        "nome": "Teste",
        "microrregiao": {
            "id": 99001,
            "nome": "Micro",
            "mesorregiao": {
                "id": 9901,
                "nome": "Meso",
                "UF": {
                    "id": 99,
                    "sigla": "ZZ",
                    "nome": "Zeta",
                    "regiao": {"id": 9, "sigla": "NN", "nome": "Norte"},
                },
            },
        },
        # no 'regiao-imediata'
    }
    row = mesh._row(m)
    assert row["state_acronym"] == "ZZ"
    assert row["meso_code"] == "9901" and row["micro_code"] == "99001"
    assert row["intermediaria_code"] == "" and row["imediata_code"] == ""  # 2017 blank


def test_row_never_raises_on_a_bare_municipio():
    """The defensive ``.get`` chain must degrade to blanks, never KeyError — except the
    mandatory ``id`` (every Localidades record carries one)."""
    row = mesh._row({"id": 9999999})
    assert row["city_code"] == "9999999"
    assert row["state_acronym"] == ""
    assert row["meso_code"] == "" and row["imediata_code"] == ""
