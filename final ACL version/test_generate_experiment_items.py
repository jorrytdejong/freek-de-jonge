from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import generate_experiment_items as generator


class ExperimentItemGeneratorTests(unittest.TestCase):
    def test_locked_design_has_ninety_unique_jobs(self) -> None:
        topics = generator.load_topics(generator.DEFAULT_TOPICS)["topics"]
        jobs = generator.build_jobs(topics)

        self.assertEqual(len(jobs), 90)
        self.assertEqual(len({job["job_id"] for job in jobs}), 90)
        self.assertEqual({job["condition_code"] for job in jobs}, set(generator.CONDITION_CODES))
        self.assertNotIn("de wachtrij bij de gemeente", {job["topic"] for job in jobs})

    def test_atomic_checkpoint_validates_and_detects_model_change(self) -> None:
        topics = generator.load_topics(generator.DEFAULT_TOPICS)["topics"]
        job = generator.build_jobs(topics)[0]
        result = {
            "pipeline_code": job["condition_code"],
            "request": {"topic": job["topic"]},
            "joke": "test joke",
        }
        item = {
            "schema_version": generator.SCHEMA_VERSION,
            "study_id": generator.STUDY_ID,
            **job,
            "model": "gpt-5.6-terra",
            "dry_run": False,
            "result": result,
            "result_sha256": generator.sha256(result),
        }

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "item.json"
            generator.atomic_write_json(path, item)
            payload = json.loads(path.read_text(encoding="utf-8"))
            valid, _ = generator.validate_item(
                payload, job, model="gpt-5.6-terra", dry_run=False
            )
            wrong_model, _ = generator.validate_item(
                payload, job, model="gpt-5.4-mini", dry_run=False
            )

        self.assertTrue(valid)
        self.assertFalse(wrong_model)


if __name__ == "__main__":
    unittest.main()
