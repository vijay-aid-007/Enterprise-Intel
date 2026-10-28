"""Retrieval evaluation (Step 9a): hit@k and MRR for dense, bm25 and hybrid, plus a DENSE_MIN_SIM sweep.

Protocol: tune on the dev split only (the default). Run `--split heldout` once, after the retrieval mode
and DENSE_MIN_SIM are frozen. Gold questions come from SYNTHETIC documents, so scores are optimistic.

    python -m eval.retrieval_eval --split dev
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Iterable

from src import config

logger = logging.getLogger(__name__)

TYPES: tuple[str, ...] = ("answerable", "out_of_scope", "gap")
SPLITS: tuple[str, ...] = ("dev", "heldout")
_ODD_CHARS = str.maketrans(
    {"\u00a0": " ", "\u2009": " ", "\u202f": " ", "\u200b": "", "\u2010": "-", "\u2011": "-", "\u2012": "-"}
)

RetrieveFn = Callable[[str, int, str], list[dict[str, Any]]]  # (query, k, mode) -> chunks
EvidenceFn = Callable[[str], Any]  # query -> object with dense_top, bm25_top, sufficient


def normalize(text: str) -> str:
    """Lower-case, map odd spaces and hyphens to plain ones, collapse whitespace: eval matching ignores formatting."""
    return re.sub(r"\s+", " ", text.translate(_ODD_CHARS).lower()).strip()


def load_gold(path: Path = config.GOLD_JSON) -> list[dict[str, Any]]:
    """Gold questions from eval/gold_questions.json."""
    return json.loads(path.read_text(encoding="utf-8"))["questions"]


def load_chunks(path: Path = config.CHUNKS_JSONL) -> dict[str, dict[str, Any]]:
    """chunks.jsonl as {chunk_id: row}."""
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    return {row["chunk_id"]: row for row in rows}


def validate_gold(questions: list[dict[str, Any]], chunks: dict[str, dict[str, Any]]) -> list[str]:
    """Check every label against the real chunks. An empty list means the gold file matches the documents.

    Only chunks of the generation doc types count, because support tickets are never shown to the model.
    """
    usable = {cid: c for cid, c in chunks.items() if c.get("doc_type") in config.GEN_DOC_TYPES}
    corpus = normalize(" ".join(c["text"] for c in usable.values()))
    problems: list[str] = []
    ids = [q.get("id") for q in questions]
    if len(set(ids)) != len(ids):
        problems.append("duplicate question ids")
    for q in questions:
        qid, kind = q.get("id", "?"), q.get("type")
        if kind not in TYPES or q.get("split") not in SPLITS or not str(q.get("question", "")).strip():
            problems.append(f"{qid}: bad type, split or question text")
            continue
        relevant, facts = q.get("relevant_chunks", []), q.get("expected_facts", [])
        if kind != "answerable":
            if relevant or facts:
                problems.append(f"{qid}: {kind} question must not list relevant chunks or facts")
        else:
            bad = [cid for cid in relevant if cid not in usable]
            if not relevant or bad:
                problems.append(f"{qid}: relevant chunk missing, unknown or not retrievable: {bad}")
                continue
            if not facts:
                problems.append(f"{qid}: answerable question needs expected_facts")
            text = normalize(" ".join(usable[cid]["text"] for cid in relevant))
            problems += [f"{qid}: fact not in relevant chunks: {f!r}" for f in facts if normalize(f) not in text]
        
        terms = q.get("absent_terms", [])    
        if kind == "gap" and not terms:
            problems.append(f"{qid}: gap question needs absent_terms")
        if kind == "answerable" and terms:
            problems.append(f"{qid}: answerable questions must not list absent_terms")
        problems += [
            f"{qid}: term appears in the documents, so this is not a gap: {t!r}"
            for t in terms if normalize(t) in corpus
        ]
    return problems


def first_relevant_rank(ranked_ids: list[str], relevant: Iterable[str]) -> int | None:
    """1-based rank of the first relevant chunk, or None if none was retrieved."""
    wanted = set(relevant)
    return next((i for i, cid in enumerate(ranked_ids, 1) if cid in wanted), None)


def summarize_ranks(ranks: list[int | None], ks: Iterable[int]) -> dict[str, Any]:
    """hit@k (count and rate) and MRR over ranks; None counts as a miss."""
    n = len(ranks)
    out: dict[str, Any] = {"n": n}
    for k in ks:
        hits = sum(1 for r in ranks if r is not None and r <= k)
        out[f"hit@{k}"] = {"hits": hits, "rate": round(hits / n, 3) if n else None}
    out["mrr"] = round(sum(1 / r for r in ranks if r) / n, 3) if n else None
    return out


def refusal_table(rows: list[dict[str, Any]], refused: Callable[[dict[str, Any]], bool]) -> dict[str, dict[str, int]]:
    """Per question type: how many rows were refused out of how many."""
    table = {t: {"refused": 0, "n": 0} for t in TYPES}
    for row in rows:
        table[row["type"]]["n"] += 1
        table[row["type"]]["refused"] += int(bool(refused(row)))
    return table


def sweep(rows: list[dict[str, Any]], thresholds: Iterable[float]) -> list[dict[str, Any]]:
    """Refusal counts at each candidate threshold, assuming 'refuse when top dense similarity < threshold'."""
    return [{"threshold": t, **refusal_table(rows, lambda r, t=t: r["dense_top"] < t)} for t in thresholds]


def suggest_threshold(rows: list[dict[str, Any]]) -> float | None:
    """Midpoint between the best out-of-scope score and the worst answerable score; None if they overlap.

    Gap questions are left out on purpose: they look in-scope, so retrieval alone cannot separate them.
    """
    answerable = [r["dense_top"] for r in rows if r["type"] == "answerable"]
    out_of_scope = [r["dense_top"] for r in rows if r["type"] == "out_of_scope"]
    if not answerable or not out_of_scope or max(out_of_scope) >= min(answerable):
        return None
    return round((max(out_of_scope) + min(answerable)) / 2, 3)


def sufficiency_is_dense_only(rows: list[dict[str, Any]], threshold: float) -> bool:
    """True if the retriever's `sufficient` flag equals (dense_top >= threshold) on every row, as the sweep assumes."""
    return all(bool(r["sufficient"]) == (r["dense_top"] >= threshold) for r in rows)


def run_split(
    questions: list[dict[str, Any]],
    retrieve_fn: RetrieveFn,
    evidence_fn: EvidenceFn,
    *,
    modes: Iterable[str],
    ks: Iterable[int],
    max_rank: int,
    thresholds: Iterable[float],
    configured_threshold: float,
) -> dict[str, Any]:
    """Ablation, refusal table and threshold sweep for one split. Retrieval functions are injected, so tests need no models."""
    modes, ks = tuple(modes), tuple(ks)
    rows: list[dict[str, Any]] = []
    ranks: dict[str, list[int | None]] = {m: [] for m in modes}
    for q in questions:
        evidence = evidence_fn(q["question"])
        row: dict[str, Any] = {
            "id": q["id"], "type": q["type"], "question": q["question"],
            "dense_top": float(evidence.dense_top), "bm25_top": float(evidence.bm25_top),
            "sufficient": bool(evidence.sufficient), "ranks": {},
        }
        if q["type"] == "answerable":
            for mode in modes:
                ids = [c["chunk_id"] for c in retrieve_fn(q["question"], max_rank, mode)]
                row["ranks"][mode] = first_relevant_rank(ids, q["relevant_chunks"])
                ranks[mode].append(row["ranks"][mode])
        rows.append(row)
    return {
        "n_questions": len(rows),
        "ablation": {m: summarize_ranks(ranks[m], ks) for m in modes},
        "refusal_at_configured": {
            "threshold": configured_threshold,
            "table": refusal_table(rows, lambda r: not r["sufficient"]),
        },
        "sweep": sweep(rows, thresholds),
        "suggested_threshold": suggest_threshold(rows),
        "dense_only_rule_holds": sufficiency_is_dense_only(rows, configured_threshold),
        "rows": rows,
    }


def render_markdown(split: str, result: dict[str, Any], ks: Iterable[int]) -> str:
    """Tables for the README: ablation, refusal at the configured threshold, threshold sweep, per-question ranks."""
    ks = tuple(ks)
    out = [
        f"# Retrieval evaluation: {split} split", "",
        f"{result['n_questions']} questions. Gold questions come from SYNTHETIC documents, so these scores are "
        "optimistic. Relevance labels are not exhaustive.", "",
        "## Ablation (answerable questions only)", "",
        "| mode | n | " + " | ".join(f"hit@{k}" for k in ks) + " | MRR |",
        "|---|---|" + "---|" * (len(ks) + 1),
    ]
    for mode, s in result["ablation"].items():
        cells = " | ".join(f"{s[f'hit@{k}']['hits']}/{s['n']}" for k in ks)
        out.append(f"| {mode} | {s['n']} | {cells} | {s['mrr']} |")
    cfg = result["refusal_at_configured"]
    out += ["", f"## Refusal at the configured threshold ({cfg['threshold']})", "",
            "| question type | refused / n |", "|---|---|"]
    out += [f"| {t} | {cfg['table'][t]['refused']}/{cfg['table'][t]['n']} |" for t in TYPES]
    out += ["", "Target: no answerable question refused, every out_of_scope question refused. Gap questions look "
            "in-scope to retrieval, so the model has to refuse them (generation eval).", "",
            "## Threshold sweep (refuse when top dense similarity < threshold)", "",
            "| threshold | answerable refused | out_of_scope refused | gap refused |", "|---|---|---|---|"]
    for row in result["sweep"]:
        out.append(f"| {row['threshold']} | " + " | ".join(f"{row[t]['refused']}/{row[t]['n']}" for t in TYPES) + " |")
    out += ["", f"Suggested threshold (midpoint of the best out-of-scope and worst answerable score): "
            f"{result['suggested_threshold']}",
            f"Sufficiency is dense-only at the configured threshold: {result['dense_only_rule_holds']}", ""]
    modes = list(result["ablation"])
    out += ["## Per question", "",
            "| id | type | top dense sim | " + " | ".join(f"rank {m}" for m in modes) + " | refused |",
            "|---|---|---|" + "---|" * (len(modes) + 1)]
    for r in result["rows"]:
        ranks = " | ".join(
            "n/a" if m not in r["ranks"] else ("miss" if r["ranks"][m] is None else str(r["ranks"][m]))
            for m in modes
        )
        out.append(f"| {r['id']} | {r['type']} | {r['dense_top']:.3f} | {ranks} | {not r['sufficient']} |")
    return "\n".join(out) + "\n"


def main() -> None:
    """CLI: python -m eval.retrieval_eval [--split dev|heldout]"""
    parser = argparse.ArgumentParser(description="Retrieval ablation and threshold sweep.")
    parser.add_argument("--split", choices=SPLITS, default="dev")
    args = parser.parse_args()
    config.configure_logging()
    questions, chunks = load_gold(), load_chunks()
    problems = validate_gold(questions, chunks)
    if problems:
        raise SystemExit("Gold file does not match the documents:\n" + "\n".join(problems))
    if args.split == "heldout":
        logger.warning("Held-out run: report these numbers once, after the threshold and mode are frozen.")
    from src.rag.retriever import MODES, check_evidence, retrieve  # lazy: keeps the embedder out of test imports

    result = run_split(
        [q for q in questions if q["split"] == args.split],
        lambda query, k, mode: retrieve(query, k, mode=mode, doc_types=config.GEN_DOC_TYPES),
        lambda query: check_evidence(query, doc_types=config.GEN_DOC_TYPES),
        modes=MODES, ks=config.EVAL_KS, max_rank=config.EVAL_MAX_RANK,
        thresholds=config.EVAL_SWEEP, configured_threshold=config.DENSE_MIN_SIM,
    )
    config.ensure_dirs()
    (config.RESULTS_DIR / f"retrieval_{args.split}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    markdown = render_markdown(args.split, result, config.EVAL_KS)
    (config.RESULTS_DIR / f"retrieval_{args.split}.md").write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()