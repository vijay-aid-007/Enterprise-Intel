"""Step 7 smoke tests: every endpoint with all dependencies faked, so they are deterministic and free.

They prove wiring, validation, error mapping, and what the API refuses to return. They do not prove
the live model, index or LLM path; the manual calls in the run instructions do.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.agent.agent import AgentResult, TraceStep
from src.api import main
from src.api.schemas import SYNTHETIC_NOTICE
from src.llm.answer import GroundedAnswer
from src.llm.report import Recommendation, Report, Withheld
from src.llm.report_evidence import UnknownCustomerError
from src.rag.retriever import IndexMissingError

client = TestClient(main.app)

CHUNK_ROW = {
    "chunk_id": "t-0001",
    "text": "The maximum retention discount is 30%.",
    "source": "retention_policy.pdf",
    "location": {"page": 1},
}


@pytest.fixture(autouse=True)
def fake_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_chunk_index", lambda: {"t-0001": CHUNK_ROW})


def make_answer(**overrides: Any) -> GroundedAnswer:
    fields: dict[str, Any] = {
        "question": "q", "answer": "The cap is 30%.", "status": "answered", "citations": ["t-0001"],
        "can_answer": True, "retrieved_ids": ["t-0001"],
    }
    fields.update(overrides)
    return GroundedAnswer(**fields)


def post(path: str, payload: dict[str, Any]):
    return client.post(path, json=payload)


def test_openapi_lists_all_endpoints() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/health", "/predict", "/ask", "/agent", "/report"} <= set(paths)


def test_health_shape() -> None:
    body = client.get("/health").json()
    assert set(body) == {"status", "has_model", "has_chunks", "has_index", "llm_key_set"}
    assert body["status"] in {"ok", "degraded"}


def test_predict_happy_path_converts_numpy_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_customer_profile", lambda cid: {})
    fake = {
        "prob": np.float32(0.85), "label": "churn",
        "top_drivers": [{"feature": "tenure", "customer_value": np.int64(1),
                         "contribution": np.float32(0.8), "effect": "raises churn risk"}],
    }
    monkeypatch.setattr(main, "predict_customer", lambda cid: fake)
    response = post("/predict", {"customer_id": "7590-VHVEG"})
    body = response.json()
    assert response.status_code == 200 and body["customer_id"] == "7590-VHVEG"
    assert body["prob"] == pytest.approx(0.85) and body["top_drivers"][0]["customer_value"] == 1


def test_predict_unknown_customer_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(cid: str) -> dict:
        raise UnknownCustomerError(f"customer id not found: {cid!r}")

    monkeypatch.setattr(main, "load_customer_profile", missing)
    response = post("/predict", {"customer_id": "NOPE-0000"})
    assert response.status_code == 404 and "not found" in response.json()["detail"]


@pytest.mark.parametrize("bad_id", ["", "a b", "x" * 21, "'; DROP"])
def test_predict_rejects_malformed_ids(bad_id: str) -> None:
    assert post("/predict", {"customer_id": bad_id}).status_code == 422


def test_ask_resolves_citations_normalises_text_and_hides_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = make_answer(answer="The cap is 30\u2011percent.", draft_answer="secret draft")
    monkeypatch.setattr(main, "answer_question", lambda question, **kw: answer)
    response = post("/ask", {"question": "What is the cap?"})
    body = response.json()
    assert response.status_code == 200 and "secret draft" not in response.text
    assert body["answer"] == "The cap is 30-percent." and body["notice"] == SYNTHETIC_NOTICE
    assert body["citation_details"] == [{**CHUNK_ROW, "location": {"page": 1}}]


def test_ask_passes_k_and_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake(question: str, *, k: int, mode: str | None) -> GroundedAnswer:
        seen.update(question=question, k=k, mode=mode)
        return make_answer()

    monkeypatch.setattr(main, "answer_question", fake)
    assert post("/ask", {"question": "  max discount?  ", "k": 3, "mode": "dense"}).status_code == 200
    assert seen == {"question": "max discount?", "k": 3, "mode": "dense"}


def test_ask_rejected_draft_never_leaves_the_server(monkeypatch: pytest.MonkeyPatch) -> None:
    rejected = make_answer(
        status="rejected_validation", answer="The drafted answer failed automatic citation checks and was withheld.",
        citations=[], can_answer=False, issues=["number not found in cited chunks: 45"], draft_answer="Offer 45%.",
    )
    monkeypatch.setattr(main, "answer_question", lambda question, **kw: rejected)
    response = post("/ask", {"question": "What is the cap?"})
    assert response.status_code == 200 and "Offer 45%." not in response.text
    assert response.json()["status"] == "rejected_validation" and response.json()["citation_details"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 501},
        {"question": "q", "k": 0},
        {"question": "q", "k": 99},
        {"question": "q", "mode": "magic"},
    ],
)
def test_ask_validation(payload: dict[str, Any]) -> None:
    assert post("/ask", payload).status_code == 422


def test_agent_returns_trace_and_hides_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    result = AgentResult(
        question="q", answer="Done\u2011ish", status="answered", steps_used=1, citations=["t-0001"],
        trace=[TraceStep(1, "calculate", {"expression": "1+1"}, True, 0.01, "1+1 = 2")],
        issues=[], draft_answer="hidden draft",
    )
    monkeypatch.setattr(main, "run_agent", lambda question: result)
    response = post("/agent", {"question": "What is 1+1?"})
    body = response.json()
    assert response.status_code == 200 and "hidden draft" not in response.text
    assert body["trace"][0]["tool"] == "calculate" and body["answer"] == "Done-ish"
    assert body["notice"] == SYNTHETIC_NOTICE and body["citation_details"][0]["chunk_id"] == "t-0001"


def test_report_endpoint_returns_structured_data_and_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    built = Report(
        customer_id="7590-VHVEG",
        profile={"Contract": "Month-to-month", "InternetService": "DSL"},
        prediction={"prob": 0.85, "label": "churn", "top_drivers": [
            {"feature": "tenure", "customer_value": 1.0, "contribution": 0.8, "effect": "raises churn risk"}]},
        tier="Critical", status="partial",
        recommendations=[Recommendation("Offer 30% for 6 months.", ["t-0001"])],
        withheld=[Withheld("Offer 45%.", ["number not found in cited chunks: 45"])],
        evidence=[{**CHUNK_ROW, "score": np.float32(0.033)}], notes=["a note"],
    )
    monkeypatch.setattr(main, "build_report", lambda cid: built)
    monkeypatch.setattr(main, "write_report", lambda r: Path("report_7590-VHVEG.md"))
    monkeypatch.setattr(main, "render_markdown", lambda r: "# Churn risk report")
    body = post("/report", {"customer_id": "7590-VHVEG"}).json()
    assert body["report_file"] == "report_7590-VHVEG.md" and body["markdown"] == "# Churn risk report"
    assert body["status"] == "partial" and body["recommendations"][0]["citations"] == ["t-0001"]
    assert body["withheld"][0]["text"] == "Offer 45%." and body["evidence"][0]["score"] == pytest.approx(0.033, abs=1e-6)
    assert body["notice"] == SYNTHETIC_NOTICE


def test_report_unknown_customer_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(cid: str) -> Report:
        raise UnknownCustomerError("customer id not found")

    monkeypatch.setattr(main, "build_report", missing)
    assert post("/report", {"customer_id": "NOPE-0000"}).status_code == 404


def test_missing_index_is_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(question: str, **kw: Any) -> GroundedAnswer:
        raise IndexMissingError("run the index build")

    monkeypatch.setattr(main, "answer_question", broken)
    response = post("/ask", {"question": "q"})
    assert response.status_code == 503 and "build steps" in response.json()["detail"]


def test_missing_model_file_is_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(cid: str) -> dict:
        raise FileNotFoundError("churn_model.joblib")

    monkeypatch.setattr(main, "load_customer_profile", broken)
    assert post("/predict", {"customer_id": "7590-VHVEG"}).status_code == 503