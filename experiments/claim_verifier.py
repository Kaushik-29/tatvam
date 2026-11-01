"""
MedResolve — Claim-Level Verification Module
Phase 5 Component

Implements:
1. Sentence/assertion decomposition into atomic clinical claims.
2. Citation extraction and validity verification.
3. Reference literature verification (SUPPORTED_BY_SOURCE, CONTRADICTED_BY_SOURCE, INSUFFICIENT_EVIDENCE, OUT_OF_SCOPE).
4. Dual-axis verification: Patient Evidence Ledger Consistency vs Reference Support.
5. Detection of unconfirmed extraction reliance, missing findings, and ledger contradictions.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.evidence_ledger import (
    EvidenceItem,
    EvidenceLedger,
    EvidenceStatus,
    UserConfirmationStatus,
)
from experiments.knowledge_retriever import Passage, RetrievalResult

logger = logging.getLogger("MedResolve.ClaimVerifier")


class VerificationStatus(str, Enum):
    SUPPORTED_BY_SOURCE = "SUPPORTED_BY_SOURCE"
    CONTRADICTED_BY_SOURCE = "CONTRADICTED_BY_SOURCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ClaimType(str, Enum):
    GENERAL_MEDICAL_STATEMENT = "GENERAL_MEDICAL_STATEMENT"
    PATIENT_SPECIFIC_FINDING = "PATIENT_SPECIFIC_FINDING"


class PatientConsistencyStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    CONTRADICTED_BY_LEDGER = "CONTRADICTED_BY_LEDGER"
    FINDING_NOT_IN_LEDGER = "FINDING_NOT_IN_LEDGER"
    UNCONFIRMED_EXTRACTION = "UNCONFIRMED_EXTRACTION"
    NOT_APPLICABLE_GENERAL = "NOT_APPLICABLE_GENERAL"


@dataclass
class AtomicClaim:
    """Atomic clinical claim with dual-axis verification metadata."""
    claim_id: str
    claim_text: str
    claim_type: ClaimType
    cited_passage_ids: List[str] = field(default_factory=list)

    # Axis 1: Medical Reference Support
    reference_verification_status: VerificationStatus = VerificationStatus.INSUFFICIENT_EVIDENCE
    supporting_passage_ids: List[str] = field(default_factory=list)
    contradicting_passage_ids: List[str] = field(default_factory=list)
    reference_rationale: str = ""
    has_valid_citation: bool = False
    has_hallucinated_citation: bool = False

    # Axis 2: Patient Evidence Ledger Consistency
    patient_consistency_status: PatientConsistencyStatus = PatientConsistencyStatus.NOT_APPLICABLE_GENERAL
    patient_consistency_rationale: str = ""
    matched_ledger_concept: Optional[str] = None

    # Final response gating
    is_permitted_in_final: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type.value,
            "cited_passage_ids": self.cited_passage_ids,
            "is_permitted_in_final": self.is_permitted_in_final,
            "reference_verification": {
                "status": self.reference_verification_status.value,
                "supporting_passages": self.supporting_passage_ids,
                "contradicting_passages": self.contradicting_passage_ids,
                "rationale": self.reference_rationale,
                "has_valid_citation": self.has_valid_citation,
                "has_hallucinated_citation": self.has_hallucinated_citation,
            },
            "patient_consistency": {
                "status": self.patient_consistency_status.value,
                "rationale": self.patient_consistency_rationale,
                "matched_ledger_concept": self.matched_ledger_concept,
            },
        }


@dataclass
class VerificationReport:
    """Comprehensive claim-level verification report for an explanation."""
    total_claims: int
    general_claims_count: int
    patient_claims_count: int

    # Reference verification metrics
    supported_claims_count: int
    contradicted_claims_count: int
    insufficient_claims_count: int
    out_of_scope_claims_count: int
    evidence_support_rate: float
    unsupported_claim_rate: float
    general_medical_evidence_support_rate: float = 0.0
    general_medical_unsupported_rate: float = 0.0

    # Citation metrics
    citations_total_cited: int = 0
    citations_valid_count: int = 0
    citations_hallucinated_count: int = 0
    citation_correctness_rate: float = 1.0

    # Patient ledger consistency metrics
    ledger_consistent_count: int = 0
    ledger_contradicted_count: int = 0
    ledger_unconfirmed_reliance_count: int = 0
    ledger_missing_finding_count: int = 0
    patient_ledger_consistency_rate: float = 1.0
    overall_grounding_rate: float = 0.0

    # Detailed claims
    claims: List[AtomicClaim] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_claims": self.total_claims,
            "general_claims_count": self.general_claims_count,
            "patient_claims_count": self.patient_claims_count,
            "reference_support_metrics": {
                "supported": self.supported_claims_count,
                "contradicted": self.contradicted_claims_count,
                "insufficient": self.insufficient_claims_count,
                "out_of_scope": self.out_of_scope_claims_count,
                "evidence_support_rate": round(self.evidence_support_rate, 4),
                "general_medical_evidence_support_rate": round(self.general_medical_evidence_support_rate, 4),
                "unsupported_claim_rate": round(self.unsupported_claim_rate, 4),
                "general_medical_unsupported_rate": round(self.general_medical_unsupported_rate, 4),
            },
            "citation_metrics": {
                "total_citations": self.citations_total_cited,
                "valid_citations": self.citations_valid_count,
                "hallucinated_citations": self.citations_hallucinated_count,
                "citation_correctness_rate": round(self.citation_correctness_rate, 4),
            },
            "patient_ledger_metrics": {
                "consistent_findings": self.ledger_consistent_count,
                "ledger_contradictions": self.ledger_contradicted_count,
                "unconfirmed_extractions_relied_upon": self.ledger_unconfirmed_reliance_count,
                "missing_findings_claimed": self.ledger_missing_finding_count,
                "patient_ledger_consistency_rate": round(self.patient_ledger_consistency_rate, 4),
            },
            "overall_grounding_rate": round(self.overall_grounding_rate, 4),
            "claims": [c.to_dict() for c in self.claims],
        }


class ClaimVerifier:
    """
    Decomposes explanatory text into atomic clinical assertions and evaluates both:
    1. Reference Support (against retrieved reference passages)
    2. Patient Evidence Consistency (against EvidenceLedger)
    """

    CITATION_PATTERN = re.compile(r"\[([A-Z0-9_\-]+_P\d+)\]")

    PATIENT_MARKERS = [
        "patient", "reported", "reports", "presented", "presents with",
        "denies", "confirmed", "measured", "vitals", "history of",
        "complaining of", "feeling", "experienced", "symptoms include",
        "has noted", "denied"
    ]

    CONTRADICTION_PAIRS = [
        ("antibiotic", "minimal clinical benefit"),
        ("antibiotics are recommended", "minimal clinical benefit"),
        ("antibiotic therapy is recommended", "minimal clinical benefit"),
        ("antibiotic", "not recommended"),
        ("antibiotics are recommended", "not recommended"),
        ("antibiotic", "not indicated"),
        ("antibiotics are recommended", "routine antibiotics are not indicated"),
        ("emergency surgery", "conservative"),
        ("paper bag", "contraindicated"),
        ("delay epinephrine", "never delay"),
        ("antihistamines are first line", "epinephrine is first-line"),
    ]

    def decompose_text_to_claims(self, text: str) -> List[AtomicClaim]:
        """
        Decomposes explanatory text into atomic claims based on sentences and bullet items.
        Filters out non-claim formatting artifacts (markdown headers, horizontal rules, disclaimers).
        Normalizes trailing citations so they remain attached to their originating sentence.
        """
        cleaned_lines = []
        for line in text.splitlines():
            l = line.strip()
            # Strip markdown headers (e.g. ## Title, ### 1. Title), rules, table borders, and disclaimers
            if not l or l.startswith("#") or l.startswith("---") or l.startswith("***") or l.startswith("|"):
                continue
            if l.startswith("*Disclaimer") or "disclaimer:" in l.lower() or "not a diagnostic determination" in l.lower():
                continue
            # If line is just a sub-section title like "1. Documented Patient Observations" or "Clinical Reference Guidance"
            if re.match(r"^(\d+\.\s*)?[A-Z][a-zA-Z\s&]{4,35}$", l) and not l.endswith("."):
                continue
            cleaned_lines.append(l)

        content = "\n".join(cleaned_lines)
        # Pull trailing citations inside the sentence boundary: e.g. "sentence. [DOC_P01]" -> "sentence [DOC_P01]."
        content = re.sub(r"\.\s*(\[[A-Z0-9_\-]+\])", r" \1.", content)

        # Split on sentence boundaries
        raw_sentences = re.split(r"(?<=[.!?])\s+", content)
        claims = []
        claim_idx = 1

        for raw in raw_sentences:
            cleaned = raw.strip()
            if not cleaned or len(cleaned.split()) < 3 or len(cleaned) < 15:
                continue
            # Filter isolated citations
            if re.match(r"^[\[\(][A-Z0-9_\-]+[\]\)]\.?$", cleaned):
                continue
            # Filter pure headers that slipped through
            if any(h in cleaned for h in ["Patient Observations", "Reference Guidance", "Safety Guidance & Limitations"]):
                if len(cleaned.split()) <= 4:
                    continue

            cited_ids = self.CITATION_PATTERN.findall(cleaned)

            is_patient = any(marker in cleaned.lower() for marker in self.PATIENT_MARKERS)
            claim_type = ClaimType.PATIENT_SPECIFIC_FINDING if is_patient else ClaimType.GENERAL_MEDICAL_STATEMENT

            claim = AtomicClaim(
                claim_id=f"CLAIM_{claim_idx:03d}",
                claim_text=cleaned,
                claim_type=claim_type,
                cited_passage_ids=cited_ids,
            )
            claims.append(claim)
            claim_idx += 1

        return claims

    def verify_claim_reference_support(
        self,
        claim: AtomicClaim,
        retrieved_passages: List[Passage],
    ) -> AtomicClaim:
        """
        Evaluates whether a claim is supported or contradicted by the retrieved reference passages.
        Verifies citation integrity.
        """
        passage_map = {p.passage_id: p for p in retrieved_passages}
        claim_lower = claim.claim_text.lower()

        # Check for citation hallucinations
        if claim.cited_passage_ids:
            hallucinated = [pid for pid in claim.cited_passage_ids if pid not in passage_map]
            valid_pids = [pid for pid in claim.cited_passage_ids if pid in passage_map]

            if hallucinated:
                claim.has_hallucinated_citation = True
                claim.reference_verification_status = VerificationStatus.INSUFFICIENT_EVIDENCE
                claim.reference_rationale = f"Cited passage(s) {', '.join(hallucinated)} do not exist in retrieved material."
                return claim

            claim.has_valid_citation = True
            passages_to_check = [passage_map[pid] for pid in valid_pids]
        else:
            passages_to_check = retrieved_passages

        if not passages_to_check:
            claim.reference_verification_status = VerificationStatus.INSUFFICIENT_EVIDENCE
            claim.reference_rationale = "No retrieved reference passages available to verify claim."
            return claim

        # Check for direct contradictions
        for p in passages_to_check:
            p_text_lower = p.text.lower()
            for assertion_term, contradiction_term in self.CONTRADICTION_PAIRS:
                if assertion_term in claim_lower and contradiction_term in p_text_lower:
                    claim.reference_verification_status = VerificationStatus.CONTRADICTED_BY_SOURCE
                    claim.contradicting_passage_ids.append(p.passage_id)
                    claim.reference_rationale = (
                        f"Claim contradicts reference [{p.passage_id}]: text asserts '{assertion_term}' "
                        f"whereas guideline states '{contradiction_term}'."
                    )
                    return claim

        # Token overlap & semantic entailment check
        claim_tokens = set(re.findall(r"\b[a-z]{3,}\b", claim_lower))
        stop_words = {"this", "that", "with", "from", "have", "been", "patient", "presents", "about", "which", "there", "their", "after", "should", "could", "would"}
        informative_tokens = claim_tokens - stop_words

        supporting = []
        for p in passages_to_check:
            p_tokens = set(re.findall(r"\b[a-z]{3,}\b", p.text.lower()))
            overlap = informative_tokens.intersection(p_tokens)
            overlap_ratio = len(overlap) / len(informative_tokens) if informative_tokens else 0.0

            # If strong clinical keyword overlap (> 35% of informative terms), passage supports the claim
            if overlap_ratio >= 0.35 or len(overlap) >= 4:
                supporting.append(p.passage_id)

        if supporting:
            claim.reference_verification_status = VerificationStatus.SUPPORTED_BY_SOURCE
            claim.supporting_passage_ids = supporting
            claim.reference_rationale = f"Supported by retrieved reference passage(s): {', '.join(supporting)}."
        else:
            claim.reference_verification_status = VerificationStatus.INSUFFICIENT_EVIDENCE
            claim.reference_rationale = "Retrieved passages contain insufficient evidence to substantiate claim assertions."

        return claim

    def verify_claim_ledger_consistency(
        self,
        claim: AtomicClaim,
        ledger: Optional[EvidenceLedger] = None,
    ) -> AtomicClaim:
        """
        Evaluates whether a patient-specific claim is consistent with the patient's EvidenceLedger.
        Guarantees that general medical statements do not trigger spurious patient contradictions,
        and ensures unconfirmed low-confidence extractions are flagged.
        """
        if ledger is None or claim.claim_type == ClaimType.GENERAL_MEDICAL_STATEMENT:
            claim.patient_consistency_status = PatientConsistencyStatus.NOT_APPLICABLE_GENERAL
            claim.patient_consistency_rationale = (
                "General medical fact; not an assertion of specific patient finding."
                if claim.claim_type == ClaimType.GENERAL_MEDICAL_STATEMENT
                else "No patient evidence ledger provided for consistency validation."
            )
            return claim

        claim_lower = claim.claim_text.lower()

        # Find matching ledger concepts by concept name or keyword
        matched_items = []
        for item in ledger.items:
            c_name = (item.concept_name_en or item.concept).lower()
            tokens = [t for t in re.findall(r"\b[a-z]{3,}\b", c_name) if t not in {"you", "have", "feel", "with", "does"}]
            if any(t in claim_lower for t in tokens):
                matched_items.append(item)

        if not matched_items:
            claim.patient_consistency_status = PatientConsistencyStatus.FINDING_NOT_IN_LEDGER
            claim.patient_consistency_rationale = "Patient finding asserted in explanation does not appear in recorded ledger."
            return claim

        # Evaluate matched items for status, confirmation, and contradictions
        for item in matched_items:
            claim.matched_ledger_concept = item.concept
            # Check 1: Unconfirmed extraction reliance
            if (
                item.extraction_confidence < 0.70
                and item.user_confirmation_status == UserConfirmationStatus.UNCONFIRMED
            ):
                claim.patient_consistency_status = PatientConsistencyStatus.UNCONFIRMED_EXTRACTION
                claim.patient_consistency_rationale = (
                    f"Claim relies on concept '{item.concept}' which has low extraction confidence "
                    f"({item.extraction_confidence:.2f}) and remains UNCONFIRMED by patient."
                )
                return claim

            # Check 2: Contradiction with ledger evidence status
            asserts_present = not any(neg in claim_lower for neg in ["no ", "not ", "denies", "absent", "without"])
            if item.evidence_status == EvidenceStatus.ABSENT and asserts_present:
                claim.patient_consistency_status = PatientConsistencyStatus.CONTRADICTED_BY_LEDGER
                claim.patient_consistency_rationale = (
                    f"Claim asserts presence of '{item.concept_name_en or item.concept}', "
                    "but patient evidence ledger explicitly records this finding as ABSENT."
                )
                return claim
            elif item.evidence_status == EvidenceStatus.PRESENT and not asserts_present:
                claim.patient_consistency_status = PatientConsistencyStatus.CONTRADICTED_BY_LEDGER
                claim.patient_consistency_rationale = (
                    f"Claim asserts absence of '{item.concept_name_en or item.concept}', "
                    "but patient evidence ledger explicitly records this finding as PRESENT."
                )
                return claim

        claim.patient_consistency_status = PatientConsistencyStatus.CONSISTENT
        claim.patient_consistency_rationale = "Claim findings are consistent with confirmed patient evidence ledger items."
        return claim

    def verify_explanation(
        self,
        explanation_text: str,
        retrieved_passages: List[Passage],
        ledger: Optional[EvidenceLedger] = None,
    ) -> VerificationReport:
        """Runs end-to-end claim decomposition and dual-axis verification."""
        claims = self.decompose_text_to_claims(explanation_text)

        supp_cnt = 0
        contra_cnt = 0
        insuff_cnt = 0
        oos_cnt = 0

        tot_citations = 0
        valid_citations = 0
        halluc_citations = 0

        ledg_cons = 0
        ledg_contra = 0
        ledg_unconf = 0
        ledg_miss = 0

        gen_cnt = 0
        pat_cnt = 0
        gen_supp_cnt = 0
        gen_contra_cnt = 0
        gen_insuff_cnt = 0
        pat_cons_cnt = 0

        verified_claims = []
        for c in claims:
            is_gen = (c.claim_type == ClaimType.GENERAL_MEDICAL_STATEMENT)
            if is_gen:
                gen_cnt += 1
            else:
                pat_cnt += 1

            # Axis 1: Reference support
            c = self.verify_claim_reference_support(c, retrieved_passages)
            if c.reference_verification_status == VerificationStatus.SUPPORTED_BY_SOURCE:
                supp_cnt += 1
                if is_gen:
                    gen_supp_cnt += 1
            elif c.reference_verification_status == VerificationStatus.CONTRADICTED_BY_SOURCE:
                contra_cnt += 1
                if is_gen:
                    gen_contra_cnt += 1
            elif c.reference_verification_status == VerificationStatus.OUT_OF_SCOPE:
                oos_cnt += 1
            else:
                insuff_cnt += 1
                if is_gen:
                    gen_insuff_cnt += 1

            # Citation stats
            if c.cited_passage_ids:
                tot_citations += len(c.cited_passage_ids)
                if c.has_valid_citation and not c.has_hallucinated_citation:
                    valid_citations += len(c.cited_passage_ids)
                if c.has_hallucinated_citation:
                    halluc_citations += len(c.cited_passage_ids)

            # Axis 2: Patient consistency
            c = self.verify_claim_ledger_consistency(c, ledger)
            if c.patient_consistency_status == PatientConsistencyStatus.CONSISTENT:
                ledg_cons += 1
                if not is_gen:
                    pat_cons_cnt += 1
            elif c.patient_consistency_status == PatientConsistencyStatus.CONTRADICTED_BY_LEDGER:
                ledg_contra += 1
            elif c.patient_consistency_status == PatientConsistencyStatus.UNCONFIRMED_EXTRACTION:
                ledg_unconf += 1
            elif c.patient_consistency_status == PatientConsistencyStatus.FINDING_NOT_IN_LEDGER:
                ledg_miss += 1

            # Gating: determine if permitted in final explanation
            is_permitted = True
            if c.reference_verification_status == VerificationStatus.CONTRADICTED_BY_SOURCE:
                is_permitted = False
            if c.has_hallucinated_citation:
                is_permitted = False
            if c.patient_consistency_status == PatientConsistencyStatus.CONTRADICTED_BY_LEDGER:
                is_permitted = False
            c.is_permitted_in_final = is_permitted

            verified_claims.append(c)

        total_claims = len(claims)
        support_rate = (supp_cnt / total_claims) if total_claims > 0 else 0.0
        unsupported_rate = ((insuff_cnt + contra_cnt) / total_claims) if total_claims > 0 else 0.0
        citation_acc = (valid_citations / tot_citations) if tot_citations > 0 else 1.0

        # Refined Dual-Axis Metrics (Compatible Denominators)
        gen_support_rate = (gen_supp_cnt / gen_cnt) if gen_cnt > 0 else 1.0
        gen_unsupp_rate = ((gen_contra_cnt + gen_insuff_cnt) / gen_cnt) if gen_cnt > 0 else 0.0
        pat_consistency_rate = (pat_cons_cnt / pat_cnt) if pat_cnt > 0 else 1.0
        total_evaluable = gen_cnt + pat_cnt
        overall_grounding = ((gen_supp_cnt + pat_cons_cnt) / total_evaluable) if total_evaluable > 0 else 0.0

        return VerificationReport(
            total_claims=total_claims,
            general_claims_count=gen_cnt,
            patient_claims_count=pat_cnt,
            supported_claims_count=supp_cnt,
            contradicted_claims_count=contra_cnt,
            insufficient_claims_count=insuff_cnt,
            out_of_scope_claims_count=oos_cnt,
            evidence_support_rate=support_rate,
            unsupported_claim_rate=unsupported_rate,
            general_medical_evidence_support_rate=gen_support_rate,
            general_medical_unsupported_rate=gen_unsupp_rate,
            citations_total_cited=tot_citations,
            citations_valid_count=valid_citations,
            citations_hallucinated_count=halluc_citations,
            citation_correctness_rate=citation_acc,
            ledger_consistent_count=ledg_cons,
            ledger_contradicted_count=ledg_contra,
            ledger_unconfirmed_reliance_count=ledg_unconf,
            ledger_missing_finding_count=ledg_miss,
            patient_ledger_consistency_rate=pat_consistency_rate,
            overall_grounding_rate=overall_grounding,
            claims=verified_claims,
        )
