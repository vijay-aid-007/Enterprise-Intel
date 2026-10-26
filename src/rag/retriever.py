"""Pluggable retrieval behind one retrieve() call: dense | bm25 | hybrid (RRF).

Every result is {chunk_id, text, source, score, location}. `score` is
mode-specific (cosine / raw BM25 / RRF) and NOT comparable across modes.

CLI:  python -m src.rag.retriever "question" [--mode hybrid] [--k 5]
      python -m src.rag.retriever --probe "q1" "q2"   (evidence signals only)
"""
from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from typing import Iterable

from rank_bm25 import BM25Okapi

from src import config
from src.docs.chunker import read_chunks
from src.rag.index import embed_texts, file_sha256, get_client

log = logging.getLogger(__name__)
MODES = ("dense", "bm25", "hybrid")
STOPWORDS = frozenset(
    "a an and are as at be by for from how i in is it of on or that the this to "
    "what when which who with you your can do does".split()
)


class IndexMissingError(RuntimeError):
    """The Chroma collection has not been built."""


class IndexOutOfDateError(RuntimeError):
    """chunks.jsonl changed after the Chroma collection was built."""


@dataclass(frozen=True)
class Evidence:
    """Absolute retrieval signals used by the refusal guardrail."""

    dense_top: float
    bm25_top: float
    sufficient: bool
    reason: str


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens minus stopwords ('30%' becomes '30')."""
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


def rrf_fuse(rankings: list[list[str]], k_const: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion: score(d) = sum over rankings of 1 / (k + rank), rank from 1."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (k_const + rank)
    return fused


class Retriever:
    """Holds chunks, an in-memory BM25 index and a lazily opened Chroma collection."""

    def __init__(self, chunks: list[dict] | None = None) -> None:
        self._expected_sha = file_sha256(config.CHUNKS_JSONL) if chunks is None else None
        self.chunks = chunks if chunks is not None else read_chunks(config.CHUNKS_JSONL)
        self._by_id = {c["chunk_id"]: c for c in self.chunks}
        self._bm25_index = BM25Okapi([tokenize(c["text"]) for c in self.chunks])
        self._collection = None

    def _dense_collection(self):
        if self._collection is None:
            try:
                col = get_client().get_collection(config.CHROMA_COLLECTION)
            except Exception as exc:  # noqa: BLE001 - type differs across versions
                raise IndexMissingError("Dense index missing. Run: python -m src.rag.index") from exc
            built = (col.metadata or {}).get("chunks_sha256")
            if self._expected_sha is not None and built != self._expected_sha:
                raise IndexOutOfDateError(
                    "chunks.jsonl changed since the index was built. Run: python -m src.rag.index"
                )
            self._collection = col
        return self._collection

    def _allowed(self, doc_types: Iterable[str] | None) -> set[str] | None:
        if not doc_types:
            return None
        wanted = set(doc_types)
        return {c["chunk_id"] for c in self.chunks if c.get("doc_type") in wanted}

    def _dense(self, query: str, n: int, doc_types: Iterable[str] | None) -> list[tuple[str, float]]:
        col = self._dense_collection()
        where = {"doc_type": {"$in": sorted(set(doc_types))}} if doc_types else None
        res = col.query(
            query_embeddings=embed_texts([query]),
            n_results=max(1, min(n, col.count())),
            where=where,
        )
        return [(cid, 1.0 - dist / 2.0) for cid, dist in zip(res["ids"][0], res["distances"][0])]

    def _sparse(self, query: str, n: int, doc_types: Iterable[str] | None) -> list[tuple[str, float]]:
        scores = self._bm25_index.get_scores(tokenize(query))
        allowed = self._allowed(doc_types)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], self.chunks[i]["chunk_id"]))
        out: list[tuple[str, float]] = []
        for i in order:
            cid = self.chunks[i]["chunk_id"]
            if scores[i] <= 0:
                break
            if allowed is not None and cid not in allowed:
                continue
            out.append((cid, float(scores[i])))
            if len(out) >= n:
                break
        return out

    def _result(self, cid: str, score: float) -> dict:
        c = self._by_id[cid]
        return {
            "chunk_id": cid,
            "text": c["text"],
            "source": c["source"],
            "score": round(float(score), 6),
            "location": c.get("location") or {},
        }

    def search(
        self, query: str, k: int = 5, *, mode: str | None = None,
        doc_types: Iterable[str] | None = None,
    ) -> list[dict]:
        """Top-k chunks for `query` using dense, bm25 or hybrid (RRF) retrieval."""
        mode = mode or config.RETRIEVAL_MODE
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        if not query.strip() or k < 1:
            return []
        n = max(config.CANDIDATES_PER_BACKEND, k)
        if mode == "dense":
            scored = self._dense(query, n, doc_types)
        elif mode == "bm25":
            scored = self._sparse(query, n, doc_types)
        else:
            dense = self._dense(query, n, doc_types)
            sparse = self._sparse(query, n, doc_types)
            fused = rrf_fuse([[c for c, _ in dense], [c for c, _ in sparse]], config.RRF_K)
            scored = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
        return [self._result(cid, s) for cid, s in scored[:k]]

    def check_evidence(self, query: str, *, doc_types: Iterable[str] | None = None) -> Evidence:
        """Absolute-score sufficiency check (RRF scores are rank-based, so not usable here)."""
        dense = self._dense(query, 1, doc_types)
        sparse = self._sparse(query, 1, doc_types)
        d = dense[0][1] if dense else 0.0
        b = sparse[0][1] if sparse else 0.0
        reasons = []
        if d < config.DENSE_MIN_SIM:
            reasons.append(f"dense {d:.3f} < {config.DENSE_MIN_SIM}")
        if b < config.BM25_MIN_SCORE:
            reasons.append(f"bm25 {b:.2f} < {config.BM25_MIN_SCORE}")
        return Evidence(round(d, 4), round(b, 4), not reasons, "; ".join(reasons) or "ok")


_default: Retriever | None = None


def get_retriever() -> Retriever:
    """Process-wide Retriever (loads chunks and builds BM25 once)."""
    global _default
    if _default is None:
        _default = Retriever()
    return _default


def retrieve(query: str, k: int = 5, *, mode: str | None = None,
             doc_types: Iterable[str] | None = None) -> list[dict]:
    """Contract function: list of {chunk_id, text, source, score, location}."""
    return get_retriever().search(query, k, mode=mode, doc_types=doc_types)


def check_evidence(query: str, *, doc_types: Iterable[str] | None = None) -> Evidence:
    """Is there enough absolute similarity to even attempt an answer?"""
    return get_retriever().check_evidence(query, doc_types=doc_types)


def retrieve_checked(query: str, k: int = 5, *, mode: str | None = None,
                     doc_types: Iterable[str] | None = None) -> tuple[list[dict], Evidence]:
    """Retrieve, but return [] when the evidence check fails (refusal path)."""
    ev = check_evidence(query, doc_types=doc_types)
    if not ev.sufficient:
        log.info("Insufficient evidence for %r: %s", query, ev.reason)
        return [], ev
    return retrieve(query, k, mode=mode, doc_types=doc_types), ev


def _main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("queries", nargs="+")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--mode", choices=MODES, default=None)
    p.add_argument("--doc-types", nargs="+", default=None)
    p.add_argument("--probe", action="store_true", help="print evidence signals only")
    args = p.parse_args()
    config.configure_logging()
    for q in args.queries:
        if args.probe:
            ev = check_evidence(q, doc_types=args.doc_types)
            print(f"dense_top={ev.dense_top:.3f} bm25_top={ev.bm25_top:.2f} "
                  f"sufficient={ev.sufficient} | {q}")
            continue
        print(f"\nQ: {q}  (mode={args.mode or config.RETRIEVAL_MODE})")
        for rank, hit in enumerate(retrieve(q, args.k, mode=args.mode, doc_types=args.doc_types), 1):
            snippet = " ".join(hit["text"].split())[:150]
            print(f"{rank}. {hit['chunk_id']} score={hit['score']:.4f} {hit['source']} "
                  f"{hit['location']}\n   {snippet}")


if __name__ == "__main__":
    _main()