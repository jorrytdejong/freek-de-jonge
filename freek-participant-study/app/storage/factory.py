"""Select the progress backend from environment variables or app secrets."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from app.storage.base import ProgressStorage
from app.storage.csv_storage import DEFAULT_PROGRESS_PATH, CSVProgressStorage
from app.storage.google_sheets import GoogleSheetsProgressStorage
from app.storage.shadow import ShadowProgressStorage
from app.storage.supabase import SupabaseProgressStorage


class StorageConfigurationError(RuntimeError):
    """Raised when a requested storage backend is incomplete or unknown."""


def _mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StorageConfigurationError(f"Missing or invalid {name} configuration.")
    return value


def create_progress_storage(
    *,
    environ: Mapping[str, str] | None = None,
    secrets: Mapping[str, object] | None = None,
) -> ProgressStorage:
    environment = environ if environ is not None else os.environ
    configured_secrets = secrets or {}
    backend = (
        environment.get(
            "FREEK_STUDY_STORAGE",
            str(configured_secrets.get("storage_backend", "csv")),
        )
        .strip()
        .lower()
    )

    if backend == "csv":
        return CSVProgressStorage(
            Path(
                environment.get(
                    "FREEK_STUDY_PROGRESS_PATH",
                    str(DEFAULT_PROGRESS_PATH),
                )
            )
        )
    if backend != "google_sheets":
        raise StorageConfigurationError(f"Unknown storage backend: {backend!r}.")

    section = _mapping(configured_secrets.get("google_sheets"), name="google_sheets")
    spreadsheet_url = environment.get(
        "FREEK_STUDY_GOOGLE_SHEET_URL",
        str(section.get("spreadsheet_url", "")),
    ).strip()
    worksheet_name = environment.get(
        "FREEK_STUDY_GOOGLE_WORKSHEET",
        str(section.get("worksheet", "progress")),
    ).strip()
    credentials_json = environment.get("FREEK_STUDY_GOOGLE_CREDENTIALS_JSON")
    if credentials_json:
        try:
            decoded_credentials = json.loads(credentials_json)
        except (json.JSONDecodeError, TypeError) as error:
            raise StorageConfigurationError(
                "FREEK_STUDY_GOOGLE_CREDENTIALS_JSON is invalid."
            ) from error
        credentials = _mapping(
            decoded_credentials,
            name="FREEK_STUDY_GOOGLE_CREDENTIALS_JSON",
        )
    else:
        credentials = _mapping(section.get("credentials"), name="Google credentials")
    if not spreadsheet_url or not worksheet_name:
        raise StorageConfigurationError(
            "Google Sheets requires spreadsheet_url and worksheet."
        )
    primary = GoogleSheetsProgressStorage.from_service_account(
        spreadsheet_url=spreadsheet_url,
        worksheet_name=worksheet_name,
        credentials=credentials,
    )
    shadow_section = configured_secrets.get("supabase_shadow")
    if (
        isinstance(shadow_section, Mapping)
        and str(shadow_section.get("enabled", "false")).lower() == "true"
    ):
        connection_string = environment.get(
            "SUPABASE_DB_URL",
            str(shadow_section.get("connection_string", "")),
        )
        return ShadowProgressStorage(primary, SupabaseProgressStorage(connection_string))
    return primary
