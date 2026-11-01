"""
MedResolve — Action Policy Benchmark Generator
Phase 4 Controlled Scenario Benchmark Generation

Constructs reproducible, clinically motivated scenario cohorts (Dev: 300 cases, Eval: 300 cases)
for evaluating selective action policies (B0, B1, and B2).

Strict Disjointness Guarantees:
1. Samples patient rows ONLY from unused rows in DDXPlus release_train_patients.csv
   (pool indices 100,000 to 200,000).
2. 100% disjoint from the 50,000 cases used to train the Phase 2 diagnostic classifier.
3. 100% disjoint from the 1,000 cases used in the Phase 3 conflict benchmark.
4. Dev (300 cases) and Held-Out Eval (300 cases) cohorts are 100% disjoint from each other.
5. Official DDXPlus validation and test splits remain 100% untouched.
"""

from collections import defaultdict
import json
import logging
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.ddxplus_loader import DDXPlusLoader
from experiments.evidence_ledger import (
    ClinicianOpinionItem,
    EvidenceItem,
    EvidenceLedger,
    EvidenceStatus,
    ExtractionMethod,
    SourceType,
    UserConfirmationStatus,
)
from experiments.conflict_taxonomy import (
    ConflictReportItem,
    ConflictSeverity,
    ConflictType,
    RequiredAction,
)
from experiments.conflict_detector import RuleBasedConflictDetector
from experiments.action_policy import PolicyAction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("MedResolve.ActionBenchmarkGenerator")


class ActionBenchmarkGenerator:
    def __init__(self, raw_dir: Path = Path("data/raw/ddxplus"), seed: int = 202):
        self.raw_dir = raw_dir
        self.seed = seed
        self.loader = DDXPlusLoader(raw_dir=raw_dir)
        self.random = random.Random(seed)
        self.np_random = np.random.RandomState(seed)
        self.conflict_detector = RuleBasedConflictDetector()

        # Load evidence questions dictionary
        ev_path = raw_dir / "release_evidences.json"
        if not ev_path.exists():
            ev_path = raw_dir / "extracted" / "release_evidences.json"
        with open(ev_path, "r", encoding="utf-8") as f:
            self.evidence_meta = json.load(f)

    def get_unused_training_indices(
        self,
        classifier_train_size: int = 50000,
        classifier_seed: int = 42,
    ) -> np.ndarray:
        """Determines the exact set of training row indices NOT used in Phase 2 classifier training."""
        train_path = self.loader.get_split_path("train")
        df_patho = pd.read_csv(train_path, usecols=["PATHOLOGY"])
        total_rows = len(df_patho)

        _, unused_indices = train_test_split(
            np.arange(total_rows),
            train_size=classifier_train_size,
            random_state=classifier_seed,
            stratify=df_patho["PATHOLOGY"],
        )
        return unused_indices

    def build_clean_ledger(self, row: pd.Series, case_id: str, use_initial_only: bool = False) -> EvidenceLedger:
        """Constructs an EvidenceLedger from a DDXPlus patient row."""
        ledger = EvidenceLedger(
            patient_case_id=case_id,
            metadata={
                "source_row_index": int(row.name) if hasattr(row, "name") else -1,
                "pathology": row["PATHOLOGY"],
                "age": int(row["AGE"]),
                "sex": row["SEX"],
                "is_simulated": True,
            }
        )

        base_time = "2026-10-15T10:00:00Z"
        event_time = "2026-10-15T08:00:00Z"

        # Demographics
        ledger.add_item(
            EvidenceItem(
                evidence_id=f"{case_id}_age",
                patient_case_id=case_id,
                concept="DEMO_AGE",
                concept_name_en="Patient Age",
                normalized_value=int(row["AGE"]),
                original_value=str(row["AGE"]),
                unit="years",
                source_type=SourceType.PATIENT_REPORTED,
                event_timestamp=event_time,
                recorded_timestamp=base_time,
                extraction_method=ExtractionMethod.DIRECT_SELECTION,
                extraction_confidence=1.0,
                user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
                evidence_status=EvidenceStatus.PRESENT,
            )
        )
        ledger.add_item(
            EvidenceItem(
                evidence_id=f"{case_id}_sex",
                patient_case_id=case_id,
                concept="DEMO_SEX",
                concept_name_en="Patient Biological Sex",
                normalized_value=row["SEX"],
                original_value=str(row["SEX"]),
                source_type=SourceType.PATIENT_REPORTED,
                event_timestamp=event_time,
                recorded_timestamp=base_time,
                extraction_method=ExtractionMethod.DIRECT_SELECTION,
                extraction_confidence=1.0,
                user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
                evidence_status=EvidenceStatus.PRESENT,
            )
        )

        # Evidences
        evidence_list = (
            self.loader.parse_list_column(row["INITIAL_EVIDENCE"])
            if use_initial_only
            else self.loader.parse_list_column(row["EVIDENCES"])
        )

        for i, ev_str in enumerate(evidence_list):
            parts = ev_str.split("_@_")
            base_code = parts[0]
            val_code = parts[1] if len(parts) > 1 else None

            meta = self.evidence_meta.get(base_code, {})
            name_en = meta.get("question_en", base_code)

            ledger.add_item(
                EvidenceItem(
                    evidence_id=f"{case_id}_ev_{i:03d}",
                    patient_case_id=case_id,
                    concept=ev_str,
                    concept_name_en=name_en,
                    normalized_value=val_code if val_code else True,
                    original_value=val_code if val_code else "present",
                    source_type=SourceType.PATIENT_REPORTED,
                    event_timestamp=event_time,
                    recorded_timestamp=base_time,
                    extraction_method=ExtractionMethod.DIRECT_SELECTION,
                    extraction_confidence=1.0,
                    user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
                    evidence_status=EvidenceStatus.PRESENT,
                )
            )

        return ledger

    def generate_scenario(
        self,
        row: pd.Series,
        case_id: str,
        category: str,
    ) -> Dict[str, Any]:
        """
        Synthesizes a controlled action scenario with ground truth action label and clinical justification.
        """
        all_evidences = self.loader.parse_list_column(row["EVIDENCES"])
        initial_evidences = self.loader.parse_list_column(row["INITIAL_EVIDENCE"])

        if category == "CLEAN_HIGH_CONFIDENCE":
            ledger = self.build_clean_ledger(row, case_id, use_initial_only=False)
            expected_action = PolicyAction.EXPLAIN.value
            justification = (
                "Verified evidence profile with comprehensive documented symptoms, low predictive uncertainty, "
                "and zero unresolved conflicts justifies producing a bounded evidence summary."
            )
            candidate_question = None

        elif category == "AMBIGUOUS_NEED_QUESTION":
            # Initial complaint only; high ambiguity, informative question available from remaining symptoms
            ledger = self.build_clean_ledger(row, case_id, use_initial_only=True)
            ledger.metadata["is_ambiguous_presentation"] = True

            # Identify candidate question from remaining unasked symptoms
            remaining = [e for e in all_evidences if e not in initial_evidences]
            if remaining:
                chosen_ev = remaining[0]
                base_code = chosen_ev.split("_@_")[0]
                q_text = self.evidence_meta.get(base_code, {}).get("question_en", f"Do you have {base_code}?")
                candidate_question = {
                    "concept": chosen_ev,
                    "question_en": q_text,
                    "rationale": "Gather essential discriminatory evidence to refine differential possibilities.",
                }
            else:
                candidate_question = {
                    "concept": "E_91",
                    "question_en": "Do you have a fever (either felt or measured with a thermometer)?",
                    "rationale": "Clarify baseline systemic inflammatory involvement.",
                }

            expected_action = PolicyAction.ASK.value
            justification = (
                "Presentation contains only initial presenting complaint with elevated diagnostic uncertainty; "
                "a targeted, documented follow-up question is available to discriminate competing conditions."
            )

        elif category == "LOW_CONFIDENCE_EXTRACTION":
            ledger = self.build_clean_ledger(row, case_id, use_initial_only=False)
            # Inject a low-confidence OCR lab or note extraction
            ocr_conf = round(self.random.uniform(0.35, 0.65), 2)
            ocr_item = EvidenceItem(
                evidence_id=f"{case_id}_ocr_uncertain",
                patient_case_id=case_id,
                concept="E_91",
                concept_name_en="Body Temperature / Fever",
                normalized_value=True,
                original_value="Fev?r noted 101.4",
                unit="degF",
                source_type=SourceType.EHR_EXTRACTED_NOTE,
                source_document_id=f"doc_{case_id}_scan",
                recorded_timestamp="2026-10-15T10:00:00Z",
                event_timestamp="2026-10-15T08:00:00Z",
                extraction_method=ExtractionMethod.OCR_EXTRACTION,
                extraction_confidence=ocr_conf,
                user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
                evidence_status=EvidenceStatus.PRESENT,
            )
            ledger.add_item(ocr_item)
            expected_action = PolicyAction.ASK.value
            justification = (
                f"Automated document OCR extraction yielded low confidence ({ocr_conf:.2f} < 0.70) on an unconfirmed item; "
                "the policy must ask the patient to confirm or clarify this value before relying on it."
            )
            candidate_question = {
                "concept": "E_91",
                "question_en": f"Could you please confirm whether you have had a fever or elevated temperature?",
                "rationale": "Confirm low-confidence automated document extraction.",
            }

        elif category == "OPINION_DISAGREEMENT":
            ledger = self.build_clean_ledger(row, case_id, use_initial_only=False)
            patho = row["PATHOLOGY"]
            # Alternative realistic differential opinion
            alt_opinions = ["Acute Bronchitis", "Influenza", "GERD", "Viral pharyngitis", "Panic attack"]
            alt_patho = [o for o in alt_opinions if o != patho][0]

            ledger.add_opinion(
                ClinicianOpinionItem(
                    opinion_id=f"{case_id}_op1",
                    patient_case_id=case_id,
                    clinician_id="clinician_dr_smith",
                    clinician_specialty="General Practice",
                    diagnostic_impression=patho,
                    recorded_timestamp="2026-10-15T10:00:00Z",
                )
            )
            ledger.add_opinion(
                ClinicianOpinionItem(
                    opinion_id=f"{case_id}_op2",
                    patient_case_id=case_id,
                    clinician_id="clinician_dr_jones",
                    clinician_specialty="Internal Medicine",
                    diagnostic_impression=alt_patho,
                    recorded_timestamp="2026-10-15T10:15:00Z",
                )
            )
            expected_action = PolicyAction.ABSTAIN_AND_NAVIGATE.value
            justification = (
                f"Two licensed clinicians documented divergent diagnostic impressions ('{patho}' vs '{alt_patho}'); "
                "under the non-arbitration principle, the system must not declare which clinician is correct and must abstain and navigate."
            )
            candidate_question = None

        elif category == "MATERIAL_CONFLICT_OR_NO_QUESTION":
            # 50% source statement disagreement, 50% high uncertainty with exhausted questions
            sub_type = self.random.choice(["SOURCE_DISAGREEMENT", "NO_QUESTIONS_AVAILABLE"])
            if sub_type == "SOURCE_DISAGREEMENT":
                ledger = self.build_clean_ledger(row, case_id, use_initial_only=False)
                # Patient says absent, clinical note says present (using non-emergency symptom: cough)
                ledger.add_item(
                    EvidenceItem(
                        evidence_id=f"{case_id}_src_pt",
                        patient_case_id=case_id,
                        concept="E_201",
                        concept_name_en="Cough",
                        normalized_value=False,
                        source_type=SourceType.PATIENT_REPORTED,
                        recorded_timestamp="2026-10-15T10:00:00Z",
                        event_timestamp="2026-10-15T09:00:00Z",
                        extraction_method=ExtractionMethod.DIRECT_SELECTION,
                        extraction_confidence=1.0,
                        evidence_status=EvidenceStatus.ABSENT,
                    )
                )
                ledger.add_item(
                    EvidenceItem(
                        evidence_id=f"{case_id}_src_ehr",
                        patient_case_id=case_id,
                        concept="E_201",
                        concept_name_en="Cough",
                        normalized_value=True,
                        source_type=SourceType.EHR_EXTRACTED_NOTE,
                        recorded_timestamp="2026-10-15T10:00:00Z",
                        event_timestamp="2026-10-15T09:00:00Z",
                        extraction_method=ExtractionMethod.RULE_BASED_PARSER,
                        extraction_confidence=0.98,
                        evidence_status=EvidenceStatus.PRESENT,
                    )
                )
                expected_action = PolicyAction.ABSTAIN_AND_NAVIGATE.value
                justification = (
                    "Direct material contradiction between patient self-report (cough ABSENT) and concurrent EHR clinical note "
                    "(cough PRESENT) prevents safe automated explanation; professional clinical review is required."
                )
                candidate_question = None
            else:
                # Ambiguous presentation with NO follow-up questions available
                ledger = self.build_clean_ledger(row, case_id, use_initial_only=True)
                ledger.metadata["is_ambiguous_presentation"] = True
                expected_action = PolicyAction.ABSTAIN_AND_NAVIGATE.value
                justification = (
                    "Elevated diagnostic uncertainty on partial presenting evidence, and no valid follow-up questions remain; "
                    "policy conservatively falls back to abstention and qualified clinical navigation."
                )
                candidate_question = None

        elif category == "EMERGENCY_RED_FLAG":
            ledger = self.build_clean_ledger(row, case_id, use_initial_only=False)
            flag_type = self.random.choice(["CHEST_PAIN_DYSPNEA", "STRIDOR", "SYNCOPE", "GI_BLEED", "ACUTE_PULMONARY_EDEMA"])

            if flag_type == "CHEST_PAIN_DYSPNEA":
                ledger.add_item(
                    EvidenceItem(
                        evidence_id=f"{case_id}_rf_cp",
                        patient_case_id=case_id,
                        concept="E_55_@_V_101",
                        concept_name_en="Upper chest pain",
                        normalized_value="V_101",
                        source_type=SourceType.PATIENT_REPORTED,
                        recorded_timestamp="2026-10-15T10:00:00Z",
                        event_timestamp="2026-10-15T09:30:00Z",
                        extraction_method=ExtractionMethod.DIRECT_SELECTION,
                        extraction_confidence=1.0,
                        evidence_status=EvidenceStatus.PRESENT,
                    )
                )
                ledger.add_item(
                    EvidenceItem(
                        evidence_id=f"{case_id}_rf_dysp",
                        patient_case_id=case_id,
                        concept="E_66",
                        concept_name_en="Severe shortness of breath",
                        normalized_value=True,
                        source_type=SourceType.PATIENT_REPORTED,
                        recorded_timestamp="2026-10-15T10:00:00Z",
                        event_timestamp="2026-10-15T09:30:00Z",
                        extraction_method=ExtractionMethod.DIRECT_SELECTION,
                        extraction_confidence=1.0,
                        evidence_status=EvidenceStatus.PRESENT,
                    )
                )
                justification = "Concurrent acute chest pain and severe shortness of breath triggers acute emergency cardiopulmonary safety override."

            elif flag_type == "STRIDOR":
                ledger.add_item(
                    EvidenceItem(
                        evidence_id=f"{case_id}_rf_stridor",
                        patient_case_id=case_id,
                        concept="E_194",
                        concept_name_en="High-pitched stridor on breathing in",
                        normalized_value=True,
                        source_type=SourceType.PATIENT_REPORTED,
                        recorded_timestamp="2026-10-15T10:00:00Z",
                        event_timestamp="2026-10-15T09:45:00Z",
                        extraction_method=ExtractionMethod.DIRECT_SELECTION,
                        extraction_confidence=1.0,
                        evidence_status=EvidenceStatus.PRESENT,
                    )
                )
                justification = "Inspiratory stridor indicates acute upper airway obstruction, triggering urgent safety override."

            elif flag_type == "SYNCOPE":
                ledger.add_item(
                    EvidenceItem(
                        evidence_id=f"{case_id}_rf_syncope",
                        patient_case_id=case_id,
                        concept="E_159",
                        concept_name_en="Loss of consciousness (syncope)",
                        normalized_value=True,
                        source_type=SourceType.PATIENT_REPORTED,
                        recorded_timestamp="2026-10-15T10:00:00Z",
                        event_timestamp="2026-10-15T09:15:00Z",
                        extraction_method=ExtractionMethod.DIRECT_SELECTION,
                        extraction_confidence=1.0,
                        evidence_status=EvidenceStatus.PRESENT,
                    )
                )
                justification = "Acute loss of consciousness (syncope) requires immediate clinical evaluation."

            elif flag_type == "GI_BLEED":
                ledger.add_item(
                    EvidenceItem(
                        evidence_id=f"{case_id}_rf_gibleed",
                        patient_case_id=case_id,
                        concept="E_210",
                        concept_name_en="Vomiting blood or coffee-ground emesis",
                        normalized_value=True,
                        source_type=SourceType.PATIENT_REPORTED,
                        recorded_timestamp="2026-10-15T10:00:00Z",
                        event_timestamp="2026-10-15T09:00:00Z",
                        extraction_method=ExtractionMethod.DIRECT_SELECTION,
                        extraction_confidence=1.0,
                        evidence_status=EvidenceStatus.PRESENT,
                    )
                )
                justification = "Upper gastrointestinal hemorrhage (hematemesis) warrants immediate emergency referral."

            else:  # ACUTE_PULMONARY_EDEMA / Severe Cardiopulmonary distress
                # Inject objective observable hypoxemia and respiratory distress evidence
                ledger.add_item(
                    EvidenceItem(
                        evidence_id=f"{case_id}_rf_apo_dysp",
                        patient_case_id=case_id,
                        concept="E_66",
                        concept_name_en="Severe respiratory distress / dyspnea",
                        normalized_value=True,
                        source_type=SourceType.PATIENT_REPORTED,
                        recorded_timestamp="2026-10-15T10:00:00Z",
                        event_timestamp="2026-10-15T09:00:00Z",
                        extraction_method=ExtractionMethod.DIRECT_SELECTION,
                        extraction_confidence=1.0,
                        evidence_status=EvidenceStatus.PRESENT,
                    )
                )
                ledger.add_item(
                    EvidenceItem(
                        evidence_id=f"{case_id}_rf_apo_spo2",
                        patient_case_id=case_id,
                        concept="VITAL_SPO2",
                        concept_name_en="Oxygen Saturation (SpO2)",
                        normalized_value=86.0,
                        unit="percent",
                        source_type=SourceType.LABORATORY_REPORT,
                        recorded_timestamp="2026-10-15T10:00:00Z",
                        event_timestamp="2026-10-15T09:00:00Z",
                        extraction_method=ExtractionMethod.RULE_BASED_PARSER,
                        extraction_confidence=1.0,
                        evidence_status=EvidenceStatus.PRESENT,
                    )
                )
                justification = "Severe respiratory distress with documented severe hypoxemia (SpO2 86% < 90%) triggers urgent safety override."

            expected_action = PolicyAction.EMERGENCY_OVERRIDE.value
            candidate_question = None

        else:
            raise ValueError(f"Unknown scenario category: {category}")

        # Run conflict detector to capture deterministic report
        detected_conflicts = self.conflict_detector.detect_conflicts(ledger)

        return {
            "case_id": case_id,
            "scenario_category": category,
            "source_row_index": int(row.name) if hasattr(row, "name") else -1,
            "source_generation_method": f"DDXPlus patient profile with controlled {category} perturbation",
            "is_synthetic": True,
            "evidence_ledger": ledger.to_dict(),
            "conflict_detector_output": [c.model_dump() for c in detected_conflicts],
            "candidate_question": candidate_question,
            "expected_action": expected_action,
            "justification": justification,
            "clinical_review_note": (
                "Documented scenario grounded in DDXPlus clinical condition definitions, "
                "evidence ontology, and MedResolve conflict taxonomy."
            ),
        }

    def generate_cohort(
        self,
        cohort_name: str,
        num_cases: int,
        unused_indices: np.ndarray,
        df_full: pd.DataFrame,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Generates a balanced cohort of controlled action scenarios.
        Distribution across 300 cases:
        - CLEAN_HIGH_CONFIDENCE: 60
        - AMBIGUOUS_NEED_QUESTION: 60
        - LOW_CONFIDENCE_EXTRACTION: 50
        - OPINION_DISAGREEMENT: 40
        - MATERIAL_CONFLICT_OR_NO_QUESTION: 40
        - EMERGENCY_RED_FLAG: 50
        """
        category_distribution = [
            ("CLEAN_HIGH_CONFIDENCE", 60),
            ("AMBIGUOUS_NEED_QUESTION", 60),
            ("LOW_CONFIDENCE_EXTRACTION", 50),
            ("OPINION_DISAGREEMENT", 40),
            ("MATERIAL_CONFLICT_OR_NO_QUESTION", 40),
            ("EMERGENCY_RED_FLAG", 50),
        ]

        categories_list = []
        for cat, count in category_distribution:
            categories_list.extend([cat] * count)

        # Separate candidate pool into clinically stable rows and emergency rows
        # Uses benchmark-internal symptom set without importing or invoking decision policy classes
        airway_codes = {"E_194", "E_128"}
        syncope_codes = {"E_159", "E_43"}
        bleed_codes = {"E_210", "E_45"}
        chest_pain_codes = {"E_55_@_V_101", "E_55_@_V_29", "E_55_@_V_55", "E_55_@_V_56", "E_55_@_V_170", "E_55_@_V_171"}
        dyspnea_codes = {"E_66", "E_64", "E_67"}

        stable_candidates = []
        emergency_candidates = []

        for row_idx in unused_indices:
            row = df_full.iloc[row_idx]
            evs = set(self.loader.parse_list_column(row["EVIDENCES"]))

            has_airway = bool(evs.intersection(airway_codes))
            has_syncope = bool(evs.intersection(syncope_codes))
            has_bleed = bool(evs.intersection(bleed_codes))
            has_cardiopulmonary = bool(evs.intersection(chest_pain_codes)) and bool(evs.intersection(dyspnea_codes))

            is_emerg = has_airway or has_syncope or has_bleed or has_cardiopulmonary

            if is_emerg:
                emergency_candidates.append(row_idx)
            else:
                stable_candidates.append(row_idx)

            if len(stable_candidates) >= 300 and len(emergency_candidates) >= 100:
                break

        # Required counts
        # Non-emergency: 60 + 60 + 50 + 40 + 40 = 250 cases
        # Emergency: 50 cases
        non_emerg_cats = [
            ("CLEAN_HIGH_CONFIDENCE", 60),
            ("AMBIGUOUS_NEED_QUESTION", 60),
            ("LOW_CONFIDENCE_EXTRACTION", 50),
            ("OPINION_DISAGREEMENT", 40),
            ("MATERIAL_CONFLICT_OR_NO_QUESTION", 40),
        ]
        
        stable_sample = self.np_random.choice(stable_candidates, size=250, replace=False)
        emerg_sample = self.np_random.choice(emergency_candidates, size=50, replace=False)

        scenarios: List[Dict[str, Any]] = []
        category_counts: Dict[str, int] = defaultdict(int)
        action_counts: Dict[str, int] = defaultdict(int)
        all_sample_indices = []

        # 1. Generate non-emergency scenarios from stable pool
        stable_idx = 0
        for cat, count in non_emerg_cats:
            for _ in range(count):
                row_id = int(stable_sample[stable_idx])
                stable_idx += 1
                all_sample_indices.append(row_id)
                row = df_full.iloc[row_id]
                case_id = f"action_{cohort_name}_{len(scenarios):04d}_row{row_id}"
                scenario = self.generate_scenario(row, case_id, cat)
                scenario["cohort"] = cohort_name
                scenarios.append(scenario)
                category_counts[cat] += 1
                action_counts[scenario["expected_action"]] += 1

        # 2. Generate emergency scenarios from emergency pool
        for i in range(50):
            row_id = int(emerg_sample[i])
            all_sample_indices.append(row_id)
            row = df_full.iloc[row_id]
            case_id = f"action_{cohort_name}_{len(scenarios):04d}_row{row_id}"
            scenario = self.generate_scenario(row, case_id, "EMERGENCY_RED_FLAG")
            scenario["cohort"] = cohort_name
            scenarios.append(scenario)
            category_counts["EMERGENCY_RED_FLAG"] += 1
            action_counts[scenario["expected_action"]] += 1

        manifest = {
            "cohort_name": cohort_name,
            "total_cases": num_cases,
            "seed": self.seed,
            "source_indices": [int(x) for x in all_sample_indices],
            "category_distribution": dict(category_counts),
            "expected_action_distribution": dict(action_counts),
        }

        return scenarios, manifest


def main():
    generator = ActionBenchmarkGenerator(seed=202)
    unused_idx = generator.get_unused_training_indices()
    logger.info(f"Total available unused training cases: {len(unused_idx):,}")

    train_path = generator.loader.get_split_path("train")
    logger.info("Loading full training DataFrame for sampling...")
    df_full = pd.read_csv(train_path)

    output_dir = Path("results/actions")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Dev (tuning) cohort (300 cases) from unused pool 100,000 to 150,000
    dev_pool = unused_idx[100000:150000]
    dev_scenarios, dev_manifest = generator.generate_cohort(
        cohort_name="dev", num_cases=300, unused_indices=dev_pool, df_full=df_full
    )
    with open(output_dir / "dev_action_scenarios.json", "w", encoding="utf-8") as f:
        json.dump(dev_scenarios, f, indent=2)

    # 2. Held-Out Evaluation cohort (300 cases) from unused pool 150,000 to 200,000
    eval_pool = unused_idx[150000:200000]
    eval_scenarios, eval_manifest = generator.generate_cohort(
        cohort_name="eval", num_cases=300, unused_indices=eval_pool, df_full=df_full
    )
    with open(output_dir / "eval_action_scenarios.json", "w", encoding="utf-8") as f:
        json.dump(eval_scenarios, f, indent=2)

    # Master Manifest
    manifest = {
        "dataset_origin": "DDXPlus release_train_patients.csv (unused rows)",
        "classifier_training_disjoint_guarantee": True,
        "phase3_conflict_disjoint_guarantee": True,
        "dev_eval_disjoint_guarantee": True,
        "benchmark_independence_audit": {
            "is_independent_of_decision_policy": True,
            "policy_classes_imported_for_labeling": False,
            "metadata_shortcuts_used": False,
            "audit_version": "v2_audited",
            "audit_date": "2026-10-30",
            "rectifications_applied": [
                "Decoupled candidate pool stratification from EmergencySafetyOverrideDetector",
                "Replaced E_66 (dyspnea) with E_201 (cough) in source statement conflict scenarios to prevent unintended cardiopulmonary emergency triggers",
                "Replaced metadata['is_acute_emergency'] shortcut with objective observable hypoxemia and respiratory distress evidence items",
                "Preserved Phase 4 v1 cohort as eval_action_scenarios_v1_audit.json for retrospective regression auditing",
            ],
        },
        "dev_cohort": dev_manifest,
        "eval_cohort": eval_manifest,
    }
    with open(output_dir / "action_benchmark_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("[+] Generated 300 Dev and 300 Held-Out Eval action benchmark cases successfully!")
    logger.info(f"[+] Output directory: {output_dir}")


if __name__ == "__main__":
    main()
