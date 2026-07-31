# Freek Participant Study

Dutch Streamlit application for a participant study about humour and style.

The project is being delivered in the checkpoints described in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md). Checkpoint 11 adds one local
and GitHub Actions quality gate plus an isolated, test-only staging contract.

## Requirements

- Python 3.11 or newer
- `pip`

## Local Setup

Run all commands from this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Run The App

```bash
streamlit run streamlit_app.py
```

Streamlit prints the local URL, normally <http://localhost:8501>.

The temporary checkpoint-2 stimulus preview is available at:

<http://localhost:8501/?preview=1>

Change the port in this URL if Streamlit selected another local port.

## Checkpoint 3 Test Links

These links are test-only and may safely be committed to the repository:

1. `?session=test-01-DU8NXu1m`
2. `?session=test-02-CVM5_s67`
3. `?session=test-03-viwspebC`
4. `?session=test-04-es8fvhYW`
5. `?session=test-05-SIhk_boI`
6. `?session=test-06-fDpGFu6p`
7. `?session=test-07-SNKbCw41`
8. `?session=test-08-bxdyKo5y`
9. `?session=test-09-rHQtzmEl`
10. `?session=test-10-KvPvblxx`

Append one of these paths to the local app URL. For example:

<http://localhost:8501/?session=test-01-DU8NXu1m>

## Automated Checks

Run the same complete gate used by GitHub Actions:

```bash
python scripts/run_quality_gate.py
```

It checks Ruff formatting and linting, Python compilation, primary and staging
data contracts, unit and Streamlit flow tests, and a real process-level startup
health check. The path-scoped workflow lives at
`.github/workflows/freek-study-quality.yml` in the repository root.

With the application running, verify Streamlit's process health endpoint:

```bash
curl --fail http://localhost:8501/_stcore/health
```

The expected response is `ok`.

## Checkpoint 9 Data Export

Generate both analysis CSV files from durable local progress:

```bash
python scripts/export_results.py
```

The command writes `data/runtime/exports/participants.csv` and
`data/runtime/exports/ratings.csv`. Optional `--progress`, `--sessions`,
`--stimuli`, and `--output` arguments support isolated staging and test data.
The exact row grain, fields, repeated-test policy, and validation rules are
versioned in [`EXPORT_SCHEMA.md`](EXPORT_SCHEMA.md).

Before analysis, filter `is_test = false` and normally
`submission_status = submitted`.

## Checkpoint 10 Admin Page

The hidden local route is:

<http://localhost:8501/?admin=1>

Configure the password outside Git with either:

```toml
# .streamlit/secrets.toml
admin_password = "use-a-long-unique-password"
```

or the `FREEK_STUDY_ADMIN_PASSWORD` environment variable. The committed
`.streamlit/secrets.toml.example` documents the key; `.streamlit/secrets.toml`
is ignored and must never be committed.

The dashboard can switch between real participants, test sessions, and all
saved sessions, and between definitive submissions or all saved states. It
defaults to definitive submissions so provisional autosaves do not influence
research means. It shows completion totals, rating counts, both overall rating
means, assigned-versus-rated group exposure, per-variant means, read-only
answers, and two downloads that follow the current selection.

## Checkpoint 11 Acceptance Test

1. Run `python scripts/run_quality_gate.py` locally.
2. Review the checkpoint pull request and its `Freek study quality gate` check.
3. Confirm a deliberately malformed staging registry fails validation.
4. Deploy the `staging` branch using [`STAGING.md`](STAGING.md).
5. Complete two different test links from desktop and mobile.
6. Review staging logs, admin totals, and both downloaded CSV files.
7. Confirm no real participant link is accepted by staging.

Development progress is stored in the ignored file
`data/runtime/progress.csv`. Set `FREEK_STUDY_PROGRESS_PATH` to use a different
local path. `FREEK_STUDY_SESSIONS_PATH` can point automated or staging runs to a
separate session registry. Production Google Sheets storage is added later
through the same storage contract.

The stimulus contract is documented in [`STUDY_SPEC.md`](STUDY_SPEC.md).

## Configuration

Shared Streamlit settings live in `.streamlit/config.toml`.

Local secrets will later live in `.streamlit/secrets.toml`. That file is ignored
by Git and must never be committed.

Staging coordinates, secrets, test procedure, and the temporary-storage warning
are documented in [`STAGING.md`](STAGING.md).
