"""Check how well the synthetic price list matches the REAL Telco charges.

Read-only. Part 1 fits the real MonthlyCharges on the service columns to see what
prices the data implies, next to the prices in scripts/synth_rules.py. Part 2
compares a per-customer list price (docs) with the real MonthlyCharges.
Run:  python -m scripts.check_doc_sync
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.synth_rules import ADDONS, PHONE_EXTRA, PHONE_FIRST, PLANS
from src import config

SERVICES = ["OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"]


def _fiber_price() -> int:
    """Cheapest fiber plan in the docs (the data has one 'Fiber optic' type)."""
    return min(v[1] for k, v in PLANS.items() if k.startswith("Fiber optic"))


def main() -> int:
    """Print the sync report."""
    df = pd.read_csv(config.CHURN_CSV, dtype=str, keep_default_na=False)
    y = pd.to_numeric(df["MonthlyCharges"]).to_numpy()
    flag = lambda col: (df[col] == "Yes").to_numpy(float)  # noqa: E731
    cols = [(df["PhoneService"] == "Yes").to_numpy(float), flag("MultipleLines"),
            (df["InternetService"] == "DSL").to_numpy(float),
            (df["InternetService"] == "Fiber optic").to_numpy(float), *[flag(c) for c in SERVICES]]
    names = ["Phone line", "Extra line", "DSL", "Fiber optic", *SERVICES]
    docs = [PHONE_FIRST, PHONE_EXTRA, PLANS["DSL"][1], _fiber_price(), *ADDONS.values()]
    coef, *_ = np.linalg.lstsq(np.column_stack(cols), y, rcond=None)
    print(f"{'component':20}{'data implies':>14}{'docs say':>10}")
    for name, c, d in zip(names, coef, docs):
        print(f"{name:20}{c:>14.2f}{d:>10}")

    phone = np.where(df["PhoneService"] == "Yes", PHONE_FIRST + np.where(df["MultipleLines"] == "Yes", PHONE_EXTRA, 0), 0)
    net = df["InternetService"].map({"DSL": PLANS["DSL"][1], "Fiber optic": _fiber_price(), "No": 0}).to_numpy()
    addons = sum(np.where(df[name.replace(" ", "")] == "Yes", price, 0) for name, price in ADDONS.items())
    implied = phone + net + addons
    err = np.abs(implied - y) / y
    print(f"\ncorrelation docs-vs-data: {np.corrcoef(implied, y)[0, 1]:.3f}")
    print(f"customers within 10%: {np.mean(err <= 0.10):.1%} | within 25%: {np.mean(err <= 0.25):.1%} | median error: {np.median(implied - y):+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())