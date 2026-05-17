"""Application Default Credentials (ADC) wrapper — no Colab dependency."""

from __future__ import annotations

import google.auth
from google.auth.credentials import Credentials


def get_credentials(project_id: str) -> tuple[Credentials, str]:
    """Return ADC credentials and the resolved project.

    Locally, run `gcloud auth application-default login` once.
    In CI (future) use Workload Identity Federation — the same call works.
    """
    credentials, detected_project = google.auth.default()
    return credentials, project_id or detected_project
