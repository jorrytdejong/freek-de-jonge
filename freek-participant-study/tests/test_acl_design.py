import unittest
from collections import Counter

from app.acl_assignment import assignment_fingerprint, build_assignment
from app.acl_config import CONDITION_CODES
from app.acl_sessions import load_sessions
from app.acl_stimuli import load_stimuli
from scripts.build_acl_study_data import (
    assignment_item_ids,
    validate_assignment_matrix,
)


class ACLDesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stimuli = load_stimuli()
        cls.sessions = load_sessions(cls.stimuli)

    def test_locked_bank_contains_15_topics_by_6_conditions(self) -> None:
        self.assertEqual(len(self.stimuli), 90)
        self.assertEqual(
            Counter(item.condition_code for item in self.stimuli),
            Counter({condition: 15 for condition in CONDITION_CODES}),
        )
        self.assertEqual(
            set(Counter(item.topic_id for item in self.stimuli).values()), {6}
        )
        self.assertEqual({item.model for item in self.stimuli}, {"gpt-5.6-terra"})

    def test_each_staging_link_has_the_preregistered_within_person_design(self) -> None:
        fingerprints = set()
        for session in self.sessions.values():
            assignment = build_assignment(session, self.stimuli)
            fingerprints.add(assignment_fingerprint(assignment))
            assigned = {
                item.item_id: item
                for item in self.stimuli
                if item.item_id in session.assigned_item_ids
            }
            self.assertEqual(len(assignment.items), 12)
            self.assertEqual(len({item.topic_id for item in assigned.values()}), 12)
            self.assertEqual(
                Counter(item.condition_code for item in assigned.values()),
                Counter({condition: 2 for condition in CONDITION_CODES}),
            )
        self.assertEqual(len(fingerprints), len(self.sessions))

    def test_25_participant_matrix_is_exactly_balanced(self) -> None:
        matrix = assignment_item_ids(25, seed=20260806)
        validate_assignment_matrix(matrix)
        topic_exposure = Counter(
            item_id.split("-")[0] for row in matrix for item_id in row
        )
        condition_exposure = Counter(
            item_id.split("-")[1] for row in matrix for item_id in row
        )
        item_exposure = Counter(item_id for row in matrix for item_id in row)
        self.assertEqual(set(topic_exposure.values()), {20})
        self.assertEqual(set(condition_exposure.values()), {50})
        self.assertEqual(set(item_exposure.values()), {3, 4})


if __name__ == "__main__":
    unittest.main()
