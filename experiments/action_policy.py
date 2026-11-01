"""
MedResolve — Uncertainty-Aware Selective Action Policy
Phase 4 Action Policy Module

Implements selective action selection across three ordinary action pathways:
1. ASK: request a targeted missing piece of information or confirm an uncertain extraction.
2. EXPLAIN: produce a bounded, evidence-grounded summary when evidence is adequate and verified.
3. ABSTAIN_AND_NAVIGATE: decline unsupported arbitration/comparison, summarize unresolved
   evidence, and advise qualified professional clinical assessment.

A separate urgent-warning override (EMERGENCY_OVERRIDE) takes strict precedence over ordinary
action selection to flag potential acute emergencies.

Key Design Guarantees:
- The policy does NOT declare a diagnosis merely because a classifier assigned a top score.
- The policy explicitly represents predictive uncertainty (entropy, top-1 margin), extraction
  uncertainty (OCR/parser confidence), and conflict taxonomy reports.
- Signals are kept distinct; raw classifier entropy, OCR confidence, and conflict count are
  never conflated as interchangeable probabilities.
- Non-Arbitration Principle: Conflicting clinician opinions trigger abstention and navigation
  without declaring either clinician correct.
- Non-Fabrication Principle: Abstention and explanation responses never invent diagnoses,
  providers, or clinical certainty.
- ASK is chosen only when a documented, useful question is available; if no question exists,
  the policy conservatively falls back to ABSTAIN_AND_NAVIGATE.
"""

from collections import defaultdict
from enum import Enum
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


class PolicyAction(str, Enum):
    """Action pathway selected by the policy."""
    ASK = "ASK"
    EXPLAIN = "EXPLAIN"
    ABSTAIN_AND_NAVIGATE = "ABSTAIN_AND_NAVIGATE"
    EMERGENCY_OVERRIDE = "EMERGENCY_OVERRIDE"


class PolicyDecision(BaseModel):
    """
    Structured outcome emitted by an action policy.
    Contains the chosen action, safety override status, objective rationale,
    uncertainty signals, and action-specific payloads.
    """
    selected_action: PolicyAction
    is_emergency_override: bool = False
    reason: str = Field(description="Primary decision rule triggered")
    detailed_rationale: str = Field(description="Comprehensive explanation of decision signals")
    uncertainty_signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Explicit uncertainty signals (entropy, margin, extraction confidence, conflicts)"
    )
    detected_conflicts_count: int = 0
    target_concept_to_ask: Optional[str] = None
    candidate_question_en: Optional[str] = None
    question_rationale: Optional[str] = None
    explanation_summary: Optional[Dict[str, Any]] = None
    abstention_summary: Optional[Dict[str, Any]] = None
    emergency_details: Optional[Dict[str, Any]] = None
    disclaimer: str = Field(
        default=(
            "MedResolve is an academic research prototype for evidence-grounded health assessment. "
            "It does not provide medical diagnoses, triage certifications, or treatment orders. "
            "All findings and summaries must be reviewed by a licensed medical professional."
        ),
        description="Standard medical safety disclaimer"
    )


def compute_predictive_uncertainty(
    probabilities: np.ndarray,
    num_classes: int = 49,
) -> Dict[str, float]:
    """
    Calculates explicit diagnostic prediction uncertainty metrics from a probability distribution.
    
    Metrics:
    - shannon_entropy: H(p) = -sum(p_i * log2(p_i))
    - normalized_entropy: H(p) / log2(C), bounded in [0.0, 1.0]
    - top1_probability: max(p)
    - top2_probability: second highest probability
    - prediction_margin: p_{(1)} - p_{(2)} (confidence gap)
    """
    probs = np.asarray(probabilities, dtype=np.float64).flatten()
    if len(probs) != num_classes:
        # Pad or truncate if needed
        if len(probs) < num_classes:
            padded = np.zeros(num_classes, dtype=np.float64)
            padded[:len(probs)] = probs
            probs = padded
        else:
            probs = probs[:num_classes]

    # Normalize to ensure valid probability simplex
    total = np.sum(probs)
    if total > 0:
        probs = probs / total
    else:
        probs = np.ones(num_classes, dtype=np.float64) / num_classes

    # Shannon Entropy with numerical stability
    eps = 1e-12
    safe_probs = np.clip(probs, eps, 1.0)
    shannon_entropy = float(-np.sum(safe_probs * np.log2(safe_probs)))
    max_entropy = math.log2(num_classes)
    normalized_entropy = float(shannon_entropy / max_entropy) if max_entropy > 0 else 0.0

    sorted_probs = np.sort(probs)[::-1]
    top1 = float(sorted_probs[0])
    top2 = float(sorted_probs[1]) if len(sorted_probs) > 1 else 0.0
    margin = float(top1 - top2)

    return {
        "shannon_entropy": round(shannon_entropy, 4),
        "normalized_entropy": round(normalized_entropy, 4),
        "top1_probability": round(top1, 4),
        "top2_probability": round(top2, 4),
        "prediction_margin": round(margin, 4),
    }


class EmergencySafetyOverrideDetector:
    """
    Deterministic clinical red-flag detector implementing the urgent-warning override.
    
    Grounds safety checks strictly in reviewed, documented criteria:
    1. Critical DDXPlus acute evidence codes:
       - E_194: Stridor (acute upper airway obstruction)
       - E_128: Suffocating / inability to breathe or speak (acute laryngospasm)
       - E_159 / E_43: Syncope / acute loss of consciousness
       - E_210: Massive hematemesis (vomiting blood / coffee grounds)
       - Acute severe chest pain + severe dyspnea (E_66 + E_55 thoracic pain)
       - Anaphylaxis constellation: diffuse swelling (E_151/E_152) + respiratory distress (E_194/E_66)
    2. Documented severe vital abnormalities:
       - Core body temperature >= 104.0 degF (40.0 degC)
       - Oxygen saturation (SpO2) < 90%
    3. Severe DDXPlus conditions (severity=1):
       - If presenting symptoms strongly match severity=1 condition (NSTEMI, Pulmonary Edema, Anaphylaxis)
    """

    # Clinical Provenance for Observable Evidence Red Flags:
    # 1. Airway obstruction (Stridor / Suffocation): Manchester Triage System (Airway Red), ESI Level 1
    # 2. Acute Syncope (Loss of Consciousness): ESC Guidelines on Syncope, ESI Level 2
    # 3. Cardiopulmonary Syndrome (Chest Pain + Dyspnea): AHA/ACC Chest Pain Guidelines, ESI Level 2
    # 4. Severe Hemorrhage (Hematemesis / Hemoptysis): BTS Hemoptysis Guidelines, ESI Level 2
    # 5. Anaphylaxis Constellation (Swelling + Respiratory Distress): World Allergy Organization (WAO)
    # 6. Physiological Extremes (Hyperpyrexia >=104F, Hypoxemia SpO2 <90%): WHO ETAT Protocol, ESI Level 1/2

    CHEST_PAIN_TOKENS = {
        "E_55_@_V_101", "E_55_@_V_29", "E_55_@_V_55",
        "E_55_@_V_56", "E_55_@_V_170", "E_55_@_V_171",
    }
    DYSPNEA_TOKENS = {"E_66", "E_64", "E_67"}
    STRIDOR_TOKENS = {"E_194", "E_128"}
    SYNCOPE_TOKENS = {"E_159", "E_43"}
    GI_BLEED_TOKENS = {"E_210", "E_45"}
    SWELLING_TOKENS = {"E_151", "E_152"}

    def check_emergency(
        self,
        ledger: EvidenceLedger,
    ) -> Tuple[bool, List[str]]:
        """
        Evaluates the ledger for clinical urgent-warning conditions strictly using
        observed evidence and defined physiological vitals legitimately available to the application.
        
        Zero Leakage Guarantee:
        - Never accesses hidden ground truth (PATHOLOGY, DIFFERENTIAL_DIAGNOSIS).
        - Never accesses synthetic benchmark metadata (e.g. is_acute_emergency).
        - Never conflates disease classification probability with triage safety overrides.
        
        Returns:
            Tuple[bool, List[str]]: (is_emergency, list_of_triggered_red_flags)
        """
        red_flags: List[str] = []

        # Collect present concepts strictly from observable ledger items
        present_concepts = set()
        for item in ledger.items:
            if item.evidence_status == EvidenceStatus.PRESENT:
                present_concepts.add(item.concept)

        # 1. Critical Airway & Breathing Red Flags (Manchester Triage System / ESI 1)
        if present_concepts.intersection(self.STRIDOR_TOKENS):
            red_flags.append(
                "Critical acute upper airway compromise: patient presents with inspiratory stridor or acute suffocation sensation."
            )

        # 2. Syncope / Acute Loss of Consciousness (ESC Guidelines on Syncope / ESI 2)
        if present_concepts.intersection(self.SYNCOPE_TOKENS):
            red_flags.append(
                "Critical neurological / cardiovascular sign: documented acute loss of consciousness (syncope)."
            )

        # 3. Severe Acute Chest Pain with Dyspnea (AHA/ACC Chest Pain Guidelines / ESI 2)
        has_chest_pain = bool(present_concepts.intersection(self.CHEST_PAIN_TOKENS))
        has_dyspnea = bool(present_concepts.intersection(self.DYSPNEA_TOKENS))
        if has_chest_pain and has_dyspnea:
            red_flags.append(
                "Potential acute cardiopulmonary syndrome: concurrent acute thoracic chest pain and severe dyspnea."
            )

        # 4. Severe Hemorrhage (BTS Hemoptysis Guidelines / ESI 2)
        if present_concepts.intersection(self.GI_BLEED_TOKENS):
            red_flags.append(
                "Active hemorrhage sign: documented hematemesis (coffee-ground vomiting) or gross hemoptysis."
            )

        # 5. Anaphylaxis constellation (World Allergy Organization Guidelines / ESI 1)
        has_swelling = bool(present_concepts.intersection(self.SWELLING_TOKENS))
        if has_swelling and (has_dyspnea or present_concepts.intersection(self.STRIDOR_TOKENS)):
            red_flags.append(
                "Suspected acute anaphylaxis: acute swelling combined with respiratory compromise."
            )

        # 6. Critical Vital Sign Extremes (WHO ETAT / ESI 1/2) with Robust Unit Normalization
        for item in ledger.items:
            concept_lower = item.concept.lower()
            if "temp" in concept_lower and item.normalized_value is not None:
                is_flag, flag_msg = self._evaluate_temperature_measurement(
                    raw_val=item.normalized_value,
                    original_val=item.original_value,
                    unit=item.unit
                )
                if is_flag and flag_msg:
                    red_flags.append(flag_msg)

            if "spo2" in concept_lower and item.normalized_value is not None:
                is_flag, flag_msg = self._evaluate_spo2_measurement(
                    raw_val=item.normalized_value,
                    original_val=item.original_value,
                    unit=item.unit
                )
                if is_flag and flag_msg:
                    red_flags.append(flag_msg)

        return (len(red_flags) > 0, red_flags)

    @staticmethod
    def _evaluate_temperature_measurement(
        raw_val: Any,
        original_val: Optional[str] = None,
        unit: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Robustly parses and normalizes core body temperature observations:
        - Explicit handling for missing units (infers physiological range without silent discard)
        - Explicit handling for unrecognized/invalid units (preserves observation, warns of ambiguity)
        - Explicit handling for ambiguous measurements (<30C or >115F)
        - Separates original and normalized representation
        """
        try:
            val = float(raw_val)
        except (ValueError, TypeError):
            return (False, None)

        u_str = (unit or "").strip().lower()
        f_units = {"degf", "f", "°f", "deg f", "fahrenheit"}
        c_units = {"degc", "c", "°c", "deg c", "celsius"}

        normalized_unit = None
        norm_val = val
        ambiguity_note = None

        if u_str in f_units:
            normalized_unit = "degF"
        elif u_str in c_units:
            normalized_unit = "degC"
        elif not u_str or u_str in {"none", "unknown", "null"}:
            # Missing unit: physiologically determine scale
            if 90.0 <= val <= 115.0:
                normalized_unit = "degF"
                ambiguity_note = "unit missing; inferred degF from physiological range [90, 115]"
            elif 30.0 <= val <= 45.0:
                normalized_unit = "degC"
                ambiguity_note = "unit missing; inferred degC from physiological range [30, 45]"
            else:
                return (False, None)  # Physiologically ambiguous
        else:
            # Unrecognized / invalid unit string (e.g. 'bpm', 'kg')
            if 90.0 <= val <= 115.0:
                normalized_unit = "degF"
                ambiguity_note = f"unrecognized unit '{unit}'; evaluated as degF from physiological range"
            elif 30.0 <= val <= 45.0:
                normalized_unit = "degC"
                ambiguity_note = f"unrecognized unit '{unit}'; evaluated as degC from physiological range"
            else:
                return (False, None)

        # Evaluate hyperpyrexia threshold (>= 104 degF or >= 40 degC)
        is_hyperpyrexia = (
            (normalized_unit == "degF" and norm_val >= 104.0) or
            (normalized_unit == "degC" and norm_val >= 40.0)
        )

        if is_hyperpyrexia:
            note_suffix = f" ({ambiguity_note})" if ambiguity_note else ""
            msg = f"Hyperpyrexia red flag: recorded core temperature {norm_val} {normalized_unit} >= 104 degF / 40 degC{note_suffix}."
            return (True, msg)

        return (False, None)

    @staticmethod
    def _evaluate_spo2_measurement(
        raw_val: Any,
        original_val: Optional[str] = None,
        unit: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Robustly parses and normalizes oxygen saturation (SpO2):
        - Handles decimal fractions (0.88 -> 88%)
        - Handles missing or percentage units
        - Flags hypoxemia (<90%)
        """
        try:
            val = float(raw_val)
        except (ValueError, TypeError):
            return (False, None)

        # Decimal fraction normalization
        if 0.40 <= val <= 1.0:
            norm_val = round(val * 100.0, 1)
        elif 1.0 < val <= 100.0:
            norm_val = val
        else:
            return (False, None)  # Sensor disconnect / ambiguous

        if norm_val < 90.0:
            return (True, f"Severe hypoxemia red flag: oxygen saturation {norm_val}% < 90%.")

        return (False, None)



class BasePolicy:
    """Abstract interface for action selection policies."""
    def select_action(
        self,
        ledger: EvidenceLedger,
        probabilities: Optional[np.ndarray] = None,
        candidate_question: Optional[Dict[str, Any]] = None,
        pathology_list: Optional[List[str]] = None,
    ) -> PolicyDecision:
        raise NotImplementedError


class B0_AlwaysExplainPolicy(BasePolicy):
    """
    Baseline B0: Naive Explain Policy.
    Always produces an explanation (EXPLAIN) unless the explicitly tested emergency override fires.
    Ignores extraction uncertainty, opinion disagreements, and predictive ambiguity.
    """
    def __init__(self):
        self.emergency_detector = EmergencySafetyOverrideDetector()

    def select_action(
        self,
        ledger: EvidenceLedger,
        probabilities: Optional[np.ndarray] = None,
        candidate_question: Optional[Dict[str, Any]] = None,
        pathology_list: Optional[List[str]] = None,
    ) -> PolicyDecision:
        is_emerg, flags = self.emergency_detector.check_emergency(ledger)
        if is_emerg:
            return PolicyDecision(
                selected_action=PolicyAction.EMERGENCY_OVERRIDE,
                is_emergency_override=True,
                reason="Predefined urgent-warning emergency condition detected.",
                detailed_rationale="; ".join(flags),
                emergency_details={"red_flags": flags},
            )

        # B0 always explains
        unc = compute_predictive_uncertainty(probabilities, num_classes=len(pathology_list) if pathology_list else 49) if probabilities is not None else {}
        return PolicyDecision(
            selected_action=PolicyAction.EXPLAIN,
            is_emergency_override=False,
            reason="Baseline B0: Default unconditional explanation policy.",
            detailed_rationale="Policy provides evidence summary without checking conflicts or uncertainty signals.",
            uncertainty_signals=unc,
            explanation_summary={
                "present_evidence_count": sum(1 for i in ledger.items if i.evidence_status == EvidenceStatus.PRESENT),
                "policy_baseline": "B0_AlwaysExplain",
            },
        )


class B1_ConflictOnlyPolicy(BasePolicy):
    """
    Baseline B1: Conflict-Only Policy.
    Incorporates Phase 3 conflict detection without the new uncertainty-aware policy.
    - If emergency override fires -> EMERGENCY_OVERRIDE
    - If conflict detector finds any conflict -> ABSTAIN_AND_NAVIGATE
    - Otherwise -> EXPLAIN
    Does not ask follow-up questions, does not track predictive entropy or extraction uncertainty.
    """
    def __init__(self, low_confidence_threshold: float = 0.70):
        self.emergency_detector = EmergencySafetyOverrideDetector()
        self.conflict_detector = RuleBasedConflictDetector(low_confidence_threshold=low_confidence_threshold)

    def select_action(
        self,
        ledger: EvidenceLedger,
        probabilities: Optional[np.ndarray] = None,
        candidate_question: Optional[Dict[str, Any]] = None,
        pathology_list: Optional[List[str]] = None,
    ) -> PolicyDecision:
        is_emerg, flags = self.emergency_detector.check_emergency(ledger)
        if is_emerg:
            return PolicyDecision(
                selected_action=PolicyAction.EMERGENCY_OVERRIDE,
                is_emergency_override=True,
                reason="Predefined urgent-warning emergency condition detected.",
                detailed_rationale="; ".join(flags),
                emergency_details={"red_flags": flags},
            )

        conflicts = self.conflict_detector.detect_conflicts(ledger)
        unc = compute_predictive_uncertainty(probabilities, num_classes=len(pathology_list) if pathology_list else 49) if probabilities is not None else {}

        if len(conflicts) > 0:
            c_types = [c.conflict_type.value for c in conflicts]
            return PolicyDecision(
                selected_action=PolicyAction.ABSTAIN_AND_NAVIGATE,
                is_emergency_override=False,
                reason="Baseline B1: Conflict detected in evidence ledger.",
                detailed_rationale=f"Detected {len(conflicts)} conflict(s): {', '.join(set(c_types))}. Declining explanation.",
                uncertainty_signals=unc,
                detected_conflicts_count=len(conflicts),
                abstention_summary={
                    "conflicts": [c.model_dump() for c in conflicts],
                    "recommendation": "Consult a qualified medical provider to resolve documented discrepancies.",
                },
            )

        return PolicyDecision(
            selected_action=PolicyAction.EXPLAIN,
            is_emergency_override=False,
            reason="Baseline B1: No conflict detected in evidence ledger.",
            detailed_rationale="All evidence items passed standard conflict checks; generating bounded evidence summary.",
            uncertainty_signals=unc,
            detected_conflicts_count=0,
            explanation_summary={
                "present_evidence_count": sum(1 for i in ledger.items if i.evidence_status == EvidenceStatus.PRESENT),
                "policy_baseline": "B1_ConflictOnly",
            },
        )


class SelectiveActionPolicy(BasePolicy):
    """
    Proposed Policy B2: Uncertainty-Aware Selective Action Policy.
    
    Synthesizes:
    - Predefined urgent-warning emergency rules (strict priority override)
    - Source-aware extraction uncertainty (OCR confidence, user confirmation status)
    - Conflict taxonomy reports (non-arbitration of clinician opinions, source disagreements)
    - Diagnostic predictive uncertainty (Shannon entropy, top-1 margin)
    - Follow-up question availability
    
    Decision Hierarchy:
    1. Safety Override: If acute emergency criteria met -> EMERGENCY_OVERRIDE
    2. Extraction Uncertainty: If an unconfirmed low-confidence extraction exists -> ASK
    3. Unresolved Material Conflict: If material conflict detected (opinions disagree,
       source contradiction, high severity value discrepancy) -> ABSTAIN_AND_NAVIGATE
    4. Diagnostic Ambiguity & Active Questioning: If entropy is elevated or margin is low,
       and a documented useful question is available -> ASK
    5. Bounded Evidence Explanation: If uncertainty is low, evidence is adequate, and no
       unresolved conflicts exist -> EXPLAIN
    6. Conservative Fallback: If none met (e.g. high uncertainty but no question available)
       -> ABSTAIN_AND_NAVIGATE
    """

    def __init__(
        self,
        low_confidence_threshold: float = 0.70,
        entropy_threshold: float = 0.45,
        margin_threshold: float = 0.35,
    ):
        self.low_confidence_threshold = low_confidence_threshold
        self.entropy_threshold = entropy_threshold
        self.margin_threshold = margin_threshold
        self.emergency_detector = EmergencySafetyOverrideDetector()
        self.conflict_detector = RuleBasedConflictDetector(low_confidence_threshold=low_confidence_threshold)

    def select_action(
        self,
        ledger: EvidenceLedger,
        probabilities: Optional[np.ndarray] = None,
        candidate_question: Optional[Dict[str, Any]] = None,
        pathology_list: Optional[List[str]] = None,
    ) -> PolicyDecision:
        num_classes = len(pathology_list) if pathology_list else 49

        # Calculate predictive uncertainty signals
        unc = compute_predictive_uncertainty(probabilities, num_classes=num_classes) if probabilities is not None else {
            "shannon_entropy": 0.0,
            "normalized_entropy": 0.0,
            "top1_probability": 0.0,
            "top2_probability": 0.0,
            "prediction_margin": 0.0,
        }

        # Run Phase 3 conflict detection
        conflicts = self.conflict_detector.detect_conflicts(ledger)
        num_conflicts = len(conflicts)

        # ---------------------------------------------------------------------
        # STEP 1: Emergency Safety Override (Takes strict precedence)
        # ---------------------------------------------------------------------
        is_emerg, red_flags = self.emergency_detector.check_emergency(ledger)
        if is_emerg:
            return PolicyDecision(
                selected_action=PolicyAction.EMERGENCY_OVERRIDE,
                is_emergency_override=True,
                reason="Predefined urgent-warning emergency condition detected.",
                detailed_rationale="; ".join(red_flags),
                uncertainty_signals=unc,
                detected_conflicts_count=num_conflicts,
                emergency_details={
                    "red_flags": red_flags,
                    "immediate_action": "Seek immediate emergency medical evaluation (call emergency services or go to nearest emergency department).",
                },
            )

        # ---------------------------------------------------------------------
        # STEP 2: Extraction Uncertainty (Low-confidence unconfirmed extraction)
        # ---------------------------------------------------------------------
        low_conf_items = []
        for item in ledger.items:
            if (
                item.extraction_confidence < self.low_confidence_threshold
                and item.user_confirmation_status == UserConfirmationStatus.UNCONFIRMED
            ):
                low_conf_items.append(item)

        if low_conf_items:
            target_item = low_conf_items[0]
            concept_display = target_item.concept_name_en or target_item.concept
            q_text = (
                f"We noticed that the value for '{concept_display}' from your uploaded document "
                f"({target_item.source_type.value}) had low extraction confidence ({target_item.extraction_confidence:.2f}). "
                f"Could you please confirm or clarify if this finding is accurate?"
            )
            return PolicyDecision(
                selected_action=PolicyAction.ASK,
                is_emergency_override=False,
                reason="Low-confidence document extraction requires user verification.",
                detailed_rationale=(
                    f"Evidence item '{target_item.evidence_id}' ({target_item.concept}) has extraction confidence "
                    f"{target_item.extraction_confidence:.2f} < {self.low_confidence_threshold} and remains unconfirmed. "
                    "Prompting user for direct confirmation before accepting the extracted value."
                ),
                uncertainty_signals=unc,
                detected_conflicts_count=num_conflicts,
                target_concept_to_ask=target_item.concept,
                candidate_question_en=q_text,
                question_rationale="Verify uncertain automated document extraction with the patient.",
            )

        # ---------------------------------------------------------------------
        # STEP 3: Unresolved Material Conflicts (Non-Arbitration & Abstention)
        # ---------------------------------------------------------------------
        material_conflict_types = {
            ConflictType.ENTERED_OPINION_DISAGREEMENT,
            ConflictType.SOURCE_STATEMENT_DISAGREEMENT,
            ConflictType.VALUE_OR_UNIT_DISCREPANCY,
        }
        material_conflicts = [
            c for c in conflicts
            if c.conflict_type in material_conflict_types or c.severity == ConflictSeverity.HIGH
        ]

        if material_conflicts:
            c_types = list({c.conflict_type.value for c in material_conflicts})
            reasons = [c.reason for c in material_conflicts]

            # Special check for clinician opinion disagreement non-arbitration
            has_opinion_disagreement = any(
                c.conflict_type == ConflictType.ENTERED_OPINION_DISAGREEMENT for c in material_conflicts
            )
            specific_reason = (
                "Conflicting clinician impressions detected. System refrains from arbitrating clinical truth "
                "between differing medical opinions."
                if has_opinion_disagreement
                else f"Unresolved material clinical data conflict(s): {', '.join(c_types)}."
            )

            return PolicyDecision(
                selected_action=PolicyAction.ABSTAIN_AND_NAVIGATE,
                is_emergency_override=False,
                reason=specific_reason,
                detailed_rationale="; ".join(reasons),
                uncertainty_signals=unc,
                detected_conflicts_count=num_conflicts,
                abstention_summary={
                    "unresolved_conflicts": [c.model_dump() for c in material_conflicts],
                    "non_arbitration_notice": (
                        "MedResolve does not assess or arbitrate clinical correctness when clinician opinions differ. "
                        "A formal consultation with an independent physician is advised."
                    ),
                    "navigation_guidance": "Provide the complete evidence summary to an attending clinician for in-person assessment.",
                },
            )

        # ---------------------------------------------------------------------
        # STEP 4: Diagnostic Ambiguity & Active Questioning
        # ---------------------------------------------------------------------
        # Check if diagnostic uncertainty is elevated (only if predictive distribution is supplied)
        has_predictive_uncertainty = (probabilities is not None) and (
            unc["normalized_entropy"] >= self.entropy_threshold
            or unc["prediction_margin"] < self.margin_threshold
        )
        is_uncertain = (
            has_predictive_uncertainty
            or ledger.metadata.get("is_ambiguous_presentation", False)
        )

        if is_uncertain:
            # Check if a meaningful follow-up question is available
            if candidate_question and candidate_question.get("question_en"):
                q_concept = candidate_question.get("concept", "UNKNOWN_CONCEPT")
                q_text = candidate_question.get("question_en", "")
                return PolicyDecision(
                    selected_action=PolicyAction.ASK,
                    is_emergency_override=False,
                    reason="Elevated diagnostic uncertainty with informative follow-up question available.",
                    detailed_rationale=(
                        f"Predictive uncertainty is elevated (normalized entropy: {unc['normalized_entropy']:.2f} >= {self.entropy_threshold} "
                        f"or margin: {unc['prediction_margin']:.2f} < {self.margin_threshold}). "
                        f"Requesting targeted information on '{q_concept}' to narrow differential possibilities."
                    ),
                    uncertainty_signals=unc,
                    detected_conflicts_count=num_conflicts,
                    target_concept_to_ask=q_concept,
                    candidate_question_en=q_text,
                    question_rationale=candidate_question.get("rationale", "Discriminate between top competing diagnostic possibilities."),
                )
            else:
                # High uncertainty, but NO question is available -> Conservative Abstain
                return PolicyDecision(
                    selected_action=PolicyAction.ABSTAIN_AND_NAVIGATE,
                    is_emergency_override=False,
                    reason="Elevated diagnostic uncertainty without available follow-up question.",
                    detailed_rationale=(
                        f"Predictive uncertainty is elevated (normalized entropy: {unc['normalized_entropy']:.2f}, "
                        f"margin: {unc['prediction_margin']:.2f}), but no further discriminating follow-up question is available. "
                        "Conservatively abstaining from ungrounded differential generation."
                    ),
                    uncertainty_signals=unc,
                    detected_conflicts_count=num_conflicts,
                    abstention_summary={
                        "uncertainty_status": "HIGH_ENTROPY_NO_QUESTIONS",
                        "navigation_guidance": "Present findings to a primary care clinician for formal comprehensive examination.",
                    },
                )

        # ---------------------------------------------------------------------
        # STEP 5: Bounded Evidence Explanation
        # ---------------------------------------------------------------------
        # Uncertainty is low, evidence is adequate, and no material conflicts
        present_items = [
            {"concept": i.concept, "name": i.concept_name_en, "source": i.source_type.value}
            for i in ledger.items if i.evidence_status == EvidenceStatus.PRESENT
        ]
        absent_items = [
            {"concept": i.concept, "name": i.concept_name_en, "source": i.source_type.value}
            for i in ledger.items if i.evidence_status == EvidenceStatus.ABSENT
        ]

        # Top diagnostic candidates for bounded context (non-binding)
        top_candidates = []
        if probabilities is not None and pathology_list is not None:
            top_k_indices = np.argsort(probabilities)[::-1][:3]
            for rank, idx in enumerate(top_k_indices, 1):
                top_candidates.append({
                    "rank": rank,
                    "condition": pathology_list[idx],
                    "calibrated_score": round(float(probabilities[idx]), 4),
                })

        return PolicyDecision(
            selected_action=PolicyAction.EXPLAIN,
            is_emergency_override=False,
            reason="Sufficient verified evidence with low diagnostic uncertainty.",
            detailed_rationale=(
                f"Predictive uncertainty is low (normalized entropy: {unc['normalized_entropy']:.2f} < {self.entropy_threshold}, "
                f"margin: {unc['prediction_margin']:.2f} >= {self.margin_threshold}) with zero unresolved material conflicts. "
                "Generating bounded evidence summary grounded strictly in documented findings."
            ),
            uncertainty_signals=unc,
            detected_conflicts_count=num_conflicts,
            explanation_summary={
                "present_findings": present_items,
                "pertinent_negatives": absent_items,
                "top_differential_considerations": top_candidates,
                "grounding_disclaimer": "Differential considerations are provided for discussion with a physician and are not diagnostic determinations.",
            },
        )

    def execute_policy_with_rag(
        self,
        ledger: EvidenceLedger,
        probabilities: Optional[np.ndarray] = None,
        candidate_question: Optional[Dict[str, Any]] = None,
        pathology_list: Optional[List[str]] = None,
        kb: Optional[Any] = None,
        rag_generator: Optional[Any] = None,
        system_mode: str = "B2_RAG_Verified",
    ) -> PolicyDecision:
        """
        Executes selective action policy and conditionally attaches evidence-grounded
        RAG explanations ONLY when EXPLAIN action is selected.
        
        Strict Safety Guarantees:
        - EMERGENCY_OVERRIDE strictly preempts RAG and all ordinary actions.
        - Material conflicts trigger ABSTAIN_AND_NAVIGATE without generating RAG advice.
        - High uncertainty triggers ASK (or ABSTAIN_AND_NAVIGATE) without generating RAG advice.
        - RAG passages are never used to override unresolved conflicts in the ledger.
        """
        decision = self.select_action(
            ledger=ledger,
            probabilities=probabilities,
            candidate_question=candidate_question,
            pathology_list=pathology_list,
        )

        # Conditionally invoke RAG ONLY IF action is EXPLAIN and RAG components provided
        if decision.selected_action == PolicyAction.EXPLAIN and kb is not None and rag_generator is not None:
            present_symptoms = [
                i.concept_name_en or i.concept
                for i in ledger.items
                if i.evidence_status == EvidenceStatus.PRESENT
            ]
            top_diff = None
            if decision.explanation_summary and decision.explanation_summary.get("top_differential_considerations"):
                top_diff = decision.explanation_summary["top_differential_considerations"][0]["condition"]

            query = f"{' '.join(present_symptoms[:3])} {top_diff or ''}".strip()
            retrieved = kb.search_hybrid(query, top_k=3)

            rag_res = rag_generator.generate_explanation(
                ledger=ledger,
                retrieved_results=retrieved,
                candidate_differentials=decision.explanation_summary.get("top_differential_considerations"),
                system_mode=system_mode,
            )

            if decision.explanation_summary is not None:
                decision.explanation_summary["grounded_rag_explanation"] = rag_res.to_dict()

        return decision


class B2_NoExtractionUncertaintyPolicy(SelectiveActionPolicy):
    """
    Ablation Policy: Disables Step 2 (extraction uncertainty check).
    Treats low-confidence automated document extractions as ordinary verified items.
    Used to quantify the specific impact of extraction uncertainty awareness.
    """
    def select_action(
        self,
        ledger: EvidenceLedger,
        probabilities: Optional[np.ndarray] = None,
        candidate_question: Optional[Dict[str, Any]] = None,
        pathology_list: Optional[List[str]] = None,
    ) -> PolicyDecision:
        # Emergency check
        is_emerg, red_flags = self.emergency_detector.check_emergency(ledger)
        if is_emerg:
            return PolicyDecision(
                selected_action=PolicyAction.EMERGENCY_OVERRIDE,
                is_emergency_override=True,
                reason="Predefined urgent-warning emergency condition detected.",
                detailed_rationale="; ".join(red_flags),
                emergency_details={"red_flags": red_flags},
            )

        # SKIPS STEP 2 (Extraction Uncertainty) completely!

        # Step 3: Material conflicts
        conflicts = self.conflict_detector.detect_conflicts(ledger)
        material_conflicts = [
            c for c in conflicts
            if c.conflict_type in {
                ConflictType.ENTERED_OPINION_DISAGREEMENT,
                ConflictType.SOURCE_STATEMENT_DISAGREEMENT,
                ConflictType.VALUE_OR_UNIT_DISCREPANCY,
            } or c.severity == ConflictSeverity.HIGH
        ]
        if material_conflicts:
            c_types = list({c.conflict_type.value for c in material_conflicts})
            return PolicyDecision(
                selected_action=PolicyAction.ABSTAIN_AND_NAVIGATE,
                is_emergency_override=False,
                reason=f"Unresolved material clinical data conflict(s): {', '.join(c_types)}.",
                detailed_rationale="; ".join([c.reason for c in material_conflicts]),
                detected_conflicts_count=len(conflicts),
                abstention_summary={"unresolved_conflicts": [c.model_dump() for c in material_conflicts]},
            )

        # Step 4: Diagnostic ambiguity
        unc = compute_predictive_uncertainty(probabilities, num_classes=len(pathology_list) if pathology_list else 49) if probabilities is not None else {}
        is_uncertain = (
            unc.get("normalized_entropy", 0.0) >= self.entropy_threshold
            or unc.get("prediction_margin", 1.0) < self.margin_threshold
            or ledger.metadata.get("is_ambiguous_presentation", False)
        )
        if is_uncertain:
            if candidate_question and candidate_question.get("question_en"):
                return PolicyDecision(
                    selected_action=PolicyAction.ASK,
                    is_emergency_override=False,
                    reason="Elevated diagnostic uncertainty with informative follow-up question available.",
                    detailed_rationale="Active question prompted by predictive entropy.",
                    uncertainty_signals=unc,
                    target_concept_to_ask=candidate_question.get("concept"),
                    candidate_question_en=candidate_question.get("question_en"),
                )
            else:
                return PolicyDecision(
                    selected_action=PolicyAction.ABSTAIN_AND_NAVIGATE,
                    is_emergency_override=False,
                    reason="Elevated diagnostic uncertainty without available follow-up question.",
                    detailed_rationale="Conservative abstention.",
                    uncertainty_signals=unc,
                )

        return PolicyDecision(
            selected_action=PolicyAction.EXPLAIN,
            is_emergency_override=False,
            reason="Ablation policy: default explanation.",
            detailed_rationale="Extraction uncertainty disabled; proceeding with explanation.",
            uncertainty_signals=unc,
        )


class B2_NoPredictiveUncertaintyPolicy(SelectiveActionPolicy):
    """
    Ablation Policy: Disables Step 4 (predictive uncertainty & entropy check).
    Never asks clarifying follow-up questions for ambiguous presentations.
    Used to quantify the specific impact of active diagnostic questioning.
    """
    def select_action(
        self,
        ledger: EvidenceLedger,
        probabilities: Optional[np.ndarray] = None,
        candidate_question: Optional[Dict[str, Any]] = None,
        pathology_list: Optional[List[str]] = None,
    ) -> PolicyDecision:
        # Emergency check
        is_emerg, red_flags = self.emergency_detector.check_emergency(ledger)
        if is_emerg:
            return PolicyDecision(
                selected_action=PolicyAction.EMERGENCY_OVERRIDE,
                is_emergency_override=True,
                reason="Predefined urgent-warning emergency condition detected.",
                detailed_rationale="; ".join(red_flags),
                emergency_details={"red_flags": red_flags},
            )

        # Step 2: Extraction uncertainty
        low_conf = [
            it for it in ledger.items
            if it.extraction_confidence < self.low_confidence_threshold
            and it.user_confirmation_status == UserConfirmationStatus.UNCONFIRMED
        ]
        if low_conf:
            target = low_conf[0]
            return PolicyDecision(
                selected_action=PolicyAction.ASK,
                is_emergency_override=False,
                reason="Low-confidence document extraction requires user verification.",
                detailed_rationale="Prompting user for direct confirmation.",
                target_concept_to_ask=target.concept,
                candidate_question_en=f"Please confirm value for {target.concept_name_en or target.concept}.",
            )

        # Step 3: Material conflicts
        conflicts = self.conflict_detector.detect_conflicts(ledger)
        material_conflicts = [
            c for c in conflicts
            if c.conflict_type in {
                ConflictType.ENTERED_OPINION_DISAGREEMENT,
                ConflictType.SOURCE_STATEMENT_DISAGREEMENT,
                ConflictType.VALUE_OR_UNIT_DISCREPANCY,
            } or c.severity == ConflictSeverity.HIGH
        ]
        if material_conflicts:
            c_types = list({c.conflict_type.value for c in material_conflicts})
            return PolicyDecision(
                selected_action=PolicyAction.ABSTAIN_AND_NAVIGATE,
                is_emergency_override=False,
                reason=f"Unresolved material clinical data conflict(s): {', '.join(c_types)}.",
                detailed_rationale="; ".join([c.reason for c in material_conflicts]),
                abstention_summary={"unresolved_conflicts": [c.model_dump() for c in material_conflicts]},
            )

        # SKIPS STEP 4 (Predictive Uncertainty & Active Questioning)!
        # Directly explains!
        return PolicyDecision(
            selected_action=PolicyAction.EXPLAIN,
            is_emergency_override=False,
            reason="Ablation policy: predictive uncertainty disabled; explaining directly.",
            detailed_rationale="Proceeding with explanation without checking entropy.",
        )

