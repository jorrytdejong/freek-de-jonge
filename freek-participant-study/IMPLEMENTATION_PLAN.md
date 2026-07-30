# Freek Participant Study: Implementation and DevOps Plan

## Goal

Build a Dutch Streamlit research application in which participants use anonymous
session links to rate multiple versions of jokes. The application must preserve
randomization, prevent invalid submissions, support resuming, and produce
analysis-ready data.

We will build this in **12 tangible checkpoints**. Every checkpoint ends with
something Jorryt can test. We only continue after that checkpoint has been
reviewed and accepted.

## Agreed Study Design

- The interface is in Dutch.
- The initial data contains 12 fictional mock joke groups.
- Every group contains exactly 8 joke versions.
- Every participant receives 5 groups, or 40 versions in total.
- The intended completion time is approximately 15 minutes; participants always
  finish the fixed set rather than being stopped by a timer.
- Group assignment is balanced across participants.
- Group order and version order are randomized.
- All 8 versions in a group appear on one page in separate blocks.
- Randomized versions are neutrally labelled `Versie A` through `Versie H`.
- Participants can see that the versions belong to the same group, but do not
  see an original or base joke.
- Every version receives two 1-5 ratings:
  - `Grappigheid`: `Helemaal niet grappig` to `Heel grappig`
  - `Lijkt op Freek de Jonge`: `Helemaal niet` to `Heel erg`
- Ratings use sliders and must all be answered.
- Participants can move backward, revise answers, and review everything before
  submission.
- Progress is autosaved and shown with a progress bar.
- Participants enter their exact age.
- Familiarity with Freek de Jonge is collected on a scale.
- There is no attention check and no separate question about whether the
  participant can distinguish Freek de Jonge's style.
- Consent is required.
- Group comments and one final overall comment are supported.
- Participants need a valid anonymous session link.
- Real links submit once; submitted answers reopen read-only.
- Test links can submit repeatedly and are marked as test data.
- The first session file contains 10 test links.
- A password-protected admin page provides read-only answers, downloads, and
  quick descriptive statistics.
- Mock material is experimental and not written by Freek de Jonge. The app says
  this explicitly.

## Architecture

The code will be separated by responsibility so storage or interface changes do
not affect the research logic unnecessarily.

```text
freek-participant-study/
├── streamlit_app.py
├── app/
│   ├── participant_flow.py
│   ├── admin.py
│   ├── assignment.py
│   ├── models.py
│   ├── validation.py
│   └── storage/
│       ├── base.py
│       ├── csv_storage.py
│       └── sheets_storage.py
├── data/
│   ├── jokes.csv
│   └── sessions.csv
├── tests/
├── .github/workflows/ci.yml
├── .streamlit/config.toml
├── requirements.txt
├── README.md
├── STUDY_SPEC.md
└── CHANGELOG.md
```

The user interface will call a storage interface with operations such as:

```python
load_session()
save_progress()
submit_response()
load_response()
list_results()
```

This allows local CSV storage during development and Google Sheets storage for
the deployed study.

## Build Checkpoints

### 1. Project Skeleton and Local App

**Build**

- Create the Python project structure.
- Pin the Python dependencies.
- Add Streamlit configuration and a minimal Dutch start screen.
- Add `.gitignore`, setup instructions, and a simple health check.

**Jorryt tests**

- Start the app using one documented command.
- Open it in a browser.
- Confirm that the Dutch start screen works on desktop and mobile.

**DevOps result**

- Anyone can create the same development environment from the repository.
- The application has a known entry point and pinned dependencies.

### 2. Study Specification and Mock Stimuli

**Build**

- Add `STUDY_SPEC.md` as the authoritative research specification.
- Create 12 Dutch fictional joke groups with 8 variants each.
- Give every group and variant a stable internal ID.
- Add a `study_version`, initially `pilot-1`.
- Validate the stimulus file automatically at startup.

**Jorryt tests**

- Browse a temporary stimulus preview.
- Check the tone, Dutch wording, group names, and eight variants.
- Deliberately remove a variant and confirm validation reports the problem.

**DevOps result**

- Stimuli are version-controlled and reproducible.
- Invalid research data cannot quietly reach deployment.

### 3. Anonymous Session Links

**Build**

- Define the fixed session-file format.
- Generate 10 test sessions.
- Reject missing, unknown, or inactive session IDs.
- Distinguish test sessions from real sessions.
- Make assignments deterministic from the session ID.

**Jorryt tests**

- Open a valid test link.
- Open the app without a link and with an invalid link.
- Refresh a valid link and confirm it keeps the same identity.

**DevOps result**

- Access rules are automated and testable.
- Session IDs are configuration data, not hard-coded application behaviour.

### 4. Consent and Participant Questions

**Build**

- Add the Dutch introduction, study duration, privacy note, experimental-joke
  warning, and consent checkbox.
- Collect exact age and familiarity with Freek de Jonge.
- Validate required fields before continuing.

**Jorryt tests**

- Try to continue without consent or required answers.
- Complete the form and refresh or reopen the link.
- Review all participant-facing wording.

**DevOps result**

- Consent and metadata validation have automated tests.
- Wording changes are traceable in Git history.

### 5. One Complete Joke Group

**Build**

- Display one group with eight separately presented variants.
- Show randomized labels `Versie A` through `Versie H`.
- Add the two required 1-5 sliders per variant.
- Add the optional group comment and clear validation messages.
- Ensure an untouched slider cannot accidentally count as a neutral answer.

**Jorryt tests**

- Rate a complete group.
- Attempt to continue with missing ratings.
- Check readability and slider usability on desktop and mobile.

**DevOps result**

- The central research interaction is testable before adding navigation
  complexity.

### 6. Five-Group Assignment and Navigation

**Build**

- Assign exactly 5 of the 12 groups using a balanced schedule.
- Randomize group order and each group's version order.
- Add Previous and Next navigation.
- Add the progress bar.
- Keep ratings when moving backward and forward.

**Jorryt tests**

- Complete parts of several groups and navigate backward.
- Refresh the browser and verify that assignment and order do not change.
- Compare several test links and inspect their different assignments.

**DevOps result**

- Automated tests verify 5 unique groups, 8 unique variants per group, stable
  assignment, and acceptable balance across the session pool.

### 7. Autosave, Pause, and Resume

**Build**

- Save partial progress after meaningful actions, especially group navigation.
- Restore the current group and completed ratings from the same link.
- Protect saved records against partial or malformed writes.
- Record update timestamps without collecting response-time measurements.

**Jorryt tests**

- Stop halfway through, close the browser, and resume later.
- Change previous ratings and confirm the latest values return.
- Simulate a refresh during the study.

**DevOps result**

- Participant interruption no longer causes data loss.
- Storage behaviour has contract tests independent of Streamlit.

### 8. Review, Submission, and Read-Only Reopening

**Build**

- Add a review page with all five groups and the final optional comment.
- Require all ratings before final submission.
- Store a submission as an atomic final event.
- Block a second real submission.
- Allow repeated test submissions while keeping them identifiable.
- Show submitted real sessions read-only.
- Add the Dutch debrief and thank-you page.

**Jorryt tests**

- Edit ratings from the review screen.
- Submit a test link more than once.
- Simulate a real link and verify that it cannot submit twice.
- Reopen a submitted real link and inspect the read-only answers.

**DevOps result**

- Submission rules are enforced in both application and storage layers.
- Regression tests protect the most consequential workflow.

### 9. Analysis-Ready Data Model

**Build**

- Produce a participant table with one row per session.
- Produce a ratings table with one row per rated joke version.
- Repeat selected participant metadata in rating rows for convenient analysis.
- Record study version, group ID, variant ID, displayed label, display position,
  assignment seed, test status, ratings, comments, and submission status.
- Add CSV exports and schema validation.

**Jorryt tests**

- Complete several contrasting test sessions.
- Download both files.
- Open them in a spreadsheet and confirm every displayed version maps to the
  correct internal variant.

**DevOps result**

- The output schema is documented, versioned, and automatically validated.
- Research reproducibility is part of the application rather than a later repair.

### 10. Protected Admin Page

**Build**

- Add a hidden admin route in the same Streamlit app.
- Read the admin password from local or deployed secrets.
- Show response counts, completion counts, group exposure, mean ratings per
  group and version, and a comparison of both rating dimensions.
- Provide read-only response inspection and CSV downloads.

**Jorryt tests**

- Try incorrect and correct passwords.
- Compare dashboard totals with downloaded CSV rows.
- Confirm that admin controls are not exposed in the participant flow.

**DevOps result**

- Operational visibility is built in.
- Passwords and credentials remain outside Git.

### 11. Automated Quality Gate and Staging Deployment

**Build**

- Add GitHub Actions for formatting, linting, unit tests, data validation, and an
  application startup smoke test.
- Use feature branches and pull requests.
- Deploy a staging app from a staging branch with only test sessions.
- Configure staging secrets outside the repository.

**Jorryt tests**

- Review a pull request and its automated checks.
- Use the public staging URL from a computer and phone.
- Ask a small number of test participants to complete the full flow.
- Review staging logs, exports, and summaries.

**DevOps result**

- Every proposed change receives the same automated checks.
- Staging resembles production without mixing in real research data.

### 12. Durable Storage and Production Release

**Build**

- Connect the storage interface to Google Sheets.
- Test concurrent submissions and retry behaviour.
- Create real balanced session links.
- Deploy production from the protected `main` branch.
- Add a release tag and changelog entry.
- Document backup, recovery, link deactivation, and study-closing procedures.

**Jorryt tests**

- Run a final pilot with 2-3 people.
- Confirm autosave survives an app reboot.
- Confirm production and staging data are separated.
- Download and inspect a backup.
- Approve the frozen `pilot-1` release before recruitment.

**DevOps result**

- Production data lives outside the app's temporary filesystem.
- The exact application, stimuli, configuration, and study version can be
  reconstructed later.

## Collaboration Rhythm

For every checkpoint:

1. Codex confirms the checkpoint scope and unresolved decisions.
2. Codex implements it on a `codex/...` branch.
3. Codex runs automated checks and starts the local app.
4. Codex gives Jorryt the URL, test links, and a short test script.
5. Jorryt tests the visible behaviour and gives feedback.
6. Codex fixes findings and reruns the checks.
7. The accepted checkpoint is committed before the next one begins.

This keeps every change small enough to understand and prevents several
unverified features from accumulating at once.

## Git and Deployment Flow

```text
codex/feature branch
        |
        v
GitHub pull request + automated checks
        |
        v
staging branch + staging Streamlit app
        |
        v
Jorryt's acceptance test
        |
        v
main branch + production Streamlit app
```

Streamlit Community Cloud can deploy directly from a configured GitHub branch.
Secrets are configured in Streamlit rather than committed to the repository.

## Data Safety

Local CSV files are suitable for development and export, but not as the only
production storage. Streamlit Community Cloud does not guarantee persistence of
files created by a running app. Therefore:

- CSV is used for early local checkpoints.
- Google Sheets is connected before real participant recruitment.
- Staging and production use separate sheets and credentials.
- Backups are downloaded regularly during data collection.
- Changes to stimuli or measurement wording create a new `study_version`.

## Decisions To Finalize During Relevant Checkpoints

These decisions do not block the planning document. We will settle them before
the checkpoint that uses them:

- Whether comments become required only after extreme ratings of 1 or 5.
- Exact wording and endpoints of the Freek de Jonge familiarity scale.
- Whether test links retain stable assignments or offer an explicit reshuffle
  control.
- Whether the final review starts expanded or collapsed by group.
- The preferred themes and tone of the fictional Dutch mock jokes.
- The final production session-ID format and number of real links.

## Definition of Done

The study is ready for production only when:

- All automated checks pass.
- The full participant journey works on desktop and mobile.
- The pilot confirms an acceptable completion time.
- Randomization and displayed-label mappings are recoverable from the exports.
- Autosave survives browser closure and application restart.
- Real sessions cannot submit twice.
- Test and production data are clearly separated.
- Secrets are absent from Git.
- Google Sheets storage and CSV backup have been tested.
- The exact production commit and `study_version` are tagged and documented.
