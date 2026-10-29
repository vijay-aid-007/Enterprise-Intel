"""Disk cache and call pacing for any LLMClient, used by the evaluation scripts only.

Why: Groq allows roughly 8000 tokens per minute, so a full eval run is slow and every re-run would cost
the same again. With the cache a re-run is free, and --offline reproduces the tables without an API key.
Application code never imports this module.

The cache key covers the system prompt, messages, tool schemas and forced tool, so editing a prompt or a
tool description misses the cache and calls the model again. The model name is stored beside each reply
and compared in live mode, so switching LLM_MODEL never silently reuses old replies. Errors are not cached.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

from src.llm.client import LLMClient, LLMError, LLMResponse, ToolCall, ToolSpec

logger = logging.getLogger(__name__)


def _encode(response: LLMResponse) -> dict[str, Any]:
    calls = [{"id": c.id, "name": c.name, "arguments": c.arguments} for c in response.tool_calls]
    return {"text": response.text, "tool_calls": calls}


def _decode(data: dict[str, Any]) -> LLMResponse:
    calls = [ToolCall(c["id"], c["name"], c["arguments"]) for c in data.get("tool_calls", [])]
    return LLMResponse(text=data.get("text", ""), tool_calls=calls)


class CachingClient:
    """LLMClient wrapper: replay from disk when possible, otherwise call `inner` (paced) and record the reply."""

    def __init__(
        self,
        inner: LLMClient | None,
        path: Path,
        *,
        model_id: str,
        min_interval_s: float = 0.0,
        offline: bool = False,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = None if offline else inner  # no inner client means replay-only
        self._path, self._model_id, self._min_interval = path, model_id, min_interval_s
        self._sleep, self._clock = sleep, clock
        self._last_call: float | None = None
        self._entries: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        self._load()

    @staticmethod
    def make_key(system: str, messages: list[dict[str, Any]], tools: list[ToolSpec] | None, force_tool: str | None) -> str:
        payload = {"system": system, "messages": messages, "tools": tools or [], "force_tool": force_tool}
        text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _load(self) -> None:
        if not self._path.exists():
            return
        for number, line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                self._entries[row["key"]] = {"model": row.get("model", ""), "response": row["response"]}
            except (ValueError, KeyError):
                logger.warning("skipping unreadable cache line %d in %s", number, self._path)

    def _lookup(self, key: str) -> dict[str, Any] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if self._inner is not None and entry["model"] != self._model_id:
            return None  # live run with a different model: do not reuse another model's reply
        return entry

    def _store(self, key: str, response: LLMResponse) -> None:
        entry = {"model": self._model_id, "response": _encode(response)}
        self._entries[key] = entry
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"key": key, **entry}, ensure_ascii=False) + "\n")

    def _pace(self) -> None:
        if self._last_call is not None and self._min_interval > 0:
            wait = self._min_interval - (self._clock() - self._last_call)
            if wait > 0:
                logger.info("pacing: waiting %.1fs before the next model call", wait)
                self._sleep(wait)

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
        force_tool: str | None = None,
    ) -> LLMResponse:
        key = self.make_key(system, messages, tools, force_tool)
        entry = self._lookup(key)
        if entry is not None:
            self.hits += 1
            return _decode(entry["response"])
        if self._inner is None:
            raise LLMError("eval cache miss in offline mode: run once online (with an API key) to fill the cache")
        self._pace()
        response = self._inner.complete(system, messages, tools, force_tool)  # LLMError propagates, nothing stored
        self._last_call = self._clock()
        self.misses += 1
        self._store(key, response)
        return response