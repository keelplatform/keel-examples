"""A small multi-step research agent built on Keel.

The whole reason this file exists: show that a real agentic flow — multi-step
LLM reasoning with tool calls, across multiple providers, with reliable
failover and full distributed tracing — fits in **~80 lines of agent code**
when the reliability + observability layers are libraries instead of a
framework. The consumer (this file) owns the workflow; Keel handles the
boring-but-critical parts.

Flow per query:
1. **Plan** — ask the LLM what to search for.
2. **Search** — call the (mock) tool.
3. **Synthesize** — ask the LLM to answer from the search results.

Every call goes through ``ResilientClient`` across three mock providers.
With ``opentelemetry-instrument python -m keel_research_agent.run`` (or the
docker-compose default), every step appears in Jaeger as a span; every
attempt's outcome shows as a ``keel.attempt`` event with the disposition
(``success`` / ``deferred_backpressure`` / ``failed`` / etc.).
"""

from __future__ import annotations

from opentelemetry import trace

from keel_llm_protocol import system, user
from keel_llm_reliability import Request, ResilientClient

from keel_research_agent.tools import search, search_tool_spec

_tracer = trace.get_tracer("keel.research-agent")


async def research(question: str, client: ResilientClient) -> str:
    """Run a 3-step research agent for ``question``. Returns the answer text.

    Each step opens its own span so the trace tree shows the agent's logic
    structure (plan → search → synthesize) and the ``keel.attempt`` events
    from `keel-llm-otel` light up the reliability dispositions per step.
    """
    with _tracer.start_as_current_span("research") as span:
        span.set_attribute("research.question", question)

        # Step 1: planning — what should we search for?
        with _tracer.start_as_current_span("plan"):
            plan = await client.failover(
                Request(
                    messages=[
                        system(
                            "You are a research assistant. Decide the single best search "
                            "query for the user's question. Return ONLY the search query."
                        ),
                        user(question),
                    ]
                )
            )
            if not plan.succeeded or plan.response is None:
                return "Failed: planning step exhausted all providers."
            query = plan.response.text.strip()

        # Step 2: tool call — search.
        with _tracer.start_as_current_span("tool.search") as tool_span:
            tool_span.set_attribute("tool.name", "search")
            tool_span.set_attribute("tool.input.query", query)
            results = await search(query)
            tool_span.set_attribute("tool.output.length", len(results))

        # Step 3: synthesis — answer based on search results.
        with _tracer.start_as_current_span("synthesize"):
            synth = await client.failover(
                Request(
                    messages=[
                        system(
                            "You are a research assistant. Use the search results "
                            "to answer the user's question in 1–2 sentences."
                        ),
                        user(
                            f"Question: {question}\n\nSearch results:\n{results}\n\nAnswer:"
                        ),
                    ]
                )
            )
            if not synth.succeeded or synth.response is None:
                return "Failed: synthesis step exhausted all providers."

        answer = synth.response.text
        span.set_attribute("research.answer.length", len(answer))
        return answer


def search_tool() -> object:
    """Re-exported for the agent's tool registration story (not used in this
    minimal demo, but available if you extend the agent to native tool-calling)."""
    return search_tool_spec()
