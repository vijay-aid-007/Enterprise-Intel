"""Loaders that turn raw files into ``Section`` objects.

A ``Section`` is text that lives in ONE place of ONE file (a heading section,
a table, a CSV row). The chunker never merges sections, so ``location`` stays
truthful. Tables from every format are emitted as markdown pipe tables so the
chunker can treat them uniformly. PDFs are handled in ``pdf_loader``.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from src import config
from src.docs.common import Section, make_location, push_heading, rows_to_markdown
from src.docs.pdf_loader import load_pdf

logger = logging.getLogger(__name__)

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_DOCX_HEADING = re.compile(r"^Heading (\d)")


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
            sections.append(Section(text, path.name, "markdown", make_location(stack)))

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else _MD_HEADING.match(line)
        if match:
            flush()
            push_heading(stack, len(match.group(1)), match.group(2).strip())
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
            sections.append(Section(text, path.name, "docx", make_location(stack)))

    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name if para.style is not None else None) or ""
            match = _DOCX_HEADING.match(style)
            if match:
                flush()
                push_heading(stack, int(match.group(1)), text)
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
                    Section(markdown, path.name, "docx", make_location(stack, table=table_no))
                )
    flush()
    return sections


def load_csv_rows(path: Path) -> list[Section]:
    """One Section per CSV row. ``row`` = spreadsheet row (header is row 1)."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    sections: list[Section] = []
    for number, (_, row) in enumerate(frame.iterrows()):
        lines = [f"{col}: {str(val).strip()}" for col, val in row.items() if str(val).strip()]
        if lines:
            sections.append(
                Section("\n".join(lines), path.name, "csv", {"row": number + 2})
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