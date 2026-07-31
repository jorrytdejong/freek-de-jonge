# Analysis Export Schema

Schema version: `1`  
Study version: `pilot-1`

Checkpoint 9 produces two UTF-8 CSV files. Every export is reconstructed from
the fixed session registry, versioned stimuli, deterministic assignment logic,
and durable progress snapshots. Validation fails before files are replaced if
those sources disagree.

## Snapshot Rule

- `participants.csv` has exactly one row per session present in progress data.
- `ratings.csv` has one row per completed joke version in that session's
  analysis snapshot: 8 rows per completed group and 40 after submission.
- A submitted session uses its latest immutable submission event.
- A repeatedly submitted test session therefore remains one participant in the
  analysis tables. `submission_count` records the history and
  `latest_submission_id` identifies the selected snapshot.
- Raw submission history remains preserved in `data/runtime/progress.csv`.
- An in-progress session is included, but only completed groups produce rating
  rows. Blank submission fields distinguish these rows from submitted data.

## participants.csv

| Column | Meaning |
| --- | --- |
| `export_schema_version` | Version of this output contract. |
| `session_id` | Anonymous fixed session identifier. |
| `study_version` | Research treatment and measurement version. |
| `is_test` | `true` for a test link. |
| `submission_status` | `in_progress` or `submitted`. |
| `submission_count` | Number of immutable submission events. |
| `latest_submission_id` | Stable ID of the selected submission snapshot. |
| `latest_submission_number` | Sequential test submission number. |
| `age` | Exact age in whole years, blank before profile completion. |
| `freek_familiarity` | Freek de Jonge familiarity score, 1-5. |
| `consent` | Recorded consent, blank before profile completion. |
| `assigned_group_ids` | Deterministic displayed group order, pipe-separated. |
| `assignment_seed` | Session ID used by deterministic assignment. |
| `assignment_fingerprint` | Short checksum of group and variant order. |
| `group_count` | Number of assigned groups. |
| `completed_group_count` | Number of validated completed groups. |
| `final_comment` | Optional overall participant comment. |
| `created_at` | First durable save timestamp with timezone. |
| `updated_at` | Latest durable save timestamp with timezone. |
| `submitted_at` | Selected submission timestamp, blank in progress. |

## ratings.csv

The row grain is unique by `session_id`, `group_id`, and `variant_id` within the
selected snapshot. Participant metadata is repeated to make spreadsheet and
statistical analysis easier.

| Column | Meaning |
| --- | --- |
| `export_schema_version` | Version of this output contract. |
| `session_id` | Anonymous fixed session identifier. |
| `submission_id` | Selected immutable submission ID. |
| `submission_number` | Selected test submission number. |
| `study_version` | Research treatment and measurement version. |
| `is_test` | `true` for a test link. |
| `submission_status` | `in_progress` or `submitted`. |
| `age` | Repeated participant age. |
| `freek_familiarity` | Repeated familiarity score, 1-5. |
| `assignment_seed` | Session ID used by deterministic assignment. |
| `assignment_fingerprint` | Checksum of the complete assignment. |
| `group_id` | Stable internal base-joke group ID. |
| `group_position` | Position of the group shown to this participant, 1-5. |
| `group_title` | Descriptive internal group title. |
| `variant_id` | Stable internal joke-version ID. |
| `variant_role` | Experimental transformation role. |
| `joke_text` | Exact version text from the versioned stimulus file. |
| `display_label` | Neutral label shown to the participant, A-H. |
| `display_position` | Position within the displayed group, 1-8. |
| `funniness` | Grappigheid rating, 1-5. |
| `freek_similarity` | Lijkt op Freek de Jonge rating, 1-5. |
| `group_comment` | Optional comment after that joke group. |
| `final_comment` | Optional overall participant comment. |
| `submitted_at` | Selected submission timestamp, blank in progress. |

## Validation Contract

The exporter rejects unknown sessions, changed test status, incomplete submitted
sessions, responses outside the fixed assignment, duplicate variants, invalid
1-5 ratings, and any mismatch between displayed labels and deterministic
internal variants. Automated tests protect column order, row grain, latest-test-
submission selection, CSV parsing, and atomic output replacement. Text beginning
with a spreadsheet formula marker is prefixed with an apostrophe in CSV output;
the untouched value remains available in raw progress storage.
