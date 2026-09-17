from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
from generate_experiment_items import build_jobs, load_topics


class GenerationSmokeTest(unittest.TestCase):
    def test_locked_manifest_produces_120_jobs(self) -> None:
        topics_path = Path(__file__).parents[1] / "experiments" / "freek_style_topics_v2.json"
        topics = load_topics(topics_path)["topics"]
        jobs = build_jobs(topics)
        self.assertEqual(len(topics), 20)
        self.assertEqual(len(jobs), 120)
        self.assertEqual(len({job["job_id"] for job in jobs}), 120)


if __name__ == "__main__":
    unittest.main()
