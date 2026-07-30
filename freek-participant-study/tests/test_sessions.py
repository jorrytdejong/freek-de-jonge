import csv
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from app.assignment import assignment_fingerprint, build_assignment
from app.sessions import (
    EXPECTED_TEST_SESSIONS,
    ParticipantSession,
    SessionAccessStatus,
    SessionValidationError,
    load_sessions,
    resolve_session,
)
from app.stimuli import load_stimuli


class SessionRegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.groups = load_stimuli()
        cls.group_ids = {group.group_id for group in cls.groups}
        cls.sessions = load_sessions(cls.group_ids)

    def test_registry_contains_ten_active_test_sessions(self) -> None:
        active_tests = [
            session
            for session in self.sessions.values()
            if session.active and session.is_test
        ]
        self.assertEqual(len(active_tests), EXPECTED_TEST_SESSIONS)

    def test_group_exposure_is_balanced(self) -> None:
        exposure = Counter(
            group_id
            for session in self.sessions.values()
            for group_id in session.assignment_groups
        )

        self.assertEqual(set(exposure), self.group_ids)
        self.assertLessEqual(max(exposure.values()) - min(exposure.values()), 1)

    def test_assignment_is_stable_and_complete(self) -> None:
        session = next(iter(self.sessions.values()))

        first = build_assignment(session, self.groups)
        second = build_assignment(session, self.groups)

        self.assertEqual(first, second)
        self.assertEqual(assignment_fingerprint(first), assignment_fingerprint(second))
        self.assertEqual(len(first.groups), 5)
        self.assertTrue(all(len(group.variant_ids) == 8 for group in first.groups))
        self.assertTrue(
            all(
                len(set(group.variant_ids)) == len(group.variant_ids)
                for group in first.groups
            )
        )

    def test_session_access_states(self) -> None:
        active_session = next(iter(self.sessions.values()))
        inactive_session = ParticipantSession(
            session_id="inactive-demo",
            is_test=True,
            active=False,
            assignment_groups=active_session.assignment_groups,
            created_at=active_session.created_at,
            notes="",
        )
        registry = {**self.sessions, inactive_session.session_id: inactive_session}

        self.assertEqual(
            resolve_session(None, registry).status,
            SessionAccessStatus.MISSING,
        )
        self.assertEqual(
            resolve_session("unknown-link", registry).status,
            SessionAccessStatus.UNKNOWN,
        )
        self.assertEqual(
            resolve_session(inactive_session.session_id, registry).status,
            SessionAccessStatus.INACTIVE,
        )
        valid = resolve_session(active_session.session_id, registry)
        self.assertEqual(valid.status, SessionAccessStatus.VALID)
        self.assertEqual(valid.session, active_session)

    def test_unknown_assignment_group_is_rejected(self) -> None:
        source_path = Path(__file__).resolve().parents[1] / "data" / "sessions.csv"
        with source_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["assignment_groups"] = "G01|G02|G03|G04|G99"

        with tempfile.TemporaryDirectory() as temp_directory:
            invalid_path = Path(temp_directory) / "sessions.csv"
            with invalid_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            with self.assertRaisesRegex(
                SessionValidationError,
                "onbekende groepen: G99",
            ):
                load_sessions(self.group_ids, invalid_path)


if __name__ == "__main__":
    unittest.main()
