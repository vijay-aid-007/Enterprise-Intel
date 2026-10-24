"""SHAP-based per-customer explanations and the public `predict_customer` contract."""
from __future__ import annotations

import json
import logging
import sys
from functools import lru_cache
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap

from src import config
from src.ml.preprocess import CATEGORICAL, clean_and_engineer, get_features, load_raw

logger = logging.getLogger(__name__)

LABEL_CHURN = "churn"
LABEL_STAY = "no_churn"


class UnknownCustomerError(KeyError):
    """Raised when a customer_id is not in the churn CSV (the only IDs we can score)."""


@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    """Load the model bundle saved by src.ml.train."""
    if not config.MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No trained model at {config.MODEL_PATH}; run `python -m src.ml.train` first"
        )
    return joblib.load(config.MODEL_PATH)


@lru_cache(maxsize=1)
def _customers() -> pd.DataFrame:
    """Cleaned + engineered dataset indexed by customerID (read-only view of the CSV)."""
    return clean_and_engineer(load_raw(), engineer=True).set_index(config.ID_COL)


@lru_cache(maxsize=1)
def _split_ids() -> dict[str, set[str]]:
    """Which customer IDs were in the train vs test split."""
    raw = json.loads(config.SPLIT_IDS_JSON.read_text(encoding="utf-8"))
    return {name: set(ids) for name, ids in raw.items()}


@lru_cache(maxsize=1)
def _explainer() -> Any:
    """SHAP explainer matching the selected model type (values are in log-odds)."""
    bundle = _bundle()
    model = bundle["pipeline"].named_steps["model"]
    if bundle["model_name"] == "xgboost":
        return shap.TreeExplainer(model)
    return shap.LinearExplainer(model, bundle["background"])


def _contributions(matrix: np.ndarray) -> np.ndarray:
    """SHAP values for the churn class as a (rows, features) array, across shap versions."""
    values = _explainer().shap_values(matrix)
    if isinstance(values, list):  # older shap: one array per class
        values = values[1]
    values = np.asarray(values)
    if values.ndim == 3:  # newer shap: (rows, features, classes)
        values = values[:, :, 1]
    return values


def _customer_value(feature: str, row: pd.Series) -> Any:
    """Human-readable value of the customer for a (possibly one-hot) model feature."""
    if feature in row.index:  # numeric feature: show the raw, unscaled value
        return round(float(row[feature]), 2)
    for col in CATEGORICAL:  # one-hot feature like "Contract_One year"
        if feature.startswith(col + "_"):
            return str(row[col])
    return None


def customer_split(customer_id: str) -> str:
    """'train', 'test' or 'unknown'. Train-set predictions are in-sample (optimistic)."""
    for name, ids in _split_ids().items():
        if customer_id in ids:
            return name
    return "unknown"


def predict_customer(customer_id: str, top_k: int = 5) -> dict[str, Any]:
    """Score one customer from the churn CSV.

    Returns {"prob": float, "label": "churn"|"no_churn", "top_drivers": [...]}.
    Each driver: feature, customer_value, contribution (log-odds), effect.
    Raises UnknownCustomerError for IDs not in the CSV (known limitation).
    """
    customers = _customers()
    customer_id = customer_id.strip()
    if customer_id not in customers.index:
        raise UnknownCustomerError(f"customer_id {customer_id!r} not found in the churn CSV")

    bundle = _bundle()
    pipeline = bundle["pipeline"]
    # row = customers.loc[customer_id]
    features = get_features(customers.loc[[customer_id]], engineer=bundle["engineer"])
    row = features.loc[[customer_id]].iloc[0]
    matrix = pipeline.named_steps["prep"].transform(features)
    prob = float(pipeline.named_steps["model"].predict_proba(matrix)[0, 1])

    contrib = _contributions(matrix)[0]
    names = bundle["feature_names"]
    drivers = [
        {
            "feature": names[i],
            "customer_value": _customer_value(names[i], row),
            "contribution": round(float(contrib[i]), 4),
            "effect": "raises churn risk" if contrib[i] > 0 else "lowers churn risk",
        }
        for i in np.argsort(-np.abs(contrib))[:top_k]
    ]
    label = LABEL_CHURN if prob >= bundle["threshold"] else LABEL_STAY
    return {"prob": round(prob, 4), "label": label, "top_drivers": drivers}


def main() -> None:
    """CLI: python -m src.ml.explain [customerID]  (defaults to the first test-set customer)."""
    config.configure_logging()
    customer_id = sys.argv[1] if len(sys.argv) > 1 else sorted(_split_ids()["test"])[0]
    result = predict_customer(customer_id)
    print(json.dumps(
        {"customer_id": customer_id, "split": customer_split(customer_id), "prediction": result},
        indent=2,
    ))


if __name__ == "__main__":
    main()