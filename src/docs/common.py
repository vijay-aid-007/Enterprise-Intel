"""Shared types and helpers for the document loaders."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections.abc import Sequence

CID_PATTERN = re.compile(r"\(cid:\d+\)")  # pdfplumber placeholder for unmapped glyphs


@dataclass(frozen=True)
class Section:
    """A block of text with its origin. ``location`` may be empty."""

    text: str
    source: str
    doc_type: str
    location: dict = field(default_factory=dict)


def clean_pdf_text(text: str) -> str:
    """Drop ``(cid:N)`` placeholders that pdfplumber emits for unmapped glyphs."""
    return CID_PATTERN.sub("", text)


def rows_to_markdown(rows: Sequence[Sequence[str | None]]) -> str:
    """Render table rows as a markdown pipe table (first row = header)."""
    clean = [
        [" ".join(clean_pdf_text(cell or "").split()) for cell in row]
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


def push_heading(stack: list[tuple[int, str]], level: int, title: str) -> None:
    """Maintain a heading stack: a heading closes every heading of its level or deeper."""
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))


def make_location(stack: list[tuple[int, str]], **extra: object) -> dict:
    """Location dict: heading path as ``section`` (omitted when empty) plus extras."""
    path = " > ".join(title for _, title in stack)
    location: dict = {"section": path} if path else {}
    location.update(extra)
    return location