# agentic-research

> A small multi-step research agent built on Keel — **multi-model reliability + distributed OTel tracing in ~80 lines of agent code.** Run `docker compose up` and you're watching real reliability behaviour in Jaeger within 5 minutes.

This is the canonical Keel example: a real agentic flow (plan → tool-call → synthesize) that demonstrates *why* the boring-but-critical reliability + observability parts being **libraries** (not a framework) keeps the agent code small and your control loop yours.

## What you'll see

`docker compose up` brings up:
- **Jaeger** (all-in-one — OTLP collector + UI on http://localhost:16686).
- **The agent**, which fires 24 concurrent research queries per round × 3 rounds across three mock providers with realistic reliability profiles:
  - `mock-fast:fast-throttled` — fast (80 ms) but trips `RateLimitError` after 3 calls/second.
  - `mock-medium:medium-flaky` — moderate (220 ms), occasional `TransientError`.
  - `mock-slow:slow-reliable` — slow (520 ms) fallback that almost never fails.

In Jaeger you immediately see:
- The agent's **trace tree**: `research` → `plan` → `tool.search` → `synthesize`.
- **`keel.attempt` events** on each LLM step showing per-provider disposition (`success` / `deferred_backpressure` / `failed`).
- Visible **failover under load**: when the throttled primary 429s, the next provider picks up — *without* its circuit tripping (because backpressure isn't failure).

## Quickstart — 5 minutes from clone to traces

```bash
git clone https://github.com/keelplatform/keel-examples
cd keel-examples/agentic-research
docker compose up
# In another terminal — open Jaeger UI:
open http://localhost:16686    # macOS;  xdg-open on Linux;  start on Windows
# In the UI: Service = "keel-research-agent" → Find Traces
```

That's it. No API keys, no SDK setup, no LangChain. The reliability dispositions you see are the same machinery you'd use against real providers.

## What this demonstrates (and what it doesn't)

**Demonstrates:**
- Multi-step agentic flow (plan → tool → synthesize) where the consumer's code owns the loop — Keel is libraries, not a framework.
- `ResilientClient.failover()` across three providers with different reliability profiles, transparent degradation visible in traces.
- Category-correct breaker behaviour: `RateLimitError` defers (doesn't trip the model's circuit); `TransientError` records and fails over.
- Distributed OTel tracing with **zero code change** in the agent — `OTelInstrumentor().instrument()` is one line at startup; every `ResilientClient` call emits without explicit hooks.

**Doesn't demonstrate (because they aren't this demo's job):**
- Real provider HTTP traffic (mocks; swap them for real adapters via the snippet below).
- Memory / retrieval / RAG (orthogonal — Keel is the reliability layer; bring your own RAG stack).
- Agent frameworks like LangChain / LlamaIndex — the explicit `async def research(question, client)` loop *is* the agentic pattern in this style.

## Using real providers instead of mocks

Swap the mock adapters for real ones — `pip install keel-llm-adapter-openai` then:

```python
from keel_llm_adapter_openai import OpenAIAdapter

client = ResilientClient(
    adapters=[
        OpenAIAdapter(model="llama-3.3-70b-versatile", api_key=os.environ["GROQ_API_KEY"],
                      base_url="https://api.groq.com/openai/v1", provider="groq"),
        OpenAIAdapter(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"], provider="openai"),
    ],
    transient_retries=1,
)
```

With `keel-llm-otel[full]` installed (it already is), `opentelemetry-instrumentation-httpx` auto-activates, so each provider HTTP call appears as a real child span with `traceparent` propagated to the provider — **full distributed tracing**.

## What's inside

```
agentic-research/
├── docker-compose.yml         # Jaeger all-in-one + the agent
├── Dockerfile
├── pyproject.toml
├── README.md
└── src/keel_research_agent/
    ├── agent.py               # ~80 LOC — the research agent itself
    ├── mock_providers.py      # Three adapter mocks with realistic reliability
    ├── tools.py               # A mock 'search' tool with canned results
    ├── telemetry.py           # OTel SDK wiring → OTLP → Jaeger
    └── run.py                 # Concurrent workload that exercises the failover
```

## The Keel toolkit

Composable, vendor-neutral LLM reliability libraries on PyPI:
[`keel-llm-reliability`](https://pypi.org/project/keel-llm-reliability/) · [`keel-llm-protocol`](https://pypi.org/project/keel-llm-protocol/) · [`keel-llm-adapter-openai`](https://pypi.org/project/keel-llm-adapter-openai/) · [`keel-llm-adapter-anthropic`](https://pypi.org/project/keel-llm-adapter-anthropic/) · [`keel-llm-adapter-google`](https://pypi.org/project/keel-llm-adapter-google/) · [`keel-circuit-breaker`](https://pypi.org/project/keel-circuit-breaker/) · [`keel-llm-otel`](https://pypi.org/project/keel-llm-otel/)

MIT licensed.
