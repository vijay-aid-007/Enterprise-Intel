"""Loaders that turn raw files into ``Section`` objects.

A ``Section`` is text that lives in ONE place of ONE file (a page, a heading
section, a table, a CSV row). The chunker never merges sections, so
``location`` stays truthful. Tables from every format are emitted as
markdown pipe tables so the chunker can treat them uniformly.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd
import pdfplumber
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from src import config

logger = logging.getLogger(__name__)

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_DOCX_HEADING = re.compile(r"^Heading (\d)")


@dataclass(frozen=True)
class Section:
    """A block of text with its origin. ``location`` may be empty."""

    text: str
    source: str
    doc_type: str
    location: dict = field(default_factory=dict)


def rows_to_markdown(rows: list[list[str | None]]) -> str:
    """Render table rows as a markdown pipe table (first row = header)."""
    clean = [
        [" ".join((cell or "").split()) for cell in row]
        for row in rows
        if row and any((cell or "").strip() for cell in row)
    ]
    if not clean:
        return ""
    width = max(len(row) for row in clean)
    clean = [row + [""] * (width - len(row)) for row in clean]
    lines = ["| " + " | ".join(row) + " |" for row in clean]
    separator = "| " + " | ".join("---" for _ in range(width)) + " |"
    return "\n".join([lines[0], separator, *lines[1:]])


def _push_heading(stack: list[tuple[int, str]], level: int, title: str) -> None:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))


def _loc(stack: list[tuple[int, str]], **extra: object) -> dict:
    path = " > ".join(title for _, title in stack)
    location: dict = {"section": path} if path else {}
    location.update(extra)
    return location


def load_markdown(path: Path) -> list[Section]:
    """Split a markdown file into one Section per heading section."""
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        text = "\n".join(buf).strip()
        buf.clear()
        if text:
            sections.append(Section(text, path.name, "markdown", _loc(stack)))

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else _MD_HEADING.match(line)
        if match:
            flush()
            _push_heading(stack, len(match.group(1)), match.group(2).strip())
        else:
            buf.append(line)
    flush()
    return sections


def load_docx(path: Path) -> list[Section]:
    """Read a DOCX in document order: heading sections and tables."""
    doc = Document(str(path))
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    table_no = 0

    def flush() -> None:
        text = "\n\n".join(buf).strip()
        buf.clear()
        if text:
            sections.append(Section(text, path.name, "docx", _loc(stack)))

    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            style = para.style.name if para.style is not None else ""
            match = _DOCX_HEADING.match(style)
            if match:
                flush()
                _push_heading(stack, int(match.group(1)), text)
            else:
                buf.append(text)
        elif tag == "tbl":
            flush()
            table_no += 1
            table = Table(child, doc)
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            markdown = rows_to_markdown(rows)
            if markdown:
                sections.append(
                    Section(markdown, path.name, "docx", _loc(stack, table=table_no))
                )
    flush()
    return sections


def load_pdf(path: Path) -> list[Section]:
    """Read a PDF page by page; tables become separate Sections."""
    sections: list[Section] = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            body = page
            for table in tables:  # mask tables so their text is not duplicated
                try:
                    body = body.outside_bbox(table.bbox)
                except Exception:  # pdfplumber geometry edge cases
                    logger.warning(
                        "%s p%d: could not mask a table; text may be duplicated",
                        path.name,
                        page_no,
                    )
            text = (body.extract_text() or "").strip()
            if text:
                sections.append(Section(text, path.name, "pdf", {"page": page_no}))
            elif not tables:
                logger.warning(
                    "%s p%d: no extractable text (scanned? OCR is out of scope)",
                    path.name,
                    page_no,
                )
            for table_no, table in enumerate(tables, start=1):
                markdown = rows_to_markdown(table.extract())
                if markdown:
                    sections.append(
                        Section(
                            markdown,
                            path.name,
                            "pdf",
                            {"page": page_no, "table": table_no},
                        )
                    )
    return sections


def load_csv_rows(path: Path) -> list[Section]:
    """One Section per CSV row. ``row`` = spreadsheet row (header is row 1)."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    sections: list[Section] = []
    for idx, row in frame.iterrows():
        lines = [f"{col}: {str(val).strip()}" for col, val in row.items() if str(val).strip()]
        if lines:
            sections.append(
                Section("\n".join(lines), path.name, "csv", {"row": int(idx) + 2})
            )
    return sections


_LOADERS: dict[str, Callable[[Path], list[Section]]] = {
    ".md": load_markdown,
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".csv": load_csv_rows,
}


def load_all(
    files: Iterable[str] = config.DOC_FILES,
    directory: Path = config.DATA_RAW,
) -> list[Section]:
    """Load every configured document. Fails loudly on a missing file."""
    sections: list[Section] = []
    for name in files:
        path = directory / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing input document: {path}")
        loader = _LOADERS.get(path.suffix.lower())
        if loader is None:
            raise ValueError(f"No loader for file type: {path.suffix}")
        found = loader(path)
        logger.info("loaded %-28s -> %d sections", name, len(found))
        sections.extend(found)
    return sections