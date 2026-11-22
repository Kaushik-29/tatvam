# Blinded doctor review

Two clinicians rate the answers MedResolve already generated. No new generation is done. Three system versions are compared:

- **B0:** the LLM alone.
- **B4:** retrieval with patient context.
- **B5:** B4 plus claim verification.

## Send to each doctor (folder `packet/`)
| File | For |
|---|---|
| `MedResolve_Doctor_Review_RaterA.xlsx` | Doctor A |
| `MedResolve_Doctor_Review_RaterB.xlsx` | Doctor B |
| `MedResolve_Full_Patient_Records.xlsx` | Both (reference only, about 52k rows) |

Each rating workbook has three sheets:

1. **Instructions:** the task and anchored 1–5 scales.
2. **Ratings:** 120 shuffled answers, with drop-downs in the yellow columns.
3. **Question records:** for each question, a short patient overview plus every record in the benchmark's gold concept groups. This is the same chart for all three versions, so it favours none of them.

**Do not send** `key/review_key.json`. It maps each row to its system version.

## Before sending
- Ask the guide (Dr. B. Jothi) whether the department needs ethics or IRB approval for this. The patient data is synthetic (Synthea) or open-access de-identified (MIMIC-IV demo), and the doctors are rating text, not patients.
- Record each doctor's name, specialty and years of experience for the paper.

## When both files are back
```
python -m evaluation.experiments.doctor_review.analyze_ratings --raters RaterA_filled.xlsx RaterB_filled.xlsx
```
The script writes `results/doctor_review_summary.json`, which contains:

- Inter-rater agreement: exact agreement, Cohen's kappa, quadratic-weighted kappa, and Krippendorff's alpha.
- The mean score for each version, with patient-clustered bootstrap CIs.
- Paired differences: B4−B0, B5−B4 and B5−B0.
- How well the automatic claim verifier agrees with the doctors on unsupported patient claims.

## Design notes and limitations
- **Questions:** 40 in total (24 Synthea, 16 MIMIC), stratified by category, seed 2026, giving 38 patients. Answers to the same question are never placed next to each other.
- **Answer sources:**
  - Synthea: Kaggle run 20261120_1910.
  - MIMIC B0/B4: run 20261120_2042.
  - MIMIC B5: re-run 20261121_0045, made after the date-shift fix. MIMIC B5 therefore comes from a different GPU run than B0/B4.
- **Answer text:** each answer is the exact released text. The one exception is the constant "research prototype" footer, which is removed from every version.
- **Blinding is partial.** B0 has no citations, and B5 can show a "statements withheld" note. Report this as a limitation.
- **Result:** a human evaluation of a research prototype on synthetic or de-identified data. It is not clinical validation.
