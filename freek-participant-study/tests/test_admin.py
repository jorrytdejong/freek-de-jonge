import csv
import unittest

from app.admin import (
    SCOPE_ALL,
    SCOPE_REAL,
    SCOPE_TEST,
    STATUS_ALL,
    STATUS_SUBMITTED,
    build_dimension_summary,
    build_group_summary,
    build_overview,
    build_variant_summary,
    filter_export_tables,
    filter_submission_status,
    verify_admin_password,
)
from app.exports import (
    PARTICIPANT_COLUMNS,
    RATING_COLUMNS,
    ExportTables,
    rows_to_csv,
)


def participant_row(
    session_id: str,
    *,
    is_test: bool,
    status: str,
) -> dict[str, object]:
    row = dict.fromkeys(PARTICIPANT_COLUMNS, "")
    row.update(
        {
            "export_schema_version": "1",
            "session_id": session_id,
            "study_version": "pilot-1",
            "is_test": is_test,
            "submission_status": status,
            "submission_count": 1 if status == "submitted" else 0,
            "age": 40,
            "freek_familiarity": 3,
            "consent": True,
            "assigned_group_ids": "G01|G02|G03|G04|G05",
            "assignment_seed": session_id,
            "assignment_fingerprint": f"fingerprint-{session_id}",
            "group_count": 5,
            "completed_group_count": 1,
            "created_at": "2026-07-31T12:00:00+00:00",
            "updated_at": "2026-07-31T12:05:00+00:00",
        }
    )
    return row


def rating_rows(
    session_id: str,
    *,
    is_test: bool,
    status: str,
    group_id: str,
    funniness: int,
    similarity: int,
) -> tuple[dict[str, object], ...]:
    rows = []
    for position, label in enumerate("ABCDEFGH", start=1):
        row = dict.fromkeys(RATING_COLUMNS, "")
        row.update(
            {
                "export_schema_version": "1",
                "session_id": session_id,
                "study_version": "pilot-1",
                "is_test": is_test,
                "submission_status": status,
                "age": 40,
                "freek_familiarity": 3,
                "assignment_seed": session_id,
                "assignment_fingerprint": f"fingerprint-{session_id}",
                "group_id": group_id,
                "group_position": 1,
                "group_title": f"Titel {group_id}",
                "variant_id": f"{group_id}-V{position:02d}",
                "variant_role": f"role-{position}",
                "joke_text": f"Tekst {position}",
                "display_label": label,
                "display_position": position,
                "funniness": funniness,
                "freek_similarity": similarity,
                "group_comment": "",
                "final_comment": "",
            }
        )
        rows.append(row)
    return tuple(rows)


class AdminSummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        participants = (
            participant_row(
                "real-session-01",
                is_test=False,
                status="submitted",
            ),
            participant_row(
                "test-session-01",
                is_test=True,
                status="in_progress",
            ),
        )
        ratings = (
            *rating_rows(
                "real-session-01",
                is_test=False,
                status="submitted",
                group_id="G01",
                funniness=5,
                similarity=2,
            ),
            *rating_rows(
                "test-session-01",
                is_test=True,
                status="in_progress",
                group_id="G02",
                funniness=1,
                similarity=4,
            ),
        )
        self.tables = ExportTables(participants, ratings)

    def test_password_requires_nonempty_configured_exact_match(self) -> None:
        self.assertTrue(verify_admin_password("correct", "correct"))
        self.assertFalse(verify_admin_password("wrong", "correct"))
        self.assertFalse(verify_admin_password("", "correct"))
        self.assertFalse(verify_admin_password("anything", None))

    def test_scope_filters_participants_and_corresponding_ratings(self) -> None:
        real = filter_export_tables(self.tables, SCOPE_REAL)
        test = filter_export_tables(self.tables, SCOPE_TEST)
        all_data = filter_export_tables(self.tables, SCOPE_ALL)

        self.assertEqual(len(real.participants), 1)
        self.assertEqual(len(real.ratings), 8)
        self.assertFalse(real.participants[0]["is_test"])
        self.assertEqual(len(test.participants), 1)
        self.assertEqual(len(test.ratings), 8)
        self.assertTrue(test.participants[0]["is_test"])
        self.assertEqual(all_data, self.tables)

    def test_overview_counts_and_compares_both_dimensions(self) -> None:
        overview = build_overview(self.tables)

        self.assertEqual(overview.session_count, 2)
        self.assertEqual(overview.submitted_count, 1)
        self.assertEqual(overview.in_progress_count, 1)
        self.assertEqual(overview.completed_group_count, 2)
        self.assertEqual(overview.rating_count, 16)
        self.assertEqual(overview.mean_funniness, 3.0)
        self.assertEqual(overview.mean_freek_similarity, 3.0)
        self.assertEqual(len(build_dimension_summary(self.tables)), 2)

    def test_submission_filter_defaults_analysis_to_final_answers(self) -> None:
        submitted = filter_submission_status(
            self.tables,
            STATUS_SUBMITTED,
        )
        all_statuses = filter_submission_status(self.tables, STATUS_ALL)

        self.assertEqual(len(submitted.participants), 1)
        self.assertEqual(len(submitted.ratings), 8)
        self.assertEqual(
            submitted.participants[0]["submission_status"],
            "submitted",
        )
        self.assertEqual(all_statuses, self.tables)

    def test_group_exposure_and_variant_means_match_rating_rows(self) -> None:
        group_summary = build_group_summary(self.tables)
        variant_summary = build_variant_summary(self.tables)

        self.assertEqual(len(group_summary), 5)
        self.assertEqual(group_summary[0]["Groep"], "G01")
        self.assertEqual(group_summary[0]["Toegewezen"], 2)
        self.assertEqual(group_summary[0]["Beoordeeld door"], 1)
        self.assertEqual(group_summary[0]["Beoordelingen"], 8)
        self.assertEqual(group_summary[0]["Gem. grappigheid"], 5.0)
        self.assertEqual(len(variant_summary), 16)
        self.assertEqual(variant_summary[0]["N"], 1)

    def test_dashboard_rating_total_matches_download_rows(self) -> None:
        selected = filter_export_tables(self.tables, SCOPE_TEST)
        overview = build_overview(selected)
        downloaded_rows = list(
            csv.DictReader(
                rows_to_csv(RATING_COLUMNS, selected.ratings).splitlines()
            )
        )

        self.assertEqual(overview.rating_count, len(downloaded_rows))


if __name__ == "__main__":
    unittest.main()
