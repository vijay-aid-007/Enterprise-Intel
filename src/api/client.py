"""HTTP client for the FastAPI service. The Streamlit UI reaches the backend only through this module."""
from __future__ import annotations

import os
from typing import Any

import httpx

from src import config

DEFAULT_URL = f"http://{config.API_HOST}:{config.API_PORT}"
URL_ENV = "API_URL"


class ApiError(RuntimeError):
    """A failure whose message is safe to show to the user as is."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _detail(response: httpx.Response) -> str:
    """Readable message from a FastAPI error body: 404/503 give a string, 422 gives a list."""
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, list):
        problems = "; ".join(str(i.get("msg", i)) if isinstance(i, dict) else str(i) for i in detail)
        return f"Invalid input: {problems}"
    return f"API error {response.status_code}"


class ApiClient:
    """One method per endpoint. Every failure becomes an ApiError with a readable message."""

    def __init__(self, base_url: str | None = None, *, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = (base_url or os.environ.get(URL_ENV) or DEFAULT_URL).rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, transport=transport)

    def _call(
        self, method: str, path: str, payload: dict[str, Any] | None = None, *, timeout: float
    ) -> dict[str, Any]:
        try:
            response = self._http.request(method, path, json=payload, timeout=timeout)
        except httpx.ConnectError as exc:
            raise ApiError(f"Cannot reach the API at {self.base_url}. Start it with: python -m src.api.main") from exc
        except httpx.TimeoutException as exc:
            raise ApiError(
                f"The API did not answer within {timeout:g}s. The language model may be rate limited; "
                "try again in a minute."
            ) from exc
        except httpx.HTTPError as exc:
            raise ApiError(f"Could not talk to the API: {exc}") from exc
        if response.status_code >= 400:
            raise ApiError(_detail(response), response.status_code)
        try:
            body = response.json()
        except ValueError as exc:
            raise ApiError("The API returned a reply that is not valid JSON.") from exc
        if not isinstance(body, dict):
            raise ApiError("The API returned an unexpected reply shape.")
        return body

    def health(self) -> dict[str, Any]:
        return self._call("GET", "/health", timeout=config.UI_FAST_TIMEOUT_S)

    def predict(self, customer_id: str) -> dict[str, Any]:
        return self._call("POST", "/predict", {"customer_id": customer_id.strip()}, timeout=config.UI_FAST_TIMEOUT_S)

    def ask(self, question: str, k: int = config.GEN_K, mode: str | None = None) -> dict[str, Any]:
        payload = {"question": question, "k": k, "mode": mode}
        return self._call("POST", "/ask", payload, timeout=config.UI_SLOW_TIMEOUT_S)

    def agent(self, question: str) -> dict[str, Any]:
        return self._call("POST", "/agent", {"question": question}, timeout=config.UI_SLOW_TIMEOUT_S)

    def report(self, customer_id: str) -> dict[str, Any]:
        return self._call("POST", "/report", {"customer_id": customer_id.strip()}, timeout=config.UI_SLOW_TIMEOUT_S)