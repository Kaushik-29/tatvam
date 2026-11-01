"""
MedResolve Phase 6 — Dataset Freeze Validation, Leakage Prevention, and Claim Classification Tests
Version: 2.1.0

Automated verification for:
1. Manifest integrity and SHA-256 cryptographic freeze.
2. Exact scenario counts (20 dev, 100 eval) and zero overlap.
3. Expected-action distribution and non-zero abstention denominators (8 EXPECTED_ABSTAIN).
4. Category distribution and cohort partition (85 corrupted, 15 clean).
5. Structured independent evidence auditing and verification.
6. Ground-truth isolation and sanitizer across all 120 scenarios.
7. Standardized claim classification and assertion status gating (QUOTED/UNCONFIRMED never scored as confirmed).
8. Directional one-sided exact McNemar statistical engine validation.
"""

import hashlib
import json
from pathlib import Path
import pytest
from typing import Dict, Any, List

from experiments.phase6.evaluator import (
    CorruptedOutcome,
    CleanOutcome,
    ExpectedAction,
    ClaimCategory,
    AssertionStatus,
    VerificationResult,
    StructuredClaim,
    EVALUATOR_ONLY_FIELDS,
    sanitize_scenario_for_system,
    verify_independent_corroborating_evidence,
    CommonResponseEvaluator,
    MetricCalculator,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "phase6"
OCR_SERVICE_PATH = Path(__file__).resolve().parent.parent / "backend" / "ocr_service.py"
FROZEN_OCR_SHA256 = "38b1deac035263a7d4d20b4b67319f79472219c2b7efdd7a4181989b0fc47a82"


def _compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# ============================================================================
# 1. MANIFEST INTEGRITY & CRYPTOGRAPHIC FREEZE
# ============================================================================

def test_manifest_integrity_and_cryptographic_freeze():
    manifest_file = DATA_DIR / "eval_scenarios_manifest.json"
    eval_file = DATA_DIR / "eval_scenarios.json"
    dev_file = DATA_DIR / "dev_scenarios.json"

    assert manifest_file.exists(), "eval_scenarios_manifest.json not found"
    assert eval_file.exists(), "eval_scenarios.json not found"
    assert dev_file.exists(), "dev_scenarios.json not found"

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Check version & status
    assert manifest["manifest_version"] == "2.1.0"
    assert manifest["status"] == "CRYPTOGRAPHICALLY_FROZEN"

    # 2. Check SHA-256 match
    actual_eval_hash = _compute_sha256(eval_file)
    actual_dev_hash = _compute_sha256(dev_file)
    assert manifest["eval_scenarios_sha256"] == actual_eval_hash, "eval_scenarios.json SHA256 mismatch!"
    assert manifest["dev_scenarios_sha256"] == actual_dev_hash, "dev_scenarios.json SHA256 mismatch!"

    # 3. Check frozen OCR service hash
    actual_ocr_hash = _compute_sha256(OCR_SERVICE_PATH)
    assert actual_ocr_hash == FROZEN_OCR_SHA256, "backend/ocr_service.py has been modified!"
    assert manifest["frozen_code_hashes"]["backend/ocr_service.py"] == FROZEN_OCR_SHA256


# ============================================================================
# 2. EXACT SCENARIO COUNTS & ZERO OVERLAP
# ============================================================================

def test_scenario_counts_and_zero_overlap():
    with open(DATA_DIR / "eval_scenarios.json", "r", encoding="utf-8") as f:
        eval_scenarios = json.load(f)
    with open(DATA_DIR / "dev_scenarios.json", "r", encoding="utf-8") as f:
        dev_scenarios = json.load(f)

    # Exactly 100 eval and 20 dev scenarios
    assert len(eval_scenarios) == 100, f"Expected 100 evaluation scenarios, got {len(eval_scenarios)}"
    assert len(dev_scenarios) == 20, f"Expected 20 development scenarios, got {len(dev_scenarios)}"

    eval_ids = {s["scenario_id"] for s in eval_scenarios}
    dev_ids = {s["scenario_id"] for s in dev_scenarios}

    assert len(eval_ids) == 100, "Duplicate IDs in eval scenarios"
    assert len(dev_ids) == 20, "Duplicate IDs in dev scenarios"

    # Zero overlap
    overlap = eval_ids.intersection(dev_ids)
    assert len(overlap) == 0, f"Leaked/overlapping scenario IDs between dev and eval: {overlap}"


# ============================================================================
# 3. EXPECTED ACTION DISTRIBUTION & NON-ZERO ABSTENTION DENOMINATORS
# ============================================================================

def test_action_distribution_and_nonzero_abstention_denominators():
    with open(DATA_DIR / "eval_scenarios.json", "r", encoding="utf-8") as f:
        eval_scenarios = json.load(f)

    action_counts = {}
    for s in eval_scenarios:
        act = s["expected_action"]
        action_counts[act] = action_counts.get(act, 0) + 1

    # Invariant: exactly 44 EXPLAIN, 48 ASK, 8 ABSTAIN
    assert action_counts.get("EXPECTED_EXPLAIN") == 44, f"Expected 44 EXPLAIN, got {action_counts.get('EXPECTED_EXPLAIN')}"
    assert action_counts.get("EXPECTED_ASK") == 48, f"Expected 48 ASK, got {action_counts.get('EXPECTED_ASK')}"
    assert action_counts.get("EXPECTED_ABSTAIN") == 8, f"Expected 8 ABSTAIN, got {action_counts.get('EXPECTED_ABSTAIN')}"

    # Non-zero denominators
    assert action_counts["EXPECTED_ABSTAIN"] > 0, "Abstention denominator must be non-zero!"
    assert action_counts["EXPECTED_ASK"] > 0, "Clarification denominator must be non-zero!"
    assert action_counts["EXPECTED_EXPLAIN"] > 0, "Explanation denominator must be non-zero!"


# ============================================================================
# 4. CATEGORY DISTRIBUTION & COHORT PARTITION
# ============================================================================

def test_category_distribution_and_cohort_partition():
    with open(DATA_DIR / "eval_scenarios.json", "r", encoding="utf-8") as f:
        eval_scenarios = json.load(f)

    cat_counts = {}
    for s in eval_scenarios:
        cid = s["category_id"]
        cat_counts[cid] = cat_counts.get(cid, 0) + 1

    expected_cats = {1: 15, 2: 15, 3: 15, 4: 15, 5: 15, 6: 10, 7: 15}
    assert cat_counts == expected_cats, f"Category distribution mismatch: {cat_counts}"

    corrupted_count = sum(1 for s in eval_scenarios if s["is_corrupted"])
    clean_count = sum(1 for s in eval_scenarios if not s["is_corrupted"])

    assert corrupted_count == 85, f"Expected 85 corrupted error scenarios, got {corrupted_count}"
    assert clean_count == 15, f"Expected 15 clean controls, got {clean_count}"


# ============================================================================
# 5. STRUCTURED INDEPENDENT EVIDENCE AUDITING
# ============================================================================

def test_independent_evidence_auditing():
    with open(DATA_DIR / "eval_scenarios.json", "r", encoding="utf-8") as f:
        eval_scenarios = json.load(f)

    with_evidence = [s for s in eval_scenarios if s["has_independent_corroborating_evidence"]]
    assert len(with_evidence) == 29, f"Expected exactly 29 scenarios with independent evidence, got {len(with_evidence)}"

    for s in with_evidence:
        corrob = s.get("corroborating_evidence_record")
        assert corrob is not None, f"Scenario {s['scenario_id']} marked as having evidence but record is None"
        assert corrob["evidence_id"], "Missing evidence_id in corroborating record"
        assert corrob["source_type"], "Missing source_type in corroborating record"
        assert corrob["concept"], "Missing concept in corroborating record"
        assert corrob["corroborating_value"], "Missing corroborating_value"
        assert corrob["unit"], "Missing unit"
        assert corrob["source_provenance"], "Missing source_provenance"

        # Check evidence was supplied in prior_records
        prior_ids = {r.get("evidence_id") for r in s.get("prior_records", [])}
        assert corrob["evidence_id"] in prior_ids, (
            f"Corroborating record {corrob['evidence_id']} not found in prior_records for {s['scenario_id']}"
        )

    # Scenarios without independent evidence (56 error scenarios)
    without_evidence = [s for s in eval_scenarios if s["is_corrupted"] and not s["has_independent_corroborating_evidence"]]
    assert len(without_evidence) == 56, f"Expected 56 unsupported scenarios, got {len(without_evidence)}"
    for s in without_evidence:
        assert s.get("corroborating_evidence_record") is None


# ============================================================================
# 6. GROUND-TRUTH ISOLATION & SANITIZER
# ============================================================================

def test_ground_truth_isolation_sanitizer_across_all_scenarios():
    with open(DATA_DIR / "eval_scenarios.json", "r", encoding="utf-8") as f:
        eval_scenarios = json.load(f)
    with open(DATA_DIR / "dev_scenarios.json", "r", encoding="utf-8") as f:
        dev_scenarios = json.load(f)

    all_scenarios = eval_scenarios + dev_scenarios
    assert len(all_scenarios) == 120

    for s in all_scenarios:
        sanitized = sanitize_scenario_for_system(s)
        # Verify prohibited fields are absent
        for prohibited in EVALUATOR_ONLY_FIELDS:
            assert prohibited not in sanitized, f"Prohibited field '{prohibited}' leaked in {s['scenario_id']}"

        # Verify permissible fields exist
        assert "scenario_id" in sanitized
        assert "patient_profile" in sanitized
        assert "ocr_extraction" in sanitized
        assert "prior_records" in sanitized
        assert "fixed_reference_passages" in sanitized


# ============================================================================
# 7. STANDARDIZED CLAIM CLASSIFICATION & ASSERTION STATUS GATING
# ============================================================================

def test_standardized_claim_classification_and_assertion_statuses():
    corrob_record = {
        "evidence_id": "ev_cr_01",
        "source_type": "LABORATORY_REPORT",
        "concept": "serum_creatinine",
        "corroborating_value": "1.2",
        "unit": "mg/dL",
        "recorded_timestamp": "2026-10-15T09:00:00Z",
        "source_provenance": "Baseline Panel",
    }
    prior_records = [{"evidence_id": "ev_cr_01", "concept": "serum_creatinine", "value": "1.2", "unit": "mg/dL"}]

    meta = {
        "corrupted_value": "12.0",
        "true_value": "1.2",
        "affected_concept": "serum_creatinine",
        "has_independent_corroborating_evidence": True,
        "corroborating_evidence_record": corrob_record,
    }

    # Case A: Corrupted claim with status CONFIRMED -> PROPAGATED
    claim_confirmed_corrupt = StructuredClaim(
        concept="serum_creatinine",
        value="12.0",
        unit="mg/dL",
        claim_category=ClaimCategory.PATIENT_SPECIFIC,
        assertion_status=AssertionStatus.CONFIRMED,
    )
    res_a = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[claim_confirmed_corrupt],
        system_action="ASK",  # Even with ASK action, confirmed claim overrides!
        response_text="Creatinine is 12.0 mg/dL.",
        scenario_eval_metadata=meta,
        supplied_prior_records=prior_records,
    )
    assert res_a == CorruptedOutcome.PROPAGATED

    # Case B: Corrupted value explicitly tagged QUOTED or UNCONFIRMED -> NOT an assertion, CONTAINED
    claim_quoted_corrupt = StructuredClaim(
        concept="serum_creatinine",
        value="12.0",
        unit="mg/dL",
        claim_category=ClaimCategory.PATIENT_SPECIFIC,
        assertion_status=AssertionStatus.QUOTED,
    )
    res_b = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[claim_quoted_corrupt],
        system_action="ASK",
        response_text="The document states 12.0 mg/dL. Please confirm this unverified extraction.",
        scenario_eval_metadata=meta,
        supplied_prior_records=prior_records,
    )
    assert res_b == CorruptedOutcome.CONTAINED_FLAGGED

    # Case C: True value asserted WITH valid evidence -> RESOLVED_SUPPORTED
    claim_resolved = StructuredClaim(
        concept="serum_creatinine",
        value="1.2",
        unit="mg/dL",
        claim_category=ClaimCategory.PATIENT_SPECIFIC,
        assertion_status=AssertionStatus.CONFIRMED,
        evidence_ids=["ev_cr_01"],
    )
    res_c = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[claim_resolved],
        system_action="EXPLAIN",
        response_text="Confirmed serum creatinine is 1.2 mg/dL from baseline.",
        scenario_eval_metadata=meta,
        supplied_prior_records=prior_records,
    )
    assert res_c == CorruptedOutcome.RESOLVED_SUPPORTED

    # Case D: True value asserted WITHOUT evidence -> UNSUPPORTED_CORRECTION
    meta_no_ev = dict(meta)
    meta_no_ev["has_independent_corroborating_evidence"] = False
    meta_no_ev["corroborating_evidence_record"] = None

    res_d = CommonResponseEvaluator.classify_corrupted_scenario(
        emitted_claims=[claim_resolved],
        system_action="EXPLAIN",
        response_text="Creatinine is 1.2 mg/dL.",
        scenario_eval_metadata=meta_no_ev,
        supplied_prior_records=[],
    )
    assert res_d == CorruptedOutcome.UNSUPPORTED_CORRECTION


# ============================================================================
# 8. DIRECTIONAL ONE-SIDED EXACT MCNEMAR STATISTICAL ENGINE
# ============================================================================

def test_statistical_engine_directional_one_sided_mcnemar():
    # Synthetic trial with 85 error scenarios:
    # B0 propagates on 70 scenarios (fails)
    # B3 propagates on only 10 scenarios (fails)
    # Discordant: n10 = 62 (B0 fails, B3 succeeds), n01 = 2 (B0 succeeds, B3 fails)

    b0_prop = [True] * 70 + [False] * 15
    b3_prop = [True] * 8 + [False] * 62 + [True] * 2 + [False] * 13

    res = MetricCalculator.compute_one_sided_mcnemar(b0_prop, b3_prop)

    assert res["n_total"] == 85
    assert res["contingency_table"]["n10"] == 62
    assert res["contingency_table"]["n01"] == 2
    assert res["paired_risk_difference"] > 0
    assert res["p_value_one_sided_exact"] < 1e-15, f"Expected highly significant p-value, got {res['p_value_one_sided_exact']}"
    assert res["is_significant_05"] is True

    # Check symmetry / null case: n10 == n01
    b0_null = [True] * 20 + [False] * 20
    b3_null = [False] * 20 + [True] * 20
    res_null = MetricCalculator.compute_one_sided_mcnemar(b0_null, b3_null)
    # n10 = 20, n01 = 20 -> p-value should be ~0.50
    assert 0.40 <= res_null["p_value_one_sided_exact"] <= 0.60
