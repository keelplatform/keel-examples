"""Entry point. Wires OTel, activates the Keel auto-instrumentor, and fires N
concurrent agent runs so the reliability/observability story is *visible* —
not hypothetical — in the trace tree within seconds of ``docker compose up``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random

from keel_llm_otel import OTelInstrumentor
from keel_llm_reliability import ResilientClient

from keel_research_agent.agent import research
from keel_research_agent.mock_providers import (
    FastThrottledAdapter,
    MediumFlakyAdapter,
    SlowReliableAdapter,
)
from keel_research_agent.telemetry import setup_otel

# Questions are intentionally varied so the planning step produces different
# search queries, exercising the mock canned-results pool.
_QUESTIONS = [
    "What is OpenTelemetry?",
    "How do circuit breakers work?",
    "How do LLM rate limits work?",
    "What's the difference between distributed tracing and metrics?",
    "Why is treating 429 as a failure a bad idea?",
    "How does a half-open circuit work in practice?",
    "What is OTLP and why does it matter?",
    "How do you propagate trace context across services?",
]


async def _one(question: str, client: ResilientClient) -> None:
    """One agent run; swallow exhaustion to keep the demo continuing.
    The trace tree shows what happened either way."""
    try:
        answer = await research(question, client)
        logging.info("answered %r → %s", question[:40], answer[:80])
    except Exception as e:  # pragma: no cover
        logging.warning("agent run failed for %r: %s", question[:40], e)


async def main() -> None:
    # 1. OTel SDK pointing at the OTLP collector (Jaeger / SigNoz / etc.).
    setup_otel()

    # 2. Auto-instrument keel-llm-reliability — zero code change in the agent;
    #    every ResilientClient.failover / fan_out call now emits keel.attempt
    #    events + metrics. With [full] extra installed, instrumentation-httpx
    #    *also* activates and adds per-provider HTTP child spans (in a real
    #    setup against real providers — mock adapters don't issue HTTP).
    OTelInstrumentor().instrument()

    # 3. Build a multi-model ResilientClient with three mocks of varying
    #    reliability character. Order matters for failover (primary first):
    client = ResilientClient(
        adapters=[
            FastThrottledAdapter(free_quota_per_second=3),  # fast but trips 429
            MediumFlakyAdapter(transient_rate=0.10),         # ~10% 5xx
            SlowReliableAdapter(),                            # last resort
        ],
        transient_retries=1,  # bounded transient retry before failing over
    )

    # 4. Fire concurrent agents. With the throttled primary and 24 simultaneous
    #    runs, you'll see: many 'success' on primary, some 'deferred_backpressure'
    #    routing to fallback, occasional 'failed' (transient) failing over.
    concurrency = int(os.getenv("AGENT_CONCURRENCY", "24"))
    rounds = int(os.getenv("AGENT_ROUNDS", "3"))
    logging.info("running %d agents per round × %d rounds", concurrency, rounds)

    for round_idx in range(rounds):
        logging.info("round %d", round_idx + 1)
        questions = [random.choice(_QUESTIONS) for _ in range(concurrency)]
        await asyncio.gather(*[_one(q, client) for q in questions])
        await asyncio.sleep(1.0)  # let the rate-limit window reset between rounds

    logging.info("done — open Jaeger UI (http://localhost:16686) and select service 'keel-research-agent'")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(main())
