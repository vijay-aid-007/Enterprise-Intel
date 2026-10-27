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
    assert any(metric.label == "Churn probability" for metric in at.metric)


def test_app_survives_unreachable_api(monkeypatch: pytest.MonkeyPatch) -> None:
    testing = pytest.importorskip("streamlit.testing.v1")

    def down(self: ApiClient) -> dict[str, Any]:
        raise ApiError("Cannot reach the API")

    monkeypatch.setattr(ApiClient, "health", down)
    at = testing.AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception