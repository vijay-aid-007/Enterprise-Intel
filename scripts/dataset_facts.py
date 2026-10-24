"""Compute real aggregate facts from the Telco CSV for grounding synthetic docs.

Read-only on data/raw. Writes data/processed/dataset_facts.md and prints it.
"""
from __future__ import annotations

import logging

import pandas as pd

from src import config

logger = logging.getLogger(__name__)

GROUP_COLS = [
    "Contract",
    "InternetService",
    "PaymentMethod",
    "PaperlessBilling",
    "TechSupport",
    "SeniorCitizen",
]


def build_facts(df: pd.DataFrame) -> str:
    """Return a markdown summary of the dataset (counts and churn rates)."""
    churn = df[config.TARGET_COL].eq("Yes")
    monthly = pd.to_numeric(df["MonthlyCharges"], errors="coerce")
    tenure = pd.to_numeric(df["tenure"], errors="coerce")
    lines = [
        "# Dataset facts (computed from telco-customer-churn.csv)",
        "",
        f"- rows: {len(df)}",
        f"- overall churn rate: {churn.mean():.1%}",
        f"- MonthlyCharges min / median / max: "
        f"{monthly.min():.2f} / {monthly.median():.2f} / {monthly.max():.2f}",
        f"- tenure (months) min / median / max: "
        f"{int(tenure.min())} / {int(tenure.median())} / {int(tenure.max())}",
    ]
    keys: dict[str, pd.Series] = {col: df[col] for col in GROUP_COLS}
    keys["tenure_band"] = pd.cut(
        tenure, bins=[-1, 12, 24, 48, 72], labels=["0-12", "13-24", "25-48", "49-72"]
    )
    for name, key in keys.items():
        table = churn.groupby(key, observed=True).agg(["size", "mean"])
        lines += ["", f"## Churn rate by {name}"]
        for value, row in table.iterrows():
            lines.append(f"- {value}: n={int(row['size'])}, churn={row['mean']:.1%}")
    return "\n".join(lines)


def main() -> int:
    """CLI entry point."""
    config.configure_logging()
    df = pd.read_csv(config.CHURN_CSV)
    text = build_facts(df)
    out = config.DATA_PROCESSED / "dataset_facts.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    logger.info("wrote %s", out)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())