import unittest

from app.health import health_snapshot


class HealthSnapshotTest(unittest.TestCase):
    def test_health_snapshot_is_ready(self) -> None:
        self.assertEqual(
            health_snapshot(),
            {
                "status": "ok",
                "app_version": "0.11.0",
                "study_version": "pilot-1",
            },
        )


if __name__ == "__main__":
    unittest.main()
