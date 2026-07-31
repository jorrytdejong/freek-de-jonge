# Freek Participant Study

Dutch Streamlit application for a participant study about humour and style.

The project is being delivered in the checkpoints described in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md). Checkpoint 8 adds the final
review, editable answers, optional overall comment, atomic submission, repeated
test submissions, one-time real submissions, and a Dutch debrief.

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

Run the automated contract and Streamlit flow tests:

```bash
python -m unittest discover -s tests
```

With the application running, verify Streamlit's process health endpoint:

```bash
curl --fail http://localhost:8501/_stcore/health
```

The expected response is `ok`.

## Checkpoint 8 Acceptance Test

1. Complete all five joke groups with a test link.
2. Expand every group on the review page and inspect its ratings.
3. Choose `Bewerk jokegroep 2`, change a rating, and choose
   `Terug naar controle`.
4. Add an optional general comment.
5. Choose `Definitief indienen` and review the Dutch debrief.
6. Inspect the read-only submitted answers.
7. Choose `Nieuwe testinzending` and submit the test link again.
8. Confirm the debrief identifies the second test submission.
9. Run the automated and HTTP health checks above.

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
