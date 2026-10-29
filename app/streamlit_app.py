"""Streamlit UI. It talks to the FastAPI service only, through src.api.client.

Run from the repo root, with the API already running in another terminal:
    python -m streamlit run app\\streamlit_app.py
"""
from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from app.render import render_answer, render_prediction, render_report, render_trace
from src import config
from src.api.client import ApiClient, ApiError

st.set_page_config(page_title="Enterprise Intelligence Platform", layout="wide")

# Hints are facts from the Telco CSV (contract, internet service), not model output.
EXAMPLE_CUSTOMERS = (
    ("7590-VHVEG", "month-to-month, DSL"),
    ("1452-KIOVK", "month-to-month, fiber optic"),
    ("3668-QPYBK", "month-to-month, DSL"),
    ("8091-TTVAX", "one year, fiber optic"),
    ("5575-GNVDE", "one year, DSL"),
    ("7469-LKBCI", "two year, no internet service"),
)
DOC_EXAMPLES = (
    "What is the absolute cap on any retention discount?",
    "What is the maximum retention discount for Platinum tier customers?",  # in-scope-looking gap
    "What is the capital of France?",  # out of scope
)
AGENT_EXAMPLES = (
    "What is the churn rate for each contract type?",
    "Create a retention report for customer 7590-VHVEG.",
    "A Critical tier customer on a two year contract on Fiber optic with a $50 list price: "
    "what is the internet charge after the maximum combined discount?",
)


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


def _set(key: str, value: str) -> None:
    st.session_state[key] = value


def run_call(message: str, func: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any] | None:
    """Call the API behind a spinner. Errors are shown in place and returned as None."""
    with st.spinner(message):
        try:
            return func(*args, **kwargs)
        except ApiError as exc:
            st.error(str(exc))
            return None


def example_questions(key: str, examples: tuple[str, ...]) -> None:
    with st.expander("Example questions"):
        for index, text in enumerate(examples):
            st.button(text, key=f"{key}_ex{index}", on_click=_set, args=(key, text))


def sidebar(client: ApiClient) -> None:
    st.sidebar.header("API")
    st.sidebar.caption(client.base_url)
    try:
        health = client.health()
    except ApiError as exc:
        st.sidebar.error(str(exc))
        return
    missing = [name for name, ok in health.items() if name != "status" and not ok]
    if health["status"] == "ok":
        st.sidebar.success("API ready")
    else:
        st.sidebar.warning("API degraded. Missing: " + ", ".join(missing))


def report_tab(client: ApiClient) -> None:
    st.session_state.setdefault("customer_id", EXAMPLE_CUSTOMERS[0][0])
    st.text_input("Customer ID (must exist in the Telco CSV)", key="customer_id")
    columns = st.columns(len(EXAMPLE_CUSTOMERS))
    for column, (cid, hint) in zip(columns, EXAMPLE_CUSTOMERS):
        column.button(cid, key=f"cust_{cid}", help=hint, on_click=_set, args=("customer_id", cid))
    customer_id = st.session_state["customer_id"].strip()
    left, right = st.columns(2)
    if left.button("Full report (prediction + cited actions)", type="primary", key="report_btn"):
        st.session_state["report"] = run_call("Building report (the first call can take a minute)...", client.report, customer_id)
        st.session_state["prediction"] = None
    if right.button("Prediction only (no language model)", key="predict_btn"):
        st.session_state["prediction"] = run_call("Predicting...", client.predict, customer_id)
        st.session_state["report"] = None
    if st.session_state.get("report"):
        render_report(st.session_state["report"])
    elif st.session_state.get("prediction"):
        render_prediction(st.session_state["prediction"])


def ask_tab(client: ApiClient) -> None:
    st.session_state.setdefault("ask_q", DOC_EXAMPLES[0])
    st.text_area("Question about the policy, plans and terms documents", key="ask_q", height=80)
    example_questions("ask_q", DOC_EXAMPLES)
    with st.expander("Retrieval settings"):
        mode = st.selectbox("Retrieval mode", ("hybrid", "dense", "bm25"), key="ask_mode")
        k = st.slider("Chunks retrieved (k)", 1, config.API_MAX_K, config.GEN_K, key="ask_k")
    if st.button("Ask", type="primary", key="ask_btn"):
        st.session_state["ask_result"] = run_call(
            "Searching the documents...", client.ask, st.session_state["ask_q"], k=k, mode=mode
        )
    result = st.session_state.get("ask_result")
    if result:
        render_answer(result)
        st.caption(f"Retrieval: {result['evidence_reason']}")


def agent_tab(client: ApiClient) -> None:
    st.session_state.setdefault("agent_q", AGENT_EXAMPLES[0])
    st.text_area("Ask the agent (it chooses between document search, data analysis, calculator and report)", key="agent_q", height=80)
    example_questions("agent_q", AGENT_EXAMPLES)
    if st.button("Run agent", type="primary", key="agent_btn"):
        st.session_state["agent_result"] = run_call("Agent working (up to 5 tool calls)...", client.agent, st.session_state["agent_q"])
    result = st.session_state.get("agent_result")
    if result:
        render_answer(result)
        render_trace(result["trace"], result["steps_used"])


def main() -> None:
    client = get_client()
    st.title("Autonomous Enterprise Intelligence Platform")
    st.caption(
        "Churn model and customer table: real Telco data. "
        "Policy, plans, pricing and service-terms documents: SYNTHETIC (generated for this assignment)."
    )
    sidebar(client)
    report, ask, agent = st.tabs(["Customer report", "Ask the documents", "Agent"])
    with report:
        report_tab(client)
    with ask:
        ask_tab(client)
    with agent:
        agent_tab(client)


main()