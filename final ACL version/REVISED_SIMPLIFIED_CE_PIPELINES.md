# Revised simplified C and E pipelines

These prompts are based on the Script-Based Semantic Theory of Humor (SSTH) and
the GTVH hierarchy. The doctor example is used only as a structural demonstration
for the Script B planner. Its subject matter and wording must not be copied.

The central mechanism is:

1. Script A is the ordinary first reading.
2. Script B overlaps with Script A but is opposed to it.
3. A late clue makes Script B clear.
4. The clue changes the meaning of something heard earlier.

## Shared Script A

```text
You are the Script A stage of a Dutch joke pipeline.

Treat the topic as a broad starting point, not a literal assignment.
Find one ordinary situation an audience could recognize.

In SSTH, a script is a familiar, structured situation: it includes typical
participants, roles, goals, conditions, actions, and expected outcomes. Script A
is the first script the wording should activate. Audience expectation means the
normal inference a listener would make before any surprise or reinterpretation.
Keep this first script concrete and recognizable, but do not make it a literal
definition of the topic and do not invent Script B at this stage.

Topic:
{topic}

Return:

- script_a: the ordinary situation
- audience_expectation: what the audience expects next

Do not write a joke or invent Script B.
Write in Dutch.
```

## Shared Script B

```text
You are the Script B stage of a Dutch script-opposition pipeline.

Topic:
{topic}

Script A:
{script_a}

Audience expectation:
{audience_expectation}

A joke works here when one text supports two overlapping but opposed scripts:
Script A is expected first, while Script B becomes clear through a late clue.

Worked example:

“Is the doctor in?” a patient asks in a bronchial whisper.
The doctor's young wife whispers that he is not, then says:
“Come right in.”

Analysis:

- Script A is a medical consultation: a patient asks whether a physician is available.
- Script B is a secret affair: a visitor checks whether the husband is absent.
- The dominant opposition is non-sex versus sex.
- “Doctor”, “patient”, and “bronchial” make the medical reading dominant.
- Whispering fits both illness and secrecy.
- The doctor's absence blocks the medical goal but enables the affair goal.
- “Come right in” is anomalous under Script A but purposeful under Script B.
- The punchline retrospectively changes the roles and meaning of earlier details.

Use this example only as a structural demonstration.
Do not reuse medicine, doctors, patients, spouses, affairs, whispering,
the invitation phrase, or the non-sex/sex opposition.

Propose exactly two fresh candidates, B1 and B2.

For each candidate, give:

- script_b
- opposition
- shared_cue
- switch_trigger
- role_or_goal_reversal
- retrospective_reinterpretation

The scripts must genuinely conflict.
Script A must remain the natural first reading.
Do not write jokes yet.
```

## Shared Script B audit

```text
Audit these Script B candidates:

{candidates}

For each candidate, answer:

- Does it support both scripts?
- Are the scripts genuinely opposed?
- Does Script A come first?
- Does the late clue reveal Script B?
- Does the clue change the meaning of something earlier?

Select the strongest passing candidate.
Do not rewrite the candidates.
```

## C pipeline

### C writer

```text
Write exactly two Dutch jokes, V1 and V2.

Topic:
{topic}

Script A:
{script_a}

Selected Script B:
{selected_script_b}

Opposition:
{opposition}

Shared cue:
{shared_cue}

Switch trigger:
{switch_trigger}

Write 20–45 words and no more than three sentences.

Make Script A believable first.
Reveal Script B late.
Let the final line change the meaning of an earlier detail.
Do not explain the joke.
Do not mention or copy the doctor example.
```

### C evaluator

```text
Evaluate these two jokes against the approved plan.

Plan:
{selected_plan}

Jokes:
{variants}

For each joke, check:

- Script A is the first reading.
- Script B is supported but delayed.
- The scripts are opposed.
- The switch is clear and late.
- Earlier material is reinterpreted.
- The punchline lands.

Give each joke a score from 1 to 5.
Select the stronger joke.
Do not rewrite them.
```

## E pipeline

E uses the same Script A, Script B, and audit stages as C.

### E GTVH enrichment

```text
Complete the approved joke plan with the remaining GTVH choices.

Approved Script Opposition:
{selected_plan}

Do not change Script A, Script B, the opposition, or the switch.

Return:

- logical_mechanism
- situation
- target
- narrative_strategy
- language

Write briefly in Dutch.
```

### E writer

```text
Write exactly two Dutch jokes, V1 and V2.

Topic:
{topic}

Approved Script Opposition:
{selected_plan}

GTVH choices:
{gtvh_plan}

Write 20–45 words and no more than three sentences.

Make Script A believable first.
Reveal Script B late.
Use the approved logical mechanism, situation, target,
narrative strategy, and language.
Let the punchline reinterpret an earlier detail.
Do not explain the joke.
Do not mention or copy the doctor example.
```

### E evaluator

```text
Evaluate these two jokes against the approved plan.

Script Opposition:
{selected_plan}

GTVH choices:
{gtvh_plan}

Jokes:
{variants}

For each joke, check:

- Script Opposition is preserved.
- Script A comes first.
- Script B appears late.
- Earlier material is reinterpreted.
- Logical Mechanism is preserved.
- Situation is preserved.
- Target is preserved.
- Narrative Strategy is preserved.
- Language choices are used.
- The punchline lands.

Give each joke a score from 1 to 5.
Select the strongest joke.
Do not rewrite them.
```

## Call sequence

```text
C:
Script A
→ two Script B candidates
→ Script Opposition audit
→ two jokes
→ evaluation

E:
Script A
→ two Script B candidates
→ Script Opposition audit
→ five GTVH choices
→ two jokes
→ evaluation
```
