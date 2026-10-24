"""Train, compare and select the churn model (LogReg baseline vs XGBoost).

Usage (repo root):
    python -m src.ml.train            # CV on train only; saves model; test set untouched
    python -m src.ml.train --final    # also scores the test set ONCE and writes metrics.json
"""
from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss, confusion_matrix,
    f1_score, precision_recall_curve, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from src import config
from src.ml.preprocess import build_preprocessor, get_features, get_target, prepare_data

logger = logging.getLogger(__name__)

THRESHOLD_BETA = 1.0  # 1.0 = F1; raise it to favour recall over precision


def make_pipelines(engineer: bool, pos_weight: float) -> dict[str, Pipeline]:
    """Unfitted preprocess+model pipelines. Class imbalance handled via class weights."""
    logreg = LogisticRegression(
        class_weight="balanced", max_iter=1000, random_state=config.SEED
    )
    xgb = XGBClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8,
        colsample_bytree=0.8, scale_pos_weight=pos_weight, eval_metric="logloss",
        random_state=config.SEED, n_jobs=1,  # n_jobs=1 keeps runs reproducible
    )
    return {
        name: Pipeline([("prep", build_preprocessor(engineer)), ("model", model)])
        for name, model in (("logreg", logreg), ("xgboost", xgb))
    }


def run_cv(
    pipe: Pipeline, x: pd.DataFrame, y: pd.Series
) -> tuple[np.ndarray, list[float], list[float]]:
    """Stratified CV. The whole pipeline is refit per fold, so preprocessing never sees val rows.

    Returns out-of-fold probabilities plus per-fold PR-AUC and ROC-AUC.
    """
    skf = StratifiedKFold(n_splits=config.CV_FOLDS, shuffle=True, random_state=config.SEED)
    oof = np.zeros(len(y))
    pr_aucs: list[float] = []
    roc_aucs: list[float] = []
    for fit_idx, val_idx in skf.split(x, y):
        model = clone(pipe).fit(x.iloc[fit_idx], y.iloc[fit_idx])
        proba = model.predict_proba(x.iloc[val_idx])[:, 1]
        oof[val_idx] = proba
        pr_aucs.append(float(average_precision_score(y.iloc[val_idx], proba)))
        roc_aucs.append(float(roc_auc_score(y.iloc[val_idx], proba)))
    return oof, pr_aucs, roc_aucs


def best_threshold(y_true: Any, proba: Any, beta: float = THRESHOLD_BETA) -> float:
    """Probability cut-off that maximises F-beta on the given predictions."""
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    precision, recall = precision[:-1], recall[:-1]  # last point has no threshold
    b2 = beta**2
    fbeta = (1 + b2) * precision * recall / np.maximum(b2 * precision + recall, 1e-12)
    return float(thresholds[int(np.argmax(fbeta))])


def evaluate(y_true: Any, proba: np.ndarray, threshold: float) -> dict[str, Any]:
    """Threshold-free (PR-AUC, ROC-AUC, Brier) and thresholded metrics."""
    pred = (proba >= threshold).astype(int)
    return {
        "threshold": round(float(threshold), 4),
        "pr_auc": round(float(average_precision_score(y_true, proba)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, proba)), 4),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "accuracy": round(float(accuracy_score(y_true, pred)), 4),
        "brier": round(float(brier_score_loss(y_true, proba)), 4),
        "confusion_tn_fp_fn_tp": confusion_matrix(y_true, pred, labels=[0, 1]).ravel().tolist(),
    }


def run_comparison(
    train_df: pd.DataFrame, y_train: pd.Series, pos_weight: float
) -> tuple[dict[str, dict], dict[str, np.ndarray], dict[str, Pipeline]]:
    """CV every (model x engineered-features on/off) combination on TRAIN only."""
    results: dict[str, dict] = {}
    oofs: dict[str, np.ndarray] = {}
    pipes: dict[str, Pipeline] = {}
    for engineer in (True, False):
        x_train = get_features(train_df, engineer)
        for name, pipe in make_pipelines(engineer, pos_weight).items():
            key = f"{name}|engineered={engineer}"
            oof, pr, roc = run_cv(pipe, x_train, y_train)
            results[key] = {
                "model": name,
                "engineered": engineer,
                "cv_pr_auc_mean": round(float(np.mean(pr)), 4),
                "cv_pr_auc_std": round(float(np.std(pr, ddof=1)), 4),
                "cv_roc_auc_mean": round(float(np.mean(roc)), 4),
                "oof_brier": round(float(brier_score_loss(y_train, oof)), 4),
            }
            oofs[key], pipes[key] = oof, pipe
            logger.info("%s PR-AUC %.4f +/- %.4f", key, np.mean(pr), np.std(pr, ddof=1))
    return results, oofs, pipes


def main() -> None:
    """Compare models by CV, pick one, tune its threshold, save it, optionally test once."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--final", action="store_true", help="score the test set once")
    args = parser.parse_args()

    config.configure_logging()
    config.ensure_dirs()
    train_df, test_df = prepare_data(engineer=True)
    y_train = get_target(train_df)
    # Class ratio from train labels; folds are stratified, so it is ~equal per fold.
    pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())

    cv_results, oofs, pipes = run_comparison(train_df, y_train, pos_weight)
    best_key = max(cv_results, key=lambda k: cv_results[k]["cv_pr_auc_mean"])
    best = cv_results[best_key]
    threshold = best_threshold(y_train, oofs[best_key])
    cv_at_threshold = evaluate(y_train, oofs[best_key], threshold)
    logger.info("Selected %s, threshold %.4f", best_key, threshold)

    x_train = get_features(train_df, best["engineered"])
    final_pipe = clone(pipes[best_key]).fit(x_train, y_train)
    prep = final_pipe.named_steps["prep"]
    joblib.dump(
        {
            "pipeline": final_pipe,
            "model_name": best["model"],
            "engineer": best["engineered"],
            "threshold": threshold,
            "feature_names": prep.get_feature_names_out().tolist(),
            "background": prep.transform(x_train),  # SHAP background (train only)
        },
        config.MODEL_PATH,
    )

    report: dict[str, Any] = {
        "seed": config.SEED,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "train_churn_rate": round(float(y_train.mean()), 4),
        "scale_pos_weight": round(pos_weight, 4),
        "cv_models": cv_results,
        "selected": {**{k: best[k] for k in ("model", "engineered")},
                     "criterion": "mean 5-fold PR-AUC on train"},
        "threshold": {"value": round(threshold, 4), "beta": THRESHOLD_BETA,
                      "chosen_on": "out-of-fold predictions, train only"},
        "cv_oof_at_threshold": cv_at_threshold,
        "test": None,
        "notes": [
            "Class weights inflate probabilities: prob is a risk score, not calibrated.",
            "cv_oof_at_threshold is optimistic: the threshold was tuned on the same predictions.",
        ],
    }
    if args.final:
        x_test = get_features(test_df, best["engineered"])
        proba = final_pipe.predict_proba(x_test)[:, 1]
        report["test"] = evaluate(get_target(test_df), proba, threshold)
        config.METRICS_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info("Wrote %s", config.METRICS_JSON)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()