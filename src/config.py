"""Central configuration: paths, seeds, split settings, logging helpers.

Every other module imports paths from here. Nothing else hard-codes a path.
"""
from __future__ import annotations

import logging
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

DATA_RAW: Path = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED: Path = PROJECT_ROOT / "data" / "processed"
MODELS_DIR: Path = PROJECT_ROOT / "models"
INDEXES_DIR: Path = PROJECT_ROOT / "indexes"
EVAL_DIR: Path = PROJECT_ROOT / "eval"
RESULTS_DIR: Path = EVAL_DIR / "results"

CHURN_CSV: Path = DATA_RAW / "telco-customer-churn.csv"
SPLIT_IDS_JSON: Path = DATA_PROCESSED / "split_ids.json"
AUDIT_JSON: Path = DATA_PROCESSED / "audit.json"
MODEL_PATH: Path = MODELS_DIR / "churn_model.joblib"
METRICS_JSON: Path = MODELS_DIR / "metrics.json"

ID_COL: str = "customerID"
TARGET_COL: str = "Churn"

SEED: int = 42
TEST_SIZE: float = 0.2
CV_FOLDS: int = 5


def ensure_dirs() -> None:
    """Create every output directory the project writes to (idempotent)."""
    for directory in (DATA_PROCESSED, MODELS_DIR, INDEXES_DIR, RESULTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def configure_logging(level: int = logging.INFO) -> None:
    """Set up one consistent log format for scripts and CLI entry points."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

# --- Step 2: documents / chunking ---
DOC_FILES: tuple[str, ...] = (
    "facts_sheet.md",
    "retention_policy.pdf",
    "plans_pricing_guide.docx",
    "service_terms.pdf",
    "support_tickets.csv",
)
SYNTHETIC_DOCS: frozenset[str] = frozenset(DOC_FILES)  # all five are LLM-generated
CHUNKS_JSONL: Path = DATA_PROCESSED / "chunks.jsonl"
CHUNK_MAX_CHARS: int = 900  # ~200 tokens; MiniLM truncates at 256 tokens