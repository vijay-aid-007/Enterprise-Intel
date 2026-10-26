"""Report helpers: customer profile, risk tier, and selection of evidence for one customer.

No policy number lives here. This module only decides WHICH retrieved chunks the LLM may see.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, Callable

import pandas as pd

from src import config

logger = logging.getLogger(__name__)

# Retriever contract: (question, k, *, mode, doc_types) -> (chunks, evidence_with_.reason)
Retriever = Callable[..., tuple[list[dict[str, Any]], Any]]

PROFILE_COLUMNS: tuple[str, ...] = (
    "Contract",
    "InternetService",
    "tenure",
    "MonthlyCharges",
    "PaymentMethod",
)

_TIER_RE = re.compile(r"\b(low|medium|high|critical) tier\b", re.IGNORECASE)
_CONTRACT_RE = re.compile(r"\b(month-to-month|one year|two year) contract\b", re.IGNORECASE)


class UnknownCustomerError(ValueError):
    """The customer id is not in the Telco CSV (predict_customer supports CSV ids only)."""


@lru_cache(maxsize=1)
def _customers() -> pd.DataFrame:
    """Raw Telco CSV as strings, indexed by customer id."""
    return pd.read_csv(config.CHURN_CSV, dtype=str).set_index(config.ID_COL)


def load_customer_profile(customer_id: str) -> dict[str, str]:
    """Raw CSV fields the report needs. Raises UnknownCustomerError for ids not in the CSV."""
    frame = _customers()
    if customer_id not in frame.index:
        raise UnknownCustomerError(
            f"customer id not found in {config.CHURN_CSV.name}: {customer_id!r}"
        )
    row = frame.loc[customer_id]
    return {col: str(row[col]) for col in PROFILE_COLUMNS}


def risk_tier(prob: float) -> str:
    """Highest band whose lower bound is <= prob.

    Bands are treated as half-open because the policy text leaves 0.59-0.60 undefined.
    """
    tier = config.TIER_BANDS[0][0]
    for name, lower in config.TIER_BANDS:
        if prob >= lower:
            tier = name
    return tier


def _mentions(text: str) -> tuple[set[str], set[str]]:
    """Tier names and contract types a chunk talks about, lower-cased."""
    tiers = {m.lower() for m in _TIER_RE.findall(text)}
    contracts = {m.lower() for m in _CONTRACT_RE.findall(text)}
    return tiers, contracts


def is_exact_match(text: str, tier: str, contract: str) -> bool:
    """True if the chunk names both this customer's tier and contract type."""
    tiers, contracts = _mentions(text)
    return tier.lower() in tiers and contract.lower() in contracts


def is_off_profile(text: str, tier: str, contract: str) -> bool:
    """True if the chunk names tiers or contract types but not this customer's."""
    tiers, contracts = _mentions(text)
    wrong_tier = bool(tiers) and tier.lower() not in tiers
    wrong_contract = bool(contracts) and contract.lower() not in contracts
    return wrong_tier or wrong_contract


def playbook_query(tier: str, contract: str) -> str:
    """Query phrased like the Appendix A headings, to pull the exact tier/contract chunk."""
    return (
        f"Playbook by tier and contract: {tier} tier, {contract} customer. "
        "Maximum retention discount, approval and combined discount ceiling"
    )

def heading_query(tier: str, contract: str) -> str:
    """Query that copies the Appendix A chunk heading only (reaches Low-tier playbook chunks)."""
    return f"Appendix A. Playbook by tier and contract > {tier} tier, {contract} customer"

def ceiling_query(tier: str, contract: str) -> str:
    """Query phrased like the facts-sheet 'Discount ceiling' headings (reaches tiers Appendix A lacks)."""
    return (
        f"Discount ceiling: {tier} tier, {contract.lower()} contract. "
        "Combined discount ceiling: contract discount plus retention discount"
    )

def driver_queries(drivers: list[dict[str, Any]], limit: int) -> list[str]:
    """Queries for one-hot drivers that raise churn risk, e.g. 'Contract_Month-to-month'."""
    if limit <= 0:
        return []
    
    queries: list[str] = []
    for driver in drivers:
        if float(driver.get("contribution", 0.0)) <= 0:
            continue
        column, _, value = str(driver.get("feature", "")).partition("_")
        query = f"{column} {value} customers retention offer"
        if value and query not in queries:
            queries.append(query)
        if len(queries) >= limit:
            break
    return queries


def gather_evidence(
    profile: dict[str, str],
    tier: str,
    drivers: list[dict[str, Any]],
    retriever: Retriever,
    k: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Retrieve, drop off-profile chunks, put exact tier/contract matches first.

    Returns (chunks to show the LLM, ids of chunks excluded as off-profile).
    """
    contract = profile["Contract"]
    queries = [
        playbook_query(tier, contract),
        heading_query(tier, contract),
        ceiling_query(tier, contract),
        *driver_queries(drivers, config.REPORT_MAX_DRIVER_QUERIES),
    ]
    merged: dict[str, dict[str, Any]] = {}
    dropped: list[str] = []
    for query in queries:
        chunks, evidence = retriever(query, k, mode=None, doc_types=config.GEN_DOC_TYPES)
        logger.info("report retrieval %r -> %d chunks (%s)", query, len(chunks), evidence.reason)
        for chunk in chunks:
            cid = chunk["chunk_id"]
            if is_off_profile(chunk["text"], tier, contract):
                if cid not in dropped:
                    dropped.append(cid)
            else:
                merged.setdefault(cid, chunk)
    ordered = sorted(merged.values(), key=lambda c: not is_exact_match(c["text"], tier, contract))
    return ordered[: config.REPORT_MAX_CHUNKS], dropped