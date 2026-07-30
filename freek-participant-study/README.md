# Freek Participant Study

Dutch Streamlit application for a participant study about humour and style.

The project is being delivered in the checkpoints described in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md). Checkpoint 1 contains only a
reproducible application skeleton and start screen. Participant sessions and the
research flow are deliberately not active yet.

## Requirements

- Python 3.11 or newer
- `pip`

## Local Setup

Run all commands from this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run The App

```bash
streamlit run streamlit_app.py
```

Streamlit prints the local URL, normally <http://localhost:8501>.

## Verify Checkpoint 1

Run the dependency-free health test:

```bash
python -m unittest discover -s tests
```

With the application running, verify Streamlit's process health endpoint:

```bash
curl --fail http://localhost:8501/_stcore/health
```

The expected response is `ok`.

## Checkpoint 1 Acceptance Test

1. Open the local URL on a desktop browser.
2. Confirm the Dutch heading, ready status, disabled start button, and
   `pilot-1` version are visible.
3. Resize the browser to a narrow mobile width.
4. Confirm the text and button fit without horizontal scrolling or overlap.
5. Run the unit and HTTP health checks above.

## Configuration

Shared Streamlit settings live in `.streamlit/config.toml`.

Local secrets will later live in `.streamlit/secrets.toml`. That file is ignored
by Git and must never be committed.

