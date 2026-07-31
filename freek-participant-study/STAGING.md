# Staging Deployment

Checkpoint 11 uses a long-lived `staging` branch and Streamlit Community Cloud.
Staging accepts only the ten links in `data/sessions.staging.csv`; the quality
gate fails if that registry contains a real participant session.

- Public app: <https://freek-participant-pilot.streamlit.app/>
- Admin: <https://freek-participant-pilot.streamlit.app/?admin=1>
- Example test link: <https://freek-participant-pilot.streamlit.app/?session=test-01-DU8NXu1m>

## Release Flow

1. Develop on a `codex/*` feature branch.
2. Run `python scripts/run_quality_gate.py` locally.
3. Open a pull request and require the `Freek study quality gate` check.
4. Merge an approved pull request into `staging` for participant testing.
5. Reconcile the repository branch history before selecting the production
   branch, then merge the frozen release only after staging acceptance.

Do not commit directly to `staging` or `main`. Configure both branches to require
a pull request and the quality-gate status check in GitHub branch protection.

The participant-study history currently descends from `master`. The repository's
default `main` branch has separate orphan history for a notebook workflow, so
GitHub cannot create a normal participant-study pull request to `main`. Draft PR
#2 therefore targets `master`. Resolve this branch split before checkpoint 12's
production release; do not use an unrelated-history merge as a shortcut.

## Community Cloud Coordinates

Create the staging app at <https://share.streamlit.io> with:

- Repository: `jorrytdejong/freek-de-jonge`
- Branch: `staging`
- Entrypoint: `freek-participant-study/streamlit_app.py`
- Python: `3.11`

In Advanced settings, add secrets with a unique staging admin password:

```toml
admin_password = "replace-with-a-long-staging-only-password"
FREEK_STUDY_SESSIONS_PATH = "freek-participant-study/data/sessions.staging.csv"
```

Never paste a production password or production data credential into staging.
The official deployment and secret-management instructions are:

- <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy>
- <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management>

## Checkpoint 12 Storage Migration

The existing checkpoint 11 staging deployment still uses disposable local CSV
storage. Before the final pilot, create a staging-only private Google Sheet and
add the `storage_backend` and `google_sheets` settings documented in
`.streamlit/secrets.toml.example`. Keep
`FREEK_STUDY_SESSIONS_PATH = "freek-participant-study/data/sessions.staging.csv"`
so staging continues to accept test links only. Never point staging at the
production spreadsheet.

## Staging Acceptance

1. Confirm the app rejects a missing, unknown, and inactive link.
2. Complete two different test links on desktop and mobile.
3. Refresh midway and confirm autosave resumes while the app remains running.
4. Submit, reopen, and repeat one test link.
5. Open `?admin=1`, select `Testsessies` and `Ingediend`, and inspect totals.
6. Download both CSV files and compare their row counts with the dashboard.
7. Review Community Cloud logs for exceptions.
8. Reboot the staging app and confirm Google Sheets autosave still resumes.
