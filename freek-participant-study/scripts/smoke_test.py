#!/usr/bin/env python3
"""Start Streamlit and verify its HTTP health endpoint."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGING_SESSIONS = PROJECT_ROOT / "data" / "acl_sessions.staging.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local Streamlit startup and health smoke test."
    )
    parser.add_argument(
        "--sessions",
        type=Path,
        default=DEFAULT_STAGING_SESSIONS,
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def run_smoke_test(*, sessions_path: Path, timeout: float) -> None:
    port = available_port()
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    with (
        tempfile.TemporaryDirectory() as runtime_directory,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log,
    ):
        environment = {
            **os.environ,
            "FREEK_STUDY_ADMIN_PASSWORD": "ci-smoke-test-only",
            "FREEK_STUDY_PROGRESS_PATH": str(Path(runtime_directory) / "progress.csv"),
            "FREEK_STUDY_SESSIONS_PATH": str(sessions_path.resolve()),
        }
        command = (
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_app.py",
            "--server.headless=true",
            "--server.address=127.0.0.1",
            f"--server.port={port}",
            "--browser.gatherUsageStats=false",
        )
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(health_url, timeout=1) as response:
                        if response.status == 200 and response.read() == b"ok":
                            return
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.25)
            log.seek(0)
            output = log.read()[-4000:]
            raise RuntimeError(
                "Streamlit did not become healthy before the timeout.\n" + output
            )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main() -> int:
    args = parse_args()
    run_smoke_test(sessions_path=args.sessions, timeout=args.timeout)
    print("Streamlit startup smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
