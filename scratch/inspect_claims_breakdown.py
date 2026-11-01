import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.evidence_ledger import (
    EvidenceItem, EvidenceLedger, EvidenceStatus, SourceType, UserConfirmationStatus, ExtractionMethod
)
from experiments.knowledge_retriever import MedicalKnowledgeBase
from experiments.claim_verifier import ClaimVerifier
from experiments.rag_generator import EvidenceGroundedGenerator
import json

kb = MedicalKnowledgeBase()
kb.load_and_ingest()
kb.build_lexical_index()
kb.build_dense_index()

verifier = ClaimVerifier()
generator = EvidenceGroundedGenerator(verifier=verifier)

# Run on Scenario 1: GERD Clean
ledger = EvidenceLedger(patient_case_id="rag_sc_01_gerd", metadata={"age": 45, "sex": "M"})
ledger.add_item(EvidenceItem(
    evidence_id="sc1_ev1", patient_case_id="rag_sc_01_gerd", concept="E_173",
    concept_name_en="Retrosternal burning sensation after meals", normalized_value=True,
    source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
    extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
    user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.PRESENT
))

query = "Patient with retrosternal burning after meals and acid taste in mouth"
retrieved = kb.search_hybrid(query, top_k=3)

res = generator.generate_explanation(
    ledger=ledger,
    retrieved_results=retrieved,
    candidate_differentials=[{"condition": "Gastroesophageal Reflux Disease", "rank": 1}],
    system_mode="B1_RAG",
)

print("GENERATED TEXT:\n", res.generated_text)
print("\n" + "="*80)
vr = res.verification_report
print("VERIFICATION REPORT SUMMARY:")
print(f"Total claims: {vr['total_claims']}")
print(f"Supported claims: {vr['reference_support_metrics']['supported']}")
print(f"Contradicted claims: {vr['reference_support_metrics']['contradicted']}")
print(f"Insufficient claims: {vr['reference_support_metrics']['insufficient']}")
print(f"Evidence Support Rate: {vr['reference_support_metrics']['evidence_support_rate']}")
print(f"Unsupported Claim Rate: {vr['reference_support_metrics']['unsupported_claim_rate']}")
print("\nCLAIMS BREAKDOWN:")
for idx, c in enumerate(vr['claims'], 1):
    print(f"[{idx}] Type: {c['claim_type']} | Ref Status: {c['reference_verification']['status']} | Patient Status: {c['patient_consistency']['status']}")
    print(f"    Text: {c['claim_text']}")
    print(f"    Rationale: {c['reference_verification']['rationale']}")
