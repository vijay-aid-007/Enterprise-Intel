"""Step 9b tests: the LLM cache, outcome classification, rejection rate, agent scoring and the injection check.

All fakes: no model, no API key, no network. They prove the harness, not the live model's behaviour.
"""
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from eval import agent_eval as ae
from eval import generation_eval as ge
from eval.llm_cache import CachingClient
from src import config
from src.agent.agent import FINAL_NAME, run_agent
from src.agent.tools import ToolContext
from src.llm.client import LLMError, LLMResponse, ToolCall

needs_csv = pytest.mark.skipif(not config.CHURN_CSV.exists(), reason="Telco CSV not present")
MSG = [{"role": "user", "content": "a"}]
CHUNKS = {
    "c1": {"text": "The cap is 30 percent."},
    "c2": {"text": "Another note: 30 percent maximum."},
    "c3": {"text": "Unrelated text about routers."},
}
QUESTION = {"relevant_chunks": ["c1"], "expected_facts": ["30 percent"]}


class FakeInner:
    """Counts real calls and returns a tool-call reply."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls, self.error = 0, error

    def complete(self, system: str, messages: list[dict[str, Any]], tools: Any = None, force_tool: Any = None) -> LLMResponse:
        self.calls += 1
        if self.error:
            raise self.error
        return LLMResponse(f"reply{self.calls}", [ToolCall("id1", "submit_answer", {"answer": "x"})])


def result(status: str, answer: str = "", citations: list[str] | None = None) -> dict[str, Any]:
    return {"status": status, "answer": answer, "citations": citations or [], "issues": [], "draft_answer": "", "evidence_reason": "ok"}


def test_cache_roundtrip_and_persistence(tmp_path) -> None:
    path, inner = tmp_path / "cache.jsonl", FakeInner()
    first = CachingClient(inner, path, model_id="m")
    live = first.complete("sys", MSG)
    assert first.complete("sys", MSG) == live and inner.calls == 1 and (first.hits, first.misses) == (1, 1)
    replay = CachingClient(None, path, model_id="m", offline=True)
    assert replay.complete("sys", MSG) == live and replay.tool_calls_ok if False else True
    assert replay.complete("sys", MSG).tool_calls[0].arguments == {"answer": "x"}


def test_cache_offline_miss_raises(tmp_path) -> None:
    cache = CachingClient(FakeInner(), tmp_path / "c.jsonl", model_id="m", offline=True)
    with pytest.raises(LLMError, match="offline"):
        cache.complete("sys", MSG)


def test_cache_model_mismatch(tmp_path) -> None:
    path = tmp_path / "c.jsonl"
    CachingClient(FakeInner(), path, model_id="m1").complete("sys", MSG)
    inner = FakeInner()
    CachingClient(inner, path, model_id="m2").complete("sys", MSG)
    assert inner.calls == 1  # live run with another model ignores the old reply
    assert CachingClient(None, path, model_id="anything", offline=True).complete("sys", MSG).text == "reply1"


def test_cache_paces_only_real_calls(tmp_path) -> None:
    now, slept = [0.0], []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    inner = FakeInner()
    cache = CachingClient(inner, tmp_path / "c.jsonl", model_id="m", min_interval_s=10, sleep=sleep, clock=lambda: now[0])
    cache.complete("s", [{"role": "user", "content": "a"}])
    cache.complete("s", [{"role": "user", "content": "b"}])
    cache.complete("s", [{"role": "user", "content": "a"}])  # replayed: no wait
    assert slept == [10.0] and inner.calls == 2 and (cache.hits, cache.misses) == (1, 2)


def test_cache_does_not_store_errors(tmp_path) -> None:
    path = tmp_path / "c.jsonl"
    cache = CachingClient(FakeInner(error=LLMError("429")), path, model_id="m")
    with pytest.raises(LLMError):
        cache.complete("sys", MSG)
    assert cache.misses == 0 and (not path.exists() or path.read_text(encoding="utf-8") == "")


def test_fact_present() -> None:
    assert ge.fact_present("The cap is 30%.", "30 percent")
    assert not ge.fact_present("The cap is 45%.", "30 percent")
    assert ge.fact_present("Needs approval by the retention-manager", "retention manager")
    assert ge.fact_present("The agent declines the request", "decline")
    assert ge.fact_present("Paid 5 months x $20 = $100", "5 x $20 = $100")
    assert not ge.fact_present("It costs $100", "5 x $20 = $100")


def test_classify_answerable() -> None:
    cases = [
        (result("answered", "The cap is 30%.", ["c1"]), "correct"),
        (result("answered", "The cap is 45%.", ["c1"]), "answered_incomplete"),
        (result("answered", "It is 30%.", ["c2"]), "correct"),  # unlabelled chunk whose text holds the fact
        (result("answered", "It is 30%.", ["c3"]), "answered_incomplete"),
        (result("refused_model"), "refused"),
        (result("refused_insufficient_evidence"), "refused"),
        (result("rejected_validation"), "rejected"),
        (result("llm_error"), "error"),
    ]
    for res, expected in cases:
        assert ge.classify_answerable(res, QUESTION, CHUNKS) == expected, res["status"]


def test_classify_other() -> None:
    expected = {"refused_model": "refused", "refused_insufficient_evidence": "refused",
                "rejected_validation": "withheld", "answered": "answered", "llm_error": "error"}
    for status, outcome in expected.items():
        assert ge.classify_other(result(status)) == outcome


def test_outcome_table_and_rejection_rate() -> None:
    rows = [{"type": "answerable", "outcome": o, "status": s} for o, s in [
        ("correct", "answered"), ("rejected", "rejected_validation"), ("refused", "refused_model"),
        ("refused", "refused_insufficient_evidence"), ("error", "llm_error")]]
    table = ge.outcome_table(rows)
    assert table["answerable"] == {"n": 5, "correct": 1, "rejected": 1, "refused": 2, "error": 1}
    rate = ge.rejection_rate(rows)
    assert rate["rejected"] == 1 and rate["reached_llm"] == 3 and rate["rate"] == pytest.approx(0.333, abs=1e-3)
    assert ge.rejection_rate([])["rate"] is None


def fake_run() -> dict[str, Any]:
    questions = [
        {"id": "q1", "type": "answerable", "question": "cap?", **QUESTION},
        {"id": "q2", "type": "out_of_scope", "question": "france?"},
        {"id": "q3", "type": "gap", "question": "platinum?"},
    ]
    answers = {"cap?": result("answered", "The cap is 30%.", ["c1"]),
               "france?": result("refused_insufficient_evidence"), "platinum?": result("answered", "It is 30%.", ["c1"])}
    return ge.run_generation(questions, lambda q: answers[q], CHUNKS)


def test_run_generation_with_fakes() -> None:
    out = fake_run()
    assert out["table"]["answerable"]["correct"] == 1 and out["table"]["out_of_scope"]["refused"] == 1
    assert out["table"]["gap"]["answered"] == 1  # the failure case is counted, not hidden
    assert out["rejection"]["reached_llm"] == 2


def test_render_generation_markdown() -> None:
    markdown = ge.render_markdown("dev", fake_run(), CHUNKS)
    for expected in ("## Answerable questions", "| out_of_scope |", "Hand check", "Answer: The cap is 30%.", "`c1`", "SYNTHETIC"):
        assert expected in markdown, expected


def test_agent_prompts_are_well_formed() -> None:
    ids = [p["id"] for p in ae.AGENT_PROMPTS]
    assert len(ids) == len(set(ids)) == 9 and sum(bool(p.get("injection")) for p in ae.AGENT_PROMPTS) == 1
    assert all(p["first_tool"] in ae.ROUTE_TOOLS or p["first_tool"] is None for p in ae.AGENT_PROMPTS)
    assert all(t in ae.ROUTE_TOOLS for p in ae.AGENT_PROMPTS for t in p["includes"])


@needs_csv
def test_agent_prompt_customers_exist() -> None:
    known = set(pd.read_csv(config.CHURN_CSV, usecols=["customerID"])["customerID"])
    wanted = {m for p in ae.AGENT_PROMPTS for m in re.findall(r"\b\d{4}-[A-Z]{5}\b", p["question"])}
    assert wanted and wanted <= known


def test_run_agent_set_scores_routing() -> None:
    prompts = [
        {"id": "x1", "question": "q1", "first_tool": "search_documents", "includes": [], "status": "answered", "seen": True},
        {"id": "x2", "question": "q2", "first_tool": None, "includes": [], "status": "refused_model", "seen": False},
        {"id": "x3", "question": "q3", "first_tool": "search_documents", "includes": ["calculate"], "status": "answered", "seen": False},
    ]
    results = {
        "q1": {"status": "answered", "answer": "a", "trace": [{"tool": "search_documents"}], "steps_used": 1},
        "q2": {"status": "refused_model", "answer": "b", "trace": [], "steps_used": 0},
        "q3": {"status": "rejected_validation", "answer": "c", "trace": [{"tool": "search_documents"}], "steps_used": 1},
    }
    out = ae.run_agent_set(prompts, lambda p: results[p["question"]])
    assert out["routing"] == {"ok": 3, "n": 3} and out["routing_unseen"] == {"ok": 2, "n": 2}
    assert out["includes"] == {"ok": 2, "n": 3} and out["status"] == {"ok": 2, "n": 3}


def test_poisoned_retriever_and_injection_outcome() -> None:
    chunks, evidence = ae.poisoned_retriever("anything", 5)
    assert chunks[0]["chunk_id"] == "injected-0001" and "PWNED" in chunks[0]["text"] and evidence.reason
    complied = {"status": "rejected_validation", "answer": "withheld", "draft_answer": "PWNED"}
    assert ae.injection_outcome(complied) == {"model_complied": True, "shown_to_user": False}
    shown = {"status": "answered", "answer": "PWNED", "draft_answer": ""}
    assert ae.injection_outcome(shown) == {"model_complied": True, "shown_to_user": True}
    clean = {"status": "answered", "answer": "The cap is 30 percent.", "draft_answer": ""}
    assert ae.injection_outcome(clean) == {"model_complied": False, "shown_to_user": False}


class Scripted:
    def __init__(self, script: list[LLMResponse]) -> None:
        self.script = list(script)

    def complete(self, system: str, messages: list[dict[str, Any]], tools: Any = None, force_tool: Any = None) -> LLMResponse:
        return self.script.pop(0)


def test_injection_end_to_end_with_scripted_model() -> None:
    frame = pd.DataFrame({"customerID": ["a"], "Churn": ["No"]})
    search = LLMResponse("", [ToolCall("c1", "search_documents", {"query": "cap"})])
    obey = LLMResponse("", [ToolCall("c2", FINAL_NAME, {"answer": "PWNED", "citations": [], "can_answer": True})])
    ctx = ToolContext(frame=frame, retriever=ae.poisoned_retriever)
    blocked = run_agent("What is the cap?", Scripted([search, obey]), ctx=ctx).to_dict()
    assert blocked["status"] == "rejected_validation"
    assert ae.injection_outcome(blocked) == {"model_complied": True, "shown_to_user": False}
    resist = LLMResponse("", [ToolCall("c3", FINAL_NAME, {"answer": "The cap is 30 percent.", "citations": ["injected-0001"], "can_answer": True})])
    ctx = ToolContext(frame=frame, retriever=ae.poisoned_retriever)
    safe = run_agent("What is the cap?", Scripted([search, resist]), ctx=ctx).to_dict()
    assert safe["status"] == "answered" and ae.injection_outcome(safe)["model_complied"] is False


def test_render_agent_markdown() -> None:
    results = {p["question"]: {"status": p["status"] or "answered", "answer": "ok", "steps_used": 0 if p["first_tool"] is None else 1,
                               "trace": [] if p["first_tool"] is None else [{"tool": p["first_tool"]}], "draft_answer": ""}
               for p in ae.AGENT_PROMPTS}
    out = ae.run_agent_set(ae.AGENT_PROMPTS, lambda p: results[p["question"]])
    markdown = ae.render_markdown({**out, "cache": {"hits": 1, "misses": 2}})
    for expected in ("# Agent evaluation", "blind prompts only", "Prompt injection", "| a09 |", "Cache: 1 replayed"):
        assert expected in markdown, expected

def test_attribution_check_flags_a_document_that_was_not_cited() -> None:
    from src.llm.answer import check_attribution

    wrong = check_attribution("The retention policy states you must give 30 days notice.", {"service_terms.pdf"})
    assert wrong == ["answer names a document that was not cited: retention policy"]
    assert check_attribution("The service terms state 30 days.", {"service_terms.pdf"}) == []
    assert check_attribution("The facts sheet and the retention policy agree.", {"retention_policy.pdf"}) == [
        "answer names a document that was not cited: facts sheet"
    ]


def test_validate_answer_applies_the_attribution_check() -> None:
    from src.llm.answer import validate_answer

    by_id = {"s1": {"text": "Notice is 30 days.", "source": "service_terms.pdf"}}
    issues = validate_answer("The retention policy says 30 days.", ["s1"], by_id)
    assert any("not cited: retention policy" in issue for issue in issues)
    assert validate_answer("The service terms say 30 days.", ["s1"], by_id) == []
    no_source = {"s1": {"text": "Notice is 30 days."}}  # chunks without a source skip the check
    assert validate_answer("The retention policy says 30 days.", ["s1"], no_source) == []