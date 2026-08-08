"""Small, dependency-free health contract for local and deployed checks."""

from app.config import APP_VERSION, STUDY_VERSION


def health_snapshot() -> dict[str, str]:
    """Return stable application metadata for health checks."""
    return {
        "status": "ok",
        "app_version": APP_VERSION,
        "study_version": STUDY_VERSION,
    }
