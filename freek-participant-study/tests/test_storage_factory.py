import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.storage import (
    CSVProgressStorage,
    GoogleSheetsProgressStorage,
    StorageConfigurationError,
    create_progress_storage,
)


class StorageFactoryTest(unittest.TestCase):
    def test_csv_is_the_local_default(self) -> None:
        storage = create_progress_storage(environ={}, secrets={})

        self.assertIsInstance(storage, CSVProgressStorage)

    def test_csv_path_can_be_overridden(self) -> None:
        storage = create_progress_storage(
            environ={"FREEK_STUDY_PROGRESS_PATH": "/tmp/study-progress.csv"},
            secrets={},
        )

        self.assertEqual(storage.path, Path("/tmp/study-progress.csv"))

    @patch.object(GoogleSheetsProgressStorage, "from_service_account")
    def test_google_sheets_uses_private_streamlit_configuration(self, factory) -> None:
        factory.return_value = object()
        secrets = {
            "storage_backend": "google_sheets",
            "google_sheets": {
                "spreadsheet_url": "https://docs.google.com/spreadsheets/d/example",
                "worksheet": "progress",
                "credentials": {"type": "service_account", "client_email": "x"},
            },
        }

        result = create_progress_storage(environ={}, secrets=secrets)

        self.assertIs(result, factory.return_value)
        factory.assert_called_once_with(
            spreadsheet_url="https://docs.google.com/spreadsheets/d/example",
            worksheet_name="progress",
            credentials={"type": "service_account", "client_email": "x"},
        )

    @patch.object(GoogleSheetsProgressStorage, "from_service_account")
    def test_environment_credentials_support_non_streamlit_hosts(self, factory) -> None:
        factory.return_value = object()
        credentials = {"type": "service_account", "client_email": "x"}

        create_progress_storage(
            environ={
                "FREEK_STUDY_STORAGE": "google_sheets",
                "FREEK_STUDY_GOOGLE_SHEET_URL": "https://example.test/sheet",
                "FREEK_STUDY_GOOGLE_WORKSHEET": "production",
                "FREEK_STUDY_GOOGLE_CREDENTIALS_JSON": json.dumps(credentials),
            },
            secrets={"google_sheets": {}},
        )

        factory.assert_called_once_with(
            spreadsheet_url="https://example.test/sheet",
            worksheet_name="production",
            credentials=credentials,
        )

    def test_incomplete_google_configuration_is_rejected(self) -> None:
        with self.assertRaisesRegex(StorageConfigurationError, "credentials"):
            create_progress_storage(
                environ={"FREEK_STUDY_STORAGE": "google_sheets"},
                secrets={"google_sheets": {"spreadsheet_url": "https://example.test"}},
            )

    def test_unknown_backend_is_rejected(self) -> None:
        with self.assertRaisesRegex(StorageConfigurationError, "Unknown"):
            create_progress_storage(
                environ={"FREEK_STUDY_STORAGE": "sqlite"},
                secrets={},
            )


if __name__ == "__main__":
    unittest.main()
