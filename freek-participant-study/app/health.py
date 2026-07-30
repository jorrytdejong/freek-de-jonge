"""Small, dependency-free health contract for local and deployed checks."""

APP_VERSION = "0.1.0"
STUDY_VERSION = "pilot-1"


def health_snapshot() -> dict[str, str]:
    """Return stable application metadata for health checks."""
    return {
        "status": "ok",
        "app_version": APP_VERSION,
        "study_version": STUDY_VERSION,
    }

