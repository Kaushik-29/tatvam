"""
MedResolve longitudinal answer pipeline (B0–B5).

  B0  generic LLM, new query only
  B1  medical RAG (references) without patient history
  B2  patient-history retrieval (STAIR-Clinical) without general medical RAG
  B3  patient-context hybrid RAG (BM25 + BGE-M3 + structured ops) without STAIR
  B4  STAIR-Clinical + hybrid patient retrieval + STAIR-routed reference RAG
  B5  B4 + emergency pre-emption, evidence reconciliation, selective action
      policy and claim-level verification with buffered release (the product)

Order of operations for B5 (safety first):
  emergency screen -> query understanding -> patient-scoped retrieval -> reference
  retrieval -> reconciliation -> action policy -> LLM (buffered) -> claim
  verification -> release only permitted claims.
"""

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from backend import config
from backend.claim_verification.verifier import LongitudinalClaimVerifier
from backend.evidence_reconciliation.emergency import screen_text
from backend.evidence_reconciliation.reconcile import reconcile
from backend.llm.ollama_client import OllamaClient, OllamaUnavailable
from backend.patient_memory.models import ClinicalRecord, Consultation
from backend.patient_memory.repository import PatientMemory
from backend.rag.evidence_assembly import assemble
from backend.rag.fusion import rrf
from backend.rag.query_understanding import lay_name, understand
from backend.structured_retrieval.patient_retriever import PatientRetriever

logger = logging.getLogger("MedResolve.Pipeline")

SYSTEM_PROMPT = """You are MedResolve, an academic medical INFORMATION assistant (not a doctor). You never diagnose, never prescribe, and never change medications.
Rules you must follow exactly:
1. Use ONLY the facts in the context sections. Every sentence that states a fact about this patient MUST end with the [E#] citation(s) it comes from. Never invent records, dates, values, diagnoses, or medication changes.
2. Every sentence of general medical information MUST end with the [R#] citation(s) it comes from. General knowledge is NOT a fact about this patient: write it as general information ("In general, ...").
3. Say clearly when information is patient-reported, extracted but unconfirmed, derived, or estimated, as labelled in the context.
4. State conflicts, uncertainty and missing information from section I explicitly.
5. If something is not in the context, say it is not in the record. Do not guess.
6. Talk to the person directly as "you" and "your". Never write "the patient" or "this patient".
7. Answer the question that was asked. For general questions (symptoms, causes, prevention, what to do) give that information from the [R#] passages.
8. Under "What your records show", mention only records that are directly relevant to the question. If none are, write exactly: "Nothing in your records appears directly related to this question."
9. Under "Suggested next steps", give practical steps from the [R#] passages and say when to see a doctor. End with when to seek professional assessment. Keep it under 300 words.
Citation examples (copy this format exactly):
  "Your record lists anemia diagnosed on 2024-09-02 [E3]."
  "In general, anemia can cause tiredness and shortness of breath [R1]."
  "Talk to your doctor if the tiredness lasts more than two weeks." (where-to-go advice needs no citation)
Write in plain language with these headings:
## Summary
## What your records show
## General medical information
## Uncertainties and missing information
## Suggested next steps"""

DECISION_RE = re.compile(r"\bshould i (stop|start|take|increase|decrease|double|skip|quit|change)\b|\bwhat dose\b|"
                         r"\bhow (much|many) .{0,30}should i take\b|\bcan i (stop|take|double)\b|\bprescribe\b|"
                         r"\bdo i have (cancer|a tumou?r|diabetes|covid|heart disease)\b|\bdiagnose me\b", re.I)
DURATION_RE = re.compile(r"\b(\d+|a|one|two|few|several)\s+(hour|day|week|month|year)s?\b|since|yesterday|today|this (morning|week)|last night", re.I)

_vocab_cache: Optional[List[str]] = None


def clinical_vocabulary(s: Session) -> List[str]:
    """Cohort-wide vocabulary of medication / diagnosis / lab names (for entity checks)."""
    global _vocab_cache
    if _vocab_cache is None:
        leaves = ["medical_history/diagnoses", "medical_history/conditions", "medication_history/current_medications",
                  "medication_history/previous_medications", "laboratory_observations/laboratory_results",
                  "allergy_history", "medical_history/procedures"]
        keys = s.scalars(select(distinct(ClinicalRecord.concept_key)).where(ClinicalRecord.leaf_path.in_(leaves))).all()
        vocab = set()
        for k in keys:
            name = lay_name(k)
            if 5 <= len(name) <= 40:
                vocab.add(name)
        _vocab_cache = sorted(vocab)
    return _vocab_cache


@dataclass
class PipelineConfig:
    variant: str = "B5"
    k_patient: int = 20
    k_reference: int = 4
    use_llm: bool = True
    persist: bool = True


@dataclass
class PipelineDeps:
    embedder: Any = None
    reference_index: Any = None
    selector: Any = None
    llm: Optional[OllamaClient] = None


def _policy(emergency, qu, findings, n_records, query) -> (str, str):
    if emergency.is_emergency:
        return "EMERGENCY_OVERRIDE", "Red-flag symptoms: " + "; ".join(emergency.red_flags)
    if any(f.severity == "HIGH" for f in findings):
        return "ABSTAIN_AND_NAVIGATE", "High-severity conflict in the record requires clinician review."
    if DECISION_RE.search(query):
        return "ABSTAIN_AND_NAVIGATE", "The question asks for a diagnostic or prescribing decision."
    if n_records == 0:
        return "ASK", "No medical history is on file; history is needed for a personalised answer."
    if any(f.finding_type == "MISSING_INFORMATION" and "mentioned" in f.description for f in findings):
        return "ASK", "A medication you mentioned is not in your record; please confirm it."
    if qu.is_new_concern and len(query.split()) < 7 and not DURATION_RE.search(query):
        return "ASK", "More detail about the new symptom (duration, severity, associated symptoms) is needed."
    return "EXPLAIN", "Sufficient evidence to provide information."


def _template_answer(ctx, qu) -> str:
    """Deterministic fallback used when the local LLM is unavailable (labelled in the response)."""
    lines = ["## Summary", f"Here is what your record contains that relates to: {qu.raw_query}", "",
             "## What your records show"]
    for alias, e in list(ctx.evidence.items())[:12]:
        lines.append(f"- Your record lists {e['text'][:160]} [{alias}].")
    if ctx.references:
        lines += ["", "## General medical information"]
        for alias, r in list(ctx.references.items())[:3]:
            lines.append(f"- In general: {r['text'][:260]} [{alias}]")
    lines += ["", "## Suggested next steps",
              "- Please discuss these records with your doctor or a qualified health care provider."]
    return "\n".join(lines)


def run_pipeline(s: Session, patient_id: str, query: str, intake: Optional[Dict[str, Any]] = None,
                 cfg: Optional[PipelineConfig] = None, deps: Optional[PipelineDeps] = None,
                 on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None) -> Dict[str, Any]:
    cfg = cfg or PipelineConfig()
    deps = deps or PipelineDeps()
    emit = on_event or (lambda *_: None)
    v = cfg.variant
    t0 = time.time()
    timings: Dict[str, float] = {}
    mem = PatientMemory(s, patient_id)
    patient = mem.patient()
    result: Dict[str, Any] = {"consultation_id": f"c_{uuid.uuid4().hex[:12]}", "patient_id": patient_id,
                              "query": query, "variant": v, "intake": intake or {}}

    # 1. emergency pre-emption (B5) — before any retrieval or generation
    full_text = query + " " + " ".join(str(x) for x in (intake or {}).values() if x)
    emergency = screen_text(full_text)
    timings["emergency_check_s"] = round(time.time() - t0, 3)
    emit("stage", {"stage": "emergency_check", "is_emergency": emergency.is_emergency})
    if v == "B5" and emergency.is_emergency:
        text = ("## Emergency warning\nYour description includes warning signs that need urgent in-person care: "
                + "; ".join(emergency.red_flags) + ".\n\nPlease call your local emergency number now "
                "(for example 112 / 108 in India, 911 in the US, 999 in the UK) or go to the nearest emergency department. "
                "Do not wait for an online answer. MedResolve has not generated any other content for this question.")
        result.update(action="EMERGENCY_OVERRIDE", action_reason="; ".join(emergency.red_flags), final_text=text,
                      evidence=[], references=[], findings=[], verification=None, emergency=emergency.__dict__,
                      timings={**timings, "total_s": round(time.time() - t0, 3)}, engine="deterministic_emergency")
        return _persist(s, result, cfg)

    # 2. query understanding
    known_meds = sorted({r["concept_key"] for r in mem.records(leaves=["medication_history/current_medications",
                                                                        "medication_history/previous_medications"])})
    qu = understand(query, known_medications=known_meds)
    result["query_understanding"] = qu.to_dict()

    # 3. patient-scoped retrieval
    retriever = PatientRetriever(mem, deps.embedder)
    retrieved, trace = [], None
    ts = time.time()
    emit("stage", {"stage": "retrieving_patient_context"})
    if v in ("B2", "B4", "B5"):
        stair_recs, trace = retriever.stair(query, qu, deps.selector, k=cfg.k_patient)
        if v == "B2":
            retrieved = stair_recs
        else:
            hyb, _ = retriever.hybrid_structured(query, qu, k=cfg.k_patient)
            by_id = {r["record_id"]: r for r in stair_recs + hyb}
            fused = rrf([[r["record_id"] for r in stair_recs], [r["record_id"] for r in hyb]], weights=[1.0, 0.5])
            retrieved = [by_id[i] for i, _ in fused[:cfg.k_patient]]
    elif v == "B3":
        retrieved, trace = retriever.hybrid_structured(query, qu, k=cfg.k_patient)
    timings["patient_retrieval_s"] = round(time.time() - ts, 3)
    uses_history = v in ("B2", "B3", "B4", "B5")
    current_meds = mem.records(leaves=["medication_history/current_medications"]) if uses_history else []
    allergies = mem.records(leaves=["allergy_history"]) if uses_history else []
    med_intervals = mem.medication_intervals() if uses_history else []

    # 4. reference retrieval
    refs = []
    ts = time.time()
    if v in ("B1", "B3", "B4", "B5") and deps.reference_index is not None:
        emit("stage", {"stage": "retrieving_references"})
        mode = "stair" if v in ("B4", "B5") else "hybrid"
        rq = query if not qu.symptoms else f"{query} ({', '.join(qu.symptoms)})"
        refs = _diverse_refs([h.to_dict() for h in deps.reference_index.search(rq, k=cfg.k_reference * 3, mode=mode)],
                             cfg.k_reference)
    timings["reference_retrieval_s"] = round(time.time() - ts, 3)

    # 5. reconciliation (B5)
    findings = []
    if v == "B5":
        emit("stage", {"stage": "reconciling"})
        leaf_counts = {n.path: n.count for n in mem.toc() for n in ([n] + n.children)}
        needed = [lp for lp, _ in (trace.selected_leaves if trace else [])]
        if qu.intent == "allergy_check":
            needed.append("allergy_history")
        findings = reconcile(retrieved + current_meds + allergies, allergies=allergies, current_meds=current_meds,
                             mentioned_medications=[], query_drug_terms=_drug_terms(query),
                             birth_date=patient.birth_date if patient else None, needed_leaves=sorted(set(needed)),
                             leaf_counts=leaf_counts, med_intervals=med_intervals)
        unknown = _unknown_medications(query, known_meds)
        if unknown:
            from backend.evidence_reconciliation.reconcile import Finding
            findings += [Finding("MISSING_INFORMATION", "MEDIUM",
                                 f"You mentioned '{m}', but it is not in your medication records.", [], "USER_CONFIRMATION")
                         for m in unknown]

    # 6. evidence assembly
    ctx = assemble(query, qu.symptoms, intake, retrieved, (current_meds + allergies) if uses_history else [],
                   refs, [f.to_dict() for f in findings], med_intervals)
    result["evidence"] = list(ctx.evidence.values())
    result["references"] = list(ctx.references.values())
    result["findings"] = [f.to_dict() for f in findings]
    result["retrieval_trace"] = trace.__dict__ if trace else None
    result["context_sections"] = ctx.sections
    emit("evidence", {"evidence": result["evidence"], "references": result["references"], "findings": result["findings"]})

    # 7. action policy (B5)
    action, reason = ("EXPLAIN", "Baseline variant: no selective policy")
    if v == "B5":
        action, reason = _policy(emergency, qu, findings, mem.count(), query)
    result.update(action=action, action_reason=reason)

    # 8. generation (buffered: nothing is streamed to the user before verification)
    ts = time.time()
    if action in ("EXPLAIN",) or v != "B5":
        emit("stage", {"stage": "generating"})
        prompt = ("Context:\n" + ctx.render() + f"\n\nQuestion: {query}\nAnswer using only the context above.")
        if v == "B0":
            prompt = f"Question: {query}\nAnswer in plain language for a patient."
        raw, engine = None, None
        if cfg.use_llm and deps.llm is not None:
            try:
                raw = deps.llm.generate(prompt, system=SYSTEM_PROMPT if v != "B0" else
                                        "You are a helpful medical information assistant. You do not diagnose or prescribe.",
                                        max_tokens=650)
                engine = f"ollama:{deps.llm.model}"
            except OllamaUnavailable as e:
                logger.warning("Ollama unavailable: %s", e)
        if raw is None:
            raw, engine = _template_answer(ctx, qu), "deterministic_template_fallback"
        result["raw_generation"] = raw
        result["engine"] = engine
    elif action == "ASK":
        raw = _ask_text(reason, qu, mem.count())
        result.update(raw_generation=raw, engine="policy_ask")
    else:   # ABSTAIN_AND_NAVIGATE
        raw = _abstain_text(reason, findings, ctx)
        result.update(raw_generation=raw, engine="policy_abstain")
    timings["generation_s"] = round(time.time() - ts, 3)

    # 9. claim verification (B5) — release only permitted claims
    if v == "B5" and result["engine"].startswith(("ollama", "deterministic_template")):
        emit("stage", {"stage": "verifying"})
        verifier = LongitudinalClaimVerifier(clinical_vocabulary(s))
        vr = verifier.verify(result["raw_generation"], ctx.evidence, ctx.references, current_report=full_text,
                             findings_text="\n".join(f.description for f in findings))
        result["verification"] = vr.to_dict()
        final = vr.final_text
        if vr.withheld:
            final += ("\n\n_Note: " + str(len(vr.withheld)) + " statement(s) were withheld because they could not "
                      "be verified against your records or the cited references._")
        result["final_text"] = final
    else:
        result["verification"] = None
        result["final_text"] = result["raw_generation"]
    if v == "B5":
        result["final_text"] += ("\n\n_MedResolve is a research prototype that provides medical information, not a "
                                 "diagnosis or treatment. Please consult a qualified clinician._")
    timings["total_s"] = round(time.time() - t0, 3)
    result["timings"] = timings
    result["model_config"] = {"llm": deps.llm.model if deps.llm else None, "embedding_model": config.EMBEDDING_MODEL,
                              "stair_backend": getattr(deps.selector, "backend_name", None)}
    return _persist(s, result, cfg)


def _diverse_refs(hits: List[Dict[str, Any]], k: int, per_path: int = 2) -> List[Dict[str, Any]]:
    """Keep rank order but take at most `per_path` passages from one subsection, so a question about
    symptoms AND prevention is not answered from one long subsection split into many passages."""
    out, seen = [], {}
    for h in hits:
        if seen.get(h["path"], 0) < per_path:
            out.append(h)
            seen[h["path"]] = seen.get(h["path"], 0) + 1
        if len(out) == k:
            break
    return out


def _drug_terms(query: str) -> List[str]:
    from backend.evidence_reconciliation.reconcile import DRUG_CLASSES
    q = query.lower()
    return sorted({m for ms in DRUG_CLASSES.values() for m in ms if re.search(r"\b" + m + r"\b", q)} |
                  {c for c in DRUG_CLASSES if re.search(r"\b" + c + r"\b", q)})


def _unknown_medications(query: str, known: List[str]) -> List[str]:
    """Medication names the patient refers to as their own ('my X') that are not in the record."""
    from backend.evidence_reconciliation.reconcile import DRUG_CLASSES
    names = {m for ms in DRUG_CLASSES.values() for m in ms} | {"metformin", "insulin", "warfarin", "levothyroxine",
                                                                "amlodipine", "metoprolol", "omeprazole", "prednisone"}
    out = []
    for n in names:
        if re.search(rf"\bmy {n}\b", query.lower()) and not any(n in k for k in known):
            out.append(n)
    return sorted(out)


def _ask_text(reason: str, qu, n_records: int) -> str:
    if n_records == 0:
        return ("## I need a bit more information\nYour MedResolve profile does not contain any medical history yet, "
                "so I cannot relate this question to your past conditions, medications or allergies.\n\n"
                "- Please add your previous conditions, current medications and allergies in your profile, or upload "
                "old medical records.\n- Then ask again and I will use them.")
    q = ["How long have you had this symptom?", "How severe is it (mild, moderate, severe)?",
         "Have you noticed any other symptoms with it?"]
    if "medication" in reason:
        q = ["Could you confirm the name and dose of the medication you mentioned?",
             "When did you start taking it?"]
    return "## Before I answer, a few questions\n" + reason + "\n\n" + "\n".join(f"- {x}" for x in q)


def _abstain_text(reason: str, findings, ctx) -> str:
    lines = ["## Please speak with a clinician about this", reason,
             "MedResolve does not make diagnostic or prescribing decisions and does not choose between conflicting records."]
    high = [f for f in findings if f.severity in ("HIGH", "MEDIUM")]
    if high:
        lines.append("\n**Issues found in your records:**")
        for f in high:
            lines.append(f"- {f.description}")
    lines.append("\nThe records related to your question are listed with this answer so you can show them to your "
                 "doctor or pharmacist. Do not start, stop or change any medication without professional advice.")
    return "\n".join(lines)


def _persist(s: Session, result: Dict[str, Any], cfg: PipelineConfig) -> Dict[str, Any]:
    if cfg.persist:
        s.add(Consultation(consultation_id=result["consultation_id"], patient_id=result["patient_id"],
                           query=result["query"], intake_json=json.dumps(result.get("intake") or {}),
                           action=result.get("action"), response_text=result.get("final_text"),
                           result_json=json.dumps(result, default=str), system_variant=result["variant"],
                           latency_s=(result.get("timings") or {}).get("total_s")))
        s.flush()
    return result
