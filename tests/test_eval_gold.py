"""Step 9a tests: gold-file integrity against the real chunks, and the pure retrieval-eval functions.

No model, index or LLM is used. run_split is exercised with fake retrieval functions.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from eval import retrieval_eval as ev
from src import config

needs_chunks = pytest.mark.skipif(not config.CHUNKS_JSONL.exists(), reason="chunks.jsonl not present")

FAKE_CHUNKS = {
    "c1": {"chunk_id": "c1", "text": "The cap is 30 percent.\u202f Only one offer.", "doc_type": "pdf"},
    "c2": {"chunk_id": "c2", "text": "Ticket text mentions a static ip.", "doc_type": "csv"},
}
ROWS = [
    {"type": "answerable", "dense_top": 0.62, "sufficient": True},
    {"type": "answerable", "dense_top": 0.48, "sufficient": True},
    {"type": "out_of_scope", "dense_top": 0.12, "sufficient": False},
    {"type": "out_of_scope", "dense_top": 0.22, "sufficient": False},
    {"type": "gap", "dense_top": 0.55, "sufficient": True},
]


def fake_result() -> dict[str, Any]:
    questions = [
        {"id": "q1", "type": "answerable", "question": "alpha", "relevant_chunks": ["c2"]},
        {"id": "q2", "type": "answerable", "question": "beta", "relevant_chunks": ["c9"]},
        {"id": "q3", "type": "out_of_scope", "question": "gamma"},
    ]

    def fake_retrieve(query: str, k: int, mode: str) -> list[dict[str, Any]]:
        order = ["c1", "c2"] if mode == "hybrid" else ["c1", "c3"]
        return [{"chunk_id": cid} for cid in order][:k]

    def fake_evidence(query: str) -> Any:
        top = {"alpha": 0.6, "beta": 0.5, "gamma": 0.1}[query]
        return SimpleNamespace(dense_top=top, bm25_top=1.0, sufficient=top >= 0.25, reason="r")

    return ev.run_split(
        questions, fake_retrieve, fake_evidence, modes=("dense", "hybrid"), ks=(1, 3),
        max_rank=10, thresholds=(0.25,), configured_threshold=0.25,
    )


def test_gold_counts_and_ids() -> None:
    questions = ev.load_gold()
    assert len(questions) == 28 and len({q["id"] for q in questions}) == 28
    assert sum(q["split"] == "dev" for q in questions) == 10
    assert {t: sum(q["type"] == t for q in questions) for t in ev.TYPES} == {
        "answerable": 20, "out_of_scope": 4, "gap": 4,
    }


def test_dev_split_has_every_question_type() -> None:
    assert {q["type"] for q in ev.load_gold() if q["split"] == "dev"} == set(ev.TYPES)


@needs_chunks
def test_gold_labels_match_the_documents() -> None:
    assert ev.validate_gold(ev.load_gold(), ev.load_chunks()) == []


def test_validate_gold_catches_bad_labels() -> None:
    good = [
        {"id": "a", "split": "dev", "type": "answerable", "question": "q",
         "relevant_chunks": ["c1"], "expected_facts": ["30 percent", "only one offer"]},
        {"id": "b", "split": "dev", "type": "gap", "question": "q", "absent_terms": ["static ip"]},  # csv only
        {"id": "c", "split": "heldout", "type": "out_of_scope", "question": "q"},
    ]
    assert ev.validate_gold(good, FAKE_CHUNKS) == []
    bad = [
        {"id": "a", "split": "dev", "type": "answerable", "question": "q",
         "relevant_chunks": ["c1"], "expected_facts": ["45 percent"]},
        {"id": "a", "split": "dev", "type": "answerable", "question": "q",
         "relevant_chunks": ["nope"], "expected_facts": ["x"]},
        {"id": "d", "split": "dev", "type": "answerable", "question": "q",
         "relevant_chunks": ["c2"], "expected_facts": ["static ip"]},
        {"id": "g", "split": "dev", "type": "gap", "question": "q", "absent_terms": ["30 percent"]},
        {"id": "o", "split": "dev", "type": "out_of_scope", "question": "q", "relevant_chunks": ["c1"]},
        {"id": "x", "split": "weird", "type": "gap", "question": "q"},
    ]
    text = "\n".join(ev.validate_gold(bad, FAKE_CHUNKS))
    for expected in (
        "duplicate question ids", "fact not in relevant chunks: '45 percent'",
        "relevant chunk missing, unknown or not retrievable", "not a gap: '30 percent'",
        "must not list relevant chunks or facts", "bad type, split or question text",
    ):
        assert expected in text, expected


def test_first_relevant_rank_and_summary() -> None:
    assert ev.first_relevant_rank(["a", "b", "c"], ["c", "z"]) == 3
    assert ev.first_relevant_rank(["a"], ["z"]) is None
    summary = ev.summarize_ranks([1, 3, None, 6], (1, 3, 5))
    assert summary["n"] == 4
    assert [summary[f"hit@{k}"]["hits"] for k in (1, 3, 5)] == [1, 2, 2]
    assert summary["mrr"] == pytest.approx((1 + 1 / 3 + 1 / 6) / 4, abs=1e-3)
    assert ev.summarize_ranks([], (1,))["mrr"] is None


def test_sweep_and_suggested_threshold() -> None:
    by_t = {row["threshold"]: row for row in ev.sweep(ROWS, (0.20, 0.30, 0.50))}
    assert by_t[0.20]["out_of_scope"] == {"refused": 1, "n": 2}
    assert by_t[0.30]["out_of_scope"] == {"refused": 2, "n": 2} and by_t[0.30]["answerable"]["refused"] == 0
    assert by_t[0.50]["answerable"] == {"refused": 1, "n": 2} and by_t[0.50]["gap"] == {"refused": 0, "n": 1}
    assert ev.suggest_threshold(ROWS) == pytest.approx(0.35, abs=1e-6)  # midpoint of 0.22 and 0.48
    assert ev.suggest_threshold(ROWS + [{"type": "out_of_scope", "dense_top": 0.5, "sufficient": True}]) is None
    assert ev.suggest_threshold([r for r in ROWS if r["type"] != "out_of_scope"]) is None


def test_sufficiency_consistency_check() -> None:
    assert ev.sufficiency_is_dense_only(ROWS, 0.25) is True
    assert ev.sufficiency_is_dense_only(ROWS, 0.60) is False


def test_run_split_with_fakes() -> None:
    result = fake_result()
    assert result["n_questions"] == 3
    assert result["ablation"]["hybrid"]["hit@3"]["hits"] == 1 and result["ablation"]["hybrid"]["hit@1"]["hits"] == 0
    assert result["ablation"]["dense"]["hit@3"]["hits"] == 0
    table = result["refusal_at_configured"]["table"]
    assert table["out_of_scope"] == {"refused": 1, "n": 1} and table["answerable"]["refused"] == 0
    assert result["suggested_threshold"] == pytest.approx(0.3, abs=1e-6)
    assert result["dense_only_rule_holds"] is True
    assert result["rows"][0]["ranks"] == {"dense": None, "hybrid": 2}


def test_render_markdown_has_tables() -> None:
    markdown = ev.render_markdown("dev", fake_result(), (1, 3))
    for expected in ("| mode |", "hit@1", "| threshold |", "SYNTHETIC", "miss", "n/a"):
        assert expected in markdown, expected


def test_normalize_handles_odd_characters() -> None:
    assert ev.normalize("One\u2011Year  \u202f$50\n") == "one-year $50"