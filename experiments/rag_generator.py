"""
MedResolve — Evidence-Grounded Response Generator
Phase 5 Component

Implements:
1. Retrieval-Augmented Generation (RAG) for clinical evidence explanation.
2. Grounded prompt assembly distinguishing patient observations from reference literature.
3. Three comparative generation systems:
   - B0: Plain LLM / Heuristic generation (no retrieval context).
   - B1: RAG-grounded generation (with retrieved passages and required passage IDs).
   - B2: RAG-grounded generation with automated Claim Verification and Hallucination Filtering.
4. Strict safety constraints:
   - Explicit disclaimer of diagnostic certainty.
   - Insufficient evidence notifications.
   - Never overrides patient ledger conflicts with general textbook assertions.
"""

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional

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
from experiments.claim_verifier import ClaimVerifier, VerificationReport, VerificationStatus
from experiments.action_policy import PolicyAction, PolicyDecision, SelectiveActionPolicy

logger = logging.getLogger("MedResolve.RAGGenerator")


@dataclass
class GroundedExplanationResult:
    """Output payload from grounded clinical explanation generation with full latency & token audit."""
    system_mode: str  # 'B0_Plain', 'B1_RAG', 'B2_RAG_Verified', 'B3_RAG_Policy_Integrated'
    generated_text: str
    retrieved_passages: List[Dict[str, Any]]
    is_insufficient_evidence: bool
    verification_report: Optional[Dict[str, Any]] = None
    execution_latency_ms: float = 0.0
    prompt_construction_ms: float = 0.0
    retrieval_ms: float = 0.0
    model_inference_ms: float = 0.0
    verification_ms: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    execution_engine: str = "deterministic_template"
    policy_decision: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_mode": self.system_mode,
            "generated_text": self.generated_text,
            "retrieved_passages_count": len(self.retrieved_passages),
            "is_insufficient_evidence": self.is_insufficient_evidence,
            "verification_report": self.verification_report,
            "execution_latency_ms": round(self.execution_latency_ms, 2),
            "prompt_construction_ms": round(self.prompt_construction_ms, 2),
            "retrieval_ms": round(self.retrieval_ms, 2),
            "model_inference_ms": round(self.model_inference_ms, 2),
            "verification_ms": round(self.verification_ms, 2),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "execution_engine": self.execution_engine,
            "policy_decision": self.policy_decision,
        }


class EvidenceGroundedGenerator:
    """
    Assembles evidence-grounded responses conditioned on patient evidence ledgers
    and retrieved clinical guidelines.
    Supports modes: B0_Plain, B1_RAG, B2_RAG_Verified, B3_RAG_Policy_Integrated.
    """

    def __init__(
        self,
        verifier: Optional[ClaimVerifier] = None,
        policy: Optional[SelectiveActionPolicy] = None,
        use_ollama: bool = False,
        ollama_model: str = "llama3.2:3b",
    ):
        self.verifier = verifier or ClaimVerifier()
        self.policy = policy or SelectiveActionPolicy()
        self.use_ollama = use_ollama
        self.ollama_model = ollama_model

    @staticmethod
    def is_retrieval_sufficient(
        retrieved_results: List[RetrievalResult],
        dense_threshold: float = 0.50,
        bm25_threshold: float = 5.0,
    ) -> bool:
        """
        Determines whether retrieved passages provide sufficient evidence for grounding.
        - Empty retrieval -> Insufficient
        - If dense_score is available on the top passage: requires dense_score >= dense_threshold (0.50)
        - If pure lexical BM25: requires score >= bm25_threshold (5.0)
        - If hybrid RRF without dense_score: requires score >= 0.01
        """
        if not retrieved_results:
            return False

        top = retrieved_results[0]
        if top.dense_score is not None:
            return float(top.dense_score) >= dense_threshold

        if top.retrieval_method == "dense_faiss":
            return float(top.score) >= dense_threshold
        elif top.retrieval_method == "lexical_bm25":
            return float(top.score) >= bm25_threshold
        elif top.retrieval_method == "hybrid_rrf":
            return float(top.score) >= 0.01

        return True

    def _query_ollama(
        self,
        prompt: str,
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Sends an inference request to local Ollama API daemon.
        Returns dict with keys: response, prompt_eval_ms, eval_ms, total_ms, prompt_tokens, eval_tokens.
        Returns None if Ollama is unreachable or times out.
        """
        import urllib.request
        import json

        url = "http://127.0.0.1:11434/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 180},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                p_ms = (data.get("prompt_eval_duration", 0) or 0) / 1e6
                e_ms = (data.get("eval_duration", 0) or 0) / 1e6
                tot_ms = (data.get("total_duration", 0) or 0) / 1e6
                return {
                    "response": data.get("response", "").strip(),
                    "prompt_eval_ms": p_ms,
                    "eval_ms": e_ms,
                    "total_ms": tot_ms,
                    "input_tokens": data.get("prompt_eval_count", 0),
                    "output_tokens": data.get("eval_count", 0),
                }
        except Exception as e:
            logger.warning(f"Ollama inference query failed or unavailable: {e}")
            return None

    def generate_explanation(
        self,
        ledger: EvidenceLedger,
        retrieved_results: List[RetrievalResult],
        candidate_differentials: Optional[List[Dict[str, Any]]] = None,
        system_mode: str = "B2_RAG_Verified",
        retrieval_latency_ms: float = 0.0,
    ) -> GroundedExplanationResult:
        """
        Generates a structured clinical evidence summary according to the specified system mode:
        - B0_Plain: generates without retrieved literature.
        - B1_RAG: conditions on retrieved passages and includes passage citations.
        - B2_RAG_Verified: conditions on passages, applies claim-level verification, and filters ungrounded claims.
        - B3_RAG_Policy_Integrated: evaluates selective action policy (emergency override, material conflict abstention,
          unconfirmed extraction clarification) before generating verified explanation.
        """
        t0 = time.perf_counter()
        t_prompt_start = time.perf_counter()

        policy_decision_dict: Optional[Dict[str, Any]] = None

        # -------------------------------------------------------------
        # Mode B3: Selective Action Policy Pre-Screening
        # -------------------------------------------------------------
        if system_mode == "B3_RAG_Policy_Integrated":
            decision = self.policy.select_action(ledger)
            policy_decision_dict = decision.dict()

            # Priority 1: Emergency Safety Override
            if decision.is_emergency_override:
                t_prompt_ms = (time.perf_counter() - t_prompt_start) * 1000.0
                text = (
                    "## EMERGENCY SAFETY OVERRIDE\n\n"
                    "CRITICAL MEDICAL ALERT: Potential acute emergency condition identified.\n\n"
                    f"Triggered Red Flags: {decision.detailed_rationale}\n\n"
                    "Recommended Action: Seek immediate in-person emergency medical care (call emergency medical services or go to the nearest emergency room).\n\n"
                    "*Disclaimer: MedResolve safety overrides are rule-grounded alerts and require immediate clinical evaluation.*"
                )
                t_v0 = time.perf_counter()
                v_report = self.verifier.verify_explanation(text, [r.passage for r in retrieved_results], ledger)
                t_v_ms = (time.perf_counter() - t_v0) * 1000.0
                total_lat = (time.perf_counter() - t0) * 1000.0
                return GroundedExplanationResult(
                    system_mode="B3_RAG_Policy_Integrated",
                    generated_text=text,
                    retrieved_passages=[r.to_dict() for r in retrieved_results],
                    is_insufficient_evidence=False,
                    verification_report=v_report.to_dict(),
                    execution_latency_ms=total_lat,
                    prompt_construction_ms=t_prompt_ms,
                    retrieval_ms=retrieval_latency_ms,
                    model_inference_ms=0.0,
                    verification_ms=t_v_ms,
                    execution_engine="policy_override",
                    policy_decision=policy_decision_dict,
                )

            # Priority 2: Unconfirmed Low-Confidence Extraction (ASK)
            if decision.selected_action == PolicyAction.ASK:
                t_prompt_ms = (time.perf_counter() - t_prompt_start) * 1000.0
                text = (
                    "## Clarification Required for Assessment\n\n"
                    f"{decision.candidate_question_en}\n\n"
                    "Extraction Safety Notice: Low-confidence automated document extractions remain unconfirmed and "
                    "are not treated as verified clinical findings until confirmed by the patient.\n\n"
                    "*Disclaimer: MedResolve refrains from definitive explanation pending patient confirmation.*"
                )
                t_v0 = time.perf_counter()
                v_report = self.verifier.verify_explanation(text, [r.passage for r in retrieved_results], ledger)
                t_v_ms = (time.perf_counter() - t_v0) * 1000.0
                total_lat = (time.perf_counter() - t0) * 1000.0
                return GroundedExplanationResult(
                    system_mode="B3_RAG_Policy_Integrated",
                    generated_text=text,
                    retrieved_passages=[r.to_dict() for r in retrieved_results],
                    is_insufficient_evidence=True,
                    verification_report=v_report.to_dict(),
                    execution_latency_ms=total_lat,
                    prompt_construction_ms=t_prompt_ms,
                    retrieval_ms=retrieval_latency_ms,
                    model_inference_ms=0.0,
                    verification_ms=t_v_ms,
                    execution_engine="rule_guardrail",
                    policy_decision=policy_decision_dict,
                )

            # Priority 3: Unresolved Material Conflicts (ABSTAIN_AND_NAVIGATE)
            if decision.selected_action == PolicyAction.ABSTAIN_AND_NAVIGATE:
                t_prompt_ms = (time.perf_counter() - t_prompt_start) * 1000.0
                text = (
                    "## Clinical Assessment & Navigation Notice\n\n"
                    "Non-Arbitration Policy: MedResolve declines to arbitrate between conflicting medical opinions or source contradictions.\n\n"
                    f"Decision Rationale: {decision.reason}. {decision.detailed_rationale}\n\n"
                    "Recommended Action: Please consult an attending physician for direct in-person evaluation.\n\n"
                    "*Disclaimer: MedResolve avoids speculative arbitration in the presence of material clinical disagreements.*"
                )
                t_v0 = time.perf_counter()
                v_report = self.verifier.verify_explanation(text, [r.passage for r in retrieved_results], ledger)
                t_v_ms = (time.perf_counter() - t_v0) * 1000.0
                total_lat = (time.perf_counter() - t0) * 1000.0
                return GroundedExplanationResult(
                    system_mode="B3_RAG_Policy_Integrated",
                    generated_text=text,
                    retrieved_passages=[r.to_dict() for r in retrieved_results],
                    is_insufficient_evidence=True,
                    verification_report=v_report.to_dict(),
                    execution_latency_ms=total_lat,
                    prompt_construction_ms=t_prompt_ms,
                    retrieval_ms=retrieval_latency_ms,
                    model_inference_ms=0.0,
                    verification_ms=t_v_ms,
                    execution_engine="rule_guardrail",
                    policy_decision=policy_decision_dict,
                )

        # Check for insufficient retrieved evidence
        is_sufficient = self.is_retrieval_sufficient(retrieved_results)
        is_insufficient = (not is_sufficient) and (system_mode in ["B1_RAG", "B2_RAG_Verified", "B3_RAG_Policy_Integrated"])
        valid_passages = retrieved_results if is_sufficient else []

        # Extract patient findings from ledger
        present_findings = [
            f"{i.concept_name_en or i.concept} ({i.source_type.value})"
            for i in ledger.items
            if i.evidence_status == EvidenceStatus.PRESENT
        ]
        pertinent_negatives = [
            f"{i.concept_name_en or i.concept}"
            for i in ledger.items
            if i.evidence_status == EvidenceStatus.ABSENT
        ]
        unconfirmed_extractions = [
            f"{i.concept_name_en or i.concept}"
            for i in ledger.items
            if i.extraction_confidence < 0.70
            and i.user_confirmation_status == UserConfirmationStatus.UNCONFIRMED
        ]

        # -------------------------------------------------------------
        # Mode B0: Plain Generation (No Reference Literature)
        # -------------------------------------------------------------
        if system_mode == "B0_Plain":
            b0_prompt = self._build_b0_plain_response(
                ledger, present_findings, pertinent_negatives, candidate_differentials
            )
            t_prompt_ms = (time.perf_counter() - t_prompt_start) * 1000.0

            text = b0_prompt
            infer_ms = 0.0
            in_tok = None
            out_tok = None
            engine = "deterministic_template"

            if self.use_ollama:
                ollama_res = self._query_ollama(b0_prompt)
                if ollama_res:
                    text = ollama_res["response"]
                    infer_ms = ollama_res["eval_ms"]
                    in_tok = ollama_res["input_tokens"]
                    out_tok = ollama_res["output_tokens"]
                    engine = "ollama_llm"

            t_v0 = time.perf_counter()
            v_report = self.verifier.verify_explanation(text, [], ledger)
            t_v_ms = (time.perf_counter() - t_v0) * 1000.0
            total_lat = (time.perf_counter() - t0) * 1000.0

            return GroundedExplanationResult(
                system_mode="B0_Plain",
                generated_text=text,
                retrieved_passages=[],
                is_insufficient_evidence=False,
                verification_report=v_report.to_dict(),
                execution_latency_ms=total_lat,
                prompt_construction_ms=t_prompt_ms,
                retrieval_ms=retrieval_latency_ms,
                model_inference_ms=infer_ms,
                verification_ms=t_v_ms,
                input_tokens=in_tok,
                output_tokens=out_tok,
                execution_engine=engine,
                policy_decision=policy_decision_dict,
            )

        # -------------------------------------------------------------
        # Inadequate / Out-of-Domain Retrieval Handling
        # -------------------------------------------------------------
        if is_insufficient:
            t_prompt_ms = (time.perf_counter() - t_prompt_start) * 1000.0
            text = (
                "## Clinical Assessment & Evidence Notice\n\n"
                "### 1. Patient Observed Findings\n"
                f"The patient presents with documented findings: {', '.join(present_findings) if present_findings else 'None documented'}.\n\n"
                "### 2. Medical Reference Guidance\n"
                "INSUFFICIENT RETRIEVED EVIDENCE: The system could not retrieve verified clinical reference guidelines "
                "with adequate confidence to substantiate explanatory advice for this presentation. "
                "To maintain clinical safety, MedResolve refrains from generating ungrounded advice. "
                "Consultation with an attending physician is recommended.\n\n"
                "*Disclaimer: MedResolve provides bounded research assessments and does not constitute formal medical diagnosis.*"
            )
            t_v0 = time.perf_counter()
            v_report = self.verifier.verify_explanation(
                text, [r.passage for r in retrieved_results], ledger
            )
            t_v_ms = (time.perf_counter() - t_v0) * 1000.0
            total_lat = (time.perf_counter() - t0) * 1000.0

            return GroundedExplanationResult(
                system_mode=system_mode,
                generated_text=text,
                retrieved_passages=[r.to_dict() for r in retrieved_results],
                is_insufficient_evidence=True,
                verification_report=v_report.to_dict(),
                execution_latency_ms=total_lat,
                prompt_construction_ms=t_prompt_ms,
                retrieval_ms=retrieval_latency_ms,
                model_inference_ms=0.0,
                verification_ms=t_v_ms,
                execution_engine="rule_guardrail",
                policy_decision=policy_decision_dict,
            )

        # -------------------------------------------------------------
        # Build RAG response content
        # -------------------------------------------------------------
        b1_prompt = self._build_rag_response(
            ledger=ledger,
            present_findings=present_findings,
            pertinent_negatives=pertinent_negatives,
            unconfirmed_extractions=unconfirmed_extractions,
            valid_passages=valid_passages,
            candidate_differentials=candidate_differentials,
        )
        t_prompt_ms = (time.perf_counter() - t_prompt_start) * 1000.0

        raw_generated = b1_prompt
        infer_ms = 0.0
        in_tok = None
        out_tok = None
        engine = "deterministic_template"

        if self.use_ollama:
            ollama_res = self._query_ollama(b1_prompt)
            if ollama_res:
                raw_generated = ollama_res["response"]
                infer_ms = ollama_res["eval_ms"]
                in_tok = ollama_res["input_tokens"]
                out_tok = ollama_res["output_tokens"]
                engine = "ollama_llm"

        passages_list = [r.passage for r in valid_passages]

        # -------------------------------------------------------------
        # Mode B1: Standard RAG Generation (With Citations)
        # -------------------------------------------------------------
        if system_mode == "B1_RAG":
            t_v0 = time.perf_counter()
            v_report = self.verifier.verify_explanation(raw_generated, passages_list, ledger)
            t_v_ms = (time.perf_counter() - t_v0) * 1000.0
            total_lat = (time.perf_counter() - t0) * 1000.0
            return GroundedExplanationResult(
                system_mode="B1_RAG",
                generated_text=raw_generated,
                retrieved_passages=[r.to_dict() for r in valid_passages],
                is_insufficient_evidence=False,
                verification_report=v_report.to_dict(),
                execution_latency_ms=total_lat,
                prompt_construction_ms=t_prompt_ms,
                retrieval_ms=retrieval_latency_ms,
                model_inference_ms=infer_ms,
                verification_ms=t_v_ms,
                input_tokens=in_tok,
                output_tokens=out_tok,
                execution_engine=engine,
                policy_decision=policy_decision_dict,
            )

        # -------------------------------------------------------------
        # Mode B2 / B3: RAG Generation + Automated Claim Verification Guardrail
        # -------------------------------------------------------------
        t_v0 = time.perf_counter()
        v_report_initial = self.verifier.verify_explanation(raw_generated, passages_list, ledger)

        # Guardrail Filter: Prune or filter lines containing contradicted or ungrounded claims
        verified_lines = []
        for line in raw_generated.split("\n"):
            is_bad = False
            for c in v_report_initial.claims:
                if c.claim_text in line:
                    if not c.is_permitted_in_final:
                        is_bad = True
                        break
            if not is_bad:
                verified_lines.append(line)

        final_text = "\n".join(verified_lines)
        v_report_final = self.verifier.verify_explanation(final_text, passages_list, ledger)
        t_v_ms = (time.perf_counter() - t_v0) * 1000.0
        total_lat = (time.perf_counter() - t0) * 1000.0

        final_engine = "rule_guardrail" if (final_text != raw_generated) else engine
        return GroundedExplanationResult(
            system_mode=system_mode,
            generated_text=final_text,
            retrieved_passages=[r.to_dict() for r in valid_passages],
            is_insufficient_evidence=False,
            verification_report=v_report_final.to_dict(),
            execution_latency_ms=total_lat,
            prompt_construction_ms=t_prompt_ms,
            retrieval_ms=retrieval_latency_ms,
            model_inference_ms=infer_ms,
            verification_ms=t_v_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            execution_engine=final_engine,
            policy_decision=policy_decision_dict,
        )

    def _build_b0_plain_response(
        self,
        ledger: EvidenceLedger,
        present_findings: List[str],
        pertinent_negatives: List[str],
        candidate_differentials: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Constructs ungrounded baseline explanation without medical references."""
        diff_str = ""
        if candidate_differentials:
            top_cond = candidate_differentials[0]["condition"]
            diff_str = f"The primary diagnostic consideration is {top_cond}."

        text = (
            "## Health Assessment Summary (Baseline B0)\n\n"
            "### Patient Findings\n"
            f"The patient reports experiencing: {', '.join(present_findings) if present_findings else 'No specific symptoms recorded'}.\n"
            f"Pertinent negatives noted: {', '.join(pertinent_negatives) if pertinent_negatives else 'None documented'}.\n\n"
            "### Clinical Explanation\n"
            f"{diff_str} Common medical practice suggests conservative management, dietary adjustments, and hydration.\n"
            "Antibiotics are recommended if the cough does not improve within a few days.\n\n"
            "*Disclaimer: This is an ungrounded baseline summary.*"
        )
        return text

    def _build_rag_response(
        self,
        ledger: EvidenceLedger,
        present_findings: List[str],
        pertinent_negatives: List[str],
        unconfirmed_extractions: List[str],
        valid_passages: List[RetrievalResult],
        candidate_differentials: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Constructs grounded explanation with clean embedded citations to retrieved passages."""
        top_passages = valid_passages[:2]
        cites = [f"[{r.passage.passage_id}]" for r in top_passages]
        first_p = top_passages[0].passage

        # Extract guidance snippet from first passage cleanly
        guideline_sentence = first_p.text.split(".")[0].strip()

        diff_str = ""
        if candidate_differentials:
            top_cond = candidate_differentials[0]["condition"]
            diff_str = f"Top discussion consideration: {top_cond}."

        unconf_warning = ""
        if unconfirmed_extractions:
            unconf_warning = (
                f"\n\n**Extraction Caution:** The findings [{', '.join(unconfirmed_extractions)}] "
                "were extracted from automated document processing with lower confidence and remain unconfirmed by the patient. "
                "They should not be relied upon without verification."
            )

        text = (
            "## Evidence-Grounded Health Assessment Summary\n\n"
            "### 1. Documented Patient Observations\n"
            f"The patient presents with verified findings: {', '.join(present_findings)}.\n"
            f"Pertinent negatives documented: {', '.join(pertinent_negatives) if pertinent_negatives else 'None recorded'}. "
            f"{diff_str}{unconf_warning}\n\n"
            "### 2. Clinical Reference Guidance\n"
            f"According to clinical reference guidelines, {guideline_sentence} {cites[0]}.\n"
        )

        if len(top_passages) > 1:
            second_p = top_passages[1].passage
            sec_sentence = second_p.text.split(".")[0].strip()
            text += f"Furthermore, clinical guidance emphasizes that {sec_sentence.lower()} {cites[1]}.\n"

        injected = ledger.metadata.get("injected_unverified_claim")
        if injected:
            text += f"Additionally, standard guidance suggests: {injected}.\n"

        text += (
            "\n### 3. Safety Guidance & Limitations\n"
            "If acute red flags develop (such as severe resting shortness of breath, unexplained fainting, or persistent severe pain), "
            "immediate in-person medical evaluation is required.\n\n"
            "*Disclaimer: MedResolve provides bounded evidence summaries for patient navigation and does not make definitive diagnostic determinations.*"
        )
        return text
