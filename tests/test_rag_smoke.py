"""Step 3 smoke tests. Live tests skip when the Chroma index is not built."""
from __future__ import annotations

import pytest

from src import config
from src.rag.retriever import Retriever, rrf_fuse, tokenize

CONTRACT_KEYS = {"chunk_id", "text", "source", "score", "location"}


def _chunk(cid: str, text: str, doc_type: str, source: str) -> dict:
    return {"chunk_id": cid, "text": text, "source": source, "doc_type": doc_type,
            "location": {"section": "S"}, "synthetic": True, "n_chars": len(text)}


@pytest.fixture()
def tiny() -> Retriever:
    return Retriever(chunks=[
        _chunk("a-0001", "Maximum retention discount is 30% for High risk customers.", "pdf", "policy.pdf"),
        _chunk("b-0001", "Ticket T-1: customer asked about the maximum discount.", "csv", "tickets.csv"),
        _chunk("c-0001", "Streaming TV add-on costs 10 dollars per month.", "docx", "plans.docx"),
    ])


def test_tokenize_drops_stopwords_keeps_numbers() -> None:
    assert tokenize("What is the MAXIMUM discount, 30%?") == ["maximum", "discount", "30"]


def test_rrf_single_list_formula() -> None:
    fused = rrf_fuse([["x", "y"]], k_const=60)
    assert fused["x"] == pytest.approx(1 / 61)
    assert fused["y"] == pytest.approx(1 / 62)


def test_rrf_rewards_agreement_over_single_list_leader() -> None:
    fused = rrf_fuse([["a", "b", "c"], ["c", "b", "d"]], k_const=60)
    assert fused["b"] > fused["a"] and fused["c"] > fused["a"]


def test_bm25_finds_exact_terms(tiny: Retriever) -> None:
    hits = tiny.search("streaming add-on price", 1, mode="bm25")
    assert [h["chunk_id"] for h in hits] == ["c-0001"]


def test_result_shape_matches_contract(tiny: Retriever) -> None:
    hit = tiny.search("maximum discount", 1, mode="bm25")[0]
    assert set(hit) == CONTRACT_KEYS
    assert isinstance(hit["location"], dict) and isinstance(hit["score"], float)


def test_doc_type_filter(tiny: Retriever) -> None:
    hits = tiny.search("maximum discount", 5, mode="bm25", doc_types=["csv"])
    assert {h["chunk_id"] for h in hits} == {"b-0001"}


def test_unknown_mode_and_empty_query(tiny: Retriever) -> None:
    with pytest.raises(ValueError):
        tiny.search("discount", 3, mode="magic")
    assert tiny.search("   ", 3, mode="bm25") == []


@pytest.fixture(scope="module")
def live() -> Retriever:
    if not config.CHROMA_DIR.exists() or not config.CHUNKS_JSONL.exists():
        pytest.skip("Run `python -m src.rag.index` first")
    return Retriever()


@pytest.mark.parametrize("mode", ["hybrid", "bm25"])
def test_live_max_discount_hits_retention_policy(live: Retriever, mode: str) -> None:
    hits = live.search("what is the maximum retention discount?", 5, mode=mode)
    assert any("retention_policy" in h["source"] and "maximum" in h["text"].lower() for h in hits)


def test_live_doc_type_filter_excludes_tickets(live: Retriever) -> None:
    hits = live.search("maximum discount", 10, mode="hybrid", doc_types=["pdf", "docx", "markdown"])
    assert hits and all(not h["chunk_id"].startswith("support_tickets") for h in hits)