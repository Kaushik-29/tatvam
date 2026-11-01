"""
Tests for DDXPlusLoader functionality, schema integrity, and list parsing.
"""

from pathlib import Path
import pytest
import pandas as pd

from experiments.ddxplus_loader import DDXPlusLoader

EXPECTED_COLUMNS = [
    "AGE",
    "DIFFERENTIAL_DIAGNOSIS",
    "SEX",
    "PATHOLOGY",
    "EVIDENCES",
    "INITIAL_EVIDENCE",
]


@pytest.fixture(scope="module")
def loader():
    return DDXPlusLoader()


def test_loader_initialization(loader):
    """Verify loader correctly indexes 49 pathologies and 972 evidence tokens."""
    assert len(loader.pathology_list) == 49
    assert len(loader.pathology_to_idx) == 49
    assert len(loader.idx_to_pathology) == 49
    assert len(loader.evidence_tokens) == 972
    assert len(loader.token_to_idx) == 972


def test_parse_list_column():
    """Verify safe parsing of stringified lists."""
    assert DDXPlusLoader.parse_list_column("['E_53', 'E_7']") == ["E_53", "E_7"]
    assert DDXPlusLoader.parse_list_column("[]") == []
    assert DDXPlusLoader.parse_list_column(None) == []
    assert DDXPlusLoader.parse_list_column("") == []
    assert DDXPlusLoader.parse_list_column(["already", "a", "list"]) == ["already", "a", "list"]


def test_load_raw_dataframe_schema(loader):
    """Verify loaded dataframes conform exactly to expected columns and non-empty rows."""
    for split in ["validate", "test"]:
        df = loader.load_raw_dataframe(split, nrows=50)
        assert len(df) == 50
        assert df.columns.tolist() == EXPECTED_COLUMNS
        assert df["AGE"].dtype.kind in {"i", "u"}
        assert set(df["SEX"].unique()).issubset({"M", "F"})


def test_pathology_mapping_coverage(loader):
    """Verify all pathologies in validate split map to valid indices 0-48."""
    df = loader.load_raw_dataframe("validate", nrows=200)
    for p in df["PATHOLOGY"]:
        assert p in loader.pathology_to_idx
        idx = loader.pathology_to_idx[p]
        assert 0 <= idx < 49


def test_evidence_modes(loader):
    """Verify feature shapes and active token counts for 'all' vs 'initial' evidence modes."""
    df = loader.load_raw_dataframe("validate", nrows=50)

    # Full evidence mode
    X_all, y_all, feats_all = loader.extract_features_and_labels(df, evidence_mode="all")
    assert X_all.shape == (50, 974)
    assert len(y_all) == 50
    assert len(feats_all) == 974

    # Initial evidence mode
    X_init, y_init, feats_init = loader.extract_features_and_labels(df, evidence_mode="initial")
    assert X_init.shape == (50, 974)
    assert len(y_init) == 50
    assert len(feats_init) == 974

    # Feature space and targets must match
    assert feats_all == feats_init
    assert (y_all == y_init).all()

    # Initial mode must have far fewer active tokens than full mode (approx 2-3 per sample vs 15-25)
    assert X_init.nnz < X_all.nnz


def test_invalid_evidence_mode(loader):
    """Verify loader raises ValueError when given an invalid evidence_mode."""
    df = loader.load_raw_dataframe("validate", nrows=10)
    with pytest.raises(ValueError):
        loader.extract_features_and_labels(df, evidence_mode="invalid_mode")

