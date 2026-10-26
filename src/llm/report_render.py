"""Markdown rendering for a Report. Pure functions: no LLM, no retrieval."""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src import config

if TYPE_CHECKING:
    from src.llm.report import Report

LIMITATIONS: tuple[str, ...] = (
    "predict_customer works only for customer ids present in the Telco CSV.",
    "Recommendations are model-drafted. Code checks that cited ids exist and that every number "
    "appears in a cited chunk (a text match). It does not check that the wording is right.",
    "Only evidence for this customer's tier and contract type is shown to the model. "
    "That filter relies on the wording of the documents.",
)


def _cell(value: Any) -> str:
    """Make a value safe inside a markdown table cell."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _fmt_score(score: Any) -> str:
    return f"{score:.3f}" if isinstance(score, (int, float)) else _cell("n/a" if score is None else score)


def format_location(location: dict[str, Any] | None) -> str:
    """Render whatever location keys exist (page/section/row); never assume a page number."""
    if not location:
        return "location not recorded"
    return ", ".join(f"{key}: {value}" for key, value in location.items())


def render_markdown(report: "Report") -> str:
    """Build the full markdown text of a report."""
    pred, prof = report.prediction, report.profile
    by_id = {c["chunk_id"]: c for c in report.evidence}
    out = [
        f"# Churn risk report: {report.customer_id}",
        "",
        f"Report status: **{report.status}**",
        "",
        "## 1. Risk prediction (ML model, real Telco data)",
        "",
        f"- Churn probability: {pred.get('prob')} (predicted label: {pred.get('label')})",
        f"- Risk tier: {report.tier}",
        f"- Contract: {prof.get('Contract')}; internet service: {prof.get('InternetService')}; "
        f"tenure: {prof.get('tenure')} months; monthly charges: {prof.get('MonthlyCharges')}; "
        f"payment method: {prof.get('PaymentMethod')}",
        "",
        "| Feature | Customer value | Effect | Contribution |",
        "|---|---|---|---|",
    ]
    out += [
        f"| {_cell(d.get('feature'))} | {_cell(d.get('customer_value'))} | "
        f"{_cell(d.get('effect'))} | {_cell(d.get('contribution'))} |"
        for d in pred.get("top_drivers", [])
    ]
    out += ["", "## 2. Recommended retention actions (from documents)", ""]
    if report.recommendations:
        for number, rec in enumerate(report.recommendations, 1):
            out.append(f"{number}. {rec.text}")
            for cid in rec.citations:
                chunk = by_id.get(cid, {})
                out.append(f"   - Source `{cid}`: {chunk.get('source')} ({format_location(chunk.get('location'))})")
    else:
        out.append("No recommendation passed validation. See notes below.")
    out += ["", "## 3. Withheld by validation (unsupported, omitted from section 2)", ""]
    if report.withheld:
        out += [f"- \"{w.text}\" -- {'; '.join(w.issues)}" for w in report.withheld]
    else:
        out.append("Nothing was withheld.")
    out += [
        "",
        "## 4. Evidence shown to the model",
        "",
        "| chunk_id | source | location | retrieval score |",
        "|---|---|---|---|",
    ]
    out += [
        f"| {_cell(c['chunk_id'])} | {_cell(c.get('source'))} | "
        f"{_cell(format_location(c.get('location')))} | {_fmt_score(c.get('score'))} |"
        for c in report.evidence
    ]
    out += ["", "## 5. Notes and limitations", ""]
    out += [f"- {note}" for note in [*report.notes, *LIMITATIONS]]
    return "\n".join(out) + "\n"


def write_report(report: "Report", out_dir: Path | None = None) -> Path:
    """Write report_<id>.md (UTF-8) and return its path."""
    directory = out_dir or config.REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", report.customer_id)
    path = directory / f"report_{safe_id}.md"
    path.write_text(render_markdown(report), encoding="utf-8")
    return path