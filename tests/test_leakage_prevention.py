"""
Tests ensuring strict prevention of target leakage and differential-diagnosis leakage.
"""

import numpy as np
import pytest

from experiments.ddxplus_loader import DDXPlusLoader


@pytest.fixture(scope="module")
def loader():
    return DDXPlusLoader()


def test_zero_target_leakage_in_feature_matrix(loader):
    """
    Assert that neither PATHOLOGY nor DIFFERENTIAL_DIAGNOSIS
    are present in the extracted feature matrix or feature names.
    """
    df = loader.load_raw_dataframe("validate", nrows=100)
    X, y, feature_names = loader.extract_features_and_labels(df)

    # Feature names must never contain target labels or differential diagnosis
    forbidden = {"PATHOLOGY", "DIFFERENTIAL_DIAGNOSIS", "target", "label"}
    for feat in feature_names:
        assert feat not in forbidden, f"Forbidden target column '{feat}' found in feature names!"
        assert not feat.startswith("PATHOLOGY"), f"Target prefix found in feature: '{feat}'"

    # Shape checks: X should be (100, 974) and y should be (100,)
    assert X.shape[0] == 100
    assert X.shape[1] == len(feature_names)
    assert y.shape == (100,)
    assert y.dtype == np.int64


def test_feature_matrix_is_independent_of_target(loader):
    """
    Verify that permuting or corrupting the PATHOLOGY column does not alter the feature matrix X.
    """
    df = loader.load_raw_dataframe("validate", nrows=50).copy()
    X1, _, _ = loader.extract_features_and_labels(df)

    # Scramble PATHOLOGY
    df["PATHOLOGY"] = df["PATHOLOGY"].sample(frac=1.0, random_state=99).values
    X2, _, _ = loader.extract_features_and_labels(df)

    # Features must remain strictly identical
    diff = (X1 != X2).nnz
    assert diff == 0, "Feature matrix changed when target label was scrambled — indicates leakage!"
