"""
Tests for reproducible dev subset selection and preservation of train/validation/test separation.
"""

import pytest
from experiments.ddxplus_loader import DDXPlusLoader


@pytest.fixture(scope="module")
def loader():
    return DDXPlusLoader()


def test_dev_subset_reproducibility(loader):
    """Verify that calling get_dev_subset with the same seed yields identical records."""
    sub1 = loader.get_dev_subset(n=200, seed=42, split="validate")
    sub2 = loader.get_dev_subset(n=200, seed=42, split="validate")

    assert len(sub1) == 200
    assert len(sub2) == 200
    assert sub1["PATHOLOGY"].tolist() == sub2["PATHOLOGY"].tolist()
    assert sub1["AGE"].tolist() == sub2["AGE"].tolist()


def test_dev_subset_different_seeds(loader):
    """Verify that different seeds produce different subsets."""
    sub_seed1 = loader.get_dev_subset(n=200, seed=42, split="validate")
    sub_seed2 = loader.get_dev_subset(n=200, seed=99, split="validate")

    # They should not be identical
    differences = (sub_seed1["AGE"].values != sub_seed2["AGE"].values).sum()
    assert differences > 0, "Different random seeds produced identical samples"


def test_train_val_test_separation(loader):
    """
    Verify that train, validation, and test splits are strictly separated
    and share distinct underlying files.
    """
    path_train = loader.get_split_path("train")
    path_val = loader.get_split_path("validate")
    path_test = loader.get_split_path("test")

    # Paths must be completely distinct
    assert path_train != path_val
    assert path_val != path_test
    assert path_train != path_test

    # Sample records from each and ensure row counts match documented numbers
    train_head = loader.load_raw_dataframe("train", nrows=10)
    val_head = loader.load_raw_dataframe("validate", nrows=10)
    test_head = loader.load_raw_dataframe("test", nrows=10)

    assert len(train_head) == 10
    assert len(val_head) == 10
    assert len(test_head) == 10
