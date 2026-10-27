"""Single LLM client: Groq only, native function calling, no agent framework.

Groq's chat API uses the OpenAI-style format (tools / tool_calls), so the
parsing below is the same shape you will see in any tutorial.
Setup: pip install groq
"""
from __future__ import annotations

import json
import re 
import time
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from src import config

logger = logging.getLogger(__name__)

# Provider-neutral tool description: {"name", "description", "parameters": JSON schema}
ToolSpec = dict[str, Any]


class LLMError(RuntimeError):
    """Configuration problem or provider failure."""


@dataclass(frozen=True)
class ToolCall:
    """One function call requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    """Model output: free text and/or tool calls."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    """Interface shared by the real client and the fakes used in tests."""

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
        force_tool: str | None = None,
    ) -> LLMResponse:
        """Run one model turn. Raises LLMError on any provider failure."""
        ...


def load_env_file(path: Path = config.ENV_FILE) -> None:
    """Minimal KEY=VALUE .env parser. Real environment variables win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))

_RETRY_AFTER_RE = re.compile(r"try again in ([0-9.]+)\s*(ms|s)", re.IGNORECASE)


def _rate_limit_wait(exc: Exception) -> float | None:
    """Seconds to wait if exc is a 429 rate-limit error, else None. Parses Groq's 'try again in 1.29s'."""
    text = str(exc)
    if getattr(exc, "status_code", None) != 429 and "rate_limit_exceeded" not in text:
        return None
    match = _RETRY_AFTER_RE.search(text)
    seconds = 0.0
    if match:
        seconds = float(match.group(1)) / (1000 if match.group(2).lower() == "ms" else 1)
    return min(max(seconds + 1.0, 2.0), config.LLM_RATE_MAX_WAIT_S)        

def _recover_tool_call(
    exc: Exception, tools: list[ToolSpec] | None, force_tool: str | None
) -> ToolCall | None:
    """Rebuild a tool call from Groq's 400 'tool_use_failed' error, or return None.

    Seen live: the model wrote the final_answer arguments as plain JSON, Groq rejected the turn and
    put the text in 'failed_generation'. Only tools offered in this request are accepted, and the
    caller validates the arguments like any other tool call.
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        body = body["error"]
    raw = body.get("failed_generation") if isinstance(body, dict) else None
    if not isinstance(raw, str):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("name"), str) and isinstance(data.get("arguments"), dict):
        name, arguments = data["name"], data["arguments"]
    elif force_tool:
        name, arguments = force_tool, data
    else:
        return None
    if name not in {t["name"] for t in tools or []}:
        return None
    return ToolCall("recovered-1", name, arguments)

class GroqClient:
    """Thin adapter over the Groq SDK."""

    def __init__(self, *, api_key: str, model: str) -> None:
        try:
            from groq import Groq
        except ImportError as exc:
            raise LLMError("Groq SDK missing. Run: pip install groq") from exc
        self._sdk = Groq(api_key=api_key, timeout=config.LLM_TIMEOUT_S, max_retries=2)
        self._model = model

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
        force_tool: str | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": config.LLM_TEMPERATURE,
            "max_completion_tokens": config.LLM_MAX_TOKENS,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]},
                }
                for t in tools
            ]
            if force_tool:
                kwargs["tool_choice"] = {"type": "function", "function": {"name": force_tool}}
        
        resp = None
        for attempt in range(config.LLM_RATE_RETRIES + 1):
            try:
                resp = self._sdk.chat.completions.create(**kwargs)
                break
            except Exception as exc:  # SDK raises many exception types; normalise to one
                wait = _rate_limit_wait(exc)
                if wait is None:
                    recovered = _recover_tool_call(exc, tools, force_tool)
                    if recovered is not None:
                        logger.warning("Recovered tool call '%s' form a Groq tool_use_failed_error", recovered.name)
                        return LLMResponse(text="", tool_calls=[recovered])
                if wait is None or attempt == config.LLM_RATE_RETRIES:
                    raise LLMError(f"Groq call failed: {exc}") from exc
                logger.warning("Groq rate limit; waiting %.1fs (retry %d)", wait, attempt + 1)
                time.sleep(wait)
        if resp is None:  # unreachable; keeps the type checker honest
            raise LLMError("Groq call returned no response")

        message = resp.choices[0].message
        calls: list[ToolCall] = []
        for tc in message.tool_calls or []:
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                raise LLMError(f"Tool call '{tc.function.name}' returned invalid JSON arguments") from exc
            calls.append(ToolCall(tc.id, tc.function.name, arguments if isinstance(arguments, dict) else {}))
        return LLMResponse(text=message.content or "", tool_calls=calls)


def get_llm_client() -> LLMClient:
    """Build the Groq client from GROQ_API_KEY and LLM_MODEL in .env."""
    load_env_file()
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    if not api_key:
        raise LLMError("Set GROQ_API_KEY in .env")
    if not model:
        raise LLMError("Set LLM_MODEL in .env (a Groq model that supports tool use)")
    logger.info("LLM client ready: Groq model=%s", model)
    return GroqClient(api_key=api_key, model=model)

def assistant_tool_message(response: LLMResponse) -> dict[str, Any]:
    """Assistant turn that requested tool calls, in the OpenAI-style format Groq expects."""
    return {
        "role": "assistant",
        "content": response.text or None,
        "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
            for c in response.tool_calls
        ],
    }


def tool_result_message(call_id: str, content: str) -> dict[str, Any]:
    """Tool turn answering one tool call. Every call id must receive exactly one of these."""
    return {"role": "tool", "tool_call_id": call_id, "content": content}