"""PDF loader.

Reads layout instead of trusting raw text order: words are grouped into lines,
lines into paragraphs (by vertical gap), headings are found by font size, page
numbers are dropped, and a sentence that runs over a page break is rejoined.
Each heading plus its text becomes one Section (like DOCX/Markdown); tables
become their own Sections. If a PDF has no larger-font headings, each page is
one Section.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from src.docs.common import (
    CID_PATTERN, Section, clean_pdf_text, make_location, push_heading, rows_to_markdown)

logger = logging.getLogger(__name__)

_FOOTER = re.compile(r"^(page\s+)?\d+(\s*(/|of)\s*\d+)?$", re.I)
_SENTENCE_END = re.compile(r"[.!?:;)\"']$")
_LINE_TOL = 2.0        # words whose tops differ by less than this share a line
_GAP_RATIO = 0.45      # a gap above this x line height starts a new paragraph
_HEADING_RATIO = 1.15  # a line this much larger than body text is a heading
_MARGIN = 0.10         # top/bottom page fraction where bare page numbers are dropped


@dataclass
class _Line:
    text: str
    top: float
    bottom: float
    size: float
    page: int


@dataclass
class _Block:
    text: str
    page: int
    size: float
    heading: bool


def _page_lines(page, number: int) -> tuple[list[_Line], list]:
    """Text lines outside tables (page numbers dropped) and the page's tables."""
    tables = page.find_tables()
    body = page
    for table in tables:  # mask tables so their text is not read twice
        try:
            body = body.outside_bbox(table.bbox)
        except Exception:  # pdfplumber geometry edge cases
            logger.warning("page %d: could not mask a table; text may be duplicated", number)
    groups: list[list[dict]] = []
    for word in sorted(body.extract_words(extra_attrs=["size"]), key=lambda w: w["top"]):
        if groups and abs(word["top"] - groups[-1][0]["top"]) <= _LINE_TOL:
            groups[-1].append(word)
        else:
            groups.append([word])
    lines: list[_Line] = []
    for group in groups:
        group.sort(key=lambda w: w["x0"])
        raw = " ".join(w["text"] for w in group)
        if CID_PATTERN.search(raw):
            logger.warning("page %d: unmapped glyphs (cid) removed from text", number)
        text = clean_pdf_text(raw).strip()
        top, bottom = min(w["top"] for w in group), max(w["bottom"] for w in group)
        in_margin = top > page.height * (1 - _MARGIN) or bottom < page.height * _MARGIN
        if text and not (in_margin and _FOOTER.match(text)):
            lines.append(_Line(text, top, bottom, max(w["size"] for w in group), number))
    return lines, tables


def _body_size(lines: list[_Line]) -> float:
    """Most common font size by character count: the body text size."""
    weight: Counter = Counter()
    for line in lines:
        weight[round(line.size * 2) / 2] += len(line.text)
    return weight.most_common(1)[0][0] if weight else 0.0


def _blocks(lines: list[_Line], body: float) -> list[_Block]:
    """Group lines into paragraphs and headings."""
    blocks: list[_Block] = []
    prev: _Line | None = None
    for line in lines:
        heading = body > 0 and line.size >= body * _HEADING_RATIO
        height = max(prev.bottom - prev.top, 1.0) if prev else 1.0
        same = (
            prev is not None and line.page == prev.page and heading == blocks[-1].heading
            and abs(line.size - prev.size) < 0.5 and line.top - prev.bottom <= _GAP_RATIO * height)
        if same:
            blocks[-1].text += " " + line.text
        else:
            blocks.append(_Block(line.text, line.page, line.size, heading))
        prev = line
    return blocks


def _join_pages(blocks: list[_Block]) -> list[_Block]:
    """Rejoin a paragraph that stops without sentence punctuation at a page break."""
    joined: list[_Block] = []
    for block in blocks:
        last = joined[-1] if joined else None
        if (last and not block.heading and not last.heading and block.page == last.page + 1
                and not _SENTENCE_END.search(last.text)):
            last.text += " " + block.text
        else:
            joined.append(block)
    return joined


def _sections(blocks: list[_Block], source: str) -> list[Section]:
    """One Section per heading + its paragraphs; one per page if no headings exist."""
    sections: list[Section] = []
    if not any(block.heading for block in blocks):
        for page in sorted({block.page for block in blocks}):
            text = "\n\n".join(b.text for b in blocks if b.page == page)
            sections.append(Section(text, source, "pdf", {"page": page}))
        return sections
    levels = {size: rank for rank, size in enumerate(
        sorted({round(b.size * 2) / 2 for b in blocks if b.heading}, reverse=True), start=1)}
    stack: list[tuple[int, str]] = []
    paras: list[str] = []
    start: int | None = None

    def flush() -> None:
        text = "\n\n".join(paras).strip()
        paras.clear()
        if text:
            sections.append(Section(text, source, "pdf", make_location(stack, page=start or 1)))

    for block in blocks:
        if block.heading:
            flush()
            push_heading(stack, levels[round(block.size * 2) / 2], block.text)
            start = block.page
        else:
            start = start if start is not None else block.page
            paras.append(block.text)
    flush()
    return sections


def load_pdf(path: Path) -> list[Section]:
    """Read a PDF into heading Sections plus table Sections."""
    lines: list[_Line] = []
    tables_out: list[Section] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            page_lines, tables = _page_lines(page, number)
            if not page_lines and not tables:
                logger.warning("%s p%d: no extractable text (scanned? OCR is out of scope)", path.name, number)
            lines += page_lines
            for index, table in enumerate(tables, start=1):
                markdown = rows_to_markdown(table.extract())
                if markdown:
                    tables_out.append(
                        Section(markdown, path.name, "pdf", {"page": number, "table": index}))
    blocks = _join_pages(_blocks(lines, _body_size(lines)))
    return _sections(blocks, path.name) + tables_out