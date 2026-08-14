# ACL-1 Study Specification

## Research design

The study compares three joke-generation pipelines with Freek de Jonge style
guidance switched off and on, giving six within-participant conditions:

| Code | Pipeline | Freek guidance |
| --- | --- | --- |
| A1 | Baseline | Off |
| A2 | Baseline | On |
| C1 | Script opposition | Off |
| C2 | Script opposition | On |
| E1 | Validated GTVH | Off |
| E2 | Validated GTVH | On |

The stimulus bank contains exactly 120 accepted jokes: one item for each of 20
topics in each condition. All were generated with `gpt-5.6-terra`; their source
hashes are preserved in `data/acl_jokes.csv`.

## Participant assignment

Every participant receives exactly 20 individual jokes:

- every one of the 20 topics exactly once;
- four jokes from two conditions and three from each other condition, with the
  larger condition slots rotating between participants;
- a precomputed, deterministically randomized order;
- no displayed topic, condition, pipeline, style-toggle, or model labels.

The complete registry contains 50 real-participant assignments and is used for
every recruitment outcome from 25 through 50. Assignment is cyclic in aligned
blocks of six participants: within each complete six-person block, every topic
appears once in every condition. Consequently:

- every participant sees all 20 topics and all six conditions;
- topic exposure is exact at every recruitment prefix;
- condition and individual-item exposure each differ by at most one at every
  recruitment prefix;
- at 50 participants four conditions have 167 observations and two have 166;
- at 50 participants 40 items have nine observations and 80 have eight.

The session registry stores the complete ordered item assignment. The personal
token therefore reproduces the same order after interruption.

## Recruitment and stopping rule

- Eligibility: participants are at least 18 years old and can comfortably read
  Dutch. Familiarity with Freek de Jonge is measured, not used as an exclusion
  criterion.
- The planned sample contains two prespecified recruitment sources: assignment
  slots P01–P25 are recruited through the researcher's personal network without
  compensation; P26–P50 are anonymous paid Prolific participants.
- Minimum viable sample: 25 valid submitted participants.
- Recruitment target: 50 valid submitted participants, aiming for 25 valid
  submissions from each source.
- Maximum sample: 50 valid submitted participants.
- Operational target: 40 participants; no balance-based stopping milestone is
  needed because every recruitment prefix is maximally balanced.
- Recruitment continues according to time and participant availability, up to
  the maximum. It never depends on observed ratings, effect estimates, or
  p-values.
- All valid submissions received before the predetermined recruitment close are
  analysed. Participants 49 and 50 are retained if valid; recruitment is not
  truncated at 48 merely to obtain exact balance.
- A source may finish below 25 when availability is exhausted at the
  predetermined close. The other source is never expanded beyond its 25-slot
  cap in response to observed ratings.

The recruitment closing date or operational feasibility decision must be
recorded before inspecting condition-level results. Recruitment must never
continue or stop because a contrast has or has not reached significance.

## Questionnaire

Each joke receives three required integer scores from 1 through 5 and one
optional open comment. Sliders begin at `Kies`, which is outside the analysis
scale.

1. **Funniness:** `Hoe grappig is deze grap?`
   - 1: `Helemaal niet grappig`
   - 5: `Heel grappig`
2. **Freek-style resemblance:**
   `In hoeverre lijkt deze grap op de stijl van Freek de Jonge?`
   - 1: `Helemaal niet`
   - 5: `Heel sterk`
3. **Coherence:**
   `Is deze grap logisch als grap?`
   - 1: `Onsamenhangend`
   - 5: `Zeer samenhangend`
4. **Open comment:** `Wat maakt dat deze grap wel of niet werkt? (optioneel)`

There is no additional general comment on the final review page, attention
check, response-time measurement, gender question, or education question.

Before the jokes, participants provide exact age, required 1–5 familiarity with
Freek de Jonge, and consent. No name or contact details are collected.

## Participant flow

1. Personal-link validation.
2. Information, privacy notice, familiarity, age, and consent.
3. Twenty joke pages with three ratings and one optional open comment each.
4. Review page with direct editing and an optional final comment.
5. Immutable final submission and debrief.

Every meaningful change is autosaved. Reopening the same token restores the
profile, partial ratings and comments, completed responses, current position,
and assignment order. A submitted real link reopens in read-only debrief mode.
Test links may create numbered repeat submissions.

## Analysis contract

The primary outcomes are funniness, Freek-style resemblance, and coherence.
The export contains one row per participant-item observation and
retains condition, pipeline family, Freek toggle, topic, item ID, presentation
position, participant familiarity, optional open comment, exact text, model,
and source hash.

Primary confirmatory effects can be estimated with mixed-effects models using
participant and item as random intercepts. Topic and familiarity effects are
secondary or exploratory unless separately preregistered.

Recruitment source is retained as a participant-level fixed effect. Interactions
between recruitment source and experimental condition, plus source-stratified
estimates, are prespecified sensitivity analyses. They are interpreted as
exploratory because the study is not separately powered for source interactions.

## Version and blinding rules

- Study version: `acl-1`.
- Export schema version: `3`.
- Generated items are immutable once recruitment starts.
- The six conditions, topic-item mapping, Freek-context block, model and
  generation settings, first-valid-output rule, assignment schedule,
  randomization procedure, primary outcome and contrast, exclusion rules,
  sample-size bounds, and stopping rule are locked before recruitment.
- Recruitment-source allocation and source-specific compensation are locked
  before recruitment.
- Items are not added or replaced after participant ratings have been viewed.
- Real tokens and their assignments are private research data.
- Condition metadata appears only in internal preview, admin, and exports.
- Stimuli are experimental and not written by Freek de Jonge.
