"""Step 8 smoke tests. The API is faked with httpx.MockTransport or monkeypatched client methods.

They prove the client's requests and error messages, the status-text coverage, the $ escaping, and that the
app script runs without exceptions. They do not prove how the page looks; only the manual browser run does.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.render import NO_RECOMMENDATION_TEXT, plain
from src.api.client import ApiClient, ApiError
from src.llm.report import REPORT_STATUSES

APP_PATH = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
HEALTH_OK = {"status": "ok", "has_model": True, "has_chunks": True, "has_index": True, "llm_key_set": True}
FAKE_REPORT = {
    "customer_id": "7590-VHVEG", "profile": {"Contract": "Month-to-month", "InternetService": "DSL"},
    "prediction": {"prob": 0.85, "label": "churn", "top_drivers": [
        {"feature": "tenure", "customer_value": 1.0, "contribution": 0.8, "effect": "raises churn risk"}]},
    "tier": "Critical", "status": "complete",
    "recommendations": [{"text": "Offer 30% for 6 months, a $50 credit.", "citations": ["t-0001"]}],
    "withheld": [], "notes": ["a note"], "notice": "SYNTHETIC", "report_file": "report_7590-VHVEG.md",
    "markdown": "# report",
    "evidence": [{"chunk_id": "t-0001", "text": "30%", "source": "retention_policy.pdf",
                  "score": 0.03, "location": {"page": 3}}],
}


def make_client(handler) -> ApiClient:
    return ApiClient("http://test", transport=httpx.MockTransport(handler))


def test_client_sends_expected_requests() -> None:
    seen: list[tuple[str, str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, json.loads(request.content) if request.content else None))
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    client.health()
    client.predict(" 7590-VHVEG ")
    client.ask("q", k=3, mode="dense")
    client.agent("a")
    client.report("7590-VHVEG")
    assert seen == [
        ("GET", "/health", None),
        ("POST", "/predict", {"customer_id": "7590-VHVEG"}),
        ("POST", "/ask", {"question": "q", "k": 3, "mode": "dense"}),
        ("POST", "/agent", {"question": "a"}),
        ("POST", "/report", {"customer_id": "7590-VHVEG"}),
    ]


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (404, {"detail": "customer id not found"}, "customer id not found"),
        (422, {"detail": [{"msg": "String should have at least 1 character"}]}, "Invalid input: String should"),
        (503, {"detail": "A required data, model or index file is missing"}, "missing"),
        (500, "oops", "API error 500"),
    ],
)
def test_http_errors_become_readable_messages(status: int, body: Any, expected: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body) if isinstance(body, dict) else httpx.Response(status, text=body)

    with pytest.raises(ApiError) as info:
        make_client(handler).report("7590-VHVEG")
    assert expected in str(info.value) and info.value.status == status


def test_unreachable_api_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ApiError, match="python -m src.api.main"):
        make_client(handler).health()


def test_timeout_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ApiError, match="did not answer"):
        make_client(handler).agent("q")


def test_invalid_json_message() -> None:
    with pytest.raises(ApiError, match="not valid JSON"):
        make_client(lambda request: httpx.Response(200, text="<html>")).health()


def test_plain_escapes_dollars() -> None:
    assert plain("$50 and $30") == "\\$50 and \\$30"


def test_every_report_status_has_ui_text() -> None:
    assert set(NO_RECOMMENDATION_TEXT) == set(REPORT_STATUSES) - {"complete", "partial"}


def test_app_runs_and_generates_a_report(monkeypatch: pytest.MonkeyPatch) -> None:
    testing = pytest.importorskip("streamlit.testing.v1")
    monkeypatch.setattr(ApiClient, "health", lambda self: HEALTH_OK)
    monkeypatch.setattr(ApiClient, "report", lambda self, cid: FAKE_REPORT)
    at = testing.AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception
    at.button(key="report_btn").click().run()
    assert not at.exception
    assert any(metric.label == "Churn risk score" for metric in at.metric)


def test_app_survives_unreachable_api(monkeypatch: pytest.MonkeyPatch) -> None:
    testing = pytest.importorskip("streamlit.testing.v1")

    def down(self: ApiClient) -> dict[str, Any]:
        raise ApiError("Cannot reach the API")

    monkeypatch.setattr(ApiClient, "health", down)
    at = testing.AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception


def test_plain_neutralises_markdown_links_and_images() -> None:
    assert plain("![x](http://e.example/?q=1) $5") == "!\\[x](http://e.example/?q=1) \\$5"


def test_theme_escapes_untrusted_text() -> None:
    from app import theme

    html = theme.chip("<img src=x onerror=alert(1)>", "danger", title='"><script>')
    assert "<img" not in html and "<script" not in html and "&lt;img" in html


def test_driver_bars_escape_and_scale() -> None:
    from app import theme

    drivers = [
        {"feature": "Contract_<b>Month</b>", "customer_value": "<i>", "contribution": 0.5, "effect": "raises churn risk"},
        {"feature": "tenure", "customer_value": 1, "contribution": -0.25, "effect": "lowers churn risk"},
    ]
    html = theme.driver_bars(drivers)
    assert "<b>Month" not in html and "&lt;b&gt;" in html and "<i>" not in html
    assert "left:50%;width:50.0%" in html and "right:50%;width:25.0%" in html
    assert theme.driver_bars([]) == ""


def test_gauge_segments_follow_config_bands() -> None:
    from app import theme
    from src import config

    html = theme.gauge(0.5)
    assert all(name in html for name, _ in config.TIER_BANDS) and "left:50.0%" in html
    assert theme.gauge(7.0).count("left:100.0%") == 1


def test_tier_for_matches_the_report_rule() -> None:
    from app import theme
    from src.llm.report_evidence import risk_tier

    for prob in (0.0, 0.2, 0.3499, 0.35, 0.5999, 0.6, 0.7999, 0.8, 1.0):
        assert theme.tier_for(prob) == risk_tier(prob), prob


def test_every_status_has_a_display_label() -> None:
    from app import theme
    from src.agent.agent import STATUS_NO_FINAL
    from src.llm import answer
    from src.llm.report import REPORT_STATUSES

    statuses = [*REPORT_STATUSES, STATUS_NO_FINAL, answer.STATUS_ANSWERED, answer.STATUS_NO_EVIDENCE,
                answer.STATUS_MODEL_REFUSED, answer.STATUS_REJECTED, answer.STATUS_LLM_ERROR]
    assert all(status in theme.STATUS_DISPLAY for status in statuses)


def test_app_renders_ask_and_agent_results(monkeypatch: pytest.MonkeyPatch) -> None:
    testing = pytest.importorskip("streamlit.testing.v1")
    ask = {
        "question": "q", "answer": "The cap is 30 percent.", "status": "answered", "citations": ["t-1"],
        "citation_details": [{"chunk_id": "t-1", "source": "retention_policy.pdf", "location": {"page": 1}, "text": "The cap is 30 percent."}],
        "can_answer": True, "issues": [], "evidence_reason": "ok", "retrieved_ids": ["t-1"], "notice": "SYNTHETIC",
    }
    agent = {**ask, "steps_used": 1, "trace": [{"step": 1, "tool": "calculate", "arguments": {"expression": "1+1"},
                                                 "ok": True, "seconds": 0.01, "result_preview": "1+1 = 2"}]}
    monkeypatch.setattr(ApiClient, "health", lambda self: HEALTH_OK)
    monkeypatch.setattr(ApiClient, "ask", lambda self, question, k=5, mode=None: ask)
    monkeypatch.setattr(ApiClient, "agent", lambda self, question: agent)
    at = testing.AppTest.from_file(APP_PATH, default_timeout=30).run()
    at.button(key="ask_btn").click().run()
    assert not at.exception and any("cap is 30 percent" in m.value for m in at.markdown)
    at.button(key="agent_btn").click().run()
    assert not at.exception


def test_kpi_strip_escapes_and_applies_tone() -> None:
    from app import theme

    html = theme.kpi_strip([("<b>Score</b>", "0.85", "cap <i>", "danger"), ("Tier", "High", "", "")])
    assert "<b>Score" not in html and "&lt;b&gt;" in html and "&lt;i&gt;" in html
    assert "var(--t-danger-fg)" in html and html.count('class="ei-kpi"') == 2


def test_css_follows_the_requested_mode() -> None:
    from app import theme

    dark, light, auto = theme.build_css("dark"), theme.build_css("light"), theme.build_css(None)
    assert "color-scheme:dark" in dark and "prefers-color-scheme" not in dark
    assert "color-scheme:light" in light and "prefers-color-scheme" not in light
    assert "prefers-color-scheme: dark" in auto
