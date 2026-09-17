# Freek de Jonge ACL paper

This repository contains the manuscript, paper-specific generation and analysis
code, public de-identified evaluation data, and the locked stimulus run for the
ACL paper.

## Repository layout

```text
paper/       ACL manuscript, bibliography, style, and TikZ figures
code/        generation, analysis, and validation code
data/        public corpus annotations, stimuli, and ratings
runs/        reproducibility manifest for the locked 120-item run
```

The repository intentionally excludes participant-deployment code, Supabase
credentials and snapshots, private identifiers, audio, generated PDFs, caches,
and exploratory experiments unrelated to the paper.

## Fresh-clone checks

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python code/validation/validate_stimuli.py
.venv/bin/python code/analysis/validate_public_data.py
.venv/bin/python code/analysis/analyze_public_data.py
.venv/bin/python -m unittest discover -s code/generation/tests
```

The Python generation code requires an `OPENAI_API_KEY` only for live joke
generation. Dry runs do not call the API:

```sh
(cd code/generation && ../../.venv/bin/python run_matrix.py --topic 'family' --pipeline A1 --dry-run)
```

## Rebuild the manuscript

The local ACL/PRISM manuscript build uses the included bibliography and figures:

```sh
./paper/build.sh
```

The generated PDF and auxiliary files are written to the ignored
`paper/build/` directory. A TeX distribution with TikZ, natbib, booktabs, and
the other packages loaded by `paper/freek_acl.sty` is required.

## Re-run the analyses

Install the R packages listed in `requirements-r.txt`, then run:

```sh
Rscript code/analysis/analyze_acl_ordinal.R
Rscript code/analysis/analyze_acl_robustness.R
```

Both scripts read the public ratings CSV and write generated results below the
ignored `analysis/results/` directory.
