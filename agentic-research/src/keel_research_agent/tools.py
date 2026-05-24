"""A mock 'search' tool with canned results — enough to make tool-call traces
realistic in Jaeger without depending on an external service. Real adoption
would swap this for a real DuckDuckGo / Tavily / Perplexity call.
"""

from __future__ import annotations

import asyncio
import random

from keel_llm_protocol import ToolSpec

# Canned responses keyed loosely so any query produces plausible-looking results.
_CANNED = {
    "opentelemetry": [
        "OpenTelemetry is an open observability framework for traces, metrics, logs.",
        "Vendor-neutral; CNCF graduated; supports OTLP protocol over gRPC/HTTP.",
    ],
    "circuit breaker": [
        "Circuit breaker pattern: skip a known-failing dependency to avoid hammering it.",
        "Open/closed/half-open states; cooldown before probing recovery.",
    ],
    "rate limit": [
        "Rate limits cap calls per window (e.g., 15 RPM on Gemini free tier).",
        "Respond to 429 by *deferring* — a throttled model is healthy, not failing.",
    ],
}


def search_tool_spec() -> ToolSpec:
    """The tool an LLM will be told it can call."""
    return ToolSpec(
        name="search",
        description="Search the web for information about a topic. Returns a list of relevant snippets.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The search query."}},
            "required": ["query"],
        },
    )


async def search(query: str) -> str:
    """Perform a mock 'search'. Returns a synthetic result snippet."""
    # Simulate network latency.
    await asyncio.sleep(0.04 + random.random() * 0.06)
    q = query.lower()
    for key, snippets in _CANNED.items():
        if key in q:
            return " ".join(snippets)
    return f"Found general info about: {query}. (Mock search — swap for a real engine to see real results.)"
