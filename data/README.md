# ACL-1 Reproducibility Data

## Corpus annotations

The file acl_corpus_annotations_69.csv consolidates the 69 laughter-linked units annotated across the five performance records. Each row is one unit. The categories_json and script_opposition_json columns preserve the complete structured annotations from the source JSON files.

## Human evaluation

The file acl_human_evaluation_ratings.csv is an analysis-ready export of the latest real ACL-1 submission for each participant from Supabase (private.study_submissions). It contains 840 item-level rating rows from 42 participants, with 20 items per participant. Each item has funniness, coherence, and perceived Freek-style similarity ratings, plus optional participant comments.

Participant identifiers and Prolific identifiers are not included. The participant_code values are sequential codes assigned after sorting the source session identifiers. Newline characters in comments are represented as the literal sequence backslash-n so each rating remains one CSV row.
