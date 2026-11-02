"""Pure helpers for model tuning: seeded config sampling, a corrected paired t-test and the adoption gate.

No model code lives here, so the decision rule can be unit-tested with made-up numbers.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import ArrayLike
from scipy import stats

from src import config

SEARCHED: tuple[str, ...] = (
    "n_estimators", "learning_rate", "max_depth", "min_child_weight", "subsample",
    "colsample_bytree", "reg_lambda", "gamma", "scale_pos_weight",
)


def sample_configs(n: int, pos_weight: float, seed: int) -> list[dict[str, Any]]:
    """n seeded random XGBoost configurations. scale_pos_weight is tried at 1, sqrt(ratio) and the full class ratio."""
    rng = np.random.default_rng(seed)
    configs: list[dict[str, Any]] = []
    for _ in range(n):
        configs.append({
            "n_estimators": int(rng.choice([100, 200, 300, 400, 600])),
            "learning_rate": round(float(np.exp(rng.uniform(np.log(0.01), np.log(0.2)))), 4),
            "max_depth": int(rng.choice([2, 3, 4, 5, 6])),
            "min_child_weight": int(rng.choice([1, 3, 5, 10, 20])),
            "subsample": round(float(rng.uniform(0.6, 1.0)), 3),
            "colsample_bytree": round(float(rng.uniform(0.5, 1.0)), 3),
            "reg_lambda": round(float(np.exp(rng.uniform(np.log(0.1), np.log(20.0)))), 3),
            "gamma": float(rng.choice([0.0, 0.1, 0.5, 1.0])),
            "scale_pos_weight": float(rng.choice([1.0, pos_weight**0.5, pos_weight])),
        })
    return configs


def corrected_paired_ttest(diffs: ArrayLike, val_fraction: float) -> dict[str, Any]:
    """One-sided paired t-test (H1: mean difference > 0) with the Nadeau-Bengio variance correction.

    Folds of repeated CV share training rows, so the plain t-test is too confident. The correction replaces
    1/n by 1/n + n_val/n_train. Applying it to repeated k-fold is an approximation.
    """
    d = np.asarray(diffs, dtype=float)
    n = len(d)
    if n < 3:
        raise ValueError("need at least 3 paired differences")
    mean, var = float(d.mean()), float(d.var(ddof=1))
    se2 = (1.0 / n + val_fraction / (1.0 - val_fraction)) * var
    if se2 <= 0.0:  # every difference identical: nothing to test against
        return {"mean": mean, "sd": 0.0, "t": None, "df": n - 1, "p": 0.0 if mean > 0 else 1.0}
    t = mean / math.sqrt(se2)
    return {"mean": mean, "sd": math.sqrt(var), "t": t, "df": n - 1, "p": float(stats.t.sf(t, n - 1))}


def decide(
    candidates: list[dict[str, list[float]]], baseline: dict[str, list[float]], *, val_fraction: float
) -> dict[str, Any]:
    """Apply the adoption gate to per-fold scores ({'pr': [...], 'brier': [...]} per arm, same folds for all).

    The best candidate by mean PR-AUC is tested against the baseline. Because it was picked among
    len(candidates) on these same folds, the significance level is TUNE_ALPHA / len(candidates).
    """
    base_pr, base_brier = np.asarray(baseline["pr"]), np.asarray(baseline["brier"])
    gains = [float(np.mean(c["pr"]) - base_pr.mean()) for c in candidates]
    best = int(np.argmax(gains))
    chosen = candidates[best]
    test = corrected_paired_ttest(np.asarray(chosen["pr"]) - base_pr, val_fraction)
    alpha = config.TUNE_ALPHA / len(candidates)
    brier_diff = float(np.mean(chosen["brier"]) - base_brier.mean())
    reasons: list[str] = []
    if gains[best] < config.TUNE_MIN_GAIN:
        reasons.append(f"mean PR-AUC gain {gains[best]:.4f} is below the required {config.TUNE_MIN_GAIN}")
    if test["p"] >= alpha:
        reasons.append(f"corrected one-sided p = {test['p']:.4f} is not below {alpha:.4f}")
    if brier_diff > config.TUNE_MAX_BRIER_WORSE:
        reasons.append(f"mean Brier is worse by {brier_diff:.4f} (limit {config.TUNE_MAX_BRIER_WORSE})")
    return {
        "best": best, "mean_gain": round(gains[best], 4), "sd_diff": round(test["sd"], 4),
        "t": None if test["t"] is None else round(test["t"], 3), "df": test["df"],
        "p_value": round(test["p"], 4), "alpha": round(alpha, 4), "brier_diff": round(brier_diff, 4),
        "adopted": not reasons, "reasons": reasons,
    }