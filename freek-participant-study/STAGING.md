# Staging Deployment

Checkpoint 11 uses a long-lived `staging` branch and Streamlit Community Cloud.
Staging accepts only the ten links in `data/sessions.staging.csv`; the quality
gate fails if that registry contains a real participant session.

## Release Flow

1. Develop on a `codex/*` feature branch.
2. Run `python scripts/run_quality_gate.py` locally.
3. Open a pull request and require the `Freek study quality gate` check.
4. Merge an approved pull request into `staging` for participant testing.
5. Merge the frozen release into `main` only after staging acceptance.

Do not commit directly to `staging` or `main`. Configure both branches to require
a pull request and the quality-gate status check in GitHub branch protection.

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

## Current Storage Limitation

Checkpoint 11 staging storage is intentionally temporary. Streamlit Community
Cloud's local filesystem is not the production data store and may reset when the
app restarts. Use staging only with test links. Checkpoint 12 connects the same
storage interface to Google Sheets before any real recruitment.

## Staging Acceptance

1. Confirm the app rejects a missing, unknown, and inactive link.
2. Complete two different test links on desktop and mobile.
3. Refresh midway and confirm autosave resumes while the app remains running.
4. Submit, reopen, and repeat one test link.
5. Open `?admin=1`, select `Testsessies` and `Ingediend`, and inspect totals.
6. Download both CSV files and compare their row counts with the dashboard.
7. Review Community Cloud logs for exceptions.
8. Reboot the staging app and confirm only disposable test data was affected.
