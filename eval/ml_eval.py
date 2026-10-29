"""ML evaluation tables (Step 9c): model comparison from models/metrics.json, plus tier and calibration on the TEST split.

The comparison table is rendered from the file train.py wrote; nothing is retrained or recomputed. The
calibration part asks predict_customer for every test-split customer and compares its probability with the real
Churn label. The tier boundaries (0.35 / 0.60 / 0.80) come from the SYNTHETIC retention policy, so the tier table
shows how those boundaries behave on real churn; it does not show that they are right.

    python -m eval.ml_eval
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Sequence

from src import config
from src.llm.report_evidence import risk_tier

logger = logging.getLogger(__name__)

BIN_EDGES: tuple[float, ...] = tuple(round(i / 10, 1) for i in range(11))
TIER_ORDER: tuple[str, ...] = tuple(name for name, _ in config.TIER_BANDS)
BRIER_TOLERANCE = 0.002  # predict_customer rounds probabilities to 4 decimals


def load_metrics(path: Path = config.METRICS_JSON) -> dict[str, Any]:
    """models/metrics.json as written by src.ml.train."""
    return json.loads(path.read_text(encoding="utf-8"))


def brier_score(probs: Sequence[float], labels: Sequence[int]) -> float:
    """Mean squared error between the predicted probability and the 0/1 outcome."""
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


def _summarize(group: list[tuple[float, int]]) -> dict[str, Any]:
    n = len(group)
    return {
        "n": n,
        "churned": sum(y for _, y in group),
        "mean_pred": round(sum(p for p, _ in group) / n, 4) if n else None,
        "observed": round(sum(y for _, y in group) / n, 4) if n else None,
    }


def calibration_bins(
    probs: Sequence[float], labels: Sequence[int], edges: Sequence[float] = BIN_EDGES
) -> list[dict[str, Any]]:
    """Predicted vs observed churn rate per probability bin. The last bin includes its upper edge."""
    pairs = list(zip(probs, labels))
    last = len(edges) - 2
    rows: list[dict[str, Any]] = []
    for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        group = [(p, y) for p, y in pairs if p >= lo and (p < hi or (i == last and p <= hi))]
        rows.append({"lo": lo, "hi": hi, **_summarize(group)})
    return rows


def tier_table(probs: Sequence[float], labels: Sequence[int]) -> list[dict[str, Any]]:
    """Customers and observed churn rate per report tier, using the same risk_tier() as the reports."""
    pairs = list(zip(probs, labels))
    return [
        {"tier": tier, **_summarize([(p, y) for p, y in pairs if risk_tier(p) == tier])} for tier in TIER_ORDER
    ]


def run_ml_eval(
    ids: Sequence[str],
    labels: dict[str, int],
    predict_fn: Callable[[str], dict[str, Any]],
    *,
    expected_n: int | None = None,
    expected_brier: float | None = None,
) -> dict[str, Any]:
    """Predict every id, then build the tier and calibration tables. The checks compare with metrics.json."""
    if not ids:
        raise ValueError("no test customers to evaluate")
    probs = [float(predict_fn(cid)["prob"]) for cid in ids]
    ys = [labels[cid] for cid in ids]
    brier = brier_score(probs, ys)
    checks: dict[str, bool] = {}
    if expected_n is not None:
        checks["n_matches_metrics_json"] = len(ids) == expected_n
    if expected_brier is not None:
        checks["brier_matches_metrics_json"] = abs(brier - expected_brier) <= BRIER_TOLERANCE
    return {
        "n": len(ids),
        "observed_churn_rate": round(sum(ys) / len(ys), 4),
        "mean_predicted": round(sum(probs) / len(probs), 4),
        "brier": round(brier, 4),
        "checks": checks,
        "tiers": tier_table(probs, ys),
        "bins": calibration_bins(probs, ys),
    }


def render_model_table(metrics: dict[str, Any]) -> str:
    """Comparison and test tables, taken from metrics.json as written by train.py."""
    rows = list(metrics["cv_models"].values())
    spread = max(r["cv_pr_auc_mean"] for r in rows) - min(r["cv_pr_auc_mean"] for r in rows)
    noise = max(r["cv_pr_auc_std"] for r in rows)
    smaller = spread < noise
    selected, threshold, test = metrics["selected"], metrics["threshold"], metrics["test"]
    tn, fp, fn, tp = test["confusion_tn_fp_fn_tp"]
    tail = (
        "so the choice follows the declared criterion and is not evidence that one model is better."
        if smaller else "so the selected model leads by more than the fold-to-fold noise."
    )
    out = [
        "## Model comparison (5-fold CV on the training split)", "",
        "| model | engineered features | CV PR-AUC (mean +/- std) | CV ROC-AUC | out-of-fold Brier |",
        "|---|---|---|---|---|",
    ]
    out += [
        f"| {r['model']} | {r['engineered']} | {r['cv_pr_auc_mean']} +/- {r['cv_pr_auc_std']} | "
        f"{r['cv_roc_auc_mean']} | {r['oof_brier']} |" for r in rows
    ]
    out += [
        "",
        f"Selected: {selected['model']} (engineered features: {selected['engineered']}) by {selected['criterion']}. "
        f"The spread of CV PR-AUC across the rows ({spread:.4f}) is {'smaller' if smaller else 'larger'} than "
        f"the largest CV standard deviation ({noise:.4f}), {tail}",
        "",
        f"## Test split (n = {metrics['n_test']}, decision threshold {threshold['value']} chosen on out-of-fold "
        "train predictions, evaluated once)", "",
        "| PR-AUC | ROC-AUC | precision | recall | F1 | accuracy | Brier |", "|---|---|---|---|---|---|---|",
        f"| {test['pr_auc']} | {test['roc_auc']} | {test['precision']} | {test['recall']} | {test['f1']} | "
        f"{test['accuracy']} | {test['brier']} |",
        "",
        f"Confusion matrix on test: TN {tn}, FP {fp}, FN {fn}, TP {tp}. Training churn rate "
        f"{metrics['train_churn_rate']}, positive class weight {metrics['scale_pos_weight']}.", "",
    ]
    out += [f"Note from train.py: {note}" for note in metrics.get("notes", [])]
    return "\n".join(out)


def render_markdown(metrics: dict[str, Any], result: dict[str, Any]) -> str:
    """Full ML evaluation report."""
    bands = ", ".join(f"{name} from {lower}" for name, lower in config.TIER_BANDS)
    out = [
        "# ML evaluation", "",
        "Churn data and labels are the REAL Telco dataset. The risk-tier boundaries come from the SYNTHETIC "
        "retention policy.", "",
        render_model_table(metrics), "",
        f"## Tiers on the test split (n = {result['n']}, observed churn rate {result['observed_churn_rate']}, "
        f"mean predicted {result['mean_predicted']}, Brier {result['brier']})", "",
        "| tier | customers | churned | observed churn rate | mean predicted probability |", "|---|---|---|---|---|",
    ]
    out += [f"| {r['tier']} | {r['n']} | {r['churned']} | {r['observed']} | {r['mean_pred']} |" for r in result["tiers"]]
    out += ["", "## Calibration on the test split", "",
            "| probability bin | customers | churned | observed rate | mean predicted |", "|---|---|---|---|---|"]
    out += [
        f"| {r['lo']:.1f} to {r['hi']:.1f} | {r['n']} | {r['churned']} | {r['observed']} | {r['mean_pred']} |"
        for r in result["bins"]
    ]
    checks = ", ".join(f"{key}: {value}" for key, value in result["checks"].items()) or "none"
    out += [
        "", f"Consistency with models/metrics.json: {checks}.", "",
        f"The churn label uses the decision threshold above; the report tiers use the policy boundaries ({bands}). "
        "They are different cut-offs.", "",
    ]
    return "\n".join(out)


def main() -> None:
    """CLI: python -m eval.ml_eval (about a minute: one prediction per test-split customer)."""
    import pandas as pd

    from src.ml.explain import customer_split, predict_customer

    config.configure_logging()
    metrics = load_metrics()
    frame = pd.read_csv(config.CHURN_CSV, usecols=[config.ID_COL, config.TARGET_COL], dtype=str)
    labels = {cid: int(churn == "Yes") for cid, churn in zip(frame[config.ID_COL], frame[config.TARGET_COL])}
    ids = [cid for cid in labels if customer_split(cid) == "test"]
    result = run_ml_eval(
        ids, labels, predict_customer, expected_n=metrics["n_test"], expected_brier=metrics["test"]["brier"]
    )
    config.ensure_dirs()
    markdown = render_markdown(metrics, result)
    (config.RESULTS_DIR / "ml_eval.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (config.RESULTS_DIR / "ml_eval.md").write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()