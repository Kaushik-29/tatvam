"""
Tests for DDXPlus dataset file presence, integrity, and JSON metadata parsing.
"""

import json
from pathlib import Path
import pytest

RAW_DIR = Path("data/raw/ddxplus")
EXTRACTED_DIR = RAW_DIR / "extracted"

EXPECTED_FILES = [
    "release_conditions.json",
    "release_evidences.json",
    "release_train_patients.zip",
    "release_validate_patients.zip",
    "release_test_patients.zip",
    "README.md",
]

EXPECTED_EXTRACTED = [
    "train/release_train_patients.csv",
    "validate/release_validate_patients.csv",
    "test/release_test_patients.csv",
]


def test_raw_dataset_files_present():
    """Verify that all official raw files and archives exist and are non-empty."""
    assert RAW_DIR.exists(), f"Raw directory {RAW_DIR} does not exist"
    for filename in EXPECTED_FILES:
        filepath = RAW_DIR / filename
        assert filepath.exists(), f"Missing required dataset file: {filepath}"
        assert filepath.stat().st_size > 0, f"File {filepath} is empty"


def test_extracted_files_present():
    """Verify that extracted train, validation, and test CSVs exist and are non-empty."""
    assert EXTRACTED_DIR.exists(), f"Extracted directory {EXTRACTED_DIR} does not exist"
    for rel_path in EXPECTED_EXTRACTED:
        filepath = EXTRACTED_DIR / rel_path
        assert filepath.exists(), f"Missing extracted split file: {filepath}"
        assert filepath.stat().st_size > 1024, f"Extracted file {filepath} suspiciously small"


def test_conditions_json_schema():
    """Verify release_conditions.json contains 49 conditions with valid metadata."""
    cond_path = RAW_DIR / "release_conditions.json"
    with open(cond_path, "r", encoding="utf-8") as f:
        conditions = json.load(f)

    assert len(conditions) == 49, f"Expected 49 conditions, got {len(conditions)}"
    sample_key = next(iter(conditions))
    meta = conditions[sample_key]

    assert "cond-name-eng" in meta
    assert "cond-name-fr" in meta
    assert "icd10-id" in meta
    assert "severity" in meta
    assert 1 <= meta["severity"] <= 5


def test_evidences_json_schema():
    """Verify release_evidences.json contains 223 evidences with valid data types."""
    ev_path = RAW_DIR / "release_evidences.json"
    with open(ev_path, "r", encoding="utf-8") as f:
        evidences = json.load(f)

    assert len(evidences) == 223, f"Expected 223 evidences, got {len(evidences)}"
    for code, meta in evidences.items():
        assert meta.get("data_type") in {"B", "C", "M"}
        assert "question_en" in meta
        assert "is_antecedent" in meta
