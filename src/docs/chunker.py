"""Chunk Sections into retrievable pieces and write ``chunks.jsonl``.

Rules: a chunk never crosses a Section boundary (so page/section/row stays
correct); tables are chunked alone and every piece repeats the header row;
text is packed by paragraph, then by sentence, never cut mid-sentence unless
one sentence alone exceeds the budget.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import re
import statistics
from collections import defaultdict
from pathlib import Path

from src import config
from src.docs.common import Section
from src.docs.loaders import load_all

logger = logging.getLogger(__name__)

_UNIT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n(?=\s*(?:[-*\u2022]|\d+[.)])\s)")  # sentence ends, list items
_MIN_BUDGET = 300
_LABEL_MAX = 200  # a text block this short right before a table is its label


def _is_table_block(block: str) -> bool:
    lines = [ln for ln in block.splitlines() if ln.strip()]
    return len(lines) >= 2 and all(ln.lstrip().startswith("|") for ln in lines)


def _split_table(block: str, budget: int) -> list[str]:
    """Split a pipe table by rows, repeating header + separator in each piece."""
    lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
    head = "\n".join(lines[:2])
    pieces: list[str] = []
    current: list[str] = []
    for row in lines[2:]:
        candidate = "\n".join([head, *current, row])
        if current and len(candidate) > budget:
            pieces.append("\n".join([head, *current]))
            current = [row]
        else:
            current.append(row)
    if current:
        pieces.append("\n".join([head, *current]))
    return pieces or [head]


def _split_text(block: str, budget: int) -> list[str]:
    """Return the block whole if it fits, else pack sentences up to budget."""
    if len(block) <= budget:
        return [block]
    pieces: list[str] = []
    current = ""
    for unit in (u.strip() for u in _UNIT_SPLIT.split(block)):
        while len(unit) > budget:  # a single sentence longer than the budget
            cut = unit.rfind(" ", 0, budget)
            cut = cut if cut > 0 else budget
            if current:
                pieces.append(current)
                current = ""
            pieces.append(unit[:cut].strip())
            unit = unit[cut:].strip()
        if not unit:
            continue
        if current and len(current) + 1 + len(unit) > budget:
            pieces.append(current)
            current = unit
        else:
            current = f"{current} {unit}".strip()
    if current:
        pieces.append(current)
    return pieces


def chunk_section(section: Section, max_chars: int) -> list[str]:
    """Chunk one Section. Heading path is prepended as context when known."""
    heading = section.location.get("section")
    prefix = f"[{heading}]\n" if heading else ""
    budget = max(max_chars - len(prefix), _MIN_BUDGET)
    blocks = [b.strip() for b in re.split(r"\n\s*\n", section.text) if b.strip()]

    pieces: list[str] = []
    current = ""
    for block in blocks:
        if _is_table_block(block):
            table_pieces = _split_table(block, budget)
            lead_fits = len(current) + 2 + len(table_pieces[0]) <= budget
            if current and len(current) <= _LABEL_MAX and lead_fits:
                table_pieces[0] = f"{current}\n\n{table_pieces[0]}"  # keep label with table
                current = ""
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(table_pieces)
            continue
        for part in _split_text(block, budget):
            if current and len(current) + 2 + len(part) > budget:
                pieces.append(current)
                current = part
            else:
                current = f"{current}\n\n{part}" if current else part
    if current:
        pieces.append(current)
    return [prefix + piece for piece in pieces if piece.strip()]


def build_chunks(sections: list[Section], max_chars: int) -> list[dict]:
    """Turn Sections into chunk dicts with deterministic ids."""
    counters: dict[str, int] = defaultdict(int)
    chunks: list[dict] = []
    for section in sections:
        stem = Path(section.source).stem
        for text in chunk_section(section, max_chars):
            ordinal = counters[stem]
            counters[stem] += 1
            chunks.append(
                {
                    "chunk_id": f"{stem}-{ordinal:04d}",
                    "text": text,
                    "source": section.source,
                    "location": dict(section.location),
                    "doc_type": section.doc_type,
                    "synthetic": section.source in config.SYNTHETIC_DOCS,
                    "n_chars": len(text),
                }
            )
    return chunks


def write_chunks(chunks: list[dict], path: Path = config.CHUNKS_JSONL) -> None:
    """Write one JSON object per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")


def read_chunks(path: Path = config.CHUNKS_JSONL) -> list[dict]:
    """Read chunks back (used by the indexer in Step 3)."""
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(argv: list[str] | None = None) -> int:
    """CLI: build chunks.jsonl, print stats, optionally sample chunks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="print one random chunk per source")
    args = parser.parse_args(argv)

    config.configure_logging()
    chunks = build_chunks(load_all(), config.CHUNK_MAX_CHARS)
    write_chunks(chunks)
    logger.info("wrote %d chunks to %s", len(chunks), config.CHUNKS_JSONL)

    by_source: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        by_source[chunk["source"]].append(chunk)

    print(f"{'source':<28}{'chunks':>8}{'median':>8}{'max':>6}")
    for source in sorted(by_source):
        sizes = [c["n_chars"] for c in by_source[source]]
        print(f"{source:<28}{len(sizes):>8}{int(statistics.median(sizes)):>8}{max(sizes):>6}")
    over = sum(1 for c in chunks if c["n_chars"] > config.CHUNK_MAX_CHARS)
    print(f"chunks over {config.CHUNK_MAX_CHARS} chars: {over}")

    if args.sample:
        rng = random.Random(config.SEED)
        for source in sorted(by_source):
            chunk = rng.choice(by_source[source])
            print(f"\n--- {chunk['chunk_id']} | location={chunk['location']} | {chunk['n_chars']} chars")
            print(chunk["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())