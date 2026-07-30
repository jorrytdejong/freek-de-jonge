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

Assignment and session-link behaviour will be implemented in later checkpoints.

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

## Participant Questions

Required:

- consent;
- exact age in whole years;
- familiarity with the work of Freek de Jonge on a 1-5 scale.

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

## Session Rules

- The participant app requires a valid anonymous session link.
- Missing, unknown, and inactive links are rejected.
- Real sessions can submit once.
- Reopening a submitted real session shows read-only answers.
- Test sessions are clearly marked in stored data and can submit repeatedly.
- The initial fixed session file contains 10 test sessions.

## Administration and Storage

- The admin page lives in the same Streamlit app behind a hidden route.
- The admin password is read from Streamlit secrets or an environment variable.
- The admin view is read-only and supports CSV downloads and descriptive
  summaries.
- Development initially uses a replaceable CSV storage adapter.
- Production uses Google Sheets because deployed Streamlit local files are not
  durable.
- Staging and production use separate data stores and credentials.

## Versioning Rule

Any change to joke text, measurement wording, assignment logic, required
participant questions, or output schema creates a new `study_version`.

Bug fixes that do not alter the research treatment may retain the same study
version, but must be recorded in `CHANGELOG.md` before production.

