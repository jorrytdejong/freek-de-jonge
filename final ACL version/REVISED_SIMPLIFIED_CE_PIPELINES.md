# Revised simplified C and E pipelines

These prompts are based on the Script-Based Semantic Theory of Humor (SSTH) and
the GTVH hierarchy. The doctor example is used only as a structural demonstration
for the Script B planner. Its subject matter and wording must not be copied.

The central mechanism is:

1. Script A is the ordinary first reading.
2. Script B overlaps with Script A but is opposed to it.
3. A late clue makes Script B clear.
4. The clue changes the meaning of something heard earlier.

## What each component represents

The pipeline uses GTVH as a planning representation, not as a guaranteed recipe
for producing a funny joke. GTVH describes six ordered Knowledge Resources:

```text
Script Opposition > Logical Mechanism > Situation > Target > Narrative Strategy > Language
```

The hierarchy describes structural dependence and similarity between jokes. It does
not require the model to generate the resources in this exact chronological order.

This interpretation follows the GTVH overview supplied with the project and the
foundational [Attardo--Raskin account](</Users/jorrytdejong/Documents/Freek%20de%20Jonge%20project/Literature/Attardo-Raskin-1991-Script-Theory-Revis-It-Ed.pdf>).

### Script A

Script A is the familiar, organized situation that the opening activates first.
It includes typical participants, roles, goals, conditions, actions, and expected
outcomes. The audience expectation records the normal inference that follows from
that script before the punchline appears.

The topic is deliberately only a broad starting point. It helps select a useful
situation, but it should not force the joke to mention or literally enact the topic.

### Script B

Script B is a second situation that overlaps with Script A enough for one text to
support both readings, but differs in a meaningful way. It should be a recognizable
script, not merely an opinion, metaphor, exaggeration, or darker description of A.

### Script Opposition

Script Opposition identifies the incompatible interpretations at the center of the
joke. The label should be specific to the text—for example, ordinary medical visit
versus secret affair, or phone distraction versus accessibility—rather than only
using a very broad label such as “normal versus abnormal.”

### Shared cue

A shared cue is a word, object, action, role, or circumstance that naturally fits
both scripts. It lets Script B be supported before it is revealed, without making
the second reading obvious too early.

### Switch trigger

The switch trigger is the late clue, usually near the punchline, that makes Script B
available. It should create a small anomaly under Script A and make that anomaly
purposeful under Script B.

### Role or goal reversal

This records what changes between the scripts. A person can become a different role,
or an action that blocked the apparent goal can enable the hidden goal. This is an
operational field for making the change between scripts concrete; it is not a
separate GTVH resource.

### Retrospective reinterpretation

This records what the audience understands differently after the switch. A successful
punchline does not merely add a surprising fact; it makes an earlier word, action,
role, or condition meaningful under Script B.

### Logical Mechanism (E only)

Logical Mechanism describes how the listener moves from Script A to Script B. It may
be ambiguity, role reversal, false analogy, figure–ground reversal, juxtaposition,
faulty reasoning, or another playful bridge. The bridge need not make the situation
literally logical; it only needs to make the second reading understandable.

### Situation (E only)

Situation describes the joke’s internal text world: its participants, objects,
activities, setting, and relevant background. It is not the venue, audience, or
performance context.

### Target (E only)

Target identifies who or what is ridiculed: a character, institution, convention,
behaviour, political practice, or sometimes nobody. A joke may be targetless,
especially when its effect is primarily absurdity or wordplay.

### Narrative Strategy (E only)

Narrative Strategy describes the textual form: dialogue, question-and-answer,
one-liner, short anecdote, list, monologue, or escalation. It also controls where
the switch and punch occur. A punchline normally closes the unit and forces a
reinterpretation; a jab can create a local humorous moment without reorganizing
the whole text.

### Language (E only)

Language is the exact Dutch realization: vocabulary, syntax, register, idiom,
rhythm, lexical ambiguity, word order, and final punch wording. Two jokes can keep
the same higher-level plan while differing only in Language.

### What is shared and what differs

C and E share Script A, Script B, Script Opposition, the switch, and the final
fidelity check. E adds the lower GTVH resources only after Script Opposition has
been selected. This keeps the central semantic comparison fixed while testing
whether extra planning choices improve the realization.

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

- script_a: the ordinary situation, including its typical people, goal, and action
- audience_expectation: the normal next step the audience would infer

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

- script_b: the recognizable alternative situation
- opposition: the specific conflict between Script A and Script B
- shared_cue: one detail that naturally fits both scripts
- switch_trigger: the late clue that makes Script B available
- role_or_goal_reversal: what role or goal changes between the scripts
- retrospective_reinterpretation: what earlier detail means differently afterward

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
Return one short assessment for B1 and B2, the selected candidate ID,
and a brief reason for the selection.
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

Return for each variant:
- variant_id
- text
- angle: the main comic approach
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
Return one assessment for each variant, one comparison, the selected variant ID,
and a brief reason. Select the stronger joke.
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

- logical_mechanism: the playful bridge from Script A to Script B
- situation: the people, objects, activity, setting, and background in the joke
- target: who or what is ridiculed, or null if nobody is targeted
- narrative_strategy: the textual form and placement of the switch and punch
- language: the Dutch wording, register, ambiguity, and final punch wording

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

Return for each variant:
- variant_id
- text
- angle: the main comic approach
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
Return one assessment for each variant, one comparison, the selected variant ID,
and a brief reason. Select the strongest joke.
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
