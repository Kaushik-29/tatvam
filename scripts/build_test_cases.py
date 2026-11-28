"""
Snapshot the 40 doctor-assessment cases for MedResolve's "Test cases" page.

Reads the Doctor Diagnostic Assessment app's cases and its stored AI run, and adds what MedResolve's
patient app would do with each case text (the deterministic emergency screen). Writes
evaluation/experiments/diagnostic_cases/test_cases.json, which the API serves read-only.

  python scripts/build_test_cases.py

The diagnoses were chosen by the AI model alone (multiple choice), not by MedResolve's patient pipeline,
which never names a diagnosis. The cases are sample content with no answer key until a clinician
reviews them, so no answer is marked right or wrong.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.evidence_reconciliation.emergency import screen_text  # noqa: E402

SRC = ROOT / "doctor_assessment_app" / "backend" / "data"
OUT = ROOT / "evaluation" / "experiments" / "diagnostic_cases" / "test_cases.json"
REASONING = OUT.with_name("ai_reasoning.json")          # from scripts/generate_case_reasoning.py (optional)
RATER = OUT.with_name("rater_1.json")                    # one clinician rater's answers (optional; not an answer key)


def main():
    qs = json.loads((SRC / "questions.json").read_text(encoding="utf-8"))
    run = json.loads((SRC / "app_answers_run.json").read_text(encoding="utf-8"))
    picks = {c["id"]: c for c in run["cases"]}
    phases = {p["number"]: p for p in qs["phases"]}
    reasoning = json.loads(REASONING.read_text(encoding="utf-8")) if REASONING.exists() else {"cases": {}}
    rater = json.loads(RATER.read_text(encoding="utf-8")) if RATER.exists() else None
    cases = []
    for q in qs["questions"]:
        pick = picks[q["id"]]
        em = screen_text(q["vignette"])
        cases.append({
            "id": q["id"], "phase": q["phase"], "phase_title": phases[q["phase"]]["title"],
            "specialty": q["specialty"], "title": q["title"], "vignette": q["vignette"], "question": q["prompt"],
            "options": q["options"], "ai_answer": pick["app_answer"], "ai_index": pick["chosen_index"],
            "answer_index": q.get("answer_index"),                     # filled in only after clinician review
            "ai_reasoning": (reasoning["cases"].get(str(q["id"])) or {}).get("reasoning"),
            "rater_answer": rater["answers"].get(str(q["id"])) if rater else None,
            "patient_app": {"emergency": em.is_emergency, "red_flags": em.red_flags},
        })
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Doctor Diagnostic Assessment app (doctor_assessment_app/backend/data)",
        "notice": qs["_notice"],
        "ai_run": {k: run[k] for k in ("generated_at", "model", "method", "seconds")},
        "reasoning_run": ({k: reasoning.get(k) for k in ("model", "temperature", "seed", "note", "generated_at")}
                          if reasoning["cases"] else None),
        "rater": ({k: v for k, v in rater.items() if k != "answers"} if rater else None),
        "phases": qs["phases"],
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for c in cases:
        if c["rater_answer"] is not None and c["rater_answer"] not in c["options"]:
            raise SystemExit(f"case {c['id']}: rater answer is not one of the options")
    n_em = sum(c["patient_app"]["emergency"] for c in cases)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(cases)} cases, {n_em} would get an emergency warning in the patient app")


if __name__ == "__main__":
    main()
