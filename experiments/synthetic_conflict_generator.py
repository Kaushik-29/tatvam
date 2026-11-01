"""
MedResolve — Synthetic Conflict Benchmark Generator
Constructs a controlled, reproducible benchmark for evaluating clinical data conflict detection.
Guarantees:
1. Samples patient cases ONLY from unused rows in the official DDXPlus training split
   (strictly disjoint from the 50,000-case classifier training subset).
2. The official DDXPlus test split remains 100% untouched.
3. Every perturbation is labeled by its generation method and category.
4. Clean (unperturbed) cases are included to evaluate false-positive specificity.
5. All synthetic metadata, timestamps, and opinions are explicitly marked as simulated.
"""

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
import sys

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
from experiments.conflict_taxonomy import ConflictType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("MedResolve.ConflictGenerator")


class SyntheticConflictGenerator:
    def __init__(self, raw_dir: Path = Path("data/raw/ddxplus"), seed: int = 101):
        self.raw_dir = raw_dir
        self.seed = seed
        self.loader = DDXPlusLoader(raw_dir=raw_dir)
        self.random = random.Random(seed)
        self.np_random = np.random.RandomState(seed)

    def get_unused_training_indices(self, classifier_train_size: int = 50000, classifier_seed: int = 42) -> np.ndarray:
        """
        Determines the exact set of training row indices NOT used in Phase 2 classifier training.
        """
        train_path = self.loader.get_split_path("train")
        df_patho = pd.read_csv(train_path, usecols=["PATHOLOGY"])
        total_rows = len(df_patho)

        train_indices, unused_indices = train_test_split(
            np.arange(total_rows),
            train_size=classifier_train_size,
            random_state=classifier_seed,
            stratify=df_patho["PATHOLOGY"],
        )
        assert set(train_indices).isdisjoint(set(unused_indices)), "Classifier and unused indices must be strictly disjoint!"
        return unused_indices

    def convert_patient_to_clean_ledger(self, row: pd.Series, case_id: str) -> EvidenceLedger:
        """
        Transforms a raw DDXPlus row into a clean, unperturbed EvidenceLedger.
        """
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

        # 1. Patient Demographics as evidence items
        ledger.add_item(
            EvidenceItem(
                evidence_id=f"{case_id}_demo_age",
                patient_case_id=case_id,
                concept="DEMO_AGE",
                concept_name_en="Patient Age",
                normalized_value=int(row["AGE"]),
                original_value=str(row["AGE"]),
                unit="years",
                source_type=SourceType.PATIENT_REPORTED,
                recorded_timestamp=base_time,
                event_timestamp=event_time,
                extraction_method=ExtractionMethod.DIRECT_SELECTION,
                extraction_confidence=1.0,
                user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
                evidence_status=EvidenceStatus.PRESENT,
                is_simulated=True,
            )
        )

        # 2. Add symptoms from EVIDENCES
        ev_list = DDXPlusLoader.parse_list_column(row["EVIDENCES"])
        for idx, token in enumerate(ev_list):
            # Parse token (e.g. E_53 or E_54_@_V_180)
            if "_@_" in token:
                parts = token.split("_@_")
                concept = parts[0]
                norm_val = parts[1]
            else:
                concept = token
                norm_val = True

            ev_meta = self.loader.evidences.get(concept, {})
            name_en = ev_meta.get("question_en", concept)

            item = EvidenceItem(
                evidence_id=f"{case_id}_ev_{idx:03d}_{concept}",
                patient_case_id=case_id,
                concept=concept,
                concept_name_en=name_en,
                normalized_value=norm_val,
                original_value=str(norm_val),
                unit=None,
                source_type=SourceType.PATIENT_REPORTED,
                recorded_timestamp=base_time,
                event_timestamp=event_time,
                extraction_method=ExtractionMethod.DIRECT_SELECTION,
                extraction_confidence=1.0,
                user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
                evidence_status=EvidenceStatus.PRESENT,
                is_simulated=True,
            )
            ledger.add_item(item)

        # Add single non-conflicting clinician opinion based on ground-truth pathology
        ledger.add_opinion(
            ClinicianOpinionItem(
                opinion_id=f"{case_id}_op_001",
                patient_case_id=case_id,
                clinician_id="clinician_attending_01",
                clinician_specialty="General Practice",
                diagnostic_impression=row["PATHOLOGY"],
                confidence_assessment="PROBABLE",
                recorded_timestamp=base_time,
                is_simulated=True,
            )
        )

        return ledger

    def inject_perturbation(
        self, clean_ledger: EvidenceLedger, conflict_type: ConflictType
    ) -> Tuple[EvidenceLedger, Dict[str, Any]]:
        """
        Applies a controlled, reproducible perturbation corresponding to the specified ConflictType.
        Returns the perturbed ledger and ground-truth perturbation metadata.
        """
        # Deep copy ledger
        perturbed = EvidenceLedger.from_dict(clean_ledger.to_dict())
        case_id = perturbed.patient_case_id
        meta: Dict[str, Any] = {
            "case_id": case_id,
            "injected_conflict": conflict_type.value,
            "affected_evidence_ids": [],
            "affected_concepts": [],
            "description": "",
        }

        if conflict_type == ConflictType.VALUE_OR_UNIT_DISCREPANCY:
            # Inject a conflicting quantitative value on the same concept and time
            # Add conflicting vitals or categorical symptom measurement
            concept = "E_53"  # Fever or core temperature
            item_a = EvidenceItem(
                evidence_id=f"{case_id}_conflict_val_a",
                patient_case_id=case_id,
                concept=concept,
                concept_name_en="Body Temperature",
                normalized_value=98.6,
                original_value="98.6 F",
                unit="degF",
                source_type=SourceType.PATIENT_REPORTED,
                recorded_timestamp="2026-10-15T10:00:00Z",
                event_timestamp="2026-10-15T09:30:00Z",
                extraction_method=ExtractionMethod.MANUAL_ENTRY,
                extraction_confidence=1.0,
                user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
                evidence_status=EvidenceStatus.PRESENT,
                is_simulated=True,
            )
            item_b = EvidenceItem(
                evidence_id=f"{case_id}_conflict_val_b",
                patient_case_id=case_id,
                concept=concept,
                concept_name_en="Body Temperature",
                normalized_value=103.8,
                original_value="103.8 F",
                unit="degF",
                source_type=SourceType.LABORATORY_REPORT,
                recorded_timestamp="2026-10-15T10:05:00Z",
                event_timestamp="2026-10-15T09:30:00Z",
                extraction_method=ExtractionMethod.RULE_BASED_PARSER,
                extraction_confidence=0.98,
                user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
                evidence_status=EvidenceStatus.PRESENT,
                is_simulated=True,
            )
            perturbed.add_item(item_a)
            perturbed.add_item(item_b)
            meta["affected_evidence_ids"] = [item_a.evidence_id, item_b.evidence_id]
            meta["affected_concepts"] = [concept]
            meta["description"] = "Patient reports 98.6 F while concurrent triage lab reports 103.8 F"

        elif conflict_type == ConflictType.TEMPORAL_DISCREPANCY:
            # Inject an impossible future event timestamp (event_timestamp > recorded_timestamp)
            concept = "E_201"
            item = EvidenceItem(
                evidence_id=f"{case_id}_conflict_temp_01",
                patient_case_id=case_id,
                concept=concept,
                concept_name_en="Acute Symptom Onset",
                normalized_value=True,
                original_value="Symptom started",
                unit=None,
                source_type=SourceType.EHR_EXTRACTED_NOTE,
                recorded_timestamp="2026-10-15T10:00:00Z",
                event_timestamp="2026-10-25T14:00:00Z",  # 10 days in future!
                extraction_method=ExtractionMethod.RULE_BASED_PARSER,
                extraction_confidence=0.95,
                user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
                evidence_status=EvidenceStatus.PRESENT,
                is_simulated=True,
            )
            perturbed.add_item(item)
            meta["affected_evidence_ids"] = [item.evidence_id]
            meta["affected_concepts"] = [concept]
            meta["description"] = "Event timestamp (2026-10-25) is chronologically in the future relative to document ingestion (2026-10-15)"

        elif conflict_type == ConflictType.SOURCE_STATEMENT_DISAGREEMENT:
            # Direct contradiction: Patient denies symptom (ABSENT) while clinical note confirms PRESENT
            concept = "E_50"  # Dyspnea / Shortness of breath
            item_patient = EvidenceItem(
                evidence_id=f"{case_id}_conflict_src_pt",
                patient_case_id=case_id,
                concept=concept,
                concept_name_en="Shortness of Breath / Dyspnea",
                normalized_value=False,
                original_value="No shortness of breath",
                unit=None,
                source_type=SourceType.PATIENT_REPORTED,
                recorded_timestamp="2026-10-15T10:00:00Z",
                event_timestamp="2026-10-15T09:00:00Z",
                extraction_method=ExtractionMethod.DIRECT_SELECTION,
                extraction_confidence=1.0,
                user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
                evidence_status=EvidenceStatus.ABSENT,
                is_simulated=True,
            )
            item_ehr = EvidenceItem(
                evidence_id=f"{case_id}_conflict_src_ehr",
                patient_case_id=case_id,
                concept=concept,
                concept_name_en="Shortness of Breath / Dyspnea",
                normalized_value=True,
                original_value="Patient exhibits marked dyspnea at rest",
                unit=None,
                source_type=SourceType.EHR_EXTRACTED_NOTE,
                recorded_timestamp="2026-10-15T10:15:00Z",
                event_timestamp="2026-10-15T09:00:00Z",
                extraction_method=ExtractionMethod.RULE_BASED_PARSER,
                extraction_confidence=0.92,
                user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
                evidence_status=EvidenceStatus.PRESENT,
                is_simulated=True,
            )
            perturbed.add_item(item_patient)
            perturbed.add_item(item_ehr)
            meta["affected_evidence_ids"] = [item_patient.evidence_id, item_ehr.evidence_id]
            meta["affected_concepts"] = [concept]
            meta["description"] = "Patient explicitly denies dyspnea (ABSENT) but concurrent clinical note asserts dyspnea is PRESENT"

        elif conflict_type == ConflictType.LOW_CONFIDENCE_EXTRACTION:
            # Low extraction confidence score (< 0.70)
            concept = "E_LAB_01"
            item = EvidenceItem(
                evidence_id=f"{case_id}_conflict_ocr_low",
                patient_case_id=case_id,
                concept=concept,
                concept_name_en="Serum Hemoglobin",
                normalized_value=12.4,
                original_value="12.4 g/dL (smudged)",
                unit="g/dL",
                source_type=SourceType.LABORATORY_REPORT,
                recorded_timestamp="2026-10-15T10:00:00Z",
                event_timestamp="2026-10-15T08:30:00Z",
                extraction_method=ExtractionMethod.OCR_EXTRACTION,
                extraction_confidence=0.48,  # Below 0.70 threshold
                user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
                evidence_status=EvidenceStatus.PRESENT,
                is_simulated=True,
            )
            perturbed.add_item(item)
            meta["affected_evidence_ids"] = [item.evidence_id]
            meta["affected_concepts"] = [concept]
            meta["description"] = "OCR extraction confidence score (0.48) is below the reliable threshold (< 0.70)"

        elif conflict_type == ConflictType.MISSING_INFORMATION:
            # Quantitative measurement missing unit or essential timestamp
            concept = "E_LAB_02"
            item = EvidenceItem(
                evidence_id=f"{case_id}_conflict_miss_unit",
                patient_case_id=case_id,
                concept=concept,
                concept_name_en="Serum Potassium",
                normalized_value=5.9,
                original_value="5.9",
                unit=None,  # Missing critical unit!
                source_type=SourceType.LABORATORY_REPORT,
                recorded_timestamp="2026-10-15T10:00:00Z",
                event_timestamp="2026-10-15T08:30:00Z",
                extraction_method=ExtractionMethod.RULE_BASED_PARSER,
                extraction_confidence=0.95,
                user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
                evidence_status=EvidenceStatus.PRESENT,
                is_simulated=True,
            )
            perturbed.add_item(item)
            meta["affected_evidence_ids"] = [item.evidence_id]
            meta["affected_concepts"] = [concept]
            meta["description"] = "Quantitative electrolyte measurement (5.9) missing critical unit of measurement"

        elif conflict_type == ConflictType.ENTERED_OPINION_DISAGREEMENT:
            # Second conflicting clinician diagnostic opinion
            opinion_2 = ClinicianOpinionItem(
                opinion_id=f"{case_id}_op_002",
                patient_case_id=case_id,
                clinician_id="clinician_second_opinion_02",
                clinician_specialty="Pulmonology",
                diagnostic_impression="Alternative Acute Syndrome",  # Distinct divergent impression
                confidence_assessment="PROBABLE",
                recorded_timestamp="2026-10-15T11:00:00Z",
                is_simulated=True,
            )
            perturbed.add_opinion(opinion_2)
            meta["affected_evidence_ids"] = ["op_001", opinion_2.opinion_id]
            meta["affected_concepts"] = ["CLINICAL_OPINION"]
            meta["description"] = f"Clinician 1 ({perturbed.opinions[0].diagnostic_impression}) disagrees with Clinician 2 ({opinion_2.diagnostic_impression})"

        return perturbed, meta

    def generate_benchmark_cohort(
        self,
        num_cases: int = 500,
        cohort_name: str = "dev",
        unused_indices: Optional[np.ndarray] = None,
        df_full: Optional[pd.DataFrame] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Generates a balanced benchmark cohort consisting of clean and perturbed cases across all conflict categories.
        """
        if unused_indices is None:
            unused_indices = self.get_unused_training_indices()

        # Deterministically sample indices for this cohort
        sample_indices = self.random.sample(list(unused_indices), num_cases)

        if df_full is None:
            train_path = self.loader.get_split_path("train")
            df_full = pd.read_csv(train_path)

        cohort_rows = df_full.iloc[sample_indices].copy()

        conflict_types = list(ConflictType)
        # Allocate cases: ~16% clean, ~84% evenly distributed across 6 conflict categories
        categories_cycle = [None] * int(num_cases * 0.16)
        while len(categories_cycle) < num_cases:
            for ct in conflict_types:
                if len(categories_cycle) < num_cases:
                    categories_cycle.append(ct)

        self.random.shuffle(categories_cycle)

        ledgers: List[Dict[str, Any]] = []
        ground_truth: List[Dict[str, Any]] = []

        for idx, (_, row) in enumerate(cohort_rows.iterrows()):
            case_id = f"case_{cohort_name}_{idx:04d}_row{sample_indices[idx]}"
            clean_ledger = self.convert_patient_to_clean_ledger(row, case_id)
            target_conflict = categories_cycle[idx]

            if target_conflict is None:
                # Clean unperturbed case
                ledgers.append(clean_ledger.to_dict())
                ground_truth.append({
                    "case_id": case_id,
                    "has_conflict": False,
                    "conflict_types": [],
                    "perturbations": [],
                })
            else:
                perturbed_ledger, meta = self.inject_perturbation(clean_ledger, target_conflict)
                ledgers.append(perturbed_ledger.to_dict())
                ground_truth.append({
                    "case_id": case_id,
                    "has_conflict": True,
                    "conflict_types": [target_conflict.value],
                    "perturbations": [meta],
                })

        manifest = {
            "cohort_name": cohort_name,
            "total_cases": num_cases,
            "seed": self.seed,
            "source_indices": [int(x) for x in sample_indices],
            "conflict_type_counts": {
                ct.value: sum(1 for c in categories_cycle if c == ct) for ct in conflict_types
            },
            "clean_cases_count": sum(1 for c in categories_cycle if c is None),
        }

        return ledgers, ground_truth, manifest


def main():
    generator = SyntheticConflictGenerator(seed=101)
    unused_idx = generator.get_unused_training_indices()
    logger.info(f"Total available unused training cases: {len(unused_idx):,}")

    train_path = generator.loader.get_split_path("train")
    logger.info("Loading full training DataFrame for cohort row sampling...")
    df_full = pd.read_csv(train_path)

    output_dir = Path("results/conflicts")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Dev (tuning) cohort (500 cases)
    dev_pool = unused_idx[:50000]  # pool for dev
    dev_ledgers, dev_truth, dev_manifest = generator.generate_benchmark_cohort(
        num_cases=500, cohort_name="dev", unused_indices=dev_pool, df_full=df_full
    )
    with open(output_dir / "dev_conflict_ledgers.json", "w", encoding="utf-8") as f:
        json.dump(dev_ledgers, f, indent=2)
    with open(output_dir / "dev_conflict_ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(dev_truth, f, indent=2)

    # 2. Held-out Evaluation cohort (500 cases, completely distinct indices from dev)
    eval_pool = unused_idx[50000:100000]  # pool for eval
    eval_ledgers, eval_truth, eval_manifest = generator.generate_benchmark_cohort(
        num_cases=500, cohort_name="eval", unused_indices=eval_pool, df_full=df_full
    )
    with open(output_dir / "eval_conflict_ledgers.json", "w", encoding="utf-8") as f:
        json.dump(eval_ledgers, f, indent=2)
    with open(output_dir / "eval_conflict_ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(eval_truth, f, indent=2)

    # Master manifest
    manifest = {
        "dataset_origin": "DDXPlus release_train_patients.csv (unused rows)",
        "classifier_training_disjoint_guarantee": True,
        "classifier_training_cases_count": 50000,
        "dev_cohort": dev_manifest,
        "eval_cohort": eval_manifest,
    }
    with open(output_dir / "conflict_benchmark_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("[+] Generated 500 Dev and 500 Held-Out Eval conflict benchmark cases successfully!")
    logger.info(f"[+] Output directory: {output_dir}")


if __name__ == "__main__":
    main()
