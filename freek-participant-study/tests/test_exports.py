import csv
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.assignment import build_assignment
from app.exports import (
    PARTICIPANT_COLUMNS,
    RATING_COLUMNS,
    ExportValidationError,
    build_export_tables,
    rows_to_csv,
    write_export_files,
)
from app.ratings import build_displayed_variants
from app.sessions import load_sessions
from app.stimuli import load_stimuli
from app.storage.base import SavedProgress


class ExportTablesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.groups = load_stimuli()
        cls.sessions = load_sessions(
            {group.group_id for group in cls.groups}
        )
        cls.session = cls.sessions["test-01-DU8NXu1m"]
        cls.assignment = build_assignment(cls.session, cls.groups)

    def complete_responses(self, *, score: int = 3):
        groups_by_id = {group.group_id: group for group in self.groups}
        responses = {}
        for assigned_group in self.assignment.groups:
            displayed = build_displayed_variants(
                assigned_group,
                groups_by_id[assigned_group.group_id],
            )
            responses[assigned_group.group_id] = {
                "group_id": assigned_group.group_id,
                "ratings": [
                    {
                        "display_label": variant.display_label,
                        "display_position": variant.display_position,
                        "variant_id": variant.variant_id,
                        "funniness": score,
                        "freek_similarity": 6 - score,
                    }
                    for variant in displayed
                ],
                "comment": f"Opmerking {assigned_group.group_id}",
            }
        return responses

    def saved_progress(
        self,
        *,
        responses=None,
        status="submitted",
        submissions=None,
    ) -> SavedProgress:
        now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
        profile = {
            "age": 41,
            "freek_familiarity": 4,
            "consent": True,
        }
        responses = responses if responses is not None else self.complete_responses()
        if submissions is None:
            submissions = (
                {
                    "submission_id": f"{self.session.session_id}-submission-001",
                    "submission_number": 1,
                    "submitted_at": now.isoformat(),
                    "study_version": "pilot-1",
                    "is_test": True,
                    "profile": profile,
                    "responses": responses,
                    "final_comment": "Algemene opmerking.",
                },
            )
        return SavedProgress(
            session_id=self.session.session_id,
            study_version="pilot-1",
            is_test=True,
            current_page="debrief" if status == "submitted" else "group-2",
            profile=profile,
            responses=responses,
            drafts={},
            status=status,
            final_comment="Algemene opmerking.",
            submissions=submissions,
            created_at=now,
            updated_at=now,
        )

    def test_submitted_session_produces_one_participant_and_40_ratings(self):
        tables = build_export_tables(
            [self.saved_progress()],
            self.sessions,
            self.groups,
        )

        self.assertEqual(len(tables.participants), 1)
        self.assertEqual(len(tables.ratings), 40)
        participant = tables.participants[0]
        self.assertEqual(tuple(participant), PARTICIPANT_COLUMNS)
        self.assertEqual(participant["completed_group_count"], 5)
        self.assertEqual(participant["submission_count"], 1)
        self.assertTrue(all(tuple(row) == RATING_COLUMNS for row in tables.ratings))

    def test_display_label_maps_to_deterministic_internal_variant(self):
        tables = build_export_tables(
            [self.saved_progress()],
            self.sessions,
            self.groups,
        )
        first_group = self.assignment.groups[0]
        version_a = next(
            row
            for row in tables.ratings
            if row["group_id"] == first_group.group_id
            and row["display_label"] == "A"
        )

        self.assertEqual(version_a["variant_id"], first_group.variant_ids[0])
        self.assertEqual(version_a["display_position"], 1)
        self.assertTrue(version_a["variant_role"])
        self.assertTrue(version_a["joke_text"])

    def test_latest_test_submission_is_the_analysis_snapshot(self):
        first = self.saved_progress().submissions[0]
        second = {
            **first,
            "submission_id": f"{self.session.session_id}-submission-002",
            "submission_number": 2,
            "submitted_at": "2026-07-31T12:05:00+00:00",
            "responses": self.complete_responses(score=5),
            "final_comment": "Tweede inzending.",
        }
        tables = build_export_tables(
            [self.saved_progress(submissions=(first, second))],
            self.sessions,
            self.groups,
        )

        self.assertEqual(tables.participants[0]["submission_count"], 2)
        self.assertEqual(
            tables.participants[0]["latest_submission_number"],
            2,
        )
        self.assertEqual(tables.ratings[0]["submission_number"], 2)
        self.assertEqual(tables.ratings[0]["funniness"], 5)

    def test_in_progress_session_exports_only_completed_groups(self):
        responses = self.complete_responses()
        one_response = {next(iter(responses)): next(iter(responses.values()))}
        record = self.saved_progress(
            responses=one_response,
            status="in_progress",
            submissions=(),
        )

        tables = build_export_tables([record], self.sessions, self.groups)

        self.assertEqual(tables.participants[0]["submission_status"], "in_progress")
        self.assertEqual(tables.participants[0]["completed_group_count"], 1)
        self.assertEqual(len(tables.ratings), 8)
        self.assertEqual(tables.ratings[0]["submission_id"], "")

    def test_unknown_saved_session_is_rejected(self):
        record = self.saved_progress()
        unknown = SavedProgress(
            **{**record.__dict__, "session_id": "unknown-session-123"}
        )
        with self.assertRaisesRegex(ExportValidationError, "absent from the registry"):
            build_export_tables([unknown], self.sessions, self.groups)

    def test_tampered_display_mapping_is_rejected(self):
        responses = self.complete_responses()
        first_response = next(iter(responses.values()))
        first_response["ratings"][0]["display_label"] = "H"
        record = self.saved_progress(
            responses=responses,
            status="in_progress",
            submissions=(),
        )
        with self.assertRaisesRegex(ExportValidationError, "displayed-version mapping"):
            build_export_tables([record], self.sessions, self.groups)

    def test_csv_round_trip_and_atomic_file_output(self):
        tables = build_export_tables(
            [self.saved_progress()],
            self.sessions,
            self.groups,
        )
        participant_csv = rows_to_csv(PARTICIPANT_COLUMNS, tables.participants)
        parsed = list(csv.DictReader(participant_csv.splitlines()))
        self.assertEqual(tuple(parsed[0]), PARTICIPANT_COLUMNS)
        self.assertEqual(parsed[0]["is_test"], "true")

        with tempfile.TemporaryDirectory() as directory:
            participants_path, ratings_path = write_export_files(
                tables,
                Path(directory),
            )
            with participants_path.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 1)
            with ratings_path.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 40)

    def test_csv_neutralizes_spreadsheet_formulas(self):
        text = rows_to_csv(
            ("comment",),
            ({"comment": "=HYPERLINK(\"unsafe\")"},),
        )
        parsed = next(csv.DictReader(text.splitlines()))
        self.assertEqual(parsed["comment"], "'=HYPERLINK(\"unsafe\")")


if __name__ == "__main__":
    unittest.main()
