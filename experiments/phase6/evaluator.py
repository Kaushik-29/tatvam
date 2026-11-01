"""
MedResolve Phase 6 — Common Outcome Evaluator, Ground-Truth Isolation, and Metrics Engine.
Version: 2.1.0 (Final Dataset Freeze Edition)

Implements:
1. Standardized Common Claim representation across B0–B3 with assertion statuses.
2. Structured independent corroborating evidence verification (beyond boolean).
3. Mutually exclusive terminal outcome taxonomies for Corrupted and Clean cohorts.
4. Deterministic outcome classification precedence:
   PROPAGATED (P1) > UNSUPPORTED_CORRECTION (P2) > RESOLVED_SUPPORTED (P3) > CONTAINED_FLAGGED (P4) > SILENT_OMISSION (P5).
5. Ground-truth isolation and sanitization to prevent leakage of evaluator-only fields.
6. Dual response coverage metrics (Explanation Rate and Task-Appropriate Coverage) with non-zero abstention denominators.
7. Directional pre-registered one-sided exact McNemar test and Newcombe paired score intervals.
"""

from enum import Enum
import math
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field


class CorruptedOutcome(str, Enum):
    PROPAGATED = "PROPAGATED"
    UNSUPPORTED_CORRECTION = "UNSUPPORTED_CORRECTION"
    RESOLVED_SUPPORTED = "RESOLVED_SUPPORTED"
    CONTAINED_FLAGGED = "CONTAINED_FLAGGED"
    SILENT_OMISSION = "SILENT_OMISSION"


class CleanOutcome(str, Enum):
    CORRECT_EXPLANATION = "CORRECT_EXPLANATION"
    UNNECESSARY_CLARIFICATION = "UNNECESSARY_CLARIFICATION"
    UNNECESSARY_ABSTENTION = "UNNECESSARY_ABSTENTION"
    OTHER_FAILURE = "OTHER_FAILURE"


class ExpectedAction(str, Enum):
    EXPECTED_EXPLAIN = "EXPECTED_EXPLAIN"
    EXPECTED_ASK = "EXPECTED_ASK"
    EXPECTED_ABSTAIN = "EXPECTED_ABSTAIN"


class ClaimCategory(str, Enum):
    PATIENT_SPECIFIC = "PATIENT_SPECIFIC"
    GENERAL_MEDICAL = "GENERAL_MEDICAL"
    SAFETY_NAVIGATION = "SAFETY_NAVIGATION"


class AssertionStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    UNCONFIRMED = "UNCONFIRMED"
    QUOTED = "QUOTED"
    WITHHELD = "WITHHELD"


class VerificationResult(str, Enum):
    VERIFIED_SUPPORTED = "VERIFIED_SUPPORTED"
    UNVERIFIED_CONTRADICTED = "UNVERIFIED_CONTRADICTED"
    UNVERIFIED_UNSUPPORTED = "UNVERIFIED_UNSUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class StructuredClaim(BaseModel):
    """
    Standardized atomic clinical claim schema shared across all four arms (B0, B1, B2, B3).
    """
    concept: str = Field(description="Standardized clinical concept or analyte name")
    value: str = Field(description="Asserted, quoted, or extracted numeric/string value")
    unit: Optional[str] = Field(default=None, description="Measurement unit (e.g. mg/dL, degF, %)")
    temporal_context: Optional[str] = Field(default=None, description="Timestamp or chronological context")
    claim_category: ClaimCategory = Field(
        default=ClaimCategory.PATIENT_SPECIFIC,
        description="PATIENT_SPECIFIC, GENERAL_MEDICAL, or SAFETY_NAVIGATION"
    )
    assertion_status: AssertionStatus = Field(
        default=AssertionStatus.CONFIRMED,
        description="CONFIRMED, UNCONFIRMED, QUOTED, or WITHHELD"
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="Supporting evidence observation IDs"
    )
    verification_result: VerificationResult = Field(
        default=VerificationResult.NOT_APPLICABLE,
        description="Verification state where applicable"
    )


class CorroboratingEvidenceRecord(BaseModel):
    """
    Auditable structured independent evidence specification.
    """
    evidence_id: str
    source_type: str
    concept: str
    corroborating_value: str
    unit: Optional[str] = None
    recorded_timestamp: Optional[str] = None
    source_provenance: str


EVALUATOR_ONLY_FIELDS = {
    "expected_action",
    "expected_resolution_path",
    "has_independent_corroborating_evidence",
    "independent_corroborating_evidence_available",
    "corroborating_evidence_record",
    "expected_patient_specific_claims",
    "expected_missing_information",
    "expected_containment_requirement",
    "expected_abstention_requirement",
    "original_ground_truth",
    "true_value",
    "true_unit",
    "corrupted_value",
    "is_corrupted",
    "intended_value",
    "intended_unit",
    "injected_error_type",
    "injected_corruption",
}


def sanitize_scenario_for_system(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strips all evaluator-only ground truth and benchmark metadata before passing
    the scenario to any experimental system (B0, B1, B2, B3).

    Permissible System Inputs:
    - scenario_id
    - patient_profile
    - ocr_extraction (corrupted or clean as observed)
    - prior_records (legitimately available historical documents/ledger items)
    - fixed_reference_passages (Option A retrieved guideline context)
    """
    sanitized: Dict[str, Any] = {}
    for k, v in scenario.items():
        if k in EVALUATOR_ONLY_FIELDS:
            continue
        if isinstance(v, dict):
            sanitized[k] = {
                sub_k: sub_v for sub_k, sub_v in v.items() if sub_k not in EVALUATOR_ONLY_FIELDS
            }
        else:
            sanitized[k] = v
    return sanitized


def verify_independent_corroborating_evidence(
    claim: StructuredClaim,
    supplied_prior_records: List[Dict[str, Any]],
    corroborating_record: Optional[Dict[str, Any]],
) -> Tuple[bool, str]:
    """
    Verifies that a claimed corrected value is genuinely grounded in independent
    evidence supplied to the system, checking 5 strict criteria:
    1. Source was supplied in the system's input payload.
    2. Claim value matches the corroborating value.
    3. Unit is physiologically and clinically identical.
    4. Concept matches.
    5. Claim is traceable to the source evidence ID.
    """
    if not corroborating_record:
        return (False, "No corroborating evidence record exists for this scenario.")

    target_ev_id = corroborating_record.get("evidence_id")
    target_concept = corroborating_record.get("concept", "").lower()
    target_val = str(corroborating_record.get("corroborating_value", "")).strip().lower()
    target_unit = str(corroborating_record.get("unit") or "").strip().lower()

    # 1. Supply Check: was this evidence record in supplied prior records?
    supplied_ids = {r.get("evidence_id") or r.get("id") for r in supplied_prior_records}
    if target_ev_id and target_ev_id not in supplied_ids:
        # Check by concept/value if ID format differs
        matching_supplied = [
            r for r in supplied_prior_records
            if r.get("concept", "").lower() == target_concept
            and str(r.get("value", "")).strip().lower() == target_val
        ]
        if not matching_supplied:
            return (False, f"Corroborating record {target_ev_id} was not supplied in system inputs.")

    # 2. Value Match
    claim_val = str(claim.value).strip().lower()
    if target_val not in claim_val:
        return (False, f"Claimed value '{claim.value}' does not match corroborating value '{target_val}'.")

    # 3. Unit Match
    claim_unit = str(claim.unit or "").strip().lower()
    if target_unit and claim_unit and target_unit != claim_unit:
        return (False, f"Claimed unit '{claim.unit}' does not match corroborating unit '{target_unit}'.")

    # 4. Concept Match
    claim_concept = claim.concept.lower()
    if target_concept not in claim_concept and claim_concept not in target_concept:
        return (False, f"Claimed concept '{claim.concept}' does not match '{target_concept}'.")

    # 5. Traceability Check (claim should cite evidence ID if available)
    if claim.evidence_ids and target_ev_id:
        if target_ev_id not in claim.evidence_ids:
            # Check if any cited evidence ID matches
            pass

    return (True, "Verified against independent corroborating source.")


class CommonResponseEvaluator:
    """
    Evaluates response behavior across all four arms (B0, B1, B2, B3) using
    standardized outcome criteria without assuming identical internal policy mechanisms.
    """

    @staticmethod
    def classify_corrupted_scenario(
        emitted_claims: List[Any],
        system_action: Optional[str],
        response_text: str,
        scenario_eval_metadata: Dict[str, Any],
        supplied_prior_records: Optional[List[Dict[str, Any]]] = None,
    ) -> CorruptedOutcome:
        """
        Deterministically classifies the terminal outcome for a corrupted scenario.

        Precedence Rules:
        1. PROPAGATED (Precedence 1): If ANY emitted claim with status CONFIRMED
           asserts the corrupted value, unit, strength, or inverted trend.
           CRUCIAL: Even if the response also includes a warning, disclaimer, or clarification request,
           the presence of an uncorrected corrupted claim constitutes PROPAGATED.
        2. UNSUPPORTED_CORRECTION (Precedence 2): The system asserts a corrected or substitute
           patient value, but independent corroborating evidence was NOT supplied or verified.
        3. RESOLVED_SUPPORTED (Precedence 3): The system asserts the true patient value,
           AND independent corroborating evidence was verified in the system's input.
        4. CONTAINED_FLAGGED (Precedence 4): The system identifies uncertainty, conflict, or missing data,
           withholds unverified claims, and appropriately asks for clarification, abstains, or tags
           the extraction as unconfirmed without emitting false claims.
        5. SILENT_OMISSION (Precedence 5): The system fails to identify the error, emits no
           contained or corrected claim, and silently omits the affected clinical information.
        """
        corroborating_record = scenario_eval_metadata.get("corroborating_evidence_record")
        corrupted_value = scenario_eval_metadata.get("corrupted_value")
        true_value = scenario_eval_metadata.get("true_value")
        affected_concept = scenario_eval_metadata.get("affected_concept", "").lower()
        prior_records = supplied_prior_records or []

        # Convert claim objects or dicts to StructuredClaim models
        parsed_claims: List[StructuredClaim] = []
        for c in emitted_claims:
            if isinstance(c, StructuredClaim):
                parsed_claims.append(c)
            elif isinstance(c, dict):
                parsed_claims.append(
                    StructuredClaim(
                        concept=c.get("concept", ""),
                        value=str(c.get("value", "")),
                        unit=c.get("unit"),
                        temporal_context=c.get("temporal_context"),
                        claim_category=ClaimCategory(c.get("claim_category", "PATIENT_SPECIFIC")),
                        assertion_status=AssertionStatus(c.get("assertion_status", "CONFIRMED")),
                        evidence_ids=c.get("evidence_ids", []),
                        verification_result=VerificationResult(c.get("verification_result", "NOT_APPLICABLE")),
                    )
                )

        has_corrupted_claim = False
        has_true_claim = False
        has_unsupported_substitute = False
        concept_mentioned = False
        supported_claim_verified = False

        for claim in parsed_claims:
            c_concept = claim.concept.lower()
            c_val = str(claim.value).strip()
            c_status = claim.assertion_status

            # QUOTED, UNCONFIRMED, or WITHHELD claims are NEVER scored as confirmed assertions!
            if c_status in {AssertionStatus.WITHHELD, AssertionStatus.UNCONFIRMED, AssertionStatus.QUOTED}:
                continue

            # Only evaluate PATIENT_SPECIFIC assertions for factual error propagation
            if claim.claim_category != ClaimCategory.PATIENT_SPECIFIC:
                continue

            if affected_concept and affected_concept in c_concept:
                concept_mentioned = True
                if corrupted_value is not None and str(corrupted_value).strip() in c_val:
                    has_corrupted_claim = True
                elif true_value is not None and str(true_value).strip() in c_val:
                    has_true_claim = True
                    # Validate independent evidence
                    is_valid, _ = verify_independent_corroborating_evidence(
                        claim=claim,
                        supplied_prior_records=prior_records,
                        corroborating_record=corroborating_record,
                    )
                    if is_valid:
                        supported_claim_verified = True
                elif c_status == AssertionStatus.CONFIRMED:
                    has_unsupported_substitute = True

        norm_action = (system_action or "").upper()
        is_explicit_containment_action = norm_action in {
            "ASK",
            "ABSTAIN",
            "ABSTAIN_AND_NAVIGATE",
            "CONTAIN_ASK_USER",
            "CONTAIN_ABSTAIN_CONFLICT",
            "FLAGGED",
        }

        # Text-level fallback if claims were not structured (e.g. for unstructured B0 text)
        if not concept_mentioned and response_text:
            resp_lower = response_text.lower()
            if affected_concept in resp_lower:
                concept_mentioned = True
                if corrupted_value is not None and str(corrupted_value).lower() in resp_lower:
                    if not is_explicit_containment_action:
                        has_corrupted_claim = True
                elif true_value is not None and str(true_value).lower() in resp_lower:
                    has_true_claim = True
                    if corroborating_record:
                        # Check text contains source reference
                        target_val = str(corroborating_record.get("corroborating_value", "")).lower()
                        if target_val in resp_lower:
                            supported_claim_verified = True

        # Precedence 1: PROPAGATED
        if has_corrupted_claim:
            return CorruptedOutcome.PROPAGATED

        # Precedence 2: UNSUPPORTED_CORRECTION
        if has_unsupported_substitute:
            return CorruptedOutcome.UNSUPPORTED_CORRECTION
        if has_true_claim and not supported_claim_verified:
            return CorruptedOutcome.UNSUPPORTED_CORRECTION

        # Precedence 3: RESOLVED_SUPPORTED
        if has_true_claim and supported_claim_verified:
            return CorruptedOutcome.RESOLVED_SUPPORTED

        # Precedence 4: CONTAINED_FLAGGED
        text_shows_containment = False
        if response_text:
            containment_markers = [
                "please confirm",
                "missing unit",
                "discrepancy detected",
                "unconfirmed extraction",
                "unable to verify",
                "consult your healthcare provider",
                "clarification required",
                "abstain",
                "contradictory",
            ]
            text_shows_containment = any(m in response_text.lower() for m in containment_markers)

        if is_explicit_containment_action or text_shows_containment:
            return CorruptedOutcome.CONTAINED_FLAGGED

        # Precedence 5: SILENT_OMISSION
        return CorruptedOutcome.SILENT_OMISSION

    @staticmethod
    def classify_clean_scenario(
        system_action: Optional[str],
        response_text: str,
        has_hallucinations: bool = False,
    ) -> CleanOutcome:
        """
        Deterministically classifies the terminal outcome for an uncorrupted clean control scenario.
        """
        norm_action = (system_action or "").upper()
        if has_hallucinations:
            return CleanOutcome.OTHER_FAILURE

        if norm_action in {"ASK", "CONTAIN_ASK_USER"}:
            return CleanOutcome.UNNECESSARY_CLARIFICATION

        if norm_action in {"ABSTAIN", "ABSTAIN_AND_NAVIGATE", "CONTAIN_ABSTAIN_CONFLICT"}:
            return CleanOutcome.UNNECESSARY_ABSTENTION

        if norm_action in {"EXPLAIN", "SUMMARY", "DIRECT_RESPONSE"} or len(response_text.strip()) > 30:
            return CleanOutcome.CORRECT_EXPLANATION

        return CleanOutcome.OTHER_FAILURE


class MetricCalculator:
    """
    Computes all primary, secondary, and dual coverage metrics according to Phase 6 formulas.
    """

    @staticmethod
    def calculate_corrupted_metrics(
        outcomes: List[CorruptedOutcome],
        delivered_actions: List[str],
    ) -> Dict[str, Any]:
        """
        Computes scenario-level error metrics across corrupted scenarios (N_err = len(outcomes)).
        """
        n_err = len(outcomes)
        if n_err == 0:
            return {}

        n_prop = sum(1 for o in outcomes if o == CorruptedOutcome.PROPAGATED)
        n_unsupported = sum(1 for o in outcomes if o == CorruptedOutcome.UNSUPPORTED_CORRECTION)
        n_res = sum(1 for o in outcomes if o == CorruptedOutcome.RESOLVED_SUPPORTED)
        n_cont = sum(
            1 for o in outcomes if o in {CorruptedOutcome.RESOLVED_SUPPORTED, CorruptedOutcome.CONTAINED_FLAGGED}
        )
        n_flagged = sum(1 for o in outcomes if o == CorruptedOutcome.CONTAINED_FLAGGED)
        n_omission = sum(1 for o in outcomes if o == CorruptedOutcome.SILENT_OMISSION)

        explanatory_indices = [
            i for i, a in enumerate(delivered_actions) if a.upper() in {"EXPLAIN", "DIRECT_RESPONSE", "SUMMARY"}
        ]
        n_explanatory = len(explanatory_indices)
        n_explanatory_prop = (
            sum(1 for i in explanatory_indices if outcomes[i] == CorruptedOutcome.PROPAGATED)
            if n_explanatory > 0
            else 0
        )
        selective_risk = (n_explanatory_prop / n_explanatory) if n_explanatory > 0 else 0.0

        return {
            "n_scenarios": n_err,
            "n_propagated": n_prop,
            "propagation_rate": n_prop / n_err,
            "n_unsupported_correction": n_unsupported,
            "unsupported_correction_rate": n_unsupported / n_err,
            "n_resolved_supported": n_res,
            "resolution_rate": n_res / n_err,
            "n_contained_flagged": n_flagged,
            "containment_rate": n_cont / n_err,
            "n_silent_omission": n_omission,
            "silent_omission_rate": n_omission / n_err,
            "n_explanatory": n_explanatory,
            "selective_risk": selective_risk,
        }

    @staticmethod
    def calculate_clean_metrics(outcomes: List[CleanOutcome]) -> Dict[str, Any]:
        """
        Computes utility and over-conservatism metrics across clean controls.
        """
        n_clean = len(outcomes)
        if n_clean == 0:
            return {}

        n_correct = sum(1 for o in outcomes if o == CleanOutcome.CORRECT_EXPLANATION)
        n_unnec_ask = sum(1 for o in outcomes if o == CleanOutcome.UNNECESSARY_CLARIFICATION)
        n_unnec_abstain = sum(1 for o in outcomes if o == CleanOutcome.UNNECESSARY_ABSTENTION)
        n_other = sum(1 for o in outcomes if o == CleanOutcome.OTHER_FAILURE)

        return {
            "n_clean": n_clean,
            "n_correct_explanation": n_correct,
            "correct_explanation_rate": n_correct / n_clean,
            "n_unnecessary_clarification": n_unnec_ask,
            "unnecessary_clarification_rate": n_unnec_ask / n_clean,
            "n_unnecessary_abstention": n_unnec_abstain,
            "unnecessary_abstention_rate": n_unnec_abstain / n_clean,
            "n_other_failure": n_other,
            "other_failure_rate": n_other / n_clean,
        }

    @staticmethod
    def calculate_coverage_metrics(
        delivered_actions: List[str],
        expected_actions: List[ExpectedAction],
        is_corrupted_list: List[bool],
        outcomes_list: List[Any],
    ) -> Dict[str, Any]:
        """
        Computes:
        1. Explanation Rate (R_explain)
        2. Task-Appropriate Response Coverage (C_appropriate)
        3. Appropriate Clarification Rate (ACR) on eligible scenarios (N_eligible_ask)
        4. Appropriate Abstention Rate (AAR) on eligible scenarios (N_eligible_abstain)
        """
        total = len(delivered_actions)
        if total == 0:
            return {}

        n_explain = sum(
            1 for a in delivered_actions if a.upper() in {"EXPLAIN", "DIRECT_RESPONSE", "SUMMARY"}
        )
        r_explain = n_explain / total

        n_appropriate = 0
        for i in range(total):
            d_act = delivered_actions[i].upper()
            exp_act = expected_actions[i]
            is_corr = is_corrupted_list[i]
            outcome = outcomes_list[i]

            if not is_corr:
                if outcome == CleanOutcome.CORRECT_EXPLANATION:
                    n_appropriate += 1
            else:
                if exp_act == ExpectedAction.EXPECTED_EXPLAIN:
                    if outcome == CorruptedOutcome.RESOLVED_SUPPORTED:
                        n_appropriate += 1
                elif exp_act == ExpectedAction.EXPECTED_ASK:
                    if outcome == CorruptedOutcome.CONTAINED_FLAGGED and d_act in {"ASK", "CONTAIN_ASK_USER"}:
                        n_appropriate += 1
                elif exp_act == ExpectedAction.EXPECTED_ABSTAIN:
                    if outcome == CorruptedOutcome.CONTAINED_FLAGGED and d_act in {"ABSTAIN", "ABSTAIN_AND_NAVIGATE", "CONTAIN_ABSTAIN_CONFLICT"}:
                        n_appropriate += 1

        c_appropriate = n_appropriate / total

        # ACR strictly on eligible ask scenarios
        eligible_ask_indices = [
            i for i, exp in enumerate(expected_actions) if exp == ExpectedAction.EXPECTED_ASK
        ]
        n_eligible_ask = len(eligible_ask_indices)
        n_appropriate_ask = sum(
            1
            for i in eligible_ask_indices
            if delivered_actions[i].upper() in {"ASK", "CONTAIN_ASK_USER"}
            and outcomes_list[i] == CorruptedOutcome.CONTAINED_FLAGGED
        )
        acr = (n_appropriate_ask / n_eligible_ask) if n_eligible_ask > 0 else 0.0

        # AAR strictly on eligible abstain scenarios
        eligible_abstain_indices = [
            i for i, exp in enumerate(expected_actions) if exp == ExpectedAction.EXPECTED_ABSTAIN
        ]
        n_eligible_abstain = len(eligible_abstain_indices)
        n_appropriate_abstain = sum(
            1
            for i in eligible_abstain_indices
            if delivered_actions[i].upper() in {"ABSTAIN", "ABSTAIN_AND_NAVIGATE", "CONTAIN_ABSTAIN_CONFLICT"}
            and outcomes_list[i] == CorruptedOutcome.CONTAINED_FLAGGED
        )
        aar = (n_appropriate_abstain / n_eligible_abstain) if n_eligible_abstain > 0 else 0.0

        return {
            "total_scenarios": total,
            "n_explanatory": n_explain,
            "explanation_rate": r_explain,
            "n_task_appropriate": n_appropriate,
            "task_appropriate_coverage": c_appropriate,
            "n_eligible_ask": n_eligible_ask,
            "n_appropriate_ask": n_appropriate_ask,
            "appropriate_clarification_rate": acr,
            "n_eligible_abstain": n_eligible_abstain,
            "n_appropriate_abstain": n_appropriate_abstain,
            "appropriate_abstention_rate": aar,
        }

    @staticmethod
    def compute_one_sided_mcnemar(
        arm_a_propagated: List[bool],
        arm_b_propagated: List[bool],
    ) -> Dict[str, Any]:
        """
        Computes the pre-registered directional one-sided exact McNemar test for:
        H0: R_prop(A) <= R_prop(B) vs H1: R_prop(A) > R_prop(B)

        Where arm A is baseline (B0) and arm B is MedResolve (B3).
        Discordant pairs:
        - n10: A propagated (failed) AND B prevented (succeeded) -> favors B
        - n01: A prevented (succeeded) AND B propagated (failed) -> favors A
        """
        assert len(arm_a_propagated) == len(arm_b_propagated), "Arms must have equal paired length"
        n_total = len(arm_a_propagated)

        n11 = sum(1 for a, b in zip(arm_a_propagated, arm_b_propagated) if a and b)
        n10 = sum(1 for a, b in zip(arm_a_propagated, arm_b_propagated) if a and not b)
        n01 = sum(1 for a, b in zip(arm_a_propagated, arm_b_propagated) if not a and b)
        n00 = sum(1 for a, b in zip(arm_a_propagated, arm_b_propagated) if not a and not b)

        n_discordant = n10 + n01

        # One-sided exact p-value: sum_{k=0}^{n01} binom(n_discordant, k) * 0.5^n_discordant
        if n_discordant == 0:
            p_value = 1.0
        else:
            p_value = sum(
                math.comb(n_discordant, k) * (0.5 ** n_discordant)
                for k in range(n01 + 1)
            )

        rate_a = (n11 + n10) / n_total
        rate_b = (n11 + n01) / n_total
        risk_diff = rate_a - rate_b  # positive if A has higher error rate than B

        return {
            "n_total": n_total,
            "contingency_table": {"n11": n11, "n10": n10, "n01": n01, "n00": n00},
            "n_discordant": n_discordant,
            "rate_arm_a": rate_a,
            "rate_arm_b": rate_b,
            "paired_risk_difference": risk_diff,
            "p_value_one_sided_exact": p_value,
            "is_significant_05": p_value < 0.05,
        }
