"""Tests for GCS landing-zone helpers (Cloud Storage client fully mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from embrapa_commodities.gcp.storage import (
    _LIFECYCLE_RULES,
    _apply_protections,
    ensure_bucket,
    upload_dataframe_as_parquet,
)


def _make_bucket_mock(
    *,
    exists: bool = True,
    uniform_iam: bool = False,
    versioning: bool = False,
    lifecycle_rules: list | None = None,
):
    bucket = MagicMock()
    bucket.exists.return_value = exists
    bucket.iam_configuration.uniform_bucket_level_access_enabled = uniform_iam
    bucket.versioning_enabled = versioning
    bucket.lifecycle_rules = lifecycle_rules or []
    return bucket


def test_apply_protections_enables_missing_settings() -> None:
    """First call on a legacy bucket flips all three protections + lifecycle."""
    bucket = _make_bucket_mock(uniform_iam=False, versioning=False, lifecycle_rules=[])

    changed = _apply_protections(bucket)

    assert changed is True
    assert bucket.iam_configuration.uniform_bucket_level_access_enabled is True
    assert bucket.versioning_enabled is True
    assert bucket.lifecycle_rules == _LIFECYCLE_RULES


def test_apply_protections_is_idempotent() -> None:
    """A second call after the first applied protections must be a no-op."""
    bucket = _make_bucket_mock(
        uniform_iam=True,
        versioning=True,
        lifecycle_rules=_LIFECYCLE_RULES,
    )

    changed = _apply_protections(bucket)

    assert changed is False


def test_apply_protections_idempotent_against_gcs_normalized_rules() -> None:
    """GCS echoes lifecycle rules back with reordered keys / extra defaults.

    The semantic _rule_key comparison must still recognize them as unchanged so
    we don't patch() (and log "Updating protections") on every single ingestion.
    A naive dict-equality check would see the extra field and patch forever.
    """
    echoed = [
        {
            "action": dict(rule["action"]),
            # GCS-style echo: keys reordered + a benign field we never set.
            "condition": {**rule["condition"], "daysSinceNoncurrentTime": None},
        }
        for rule in _LIFECYCLE_RULES
    ]
    bucket = _make_bucket_mock(uniform_iam=True, versioning=True, lifecycle_rules=echoed)

    changed = _apply_protections(bucket)

    assert changed is False


def test_ensure_bucket_creates_when_missing() -> None:
    """ensure_bucket calls create_bucket() with protections pre-set for new buckets."""
    client = MagicMock()
    client.bucket.return_value = _make_bucket_mock(exists=False)

    ensure_bucket(client, "test-bucket", "us-central1")

    client.create_bucket.assert_called_once()
    created = client.create_bucket.call_args.args[0]
    assert created.iam_configuration.uniform_bucket_level_access_enabled is True
    assert created.versioning_enabled is True
    # `Bucket.lifecycle_rules` getter returns a generator; materialize it.
    assert list(created.lifecycle_rules) == _LIFECYCLE_RULES


def test_ensure_bucket_patches_existing_when_drifted() -> None:
    """Existing bucket with weak protections gets upgraded via patch()."""
    bucket = _make_bucket_mock(exists=True, uniform_iam=False)
    client = MagicMock()
    client.bucket.return_value = bucket

    ensure_bucket(client, "test-bucket", "us-central1")

    bucket.reload.assert_called_once()
    bucket.patch.assert_called_once()
    assert bucket.iam_configuration.uniform_bucket_level_access_enabled is True


def test_ensure_bucket_skips_patch_when_compliant() -> None:
    """Already-compliant bucket: no patch() call."""
    bucket = _make_bucket_mock(
        exists=True,
        uniform_iam=True,
        versioning=True,
        lifecycle_rules=_LIFECYCLE_RULES,
    )
    client = MagicMock()
    client.bucket.return_value = bucket

    ensure_bucket(client, "test-bucket", "us-central1")

    bucket.patch.assert_not_called()


def test_lifecycle_backups_prefix_deletes_at_365d() -> None:
    """`backups/` Gold snapshots must DELETE at 365d, not transition to ARCHIVE.

    The chain of snapshots is itself the retention; old snapshots referencing
    dropped Gold schemas are not restorable anyway, so paying Archive storage
    indefinitely is pure waste.
    """
    delete_rules = [
        r
        for r in _LIFECYCLE_RULES
        if r["action"]["type"] == "Delete" and "backups/" in r["condition"].get("matchesPrefix", [])
    ]
    assert len(delete_rules) == 1, "exactly one backups/ delete rule"
    assert delete_rules[0]["condition"]["age"] == 365


def test_lifecycle_landing_prefix_never_deletes_live_objects() -> None:
    """`landing/` is the audit trail — transitions to ARCHIVE but never deletes live objects.

    A regression that scoped the noncurrent-version delete to landing/ (or
    added a live-object delete to landing/) would silently destroy Bronze
    provenance. Pin the invariant explicitly.
    """
    landing_deletes = [
        r
        for r in _LIFECYCLE_RULES
        if r["action"]["type"] == "Delete" and "landing/" in r["condition"].get("matchesPrefix", [])
    ]
    assert landing_deletes == [], "landing/ must never have a live-object Delete rule"

    # The bucket-wide noncurrent-version cleanup is the only unscoped Delete.
    unscoped_deletes = [
        r
        for r in _LIFECYCLE_RULES
        if r["action"]["type"] == "Delete" and "matchesPrefix" not in r["condition"]
    ]
    assert len(unscoped_deletes) == 1
    assert unscoped_deletes[0]["condition"].get("isLive") is False


def test_lifecycle_transitions_are_prefix_scoped() -> None:
    """Every SetStorageClass transition is scoped to one retention group and
    never mixes them. The archive-trail group (landing/ + raw/, which share the
    same tiering) and the backups/ group have different lifecycles, so a rule
    must target a subset of one group only — otherwise a transition would bind
    to the wrong stream and flip its storage class unexpectedly."""
    archive_trail = {"landing/", "raw/"}
    backups = {"backups/"}
    for rule in _LIFECYCLE_RULES:
        if rule["action"]["type"] != "SetStorageClass":
            continue
        prefixes = rule["condition"].get("matchesPrefix")
        assert prefixes is not None, f"transition rule must be prefix-scoped: {rule}"
        prefix_set = set(prefixes)
        assert prefix_set <= archive_trail or prefix_set <= backups, (
            f"transition rule mixes retention groups: {prefixes}"
        )


def test_upload_dataframe_as_parquet_writes_via_blob() -> None:
    """Parquet upload uses upload_from_file (in-memory, no local disk)."""
    client = MagicMock()
    bucket = MagicMock()
    blob = MagicMock()
    client.bucket.return_value = bucket
    bucket.blob.return_value = blob

    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})

    uri = upload_dataframe_as_parquet(client, "bkt", "path/to/file.parquet", df)

    assert uri == "gs://bkt/path/to/file.parquet"
    bucket.blob.assert_called_once_with("path/to/file.parquet")
    blob.upload_from_file.assert_called_once()
