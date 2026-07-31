#!/usr/bin/env python3
"""Run the exact quality gate used by GitHub Actions."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SOURCES = ("app", "scripts", "tests", "streamlit_app.py")


def run(label: str, *command: str) -> None:
    print(f"\n==> {label}", flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    run(
        "Formatting",
        sys.executable,
        "-m",
        "ruff",
        "format",
        "--check",
        *PYTHON_SOURCES,
    )
    run(
        "Linting",
        sys.executable,
        "-m",
        "ruff",
        "check",
        *PYTHON_SOURCES,
    )
    run(
        "Bytecode compilation",
        sys.executable,
        "-m",
        "compileall",
        "-q",
        *PYTHON_SOURCES,
    )
    run(
        "Primary study data",
        sys.executable,
        "scripts/validate_study.py",
    )
    run(
        "Test-only staging data",
        sys.executable,
        "scripts/validate_study.py",
        "--sessions",
        "data/sessions.staging.csv",
        "--require-test-only",
    )
    run(
        "Unit and Streamlit flow tests",
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
    )
    run(
        "Streamlit startup smoke test",
        sys.executable,
        "scripts/smoke_test.py",
    )
    print("\nQuality gate passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
