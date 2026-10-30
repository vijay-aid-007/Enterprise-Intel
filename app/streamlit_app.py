"""Streamlit UI. It talks to the FastAPI service only, through src.api.client.

Run from the repo root (the theme is read from .streamlit/config.toml there), with the API already running:
    python -m streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import inspect
from html import escape
from typing import Any, Callable

import streamlit as st

from app import theme
from app.render import render_answer, render_prediction, render_report, render_trace
from src import config
from src.api.client import ApiClient, ApiError

st.set_page_config(page_title="Enterprise Intelligence Platform", layout="wide", initial_sidebar_state="expanded")

# All test-split customers, so scores are not in-sample. Hints are facts from the Telco CSV, not model output.
DEMO_CUSTOMERS = (
    ("1024-GUALD", "Month-to-month, DSL"),
    ("7495-OOKFY", "Month-to-month, Fiber optic"),
    ("1452-KIOVK", "Month-to-month, Fiber optic"),
    ("3930-ZGWVE", "Month-to-month, no internet service"),
    ("7251-LJBQN", "One year, Fiber optic"),
    ("4190-MFLUW", "Month-to-month, DSL"),
    ("0959-WHOKV", "One year, Fiber optic"),
    ("6322-HRPFA", "Month-to-month, DSL"),
    ("6388-TABGU", "One year, DSL"),
    ("2954-PIBKO", "Two year, DSL"),
)
DEMO_HINTS = dict(DEMO_CUSTOMERS)
DEFAULT_CUSTOMER = "1452-KIOVK"
DOC_EXAMPLES = (
    ("Retention cap", "What is the absolute cap on any retention discount?"),
    ("Unsupported topic", "What is the maximum retention discount for Platinum tier customers?"),
    ("Out of scope", "What is the capital of France?"),
)
AGENT_EXAMPLES = (
    ("Churn by contract", "What is the churn rate for each contract type?"),
    ("Retention report", "Create a retention report for customer 1452-KIOVK."),
    ("Discount arithmetic", "A Critical tier customer on a two year contract on Fiber optic with a $50 list price: "
     "what is the internet charge after the maximum combined discount?"),
)
HEALTH_ITEMS = (
    ("has_model", "Churn model"), ("has_chunks", "Document chunks"),
    ("has_index", "Vector index"), ("llm_key_set", "Language model key"),
)
LEGEND = (
    ("answered", "Passed every automatic check."),
    ("refused_insufficient_evidence", "Nothing in the documents was close enough; the model was never called."),
    ("refused_model", "The model judged that the passages do not contain the answer."),
    ("rejected_validation", "A draft failed the code checks and was withheld."),
)
CHECKS = (
    "An evidence threshold before the model is called",
    "Cited passages must have been retrieved",
    "Numbers must appear in a cited passage",
    "An answer may not name a document it did not cite",
    "Tools run with validated arguments and step limits",
)
OFFLINE_HINT = "The API is offline. Start it with: python -m src.api.main"
# Full-width buttons: `width="stretch"` on current Streamlit, `use_container_width` on older releases.
STRETCH: dict[str, Any] = (
    {"width": "stretch"} if "width" in inspect.signature(st.button).parameters else {"use_container_width": True}
)


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


def _set(key: str, value: str) -> None:
    st.session_state[key] = value


def _pick() -> None:
    chosen = st.session_state.get("pick", "")
    if chosen:
        st.session_state["customer_id"] = chosen


def _clear() -> None:
    for key in ("report", "prediction", "ask_result", "agent_result"):
        st.session_state.pop(key, None)


def _demo_label(value: str) -> str:
    return f"{value}  ({DEMO_HINTS[value]})" if value else "Select a demo customer"


def run_call(message: str, func: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any] | None:
    """Call the API behind a spinner. Errors are shown in place and returned as None."""
    with st.spinner(message):
        try:
            return func(*args, **kwargs)
        except ApiError as exc:
            st.error(str(exc))
            return None


def examples(key: str, items: tuple[tuple[str, str], ...]) -> None:
    columns = st.columns(len(items))
    for index, (label, text) in enumerate(items):
        columns[index].button(label, key=f"{key}_ex{index}", help=text, on_click=_set, args=(key, text), **STRETCH)


def fetch_health(client: ApiClient) -> tuple[dict[str, Any] | None, str]:
    try:
        return client.health(), ""
    except ApiError as exc:
        return None, str(exc)


def sidebar(client: ApiClient, health: dict[str, Any] | None, error: str) -> None:
    side = st.sidebar
    side.markdown('<div class="ei-section">System status</div>', unsafe_allow_html=True)
    if health is None:
        side.error(error)
        side.code("python -m src.api.main", language="bash")
    else:
        rows = [(label, bool(health.get(key))) for key, label in HEALTH_ITEMS]
        side.markdown(theme.status_rows(rows), unsafe_allow_html=True)
    side.caption(f"Endpoint: {client.base_url}")
    side.divider()
    with side.expander("Reading the results"):
        for status, text in LEGEND:
            label, tone = theme.status_label(status)
            st.markdown(f"{theme.chip(label, tone)}<br><small>{escape(text)}</small>", unsafe_allow_html=True)
    with side.expander("Checks that run in code"):
        for item in CHECKS:
            st.markdown(f"- {item}")
    side.button("Clear results", key="clear_btn", on_click=_clear, **STRETCH)


def report_tab(client: ApiClient, offline: bool) -> None:
    st.session_state.setdefault("customer_id", DEFAULT_CUSTOMER)
    with st.container(border=True):
        # One toolbar row: inputs and actions share a baseline (needs Streamlit 1.36+ for vertical_alignment).
        pick, ident, full_col, pred_col = st.columns([3.2, 2, 1.5, 1.3], vertical_alignment="bottom")
        pick.selectbox(
            "Demo customer", [""] + [cid for cid, _ in DEMO_CUSTOMERS], key="pick",
            format_func=_demo_label, on_change=_pick, help="Test-split customers the model was not trained on.",
        )
        ident.text_input("Customer ID", key="customer_id", help="Any customer ID from the Telco CSV.")
        run_full = full_col.button("Generate report", type="primary", key="report_btn", disabled=offline,
                                   help=OFFLINE_HINT if offline else "Prediction, drivers and retention actions.", **STRETCH)
        run_pred = pred_col.button("Score only", key="predict_btn", disabled=offline,
                                   help=OFFLINE_HINT if offline else "Fast: no language model call.", **STRETCH)
    customer_id = st.session_state["customer_id"].strip()
    if run_full or run_pred:
        if not customer_id:
            st.warning("Enter a customer ID first.")
        elif run_full:
            st.session_state["report"] = run_call("Building the report. The first call after startup can take a minute.", client.report, customer_id)
            st.session_state["prediction"] = None
        else:
            st.session_state["prediction"] = run_call("Scoring...", client.predict, customer_id)
            st.session_state["report"] = None
    if st.session_state.get("report"):
        render_report(st.session_state["report"])
    elif st.session_state.get("prediction"):
        render_prediction(st.session_state["prediction"])
    else:
        theme.empty_state("No report yet", "Select a demo customer or enter an ID, then choose Generate report.")


def ask_tab(client: ApiClient, offline: bool) -> None:
    st.session_state.setdefault("ask_q", DOC_EXAMPLES[0][1])
    with st.container(border=True):
        st.text_area("Question about the policy, plans and terms documents", key="ask_q", height=90)
        st.caption("Examples. The second and third show how unsupported questions are handled.")
        examples("ask_q", DOC_EXAMPLES)
        with st.expander("Retrieval settings"):
            left, right = st.columns(2)
            mode = left.selectbox("Retrieval mode", ("hybrid", "dense", "bm25"), key="ask_mode")
            k = right.slider("Passages retrieved (k)", 1, config.API_MAX_K, config.GEN_K, key="ask_k")
        run = st.button("Ask", type="primary", key="ask_btn", disabled=offline, help=OFFLINE_HINT if offline else None, **STRETCH)
    if run:
        st.session_state["ask_result"] = run_call("Searching the documents...", client.ask, st.session_state["ask_q"], k=k, mode=mode)
    result = st.session_state.get("ask_result")
    if result:
        render_answer(result)
        st.caption(f"Retrieved: {', '.join(result['retrieved_ids']) or 'nothing'} | signal: {result['evidence_reason']}")
    else:
        theme.empty_state("No answer yet", "Ask a question about the documents. Every answer cites its sources.")


def agent_tab(client: ApiClient, offline: bool) -> None:
    st.session_state.setdefault("agent_q", AGENT_EXAMPLES[0][1])
    with st.container(border=True):
        st.text_area("Question for the agent", key="agent_q", height=90)
        st.caption("The agent chooses between document search, data analysis, a calculator and report generation.")
        examples("agent_q", AGENT_EXAMPLES)
        run = st.button("Run agent", type="primary", key="agent_btn", disabled=offline, help=OFFLINE_HINT if offline else None, **STRETCH)
    if run:
        st.session_state["agent_result"] = run_call(f"Agent working (up to {config.AGENT_MAX_STEPS} tool calls)...", client.agent, st.session_state["agent_q"])
    result = st.session_state.get("agent_result")
    if result:
        render_answer(result)
        render_trace(result["trace"], result["steps_used"])
    else:
        theme.empty_state("No run yet", "Ask a question. Every tool call the agent makes appears here.")


def main() -> None:
    theme.inject_css()
    client = get_client()
    health, error = fetch_health(client)
    offline = health is None
    if offline:
        status_text, tone = "API offline", "danger"
    else:
        status_text, tone = ("API operational", "success") if health.get("status") == "ok" else ("API degraded", "warning")
    theme.header("Enterprise Intelligence Platform", "Churn risk, cited policy answers and a tool-using agent", status_text, tone)
    theme.provenance()
    sidebar(client, health, error)
    report, ask, agent = st.tabs(["Customer report", "Ask the documents", "Agent"])
    with report:
        report_tab(client, offline)
    with ask:
        ask_tab(client, offline)
    with agent:
        agent_tab(client, offline)


main()