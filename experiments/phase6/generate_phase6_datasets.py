"""
MedResolve Phase 6 — Synthetic Dataset Generation and Manifest Freezing Script
Version: 2.1.0

Generates:
1. 20 independent Development Scenarios (DEV_SCEN_001 - DEV_SCEN_020)
2. 100 independent Final Evaluation Scenarios (EVAL_SCEN_001 - EVAL_SCEN_100)
3. Cryptographically frozen Manifest (eval_scenarios_manifest.json) with SHA-256 checksums

Action Distribution for 100 Evaluation Scenarios:
- 44 EXPECTED_EXPLAIN (15 clean + 15 chronological + 7 baseline lab + 7 prior Rx)
- 48 EXPECTED_ASK (13 missing units + 13 analyte swaps + 10 omitted fields + 6 solitary decimal + 6 solitary Rx)
- 8 EXPECTED_ABSTAIN (2 decimal conflicts + 2 unit conflicts + 2 Rx conflicts + 2 panel conflicts)

Independent Evidence Distribution:
- 29 True (7 decimal + 7 medication + 15 temporal)
- 56 False (all ASK and ABSTAIN scenarios)
- 15 Clean Controls
"""

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = WORKSPACE_ROOT / "data" / "processed" / "phase6"
KB_DIR = WORKSPACE_ROOT / "data" / "knowledge_base_v2" / "documents"

FROZEN_OCR_SHA256 = "38b1deac035263a7d4d20b4b67319f79472219c2b7efdd7a4181989b0fc47a82"


def compute_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_file_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_sample_guideline_passages() -> Dict[str, List[Dict[str, Any]]]:
    """
    Loads authentic guideline passages from data/knowledge_base_v2/documents/.
    """
    passages_by_domain: Dict[str, List[Dict[str, Any]]] = {}
    if not KB_DIR.exists():
        return {}

    for doc_file in KB_DIR.glob("*.json"):
        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                doc_id = data.get("document_id", "")
                title = data.get("title", "")
                org = data.get("author_or_organization", "")
                passages = data.get("passages", [])
                formatted = [
                    {
                        "passage_id": p.get("passage_id"),
                        "document_id": doc_id,
                        "document_title": title,
                        "organization": org,
                        "section_heading": p.get("section_heading", ""),
                        "text": p.get("text", ""),
                    }
                    for p in passages
                ]
                # Categorize by keyword
                fn_lower = doc_file.name.lower()
                if "diabetes" in fn_lower:
                    passages_by_domain["diabetes"] = formatted
                elif "hypertension" in fn_lower:
                    passages_by_domain["hypertension"] = formatted
                elif "gerd" in fn_lower:
                    passages_by_domain["gerd"] = formatted
                elif "acs" in fn_lower:
                    passages_by_domain["cardiac"] = formatted
                elif "asthma" in fn_lower or "bronchitis" in fn_lower or "pneumonia" in fn_lower:
                    passages_by_domain["respiratory"] = formatted
                else:
                    passages_by_domain["general"] = formatted
        except Exception:
            pass
    return passages_by_domain


def get_fixed_passages_for_domain(domain: str, passages_by_domain: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    plist = passages_by_domain.get(domain) or passages_by_domain.get("general") or []
    return plist[:3] if plist else [
        {
            "passage_id": f"FIXED_{domain.upper()}_01",
            "document_id": f"DOC_GUIDELINE_{domain.upper()}",
            "document_title": f"Clinical Practice Guideline: Management of {domain.title()}",
            "organization": "Ministry of Health and Family Welfare / National Health Portal",
            "section_heading": "Diagnostic Criteria and Monitoring",
            "text": f"Standard clinical practice guidelines recommend careful longitudinal monitoring of diagnostic markers and treatment reconciliation for {domain}."
        }
    ]


def generate_single_scenario(
    scenario_id: str,
    category_id: int,
    category_name: str,
    sub_index: int,
    is_development: bool,
    passages_by_domain: Dict[str, List[Dict[str, Any]]],
    assigned_action: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates a single synthetic scenario with complete structured provenance,
    corroborating evidence specifications, and fixed reference passages.
    """
    # Deterministic seed variation
    scen_seed = hash(f"{scenario_id}_{category_id}_{sub_index}")

    if category_id == 1:
        # Category 1: Decimal-Point Corruption
        domain = "cardiac" if sub_index % 2 == 0 else "diabetes"
        action = assigned_action or ("EXPECTED_EXPLAIN" if sub_index < 7 else ("EXPECTED_ASK" if sub_index < 13 else "EXPECTED_ABSTAIN"))
        true_val = "1.2"
        corrupt_val = "12.0"
        concept = "serum_creatinine"
        concept_name = "Serum Creatinine"
        unit = "mg/dL"

        if action == "EXPECTED_EXPLAIN":
            res_path = "RESOLVE_VIA_BASELINE"
            has_ind_ev = True
            ev_id = f"ev_prior_cr_{scenario_id.lower()}"
            corrob_record = {
                "evidence_id": ev_id,
                "source_type": "LABORATORY_REPORT",
                "concept": concept,
                "corroborating_value": true_val,
                "unit": unit,
                "recorded_timestamp": "2026-10-15T09:00:00Z",
                "source_provenance": "Metropolis Central Diagnostic Laboratory - Prior Baseline Panel"
            }
            prior_records = [{
                "evidence_id": ev_id,
                "concept": concept,
                "value": true_val,
                "unit": unit,
                "source_type": "LABORATORY_REPORT",
                "recorded_timestamp": "2026-10-15T09:00:00Z",
                "document_title": "Baseline Comprehensive Metabolic Panel"
            }]
        elif action == "EXPECTED_ABSTAIN":
            res_path = "CONTAIN_ABSTAIN_CONFLICT"
            has_ind_ev = False
            corrob_record = None
            prior_records = [
                {
                    "evidence_id": f"ev_hospA_{scenario_id.lower()}",
                    "concept": concept,
                    "value": "1.1",
                    "unit": unit,
                    "source_type": "LABORATORY_REPORT",
                    "recorded_timestamp": "2026-10-30T10:00:00Z",
                    "document_title": "City Hospital Diagnostic Lab (Report A)"
                },
                {
                    "evidence_id": f"ev_hospB_{scenario_id.lower()}",
                    "concept": concept,
                    "value": "3.8",
                    "unit": unit,
                    "source_type": "LABORATORY_REPORT",
                    "recorded_timestamp": "2026-10-30T11:30:00Z",
                    "document_title": "Apex Specialty Hospital Lab (Report B - Contradictory Acute Finding)"
                }
            ]
        else:
            res_path = "CONTAIN_ASK_USER"
            has_ind_ev = False
            corrob_record = None
            prior_records = []

        raw_ocr = f"LAB REPORT:\nSerum Creatinine: {corrupt_val} {unit}\nRef Range: 0.7 - 1.3 mg/dL"

    elif category_id == 2:
        # Category 2: Missing or Incorrect Unit
        domain = "diabetes"
        action = assigned_action or ("EXPECTED_ASK" if sub_index < 13 else "EXPECTED_ABSTAIN")
        true_val = "110"
        corrupt_val = "110"
        concept = "fasting_blood_glucose"
        concept_name = "Fasting Blood Glucose"
        unit = "mg/dL"
        corrob_record = None
        has_ind_ev = False

        if action == "EXPECTED_ABSTAIN":
            res_path = "CONTAIN_ABSTAIN_CONFLICT"
            prior_records = [
                {
                    "evidence_id": f"ev_glu_us_{scenario_id.lower()}",
                    "concept": concept,
                    "value": "110",
                    "unit": "mg/dL",
                    "source_type": "LABORATORY_REPORT",
                    "recorded_timestamp": "2026-10-20T08:00:00Z",
                    "document_title": "US Standard Outpatient Lab (mg/dL Standard)"
                },
                {
                    "evidence_id": f"ev_glu_si_{scenario_id.lower()}",
                    "concept": concept,
                    "value": "110",
                    "unit": "mmol/L",
                    "source_type": "LABORATORY_REPORT",
                    "recorded_timestamp": "2026-10-25T08:00:00Z",
                    "document_title": "International Clinic Lab (Irreconcilable mmol/L notation)"
                }
            ]
        else:
            res_path = "CONTAIN_ASK_USER"
            prior_records = []

        raw_ocr = f"DIAGNOSTIC TEST:\nFasting Blood Glucose: {corrupt_val}\n(Unit transcription missing)"

    elif category_id == 3:
        # Category 3: Medication Strength Misreading
        domain = "hypertension"
        action = assigned_action or ("EXPECTED_EXPLAIN" if sub_index < 7 else ("EXPECTED_ASK" if sub_index < 13 else "EXPECTED_ABSTAIN"))
        true_val = "10"
        corrupt_val = "100"
        concept = "lisinopril_dosage"
        concept_name = "Lisinopril Daily Dosage"
        unit = "mg"

        if action == "EXPECTED_EXPLAIN":
            res_path = "RESOLVE_VIA_BASELINE"
            has_ind_ev = True
            ev_id = f"ev_prior_rx_{scenario_id.lower()}"
            corrob_record = {
                "evidence_id": ev_id,
                "source_type": "PRIOR_PRESCRIPTION",
                "concept": concept,
                "corroborating_value": true_val,
                "unit": unit,
                "recorded_timestamp": "2026-09-10T14:00:00Z",
                "source_provenance": "Cardiology Outpatient Clinic - Active Maintenance Prescription"
            }
            prior_records = [{
                "evidence_id": ev_id,
                "concept": concept,
                "value": true_val,
                "unit": unit,
                "source_type": "PRIOR_PRESCRIPTION",
                "recorded_timestamp": "2026-09-10T14:00:00Z",
                "document_title": "Primary Care Maintenance Prescription"
            }]
        elif action == "EXPECTED_ABSTAIN":
            res_path = "CONTAIN_ABSTAIN_CONFLICT"
            has_ind_ev = False
            corrob_record = None
            prior_records = [
                {
                    "evidence_id": f"ev_discharge_rx_{scenario_id.lower()}",
                    "concept": concept,
                    "value": "10",
                    "unit": unit,
                    "source_type": "PRIOR_PRESCRIPTION",
                    "recorded_timestamp": "2026-10-28T16:00:00Z",
                    "document_title": "Hospital Inpatient Discharge Summary: Discontinue Lisinopril, Start Losartan"
                },
                {
                    "evidence_id": f"ev_specialist_rx_{scenario_id.lower()}",
                    "concept": concept,
                    "value": "20",
                    "unit": unit,
                    "source_type": "PRIOR_PRESCRIPTION",
                    "recorded_timestamp": "2026-10-29T10:00:00Z",
                    "document_title": "Private Cardiologist Prescription: Increase Lisinopril to 20 mg Daily"
                }
            ]
        else:
            res_path = "CONTAIN_ASK_USER"
            has_ind_ev = False
            corrob_record = None
            prior_records = []

        raw_ocr = f"PRESCRIPTION Rx:\nRx: Lisinopril {corrupt_val} {unit} PO daily\nQty: 30 tablets"

    elif category_id == 4:
        # Category 4: Analyte-Value Misassociation
        domain = "diabetes"
        action = assigned_action or ("EXPECTED_ASK" if sub_index < 13 else "EXPECTED_ABSTAIN")
        true_val = "Glucose 115 mg/dL, HbA1c 7.2%"
        corrupt_val = "Glucose 7.2 mg/dL, HbA1c 115%"
        concept = "glycemic_panel"
        concept_name = "Glycemic Panel (Glucose & HbA1c)"
        unit = "multi_unit"
        corrob_record = None
        has_ind_ev = False

        if action == "EXPECTED_ABSTAIN":
            res_path = "CONTAIN_ABSTAIN_CONFLICT"
            prior_records = [
                {
                    "evidence_id": f"ev_panel_a_{scenario_id.lower()}",
                    "concept": concept,
                    "value": "HbA1c 6.1%, FPG 95 mg/dL",
                    "unit": "multi_unit",
                    "source_type": "LABORATORY_REPORT",
                    "recorded_timestamp": "2026-10-15T08:00:00Z",
                    "document_title": "Lab A: Normal Glycemic Status"
                },
                {
                    "evidence_id": f"ev_panel_b_{scenario_id.lower()}",
                    "concept": concept,
                    "value": "HbA1c 11.4%, FPG 280 mg/dL",
                    "unit": "multi_unit",
                    "source_type": "LABORATORY_REPORT",
                    "recorded_timestamp": "2026-10-16T08:00:00Z",
                    "document_title": "Lab B: Severe Uncontrolled Diabetes (Contradictory Panel)"
                }
            ]
        else:
            res_path = "CONTAIN_ASK_USER"
            prior_records = []

        raw_ocr = f"LABORATORY REPORT:\nFasting Blood Glucose: 7.2 mg/dL\nHbA1c Glycated Hemoglobin: 115 %"

    elif category_id == 5:
        # Category 5: Temporal Ordering Inversion
        domain = "diabetes"
        action = "EXPECTED_EXPLAIN"
        res_path = "RESOLVE_VIA_CHRONOLOGY"
        has_ind_ev = True
        true_val = "Recent FPG 105 mg/dL (2026), Baseline FPG 180 mg/dL (2021)"
        corrupt_val = "Recent FPG 180 mg/dL (labeled 2026), Follow-up 105 mg/dL (labeled 2021)"
        concept = "glucose_temporal_trend"
        concept_name = "Longitudinal Glucose Trend"
        unit = "mg/dL"
        ev_id = f"ev_temporal_anchor_{scenario_id.lower()}"
        corrob_record = {
            "evidence_id": ev_id,
            "source_type": "LABORATORY_REPORT",
            "concept": concept,
            "corroborating_value": "105",
            "unit": unit,
            "recorded_timestamp": "2026-10-25T08:00:00Z",
            "source_provenance": "Longitudinal Electronic Medical Record - Authenticated 2026 Follow-up"
        }
        prior_records = [
            {
                "evidence_id": f"ev_t2021_{scenario_id.lower()}",
                "concept": "fasting_blood_glucose",
                "value": "180",
                "unit": "mg/dL",
                "source_type": "LABORATORY_REPORT",
                "recorded_timestamp": "2021-04-12T09:00:00Z",
                "document_title": "Historic Baseline Lab Report (2021)"
            },
            {
                "evidence_id": ev_id,
                "concept": "fasting_blood_glucose",
                "value": "105",
                "unit": "mg/dL",
                "source_type": "LABORATORY_REPORT",
                "recorded_timestamp": "2026-10-25T08:00:00Z",
                "document_title": "Verified Recent Follow-Up Lab (2026)"
            }
        ]
        raw_ocr = "CHRONIC DISEASE PROGRESS NOTE:\nHistorical Glucose (2026): 180 mg/dL\nLatest Glucose (2021): 105 mg/dL"

    elif category_id == 6:
        # Category 6: Critical Field Omission
        domain = "cardiac"
        action = "EXPECTED_ASK"
        res_path = "CONTAIN_ASK_USER"
        has_ind_ev = False
        corrob_record = None
        true_val = "Complete Renal Panel (BUN, Cr, Na, K)"
        corrupt_val = "Renal Panel: BUN 18 mg/dL, Na 140 mEq/L (Potassium & Creatinine omitted)"
        concept = "renal_electrolyte_panel"
        concept_name = "Renal & Electrolyte Panel"
        unit = "panel"
        prior_records = []
        raw_ocr = "BASIC METABOLIC PANEL:\nBlood Urea Nitrogen: 18 mg/dL\nSodium: 140 mEq/L\n(Potassium and Creatinine lines missing in transcription)"

    else:
        # Category 7: Clean Controls
        domain = "gerd" if sub_index % 3 == 0 else ("hypertension" if sub_index % 3 == 1 else "respiratory")
        action = "EXPECTED_EXPLAIN"
        res_path = "DELIVER_EXPLANATION"
        has_ind_ev = False
        corrob_record = None
        true_val = "98.6 degF, BP 120/80 mmHg, SpO2 98%"
        corrupt_val = true_val
        concept = "routine_vitals_panel"
        concept_name = "Routine Clinical Vitals"
        unit = "panel"
        prior_records = [
            {
                "evidence_id": f"ev_clean_history_{scenario_id.lower()}",
                "concept": "prior_annual_wellness",
                "value": "Normal baseline examination",
                "unit": None,
                "source_type": "EHR_EXTRACTED_NOTE",
                "recorded_timestamp": "2025-10-10T10:00:00Z",
                "document_title": "Annual Wellness Visit Summary"
            }
        ]
        raw_ocr = "VITALS & EXAMINATION NOTE:\nCore Temp: 98.6 degF\nBlood Pressure: 120/80 mmHg\nPulse: 72 bpm\nSpO2: 98% on room air\nAll findings within normal clinical limits."

    fixed_passages = get_fixed_passages_for_domain(domain, passages_by_domain)

    scenario_dict = {
        "scenario_id": scenario_id,
        "is_development": is_development,
        "category_id": category_id,
        "category_name": category_name,
        "is_corrupted": (category_id != 7),
        "domain": domain,
        "patient_profile": {
            "patient_id": f"PT_{scenario_id}",
            "age": 45 + (sub_index % 30),
            "gender": "F" if sub_index % 2 == 0 else "M",
            "primary_condition": domain.title(),
        },
        "ocr_extraction": {
            "concept": concept,
            "concept_name_en": concept_name,
            "extracted_value": corrupt_val,
            "extracted_unit": unit if unit != "panel" and unit != "multi_unit" else None,
            "unit_status": "MISSING" if category_id == 2 else "EXPLICIT",
            "extraction_confidence": 0.94 if category_id != 2 else 0.72,
            "raw_text": raw_ocr,
        },
        "prior_records": prior_records,
        "fixed_reference_passages": fixed_passages,
        # EVALUATOR-ONLY GROUND TRUTH (Stripped by sanitizer)
        "expected_action": action,
        "expected_resolution_path": res_path,
        "has_independent_corroborating_evidence": has_ind_ev,
        "independent_corroborating_evidence_available": has_ind_ev,
        "corroborating_evidence_record": corrob_record,
        "true_value": true_val,
        "corrupted_value": corrupt_val if category_id != 7 else None,
        "affected_concept": concept,
        "injected_error_type": category_name if category_id != 7 else "NONE",
        "expected_patient_specific_claims": [f"{concept_name}: {true_val}"],
        "expected_missing_information": ["unit"] if category_id == 2 else ([] if category_id != 6 else ["potassium", "creatinine"]),
        "expected_containment_requirement": (action in {"EXPECTED_ASK", "EXPECTED_ABSTAIN"}),
        "expected_abstention_requirement": (action == "EXPECTED_ABSTAIN"),
    }
    return scenario_dict


def build_evaluation_cohort(passages_by_domain: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Builds exactly 100 evaluation scenarios matching the approved distribution:
    - Cat 1: 15 (7 Explain, 6 Ask, 2 Abstain)
    - Cat 2: 15 (0 Explain, 13 Ask, 2 Abstain)
    - Cat 3: 15 (7 Explain, 6 Ask, 2 Abstain)
    - Cat 4: 15 (0 Explain, 13 Ask, 2 Abstain)
    - Cat 5: 15 (15 Explain, 0 Ask, 0 Abstain)
    - Cat 6: 10 (0 Explain, 10 Ask, 0 Abstain)
    - Cat 7: 15 (15 Explain, 0 Ask, 0 Abstain)
    Total = 100 scenarios.
    Actions = 44 EXPECTED_EXPLAIN, 48 EXPECTED_ASK, 8 EXPECTED_ABSTAIN.
    """
    categories = [
        (1, "Decimal-Point Corruption", 15),
        (2, "Missing or Incorrect Unit", 15),
        (3, "Medication Strength Misreading", 15),
        (4, "Analyte-Value Misassociation", 15),
        (5, "Temporal Ordering Inversion", 15),
        (6, "Critical Field Omission", 10),
        (7, "Clean Controls", 15),
    ]

    scenarios = []
    scen_counter = 1

    for cat_id, cat_name, count in categories:
        for idx in range(count):
            scen_id = f"EVAL_SCEN_{scen_counter:03d}"
            scen = generate_single_scenario(
                scenario_id=scen_id,
                category_id=cat_id,
                category_name=cat_name,
                sub_index=idx,
                is_development=False,
                passages_by_domain=passages_by_domain,
            )
            scenarios.append(scen)
            scen_counter += 1

    assert len(scenarios) == 100, f"Expected exactly 100 scenarios, got {len(scenarios)}"
    return scenarios


def build_development_cohort(passages_by_domain: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Builds exactly 20 independent development scenarios:
    - 3 Cat 1 (1 Explain, 1 Ask, 1 Abstain)
    - 3 Cat 2 (0 Explain, 2 Ask, 1 Abstain)
    - 3 Cat 3 (1 Explain, 1 Ask, 1 Abstain)
    - 3 Cat 4 (0 Explain, 2 Ask, 1 Abstain)
    - 3 Cat 5 (3 Explain, 0 Ask, 0 Abstain)
    - 2 Cat 6 (0 Explain, 2 Ask, 0 Abstain)
    - 3 Cat 7 (3 Explain, 0 Ask, 0 Abstain)
    Total = 20 scenarios.
    Actions: 8 EXPECTED_EXPLAIN, 8 EXPECTED_ASK, 4 EXPECTED_ABSTAIN.
    """
    dev_specs = [
        (1, "Decimal-Point Corruption", "EXPECTED_EXPLAIN"),
        (1, "Decimal-Point Corruption", "EXPECTED_ASK"),
        (1, "Decimal-Point Corruption", "EXPECTED_ABSTAIN"),
        (2, "Missing or Incorrect Unit", "EXPECTED_ASK"),
        (2, "Missing or Incorrect Unit", "EXPECTED_ASK"),
        (2, "Missing or Incorrect Unit", "EXPECTED_ABSTAIN"),
        (3, "Medication Strength Misreading", "EXPECTED_EXPLAIN"),
        (3, "Medication Strength Misreading", "EXPECTED_ASK"),
        (3, "Medication Strength Misreading", "EXPECTED_ABSTAIN"),
        (4, "Analyte-Value Misassociation", "EXPECTED_ASK"),
        (4, "Analyte-Value Misassociation", "EXPECTED_ASK"),
        (4, "Analyte-Value Misassociation", "EXPECTED_ABSTAIN"),
        (5, "Temporal Ordering Inversion", "EXPECTED_EXPLAIN"),
        (5, "Temporal Ordering Inversion", "EXPECTED_EXPLAIN"),
        (5, "Temporal Ordering Inversion", "EXPECTED_EXPLAIN"),
        (6, "Critical Field Omission", "EXPECTED_ASK"),
        (6, "Critical Field Omission", "EXPECTED_ASK"),
        (7, "Clean Controls", "EXPECTED_EXPLAIN"),
        (7, "Clean Controls", "EXPECTED_EXPLAIN"),
        (7, "Clean Controls", "EXPECTED_EXPLAIN"),
    ]

    scenarios = []
    for idx, (cat_id, cat_name, action) in enumerate(dev_specs, start=1):
        scen_id = f"DEV_SCEN_{idx:03d}"
        scen = generate_single_scenario(
            scenario_id=scen_id,
            category_id=cat_id,
            category_name=cat_name,
            sub_index=idx,
            is_development=True,
            passages_by_domain=passages_by_domain,
            assigned_action=action,
        )
        scenarios.append(scen)

    assert len(scenarios) == 20, f"Expected exactly 20 development scenarios, got {len(scenarios)}"
    return scenarios


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    passages_by_domain = load_sample_guideline_passages()

    print("Generating Phase 6 evaluation cohort (100 scenarios)...")
    eval_scenarios = build_evaluation_cohort(passages_by_domain)

    print("Generating Phase 6 development cohort (20 scenarios)...")
    dev_scenarios = build_development_cohort(passages_by_domain)

    eval_file = OUTPUT_DIR / "eval_scenarios.json"
    dev_file = OUTPUT_DIR / "dev_scenarios.json"
    manifest_file = OUTPUT_DIR / "eval_scenarios_manifest.json"

    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(eval_scenarios, f, indent=2)

    with open(dev_file, "w", encoding="utf-8") as f:
        json.dump(dev_scenarios, f, indent=2)

    eval_sha256 = compute_file_sha256(eval_file)
    dev_sha256 = compute_file_sha256(dev_file)

    # Compute action counts
    eval_actions = {}
    for s in eval_scenarios:
        act = s["expected_action"]
        eval_actions[act] = eval_actions.get(act, 0) + 1

    dev_actions = {}
    for s in dev_scenarios:
        act = s["expected_action"]
        dev_actions[act] = dev_actions.get(act, 0) + 1

    # Evidence counts
    ind_ev_count = sum(1 for s in eval_scenarios if s["has_independent_corroborating_evidence"])
    clean_count = sum(1 for s in eval_scenarios if not s["is_corrupted"])
    unsupported_count = len(eval_scenarios) - ind_ev_count - clean_count

    # Build per-scenario hash index
    scenario_hashes = {}
    for s in eval_scenarios:
        s_str = json.dumps(s, sort_keys=True)
        scenario_hashes[s["scenario_id"]] = {
            "category_id": s["category_id"],
            "expected_action": s["expected_action"],
            "has_independent_corroborating_evidence": s["has_independent_corroborating_evidence"],
            "sha256": compute_sha256(s_str),
        }

    manifest = {
        "manifest_version": "2.1.0",
        "created_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "CRYPTOGRAPHICALLY_FROZEN",
        "eval_scenarios_file": "eval_scenarios.json",
        "eval_scenarios_sha256": eval_sha256,
        "dev_scenarios_file": "dev_scenarios.json",
        "dev_scenarios_sha256": dev_sha256,
        "frozen_code_hashes": {
            "backend/ocr_service.py": FROZEN_OCR_SHA256
        },
        "summary_counts": {
            "total_eval_scenarios": len(eval_scenarios),
            "total_dev_scenarios": len(dev_scenarios),
            "eval_action_distribution": eval_actions,
            "dev_action_distribution": dev_actions,
            "cohort_distribution": {
                "corrupted_error_and_conflict": 85,
                "clean_control": 15
            },
            "evidence_availability_distribution": {
                "independent_evidence_present": ind_ev_count,
                "independent_evidence_absent": unsupported_count,
                "clean_controls": clean_count
            }
        },
        "scenario_index": scenario_hashes
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    manifest_sha256 = compute_file_sha256(manifest_file)

    print("\n================ DATASET FREEZE SUMMARY ================")
    print(f"Eval Scenarios File:   {eval_file}")
    print(f"Eval Scenarios SHA256: {eval_sha256}")
    print(f"Dev Scenarios File:    {dev_file}")
    print(f"Dev Scenarios SHA256:  {dev_sha256}")
    print(f"Manifest File:         {manifest_file}")
    print(f"Manifest SHA256:       {manifest_sha256}")
    print(f"Eval Actions:          {eval_actions}")
    print(f"Dev Actions:           {dev_actions}")
    print(f"Evidence Availability: Present={ind_ev_count}, Absent={unsupported_count}, Clean={clean_count}")
    print("========================================================\n")


if __name__ == "__main__":
    main()
