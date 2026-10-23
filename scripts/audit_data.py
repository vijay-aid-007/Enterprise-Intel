"""Read-only audit of the raw Telco churn CSV.

Run from the repo root:  python -m scripts.audit_data
Writes a small summary to data/processed/audit.json. Never touches data/raw.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd

from src import config

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = [
    "customerID", "gender", "SeniorCitizen", "Partner", "Dependents", "tenure",
    "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity",
    "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
    "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod",
    "MonthlyCharges", "TotalCharges", "Churn",
]


def audit(df: pd.DataFrame) -> dict[str, Any]:
    """Compute a JSON-serialisable audit summary of the raw dataframe."""
    text_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    blanks = {c: int((df[c].astype(str).str.strip() == "").sum()) for c in text_cols}

    total_charges = pd.to_numeric(df["TotalCharges"], errors="coerce")
    unparseable = df.loc[total_charges.isna()]

    target = config.TARGET_COL
    level_cols = [c for c in text_cols if c not in (config.ID_COL, "TotalCharges", target)]

    return {
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "missing_expected_columns": sorted(set(EXPECTED_COLUMNS) - set(df.columns)),
        "unexpected_columns": sorted(set(df.columns) - set(EXPECTED_COLUMNS)),
        "nan_counts": {c: int(n) for c, n in df.isna().sum().items() if n > 0},
        "blank_string_counts": {c: n for c, n in blanks.items() if n > 0},
        "duplicate_customer_ids": int(df[config.ID_COL].duplicated().sum()),
        "totalcharges_dtype": str(df["TotalCharges"].dtype),
        "totalcharges_unparseable_rows": int(len(unparseable)),
        "totalcharges_unparseable_tenures": sorted(int(t) for t in unparseable["tenure"].unique()),
        "seniorcitizen_values": sorted(int(v) for v in df["SeniorCitizen"].unique()),
        "churn_counts": {str(k): int(v) for k, v in df[target].value_counts().items()},
        "churn_rate": round(float((df[target] == "Yes").mean()), 4),
        "churn_rate_by_contract": {
            str(k): round(float(v), 4)
            for k, v in df.groupby("Contract")[target].apply(lambda s: (s == "Yes").mean()).items()
        },
        "category_levels": {
            c: {str(k): int(v) for k, v in df[c].value_counts().items()} for c in level_cols
        },
    }


def main() -> None:
    """Load the raw CSV, print the audit, and save it to data/processed."""
    config.configure_logging()
    config.ensure_dirs()
    if not config.CHURN_CSV.exists():
        raise SystemExit(f"Missing input file: {config.CHURN_CSV}")

    df = pd.read_csv(config.CHURN_CSV)  # read-only: nothing is ever written back
    report = audit(df)
    text = json.dumps(report, indent=2)
    config.AUDIT_JSON.write_text(text, encoding="utf-8")

    print(text)
    print("\nNumeric summary:")
    print(df[["tenure", "MonthlyCharges"]].describe().round(2))
    logger.info("Audit written to %s", config.AUDIT_JSON)


if __name__ == "__main__":
    main()