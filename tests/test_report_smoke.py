"""Step 5 smoke tests. The LLM, predictor and retriever are faked: deterministic and free."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

from typing import Any
from types import SimpleNamespace

import pytest
from src.llm.client import LLMError, LLMResponse, ToolCall, ToolSpec
from src import config
from src.llm.report import build_report
from src.llm.report_evidence import (
    UnknownCustomerError,
    driver_queries,
    is_exact_match,
    is_off_profile,
    risk_tier,
)
from src.llm.report_render import write_report

needs_csv = pytest.mark.skipif(not config.CHURN_CSV.exists(), reason="Telco CSV not present")

EXACT = {
    "chunk_id": "t-0001",
    "source": "retention_policy.pdf",
    "score": 0.9,
    "location": {"section": "Playbook"},
    "text": "A customer on a month-to-month contract with a risk score of 0.80 and above is in the "
    "Critical tier. The maximum retention discount is 30% for 6 months.",
}
OFF = {
    "chunk_id": "t-0002",
    "source": "retention_policy.pdf",
    "score": 0.8,
    "location": {},
    "text": "A customer on a two year contract is in the Critical tier. The maximum retention discount is 30%.",
}
UNRELATED = {
    "chunk_id": "t-0003",
    "source": "plans_pricing_guide.docx",
    "score": 0.5,
    "location": {},
    "text": "The automatic payment credit is $5 per month.",
}
GOOD = {"text": "The retention policy states a 30% maximum retention discount for 6 months.", "citations": ["t-0001"]}
BAD_NUMBER = {"text": "Offer a 45% discount.", "citations": ["t-0001"]}
WRONG_PROFILE = {"text": "A 30% discount applies.", "citations": ["t-0002"]}


def fake_predictor(customer_id: str) -> dict:
    return {
        "prob": 0.85,
        "label": "churn",
        "top_drivers": [
            {"feature": "tenure", "customer_value": 1.0, "contribution": 0.8, "effect": "raises churn risk"},
            {"feature": "Contract_Month-to-month", "customer_value": "Month-to-month", "contribution": 0.5, "effect": "raises churn risk"},
            {"feature": "InternetService_Fiber optic", "customer_value": "DSL", "contribution": -0.3, "effect": "lowers churn risk"},
        ],
    }


def make_retriever(chunks: list[dict]):
    def retriever(question, k, *, mode=None, doc_types=None):
        return list(chunks), SimpleNamespace(reason="ok")

    return retriever

class FakeClient:
    """Implements the LLMClient protocol with real LLMResponse/ToolCall objects, so a change to
    those dataclasses breaks these tests instead of passing silently. Counts calls so tests can
    prove the LLM was or was not used."""

    def __init__(self, items: list[dict[str, Any]] | None = None, error: Exception | None = None) -> None:
        self.items: list[dict[str, Any]] = items or []
        self.error = error
        self.calls = 0

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
        force_tool: str | None = None,
    ) -> LLMResponse:
        self.calls += 1
        if self.error:
            raise self.error
        call = ToolCall("1", "submit_recommendations", {"recommendations": self.items})
        return LLMResponse(text="", tool_calls=[call])


def test_risk_tier_boundaries() -> None:
    expected = [(0.0, "Low"), (0.3499, "Low"), (0.35, "Medium"), (0.5999, "Medium"),
                (0.60, "High"), (0.7999, "High"), (0.80, "Critical"), (1.0, "Critical")]
    for prob, tier in expected:
        assert risk_tier(prob) == tier, prob


def test_tier_bands_appear_in_policy_text() -> None:
    if not config.CHUNKS_JSONL.exists():
        pytest.skip("chunks.jsonl not present")
    lines = config.CHUNKS_JSONL.read_text(encoding="utf-8").splitlines()
    chunks = [json.loads(line) for line in lines if line.strip()]
    text = " ".join(c["text"] for c in chunks if c["source"] == "retention_policy.pdf")
    for name, lower in config.TIER_BANDS[1:]:
        assert f"{lower:.2f}" in text, f"{name} band {lower:.2f} not found in policy chunks"


def test_profile_matching() -> None:
    assert is_off_profile("A customer on a two year contract is in the High tier.", "Critical", "Month-to-month")
    assert not is_off_profile(EXACT["text"], "Critical", "Month-to-month")
    assert not is_off_profile("The absolute cap on any retention discount is 30 percent.", "Critical", "Month-to-month")
    assert not is_off_profile("Low tier, Medium tier, High tier and Critical tier customers.", "High", "One year")
    assert is_exact_match(EXACT["text"], "Critical", "Month-to-month")
    assert not is_exact_match(OFF["text"], "Critical", "Month-to-month")


def test_driver_queries_only_raising_one_hot() -> None:
    drivers = fake_predictor("x")["top_drivers"]
    assert driver_queries(drivers, 2) == ["Contract Month-to-month customers retention offer"]


@needs_csv
def test_happy_path_validates_filters_and_withholds() -> None:
    client = FakeClient(items=[GOOD, BAD_NUMBER, WRONG_PROFILE])
    report = build_report("7590-VHVEG", client, predictor=fake_predictor, retriever=make_retriever([EXACT, OFF]))
    assert report.tier == "Critical"
    assert report.status == "partial"
    assert [r.citations for r in report.recommendations] == [["t-0001"]]
    assert len(report.withheld) == 2
    assert [c["chunk_id"] for c in report.evidence] == ["t-0001"]
    assert any("t-0002" in n for n in report.notes)
    assert any("SYNTHETIC" in n for n in report.notes)
    assert client.calls == 1


@needs_csv
def test_no_exact_playbook_chunk_skips_llm() -> None:
    client = FakeClient(items=[GOOD])
    report = build_report("7590-VHVEG", client, predictor=fake_predictor, retriever=make_retriever([UNRELATED]))
    assert client.calls == 0
    assert report.status == "no_recommendations"
    assert any("No retrieved chunk" in n for n in report.notes)


@needs_csv
def test_llm_error_degrades_to_report_without_recommendations() -> None:
    client = FakeClient(error=LLMError("boom"))
    report = build_report("7590-VHVEG", client, predictor=fake_predictor, retriever=make_retriever([EXACT]))
    assert report.status == "no_recommendations"
    assert report.prediction["prob"] == 0.85
    assert any("failed" in n for n in report.notes)


@needs_csv
def test_unknown_customer_fails_before_predictor() -> None:
    def boom(_: str) -> dict:
        raise AssertionError("predictor must not run for unknown ids")

    with pytest.raises(UnknownCustomerError):
        build_report("NOPE-0000", FakeClient(), predictor=boom, retriever=make_retriever([]))


@needs_csv
def test_write_report_is_utf8_markdown(tmp_path) -> None:
    client = FakeClient(items=[GOOD, BAD_NUMBER])
    report = build_report("7590-VHVEG", client, predictor=fake_predictor, retriever=make_retriever([EXACT]))
    path = write_report(report, tmp_path)
    content = path.read_text(encoding="utf-8")
    assert path.name == "report_7590-VHVEG.md"
    assert "Withheld by validation" in content and "Offer a 45% discount." in content
    assert "`t-0001`" in content


@pytest.mark.skipif(os.environ.get("RUN_LIVE_LLM") != "1", reason="manual live smoke test")
def test_live_report_for_real_customer(tmp_path) -> None:
    report = build_report("7590-VHVEG")
    assert report.status in {"complete", "partial", "no_recommendations"}
    assert write_report(report, tmp_path).exists()

LOW = {
    "chunk_id": "t-0004",
    "source": "facts_sheet.md",
    "score": 0.7,
    "location": {},
    "text": "A customer on a month-to-month contract in the Low tier has a combined discount ceiling "
    "of 0% (0% contract plus 0% retention).",
}


def test_clean_normalizes_hyphens_and_spaces() -> None:
    from src.llm.report import _clean

    assert _clean("one\u2011time\u202f$50 retention\u2011manager") == "one-time $50 retention-manager"


def test_ceiling_query_mimics_lookup_heading() -> None:
    from src.llm.report_evidence import ceiling_query

    assert "Low tier, one year contract" in ceiling_query("Low", "One year")


@needs_csv
def test_low_tier_uses_lookup_chunk_and_calls_llm() -> None:
    def low_predictor(_: str) -> dict:
        return {"prob": 0.05, "label": "no_churn", "top_drivers": []}

    rec = {"text": "The facts sheet states a combined discount ceiling of 0%.", "citations": ["t-0004"]}
    client = FakeClient(items=[rec])
    report = build_report("7590-VHVEG", client, predictor=low_predictor, retriever=make_retriever([LOW]))
    assert report.tier == "Low" and report.status == "complete" and client.calls == 1

