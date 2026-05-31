"""Tests for the Comex Stat CSV client — parsing/filtering offline, HTTP mocked.

The CSV shape is pinned from the live validation (2026-05-30): ';'-separated,
latin-1, EXP has 11 columns, IMP adds VL_FRETE/VL_SEGURO, the product filter is
column-precise on CO_NCM (a substring match would false-hit country code 445
for chapter 44).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import responses

from embrapa_commodities.comex import client

# Header + rows mirroring the real export file. Row 3 (NCM 16024900, country
# 445) and row 4 (NCM 84139190, country 445) must be dropped — and crucially
# country 445 must NOT make them match chapter 44.
EXP_CSV = (
    '"CO_ANO";"CO_MES";"CO_NCM";"CO_UNID";"CO_PAIS";"SG_UF_NCM";"CO_VIA";"CO_URF";'
    '"QT_ESTAT";"KG_LIQUIDO";"VL_FOB"\n'
    '"2023";"02";"08012100";"10";"589";"AC";"07";"0230154";251580;251580;257813\n'
    '"2023";"11";"44072920";"16";"245";"RO";"01";"0917800";42;46165;41176\n'
    '"2023";"08";"16024900";"10";"445";"PA";"01";"0217800";5;5;100\n'
    '"2023";"03";"84139190";"10";"445";"RJ";"04";"0817700";107365;5;20\n'
)

# Import file: same 11 columns + VL_FRETE;VL_SEGURO.
IMP_CSV = (
    '"CO_ANO";"CO_MES";"CO_NCM";"CO_UNID";"CO_PAIS";"SG_UF_NCM";"CO_VIA";"CO_URF";'
    '"QT_ESTAT";"KG_LIQUIDO";"VL_FOB";"VL_FRETE";"VL_SEGURO"\n'
    '"2023";"02";"08012200";"10";"160";"SP";"01";"0817800";21;21;899;75;12\n'
    '"2023";"12";"62129000";"11";"160";"SP";"01";"0817800";33692;3295;29555;453;12\n'
)

NCM_CODES = {"08012100", "08012200"}
CHAPTER_CODES = {"44"}


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="latin-1")
    return str(path)


def test_read_filtered_keeps_castanha_and_chapter44_only(tmp_path: Path) -> None:
    path = _write(tmp_path, "EXP_2023.csv", EXP_CSV)
    df = client._read_filtered(path, NCM_CODES, CHAPTER_CODES)
    assert set(df["CO_NCM"]) == {"08012100", "44072920"}


def test_read_filtered_does_not_falsematch_country_code_on_chapter(tmp_path: Path) -> None:
    """Country code 445 must not be read as chapter 44 — the filter is on CO_NCM."""
    path = _write(tmp_path, "EXP_2023.csv", EXP_CSV)
    df = client._read_filtered(path, NCM_CODES, CHAPTER_CODES)
    assert "16024900" not in set(df["CO_NCM"])  # country 445, chapter 16
    assert "84139190" not in set(df["CO_NCM"])  # country 445, chapter 84


def test_read_filtered_preserves_zero_padding_and_strings(tmp_path: Path) -> None:
    path = _write(tmp_path, "EXP_2023.csv", EXP_CSV)
    df = client._read_filtered(path, NCM_CODES, CHAPTER_CODES)
    row = df[df["CO_NCM"] == "08012100"].iloc[0]
    assert row["CO_MES"] == "02"  # zero-padded month kept as string
    assert row["VL_FOB"] == "257813"


def test_read_filtered_export_gets_union_columns_with_null_import_only(tmp_path: Path) -> None:
    path = _write(tmp_path, "EXP_2023.csv", EXP_CSV)
    df = client._read_filtered(path, NCM_CODES, CHAPTER_CODES)
    assert list(df.columns) == client.SOURCE_COLUMNS  # reindexed to the 13-col union
    assert df["VL_FRETE"].isna().all()
    assert df["VL_SEGURO"].isna().all()


def test_read_filtered_import_keeps_freight_and_insurance(tmp_path: Path) -> None:
    path = _write(tmp_path, "IMP_2023.csv", IMP_CSV)
    df = client._read_filtered(path, NCM_CODES, CHAPTER_CODES)
    assert set(df["CO_NCM"]) == {"08012200"}  # 62129000 (chapter 62) dropped
    row = df.iloc[0]
    assert row["VL_FRETE"] == "75"
    assert row["VL_SEGURO"] == "12"


def test_read_filtered_empty_when_no_products_match(tmp_path: Path) -> None:
    csv = (
        '"CO_ANO";"CO_MES";"CO_NCM";"CO_UNID";"CO_PAIS";"SG_UF_NCM";"CO_VIA";"CO_URF";'
        '"QT_ESTAT";"KG_LIQUIDO";"VL_FOB"\n'
        '"2023";"08";"16024900";"10";"445";"PA";"01";"0217800";5;5;100\n'
    )
    path = _write(tmp_path, "EXP_2023.csv", csv)
    df = client._read_filtered(path, NCM_CODES, CHAPTER_CODES)
    assert df.empty
    assert list(df.columns) == client.SOURCE_COLUMNS


def test_fetch_flow_year_builds_url_and_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}

    def fake_download(url: str, dest_path: str) -> None:
        captured["url"] = url
        Path(dest_path).write_text(EXP_CSV, encoding="latin-1")

    monkeypatch.setattr(client, "_download_to_disk", fake_download)
    df = client.fetch_flow_year(
        "https://host/ncm/",
        "export",
        2023,
        ncm_codes=NCM_CODES,
        chapter_codes=CHAPTER_CODES,
    )
    assert captured["url"] == "https://host/ncm/EXP_2023.csv"
    assert set(df["CO_NCM"]) == {"08012100", "44072920"}


def test_fetch_flow_year_import_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_download(url: str, dest_path: str) -> None:
        captured["url"] = url
        Path(dest_path).write_text(IMP_CSV, encoding="latin-1")

    monkeypatch.setattr(client, "_download_to_disk", fake_download)
    client.fetch_flow_year(
        "https://host/ncm", "import", 2026, ncm_codes=NCM_CODES, chapter_codes=CHAPTER_CODES
    )
    assert captured["url"] == "https://host/ncm/IMP_2026.csv"


# ─── download HTTP handling (retry stripped via __wrapped__) ──────────────────
@responses.activate
def test_download_to_disk_writes_body(tmp_path: Path) -> None:
    responses.add(responses.GET, "https://host/EXP_2023.csv", body=EXP_CSV, status=200)
    dest = str(tmp_path / "out.csv")
    client._download_to_disk.__wrapped__("https://host/EXP_2023.csv", dest)  # type: ignore[attr-defined]
    assert Path(dest).read_text(encoding="latin-1") == EXP_CSV


@responses.activate
def test_download_to_disk_raises_transient_on_5xx(tmp_path: Path) -> None:
    responses.add(responses.GET, "https://host/EXP_2023.csv", status=503)
    with pytest.raises(client.ComexTransientError):
        client._download_to_disk.__wrapped__(  # type: ignore[attr-defined]
            "https://host/EXP_2023.csv", str(tmp_path / "out.csv")
        )


@responses.activate
def test_download_to_disk_raises_permanent_on_404(tmp_path: Path) -> None:
    responses.add(responses.GET, "https://host/EXP_2099.csv", status=404)
    with pytest.raises(client.ComexRequestError) as exc:
        client._download_to_disk.__wrapped__(  # type: ignore[attr-defined]
            "https://host/EXP_2099.csv", str(tmp_path / "out.csv")
        )
    assert not isinstance(exc.value, client.ComexTransientError)  # 404 is not retried


def test_ca_bundle_appends_intermediate_to_certifi() -> None:
    """The host omits its TLS intermediate, so we verify against certifi + the
    vendored Sectigo intermediate. The bundle must contain both and be cached."""
    import certifi

    path = client._ca_bundle()
    content = Path(path).read_text(encoding="ascii")
    assert client.SECTIGO_INTERMEDIATE_PEM.strip() in content  # vendored intermediate
    assert len(content) > len(
        Path(certifi.where()).read_text(encoding="ascii")
    )  # certifi roots too
    assert client._ca_bundle() == path  # cached, not rebuilt each call


def test_download_passes_verify_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression guard: the download must verify against the custom CA bundle,
    not requests' default — without it the gov.br host fails TLS verification."""
    captured: dict[str, object] = {}

    class _Resp:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, chunk_size):
            return iter([b"data"])

    def fake_get(url, **kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr(client.requests, "get", fake_get)
    client._download_to_disk.__wrapped__("https://host/EXP_2023.csv", str(tmp_path / "o.csv"))  # type: ignore[attr-defined]
    assert captured["verify"] == client._ca_bundle()


def test_download_wires_emit_retry_as_before_sleep() -> None:
    """Regression guard: the monitor hook must be wired into the retry policy."""
    assert client._download_to_disk.retry.before_sleep is client._emit_retry  # type: ignore[attr-defined]


def test_emit_retry_emits_event_with_file_basename(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        client.observability, "emit", lambda event, **kw: events.append((event, kw))
    )
    retry_state = SimpleNamespace(
        args=("https://host/ncm/EXP_2023.csv", "/tmp/x.csv"),
        kwargs={},
        attempt_number=2,
        outcome=SimpleNamespace(exception=lambda: client.ComexTransientError("HTTP 503")),
    )
    client._emit_retry(retry_state)
    assert len(events) == 1
    event, kw = events[0]
    assert event == "retry"
    assert kw["series"] == "EXP_2023.csv"
    assert kw["attempt"] == 2
    assert "503" in kw["reason"]
