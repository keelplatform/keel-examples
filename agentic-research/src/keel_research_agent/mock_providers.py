"""Mock providers — adapters with realistic reliability profiles so the demo
shows the multi-model failover/breaker story without needing real API keys.

Each mock simulates one provider's character:
- ``fast_throttled``  — fast (Gemini-like), trips RateLimitError after N concurrent calls (free-tier 15 RPM feel)
- ``medium_flaky``    — moderate latency (Anthropic-like), occasional TransientError
- ``slow_reliable``   — slower (OpenAI-like fallback), almost never fails

Plug them into ``ResilientClient`` and the demo's traffic simulator will visibly
exercise: breaker preempts, deferred backpressure, transient retries, failover.
With ``[full]`` extra installed and auto-instrumentation active, the entire
flow lights up in Jaeger's trace tree.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Sequence

from keel_llm_protocol import (
    AdapterResponse,
    HealthStatus,
    Message,
    RateLimitError,
    ResponseFormat,
    ToolCall,
    ToolSpec,
    TransientError,
    Usage,
)


class _MockBase:
    """Common scaffolding for mock providers."""

    capabilities: frozenset[str] = frozenset({"tools"})

    def __init__(self, model: str, provider: str, latency_ms: int) -> None:
        self._model = model
        self._provider = provider
        self._latency_ms = latency_ms

    @property
    def model_key(self) -> str:
        return f"{self._provider}:{self._model}"

    async def health_check(self) -> HealthStatus:
        return HealthStatus(self.model_key, healthy=True)

    async def _sleep(self) -> None:
        await asyncio.sleep(self._latency_ms / 1000.0)

    def _mock_text(self, messages: Sequence[Message]) -> str:
        """Return a deterministic-ish response based on the last user message —
        enough to feel realistic in traces without invoking real LLMs."""
        last = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return f"[{self.model_key}] response to: {last[:80]}"

    def _mock_tool_call(self, tools: Sequence[ToolSpec]) -> ToolCall:
        """When asked to use tools, pick the first one with synthesized args."""
        if not tools:
            return ToolCall(id="t1", name="noop", arguments="{}")
        t = tools[0]
        # Build a plausible JSON arg payload for the tool's first string param.
        props = (t.parameters or {}).get("properties", {})
        first_key = next(iter(props), None)
        args = {first_key: "what is OpenTelemetry?"} if first_key else {}
        return ToolCall(id="t1", name=t.name, arguments=json.dumps(args))

    def _response(
        self,
        text: str,
        finish_reason: str = "stop",
        tool_calls: tuple[ToolCall, ...] = (),
    ) -> AdapterResponse:
        return AdapterResponse(
            text=text,
            model_key=self.model_key,
            model_id=self._model,
            finish_reason=finish_reason,  # type: ignore[arg-type]
            tool_calls=tool_calls,
            usage=Usage(input_tokens=42, output_tokens=21),
            latency_ms=self._latency_ms,
        )


class FastThrottledAdapter(_MockBase):
    """Fast but throttled: trips RateLimitError after a small concurrency burst.
    Models a free-tier provider (~Gemini 15 RPM) where bursty traffic backs off."""

    def __init__(self, *, free_quota_per_second: int = 3) -> None:
        super().__init__(model="fast-throttled", provider="mock-fast", latency_ms=80)
        self._quota = free_quota_per_second
        self._in_flight = 0
        self._window_start = time.monotonic()
        self._window_count = 0

    def _trip_429(self) -> bool:
        now = time.monotonic()
        if now - self._window_start > 1.0:
            self._window_start = now
            self._window_count = 0
        self._window_count += 1
        return self._window_count > self._quota

    async def generate(
        self,
        messages: Sequence[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: Sequence[str] | None = None,
        response_format: ResponseFormat | None = None,
    ) -> AdapterResponse:
        if self._trip_429():
            await asyncio.sleep(0.005)  # quick failure
            raise RateLimitError("Quota exceeded (mock)", retry_after=1.0, model_key=self.model_key)
        await self._sleep()
        return self._response(self._mock_text(messages))

    async def generate_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        *,
        tool_choice: object = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AdapterResponse:
        if self._trip_429():
            raise RateLimitError("Quota exceeded (mock)", retry_after=1.0, model_key=self.model_key)
        await self._sleep()
        return self._response("", finish_reason="tool_calls", tool_calls=(self._mock_tool_call(tools),))


class MediumFlakyAdapter(_MockBase):
    """Moderate latency, occasionally throws TransientError (~5xx feel)."""

    def __init__(self, *, transient_rate: float = 0.10) -> None:
        super().__init__(model="medium-flaky", provider="mock-medium", latency_ms=220)
        self._transient_rate = transient_rate

    async def generate(
        self,
        messages: Sequence[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: Sequence[str] | None = None,
        response_format: ResponseFormat | None = None,
    ) -> AdapterResponse:
        if random.random() < self._transient_rate:
            await asyncio.sleep(0.05)
            raise TransientError("Upstream overloaded (mock 503)", model_key=self.model_key)
        await self._sleep()
        return self._response(self._mock_text(messages))

    async def generate_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        *,
        tool_choice: object = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AdapterResponse:
        if random.random() < self._transient_rate:
            raise TransientError("Upstream overloaded (mock 503)", model_key=self.model_key)
        await self._sleep()
        return self._response("", finish_reason="tool_calls", tool_calls=(self._mock_tool_call(tools),))


class SlowReliableAdapter(_MockBase):
    """Slower but very reliable. The "fallback that always works"."""

    def __init__(self) -> None:
        super().__init__(model="slow-reliable", provider="mock-slow", latency_ms=520)

    async def generate(
        self,
        messages: Sequence[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: Sequence[str] | None = None,
        response_format: ResponseFormat | None = None,
    ) -> AdapterResponse:
        await self._sleep()
        return self._response(self._mock_text(messages))

    async def generate_with_tools(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        *,
        tool_choice: object = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AdapterResponse:
        await self._sleep()
        return self._response("", finish_reason="tool_calls", tool_calls=(self._mock_tool_call(tools),))
