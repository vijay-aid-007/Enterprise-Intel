"""Generation evaluation (Step 9b): answers, refusals and the validators' rejection rate.

Runs answer_question over the gold questions through an on-disk LLM cache. Protocol: look at dev first;
run heldout once, after prompts and thresholds are frozen. Gold questions come from SYNTHETIC documents,
so scores are optimistic. Automatic fact matching is a lower bound; the report lists every shown answer
with its cited text for hand checking.

    python -m eval.generation_eval --split dev
    python -m eval.generation_eval --split agent
    python -m eval.generation_eval --split heldout     # once
    (add --offline to replay from the cache without an API key)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
from typing import Any, Callable

from eval.llm_cache import CachingClient
from eval.retrieval_eval import load_chunks, load_gold, normalize, validate_gold
from src import config
from src.llm.answer import extract_numbers

logger = logging.getLogger(__name__)

REFUSED_STATUSES = frozenset({"refused_insufficient_evidence", "refused_model"})
OUTCOMES_ANSWERABLE: tuple[str, ...] = ("correct", "answered_incomplete", "refused", "rejected", "error")
OUTCOMES_OTHER: tuple[str, ...] = ("refused", "withheld", "answered", "error")
_PERCENT = re.compile(r"\s*percent\b")
_STOP = frozenset(
    "the and for that with this are per any its can not has have from than was were you your who how".split()
)


def _percent(text: str) -> str:
    return _PERCENT.sub("%", text)


def fact_present(text: str, fact: str) -> bool:
    """Is `fact` stated in `text`? Exact (normalised) substring, or all its numbers and content words appear.

    '30 percent' matches '30%'; 'retention manager' matches 'retention-manager'. Lenient about word order, strict
    about numbers. It cannot tell right from wrong context, which is why answers are also hand checked.
    """
    haystack, needle = _percent(normalize(text)), _percent(normalize(fact))
    if needle in haystack:
        return True
    numbers = extract_numbers(needle)
    words = [w for w in re.findall(r"[a-z]{3,}", needle) if w not in _STOP]
    if not numbers and not words:
        return False
    return numbers <= extract_numbers(haystack) and all(w in haystack for w in words)


def classify_answerable(result: dict[str, Any], question: dict[str, Any], chunks: dict[str, dict[str, Any]]) -> str:
    """correct | answered_incomplete | refused | rejected | error for one answerable question."""
    status = result["status"]
    if status == "answered":
        facts = question["expected_facts"]
        cited = normalize(" ".join(chunks[c]["text"] for c in result["citations"] if c in chunks))
        grounded = bool(set(result["citations"]) & set(question["relevant_chunks"])) or all(
            fact_present(cited, f) for f in facts
        )
        stated = all(fact_present(result["answer"], f) for f in facts)
        return "correct" if stated and grounded else "answered_incomplete"
    if status in REFUSED_STATUSES:
        return "refused"
    return "rejected" if status == "rejected_validation" else "error"


def classify_other(result: dict[str, Any]) -> str:
    """refused | withheld | answered | error for an out-of-scope or gap question. 'answered' is the failure."""
    status = result["status"]
    if status in REFUSED_STATUSES:
        return "refused"
    if status == "rejected_validation":
        return "withheld"  # a draft was written but the validators blocked it
    return "answered" if status == "answered" else "error"


def outcome_table(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Counts per question type and outcome."""
    table: dict[str, dict[str, int]] = {}
    for row in rows:
        cell = table.setdefault(row["type"], {"n": 0})
        cell["n"] += 1
        cell[row["outcome"]] = cell.get(row["outcome"], 0) + 1
    return table


def rejection_rate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Share of questions that reached the model and were then rejected by the code validators."""
    reached = [r for r in rows if r["status"] not in ("refused_insufficient_evidence", "llm_error")]
    rejected = sum(r["status"] == "rejected_validation" for r in reached)
    return {"rejected": rejected, "reached_llm": len(reached), "rate": round(rejected / len(reached), 3) if reached else None}


def run_generation(
    questions: list[dict[str, Any]], answer_fn: Callable[[str], dict[str, Any]], chunks: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Answer every question through the injected function and classify the outcome."""
    rows: list[dict[str, Any]] = []
    for q in questions:
        result = answer_fn(q["question"])
        outcome = classify_answerable(result, q, chunks) if q["type"] == "answerable" else classify_other(result)
        rows.append({
            "id": q["id"], "type": q["type"], "question": q["question"], "status": result["status"],
            "outcome": outcome, "answer": result["answer"], "citations": result["citations"],
            "issues": result["issues"], "draft_answer": result.get("draft_answer", ""),
            "evidence_reason": result.get("evidence_reason", ""),
        })
    return {"n_questions": len(rows), "table": outcome_table(rows), "rejection": rejection_rate(rows), "rows": rows}


def render_markdown(split: str, result: dict[str, Any], chunks: dict[str, dict[str, Any]]) -> str:
    """Outcome tables, per-question table, and a hand-check list of every answer shown to a user."""
    table, rows = result["table"], result["rows"]
    out = [
        f"# Generation evaluation: {split} split", "",
        f"{result['n_questions']} questions. Gold questions come from SYNTHETIC documents, so these scores are optimistic. "
        "Fact matching is automatic and a lower bound; check the answers listed at the end by hand.", "",
        "## Answerable questions", "",
        "| n | " + " | ".join(OUTCOMES_ANSWERABLE) + " |", "|---|" + "---|" * len(OUTCOMES_ANSWERABLE),
    ]
    cell = table.get("answerable", {"n": 0})
    out.append(f"| {cell['n']} | " + " | ".join(str(cell.get(o, 0)) for o in OUTCOMES_ANSWERABLE) + " |")
    out += ["", "## Out-of-scope and gap questions (refusal)", "",
            "| type | n | " + " | ".join(OUTCOMES_OTHER) + " |", "|---|---|" + "---|" * len(OUTCOMES_OTHER)]
    for kind in ("out_of_scope", "gap"):
        cell = table.get(kind, {"n": 0})
        out.append(f"| {kind} | {cell['n']} | " + " | ".join(str(cell.get(o, 0)) for o in OUTCOMES_OTHER) + " |")
    rej = result["rejection"]
    out += ["", "'answered' in this table is a failure: an unsupported question got an answer. 'withheld' means the model "
            "drafted something and the validators blocked it.", "",
            f"Validator rejection rate: {rej['rejected']}/{rej['reached_llm']} of the questions that reached the model "
            f"({rej['rate']}). Rejected drafts are never shown; some rejections are correct answers with a derived number.", "",
            "## Per question", "", "| id | type | status | outcome |", "|---|---|---|---|"]
    out += [f"| {r['id']} | {r['type']} | {r['status']} | {r['outcome']} |" for r in rows]
    out += ["", "## Hand check: every answer a user would see", "",
            "For each, mark whether every claim is supported by the cited text (yes or no).", ""]
    for r in (r for r in rows if r["status"] == "answered"):
        out += [f"### {r['id']} ({r['type']}, {r['outcome']})", f"Question: {r['question']}", f"Answer: {r['answer']}"]
        for cid in r["citations"]:
            text = " ".join(chunks.get(cid, {}).get("text", "(unknown chunk)").split())
            out.append(f"- `{cid}`: {text[:700]}")
        out += ["Supported by the cited text (hand): ____", "Answers the question (hand): ____", ""]
    cache = result.get("cache")
    if cache:
        out.append(f"Cache: {cache['hits']} replayed, {cache['misses']} new model calls.")
    return "\n".join(out) + "\n"


def main() -> None:
    """CLI: python -m eval.generation_eval [--split dev|heldout|agent] [--offline]"""
    parser = argparse.ArgumentParser(description="Generation, refusal and agent evaluation.")
    parser.add_argument("--split", choices=("dev", "heldout", "agent"), default="dev")
    parser.add_argument("--offline", action="store_true", help="replay from the cache only; no API key needed")
    parser.add_argument("--interval", type=float, default=config.EVAL_LLM_MIN_INTERVAL_S)
    args = parser.parse_args()
    config.use_utf8_stdout()
    config.configure_logging()
    for noisy in ("httpx", "httpx2", "huggingface_hub", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    from src.llm.client import get_llm_client, load_env_file

    load_env_file()
    client = CachingClient(
        None if args.offline else get_llm_client(), config.EVAL_LLM_CACHE,
        model_id=os.environ.get("LLM_MODEL", "unknown"), min_interval_s=args.interval, offline=args.offline,
    )
    config.ensure_dirs()
    if args.split == "agent":
        from eval import agent_eval

        result, name = agent_eval.run_with_client(client), "agent_routing"
        result["cache"] = {"hits": client.hits, "misses": client.misses}
        markdown = agent_eval.render_markdown(result)
    else:
        questions, chunks = load_gold(), load_chunks()
        problems = validate_gold(questions, chunks)
        if problems:
            raise SystemExit("Gold file does not match the documents:\n" + "\n".join(problems))
        if args.split == "heldout":
            logger.warning("Held-out run: report these numbers once, after prompts and thresholds are frozen.")
        from src.llm.answer import answer_question

        result = run_generation(
            [q for q in questions if q["split"] == args.split], lambda q: answer_question(q, client).to_dict(), chunks
        )
        result["cache"] = {"hits": client.hits, "misses": client.misses}
        name, markdown = f"generation_{args.split}", render_markdown(args.split, result, chunks)
    (config.RESULTS_DIR / f"{name}.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (config.RESULTS_DIR / f"{name}.md").write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()