# Freek Participant Study — ACL Experiment

Dutch Streamlit application for the blinded `acl-1` humor-generation study.

## Locked design

- 90 accepted `gpt-5.6-terra` jokes: 15 topics × 6 conditions.
- Conditions: baseline, script opposition, and validated GTVH, each with Freek
  style guidance off and on.
- Every participant rates 12 jokes from 12 different topics.
- Every participant sees exactly two jokes from each condition.
- Every joke receives four required 1–5 ratings: funniness, Freek-style
  resemblance, coherence, and originality.
- Expected duration: approximately 10 minutes.

The old `pilot-1` modules and CSV files remain in the repository for historical
reproducibility. The deployed `streamlit_app.py` uses only the `app/acl_*`
modules and `data/acl_*` files.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
streamlit run streamlit_app.py
```

Example test link:

<http://localhost:8501/?session=acl-test-01-913a93e2>

Internal-only routes:

- Stimulus preview: <http://localhost:8501/?preview=1>
- Administration: <http://localhost:8501/?admin=1>

## Test links

1. `?session=acl-test-01-913a93e2`
2. `?session=acl-test-02-979d4f77`
3. `?session=acl-test-03-38452f51`
4. `?session=acl-test-04-cb9df523`
5. `?session=acl-test-05-d63af247`
6. `?session=acl-test-06-7227edfd`
7. `?session=acl-test-07-b5a26fc2`
8. `?session=acl-test-08-8c0b1676`
9. `?session=acl-test-09-030dcad5`
10. `?session=acl-test-10-86726b66`

## Validation

Run the same gate used for release acceptance:

```bash
python scripts/run_quality_gate.py
```

It validates formatting, linting, compilation, the 90-item bank, both test
registries, the mathematical assignment constraints, all unit and Streamlit
flow tests, and a process-level HTTP startup check.

## Data and exports

Local ACL progress is written to the ignored
`data/runtime/acl_progress.csv`. Generate validated analysis tables with:

```bash
python scripts/export_results.py
```

Outputs are written to `data/runtime/acl_exports/`. See
[`EXPORT_SCHEMA.md`](EXPORT_SCHEMA.md) for the exact columns.

Real participant tokens and URL files belong in the ignored `data/private/`
directory. See [`PRODUCTION.md`](PRODUCTION.md) before generating or deploying
them.
