# Study Specification

## Status

- Study version: `pilot-1`
- Application language: Dutch
- Current phase: mock-stimulus development
- Intended completion time: approximately 15 minutes

This document is the authoritative functional and research specification. Code,
stimuli, tests, and exported responses must remain consistent with it.

## Research Goal

The study investigates how participants assess multiple versions of the same
joke on two dimensions:

1. perceived funniness;
2. perceived similarity to Freek de Jonge in both style and subject matter.

The mock stimuli are fictional and experimental. They are not written or
performed by Freek de Jonge and must not reproduce his copyrighted material.

## Stimulus Design

- The stimulus pool contains exactly 12 joke groups.
- Every group contains exactly 8 versions of one shared premise.
- Participants see the 8 versions, but not an original or base joke.
- Every group and variant has a stable internal identifier.
- Stimuli are stored in `data/jokes.csv`.
- Every row records the study version to prevent data from different study
  revisions being combined silently.
- Internal variant roles describe how the mock versions differ. They are never
  shown to participants.

The eight internal variant roles are:

1. `baseline`
2. `concise`
3. `wordplay`
4. `absurdist`
5. `social_critique`
6. `narrative`
7. `self_reflexive`
8. `linguistic_turn`

These roles support mock-data review only. They are not experimental conditions
unless a later study version explicitly defines them as such.

## Participant Assignment

- Every participant receives exactly 5 of the 12 groups.
- Every selected group contributes all 8 versions.
- A participant therefore rates 40 joke versions.
- Group assignment is balanced over the available real session links.
- Assignment and ordering are deterministic from the anonymous session ID.
- Group order is randomized per participant.
- Version order is randomized within each group.
- Display labels `Versie A` through `Versie H` are assigned after randomization.
- Exports retain the mapping from displayed label and position to internal
  variant ID.

Assignment and session-link behaviour are implemented from the fixed session
registry and deterministic session-based ordering.

## Measurements

Every version receives two required integer ratings from 1 through 5:

- `Grappigheid`
  - 1: `Helemaal niet grappig`
  - 5: `Heel grappig`
- `Lijkt op Freek de Jonge`
  - 1: `Helemaal niet`
  - 5: `Heel erg`

The second scale covers both style and subject matter.

Sliders must begin in an unanswered state. An untouched slider must not silently
count as a neutral rating.

For checkpoint 7, the complete five-group rating and resume flow is
implemented:

- the deterministic assignment order maps to neutral labels `Versie A` through
  `Versie H`;
- each participant receives five unique groups in a deterministic randomized
  order;
- all eight variants in every group have a deterministic randomized order;
- participants never see internal variant IDs or variant roles;
- each version is shown with both rating sliders side by side on desktop;
- mobile layouts stack the two scales to preserve readable labels;
- every slider begins at `Kies`, outside the 1-5 analysis scale;
- choosing `3` is therefore distinguishable from leaving a slider untouched;
- all 16 ratings are required before the group response is accepted;
- the group comment remains optional;
- Previous and Next navigation preserves completed responses and partial
  drafts;
- a progress bar identifies the current group out of five;
- a compact `Opgeslagen` status confirms that persistent progress exists;
- every slider or comment change, validated profile, and navigation action
  updates the durable progress snapshot;
- reopening the anonymous link restores the profile, current page, completed
  groups, partial ratings, comments, group order, and variant order.

## Participant Questions

Required:

- consent with the wording: `Ik heb bovenstaande informatie gelezen en neem
  vrijwillig deel aan dit onderzoek.`;
- exact age in whole years from 1 through 120;
- familiarity with the wording: `Hoe goed ken je het werk van Freek de Jonge?`
  on a required 1-5 scale;
- familiarity endpoints `Helemaal niet bekend` and `Zeer bekend`.

The participant information page states:

- the expected duration is approximately 15 minutes;
- participants later receive 5 groups of 8 joke versions;
- Freek de Jonge is named in the similarity measurement;
- similarity covers both style and subject matter;
- stimuli are experimental and not written by Freek de Jonge;
- no name or contact details are collected;
- answers are linked to the unique code in the personal research link.

Not collected:

- gender;
- education;
- native language;
- country;
- 18+ confirmation;
- ability to distinguish Freek de Jonge's style;
- response-time measurements.

There is no attention check.

## Comments

- One comment field is available after each group.
- One final overall comment field is available.
- Comments are optional unless a later documented decision introduces a narrow
  extreme-rating trigger.

## Navigation and Persistence

- All eight versions of one group appear on one page in separate blocks.
- Participants proceed group by group.
- Previous and Next navigation is available.
- A progress bar shows study progress.
- Participants can revise earlier answers before submission.
- Progress is autosaved after meaningful actions, especially group navigation.
- Reopening the same anonymous link restores assignment, order, answers, and
  position.
- A final review page precedes submission.
- The review page shows all five groups and supports direct editing.
- Final submission appends an immutable event containing the complete profile,
  ratings, comments, study version, test status, and submission timestamp.
- The debrief repeats that the stimuli are experimental and not written by
  Freek de Jonge.
- Submitted real links always reopen on a read-only debrief.
- Test links can return to review and append a separately numbered submission.

Checkpoint 8 stores local development progress and submissions in
`data/runtime/progress.csv`. The fixed columns are:

- `session_id`
- `study_version`
- `is_test`
- `current_page`
- `profile_json`
- `responses_json`
- `drafts_json`
- `status`
- `final_comment`
- `submissions_json`
- `created_at`
- `updated_at`

The structured fields are JSON inside CSV cells. Each submission event receives
a stable ID such as `test-01-DU8NXu1m-submission-001` and retains its own
immutable response snapshot. The complete file is written to a temporary
sibling file, flushed, and atomically replaced. Invalid headers, malformed JSON,
duplicate sessions, invalid timestamps, inconsistent submission status, and
duplicate real submissions block writes rather than silently discarding data.
Checkpoint-7 files are accepted through an explicit legacy schema and upgraded
on their next save. The runtime file is excluded from Git. `updated_at` records
save events only; response durations are not measured.

## Session Rules

- The participant app requires a valid anonymous session link.
- Missing, unknown, and inactive links are rejected.
- The fixed registry uses the columns `session_id`, `is_test`, `active`,
  `assignment_groups`, `created_at`, and `notes`.
- Every fixed session record contains exactly 5 unique group IDs.
- The initial registry contains 10 active test sessions.
- Test-session group exposure differs by at most one across the 12 groups.
- Real sessions can submit once.
- Reopening a submitted real session shows read-only answers.
- Test sessions are clearly marked in stored data and can submit repeatedly.
- The initial fixed session file contains 10 test sessions.

## Administration and Storage

- The admin page lives in the same Streamlit app behind a hidden route.
- The admin password is read from Streamlit secrets or an environment variable.
- The admin view is read-only and supports CSV downloads and descriptive
  summaries.
- There is no default or committed production password. Password comparison is
  constant-time, and failed authentication does not expose research data.
- The participant flow contains no link or control that reveals the hidden
  administration route.
- Administrators can select real participants, test sessions, or all sessions;
  the statistics, inspection list, and downloads use the same selection.
- Definitive submissions are the default status selection so provisional
  autosaves do not enter research means; all saved states remain inspectable.
- Summary statistics include session and completion counts, completed groups,
  rating-row count, both overall rating means, group exposure, and means per
  stable internal variant.
- Read-only inspection shows participant metadata, assignment fingerprint,
  displayed labels, stable variant IDs, exact texts, ratings, and comments.
- Dashboard statistics and downloads are derived from the same validated
  analysis tables defined in `EXPORT_SCHEMA.md`.
- Development initially uses a replaceable CSV storage adapter.
- Production uses Google Sheets because deployed Streamlit local files are not
  durable.
- Staging and production use separate data stores and credentials.

## Analysis-Ready Exports

- Export schema version `1` is documented in `EXPORT_SCHEMA.md`.
- `participants.csv` contains one row per durable session.
- `ratings.csv` contains eight rows per completed group and therefore 40 rows
  for a fully submitted session.
- Displayed labels A-H and display positions are exported beside stable internal
  variant IDs, roles, and exact joke text.
- Participant metadata, study version, assignment seed and fingerprint, test
  status, submission status, comments, and selected submission metadata remain
  available for filtering and reproducibility.
- For a repeatedly submitted test link, analysis tables use the latest immutable
  submission while preserving the full event history in raw progress storage.
- In-progress sessions remain identifiable and only validated completed groups
  create rating rows.
- Export validation rejects data that no longer matches the session registry,
  versioned stimuli, deterministic assignment, rating bounds, or row grain.

## Versioning Rule

Any change to joke text, measurement wording, assignment logic, required
participant questions, or output schema creates a new `study_version`.

Bug fixes that do not alter the research treatment may retain the same study
version, but must be recorded in `CHANGELOG.md` before production.

## Automated Delivery Contract

- Python 3.11 is the shared local, CI, and staging runtime.
- `python scripts/run_quality_gate.py` is the canonical local and CI command.
- The gate checks formatting, linting, compilation, static data, deterministic
  assignment, all automated tests, and a process-level Streamlit health probe.
- GitHub Actions runs the gate for participant-study pull requests and pushes to
  `main`, `staging`, and `codex/*` branches with read-only repository permission.
- `data/sessions.staging.csv` contains test links only. Automated validation
  blocks staging if any non-test session is added.
- Staging deployment uses a long-lived `staging` branch and credentials that are
  separate from production and stored outside Git.
- Checkpoint 11 staging data is disposable because durable Google Sheets storage
  is introduced in checkpoint 12 before real participant recruitment.
