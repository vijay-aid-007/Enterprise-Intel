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
SYNTHETIC_DOCS: frozenset[str] = frozenset(DOC_FILES)  # all five are synthetic; see scripts/make_synthetic_docs.py
CHUNKS_JSONL: Path = DATA_PROCESSED / "chunks.jsonl"
CHUNK_MAX_CHARS: int = 900  # ~200 tokens; MiniLM truncates at 256 tokens


# --- RAG (Step 3) ---
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_DIR = INDEXES_DIR / "chroma"
CHROMA_COLLECTION = "chunks"
RETRIEVAL_MODE = "hybrid"          # "dense" | "bm25" | "hybrid"
RRF_K = 60                         # standard RRF constant
CANDIDATES_PER_BACKEND = 20        # each backend contributes its top-N to fusion
DENSE_MIN_SIM = 0.30  # frozen from the dev sweep: lowest value above the best dev out-of-scope score (0.290) that refuses no answerable dev question
BM25_MIN_SCORE = 0.0               # disabled until tuned


# ---------------------------------------------------------------- LLM / generation (Step 4)
from pathlib import Path

ENV_FILE: Path = Path(__file__).resolve().parents[1] / ".env"
LLM_TEMPERATURE: float = 0.0
LLM_MAX_TOKENS: int = 1024
LLM_TIMEOUT_S: float = 60.0
GEN_K: int = 5
GEN_DOC_TYPES: tuple[str, ...] = ("markdown", "pdf", "docx")  # excludes support tickets (csv)
LLM_RATE_RETRIES: int = 3        # extra attempts after a 429; the Groq on_demand limit seen was 8000 tokens/minute
LLM_RATE_MAX_WAIT_S: float = 30.0

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
REPORT_MAX_DRIVER_QUERIES: int = 0  # off: added only noise on the 5 reports seen
REPORT_MAX_RECOMMENDATIONS: int = 4

# ---------------------------------------------------------------- Agent (Step 6)
AGENT_MAX_STEPS: int = 5            # tool calls per question (rule 9)
AGENT_TOOL_TIMEOUT_S: float = 60.0  # stops WAITING for a tool; a stuck thread cannot be killed
AGENT_RESULT_MAX_CHARS: int = 6000  # cap on one tool result sent back to the model
AGENT_MAX_ROWS: int = 20            # groups returned by analyze_data
AGENT_MAX_FILTERS: int = 5
AGENT_CALC_MAX_CHARS: int = 100
AGENT_SEARCH_MAX_K: int = 5
AGENT_MAX_SEARCHES: int = 3

# ---------------------------------------------------------------- API (Step 7)
API_HOST: str = "127.0.0.1"
API_PORT: int = 8000
API_MAX_QUESTION_CHARS: int = 500
API_MAX_K: int = 8

# ---------------------------------------------------------------- UI (Step 8)
UI_FAST_TIMEOUT_S: float = 30.0    # /health and /predict
UI_SLOW_TIMEOUT_S: float = 240.0   # /ask, /agent, /report: first call loads the embedder; Groq 429 retries wait

# ---------------------------------------------------------------- Eval (Step 9)
GOLD_JSON: Path = EVAL_DIR / "gold_questions.json"
EVAL_KS: tuple[int, ...] = (1, 3, 5)
EVAL_MAX_RANK: int = 10
EVAL_SWEEP: tuple[float, ...] = (0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70)  

EVAL_LLM_CACHE: Path = EVAL_DIR / "cache" / "llm_cache.jsonl"
EVAL_LLM_MIN_INTERVAL_S: float = 20.0  # spacing between real model calls; Groq on_demand allows about 8000 tokens per minute


def use_utf8_stdout() -> None:
    """Print UTF-8 even when stdout is redirected: Windows redirects with cp1252, which cannot encode U+2011.

    sys.stdout is typed TextIO, which has no reconfigure(); the isinstance check narrows it to TextIOWrapper.
    """
    import io
    import sys

    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8")
