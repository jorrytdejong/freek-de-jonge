import unittest
from datetime import UTC, datetime

from app.acl_admin import (
    build_condition_summary,
    build_overview,
    build_pipeline_style_summary,
)
from app.acl_assignment import build_assignment
from app.acl_exports import build_export_tables
from app.acl_ratings import ItemRatingValidationError, validate_item_response
from app.acl_sessions import load_sessions
from app.acl_stimuli import load_stimuli
from app.storage.base import SavedProgress


class ACLRatingAndExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stimuli = load_stimuli()
        cls.sessions = load_sessions(cls.stimuli)
        cls.session = next(iter(cls.sessions.values()))
        cls.assignment = build_assignment(cls.session, cls.stimuli)

    def test_all_four_dimensions_are_required(self) -> None:
        with self.assertRaises(ItemRatingValidationError) as raised:
            validate_item_response(
                item_id="T01-A1",
                display_position=1,
                raw_ratings={
                    "funniness": 3,
                    "freek_similarity": None,
                    "coherence": None,
                    "originality": None,
                },
            )
        self.assertEqual(len(raised.exception.messages), 3)

    def test_complete_submission_exports_24_item_rows_and_internal_factors(
        self,
    ) -> None:
        responses = {
            assigned.item_id: {
                "item_id": assigned.item_id,
                "display_position": assigned.display_position,
                "funniness": 2,
                "freek_similarity": 3,
                "coherence": 4,
                "originality": 5,
            }
            for assigned in self.assignment.items
        }
        submitted_at = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
        event = {
            "submission_id": f"{self.session.session_id}-submission-001",
            "submission_number": 1,
            "submitted_at": submitted_at.isoformat(),
            "study_version": "acl-1",
            "is_test": True,
            "profile": {"age": 38, "freek_familiarity": 4, "consent": True},
            "responses": responses,
            "final_comment": "Test.",
        }
        record = SavedProgress(
            session_id=self.session.session_id,
            study_version="acl-1",
            is_test=True,
            current_page="debrief",
            profile=event["profile"],
            responses=responses,
            drafts={},
            status="submitted",
            final_comment="Test.",
            submissions=(event,),
            created_at=submitted_at,
            updated_at=submitted_at,
        )
        tables = build_export_tables((record,), self.sessions, self.stimuli)
        self.assertEqual(len(tables.participants), 1)
        self.assertEqual(len(tables.ratings), 24)
        self.assertEqual(
            {row["condition_code"] for row in tables.ratings},
            {"A1", "A2", "C1", "C2", "E1", "E2"},
        )
        self.assertTrue(all(row["coherence"] == 4 for row in tables.ratings))
        overview = build_overview(tables)
        self.assertEqual(overview.means["originality"], 5.0)
        self.assertEqual(len(build_condition_summary(tables)), 6)
        self.assertEqual(len(build_pipeline_style_summary(tables)), 6)


if __name__ == "__main__":
    unittest.main()
