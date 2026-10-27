"""Cleaning, feature engineering, train/test split and the sklearn preprocessor.

Design rule: anything that LEARNS from data (imputer medians, scaler mean/std,
one-hot categories) lives inside the sklearn ColumnTransformer, so it is fit on
training data only. Anything stateless (type fixes, row-wise features) lives in
`clean_and_engineer` and is safe to run before splitting.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src import config

logger = logging.getLogger(__name__)

ADDON_COLS = [
    "OnlineSecurity", "OnlineBackup", "DeviceProtection",
    "TechSupport", "StreamingTV", "StreamingMovies",
]
BASE_NUMERIC = ["tenure", "MonthlyCharges", "TotalCharges"]
ENGINEERED_NUMERIC = ["n_addon_services", "charge_gap"]
CATEGORICAL = [
    "gender", "SeniorCitizen", "Partner", "Dependents", "PhoneService",
    "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup",
    "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies",
    "Contract", "PaperlessBilling", "PaymentMethod",
]


def load_raw(path: Path = config.CHURN_CSV) -> pd.DataFrame:
    """Read the raw churn CSV (read-only) and check customerID is unique."""
    df = pd.read_csv(path)
    if df[config.ID_COL].duplicated().any():
        raise ValueError("Duplicate customerID values in raw data")
    logger.info("Loaded %d rows from %s", len(df), path.name)
    return df


def clean_and_engineer(df: pd.DataFrame, engineer: bool = True) -> pd.DataFrame:
    """Fix known Telco traps and add row-wise engineered features.

    Stateless: uses no statistics learned from data, so running it before the
    split cannot leak anything.
    """
    out = df.copy()

    # Trap 1: blank TotalCharges strings make the whole column text.
    out["TotalCharges"] = pd.to_numeric(
        out["TotalCharges"].astype(str).str.strip(), errors="coerce"
    )
    # Blank rows are tenure-0 customers (not billed yet), so 0 is a rule, not a guess.
    never_billed = out["TotalCharges"].isna() & (out["tenure"] == 0)
    out.loc[never_billed, "TotalCharges"] = 0.0
    logger.info("Set TotalCharges=0 for %d rows with tenure 0", int(never_billed.sum()))
    leftover = int(out["TotalCharges"].isna().sum())
    if leftover:
        logger.warning("%d TotalCharges still missing; pipeline imputer will fill", leftover)

    # Trap 2: SeniorCitizen is 0/1 but is a category, not a quantity.
    if pd.api.types.is_numeric_dtype(out["SeniorCitizen"]):
        out["SeniorCitizen"] = out["SeniorCitizen"].map({0: "No", 1: "Yes"})

    if engineer:
        out["n_addon_services"] = (out[ADDON_COLS] == "Yes").sum(axis=1)
        # Average price paid per month so far; the gap shows recent price rises.
        historic_avg = (out["TotalCharges"] / out["tenure"]).where(out["tenure"] > 0, 0.0)
        out["charge_gap"] = out["MonthlyCharges"] - historic_avg
    return out


def feature_columns(engineer: bool = True) -> list[str]:
    """Fixed, ordered list of model input columns."""
    numeric = BASE_NUMERIC + (ENGINEERED_NUMERIC if engineer else [])
    return numeric + CATEGORICAL


def get_features(df: pd.DataFrame, engineer: bool = True) -> pd.DataFrame:
    """Select model input columns (no ID, no target) from a cleaned dataframe."""
    return df[feature_columns(engineer)].copy()


def get_target(df: pd.DataFrame) -> pd.Series:
    """Binary target: 1 = churned, 0 = stayed."""
    return (df[config.TARGET_COL] == "Yes").astype(int)

def build_preprocessor(engineer: bool = True) -> ColumnTransformer:
    """Unfitted preprocessor; fit it only on training data (inside a Pipeline)."""
    numeric = BASE_NUMERIC + (ENGINEERED_NUMERIC if engineer else [])
    numeric_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical_enc = OneHotEncoder(
        handle_unknown="ignore", drop="if_binary", sparse_output=False
    )
    return ColumnTransformer(
        [("num", numeric_pipe, numeric), ("cat", categorical_enc, CATEGORICAL)],
        verbose_feature_names_out=False,
    )

def make_splits(df: pd.DataFrame, write: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stratified train/test split; optionally record which IDs are in which set."""
    train_df, test_df = train_test_split(
        df,
        test_size=config.TEST_SIZE,
        stratify=df[config.TARGET_COL],
        random_state=config.SEED,
    )
    train_df = train_df.reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)
    if write:
        config.ensure_dirs()
        payload = {
            "train": train_df[config.ID_COL].tolist(),
            "test": test_df[config.ID_COL].tolist(),
        }
        config.SPLIT_IDS_JSON.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("Wrote split IDs to %s", config.SPLIT_IDS_JSON)
    return train_df, test_df

def prepare_data(
    engineer: bool = True, write: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load, clean, engineer, split. Returns (train_df, test_df) with ID and target kept."""
    cleaned = clean_and_engineer(load_raw(), engineer=engineer)
    return make_splits(cleaned, write=write)

def main() -> None:
    """CLI check: build the splits and prove the preprocessor fits and transforms."""
    config.configure_logging()
    train_df, test_df = prepare_data()
    for name, part in (("train", train_df), ("test", test_df)):
        rate = float((part[config.TARGET_COL] == "Yes").mean())
        print(f"{name}: rows={len(part)} churn_rate={rate:.4f}")

    x_train = get_features(train_df)
    print("NaN left in train features:", int(x_train.isna().sum().sum()))
    print("Engineered features (train):")
    print(train_df[ENGINEERED_NUMERIC].describe().round(2))

    prep = build_preprocessor()
    train_matrix = prep.fit_transform(x_train)  # fit on TRAIN only
    test_matrix = prep.transform(get_features(test_df))
    print("Transformed shapes:", train_matrix.shape, test_matrix.shape)

if __name__ == "__main__":
    main()