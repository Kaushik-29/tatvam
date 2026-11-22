#!/usr/bin/env bash
# Held-out paraphrase set: generated locally with the same model (llama3.2:3b) and a NEW seed, only after the
# robustness fix was frozen. Up to 3 attempts per question, same validator as v1.
set -e
cd "$(dirname "$0")/../../.."
export PYTHONIOENCODING=utf-8
K=evaluation/experiments/paraphrase_robustness/results/kaggle
P="python -m evaluation.experiments.paraphrase_robustness.run_paraphrase"
gen() { for ds in synthea mimic eicu; do
          f=$K/paraphrase_prompts_${ds}_heldout$1.jsonl
          [ -s "$f" ] && python scripts/kaggle_answer_generation.py "$f" "$K/answers_paraphrase_prompts_${ds}_heldout$1.jsonl"
        done; }
$P export --set heldout && gen ""
$P export --set heldout --retry 2 && gen "_try2"
$P export --set heldout --retry 3 && gen "_try3"
$P import --set heldout
