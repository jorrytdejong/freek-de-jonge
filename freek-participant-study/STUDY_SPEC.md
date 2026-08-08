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

The stimulus bank contains exactly 90 accepted jokes: one item for each of 15
topics in each condition. All were generated with `gpt-5.6-terra`; their source
hashes are preserved in `data/acl_jokes.csv`.

## Participant assignment

Every participant receives exactly 12 individual jokes:

- 12 different topics, with no repeated topic;
- exactly two jokes from every condition;
- a precomputed order that balances condition-by-position exposure;
- no displayed topic, condition, pipeline, style-toggle, or model labels.

For 25 real participants this yields 300 observations:

- every topic appears exactly 20 times;
- every condition appears exactly 50 times;
- every individual item appears three or four times;
- at every one of the 12 display positions, condition frequencies differ by at
  most one.

The session registry stores the complete ordered item assignment. The personal
token therefore reproduces the same order after interruption.

## Questionnaire

Each joke receives four required integer scores from 1 through 5. Sliders begin
at `Kies`, which is outside the analysis scale.

1. **Funniness:** `Hoe grappig vind je deze grap?`
   - 1: `Helemaal niet grappig`
   - 5: `Heel grappig`
2. **Freek-style resemblance:**
   `In hoeverre lijkt deze grap op de stijl van Freek de Jonge?`
   - 1: `Helemaal niet`
   - 5: `Heel erg`
3. **Coherence:**
   `In hoeverre is deze grap coherent en begrijpelijk als grap?`
   - 1: `Helemaal niet coherent`
   - 5: `Zeer coherent`
4. **Originality:** `Hoe origineel vind je deze grap?`
   - 1: `Zeer algemeen`
   - 5: `Zeer origineel`

One optional general comment is collected on the final review page. There is no
per-joke comment, attention check, response-time measurement, gender question,
or education question.

Before the jokes, participants provide exact age, required 1–5 familiarity with
Freek de Jonge, and consent. No name or contact details are collected.

## Participant flow

1. Personal-link validation.
2. Information, privacy notice, familiarity, age, and consent.
3. Twelve joke pages with four ratings each.
4. Review page with direct editing and an optional final comment.
5. Immutable final submission and debrief.

Every meaningful change is autosaved. Reopening the same token restores the
profile, partial ratings, completed ratings, current position, final comment,
and assignment order. A submitted real link reopens in read-only debrief mode.
Test links may create numbered repeat submissions.

## Analysis contract

The primary outcomes are funniness, Freek-style resemblance, coherence, and
originality. The export contains one row per participant-item observation and
retains condition, pipeline family, Freek toggle, topic, item ID, presentation
position, participant familiarity, exact text, model, and source hash.

Primary confirmatory effects can be estimated with mixed-effects models using
participant and item as random intercepts. Topic and familiarity effects are
secondary or exploratory unless separately preregistered.

## Version and blinding rules

- Study version: `acl-1`.
- Export schema version: `2`.
- Generated items are immutable once recruitment starts.
- Real tokens and their assignments are private research data.
- Condition metadata appears only in internal preview, admin, and exports.
- Stimuli are experimental and not written by Freek de Jonge.
