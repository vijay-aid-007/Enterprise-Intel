"""Single LLM client: Groq only, native function calling, no agent framework.

Groq's chat API uses the OpenAI-style format (tools / tool_calls), so the
parsing below is the same shape you will see in any tutorial.
Setup: pip install groq
"""
from __future__ import annotations

import json
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
        messages: list[dict[str, str]],
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
        messages: list[dict[str, str]],
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
        try:
            resp = self._sdk.chat.completions.create(**kwargs)
        except Exception as exc:  # SDK raises many exception types; normalise to one
            raise LLMError(f"Groq call failed: {exc}") from exc

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