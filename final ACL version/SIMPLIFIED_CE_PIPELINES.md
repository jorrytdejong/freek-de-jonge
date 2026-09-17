# Simplified C and E pipelines

This experimental alternative lives beside the original implementation. It does
not replace or modify `shared_script_opposition.py`, `script_opposition.py`,
`validated_gtvh.py`, or `plan_fidelity.py`.

## Design

```text
Shared: topic -> generate Script A -> propose two Script B options -> check and choose one
                                                                    |-> C: write two jokes -> evaluate and choose
                                                                    `-> E: add GTVH choices -> write two jokes -> evaluate and choose
```

The normal path uses five model calls for C and six for E. Script A is generated
in its own call and then passed unchanged to the Script B proposal call. If none
of the two Script B options passes the check, the pipeline makes one repaired
set and checks it once more.

The prompts use ordinary descriptions:

- Script A is generated separately as the audience's normal situation.
- Script B is generated in a later call as two alternative hidden situations.
- Script A treats the topic as a broad starting point, not a literal assignment.
  It finds an ordinary situation related to the topic. Script B receives that
  frozen situation and proposes hidden meanings without repeating this guidance.
- Script Opposition is checked with five direct yes/no questions.
- E adds the Logical Mechanism, Situation, Target, Narrative Strategy, and
  Language only after the shared meaning switch has been approved.

The implementation still uses theory-oriented field names in its structured
trace. This keeps the output auditable without requiring prompt readers or the
model to work through dense theoretical instructions.

## What remains controlled

- C and E use the same meaning-switch construction and validation prompts.
- E cannot change the Script Opposition selected by the shared stages.
- Both pipelines produce exactly two variants.
- Both use the same combined fidelity and pairwise-selection stage.
- A variant that preserves all required choices outranks one that does not.
- The existing 20–45 word and three-sentence limit remains in force.
- C1/E1 use neutral guidance; C2/E2 use Freek-style guidance.

The optional narrative setup and doctor-example artifacts remain in the separate
files for possible later experiments, but they are not used by this topic-only
version. E still differs from C only by adding its GTVH plan.

## Run

From `final ACL version`:

```bash
python3 run_simplified_ce.py --pipeline C1 --topic "de wachtrij bij de gemeente"
python3 run_simplified_ce.py --pipeline E2 --topic "de wachtrij bij de gemeente"
```

The original matrix runner remains connected to the original pipelines. This
separate runner makes accidental substitution in an existing experiment less
likely.
