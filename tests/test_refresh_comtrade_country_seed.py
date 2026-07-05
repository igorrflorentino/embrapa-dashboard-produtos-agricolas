"""Tests for the COMTRADE country-seed refresh helper.

Guards the pt-BR preservation fix: `_load_existing_names` must read the curated
pt-BR `country_name` values back out of the existing seed so a refresh keeps them
instead of reverting to the English UN labels.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "refresh_comtrade_country_seed.py"
_spec = importlib.util.spec_from_file_location("refresh_comtrade_country_seed", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _write_seed(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["m49_code", "iso_a3", "country_name", "is_group"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def test_load_existing_names_reads_curated_ptbr(tmp_path, monkeypatch):
    seed = tmp_path / "comtrade_country.csv"
    _write_seed(
        seed,
        [
            {"m49_code": "76", "iso_a3": "BRA", "country_name": "Brasil", "is_group": "false"},
            {"m49_code": "0", "iso_a3": "", "country_name": "Mundo", "is_group": "true"},
        ],
    )
    monkeypatch.setattr(_mod, "SEED", seed)

    names = _mod._load_existing_names()

    # The curated pt-BR names round-trip (not the English "Brazil"/"World").
    assert names == {"76": "Brasil", "0": "Mundo"}


def test_load_existing_names_absent_seed_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "SEED", tmp_path / "does_not_exist.csv")
    assert _mod._load_existing_names() == {}
