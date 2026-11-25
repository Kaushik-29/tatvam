"""
Generate a short explanation for each of the 40 doctor-assessment answers.

The original run (doctor_assessment_app/backend/data/app_answers_run.json) asked llama3.2:3b for a letter
only. This script asks the SAME model, given the case and the option it already chose, to explain that
choice in 2-4 sentences. These are post-hoc explanations of a fixed answer, not the model's original
reasoning, and no clinician has reviewed them. Output (resumable):
evaluation/experiments/diagnostic_cases/ai_reasoning.json

  python scripts/generate_case_reasoning.py      # then: python scripts/build_test_cases.py
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.llm.ollama_client import OllamaClient  # noqa: E402

SRC = ROOT / "doctor_assessment_app" / "backend" / "data"
OUT = ROOT / "evaluation" / "experiments" / "diagnostic_cases" / "ai_reasoning.json"
MODEL, TEMPERATURE, SEED = "llama3.2:3b", 0.0, 7
SYSTEM = ("You are explaining a diagnostic choice in a clinical multiple-choice case. Use only facts stated in "
          "the case. Be concise and do not add new findings.")


def prompt(q, chosen: str) -> str:
    opts = "\n".join(f"{chr(65 + i)}. {o}" for i, o in enumerate(q["options"]))
    return (f"Case: {q['vignette']}\n\nQuestion: {q['prompt']}\n\nOptions:\n{opts}\n\n"
            f"The chosen answer is: {chosen}.\n"
            "In 2 to 4 sentences, explain which findings in the case support this answer and, briefly, why the "
            "main alternative is less likely. Plain text, no headings or lists.")


def main():
    qs = json.loads((SRC / "questions.json").read_text(encoding="utf-8"))["questions"]
    picks = {c["id"]: c for c in json.loads((SRC / "app_answers_run.json").read_text(encoding="utf-8"))["cases"]}
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {
        "model": MODEL, "temperature": TEMPERATURE, "seed": SEED, "system": SYSTEM,
        "note": "Post-hoc explanations of the already-chosen answer by the same model; not clinician-reviewed.",
        "cases": {}}
    llm = OllamaClient(model=MODEL, timeout=600)
    for q in qs:
        key = str(q["id"])
        if key in done["cases"]:
            continue
        chosen = picks[q["id"]]["app_answer"]
        t0 = time.time()
        text = llm.generate(prompt(q, chosen), system=SYSTEM, max_tokens=220, temperature=TEMPERATURE, seed=SEED).strip()
        done["cases"][key] = {"chosen": chosen, "reasoning": " ".join(text.split()), "seconds": round(time.time() - t0, 1)}
        done["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(done, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{key:>2} {time.time() - t0:5.1f}s  {q['title']}", flush=True)
    print("done:", len(done["cases"]), "cases")


if __name__ == "__main__":
    main()
