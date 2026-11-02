"""Tune the XGBoost churn model under a decision rule declared before any run (Step 11a).

Protocol (all on the TRAIN split; the test split is untouched unless the gate passes):
  1. Stage 1: score the baseline and N seeded random configurations with repeated stratified 5-fold CV (same
     folds for all, so scores are paired) and keep the top K by mean PR-AUC.
  2. Stage 2: re-score the K finalists and the baseline on FRESH folds. The best of K is picked here.
  3. Gate: adopt only if the mean PR-AUC gain is at least TUNE_MIN_GAIN, a corrected one-sided paired t-test
     passes at TUNE_ALPHA / K, and the mean Brier score is not worse by more than TUNE_MAX_BRIER_WORSE.
  4. Only if the gate passes: choose a threshold on out-of-fold predictions, refit on all of train, save
     models/churn_model_tuned.joblib and score the test split once, beside the baseline's test numbers.
The baseline model and models/metrics.json are never overwritten.

    python -m src.ml.tune [--jobs 4] [--configs 40]
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.base import clone
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import Pipeline

from src import config
from src.ml.preprocess import get_features, get_target, prepare_data
from src.ml.train import best_threshold, evaluate, make_pipelines, run_cv
from src.ml.tune_stats import SEARCHED, decide, sample_configs

logger = logging.getLogger(__name__)
ENGINEER = False  # engineered features did not help in train.py's comparison, so they are not searched


def build_pipeline(base: Pipeline, params: dict[str, Any]) -> Pipeline:
    """Copy of `base` with only the given model parameters changed; everything else stays identical."""
    return clone(base).set_params(**{f"model__{key}": value for key, value in params.items()})


def cv_splits(x: pd.DataFrame, y: pd.Series, repeats: int, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    cv = RepeatedStratifiedKFold(n_splits=config.CV_FOLDS, n_repeats=repeats, random_state=seed)
    return list(cv.split(x, y))


def score_fold(pipe: Pipeline, x: pd.DataFrame, y: pd.Series, fit_idx: np.ndarray, val_idx: np.ndarray) -> tuple[float, float]:
    """(PR-AUC, Brier) on one validation fold. The whole pipeline is refit, so preprocessing never sees val rows."""
    model = clone(pipe).fit(x.iloc[fit_idx], y.iloc[fit_idx])
    proba = model.predict_proba(x.iloc[val_idx])[:, 1]
    return float(average_precision_score(y.iloc[val_idx], proba)), float(brier_score_loss(y.iloc[val_idx], proba))


def score_configs(
    pipes: list[Pipeline], x: pd.DataFrame, y: pd.Series, splits: list[tuple[np.ndarray, np.ndarray]], jobs: int
) -> list[dict[str, list[float]]]:
    """Per-fold scores for every pipeline on the same folds. Parallel over (pipeline, fold); the order is preserved."""
    tasks = [(c, s) for c in range(len(pipes)) for s in range(len(splits))]
    scored = cast(
        "list[tuple[float, float]]",
        Parallel(n_jobs=jobs)(delayed(score_fold)(pipes[c], x, y, *splits[s]) for c, s in tasks),
    )
    result: list[dict[str, list[float]]] = [{"pr": [], "brier": []} for _ in pipes]
    for (c, _), (pr, brier) in zip(tasks, scored):
        result[c]["pr"].append(pr)
        result[c]["brier"].append(brier)
    return result


def search(
    x: pd.DataFrame, y: pd.Series, base: Pipeline, pos_weight: float, *,
    n_configs: int = config.TUNE_N_CONFIGS, top_k: int = config.TUNE_TOP_K, jobs: int = 1, seed: int = config.SEED,
    repeats_search: int = config.TUNE_REPEATS_SEARCH, repeats_confirm: int = config.TUNE_REPEATS_CONFIRM,
) -> dict[str, Any]:
    """Stages 1 and 2 plus the gate. Index 0 is always the baseline; configuration i is candidates[i - 1]."""
    candidates = sample_configs(n_configs, pos_weight, seed)
    pipes = [base] + [build_pipeline(base, params) for params in candidates]
    stage1 = score_configs(pipes, x, y, cv_splits(x, y, repeats_search, seed), jobs)
    means = [float(np.mean(s["pr"])) for s in stage1]
    finalists = sorted(range(1, len(pipes)), key=lambda i: (-means[i], i))[:top_k]
    order = [0] + finalists
    stage2 = score_configs([pipes[i] for i in order], x, y, cv_splits(x, y, repeats_confirm, seed + 1), jobs)
    decision = decide(stage2[1:], stage2[0], val_fraction=1 / config.CV_FOLDS)
    return {
        "candidates": candidates,
        "stage1": [
            {"index": i, "params": None if i == 0 else candidates[i - 1], "pr_mean": round(means[i], 4),
             "pr_std": round(float(np.std(s["pr"], ddof=1)), 4), "brier_mean": round(float(np.mean(s["brier"])), 4)}
            for i, s in enumerate(stage1)
        ],
        "finalists": finalists,
        "stage2": [{"index": i, **s} for i, s in zip(order, stage2)],
        "decision": decision,
        "winner": finalists[decision["best"]],
    }


def adopt(winner: Pipeline, train_df: pd.DataFrame, test_df: pd.DataFrame) -> dict[str, Any]:
    """Gate passed: pick the threshold on out-of-fold train predictions, refit, save, and score the test split once."""
    x_train, y_train = get_features(train_df, ENGINEER), get_target(train_df)
    oof, _, _ = run_cv(winner, x_train, y_train)
    threshold = best_threshold(y_train, oof)
    final = clone(winner).fit(x_train, y_train)
    prep = final.named_steps["prep"]
    joblib.dump(
        {
            "pipeline": final, "model_name": "xgboost", "engineer": ENGINEER, "threshold": threshold,
            "feature_names": prep.get_feature_names_out().tolist(), "background": prep.transform(x_train),
        },
        config.TUNED_MODEL_PATH,
    )
    proba = final.predict_proba(get_features(test_df, ENGINEER))[:, 1]
    return {"tuned_threshold": round(threshold, 4), "test": evaluate(get_target(test_df), proba, threshold)}


def main() -> None:
    """Run the protocol and write models/tuning.json. Prints the decision."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--jobs", type=int, default=4, help="worker processes (each fit is single-threaded)")
    parser.add_argument("--configs", type=int, default=config.TUNE_N_CONFIGS)
    args = parser.parse_args()
    config.configure_logging()
    config.ensure_dirs()
    train_df, test_df = prepare_data(engineer=True, write=False)  # write=False: leave split_ids.json alone
    x_train, y_train = get_features(train_df, ENGINEER), get_target(train_df)
    pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())
    base = make_pipelines(ENGINEER, pos_weight)["xgboost"]
    started = time.monotonic()
    result = search(x_train, y_train, base, pos_weight, n_configs=args.configs, jobs=args.jobs)
    decision = result["decision"]
    model_params = base.named_steps["model"].get_params()
    report: dict[str, Any] = {
        "seed": config.SEED, "n_train": int(len(train_df)), "n_configs": args.configs, "engineered_features": ENGINEER,
        "rule": {"top_k": config.TUNE_TOP_K, "min_gain": config.TUNE_MIN_GAIN, "alpha": config.TUNE_ALPHA,
                 "max_brier_worse": config.TUNE_MAX_BRIER_WORSE, "repeats_search": config.TUNE_REPEATS_SEARCH,
                 "repeats_confirm": config.TUNE_REPEATS_CONFIRM},
        "baseline_params": {key: model_params.get(key) for key in SEARCHED},
        "stage1": result["stage1"], "finalists": result["finalists"], "stage2": result["stage2"],
        "decision": decision, "adopted": decision["adopted"], "test": None, "baseline_test": None,
        "elapsed_s": round(time.monotonic() - started, 1),
    }
    if decision["adopted"]:
        winner = build_pipeline(base, result["candidates"][result["winner"] - 1])
        report.update(adopt(winner, train_df, test_df))
        report["baseline_test"] = json.loads(config.METRICS_JSON.read_text(encoding="utf-8"))["test"]
    config.TUNING_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Wrote %s (adopted=%s)", config.TUNING_JSON, decision["adopted"])
    summary = {"adopted": decision["adopted"], "decision": decision, "baseline": result["stage1"][0],
               "finalists": [result["stage1"][i] for i in result["finalists"]], "elapsed_s": report["elapsed_s"]}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()