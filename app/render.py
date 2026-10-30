"""Rendering helpers for the Streamlit UI. They only turn API reply dicts into widgets."""
from __future__ import annotations

import json
from typing import Any

import streamlit as st

# Text for a report that has no recommendations, keyed by report status (the API returns the status only).
NO_RECOMMENDATION_TEXT: dict[str, str] = {
    "all_withheld": "Every drafted recommendation failed validation. See the withheld list below.",
    "no_recommendations": "The model returned no recommendations for this evidence.",
    "no_playbook_evidence": "The playbook for this tier and contract was not retrieved, so the model was not asked.",
    "no_internet_service": "Not applicable: the customer has no internet service, and the policy ties retention discounts to the internet plan.",
    "llm_error": "The language model call failed, so no recommendations were generated.",
}


def plain(text: Any) -> str:
    """Escape $ so Streamlit does not render prices such as $50 and $30 as LaTeX math."""
    return str(text).replace("$", "\\$").replace("[", "\\[")


def fmt_location(location: dict[str, Any] | None) -> str:
    """Whatever location keys exist (page, section, row); never assume a page number."""
    if not location:
        return "location not recorded"
    return ", ".join(f"{key}: {value}" for key, value in location.items())


def render_citations(details: list[dict[str, Any]]) -> None:
    """One expander per cited chunk. Must not be called inside another expander (Streamlit forbids nesting)."""
    if not details:
        return
    st.markdown("**Sources**")
    for chunk in details:
        with st.expander(f"{chunk['chunk_id']} - {chunk['source']} ({fmt_location(chunk['location'])})"):
            st.text(chunk["text"])


def render_answer(result: dict[str, Any]) -> None:
    """Show an /ask or /agent reply according to its status. Only 'answered' is shown as an answer."""
    status = result["status"]
    if status == "answered":
        st.markdown(plain(result["answer"]))
    elif status in ("refused_insufficient_evidence", "refused_model"):
        st.info(plain(result["answer"]))
    elif status == "rejected_validation":
        st.warning(
            "The model's draft failed the automatic citation and number checks and was withheld. "
            "Nothing is shown rather than something unverified."
        )
    else:
        st.error(plain(result["answer"]))
    render_citations(result.get("citation_details", []))
    if result.get("issues"):
        with st.expander("Validation issues"):
            for issue in result["issues"]:
                st.text(issue)
    st.caption(f"Status: {status}. {result.get('notice', '')}")


def render_trace(trace: list[dict[str, Any]], steps_used: int) -> None:
    st.markdown(f"**Agent trace** ({steps_used} tool call(s))")
    if not trace:
        st.caption("The agent answered without calling a tool.")
        return
    st.dataframe(
        [
            {
                "step": t["step"], "tool": t["tool"], "arguments": json.dumps(t["arguments"]),
                "ok": t["ok"], "seconds": t["seconds"], "result preview": t["result_preview"],
            }
            for t in trace
        ],
        hide_index=True,
    )


def render_drivers(drivers: list[dict[str, Any]]) -> None:
    """Top SHAP drivers. customer_value is cast to text because the column mixes numbers and strings."""
    st.markdown("**Top drivers of the churn prediction (SHAP)**")
    st.dataframe(
        [
            {
                "feature": d["feature"], "customer value": str(d["customer_value"]),
                "effect": d["effect"], "contribution": round(d["contribution"], 4),
            }
            for d in drivers
        ],
        hide_index=True,
    )


def render_prediction(pred: dict[str, Any]) -> None:
    st.subheader(f"Prediction for {pred['customer_id']}")
    left, right = st.columns(2)
    left.metric("Churn probability", f"{pred['prob']:.4f}")
    right.metric("Predicted label", pred["label"])
    render_drivers(pred["top_drivers"])


def render_report(report: dict[str, Any]) -> None:
    """Full report: ML section, cited recommendations, then everything the validators withheld or noted."""
    pred, profile = report["prediction"], report["profile"]
    st.subheader(f"Report for {report['customer_id']}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Churn probability", f"{pred['prob']:.4f}")
    c2.metric("Risk tier", report["tier"])
    c3.metric("Report status", report["status"])
    st.caption(
        f"Contract: {profile.get('Contract')} | Internet: {profile.get('InternetService')} | "
        f"Tenure: {profile.get('tenure')} months | Monthly charges: {profile.get('MonthlyCharges')} | "
        f"Payment: {profile.get('PaymentMethod')}"
    )
    render_drivers(pred["top_drivers"])
    st.markdown("**Recommended retention actions (from the synthetic documents)**")
    by_id = {c["chunk_id"]: c for c in report["evidence"]}
    if report["recommendations"]:
        for number, rec in enumerate(report["recommendations"], 1):
            st.markdown(f"{number}. {plain(rec['text'])}")
            sources = "; ".join(
                f"{cid} ({by_id[cid]['source']}, {fmt_location(by_id[cid].get('location'))})"
                for cid in rec["citations"] if cid in by_id
            )
            st.caption(f"Sources: {sources}")
    else:
        st.info(NO_RECOMMENDATION_TEXT.get(report["status"], "No recommendations. See the notes below."))
    with st.expander(f"Withheld by validation ({len(report['withheld'])})"):
        if not report["withheld"]:
            st.write("Nothing was withheld.")
        for item in report["withheld"]:
            st.text(f"{item['text']}\n  -> {'; '.join(item['issues'])}")
    with st.expander(f"Evidence shown to the model ({len(report['evidence'])})"):
        st.dataframe(
            [
                {
                    "chunk_id": c["chunk_id"], "source": c["source"],
                    "location": fmt_location(c.get("location")), "retrieval score": c.get("score"),
                }
                for c in report["evidence"]
            ],
            hide_index=True,
        )
    with st.expander("Notes and limitations"):
        for note in report["notes"]:
            st.text(note)
    st.download_button(
        "Download report (.md)", data=report["markdown"], file_name=report["report_file"],
        mime="text/markdown", key="dl_report",
    )
    st.caption(report["notice"])