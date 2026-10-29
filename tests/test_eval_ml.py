"""Step 9c tests: ML evaluation helpers with synthetic numbers, plus a render check on the real metrics file."""
from __future__ import annotations

import pytest

from eval import ml_eval as ml
from src import config

FAKE_METRICS = {
    "n_train": 8, "n_test": 4, "train_churn_rate": 0.25, "scale_pos_weight": 3.0,
    "cv_models": {
        "a": {"model": "logreg", "engineered": True, "cv_pr_auc_mean": 0.66, "cv_pr_auc_std": 0.02,
              "cv_roc_auc_mean": 0.84, "oof_brier": 0.16},
        "b": {"model": "xgboost", "engineered": False, "cv_pr_auc_mean": 0.67, "cv_pr_auc_std": 0.02,
              "cv_roc_auc_mean": 0.85, "oof_brier": 0.15},
    },
    "selected": {"model": "xgboost", "engineered": False, "criterion": "mean CV PR-AUC"},
    "threshold": {"value": 0.5},
    "test": {"pr_auc": 0.6, "roc_auc": 0.8, "precision": 0.5, "recall": 0.7, "f1": 0.58, "accuracy": 0.75,
             "brier": 0.16, "confusion_tn_fp_fn_tp": [1, 1, 1, 1]},
    "notes": ["probabilities are not calibrated"],
}


def test_brier_score() -> None:
    assert ml.brier_score([0.5, 0.5], [0, 1]) == pytest.approx(0.25)
    assert ml.brier_score([1.0, 0.0], [1, 0]) == 0.0


def test_calibration_bins_edges() -> None:
    bins = ml.calibration_bins([0.05, 0.1, 0.95, 1.0], [0, 1, 1, 1])
    assert len(bins) == 10 and [b["n"] for b in bins] == [1, 1, 0, 0, 0, 0, 0, 0, 0, 2]
    assert bins[9]["observed"] == 1.0 and bins[2]["observed"] is None


def test_tier_table_follows_config_bands() -> None:
    rows = ml.tier_table([0.34, 0.35, 0.60, 0.80, 0.99], [0, 0, 1, 1, 1])
    assert [(r["tier"], r["n"]) for r in rows] == [("Low", 1), ("Medium", 1), ("High", 1), ("Critical", 2)]
    assert rows[3]["observed"] == 1.0 and rows[0]["observed"] == 0.0


def test_run_ml_eval_with_fake_predictions() -> None:
    probs = {"a": 0.9, "b": 0.7, "c": 0.2, "d": 0.1}
    labels = {"a": 1, "b": 0, "c": 0, "d": 0}
    expected = ml.brier_score(list(probs.values()), list(labels.values()))
    out = ml.run_ml_eval(list(probs), labels, lambda cid: {"prob": probs[cid]}, expected_n=4, expected_brier=expected)
    assert out["n"] == 4 and out["observed_churn_rate"] == 0.25
    assert out["checks"] == {"n_matches_metrics_json": True, "brier_matches_metrics_json": True}
    assert sum(t["n"] for t in out["tiers"]) == 4 and sum(b["n"] for b in out["bins"]) == 4
    bad = ml.run_ml_eval(list(probs), labels, lambda cid: {"prob": probs[cid]}, expected_n=5, expected_brier=expected + 0.1)
    assert bad["checks"] == {"n_matches_metrics_json": False, "brier_matches_metrics_json": False}


def test_run_ml_eval_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        ml.run_ml_eval([], {}, lambda cid: {"prob": 0.5})


def test_model_table_from_synthetic_metrics() -> None:
    text = ml.render_model_table(FAKE_METRICS)
    assert "| xgboost | False | 0.67 +/- 0.02 | 0.85 | 0.15 |" in text
    assert "is smaller than the largest CV standard deviation" in text
    assert "not evidence that one model is better" in text and "probabilities are not calibrated" in text
    rows = FAKE_METRICS["cv_models"]
    wide = {**FAKE_METRICS, "cv_models": {**rows, "b": {**rows["b"], "cv_pr_auc_mean": 0.80}}}
    assert "is larger than the largest CV standard deviation" in ml.render_model_table(wide)


def test_render_markdown_has_all_sections() -> None:
    result = ml.run_ml_eval(
        ["a", "b"], {"a": 1, "b": 0}, lambda cid: {"prob": 0.9 if cid == "a" else 0.1},
        expected_n=2, expected_brier=0.01,
    )
    text = ml.render_markdown(FAKE_METRICS, result)
    for expected in ("# ML evaluation", "REAL Telco", "SYNTHETIC", "## Tiers on the test split", "| Critical |",
                     "## Calibration on the test split", "Consistency with models/metrics.json", "different cut-offs"):
        assert expected in text, expected


@pytest.mark.skipif(not config.METRICS_JSON.exists(), reason="metrics.json not present")
def test_real_metrics_file_renders() -> None:
    metrics = ml.load_metrics()
    text = ml.render_model_table(metrics)
    assert metrics["selected"]["model"] in text and str(metrics["n_test"]) in text