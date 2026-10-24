"""Smoke tests for Step 1 (ML). Deterministic, no network, no LLM."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import numpy as  np 
from typing import Any
from scipy import sparse

from src import config
from src.ml.preprocess import (
    build_preprocessor, clean_and_engineer, get_features, load_raw, prepare_data,
)
from src.ml.train import best_threshold


def _dense(x: Any) -> np.ndarray:
    """Transformer output as a dense float array (typed dense-or-sparse)."""
    return x.toarray() if sparse.issparse(x) else np.asarray(x, dtype=float)


def _toy_frame() -> pd.DataFrame:
    """Tiny Telco-shaped frame incl. the blank-TotalCharges trap (row 0, tenure 0)."""
    rows = []
    for i in range(8):
        rows.append({
            "customerID": f"C{i}", "gender": "Male" if i % 2 else "Female",
            "SeniorCitizen": i % 2, "Partner": "Yes", "Dependents": "No", "tenure": i,
            "PhoneService": "Yes", "MultipleLines": "No", "InternetService": "DSL",
            "OnlineSecurity": "Yes" if i % 3 == 0 else "No", "OnlineBackup": "No",
            "DeviceProtection": "No", "TechSupport": "No", "StreamingTV": "No",
            "StreamingMovies": "No", "Contract": "Month-to-month",
            "PaperlessBilling": "Yes", "PaymentMethod": "Mailed check",
            "MonthlyCharges": 50.0 + i,
            "TotalCharges": " " if i == 0 else str(50.0 * i),
            "Churn": "Yes" if i % 2 else "No",
        })
    return pd.DataFrame(rows)


def test_clean_fixes_blank_totalcharges_and_adds_features() -> None:
    out = clean_and_engineer(_toy_frame())
    assert not out["TotalCharges"].isna().any()
    assert out.loc[0, "TotalCharges"] == 0.0
    assert set(out["SeniorCitizen"]) <= {"Yes", "No"}
    assert out.loc[0, "n_addon_services"] == 1
    assert out.loc[0, "charge_gap"] == out.loc[0, "MonthlyCharges"]  # tenure 0 -> hist avg 0


def test_preprocessor_survives_unseen_category() -> None:
    x = get_features(clean_and_engineer(_toy_frame()))
    prep = build_preprocessor()
    fitted = prep.fit_transform(x)
    assert fitted.shape[0] == 8 and not np.isnan(_dense(fitted)).any()
    unseen = x.copy()
    unseen["Contract"] = "Two year"  # never seen at fit time
    with pytest.warns(UserWarning, match="unknown categories"):
        out = prep.transform(unseen)
    assert out.shape[1] == fitted.shape[1] and not np.isnan(_dense(out)).any()


def test_best_threshold_separates_clean_data() -> None:
    y = np.array([0, 0, 0, 1, 1, 1])
    proba = np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9])
    assert 0.3 < best_threshold(y, proba) <= 0.7 + 1e-9


@pytest.mark.skipif(not config.CHURN_CSV.exists(), reason="raw CSV not present")
def test_split_is_disjoint_stratified_and_complete() -> None:
    train_df, test_df = prepare_data(write=False)
    assert set(train_df[config.ID_COL]).isdisjoint(test_df[config.ID_COL])
    assert len(train_df) + len(test_df) == len(load_raw())
    gap = abs(
        (train_df[config.TARGET_COL] == "Yes").mean()
        - (test_df[config.TARGET_COL] == "Yes").mean()
    )
    assert gap < 0.005


@pytest.mark.skipif(
    not (config.MODEL_PATH.exists() and config.SPLIT_IDS_JSON.exists()),
    reason="train the model first",
)
def test_predict_customer_contract_and_unknown_id() -> None:
    from src.ml.explain import UnknownCustomerError, predict_customer

    ids = json.loads(config.SPLIT_IDS_JSON.read_text(encoding="utf-8"))
    result = predict_customer(ids["test"][0])
    assert set(result) == {"prob", "label", "top_drivers"}
    assert 0.0 <= result["prob"] <= 1.0
    assert result["label"] in {"churn", "no_churn"}
    assert len(result["top_drivers"]) == 5
    with pytest.raises(UnknownCustomerError):
        predict_customer("NOT-A-REAL-ID")