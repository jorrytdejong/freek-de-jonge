# ACL Final Pipeline Matrix

This folder implements the eight original paper conditions from the ACL final
project plus two additive validated-GTVH conditions as a single configurable
matrix. A/B are direct generation conditions; C/D build script opposition
through the original staged prompt pipeline; E adds theory gates without
changing A-D.

| Code | Condition |
| --- | --- |
| A1 | Baseline prompt without Freek style |
| A2 | Baseline prompt with Freek style |
| B1 | Category-guided generation without Freek style |
| B2 | Category-guided generation with Freek style |
| C1 | Script-opposition-guided generation without Freek style |
| C2 | Script-opposition-guided generation with Freek style |
| D1 | Category + script-opposition generation without Freek style |
| D2 | Category + script-opposition generation with Freek style |
| E1 | Validated GTVH generation without Freek style |
| E2 | Validated GTVH generation with Freek style |

The implementation keeps the experiment structure explicit: A-E describe the
generation family, while 1-2 describe whether explicit Freek de Jonge context
is included. A2/C2 use general Freek examples. When both category and Freek
conditioning are enabled, B2/D2 derive their category context from Freek jokes
tagged with the selected category.

Category records contain only a name and general description. They never store
a predefined setup script, opposing script, or trigger. Those semantic elements
are generated afresh for the current topic.

## Structure

```text
final ACL version/
  app/
    streamlit_app.py
  core/
    categories.py
    category_guidance.py
    llm.py
    prompting.py
    runner.py
    schemas.py
    styles.py
  pipelines/
    conditions.py
    script_opposition.py
    validated_gtvh.py
  experiments/
    additional_conditions.json
    paper_conditions.json
  run_matrix.py
  smoke_test.py
  structured_output_test.py
  validated_gtvh_test.py
```

## Run a Smoke Test

```bash
python3 "final ACL version/smoke_test.py"
python3 "final ACL version/structured_output_test.py"
python3 "final ACL version/validated_gtvh_test.py"
```

Every model response is parsed through `client.responses.parse` into a Pydantic
model. The pipeline does not use JSON mode or manually parse model output.

## Build Prompts Without API Access

```bash
python3 "final ACL version/run_matrix.py" \
  --topic "de wachtrij bij de gemeente" \
  --category Ironie \
  --dry-run
```

## Generate Jokes

```bash
export OPENAI_API_KEY="..."
python3 "final ACL version/run_matrix.py" \
  --topic "de wachtrij bij de gemeente" \
  --category Ironie \
  --model gpt-5.6-terra
```

The Streamlit sidebar includes a model selector. The CLI accepts the same model
choices through `--model`.

## Script Opposition Flow

Pipelines `C1`, `C2`, `D1`, and `D2` use six staged prompts:

```text
request
  -> script_a
  -> script_b_candidates
  -> script_b_ranker
  -> plan_context
  -> variants
  -> critic
```

For `D1`, the selected category's general description is injected after the
category-neutral Script A stage. For `D2`, a separate Pydantic stage first
derives high-level guidance from raw Freek jokes tagged with the selected
category. That derived guidance then conditions Script B candidates, ranking,
semantic planning, generation, and criticism. It cannot prescribe scripts,
triggers, topics, or punchlines.

```text
D2 request
  -> script_a (category-neutral)
  -> Freek category guidance from matching raw jokes
  -> script_b_candidates
  -> script_b_ranker
  -> plan_context (creates the trigger)
  -> variants
  -> critic
```

The prepared script-opposition example datasets remain available as research
artifacts but are not injected into the A-D runtime prompts.

`Leedvermaak`, `Cirkelhumor`, and `Antihumor` currently have no matching Freek
examples in `data/freek_category_examples.json`. B2/D2 stop with a clear error
for those categories instead of falling back to generic context.

## Validated GTVH Flow

Pipelines `E1` and `E2` add an eight-stage, theory-gated path:

```text
request
  -> audience_expectation
  -> opposition_candidates
  -> theory_gate
  -> candidate_selection
  -> gtvh_plan
  -> variants
  -> blind_reconstruction
  -> pairwise_selection
```

The new path differs from C/D in several deliberate ways:

- Script A is represented by explicit audience propositions.
- Script B candidates have immutable IDs, an opposition axis, an opposed
  proposition, a shared anchor, two readings, and a logical mechanism.
- A non-compensatory gate requires dual compatibility, genuine opposition, a
  single axis, a usable anchor, coherent resolution, and a recognizable second
  reading.
- If no initial candidate passes, the pipeline uses the failed gate criteria to
  generate one complete replacement B1-B8 set and evaluates it again. Both
  attempts remain available in the trace.
- Candidate selection returns an ID; Python rejects IDs that did not pass the
  gate.
- The semantic plan covers the six GTVH knowledge resources.
- Generated variants separate setup and punchline and must contain their
  declared anchor verbatim.
- A plan-blind stage reconstructs the scripts from the finished jokes.
- Only variants passing blind reconstruction enter complete pairwise selection,
  which also returns an immutable variant ID.

Run only the validated conditions:

```bash
python3 "final ACL version/run_matrix.py" \
  --topic "de wachtrij bij de gemeente" \
  --pipeline E1 \
  --pipeline E2 \
  --model gpt-5.5
```

## Streamlit

```bash
streamlit run "final ACL version/app/streamlit_app.py"
```
