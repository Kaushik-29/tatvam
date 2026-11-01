"""
MedResolve — Rule-Based Clinical Conflict Detector
Deterministic, testable baseline conflict detector identifying observable data discrepancies
across patient evidence ledgers according to the MedResolve Conflict Taxonomy.

Guarantees:
1. Detects observable data discrepancies without declaring clinical causation.
2. Distinguishes extraction uncertainty (low OCR confidence) from medical falsity.
3. Preserves different observation dates without false contradiction flags.
4. Reports entered opinion disagreement without declaring which clinician is correct.
5. Emits structured ConflictReportItem objects with justified severity and required actions.
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evidence_ledger import (
    EvidenceItem,
    EvidenceLedger,
    EvidenceStatus,
    ExtractionMethod,
    SourceType,
)
from experiments.conflict_taxonomy import (
    ConflictReportItem,
    ConflictSeverity,
    ConflictType,
    RequiredAction,
)


class RuleBasedConflictDetector:
    def __init__(self, low_confidence_threshold: float = 0.70):
        self.low_confidence_threshold = low_confidence_threshold

    @staticmethod
    def _parse_iso_timestamp(ts: Optional[str]) -> Optional[datetime]:
        """Safely parses ISO 8601 timestamp strings."""
        if not ts:
            return None
        try:
            # Handle Z suffix
            clean_ts = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(clean_ts)
        except Exception:
            return None

    def detect_conflicts(self, ledger: EvidenceLedger) -> List[ConflictReportItem]:
        """
        Runs all deterministic conflict detection rules against the provided EvidenceLedger.
        Returns a list of structured ConflictReportItem detections.
        """
        detections: List[ConflictReportItem] = []

        # 1. Temporal Discrepancies
        detections.extend(self._check_temporal_discrepancies(ledger))

        # 2. Low Confidence Extractions
        detections.extend(self._check_low_confidence_extractions(ledger))

        # 3. Missing Information
        detections.extend(self._check_missing_information(ledger))

        # 4. Concept-level checks: Source Disagreements and Value/Unit Discrepancies
        detections.extend(self._check_concept_level_discrepancies(ledger))

        # 5. Entered Clinician Opinion Disagreements
        detections.extend(self._check_opinion_disagreements(ledger))

        return detections

    def _check_temporal_discrepancies(self, ledger: EvidenceLedger) -> List[ConflictReportItem]:
        """
        Detects impossible chronology: event timestamp occurring in the future relative to document ingestion.
        """
        reports = []
        for item in ledger.items:
            event_dt = self._parse_iso_timestamp(item.event_timestamp)
            recorded_dt = self._parse_iso_timestamp(item.recorded_timestamp)

            if event_dt and recorded_dt and event_dt > recorded_dt:
                reports.append(
                    ConflictReportItem(
                        conflict_type=ConflictType.TEMPORAL_DISCREPANCY,
                        affected_evidence_ids=[item.evidence_id],
                        affected_concepts=[item.concept],
                        reason=(
                            f"Observation event timestamp ({item.event_timestamp}) is chronologically "
                            f"in the future relative to document recorded timestamp ({item.recorded_timestamp})."
                        ),
                        supporting_sources=[item.source_type.value],
                        severity=ConflictSeverity.MEDIUM,
                        required_action=RequiredAction.USER_CONFIRMATION,
                    )
                )
        return reports

    def _check_low_confidence_extractions(self, ledger: EvidenceLedger) -> List[ConflictReportItem]:
        """
        Flags extractions with confidence scores below operational threshold.
        Carefully notes this indicates document extraction uncertainty, not clinical error.
        """
        reports = []
        for item in ledger.items:
            if item.extraction_confidence < self.low_confidence_threshold:
                reports.append(
                    ConflictReportItem(
                        conflict_type=ConflictType.LOW_CONFIDENCE_EXTRACTION,
                        affected_evidence_ids=[item.evidence_id],
                        affected_concepts=[item.concept],
                        reason=(
                            f"Extraction confidence ({item.extraction_confidence:.2f}) from {item.extraction_method.value} "
                            f"is below the reliability threshold ({self.low_confidence_threshold:.2f}). "
                            "Indicates document-processing uncertainty, not clinical error."
                        ),
                        supporting_sources=[item.source_type.value],
                        severity=ConflictSeverity.MEDIUM,
                        required_action=RequiredAction.USER_CONFIRMATION,
                    )
                )
        return reports

    def _check_missing_information(self, ledger: EvidenceLedger) -> List[ConflictReportItem]:
        """
        Detects missing essential units on numerical laboratory/vital measurements.
        """
        reports = []
        for item in ledger.items:
            # Check numerical values lacking a unit of measurement
            is_numerical = isinstance(item.normalized_value, (int, float)) and not isinstance(item.normalized_value, bool)
            if is_numerical and item.unit is None and item.concept.startswith("E_LAB"):
                reports.append(
                    ConflictReportItem(
                        conflict_type=ConflictType.MISSING_INFORMATION,
                        affected_evidence_ids=[item.evidence_id],
                        affected_concepts=[item.concept],
                        reason=(
                            f"Numerical laboratory measurement for '{item.concept_name_en or item.concept}' "
                            f"is missing its essential unit of measurement (unit=None)."
                        ),
                        supporting_sources=[item.source_type.value],
                        severity=ConflictSeverity.HIGH,
                        required_action=RequiredAction.QUALIFIED_CLINICAL_REVIEW,
                    )
                )
        return reports

    def _check_concept_level_discrepancies(self, ledger: EvidenceLedger) -> List[ConflictReportItem]:
        """
        Evaluates paired records on the same concept for:
        1. SOURCE_STATEMENT_DISAGREEMENT (patient says ABSENT vs. clinician note says PRESENT, or vice versa)
        2. VALUE_OR_UNIT_DISCREPANCY (conflicting numerical or categorical values for overlapping timeframes)
        """
        reports = []
        concept_groups: Dict[str, List[EvidenceItem]] = defaultdict(list)
        for item in ledger.items:
            concept_groups[item.concept].append(item)

        for concept, items in concept_groups.items():
            if len(items) < 2:
                continue

            # Compare pairs of items
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    item_a = items[i]
                    item_b = items[j]

                    # 1. Source Statement Disagreement
                    is_pt_a = item_a.source_type == SourceType.PATIENT_REPORTED
                    is_pt_b = item_b.source_type == SourceType.PATIENT_REPORTED
                    is_doc_a = item_a.source_type in [SourceType.EHR_EXTRACTED_NOTE, SourceType.LABORATORY_REPORT]
                    is_doc_b = item_b.source_type in [SourceType.EHR_EXTRACTED_NOTE, SourceType.LABORATORY_REPORT]

                    if (is_pt_a and is_doc_b) or (is_pt_b and is_doc_a):
                        pt_item = item_a if is_pt_a else item_b
                        doc_item = item_b if is_pt_a else item_a

                        # Check contradictory presence/absence status
                        if (
                            (pt_item.evidence_status == EvidenceStatus.ABSENT and doc_item.evidence_status == EvidenceStatus.PRESENT)
                            or (pt_item.evidence_status == EvidenceStatus.PRESENT and doc_item.evidence_status == EvidenceStatus.ABSENT)
                        ):
                            reports.append(
                                ConflictReportItem(
                                    conflict_type=ConflictType.SOURCE_STATEMENT_DISAGREEMENT,
                                    affected_evidence_ids=[pt_item.evidence_id, doc_item.evidence_id],
                                    affected_concepts=[concept],
                                    reason=(
                                        f"Source disagreement on '{concept}': Patient reported status is "
                                        f"{pt_item.evidence_status.value}, but clinical document documents status as "
                                        f"{doc_item.evidence_status.value}."
                                    ),
                                    supporting_sources=[pt_item.source_type.value, doc_item.source_type.value],
                                    severity=ConflictSeverity.HIGH,
                                    required_action=RequiredAction.USER_CONFIRMATION,
                                )
                            )

                    # 2. Value or Unit Discrepancy (same concept, overlapping timeframe, divergent numerical value)
                    is_num_a = isinstance(item_a.normalized_value, (int, float)) and not isinstance(item_a.normalized_value, bool)
                    is_num_b = isinstance(item_b.normalized_value, (int, float)) and not isinstance(item_b.normalized_value, bool)

                    if is_num_a and is_num_b:
                        # Check temporal overlap: within 24 hours of each other
                        dt_a = self._parse_iso_timestamp(item_a.event_timestamp or item_a.recorded_timestamp)
                        dt_b = self._parse_iso_timestamp(item_b.event_timestamp or item_b.recorded_timestamp)

                        if dt_a and dt_b and abs((dt_a - dt_b).total_seconds()) < 86400:
                            # If values diverge significantly (e.g. > 1.5 units for vitals like temp)
                            diff = abs(float(item_a.normalized_value) - float(item_b.normalized_value))
                            if diff > 1.5:
                                reports.append(
                                    ConflictReportItem(
                                        conflict_type=ConflictType.VALUE_OR_UNIT_DISCREPANCY,
                                        affected_evidence_ids=[item_a.evidence_id, item_b.evidence_id],
                                        affected_concepts=[concept],
                                        reason=(
                                            f"Conflicting values for '{concept}' during the same 24-hour observation window: "
                                            f"{item_a.normalized_value} {item_a.unit or ''} ({item_a.source_type.value}) vs. "
                                            f"{item_b.normalized_value} {item_b.unit or ''} ({item_b.source_type.value})."
                                        ),
                                        supporting_sources=[item_a.source_type.value, item_b.source_type.value],
                                        severity=ConflictSeverity.HIGH,
                                        required_action=RequiredAction.USER_CONFIRMATION,
                                    )
                                )

        return reports

    def _check_opinion_disagreements(self, ledger: EvidenceLedger) -> List[ConflictReportItem]:
        """
        Detects differing diagnostic impressions across multiple external clinician entries.
        Explicitly states the detector does NOT arbitrate which clinician is correct.
        """
        reports = []
        if len(ledger.opinions) >= 2:
            impressions = {op.diagnostic_impression for op in ledger.opinions}
            if len(impressions) > 1:
                reports.append(
                    ConflictReportItem(
                        conflict_type=ConflictType.ENTERED_OPINION_DISAGREEMENT,
                        affected_evidence_ids=[op.opinion_id for op in ledger.opinions],
                        affected_concepts=["CLINICAL_OPINION"],
                        reason=(
                            f"Divergent clinician opinions recorded: {', '.join(sorted(impressions))}. "
                            "Detector notes opinion disagreement for clinical review and does not assess or arbitrate clinical correctness."
                        ),
                        supporting_sources=[SourceType.ENTERED_CLINICIAN_OPINION.value],
                        severity=ConflictSeverity.MEDIUM,
                        required_action=RequiredAction.QUALIFIED_CLINICAL_REVIEW,
                    )
                )
        return reports
