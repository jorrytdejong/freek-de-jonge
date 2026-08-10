import unittest
from collections import Counter

from app.acl_assignment import assignment_fingerprint, build_assignment
from app.acl_config import CONDITION_CODES, ITEMS_PER_PARTICIPANT
from app.acl_sessions import load_sessions
from app.acl_stimuli import load_stimuli
from scripts.build_acl_study_data import (
    assignment_item_ids,
    session_rows,
    validate_assignment_matrix,
)


class ACLDesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stimuli = load_stimuli()
        cls.sessions = load_sessions(cls.stimuli)

    def test_locked_bank_contains_20_topics_by_6_conditions(self) -> None:
        self.assertEqual(len(self.stimuli), 120)
        self.assertEqual(
            Counter(item.condition_code for item in self.stimuli),
            Counter({condition: 20 for condition in CONDITION_CODES}),
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
            self.assertEqual(len(assignment.items), ITEMS_PER_PARTICIPANT)
            self.assertEqual(
                len({item.topic_id for item in assigned.values()}),
                20,
            )
            self.assertEqual(
                sorted(Counter(item.topic_id for item in assigned.values()).values()),
                [1] * 20,
            )
            condition_counts = Counter(
                item.condition_code for item in assigned.values()
            )
            self.assertEqual(
                sorted(condition_counts[condition] for condition in CONDITION_CODES),
                [3, 3, 3, 3, 4, 4],
            )
        self.assertEqual(len(fingerprints), len(self.sessions))

    def test_every_recruitment_prefix_from_25_to_50_is_balanced(self) -> None:
        full_matrix = assignment_item_ids(50, seed=20260806)
        for participant_count in range(25, 51):
            matrix = full_matrix[:participant_count]
            validate_assignment_matrix(matrix)
            topic_exposure = Counter(
                item_id.split("-")[0] for row in matrix for item_id in row
            )
            condition_exposure = Counter(
                item_id.split("-")[1] for row in matrix for item_id in row
            )
            item_exposure = Counter(item_id for row in matrix for item_id in row)
            self.assertEqual(set(topic_exposure.values()), {participant_count})
            self.assertLessEqual(
                max(condition_exposure.values()) - min(condition_exposure.values()), 1
            )
            self.assertLessEqual(
                max(item_exposure.values()) - min(item_exposure.values()),
                1,
            )

    def test_selected_milestones_remain_tightly_balanced(self) -> None:
        matrix = assignment_item_ids(50, seed=20260806)
        for participant_count in (24, 30, 36, 42, 48):
            prefix = matrix[:participant_count]
            condition_exposure = Counter(
                item_id.split("-")[1] for row in prefix for item_id in row
            )
            item_exposure = Counter(item_id for row in prefix for item_id in row)
            self.assertEqual(len(set(condition_exposure.values())), 1)
            self.assertLessEqual(
                max(item_exposure.values()) - min(item_exposure.values()), 1
            )

    def test_50_participants_give_balanced_condition_and_item_exposure(self) -> None:
        matrix = assignment_item_ids(50, seed=20260806)
        condition_exposure = Counter(
            item_id.split("-")[1] for row in matrix for item_id in row
        )
        item_exposure = Counter(item_id for row in matrix for item_id in row)
        self.assertEqual(
            Counter(condition_exposure.values()), Counter({167: 4, 166: 2})
        )
        self.assertEqual(Counter(item_exposure.values()), Counter({8: 80, 9: 40}))

    def test_first_ten_production_links_are_reward_free(self) -> None:
        rows = session_rows(
            50,
            is_test=False,
            created_at=self.sessions[next(iter(self.sessions))].created_at,
            id_factory=lambda index: f"participant-{index:02d}-demo",
            seed=20260806,
            reward_free_count=10,
        )

        self.assertEqual(
            [row["reward_eligible"] for row in rows],
            ["false"] * 10 + ["true"] * 40,
        )


if __name__ == "__main__":
    unittest.main()
