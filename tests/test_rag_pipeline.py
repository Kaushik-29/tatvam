"""
MedResolve — Phase 5 Test Suite: Medical RAG & Evidence Verification Pipeline

Covers:
1. Document provenance preservation and schema conformance.
2. Retrieval result source IDs, citations, and scores.
3. Citation integrity and hallucinated citation detection.
4. Empty or inadequate retrieval handling (insufficient evidence detection).
5. Unsupported and contradicted claim identification.
6. Verification between reference claims and patient evidence ledger (unconfirmed extractions & contradictions).
7. Correct abstention on out-of-domain presentations.
8. Preservation of existing emergency override precedence over RAG.
"""

from pathlib import Path
import sys
import pytest
import numpy as np

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
    UserConfirmationStatus,
    ClinicianOpinionItem,
)
from experiments.knowledge_retriever import (
    MedicalKnowledgeBase,
    Passage,
    PassageMetadata,
    RetrievalResult,
)
from experiments.claim_verifier import (
    ClaimVerifier,
    ClaimType,
    VerificationStatus,
    PatientConsistencyStatus,
)
from experiments.rag_generator import EvidenceGroundedGenerator
from experiments.action_policy import (
    SelectiveActionPolicy,
    PolicyAction,
)


@pytest.fixture(scope="module")
def knowledge_base():
    """Initializes and returns MedicalKnowledgeBase instance."""
    kb = MedicalKnowledgeBase(knowledge_base_dir="data/knowledge_base")
    kb.load_and_ingest()
    kb.build_lexical_index()
    kb.build_dense_index()
    return kb


@pytest.fixture
def claim_verifier():
    """Returns ClaimVerifier instance."""
    return ClaimVerifier()


@pytest.fixture
def rag_generator(claim_verifier):
    """Returns EvidenceGroundedGenerator instance."""
    return EvidenceGroundedGenerator(verifier=claim_verifier)


# =============================================================================
# Test 1: Document Provenance Preservation
# =============================================================================
def test_document_provenance_preservation(knowledge_base):
    """Verifies that all ingested passages retain full source provenance metadata."""
    passages = knowledge_base.passages
    assert len(passages) >= 20, "Knowledge base should contain at least 20 passages."

    required_meta_keys = [
        "document_id",
        "document_title",
        "document_organization",
        "source_url",
        "publication_date",
        "access_date",
        "license_or_reuse_conditions",
        "document_type",
        "version",
    ]

    for p in passages:
        meta = p.metadata
        assert p.passage_id.startswith(meta.document_id), f"Passage ID {p.passage_id} must start with doc ID {meta.document_id}"
        assert len(p.text.strip()) > 30, f"Passage {p.passage_id} text is too short."

        meta_dict = meta.to_dict()
        for key in required_meta_keys:
            val = meta_dict.get(key)
            assert val is not None and str(val).strip() != "", f"Missing mandatory provenance field '{key}' in passage {p.passage_id}"

        # Verify full reference citation format
        assert meta.document_title in p.full_reference_citation
        assert meta.document_organization in p.full_reference_citation


# =============================================================================
# Test 2: Retrieval Result Source IDs, Citations, and Scores
# =============================================================================
def test_retrieval_result_source_ids(knowledge_base):
    """Verifies retrieval results contain accurate source IDs, passage text, and scores."""
    query = "heartburn with acid regurgitation exacerbated by recumbency"
    results = knowledge_base.search_dense(query, top_k=2)

    assert len(results) == 2
    top_res = results[0]
    assert isinstance(top_res, RetrievalResult)
    assert top_res.passage.passage_id.startswith("DOC_MOHFW_GERD_2019")
    assert top_res.score > 0.40
    assert top_res.rank == 1
    assert "DOC_MOHFW_GERD_2019" in top_res.citation

    # Hybrid retrieval test
    hybrid_res = knowledge_base.search_hybrid(query, top_k=2)
    assert len(hybrid_res) == 2
    assert hybrid_res[0].dense_score is not None
    assert hybrid_res[0].dense_score > 0.40


# =============================================================================
# Test 3: Citation Integrity and Hallucination Detection
# =============================================================================
def test_citation_integrity_and_hallucination_detection(knowledge_base, claim_verifier):
    """Tests that valid citations are verified and fabricated/hallucinated citations are caught."""
    passages = knowledge_base.passages[:2]

    # Valid citation
    valid_text = (
        f"According to clinical reference guidelines [{passages[0].passage_id}], "
        f"{passages[0].text[:80]} [{passages[0].passage_id}]."
    )
    v_report_valid = claim_verifier.verify_explanation(valid_text, passages)
    assert v_report_valid.citations_total_cited >= 1
    assert v_report_valid.citations_hallucinated_count == 0
    assert v_report_valid.citation_correctness_rate == 1.0

    # Hallucinated citation
    fake_text = "Urgent endoscopic evaluation is mandatory within 1 hour [DOC_FICTIONAL_P99]."
    v_report_fake = claim_verifier.verify_explanation(fake_text, passages)
    assert v_report_fake.citations_hallucinated_count == 1
    assert v_report_fake.citation_correctness_rate < 1.0
    assert v_report_fake.claims[0].has_hallucinated_citation is True


# =============================================================================
# Test 4: Empty or Inadequate Retrieval Handling
# =============================================================================
def test_empty_or_inadequate_retrieval(rag_generator):
    """Verifies that empty or inadequate retrieval triggers is_insufficient_evidence flag."""
    ledger = EvidenceLedger(patient_case_id="empty_retrieval_case")
    ledger.add_item(EvidenceItem(
        evidence_id="ev_01", patient_case_id="empty_retrieval_case", concept="E_01",
        concept_name_en="Vague fatigue", normalized_value=True,
        source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.PRESENT
    ))

    # Empty retrieval
    res_empty = rag_generator.generate_explanation(
        ledger=ledger, retrieved_results=[], system_mode="B1_RAG"
    )
    assert res_empty.is_insufficient_evidence is True
    assert "INSUFFICIENT RETRIEVED EVIDENCE" in res_empty.generated_text

    # Low semantic score retrieval
    dummy_meta = PassageMetadata(
        passage_id="DOC_TEST_P01",
        document_id="DOC_TEST",
        document_title="Test",
        document_organization="Org",
        section_heading="Test Section",
        source_url="http://test",
        publication_date="2020",
        date_uncertainty_note=None,
        license_or_reuse_conditions="Public",
        document_type="Guideline",
        version="1.0",
        access_date="2026-10-15",
    )
    dummy_passage = Passage(passage_id="DOC_TEST_P01", text="Unrelated text.", metadata=dummy_meta)
    low_res = [RetrievalResult(
        passage=dummy_passage, score=0.20, rank=1, retrieval_method="dense_faiss", dense_score=0.20
    )]

    assert EvidenceGroundedGenerator.is_retrieval_sufficient(low_res) is False
    res_low = rag_generator.generate_explanation(
        ledger=ledger, retrieved_results=low_res, system_mode="B1_RAG"
    )
    assert res_low.is_insufficient_evidence is True


# =============================================================================
# Test 5: Unsupported and Contradicted Claims
# =============================================================================
def test_unsupported_and_contradicted_claims(knowledge_base, claim_verifier):
    """Tests identification of unsupported claims and direct reference contradictions."""
    bronchitis_passages = [p for p in knowledge_base.passages if "BRONCHITIS" in p.passage_id]
    assert len(bronchitis_passages) > 0

    # Contradicted statement: asserting routine antibiotics for bronchitis
    contradicted_claim = "Routine antibiotic therapy is recommended for all acute bronchitis presentations."
    v_report = claim_verifier.verify_explanation(contradicted_claim, bronchitis_passages)

    assert v_report.contradicted_claims_count >= 1
    assert any(
        c.reference_verification_status == VerificationStatus.CONTRADICTED_BY_SOURCE
        for c in v_report.claims
    )

    # Completely ungrounded claim with no passage support
    ungrounded_claim = "High dose intravenous immunoglobulin must be infused every six hours."
    v_report_ungrounded = claim_verifier.verify_explanation(ungrounded_claim, bronchitis_passages)
    assert any(
        c.reference_verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE
        for c in v_report_ungrounded.claims
    )


# =============================================================================
# Test 6: Reference Claims vs Patient Evidence Ledger Consistency
# =============================================================================
def test_conflicts_between_reference_claims_and_patient_evidence(claim_verifier):
    """Tests that claims asserting absent patient findings or relying on unconfirmed extractions are caught."""
    ledger = EvidenceLedger(patient_case_id="patient_conflict_case")
    # Absent finding
    ledger.add_item(EvidenceItem(
        evidence_id="ev_01", patient_case_id="patient_conflict_case", concept="E_CHEST_PAIN",
        concept_name_en="Retrosternal chest pain", normalized_value=False,
        source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.ABSENT
    ))
    # Low-confidence unconfirmed extraction
    ledger.add_item(EvidenceItem(
        evidence_id="ev_02", patient_case_id="patient_conflict_case", concept="E_DYSPHAGIA",
        concept_name_en="Difficulty swallowing food", normalized_value=True,
        source_type=SourceType.EHR_EXTRACTED_NOTE, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.OCR_EXTRACTION, extraction_confidence=0.51,
        user_confirmation_status=UserConfirmationStatus.UNCONFIRMED, evidence_status=EvidenceStatus.PRESENT
    ))

    # Claim asserts chest pain presence (contradicts ledger)
    claim_contra = "The patient presents with retrosternal chest pain."
    report_contra = claim_verifier.verify_explanation(claim_contra, [], ledger)
    assert report_contra.ledger_contradicted_count >= 1

    # Claim relies on unconfirmed extraction
    claim_unconf = "The patient has difficulty swallowing food according to the report."
    report_unconf = claim_verifier.verify_explanation(claim_unconf, [], ledger)
    assert report_unconf.ledger_unconfirmed_reliance_count >= 1

    # General medical statement does NOT trigger spurious patient contradiction
    claim_general = "GERD is commonly managed with proton pump inhibitors."
    report_gen = claim_verifier.verify_explanation(claim_general, [], ledger)
    assert report_gen.ledger_contradicted_count == 0


# =============================================================================
# Test 7: Correct Abstention When Evidence Is Insufficient
# =============================================================================
def test_correct_abstention_on_out_of_domain(knowledge_base, rag_generator):
    """Tests that out-of-domain queries properly trigger insufficient evidence notice."""
    ledger = EvidenceLedger(patient_case_id="ood_case")
    ledger.add_item(EvidenceItem(
        evidence_id="ev_01", patient_case_id="ood_case", concept="E_01",
        concept_name_en="Eye pain and floaters", normalized_value=True,
        source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.PRESENT
    ))

    ood_query = "surgical vitrectomy technique for detached retina"
    retrieved = knowledge_base.search_hybrid(ood_query, top_k=2)

    # Top dense score should be low (< 0.50)
    assert retrieved[0].dense_score is not None
    assert retrieved[0].dense_score < 0.50

    res = rag_generator.generate_explanation(ledger, retrieved, system_mode="B2_RAG_Verified")
    assert res.is_insufficient_evidence is True
    assert "INSUFFICIENT RETRIEVED EVIDENCE" in res.generated_text


# =============================================================================
# Test 8: Preservation of Emergency Override Precedence
# =============================================================================
def test_preservation_of_emergency_override_precedence(knowledge_base, rag_generator):
    """Verifies that acute emergency red flags trigger EMERGENCY_OVERRIDE and strictly block RAG."""
    policy = SelectiveActionPolicy()

    emergency_ledger = EvidenceLedger(patient_case_id="emergency_case")
    # Add emergency red flags: documented loss of consciousness / syncope (E_159) and acute stridor (E_194)
    emergency_ledger.add_item(EvidenceItem(
        evidence_id="em_01", patient_case_id="emergency_case", concept="E_159",
        concept_name_en="Sudden loss of consciousness syncope", normalized_value=True,
        source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.PRESENT
    ))
    emergency_ledger.add_item(EvidenceItem(
        evidence_id="em_02", patient_case_id="emergency_case", concept="E_194",
        concept_name_en="Acute inspiratory stridor and airway suffocation", normalized_value=True,
        source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.PRESENT
    ))

    probs = np.zeros(49)
    probs[0] = 0.99  # Even with high classifier confidence!

    decision = policy.execute_policy_with_rag(
        ledger=emergency_ledger,
        probabilities=probs,
        kb=knowledge_base,
        rag_generator=rag_generator,
    )

    assert decision.selected_action == PolicyAction.EMERGENCY_OVERRIDE
    assert decision.is_emergency_override is True
    # RAG explanation must NEVER be attached to an emergency override
    assert decision.explanation_summary is None or "grounded_rag_explanation" not in decision.explanation_summary


# =============================================================================
# Phase 5.1 Test 9: Knowledge Base v2 Provenance and Specific Reuse Licences
# =============================================================================
def test_kb_v2_provenance_and_licensing():
    """
    Verifies that Knowledge Base v2 contains 10 documents, 42 passages,
    and explicitly verifies that StatPearls documents are NOT marked as Public Domain.
    """
    import json
    manifest_path = Path("data/knowledge_base_v2/knowledge_manifest.json")
    assert manifest_path.exists(), "KB v2 manifest must exist."

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["version"] == "2.0.0"
    assert manifest["total_documents"] == 10
    assert manifest["total_passages"] == 42
    assert len(manifest["documents"]) == 10

    # StatPearls license check
    statpearls_docs = [d for d in manifest["documents"] if "STATPEARLS" in d["document_id"]]
    assert len(statpearls_docs) == 2, "Expected 2 StatPearls documents."

    for d in statpearls_docs:
        lic = d["license_or_reuse_conditions"].lower()
        assert "public domain" not in lic or "not public domain" in lic, (
            f"StatPearls document {d['document_id']} must NOT be claimed as public domain!"
        )
        assert "statpearls publishing" in lic or "copyright" in lic
        assert d["source_url"].startswith("https://www.ncbi.nlm.nih.gov/books/")


# =============================================================================
# Phase 5.1 Test 10: Clean Claim Decomposition (Eliminating Decomposition Artifacts)
# =============================================================================
def test_clean_claim_decomposition(claim_verifier):
    """
    Verifies that markdown headers, rules, and isolated citations are not treated as atomic claims,
    and trailing citations remain cleanly attached inside sentences.
    """
    text = (
        "## Evidence-Grounded Health Assessment Summary\n\n"
        "### 1. Documented Patient Observations\n"
        "The patient presents with verified findings: Retrosternal burning sensation.\n"
        "Pertinent negatives documented: None recorded.\n\n"
        "### 2. Clinical Reference Guidance\n"
        "According to clinical reference guidelines, gastroesophageal reflux disease is characterized by pyrosis [DOC_MOHFW_GERD_2019_P001].\n\n"
        "### 3. Safety Guidance & Limitations\n"
        "If acute red flags develop, immediate in-person medical evaluation is required.\n\n"
        "*Disclaimer: MedResolve provides bounded evidence summaries for patient navigation.*"
    )

    claims = claim_verifier.decompose_text_to_claims(text)
    claim_texts = [c.claim_text for c in claims]

    # No markdown headers should exist as claims
    assert not any("###" in t or "##" in t for t in claim_texts)
    assert not any(t.startswith("1. Documented") for t in claim_texts)
    assert not any(t.startswith("Clinical Reference Guidance") for t in claim_texts)
    assert not any(t.startswith("Safety Guidance") for t in claim_texts)
    assert not any("Disclaimer:" in t for t in claim_texts)

    # Citation should NOT be split as an orphan claim
    assert not any(t == "[DOC_MOHFW_GERD_2019_P001]" for t in claim_texts)
    assert not any(t == "[DOC_MOHFW_GERD_2019_P001]." for t in claim_texts)

    # Trailing citation must be attached to the sentence
    guideline_claim = [c for c in claims if "DOC_MOHFW_GERD_2019_P001" in c.claim_text or "DOC_MOHFW_GERD_2019_P001" in c.cited_passage_ids]
    assert len(guideline_claim) >= 1
    assert "gastroesophageal reflux" in guideline_claim[0].claim_text.lower()


# =============================================================================
# Phase 5.1 Test 11: Dual-Axis Metrics with Compatible Denominators
# =============================================================================
def test_dual_axis_metrics_compatible_denominators(claim_verifier, knowledge_base):
    """
    Verifies that general medical evidence support evaluates only general claims,
    and patient ledger consistency evaluates only patient-specific claims.
    """
    gerd_passages = [p for p in knowledge_base.passages if "GERD" in p.passage_id]

    ledger = EvidenceLedger(patient_case_id="dual_axis_test")
    ledger.add_item(EvidenceItem(
        evidence_id="ev_01", patient_case_id="dual_axis_test", concept="E_173",
        concept_name_en="Retrosternal burning after meals", normalized_value=True,
        source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.PRESENT
    ))

    text = (
        "The patient presents with documented findings: Retrosternal burning after meals.\n"
        f"According to clinical reference guidelines [{gerd_passages[0].passage_id}], {gerd_passages[0].text[:60]} [{gerd_passages[0].passage_id}]."
    )

    report = claim_verifier.verify_explanation(text, gerd_passages, ledger)

    assert report.total_claims >= 2
    assert report.general_claims_count >= 1
    assert report.patient_claims_count >= 1

    # Compatible denominators
    assert report.general_medical_evidence_support_rate == 1.0, "All general medical claims should be supported by retrieved passage."
    assert report.general_medical_unsupported_rate == 0.0
    assert report.patient_ledger_consistency_rate == 1.0, "All patient claims should match ledger items."
    assert report.overall_grounding_rate == 1.0


# =============================================================================
# Phase 5.1 Test 12: System B3 Selective Action Policy Precedence
# =============================================================================
def test_system_b3_policy_precedence(rag_generator, knowledge_base):
    """Verifies that System B3 executes selective action policy prior to generating explanation."""
    # Emergency scenario
    emerg_ledger = EvidenceLedger(patient_case_id="b3_emerg")
    emerg_ledger.add_item(EvidenceItem(
        evidence_id="em_01", patient_case_id="b3_emerg", concept="E_194",
        concept_name_en="Inspiratory stridor", normalized_value=True,
        source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.PRESENT
    ))

    res_emerg = rag_generator.generate_explanation(emerg_ledger, [], system_mode="B3_RAG_Policy_Integrated")
    assert "EMERGENCY SAFETY OVERRIDE" in res_emerg.generated_text
    assert res_emerg.policy_decision is not None
    assert res_emerg.policy_decision["is_emergency_override"] is True
    assert res_emerg.execution_engine == "policy_override"

    # Unconfirmed extraction scenario
    unconf_ledger = EvidenceLedger(patient_case_id="b3_unconf")
    unconf_ledger.add_item(EvidenceItem(
        evidence_id="unc_01", patient_case_id="b3_unconf", concept="E_DYSPHAGIA",
        concept_name_en="Difficulty swallowing food", normalized_value=True,
        source_type=SourceType.EHR_EXTRACTED_NOTE, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.OCR_EXTRACTION, extraction_confidence=0.52,
        user_confirmation_status=UserConfirmationStatus.UNCONFIRMED, evidence_status=EvidenceStatus.PRESENT
    ))

    res_unconf = rag_generator.generate_explanation(unconf_ledger, [], system_mode="B3_RAG_Policy_Integrated")
    assert "Clarification Required" in res_unconf.generated_text
    assert res_unconf.policy_decision["selected_action"] == "ASK"
    assert res_unconf.execution_engine == "rule_guardrail"

    # Material conflict scenario
    conf_ledger = EvidenceLedger(patient_case_id="b3_conflict")
    conf_ledger.add_item(EvidenceItem(
        evidence_id="conf_ev", patient_case_id="b3_conflict", concept="E_CHEST_PAIN",
        concept_name_en="Chest discomfort", normalized_value=True,
        source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.PRESENT
    ))
    conf_ledger.add_opinion(ClinicianOpinionItem(
        opinion_id="op_1", patient_case_id="b3_conflict", clinician_id="Dr_A",
        clinician_specialty="Cardiology", diagnostic_impression="Acute Coronary Syndrome",
        recorded_timestamp="2026-10-15T10:00:00Z"
    ))
    conf_ledger.add_opinion(ClinicianOpinionItem(
        opinion_id="op_2", patient_case_id="b3_conflict", clinician_id="Dr_B",
        clinician_specialty="Gastroenterology", diagnostic_impression="Gastroesophageal Reflux Disease",
        recorded_timestamp="2026-10-15T10:00:00Z"
    ))

    res_conf = rag_generator.generate_explanation(conf_ledger, [], system_mode="B3_RAG_Policy_Integrated")
    assert "Non-Arbitration Policy" in res_conf.generated_text
    assert res_conf.policy_decision["selected_action"] == "ABSTAIN_AND_NAVIGATE"
    assert res_conf.execution_engine == "rule_guardrail"

    # Clean scenario: should evaluate to EXPLAIN and generate verified explanation
    clean_ledger = EvidenceLedger(patient_case_id="b3_clean_gerd")
    clean_ledger.add_item(EvidenceItem(
        evidence_id="cl_01", patient_case_id="b3_clean_gerd", concept="E_173",
        concept_name_en="Retrosternal burning after meals", normalized_value=True,
        source_type=SourceType.PATIENT_REPORTED, recorded_timestamp="2026-10-15T10:00:00Z",
        extraction_method=ExtractionMethod.DIRECT_SELECTION, extraction_confidence=1.0,
        user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT, evidence_status=EvidenceStatus.PRESENT
    ))
    gerd_passages = [RetrievalResult(passage=p, score=0.85, rank=1, retrieval_method="hybrid") for p in knowledge_base.passages if "GERD" in p.passage_id][:2]
    res_clean = rag_generator.generate_explanation(clean_ledger, gerd_passages, system_mode="B3_RAG_Policy_Integrated")
    assert res_clean.policy_decision["selected_action"] == "EXPLAIN"
    assert res_clean.policy_decision["is_emergency_override"] is False
    assert "Non-Arbitration Policy" not in res_clean.generated_text
    assert res_clean.verification_report is not None
    assert res_clean.verification_report["total_claims"] > 0

