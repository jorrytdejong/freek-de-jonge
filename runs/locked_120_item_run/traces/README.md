# Locked generation traces

This directory contains the per-item generation traces and failed-attempt records
for the locked 120-item ACL stimulus run described by the parent
`run_manifest.json`. The `items/` directory contains one JSON record for each of
20 topics crossed with six conditions; each record preserves the prompts,
intermediate semantic plans, candidate variants, validation and selection
outputs, model usage, and final joke. The `failures/` directory preserves
rejected or retried attempts. `acl_jokes.md` is a readable rendering of the
accepted 120-item bank.

The traces are provided for reproducibility and auditability. Participant
ratings and corpus annotations are stored separately in `data/`.
