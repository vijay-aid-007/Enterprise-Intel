"""Step 11a tests: docs/TUNING.md is rendered from tuning.json, and every number is taken from the report."""
from __future__ import annotations

import pytest

from src import config
from src.ml import tune_report as tr


def make_params(depth: int, weight: float) -> dict:
    return {"n_estimators": 200, "learning_rate": 0.03, "max_depth": depth, "min_child_weight": 20, "subsample": 0.8,
            "colsample_bytree": 0.9, "reg_lambda": 1.0, "gamma": 0.1, "scale_pos_weight": weight}


REPORT = {
    "seed": 42, "n_train": 5634, "n_configs": 3, "engineered_features": False,
    "rule": {"top_k": 2, "min_gain": 0.005, "alpha": 0.05, "max_brier_worse": 0.002, "repeats_search": 2, "repeats_confirm": 3},
    "baseline_params": {**make_params(3, 2.77), "min_child_weight": None, "reg_lambda": None, "gamma": None},
    "stage1": [
        {"index": 0, "params": None, "pr_mean": 0.6678, "pr_std": 0.0203, "brier_mean": 0.1599},
        {"index": 1, "params": make_params(4, 1.0), "pr_mean": 0.67, "pr_std": 0.02, "brier_mean": 0.14},
        {"index": 2, "params": make_params(2, 1.0), "pr_mean": 0.671, "pr_std": 0.02, "brier_mean": 0.135},
        {"index": 3, "params": make_params(5, 2.77), "pr_mean": 0.66, "pr_std": 0.02, "brier_mean": 0.16},
    ],
    "finalists": [2, 1],
    "stage2": [
        {"index": 0, "pr": [0.66, 0.67, 0.68], "brier": [0.16, 0.16, 0.16]},
        {"index": 2, "pr": [0.67, 0.68, 0.69], "brier": [0.13, 0.13, 0.13]},
        {"index": 1, "pr": [0.665, 0.675, 0.685], "brier": [0.14, 0.14, 0.14]},
    ],
    "decision": {"best": 0, "mean_gain": 0.01, "sd_diff": 0.0, "t": None, "df": 2, "p_value": 0.044, "alpha": 0.025,
                 "brier_diff": -0.03, "adopted": False, "reasons": ["corrected one-sided p = 0.0440 is not below 0.0167"]},
    "adopted": False, "test": None, "baseline_test": None, "elapsed_s": 12.3,
}
METRICS = {"pr_auc": 0.663, "roc_auc": 0.84, "precision": 0.55, "recall": 0.72, "f1": 0.62, "accuracy": 0.77, "brier": 0.16}


def test_render_not_adopted_uses_only_report_numbers() -> None:
    text = tr.render_markdown(REPORT)
    for expected in (
        "**Outcome: the baseline was kept.**", "5634 customers", "ranged from 0.66 to 0.671 (median 0.67)",
        "| baseline | 0.67 +/- 0.0203 | 0.1599 |".replace("0.67 +/-", "0.6678 +/-"),
        "| baseline | 0.6700 +/- 0.0100 | 0.1600 |", "| configuration 2 | 0.6800 +/- 0.0100 | 0.1300 |",
        "Best finalist on the fresh folds: configuration 2", "t = n/a, df = 2, p = 0.044",
        "Not adopted because:", "is not below 0.0167", "was not scored for any tuned configuration", "Run time: 12.3 s",
    ):
        assert expected in text, expected


def test_render_adopted_shows_test_comparison() -> None:
    report = {**REPORT, "adopted": True, "test": {**METRICS, "pr_auc": 0.7}, "baseline_test": METRICS,
              "decision": {**REPORT["decision"], "adopted": True, "reasons": []}}
    text = tr.render_markdown(report)
    assert "**Outcome: a tuned model was adopted.**" in text and "Every gate was passed." in text
    assert "| PR-AUC | 0.663 | 0.7 |" in text and "Not adopted because:" not in text


def test_shared_values_are_detected() -> None:
    shared = tr.shared_values(REPORT)
    assert "min_child_weight" in shared and shared["min_child_weight"] == 20 and "max_depth" not in shared
    assert "Parameters with the same value in every finalist" in tr.render_markdown(REPORT)
    assert tr.shared_values({**REPORT, "finalists": []}) == {}


def test_params_table_marks_library_defaults_with_a_dash() -> None:
    table = "\n".join(tr._params_table(REPORT))
    assert "| baseline | 200 | 0.03 | 3 | - | 0.8 | 0.9 | - | - | 2.77 |" in table
    assert "| configuration 2 | 200 | 0.03 | 2 | 20 | 0.8 | 0.9 | 1 | 0.1 | 1 |" in table


@pytest.mark.skipif(not config.TUNING_JSON.exists(), reason="models/tuning.json not present")
def test_real_tuning_file_renders() -> None:
    report = tr.load_report()
    text = tr.render_markdown(report)
    assert "# XGBoost tuning experiment" in text and "**Outcome:" in text
    assert str(report["decision"]["p_value"]) in text and str(report["decision"]["mean_gain"]) in text