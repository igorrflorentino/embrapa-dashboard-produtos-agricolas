"""Unit tests for the raw-zone primitive (core/raw.py).

The two-phase pipelines delegate the verbatim-archive read/write here; these
tests pin the contract independently of any source: object path, provenance
metadata, parquet round-trip, and the absent-object → None freshness signal.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from embrapa_commodities.config import Settings
from embrapa_commodities.core import raw


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        gcs_bucket="test-bucket",
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame({"CO_NCM": ["08012100", "44072920"], "VL_FOB": ["10", "20"]})


def _parquet_bytes(frame: pd.DataFrame) -> bytes:
    buf = BytesIO()
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), buf, compression="snappy")
    return buf.getvalue()


# ─── raw_object_name ─────────────────────────────────────────────────────────
def test_raw_object_name_skeleton(settings: Settings) -> None:
    name = raw.raw_object_name(settings, "comex", "comex_flows", "EXP_2023")
    assert name == "raw/comex/comex_flows/EXP_2023.parquet"


def test_raw_object_name_honours_prefix(settings: Settings) -> None:
    settings.gcs_raw_prefix = "rawzone"
    assert raw.raw_object_name(settings, "ibge", "pevs", "x").startswith("rawzone/ibge/")


# ─── land_raw ────────────────────────────────────────────────────────────────
def test_land_raw_writes_parquet_and_returns_uri(settings: Settings, df: pd.DataFrame) -> None:
    gcs = MagicMock(name="gcs")
    blob = gcs.bucket.return_value.blob.return_value
    with patch("embrapa_commodities.core.raw.ensure_bucket") as ensure_bucket:
        uri = raw.land_raw(
            df,
            settings=settings,
            storage_client=gcs,
            source="comex",
            dataset="comex_flows",
            basename="EXP_2023",
        )
    ensure_bucket.assert_called_once_with(gcs, settings.gcs_bucket, settings.bq_location)
    gcs.bucket.return_value.blob.assert_called_once_with("raw/comex/comex_flows/EXP_2023.parquet")
    blob.upload_from_file.assert_called_once()
    assert uri == "gs://test-bucket/raw/comex/comex_flows/EXP_2023.parquet"


def test_land_raw_stamps_provenance_plus_auto_fields(settings: Settings, df: pd.DataFrame) -> None:
    gcs = MagicMock(name="gcs")
    blob = gcs.bucket.return_value.blob.return_value
    with patch("embrapa_commodities.core.raw.ensure_bucket"):
        raw.land_raw(
            df,
            settings=settings,
            storage_client=gcs,
            source="comex",
            dataset="comex_flows",
            basename="EXP_2023",
            provenance={"source_etag": "abc123", "source_url": "http://x/EXP_2023.csv"},
        )
    meta = blob.metadata
    assert meta["source_etag"] == "abc123"
    assert meta["source_url"] == "http://x/EXP_2023.csv"
    assert meta["source"] == "comex"  # auto-added
    assert meta["rows"] == "2"  # auto-added, coerced to str
    assert meta["fetched_at"].endswith("Z")  # auto-added UTC stamp


def test_land_raw_coerces_metadata_values_to_str(settings: Settings, df: pd.DataFrame) -> None:
    gcs = MagicMock(name="gcs")
    blob = gcs.bucket.return_value.blob.return_value
    with patch("embrapa_commodities.core.raw.ensure_bucket"):
        raw.land_raw(
            df,
            settings=settings,
            storage_client=gcs,
            source="comex",
            dataset="d",
            basename="b",
            provenance={"year": 2023},  # int → must be stored as str (GCS requires strings)
        )
    assert blob.metadata["year"] == "2023"


# ─── read_raw ────────────────────────────────────────────────────────────────
def test_read_raw_round_trips(settings: Settings, df: pd.DataFrame) -> None:
    gcs = MagicMock(name="gcs")
    gcs.bucket.return_value.blob.return_value.download_as_bytes.return_value = _parquet_bytes(df)
    out = raw.read_raw(
        gcs, settings=settings, source="comex", dataset="comex_flows", basename="EXP_2023"
    )
    pd.testing.assert_frame_equal(out, df)
    gcs.bucket.return_value.blob.assert_called_once_with("raw/comex/comex_flows/EXP_2023.parquet")


# ─── raw_provenance ──────────────────────────────────────────────────────────
def test_raw_provenance_returns_metadata(settings: Settings) -> None:
    gcs = MagicMock(name="gcs")
    gcs.bucket.return_value.get_blob.return_value.metadata = {"source_etag": "v1"}
    meta = raw.raw_provenance(
        gcs, settings=settings, source="comex", dataset="comex_flows", basename="EXP_2023"
    )
    assert meta == {"source_etag": "v1"}


def test_raw_provenance_none_when_absent(settings: Settings) -> None:
    gcs = MagicMock(name="gcs")
    gcs.bucket.return_value.get_blob.return_value = None
    meta = raw.raw_provenance(
        gcs, settings=settings, source="comex", dataset="comex_flows", basename="missing"
    )
    assert meta is None


# ─── land_raw_file (upload an already-written Parquet file) ───────────────────
def test_land_raw_file_uploads_from_filename_with_provenance(settings: Settings) -> None:
    gcs = MagicMock(name="gcs")
    blob = gcs.bucket.return_value.blob.return_value
    with patch("embrapa_commodities.core.raw.ensure_bucket") as ensure_bucket:
        uri = raw.land_raw_file(
            "/tmp/EXP_2023.parquet",
            settings=settings,
            storage_client=gcs,
            source="comex",
            dataset="comex_flows",
            basename="EXP_2023",
            provenance={"source_etag": "v9"},
            rows=42,
        )
    ensure_bucket.assert_called_once_with(gcs, settings.gcs_bucket, settings.bq_location)
    gcs.bucket.return_value.blob.assert_called_once_with("raw/comex/comex_flows/EXP_2023.parquet")
    blob.upload_from_filename.assert_called_once_with(
        "/tmp/EXP_2023.parquet", content_type="application/octet-stream"
    )
    assert blob.metadata["source_etag"] == "v9"
    assert blob.metadata["source"] == "comex"  # auto-added
    assert blob.metadata["rows"] == "42"  # explicit count, coerced to str
    assert blob.metadata["fetched_at"].endswith("Z")
    assert uri == "gs://test-bucket/raw/comex/comex_flows/EXP_2023.parquet"


def test_land_raw_file_omits_rows_when_unknown(settings: Settings) -> None:
    gcs = MagicMock(name="gcs")
    blob = gcs.bucket.return_value.blob.return_value
    with patch("embrapa_commodities.core.raw.ensure_bucket"):
        raw.land_raw_file(
            "/tmp/x.parquet",
            settings=settings,
            storage_client=gcs,
            source="comex",
            dataset="d",
            basename="b",
        )
    assert "rows" not in blob.metadata  # rows=None → not stamped


# ─── list_raw (enumerate the archived trail for --from-raw) ───────────────────
def test_list_raw_strips_prefix_suffix_sorts_and_filters(settings: Settings) -> None:
    gcs = MagicMock(name="gcs")

    def _blob(name: str) -> MagicMock:
        b = MagicMock()
        b.name = name
        return b

    gcs.list_blobs.return_value = [
        _blob("raw/bcb/inflation/2024-02.parquet"),
        _blob("raw/bcb/inflation/2024-01.parquet"),
        _blob("raw/bcb/inflation/_SUCCESS"),  # non-parquet → filtered out
    ]

    out = raw.list_raw(gcs, settings=settings, source="bcb", dataset="inflation")

    assert out == ["2024-01", "2024-02"]  # prefix+suffix stripped, sorted, non-parquet excluded
    gcs.list_blobs.assert_called_once_with("test-bucket", prefix="raw/bcb/inflation/")


def test_list_raw_empty_when_nothing_archived(settings: Settings) -> None:
    gcs = MagicMock(name="gcs")
    gcs.list_blobs.return_value = []
    assert raw.list_raw(gcs, settings=settings, source="bcb", dataset="inflation") == []
