"""Documentation tests: commands, links and quoted numbers in the docs must match the code.

They catch drift (a renamed module, a link with the wrong case, a stale count). They cannot judge whether
the prose is true. Module paths are checked as files, so nothing heavy is imported.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from src import config

ROOT = config.PROJECT_ROOT
DOCS = ("README.md", "data/README.md", "docs/DEMO.md")
REPO_PACKAGES = frozenset({"src", "eval", "scripts", "app"})
RESULTS_START, RESULTS_END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
_MODULE = re.compile(r"python -m ([A-Za-z_][\w.]*)")
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_STREAMLIT = re.compile(r"streamlit run ([^\s`]+)")
SOURCE_LABELS = (
    ("facts sheet", "facts_sheet.md"),
    ("retention policy", "retention_policy.pdf"),
    ("pricing guide", "plans_pricing_guide.docx"),
    ("service terms", "service_terms.pdf"),
    ("tickets", "support_tickets.csv"),
)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def documented_modules(text: str) -> set[str]:
    """Repo modules named in `python -m ...` commands. Third-party modules (pytest, streamlit, venv) are ignored."""
    found = {match.rstrip(".") for match in _MODULE.findall(text)}
    return {module for module in found if module.split(".")[0] in REPO_PACKAGES}


def module_file_exists(module: str) -> bool:
    base = ROOT.joinpath(*module.split("."))
    return base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()


def relative_links(text: str) -> list[str]:
    """Targets of markdown links that point inside the repo, without #anchors."""
    targets = [t for t in _LINK.findall(text) if not re.match(r"^(https?:|mailto:|#)", t)]
    return [t.split("#")[0] for t in targets if t.split("#")[0]]


def exact_case_exists(base: Path, relative: str) -> bool:
    """True if every path component exists with exactly this spelling (Windows would accept any case)."""
    current = base
    for part in Path(relative).parts:
        if part == "..":
            current = current.parent
        elif not current.is_dir() or part not in {entry.name for entry in current.iterdir()}:
            return False
        else:
            current = current / part
    return True


def test_documented_modules_exist() -> None:
    missing = [
        f"{rel}: python -m {module}"
        for rel in DOCS for module in sorted(documented_modules(read(rel))) if not module_file_exists(module)
    ]
    assert not missing, missing


def test_documented_streamlit_script_exists() -> None:
    for rel in DOCS:
        for target in _STREAMLIT.findall(read(rel)):
            assert (ROOT / target.replace("\\", "/")).is_file(), (rel, target)


def test_relative_links_resolve_with_exact_case() -> None:
    broken = [
        f"{rel}: {link}"
        for rel in DOCS for link in relative_links(read(rel)) if not exact_case_exists((ROOT / rel).parent, link)
    ]
    assert not broken, broken


def test_readme_results_block_is_generated() -> None:
    text = read("README.md")
    assert text.count(RESULTS_START) == 1 and text.count(RESULTS_END) == 1
    block = text.split(RESULTS_START)[1].split(RESULTS_END)[0]
    assert "| Measure | Result |" in block and "scripts/make_results_md.py" in block


def test_readme_lists_every_api_route() -> None:
    from src.api import main

    text = read("README.md")
    assert not [path for path in main.app.openapi()["paths"] if path not in text]


def test_readme_limits_match_config() -> None:
    text = read("README.md")
    assert f"{config.AGENT_MAX_STEPS} tool calls" in text
    assert f"{config.AGENT_MAX_SEARCHES} document searches" in text


@pytest.mark.skipif(not config.CHUNKS_JSONL.exists(), reason="chunks.jsonl not present")
def test_data_readme_chunk_counts_match_chunks_jsonl() -> None:
    lines = config.CHUNKS_JSONL.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    text, counts = read("data/README.md"), Counter(row["source"] for row in rows)
    assert f"{len(rows)} chunks" in text
    for label, source in SOURCE_LABELS:
        assert f"{label} {counts[source]}" in text, (label, counts[source])
    assert all(row.get("synthetic") is True for row in rows)


@pytest.mark.skipif(not config.DATA_RAW.exists(), reason="data/raw not present")
def test_data_readme_lists_every_raw_file() -> None:
    text = read("data/README.md")
    assert not [p.name for p in config.DATA_RAW.iterdir() if p.name not in text]


def test_helpers_extract_modules_and_links() -> None:
    text = "Run python -m src.api.main. Then `python -m pytest tests` and python -m scripts.make_results_md --readme x"
    assert documented_modules(text) == {"src.api.main", "scripts.make_results_md"}
    links = relative_links("[a](docs/X.md#sec) [b](https://x.org) [c](#top) [d](data/README.md)")
    assert links == ["docs/X.md", "data/README.md"]
    assert module_file_exists("src.api.main") and not module_file_exists("src.api.nope")


def test_exact_case_check(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "demo.md").write_text("x", encoding="utf-8")
    assert exact_case_exists(tmp_path, "docs/demo.md")
    assert not exact_case_exists(tmp_path, "docs/DEMO.md")
    assert not exact_case_exists(tmp_path, "docs/missing.md")