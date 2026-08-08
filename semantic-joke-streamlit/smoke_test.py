from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def main() -> None:
    app_path = Path(__file__).with_name("streamlit_app.py")
    app = AppTest.from_file(str(app_path))
    app.run(timeout=10)
    if app.exception:
        messages = "\n".join(str(exception.value) for exception in app.exception)
        raise RuntimeError(f"Streamlit smoke test failed:\n{messages}")
    print("Streamlit smoke test passed.")


if __name__ == "__main__":
    main()
