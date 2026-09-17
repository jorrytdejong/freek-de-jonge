#!/usr/bin/env bash
set -euo pipefail

PAPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${1:-$PAPER_DIR/build}"

mkdir -p "$BUILD_DIR"

# Run TeX from the paper directory so the manuscript's relative inputs resolve
# identically on every checkout.  BibTeX is run from the build directory, with
# the paper directory explicitly available for the local .bib and .bst files.
export BIBINPUTS="$PAPER_DIR${BIBINPUTS:+:$BIBINPUTS}"
export BSTINPUTS="$PAPER_DIR${BSTINPUTS:+:$BSTINPUTS}"

cd "$PAPER_DIR"
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory "$BUILD_DIR" main.tex

(cd "$BUILD_DIR" && bibtex main)

pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory "$BUILD_DIR" main.tex
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory "$BUILD_DIR" main.tex

printf 'Wrote %s/main.pdf\n' "$BUILD_DIR"
