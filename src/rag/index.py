"""Build the dense (Chroma) index from chunks.jsonl.

Run:  python -m src.rag.index

Embeddings are L2-normalised and the collection uses Chroma's default metric
(squared L2), so a returned distance d maps to cosine similarity as 1 - d / 2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from src import config
from src.docs.chunker import read_chunks

log = logging.getLogger(__name__)
BATCH_SIZE = 64


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """Load the sentence-transformer once per process."""
    log.info("Loading embedder %s", config.EMBED_MODEL)
    return SentenceTransformer(config.EMBED_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts into unit-length vectors (cosine == dot product)."""
    vectors = get_embedder().encode(
        texts, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False
    )
    return vectors.tolist()


def file_sha256(path: Path) -> str:
    """Fingerprint a file so a stale index can be detected."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def get_client() -> ClientAPI:
    """Persistent Chroma client rooted at config.CHROMA_DIR (telemetry off)."""
    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(config.CHROMA_DIR), settings=Settings(anonymized_telemetry=False)
    )


def build_index() -> int:
    """Rebuild the collection from chunks.jsonl. Returns the number of chunks indexed."""
    chunks = read_chunks(config.CHUNKS_JSONL)
    ids = [c["chunk_id"] for c in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate chunk_id in chunks.jsonl")

    client = get_client()
    try:
        client.delete_collection(config.CHROMA_COLLECTION)
        log.info("Deleted previous collection")
    except Exception:  # noqa: BLE001 - exception type differs across chromadb versions
        log.debug("No previous collection to delete")

    col = client.create_collection(
        config.CHROMA_COLLECTION,
        metadata={
            "chunks_sha256": file_sha256(config.CHUNKS_JSONL),
            "embed_model": config.EMBED_MODEL,
        },
    )
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        col.add(
            ids=[c["chunk_id"] for c in batch],
            documents=texts,
            embeddings=embed_texts(texts),              # pyright: ignore[reportArgumentType]
            metadatas=[
                {
                    "source": c["source"],
                    "doc_type": c["doc_type"],
                    "synthetic": bool(c.get("synthetic", False)),
                    "location": json.dumps(c.get("location") or {}, sort_keys=True),
                }
                for c in batch
            ],
        )
    log.info("Indexed %d chunks", col.count())
    return col.count()


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    config.ensure_dirs()
    config.configure_logging()
    n = build_index()
    print(f"Indexed {n} chunks into '{config.CHROMA_COLLECTION}' at {config.CHROMA_DIR}")


if __name__ == "__main__":
    main()