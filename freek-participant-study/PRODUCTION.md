# ACL-1 Production Operations

Do not distribute real participant URLs until the staging checklist passes.

## Private links

Generate the 50 balanced private URLs only once:

```bash
python scripts/build_acl_study_data.py \
  --production-registry data/private/acl_sessions_50x20.production.csv \
  --production-urls data/private/acl_participant_urls_50x20.production.csv \
  --prolific-taskflow data/private/acl_prolific_taskflow_25.production.csv \
  --base-url https://freek-participant-pilot.streamlit.app/
```

The command refuses to overwrite either output. Both files are ignored by Git.
Back them up in the protected research folder. The registry contains ten test
links plus 50 real links; the URL file contains only the 50 real links. Use this
one registry whether recruitment ends at 25, 40, or 50 valid participants; do
not generate a second assignment schedule for a different sample size.

In the 50-link URL file, P01–P25 have `recruitment_source=network` and P26–P50
have `recruitment_source=prolific`. All have `reward_eligible=false`: network
participants receive no compensation and Prolific handles payment externally.
The application forces all real sessions to the plain debrief. Upload the
matching production registry as the deployment's session CSV secret when
rotating or regenerating links.

Paste the complete registry into the private `sessions_csv` Streamlit secret.
Never expose `assigned_item_ids` to participants.

## Prolific Taskflow

Upload the generated headerless `acl_prolific_taskflow_25.production.csv` to
Taskflow. It contains only P26–P50, with one URL in column A and allocation `1`
in column B. Never upload the full private URL registry or
`assigned_item_ids`.

Enable the integration only on the production deployment after Prolific has
generated the two completion paths:

```toml
prolific_enabled = true
prolific_completion_url = "https://app.prolific.com/submissions/complete?cc=COMPLETE_CODE"
prolific_no_consent_url = "https://app.prolific.com/submissions/complete?cc=NO_CONSENT_CODE"
```

Taskflow appends `PROLIFIC_PID`, `STUDY_ID`, and `SESSION_ID`. The application
preserves these parameters during navigation and stores them as pseudonymous
operational metadata in the raw progress record. Progress is physically scoped
to the Prolific submission ID, so Prolific may reuse the same assignment URL for
a replacement or an additional place without overwriting an earlier response.
Analysis exports keep the records separate, map them to the shared assignment
seed, and omit the Prolific identifiers.

Keep `prolific_enabled = false` until the production URL, completion paths, and
five-place Prolific pilot have all been tested. Test and network links remain
usable without Prolific parameters after it is enabled.

Distribute P01–P25 individually through the personal network. Never reuse a
network link after someone has started it; an incomplete link contains their
autosaved research data. Keep any contact-to-link distribution log separate
from research storage and restrict access to it.

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

For the split recruitment design, step 8 means distributing only P01–P25
manually and publishing a 25-place Taskflow study containing only P26–P50.

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
