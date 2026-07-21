#!/usr/bin/env bash
#
# run_all.sh
# ==========
# Runs the full biomedical retraction analysis pipeline end to end.
# Each stage is an independent Python module, but you can also run any stage on its own.
#
# Usage:
#   bash run_all.sh              # run every stage in order
#   bash run_all.sh --no-citations # skip citation enrichment + citation analyses
#
set -euo pipefail

# Resolve the directory this script lives in, so it works from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python}"
RUN_CITATIONS=1

for arg in "$@"; do
  case "$arg" in
    --no-citations) RUN_CITATIONS=0 ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

echo "============================================================"
echo " Biomedical Retraction Analysis Pipeline"
echo "============================================================"

echo
echo ">>> Stage 1/6: Data preparation"
$PYTHON src/data_prep.py

echo
echo ">>> Stage 2/6: Descriptive analyses"
$PYTHON src/descriptive.py

echo
echo ">>> Stage 3/6: Per-subject analyses"
$PYTHON src/subject_analysis.py

if [ "$RUN_CITATIONS" -eq 1 ]; then
  echo
  echo ">>> Stage 4/6: Citation enrichment (network calls; may take a while)"
  $PYTHON src/citation_enrichment.py

  echo
  echo ">>> Stage 5/6: Citation analyses"
  $PYTHON src/citation_analysis.py
else
  echo
  echo ">>> Stages 4-5/6: Citation stages skipped (--no-citations)"
fi

echo
echo ">>> Stage 6/6: Statistical modelling"
$PYTHON src/statistics_models.py


echo
echo "============================================================"
echo " Done. Figures -> figures/   Tables -> tables/"
echo "============================================================"
