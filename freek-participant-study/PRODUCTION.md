# Production Operations

Checkpoint 12 makes participant progress durable in a private Google Sheet. Do
not recruit real participants until every item in the release checklist passes.

## External Resources

Create two private spreadsheets, one for staging and one for production. In each
spreadsheet create a worksheet named `progress`. Never reuse either worksheet
for the other environment.

1. Enable the Google Sheets API in a Google Cloud project.
2. Create a service account and JSON key.
3. Share each spreadsheet with the service-account email as an editor.
4. Keep the JSON key only in Streamlit secrets or a local ignored secrets file.

The setup follows Streamlit's private Google Sheet guide:
<https://docs.streamlit.io/develop/tutorials/databases/private-gsheet>.

## Private Participant Registry

The repository is public, so real participant links must never be committed.
Generate 40 real links alongside the ten stable test links:

```bash
python scripts/generate_production_sessions.py --real-count 40
```

The command writes the ignored file
`data/private/sessions.production.csv` and refuses to overwrite it. Back up this
file in the protected research folder. Paste its complete contents into the
`sessions_csv` multiline Streamlit secret. Use the committed staging registry
only in the staging app.

## Production Secrets

Start from `.streamlit/secrets.toml.example`. Production requires:

- a new production-only `admin_password`;
- `storage_backend = "google_sheets"`;
- the private production registry in `sessions_csv`;
- the production spreadsheet URL and worksheet name;
- the Google service-account fields under `google_sheets.credentials`.

Streamlit stores deployment secrets outside Git. After changing them, reboot
the app and test one of the included test links before inviting participants.

## Release Checklist

1. Resolve the repository's `main`/`master` history split through a reviewed
   integration pull request and protect the selected production branch.
2. Run `python scripts/run_quality_gate.py` on the exact release commit.
3. Deploy staging from `staging` with its own spreadsheet and credentials.
4. Complete a test link, reboot staging, and confirm the autosave resumes.
5. Deploy production from the protected production branch with production
   secrets and a separate sheet.
6. Confirm staging data does not appear in production or vice versa.
7. Run a final pilot with two or three people using production test links.
8. Download and inspect raw and analysis backups.
9. Record acceptance in `CHANGELOG.md`, then tag the exact commit as
   `freek-study-pilot-1`.

The release tag is deliberately created only after the final human pilot, not
merely because the software checks pass.

## Raw Backup

For a production Google Sheet, set the following local environment variables:

```text
FREEK_STUDY_STORAGE=google_sheets
FREEK_STUDY_GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/.../edit
FREEK_STUDY_GOOGLE_WORKSHEET=progress
FREEK_STUDY_GOOGLE_CREDENTIALS_JSON={...service account JSON...}
```

Then run:

```bash
python scripts/backup_progress.py
python scripts/export_results.py
```

The first command writes the complete raw snapshots to the ignored
`data/private/backups` directory. The admin downloads provide validated
analysis tables. Store dated copies in the protected research folder daily
during recruitment and once immediately after closure.

## Recovery

1. Stop recruitment and save the affected sheet unchanged.
2. Download a raw backup and verify its header matches the storage contract.
3. Create a new private spreadsheet and worksheet rather than editing damaged
   rows in place.
4. Restore the latest verified raw snapshot under supervision, point staging at
   the replacement sheet, and rehearse resume, submission, admin, and export.
5. Only then update production secrets and reopen recruitment.

Never delete the original sheet or overwrite the only backup during recovery.

## Link Deactivation

To deactivate one link, change its private registry row from `active=true` to
`active=false`, replace the `sessions_csv` secret, and reboot the production
app. Preserve the row and its progress; do not delete it. Verify that the link
shows the inactive message while another test link remains usable.

## Study Closure

1. Change every real registry row to `active=false` and update production
   secrets.
2. Reboot and verify a real link cannot enter the study.
3. Create final raw and analysis backups and record their timestamps.
4. Restrict spreadsheet access, rotate or revoke the service-account key, and
   retain data according to the approved research policy.
5. Record the closing date, release tag, study version, and final participant
   counts in `CHANGELOG.md`.
