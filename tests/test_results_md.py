"""Step 10 tests: the results generator. Fake data for the pure functions, the real files for the full build."""
from __future__ import annotations

import pytest

from scripts import make_results_md as mr
from src import config

FAKE = {
    "retrieval_dev": {"ablation": {"dense": {"n": 8, "hit@5": {"hits": 7, "rate": 0.875}, "mrr": 0.812}}},
    "retrieval_heldout": {"ablation": {
        "dense": {"n": 14, "hit@5": {"hits": 9, "rate": 0.643}, "mrr": 0.429},
        "bm25": {"n": 14, "hit@5": {"hits": 14, "rate": 1.0}, "mrr": 0.881},
    }},
    "generation_heldout": {
        "table": {
            "answerable": {"n": 14, "correct": 10, "answered_incomplete": 3, "refused": 1},
            "out_of_scope": {"n": 2, "refused": 2},
            "gap": {"n": 2, "refused": 2},
        },
        "rejection": {"rejected": 0, "reached_llm": 16, "rate": 0.0},
    },
    "agent": {
        "routing": {"ok": 9, "n": 9}, "routing_unseen": {"ok": 4, "n": 4},
        "injection": {"model_complied": False, "shown_to_user": False},
    },
}
FAKE_METRICS = {
    "n_test": 1409, "threshold": {"value": 0.5783},
    "test": {"pr_auc": 0.663, "roc_auc": 0.8446, "precision": 0.5481, "recall": 0.7166},
}
REAL_FILES = [config.RESULTS_DIR / name for name in mr.SOURCES.values()]


def test_demote_pushes_headings_down() -> None:
    assert mr.demote("# A\ntext\n## B\n| # not a heading |") == "## A\ntext\n### B\n| # not a heading |"


def test_update_block_replaces_only_the_marked_region() -> None:
    readme = f"before\n{mr.START}\nold\n{mr.END}\nafter\n"
    updated = mr.update_block(readme, "new \\1 text")  # a backslash must survive untouched
    assert updated == f"before\n{mr.START}\nnew \\1 text\n{mr.END}\nafter\n"
    for bad in ("no markers", f"{mr.START} only", f"{mr.START}{mr.END}{mr.START}{mr.END}"):
        with pytest.raises(ValueError):
            mr.update_block(bad, "x")


def test_load_results_names_the_missing_files(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="retrieval_dev.json"):
        mr.load_results(tmp_path)


def test_glance_reads_every_number_from_the_data() -> None:
    text = mr.glance(FAKE, FAKE_METRICS)
    expected = (
        "dense 9/14", "bm25 14/14", "dense 0.429", "bm25 0.881", "dense 7/8", "10 correct", "3 incomplete",
        "1 refused of 14", "out-of-scope 2/2", "0 of 16 drafts", "9/9", "4/4", "model complied: False",
        "PR-AUC 0.663", "precision 0.5481", "n = 1409", "threshold 0.5783", "SYNTHETIC",
    )
    for item in expected:
        assert item in text, item


@pytest.mark.skipif(
    not all(path.exists() for path in REAL_FILES) or not config.METRICS_JSON.exists(),
    reason="eval results not present",
)
def test_build_results_from_the_real_files() -> None:
    from eval import ml_eval

    text = mr.build_results(mr.load_results(), ml_eval.load_metrics())
    for item in (
        "# Results", "## Retrieval evaluation: dev split", "## Retrieval evaluation: heldout split",
        "## Generation evaluation: heldout split", "## Agent evaluation", "## ML evaluation", "SYNTHETIC", "frozen",
    ):
        assert item in text, item
    assert "Hand check" not in text and "____" not in text