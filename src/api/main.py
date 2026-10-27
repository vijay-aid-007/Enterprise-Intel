"""FastAPI app: a thin HTTP layer over the Step 1-6 functions.

No business logic lives here. Each endpoint validates input (schemas.py), calls one existing function
and shapes the result. Endpoints are plain `def`, so FastAPI runs the blocking model, retrieval and LLM
calls in its thread pool instead of freezing the event loop.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src import config
from src.agent.agent import run_agent
from src.api.schemas import (
    AgentRequest,
    AgentResponse,
    AskRequest,
    AskResponse,
    CustomerRequest,
    HealthResponse,
    PredictResponse,
    ReportResponse,
)
from src.llm.answer import answer_question
from src.llm.client import load_env_file
from src.llm.report import build_report, normalize_text
from src.llm.report_evidence import UnknownCustomerError, load_customer_profile
from src.llm.report_render import render_markdown, write_report
from src.ml.explain import predict_customer
from src.rag.retriever import IndexMissingError, IndexOutOfDateError

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "A required data, model or index file is missing or out of date. Run the build steps first."

app = FastAPI(
    title="Autonomous Enterprise Intelligence Platform",
    version="1.0",
    description="Churn prediction, cited document Q&A, tool-using agent and retention reports. "
    "Documents are SYNTHETIC; the Telco CSV is real.",
)


# ---------------------------------------------------------------- error mapping
@app.exception_handler(UnknownCustomerError)
async def _unknown_customer(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def _unavailable(_: Request, exc: Exception) -> JSONResponse:
    logger.error("dependency unavailable: %s: %s", type(exc).__name__, exc)
    return JSONResponse(status_code=503, content={"detail": UNAVAILABLE_DETAIL})


for _exc_type in (IndexMissingError, IndexOutOfDateError, FileNotFoundError):
    app.add_exception_handler(_exc_type, _unavailable)


# ---------------------------------------------------------------- helpers
@lru_cache(maxsize=1)
def _chunk_index() -> dict[str, dict[str, Any]]:
    """chunks.jsonl as {chunk_id: row}, read once."""
    rows: dict[str, dict[str, Any]] = {}
    with config.CHUNKS_JSONL.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                rows[row["chunk_id"]] = row
    return rows


def resolve_citations(chunk_ids: list[str]) -> list[dict[str, Any]]:
    """Source, location and text for cited ids. The validators already guarantee the ids exist."""
    index = _chunk_index()
    return [
        {
            "chunk_id": cid,
            "source": row.get("source", ""),
            "location": row.get("location") or {},
            "text": row.get("text", ""),
        }
        for cid in chunk_ids
        if (row := index.get(cid)) is not None
    ]


def _shape_answer(data: dict[str, Any]) -> dict[str, Any]:
    """Drop the withheld draft, normalise odd characters, attach citation details."""
    data.pop("draft_answer", None)
    data["answer"] = normalize_text(data["answer"])
    data["citation_details"] = resolve_citations(data["citations"])
    return data


# ---------------------------------------------------------------- endpoints
@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, Any]:
    """Cheap readiness check: files exist and an LLM key is configured. Calls no model."""
    load_env_file()
    flags = {
        "has_model": config.MODEL_PATH.exists(),
        "has_chunks": config.CHUNKS_JSONL.exists(),
        "has_index": config.CHROMA_DIR.exists(),
        "llm_key_set": bool(os.environ.get("GROQ_API_KEY", "").strip()),
    }
    return {"status": "ok" if all(flags.values()) else "degraded", **flags}


@app.post("/predict", response_model=PredictResponse)
def predict(req: CustomerRequest) -> dict[str, Any]:
    """Churn probability, label and top SHAP drivers. Works only for ids in the Telco CSV."""
    load_customer_profile(req.customer_id)  # raises UnknownCustomerError -> 404
    return {"customer_id": req.customer_id, **predict_customer(req.customer_id)}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> dict[str, Any]:
    """Grounded, cited answer from the documents. Refusals and rejections come back as statuses."""
    result = answer_question(req.question, k=req.k, mode=req.mode)
    return _shape_answer(result.to_dict())


@app.post("/agent", response_model=AgentResponse)
def agent(req: AgentRequest) -> dict[str, Any]:
    """Tool-using agent (max steps and timeouts come from config). Returns the full tool trace."""
    return _shape_answer(run_agent(req.question).to_dict())


@app.post("/report", response_model=ReportResponse)
def report(req: CustomerRequest) -> dict[str, Any]:
    """Build, save and return the churn-risk report for one customer."""
    result = build_report(req.customer_id)  # raises UnknownCustomerError -> 404
    path = write_report(result)
    data = result.to_dict()
    data["report_file"] = path.name
    data["markdown"] = render_markdown(result)
    return data


def main() -> None:
    """Run the API: python -m src.api.main (no --reload: every reload would reload the embedder)."""
    import uvicorn

    config.configure_logging()
    for noisy in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)


if __name__ == "__main__":
    main()