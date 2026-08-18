# Simplified C and E pipelines

This experimental alternative lives beside the original implementation. It does
not replace or modify `shared_script_opposition.py`, `script_opposition.py`,
`validated_gtvh.py`, or `plan_fidelity.py`.

## Design

```text
Shared: topic -> propose three meaning switches -> check and choose one
                                              |-> C: write three jokes -> evaluate and choose
                                              `-> E: add GTVH choices -> write three jokes -> evaluate and choose
```

The normal path uses four model calls for C and five for E. If none of the first
three meaning switches passes the check, the pipeline makes one repaired set and
checks it once more.

The prompts use ordinary descriptions:

- `script_a` is explained as the **normal meaning**.
- `script_b` is explained as the **hidden meaning**.
- Script Opposition is checked with five direct yes/no questions.
- E adds the Logical Mechanism, Situation, Target, Narrative Strategy, and
  Language only after the shared meaning switch has been approved.

The implementation still uses theory-oriented field names in its structured
trace. This keeps the output auditable without requiring prompt readers or the
model to work through dense theoretical instructions.

## What remains controlled

- C and E use the same meaning-switch construction and validation prompts.
- E cannot change the Script Opposition selected by the shared stages.
- Both pipelines produce exactly three variants.
- Both use the same combined fidelity and pairwise-selection stage.
- A variant that preserves all required choices outranks one that does not.
- The existing 20–45 word and three-sentence limit remains in force.
- C1/E1 use neutral guidance; C2/E2 use Freek-style guidance.

## Run

From `final ACL version`:

```bash
python3 run_simplified_ce.py --pipeline C1 --topic "de wachtrij bij de gemeente"
python3 run_simplified_ce.py --pipeline E2 --topic "de wachtrij bij de gemeente"
```

The original matrix runner remains connected to the original pipelines. This
separate runner makes accidental substitution in an existing experiment less
likely.
