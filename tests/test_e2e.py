"""End-to-end tests (spec requirement 8): the real model, index and customer table, with only the LLM faked.

They need the build artifacts (model, chunks, Chroma index, Telco CSV) and skip when any is missing. They prove
the pieces work together, not that answers are good; the evaluation does that. The first test loads the model and
the embedder, so expect it to take a few seconds.
"""
from __future__ import annotations

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src import config
from src.api import main
from src.llm.answer import answer_question
from src.llm.client import LLMResponse, ToolCall
from src.llm.report import build_report
from src.llm.report_evidence import UnknownCustomerError

REQUIRED = (config.MODEL_PATH, config.CHUNKS_JSONL, config.CHROMA_DIR, config.CHURN_CSV)
pytestmark = pytest.mark.skipif(not all(p.exists() for p in REQUIRED), reason="build artifacts not present")
_CHUNK_ID = re.compile(r'<chunk id="([^"]+)"')


class FakeLLM:
    """Implements LLMClient. Cites the first chunk it was shown, with text that has no numbers or document names,
    so the real validators accept it. Counts calls."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[Any] | None = None,
        force_tool: str | None = None,
    ) -> LLMResponse:
        self.calls += 1
        ids = _CHUNK_ID.findall(messages[0]["content"])
        assert ids, "the prompt must contain evidence chunks"
        if force_tool == "submit_answer":
            args: dict[str, Any] = {
                "answer": "The documents state the requested limit.", "citations": [ids[0]], "can_answer": True,
            }
        else:
            assert force_tool == "submit_recommendations", force_tool
            args = {"recommendations": [
                {"text": "Follow the documented playbook for this tier and contract.", "citations": [ids[0]]}
            ]}
        return LLMResponse(text="", tool_calls=[ToolCall("e2e-1", force_tool, args)])


def test_report_pipeline_with_real_model_and_index() -> None:
    fake = FakeLLM()
    report = build_report("7590-VHVEG", fake)
    evidence_ids = {c["chunk_id"] for c in report.evidence}
    assert report.status == "complete" and fake.calls == 1 and not report.withheld
    assert 0.0 < report.prediction["prob"] < 1.0 and len(report.prediction["top_drivers"]) == 5
    assert any(cid.startswith("retention_policy-") for cid in evidence_ids)
    assert set(report.recommendations[0].citations) <= evidence_ids


def test_unknown_customer_never_reaches_the_model() -> None:
    fake = FakeLLM()
    with pytest.raises(UnknownCustomerError):
        build_report("NOPE-0000", fake)
    assert fake.calls == 0


def test_api_with_real_components(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeLLM()
    monkeypatch.setattr(main, "answer_question", lambda question, **kw: answer_question(question, client=fake, **kw))
    api = TestClient(main.app)
    predicted = api.post("/predict", json={"customer_id": "7590-VHVEG"}).json()
    assert predicted["label"] in {"churn", "no_churn"} and len(predicted["top_drivers"]) == 5
    refused = api.post("/ask", json={"question": "What is the capital of France?"}).json()
    assert refused["status"] == "refused_insufficient_evidence" and fake.calls == 0
    answered = api.post("/ask", json={"question": "What is the absolute cap on any retention discount?"}).json()
    assert answered["status"] == "answered" and fake.calls == 1 and "draft_answer" not in answered
    assert answered["citation_details"][0]["chunk_id"] == answered["citations"][0]
    assert answered["citation_details"][0]["source"] and answered["notice"]