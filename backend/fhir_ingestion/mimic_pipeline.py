"""
OPTIONAL MIMIC-IV / MIMIC-IV-Note / MIMIC-IV-ED ingestion — PENDING AUTHORIZATION.

Status: NOT RUN. No MIMIC data has been downloaded, generated or used anywhere in MedResolve.

Access requires (per PhysioNet): a credentialed PhysioNet account, completed human-subjects
research training (CITI "Data or Specimens Only Research"), and a signed Data Use Agreement
for each project:
  MIMIC-IV v3.1          https://physionet.org/content/mimiciv/3.1/
  MIMIC-IV-Note v2.2     https://physionet.org/content/mimic-iv-note/2.2/
  MIMIC-IV-ED v2.2       https://physionet.org/content/mimic-iv-ed/2.2/
This module never downloads anything. The credentialed user places the files locally under
data/datasets/mimic/raw/{mimiciv/3.1, mimic-iv-note/2.2, mimic-iv-ed/2.2}/ and runs it.

DUA safeguards enforced here:
  * refuses to run unless the user confirms authorization (`--i-have-physionet-authorization`)
  * MIMIC patients are stored with source="mimic_iv" and are EXCLUDED from demo listings
  * the pipeline LLM client only accepts a localhost Ollama URL (backend/llm/ollama_client.py)
  * scripts/make_cloud_bundle.py refuses any path containing "mimic"
  * derived artefacts stay in data/datasets/mimic/processed (gitignored)

Mapping (documented linkage keys: subject_id, hadm_id, stay_id, note_id):
  hosp/patients            -> Patient (anchor_age/anchor_year shifted dates kept as-is)
  hosp/admissions          -> clinical_encounters/consultations (hadm_id = encounter_id)
  hosp/diagnoses_icd + d_icd_diagnoses -> medical_history/diagnoses (ICD-9/10, seq_num kept)
  hosp/prescriptions       -> medication_history/{current,previous}_medications (starttime/stoptime)
  hosp/labevents + d_labitems -> laboratory_observations/laboratory_results (valuenum, valueuom, ref range)
  hosp/procedures_icd      -> medical_history/procedures
  note/discharge           -> medical_documents/discharge_summaries (note_id, hadm_id)
  note/radiology           -> medical_documents/diagnostic_reports
  ed/edstays + ed/triage   -> clinical_encounters/complaints (chiefcomplaint) + vital_signs (triage vitals)
  ed/vitalsign             -> laboratory_observations/vital_signs (stay_id)
Limitation: MIMIC is hospital/ED-centred; it is not a lifelong outpatient record.
"""

import argparse
import sys
from pathlib import Path

from backend.config import DATA_DIR

RAW = DATA_DIR / "datasets" / "mimic" / "raw"
EXPECTED = {
    "mimiciv/3.1/hosp/patients.csv.gz": "MIMIC-IV hosp module",
    "mimic-iv-note/2.2/note/discharge.csv.gz": "MIMIC-IV-Note",
    "mimic-iv-ed/2.2/ed/edstays.csv.gz": "MIMIC-IV-ED",
}


def status() -> dict:
    present = {k: (RAW / k).exists() for k in EXPECTED}
    return {"status": "PENDING_AUTHORIZATION" if not any(present.values()) else "FILES_PRESENT_NOT_INGESTED",
            "expected_files": present, "raw_dir": str(RAW)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--i-have-physionet-authorization", action="store_true",
                    help="confirm you are a credentialed PhysioNet user with signed DUAs for all three datasets")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    st = status()
    if a.status or not a.i_have_physionet_authorization:
        print(st)
        if not a.i_have_physionet_authorization:
            print("Refusing to ingest: authorization flag not given. MIMIC evaluation remains PENDING.")
        return
    missing = [k for k, ok in st["expected_files"].items() if not ok]
    if missing:
        sys.exit(f"Missing credentialed files under {RAW}: {missing}. Download them yourself from PhysioNet.")
    raise NotImplementedError(
        "Mapping spec is documented above; implementation is deliberately deferred until authorized data "
        "is available to validate against (no code path is shipped that was never run on real files).")


if __name__ == "__main__":
    main()
