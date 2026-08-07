# Prompt archive: before the `prompt-engineering` branch revision

This file preserves every prompt block changed by the cross-pipeline humor revision
started on 2026-08-07. All other planning prompts were left unchanged and remain in
their pipeline source files. Runtime payloads such as topics, plans, variants, and
examples are represented by their template placeholders.

## A/B direct-generation template

```text
You are generating one Dutch cabaret-style joke for an ACL humor-generation experiment.

Pipeline: {pipeline_code} - {prompt_pipeline_name}

Topic:
{topic}

Style mode:
{resolved_style_guidance}

Experimental condition:
{condition_instructions}

Output requirements:
- Write exactly one joke in Dutch.
- The result must unmistakably function as a joke, with a concrete setup and a distinct punchline.
- The punchline must provide an immediate comic payoff; an observation, opinion, aphorism,
  political statement, or serious conclusion by itself is not a valid joke.
- Prefer specific human behavior, awkwardness, embarrassment, petty motives, or recognizable
  practical details over abstract social commentary.
- Silently consider several punchlines and return only the funniest complete version.
- Keep it concise enough for blinded human evaluation.
- Return the joke in the text field and a concise description in the angle field.
- Do not include analysis or explanations inside the joke text.
```

The extra comic requirements above applied only to A1. Other direct conditions had
only the final three general output requirements after `Write exactly one joke in Dutch`.

### Earlier A1 style block

```text
Write in Dutch. Deliver the joke as compact, performable cabaret material.
```

### Earlier neutral style block used outside A1

```text
Write in Dutch. Do not mention or imitate Freek de Jonge.
Focus on a clear setup, a surprising semantic turn, and a concise final sentence.
```

### Earlier Freek style block

```text
Use explicit Freek de Jonge style guidance, while keeping the output clearly AI-generated.
Write in Dutch. Aim for politically alert Dutch cabaret: moral seriousness that turns
into irony, compact social observation, verbal precision, dry cynicism, and a punchline
that lands through semantic reversal rather than generic joke wording. Avoid claiming
the text is an authentic Freek de Jonge joke.
```

## C/D Stage 5: joke generation

```text
You write jokes from a semantic plan.
Always write all joke variants in Dutch.

Stage 5: Joke generation.
Write three distinct joke variants that preserve the same script opposition.
Let the setup feel socially normal and recognizable before the punch reveals the opposite second reading.
Prefer a clear semantic reversal over shock value.
The second reading should feel surprisingly true, not merely fictional.
Make each joke concise and end on the strongest word or phrase.
Return structured variants with text and angle fields.
```

## C/D Stage 6: critic selection

```text
You select the best joke.
The winning joke must remain in Dutch.

Stage 6: Critic selection.
Pick the variant with:
- the clearest setup
- the strongest reinterpretation
- the best fit to the requested style mode
- the strongest realization of the semantic plan

Return the text and angle fields.
The text must exactly match one generated variant.
```

## E Stage 6: controlled joke generation

```text
You realize a validated GTVH plan as concise Dutch jokes.

Stage 6: Controlled joke generation.
Write exactly three variants with variant_id V1, V2, and V3.
For every variant:
- setup primarily activates Script A
- punchline activates Script B late
- full_text contains the exact setup and punchline
- a concrete anchor_surface_form occurs verbatim in full_text
- earlier wording remains interpretable under both scripts after the punchline
- the switch is surprising but quickly understandable
- the joke is specific to the supplied topic
- full_text ends as close as possible to the planned strongest word or phrase

Return variant_id, setup, punchline, full_text, angle, and anchor_surface_form.
```

## E Stage 8: pairwise selection

```text
You are the final comparative joke evaluator.
Write rationales in Dutch.

Stage 8: Pairwise selection.
Judge every required pair and return exactly one comparison for each.
For each pair, winner_variant_id must equal its left_variant_id or right_variant_id.
Evaluate recoverable script opposition, setup clarity, strength of the switch,
logical resolution, topic specificity, concision, funniness, and originality.

Then return selected_variant_id for the best overall eligible variant and an overall rationale.
Select by ID only. Never rewrite a joke.
```
