"""
Tests for evaluation metrics: Top-1 Accuracy, Top-3 Accuracy, Macro-F1, and Confusion Matrix.
"""

import numpy as np
import pytest

from experiments.baseline_diagnostic import compute_top_k_accuracy, evaluate_predictions


def test_compute_top_1_accuracy():
    """Verify top-1 accuracy computation with known probability matrix."""
    y_true = np.array([0, 1, 2, 0])
    # Model predictions: class 0, class 1, class 2, class 1 (last one wrong)
    y_prob = np.array([
        [0.8, 0.1, 0.1],
        [0.2, 0.7, 0.1],
        [0.1, 0.3, 0.6],
        [0.3, 0.5, 0.2],
    ])

    top1 = compute_top_k_accuracy(y_true, y_prob, k=1)
    assert top1 == 0.75  # 3 out of 4 correct


def test_compute_top_3_accuracy():
    """Verify top-3 accuracy when true class is in top 3 but not top 1."""
    y_true = np.array([2, 0])
    # Sample 0: class probabilities [0.5, 0.3, 0.2, 0.0] -> rank 1 is 0, rank 2 is 1, rank 3 is 2 (y_true=2 is in top 3)
    # Sample 1: class probabilities [0.1, 0.4, 0.3, 0.2] -> rank 1 is 1, rank 2 is 2, rank 3 is 3, rank 4 is 0 (y_true=0 is not in top 3)
    y_prob = np.array([
        [0.5, 0.3, 0.2, 0.0],
        [0.1, 0.4, 0.3, 0.2],
    ])

    top1 = compute_top_k_accuracy(y_true, y_prob, k=1)
    top3 = compute_top_k_accuracy(y_true, y_prob, k=3)

    assert top1 == 0.0
    assert top3 == 0.5  # Sample 0 is in top 3, sample 1 is not


def test_compute_top_k_input_validation():
    """Verify error handling on invalid k or dimensions."""
    y_true = np.array([0, 1])
    y_prob = np.array([0.5, 0.5])  # 1D instead of 2D
    with pytest.raises(ValueError):
        compute_top_k_accuracy(y_true, y_prob, k=1)

    y_prob_2d = np.array([[0.5, 0.5], [0.3, 0.7]])
    with pytest.raises(ValueError):
        compute_top_k_accuracy(y_true, y_prob_2d, k=0)
    with pytest.raises(ValueError):
        compute_top_k_accuracy(y_true, y_prob_2d, k=5)


def test_evaluate_predictions_structure():
    """Verify evaluate_predictions outputs full metric dictionary and valid confusion matrix."""
    y_true = np.array([0, 1, 2, 0, 1, 2])
    y_pred = np.array([0, 1, 1, 0, 1, 2])
    y_prob = np.array([
        [0.9, 0.05, 0.05],
        [0.1, 0.8, 0.1],
        [0.1, 0.6, 0.3],
        [0.7, 0.2, 0.1],
        [0.05, 0.9, 0.05],
        [0.1, 0.2, 0.7],
    ])
    names = ["ClassA", "ClassB", "ClassC"]

    metrics = evaluate_predictions(y_true, y_pred, y_prob, names)

    assert "top_1_accuracy" in metrics
    assert "top_3_accuracy" in metrics
    assert "macro_f1" in metrics
    assert "per_class_metrics" in metrics
    assert "confusion_matrix" in metrics

    assert metrics["top_1_accuracy"] == round(5 / 6, 4)
    assert metrics["top_3_accuracy"] == 1.0
    assert len(metrics["confusion_matrix"]) == 3
    assert len(metrics["per_class_metrics"]) == 3
