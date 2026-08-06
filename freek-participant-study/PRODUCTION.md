# ACL-1 Production Operations

Do not distribute real participant URLs until the staging checklist passes.

## Private links

Generate the 25 balanced private URLs only once:

```bash
python scripts/build_acl_study_data.py \
  --production-registry data/private/acl_sessions.production.csv \
  --production-urls data/private/acl_participant_urls.production.csv \
  --base-url https://freek-participant-pilot.streamlit.app/
```

The command refuses to overwrite either output. Both files are ignored by Git.
Back them up in the protected research folder. The registry contains ten test
links plus 25 real links; the URL file contains only the 25 real links.

Paste the complete registry into the private `sessions_csv` Streamlit secret.
Never expose `assigned_item_ids` to participants.

## Durable storage

Use a production-only Google Sheet and a worksheet such as `acl_progress`.
Configure `storage_backend = "google_sheets"`, the sheet URL, worksheet,
service-account credentials, admin password, and `sessions_csv` through
Streamlit secrets. Never reuse the staging sheet.

## Release checklist

1. Freeze `data/acl_jokes.csv`, the private registry, and study version.
2. Run the complete quality gate on the exact release commit.
3. Pass every item in `STAGING.md`.
4. Deploy production with its separate sheet and private registry.
5. Complete one included test link and confirm autosave, submission, admin, and
   exports.
6. Check that test data is excluded by the admin's real-participant filter.
7. Back up the private registry and raw progress sheet.
8. Only then distribute the numbered participant URLs.

## Interruption and recovery

Participants resume by reopening the same URL. For an operational incident,
stop recruitment, preserve the original sheet, export a raw backup, rehearse
recovery against a new private sheet, and switch production only after resume
and submission tests pass. Never edit or delete the only raw copy.

To deactivate a link, change its registry row to `active=false`, replace the
`sessions_csv` secret, and reboot. Preserve both the row and its responses.

At study closure, deactivate all real links, create final raw and analysis
backups, restrict sheet access, rotate credentials, and record participant and
submission counts.
