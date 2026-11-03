"""Step 11a tests: the tuning decision rule and search plumbing, with made-up numbers and tiny synthetic data.

They prove the gate does what the protocol says. They cannot say whether tuning helps the churn model.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from src import config
from src.ml.train import make_pipelines
from src.ml.tune import build_pipeline, cv_splits, score_configs, search
from src.ml.tune_stats import SEARCHED, corrected_paired_ttest, decide, sample_configs

JITTER = np.array([0.002, -0.002, 0.001, -0.001, 0.0] * 3)  # 15 folds, mean zero
NOISY = np.array([0.05, -0.03] * 7 + [0.01])  # mean 0.01 but wildly uneven
BASE_PR = 0.66 + np.linspace(-0.02, 0.02, 15)
BASELINE = {"pr": BASE_PR.tolist(), "brier": [0.16] * 15}
VAL_FRACTION = 0.2


def arm(gain: float = 0.0, brier: float = 0.0, noise: np.ndarray = JITTER) -> dict[str, list[float]]:
    return {"pr": (BASE_PR + gain + noise).tolist(), "brier": [0.16 + brier] * 15}


def tiny_data(rows: int = 300) -> tuple[pd.DataFrame, pd.Series]:
    x, y = make_classification(n_samples=rows, n_features=6, n_informative=4, random_state=0)
    return pd.DataFrame(x, columns=[f"f{i}" for i in range(6)]), pd.Series(y)


def test_sample_configs_is_seeded_and_in_range() -> None:
    weight = 2.7686
    configs = sample_configs(40, weight, 42)
    assert configs == sample_configs(40, weight, 42) and configs != sample_configs(40, weight, 43)
    assert len(configs) == 40 and all(set(c) == set(SEARCHED) for c in configs)
    assert all(0.01 <= c["learning_rate"] <= 0.2 and c["max_depth"] in range(2, 7) for c in configs)
    assert {c["scale_pos_weight"] for c in configs} <= {1.0, weight**0.5, weight}
    json.dumps(configs)  # must be serialisable for tuning.json


def test_corrected_ttest_is_more_cautious_than_the_plain_one() -> None:
    diffs = np.array([0.01, 0.02, 0.03, 0.0, 0.02])
    corrected = corrected_paired_ttest(diffs, VAL_FRACTION)
    plain_t = diffs.mean() / np.sqrt(diffs.var(ddof=1) / len(diffs))
    plain_p = stats.t.sf(plain_t, len(diffs) - 1)
    expected_se = np.sqrt((1 / 5 + 0.25) * diffs.var(ddof=1))
    assert corrected["t"] == pytest.approx(diffs.mean() / expected_se) and corrected["df"] == 4
    assert corrected["t"] < plain_t and corrected["p"] > plain_p
    assert corrected["p"] == pytest.approx(stats.t.sf(corrected["t"], 4))


def test_ttest_degenerate_inputs() -> None:
    assert corrected_paired_ttest([0.01] * 5, VAL_FRACTION)["p"] == 0.0
    assert corrected_paired_ttest([0.0] * 5, VAL_FRACTION)["p"] == 1.0
    with pytest.raises(ValueError):
        corrected_paired_ttest([0.01, 0.02], VAL_FRACTION)


def test_gate_adopts_only_a_clear_win() -> None:
    win = decide([arm(0.02)], BASELINE, val_fraction=VAL_FRACTION)
    assert win["adopted"] and win["reasons"] == [] and win["mean_gain"] == pytest.approx(0.02, abs=1e-4)
    small = decide([arm(0.003)], BASELINE, val_fraction=VAL_FRACTION)
    assert not small["adopted"] and any("below the required" in r for r in small["reasons"])


def test_gate_rejects_noise_and_worse_calibration() -> None:
    noisy = decide([arm(noise=NOISY)], BASELINE, val_fraction=VAL_FRACTION)
    assert noisy["mean_gain"] >= config.TUNE_MIN_GAIN and not noisy["adopted"]
    assert any("p =" in r for r in noisy["reasons"])
    worse = decide([arm(0.02, brier=0.01)], BASELINE, val_fraction=VAL_FRACTION)
    assert not worse["adopted"] and any("Brier" in r for r in worse["reasons"])


def test_gate_picks_the_best_candidate_and_corrects_the_level() -> None:
    out = decide([arm(0.001), arm(0.02), arm(0.01)], BASELINE, val_fraction=VAL_FRACTION)
    assert out["best"] == 1 and out["alpha"] == pytest.approx(config.TUNE_ALPHA / 3, abs=1e-4)


def test_build_pipeline_changes_only_the_given_parameters() -> None:
    base = make_pipelines(False, 2.77)["xgboost"]
    tuned = build_pipeline(base, {"max_depth": 6, "learning_rate": 0.1})
    model, original = tuned.named_steps["model"], base.named_steps["model"]
    assert (model.max_depth, model.learning_rate) == (6, 0.1) and (original.max_depth, original.learning_rate) == (3, 0.05)
    for key in ("subsample", "colsample_bytree", "eval_metric", "random_state", "n_jobs", "scale_pos_weight"):
        assert model.get_params()[key] == original.get_params()[key], key
    assert model.get_params()["n_jobs"] == 1 and model.get_params()["random_state"] == config.SEED


def test_score_configs_shape_and_determinism() -> None:
    x, y = tiny_data()
    pipes = [Pipeline([("model", LogisticRegression(C=c, max_iter=300))]) for c in (0.1, 1.0)]
    splits = cv_splits(x, y, 2, seed=1)
    first = score_configs(pipes, x, y, splits, jobs=1)
    assert first == score_configs(pipes, x, y, splits, jobs=1)
    assert len(first) == 2 and all(len(arm_["pr"]) == 10 == len(arm_["brier"]) for arm_ in first)
    assert all(0.0 <= v <= 1.0 for arm_ in first for v in arm_["pr"])


def test_parallel_scores_match_sequential_scores() -> None:
    x, y = tiny_data()
    pipes = [Pipeline([("model", LogisticRegression(C=c, max_iter=300))]) for c in (0.1, 1.0)]
    splits = cv_splits(x, y, 1, seed=2)
    assert score_configs(pipes, x, y, splits, jobs=2) == score_configs(pipes, x, y, splits, jobs=1)


def test_search_end_to_end_on_synthetic_data() -> None:
    x, y = tiny_data(400)
    base = Pipeline([("model", XGBClassifier(n_estimators=20, max_depth=2, eval_metric="logloss",
                                              random_state=config.SEED, n_jobs=1))])
    kwargs = {"n_configs": 3, "top_k": 2, "jobs": 1, "repeats_search": 1, "repeats_confirm": 1}
    first, second = search(x, y, base, 2.0, **kwargs), search(x, y, base, 2.0, **kwargs)
    assert first["decision"] == second["decision"] and first["finalists"] == second["finalists"]
    assert [row["index"] for row in first["stage1"]] == [0, 1, 2, 3] and first["stage1"][0]["params"] is None
    assert len(first["finalists"]) == 2 and set(first["finalists"]) <= {1, 2, 3}
    assert [row["index"] for row in first["stage2"]] == [0, *first["finalists"]]
    assert isinstance(first["decision"]["adopted"], bool) and first["winner"] in first["finalists"]