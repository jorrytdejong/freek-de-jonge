# Analysis Export Schema

Export schema: `2`
Study version: `acl-1`

`participants.csv` contains one row per saved session. `ratings.csv` contains
one row per completed participant-item response: 12 rows for a complete
submission.

For repeatedly submitted test links, the latest immutable submission is the
analysis snapshot; raw history remains in progress storage. Real links can
submit only once.

## participants.csv

The participant table includes:

- anonymous session ID, study version, test flag, and submission status;
- submission count and latest immutable submission identifiers;
- age, Freek familiarity, and consent;
- ordered `assigned_item_ids` and assignment fingerprint;
- assigned and completed item counts;
- optional final comment and save/submission timestamps.

## ratings.csv

The unique row key is `(session_id, item_id)`. Every row contains:

- participant/session metadata and familiarity;
- assignment fingerprint and presentation position;
- `item_id`, `topic_id`, and topic;
- condition code, pipeline family, and Freek-style toggle;
- model, result hash, exact joke text;
- funniness, Freek similarity, coherence, and originality scores;
- optional final comment and submission timestamp.

All four outcomes are integers from 1 through 5. Condition and pipeline columns
are internal research metadata and are never displayed to participants.

## Validation

Export creation rejects unknown sessions, changed test status, mismatched study
versions, responses outside an assignment, incorrect presentation positions,
incomplete submitted sessions, duplicate participant-item rows, invalid
profiles, and ratings outside 1–5. Text beginning with a spreadsheet formula
marker is neutralized in CSV output while raw storage retains the original.
