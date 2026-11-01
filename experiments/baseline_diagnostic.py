"""
MedResolve — Diagnostic Machine Learning Baseline
Phase 1 Baseline Benchmark for DDXPlus:
- Majority-Class Baseline (DummyClassifier)
- Sparse Multinomial Logistic Regression (SGDClassifier with log_loss / LogisticRegression)

Metrics:
- Top-1 Accuracy
- Top-3 Accuracy
- Macro-Averaged F1
- Per-Class Precision & Recall
- Confusion Matrix

Guarantees:
- Strict zero-leakage: PATHOLOGY & DIFFERENTIAL_DIAGNOSIS never appear in X.
- Reproducible dev subset (default 50,000 cases, seed=42).
- Preserves official validation (132,448) and test (134,529) splits.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.ddxplus_loader import DDXPlusLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MedResolve.Baseline")


def compute_top_k_accuracy(y_true: np.ndarray, y_prob: np.ndarray, k: int = 1) -> float:
    """
    Computes Top-K classification accuracy from predicted class probabilities.
    Args:
        y_true: Ground-truth class indices of shape (N,)
        y_prob: Predicted probabilities or scores of shape (N, C)
        k: Rank threshold (e.g., 1 or 3)
    Returns:
        float: Fraction of samples where y_true is in the top-k highest scoring classes.
    """
    if y_prob.ndim != 2:
        raise ValueError(f"y_prob must be 2-dimensional (N, C), got {y_prob.shape}")
    if k <= 0 or k > y_prob.shape[1]:
        raise ValueError(f"k must be between 1 and {y_prob.shape[1]}, got {k}")

    # Top-k indices per sample (sorted descending)
    top_k_indices = np.argsort(y_prob, axis=1)[:, -k:]
    # Check whether true label appears in the top-k set
    correct = np.any(top_k_indices == y_true[:, None], axis=1)
    return float(np.mean(correct))


def evaluate_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray],
    target_names: List[str],
) -> Dict[str, Any]:
    """
    Calculates Top-1, Top-3, Macro-F1, per-class metrics, and confusion matrix.
    """
    top1 = float(np.mean(y_true == y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    top3 = None
    if y_prob is not None:
        top3 = compute_top_k_accuracy(y_true, y_prob, k=min(3, y_prob.shape[1]))

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(target_names))), zero_division=0
    )

    per_class = {}
    for i, name in enumerate(target_names):
        per_class[name] = {
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1_score": round(float(f1[i]), 4),
            "support": int(support[i]),
        }

    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(target_names))))

    return {
        "top_1_accuracy": round(top1, 4),
        "top_3_accuracy": round(top3, 4) if top3 is not None else None,
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class_metrics": per_class,
        "confusion_matrix": cm.tolist(),
    }


def train_and_evaluate_baseline(
    model_name: str = "sgd_log_loss",
    dev_subset_size: int = 50000,
    eval_split: str = "validate",
    eval_max_samples: Optional[int] = None,
    evidence_mode: str = "all",
    seed: int = 42,
    output_dir: Path = Path("results/baselines"),
) -> Dict[str, Any]:
    """
    Orchestrates baseline training and evaluation.
    """
    start_time = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    loader = DDXPlusLoader()

    logger.info("=" * 60)
    logger.info(f"MedResolve Diagnostic Baseline — Model: {model_name}")
    logger.info(f"Dev Subset Size: {dev_subset_size:,} (Seed: {seed})")
    logger.info(f"Evidence Mode: {evidence_mode.upper()} ({'Full EVIDENCES' if evidence_mode == 'all' else 'INITIAL_EVIDENCE complaint only'})")
    logger.info(f"Evaluation Split: {eval_split} (Max Samples: {eval_max_samples})")
    logger.info("=" * 60)

    # 1. Load reproducible training subset
    logger.info("Loading training development subset...")
    train_df = loader.get_dev_subset(n=dev_subset_size, seed=seed, split="train")
    X_train, y_train, feat_names = loader.extract_features_and_labels(
        train_df, evidence_mode=evidence_mode
    )
    logger.info(f"X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")

    # 2. Load evaluation split
    logger.info(f"Loading {eval_split} split...")
    eval_df = loader.load_raw_dataframe(eval_split, nrows=eval_max_samples)
    X_eval, y_eval, _ = loader.extract_features_and_labels(
        eval_df, evidence_mode=evidence_mode
    )
    logger.info(f"X_eval shape: {X_eval.shape}, y_eval shape: {y_eval.shape}")

    # 3. Instantiate model
    num_classes = len(loader.pathology_list)
    if model_name == "majority":
        model = DummyClassifier(strategy="most_frequent")
    elif model_name == "sgd_log_loss":
        model = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-4,
            max_iter=1000,
            tol=1e-3,
            random_state=seed,
            n_jobs=-1,
        )
    elif model_name == "logistic":
        model = LogisticRegression(
            max_iter=200,
            solver="lbfgs",
            random_state=seed,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"Unknown model name '{model_name}'. Choose from ['majority', 'sgd_log_loss', 'logistic']")

    # 4. Train
    fit_start = time.time()
    logger.info(f"Fitting {model_name}...")
    model.fit(X_train, y_train)
    fit_duration = round(time.time() - fit_start, 2)
    logger.info(f"Model fitting complete in {fit_duration}s")

    # 5. Predict & Evaluate
    logger.info("Evaluating model predictions...")
    y_pred = model.predict(X_eval)

    y_prob = None
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_eval)
        # Ensure probability matrix has columns for all num_classes
        if y_prob.shape[1] < num_classes:
            full_prob = np.zeros((len(y_eval), num_classes), dtype=np.float32)
            for local_idx, cls_idx in enumerate(model.classes_):
                full_prob[:, cls_idx] = y_prob[:, local_idx]
            y_prob = full_prob
    elif model_name == "majority":
        # Create empirical or one-hot probability for majority class
        maj_class = model.classes_[0]
        y_prob = np.zeros((len(y_eval), num_classes), dtype=np.float32)
        y_prob[:, maj_class] = 1.0

    metrics = evaluate_predictions(y_eval, y_pred, y_prob, loader.pathology_list)
    total_duration = round(time.time() - start_time, 2)

    result_summary = {
        "model_name": model_name,
        "evidence_mode": evidence_mode,
        "dev_subset_size": dev_subset_size,
        "random_seed": seed,
        "eval_split": eval_split,
        "eval_samples": len(y_eval),
        "num_features": X_train.shape[1],
        "num_classes": num_classes,
        "fit_time_seconds": fit_duration,
        "total_runtime_seconds": total_duration,
        "metrics": metrics,
    }

    # Save results to json
    result_file = output_dir / f"{model_name}_{evidence_mode}_{eval_split}_{dev_subset_size}_results.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result_summary, f, indent=2)

    # For backward-compatibility when evidence_mode == "all"
    if evidence_mode == "all":
        legacy_file = output_dir / f"{model_name}_{eval_split}_{dev_subset_size}_results.json"
        with open(legacy_file, "w", encoding="utf-8") as f:
            json.dump(result_summary, f, indent=2)

    logger.info("=" * 60)
    logger.info(f"RESULTS FOR {model_name.upper()} (Evidence Mode: {evidence_mode.upper()}):")
    logger.info(f"Top-1 Accuracy: {metrics['top_1_accuracy'] * 100:.2f}%")
    if metrics["top_3_accuracy"] is not None:
        logger.info(f"Top-3 Accuracy: {metrics['top_3_accuracy'] * 100:.2f}%")
    logger.info(f"Macro-F1 Score: {metrics['macro_f1']:.4f}")
    logger.info(f"Saved report to: {result_file}")
    logger.info("=" * 60)

    return result_summary


def main():
    parser = argparse.ArgumentParser(description="MedResolve Diagnostic Baseline Benchmark")
    parser.add_argument(
        "--model",
        type=str,
        default="sgd_log_loss",
        choices=["majority", "sgd_log_loss", "logistic"],
        help="Model baseline to train and evaluate",
    )
    parser.add_argument(
        "--evidence_mode",
        type=str,
        default="all",
        choices=["all", "initial"],
        help="Evidence setting: 'all' (complete EVIDENCES list) or 'initial' (INITIAL_EVIDENCE starting complaint only)",
    )
    parser.add_argument(
        "--dev_subset_size",
        type=int,
        default=50000,
        help="Number of stratified training cases for reproducible dev set",
    )
    parser.add_argument(
        "--eval_split",
        type=str,
        default="validate",
        choices=["validate", "test"],
        help="Evaluation split (validate or test)",
    )
    parser.add_argument(
        "--eval_max_samples",
        type=int,
        default=None,
        help="Optional ceiling on evaluation samples for quick test cycles",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="results/baselines",
        help="Output directory for results",
    )

    args = parser.parse_args()
    train_and_evaluate_baseline(
        model_name=args.model,
        dev_subset_size=args.dev_subset_size,
        eval_split=args.eval_split,
        eval_max_samples=args.eval_max_samples,
        evidence_mode=args.evidence_mode,
        seed=args.seed,
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
