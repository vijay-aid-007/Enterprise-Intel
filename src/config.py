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


# --- RAG (Step 3) ---
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_DIR = INDEXES_DIR / "chroma"
CHROMA_COLLECTION = "chunks"
RETRIEVAL_MODE = "hybrid"          # "dense" | "bm25" | "hybrid"
RRF_K = 60                         # standard RRF constant
CANDIDATES_PER_BACKEND = 20        # each backend contributes its top-N to fusion
DENSE_MIN_SIM = 0.25               # UNTUNED placeholder: tune on dev gold questions (Step 9)
BM25_MIN_SCORE = 0.0               # disabled until tuned


# ---------------------------------------------------------------- LLM / generation (Step 4)
from pathlib import Path

ENV_FILE: Path = Path(__file__).resolve().parents[1] / ".env"
LLM_TEMPERATURE: float = 0.0
LLM_MAX_TOKENS: int = 1024
LLM_TIMEOUT_S: float = 60.0
GEN_K: int = 5
GEN_DOC_TYPES: tuple[str, ...] = ("markdown", "pdf", "docx")  # excludes support tickets (csv)


# ---------------------------------------------------------------- Report (Step 5)
# Risk-tier lower bounds read by hand from the SYNTHETIC retention policy:
# "Medium 0.35 to 0.59", "High 0.60 to 0.79", "Critical 0.80 and above".
# The Low band (below 0.35) is my inference. tests/test_report_smoke.py checks these
# numbers against chunks.jsonl so code and document cannot drift apart silently.
TIER_BANDS: tuple[tuple[str, float], ...] = (
    ("Low", 0.0),
    ("Medium", 0.35),
    ("High", 0.60),
    ("Critical", 0.80),
)
REPORT_DIR: Path = DATA_PROCESSED / "reports"
REPORT_K: int = 5
REPORT_MAX_CHUNKS: int = 8
REPORT_MAX_DRIVER_QUERIES: int = 2
REPORT_MAX_RECOMMENDATIONS: int = 4

# ---------------------------------------------------------------- Agent (Step 6)
AGENT_MAX_STEPS: int = 5            # tool calls per question (rule 9)
AGENT_TOOL_TIMEOUT_S: float = 60.0  # stops WAITING for a tool; a stuck thread cannot be killed
AGENT_RESULT_MAX_CHARS: int = 6000  # cap on one tool result sent back to the model
AGENT_MAX_ROWS: int = 20            # groups returned by analyze_data
AGENT_MAX_FILTERS: int = 5
AGENT_CALC_MAX_CHARS: int = 100
AGENT_SEARCH_MAX_K: int = 8