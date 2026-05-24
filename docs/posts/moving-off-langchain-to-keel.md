# We replaced LangChain with composable libraries. Here's what changed.

> A side-by-side look at moving a production multi-model LLM stack off LangChain onto a portfolio of small, composable libraries. The result was **less code**, **better observability**, and **measurably better reliability** — but it took rethinking *what role a framework should play* in an agent's life.

*This is the post that goes with the [migration playbook](https://github.com/keelplatform/keel-examples/tree/main/langchain-migration). Reading the playbook first isn't required; this is the why.*

---

## The thing we kept hitting

We were running a multi-model LLM workflow — calls to OpenAI, Anthropic, and Gemini across an agentic flow — and three things kept costing us:

1. **A 429 from Gemini's free-tier 15 RPM ceiling was being treated as a failure.** LangChain's `with_fallbacks` did the same thing every reliability library does by default: it counted the 429 against the model's health, eventually tripping a circuit on a model that wasn't actually unhealthy — just throttled. The throttled model would get benched, the bench would shrink, the remaining models would shoulder more load, and *those* would start to throttle. Cascading failure from healthy models.

2. **Observability was bolted on.** LangChain's callback model is its own thing. To see what was happening end-to-end, we either paid for LangSmith or hand-wired callback handlers into our existing OTel stack. Both options bought us *less* observability than we already had for non-LLM services.

3. **The framework cost stayed even after we'd outgrown it.** We'd long since moved past the things LangChain made easy on day one. Memory was a list. Output parsing was Pydantic. Prompt templates were f-strings. But we still had `AgentExecutor` in the middle of our call stack, and every change had to be made *through* the framework's shape — every refactor was a fight with the runtime.

We knew what we wanted: small libraries we could compose, no framework runtime owning our agent loop, OpenTelemetry as the observability contract, and reliability machinery that knew what a 429 actually means.

Couldn't find it. Built it. Open-sourced it: [Keel](https://github.com/keelplatform).

---

## The mental shift — frameworks vs libraries vs lego portfolios

LangChain's pitch is fine and accurate: it's a framework. You adopt its shape, and in exchange you get a lot of agent / memory / retriever / callback machinery wired together. **For day-one prototyping or simple flows, this is genuinely valuable.** Most LangChain success stories live there.

The problem is the shape-cost compounds. Every change in a production system has to thread through the framework's mental model. The "everything is a `Runnable`" abstraction is elegant when it fits and exhausting when it doesn't. And it doesn't fit forever.

The alternative isn't to write everything from scratch — that's the *other* trap most teams hit, and the place "hand-roll your own LLM stack" becomes its own quagmire of fragile retry loops.

The alternative we found useful: **a portfolio of small composable libraries**, each one solving one concern, replaceable without rewriting the rest. *Pip install one, ignore the others. Replace one, the rest don't notice.*

This is what Keel is. It's not a framework — it deliberately doesn't ship an agent runtime, a memory hierarchy, or a callback model. It ships:

- A typed `ModelAdapter` protocol (the lingua franca every provider speaks).
- Adapters for OpenAI, Anthropic, Gemini, Bedrock (and others) that conform to it.
- A reliability layer (`ResilientClient`) with category-correct breaker and failover.
- An OTel emission layer (`keel-llm-otel`) that's pure overlay — your `keel-llm-reliability` calls emit metrics + span events to whatever OTel backend you already use.
- A circuit breaker primitive (`keel-circuit-breaker`) — useful for any flaky call, not just LLMs.

Each is a separate `pip install`. Each works alone. None of them lock you in. And you keep your agent loop.

---

## What changed when we moved

### The 429 fix — measured

The thing we kept hitting: the 429 problem. In the original LangChain setup, treating a 429 as a failure dropped a throttled Gemini model from 10/10 availability to **3/10**. The fallback chain would route around the "failed" model, the breaker would open, and recovery probes would slow restoration.

In Keel:

```python
from keel_llm_protocol.errors import AdapterError, RateLimitError

try:
    return await adapter.generate(messages)
except AdapterError as e:
    if e.category == "backpressure":   # the 429
        ...  # defer to the limiter; do NOT record a breaker failure
    elif e.category == "transient":
        ...  # retry / fail over (this one DOES count as a breaker failure)
    else:
        raise   # auth / bad-request / context / content — fail fast
```

A rate-limited model is *healthy, not failing.* Acting on that one distinction took the same throttled model from **3/10 → 10/10 availability.** It's not a marketing claim; it's the result of applying the right error category to the right reliability primitive.

The keel-llm-reliability package builds this dispatch in. You don't have to think about it; the failover machinery does the right thing automatically.

### The observability shift — open standards instead of proprietary callbacks

Old:

```python
from langchain.callbacks import StdOutCallbackHandler
chain.invoke("Hello", config={"callbacks": [StdOutCallbackHandler()]})
# proprietary format. To see this anywhere besides stdout, wire to LangSmith
# or hand-roll a custom callback handler.
```

New:

```python
from keel_llm_otel.starter import setup
setup()   # ONE LINE — OTel SDK configured, OTLP exporter wired, auto-instrumentor active.

# That's it. Every keel-llm-reliability call now emits metrics + span events
# to Jaeger / Honeycomb / Datadog / Grafana Tempo / SigNoz / any OTel collector.
# Same shape as the rest of your service infrastructure.
```

With `keel-llm-otel[full]`, `opentelemetry-instrumentation-httpx` also auto-activates, so each provider HTTP call appears as a real distributed-trace span with `traceparent` propagated to the provider. Full distributed tracing of the LLM call path.

The key win: **our LLM observability now looks the same as everything else in our stack.** We didn't have to buy a SaaS. We didn't have to learn a callback format. We didn't have to bolt on. OTel is the contract.

### The code shrank — by a lot

Our agent code, after migration:

- A `~80-line` `async def research(question, client)` function that explicitly does plan → tool → synthesize.
- A `ResilientClient([groq, openai, bedrock])` initialization with three lines.
- An `OTelInstrumentor().instrument()` line at startup (or `keel_llm_otel.starter.setup()` for the bundled SDK setup).

That's all that's running in production for the reliability + observability layer. We deleted `AgentExecutor`, the callback handler tree, the retry decorators, our memory hierarchy, and a ~400-line `chain_factory.py` that wove it all together. **Net: -650 lines of framework glue; +90 lines of explicit Python.**

The trade was: we gave up the "you barely have to write any code" pitch, and got back direct readability + replaceability.

### The composability dividend

Six months later, three things have happened that would have been refactors in LangChain and were one-line changes in Keel:

1. **We added AWS Bedrock for an enterprise customer.** Replaced `OpenAIAdapter` for the enterprise tenant with `BedrockAdapter`. Same protocol; agent code didn't change.

2. **We swapped the in-process circuit breaker for a Redis-backed cross-worker one** (when we went multi-worker and per-process breaker state became a problem). Same `Breaker` async protocol; we provided a Redis implementation; the `ResilientClient` didn't know.

3. **We added Honeycomb alongside our existing Datadog OTel pipeline.** Configured an additional OTel exporter; metrics + spans went to both. No code change in the LLM layer at all — they're just OTel signals.

Each of these would have been a "we'll have to do a project for that" conversation in LangChain.

---

## What we gave up — be honest

Keel doesn't have a lot of things LangChain has. If you're considering the move, weigh these honestly:

- **No agent framework.** You write `async def agent(...)` yourself. No `AgentExecutor`, no `LangGraph`. (For multi-agent patterns, Keel will eventually ship `keel-agent-orchestration` as opt-in framework-shaped legos — but today, the explicit pattern is the answer.)

- **No memory abstractions.** Use a plain list, a database, or a vector store. There's no `ConversationBufferMemory` hierarchy to fight, but also nothing to give you for free.

- **No retrievers / RAG primitives.** Pick LlamaIndex, raw vector DBs, or your existing stack. Keel composes alongside, doesn't replace.

- **No prompt template runtime.** f-strings + Pydantic do most of what `PromptTemplate` does, but you're managing them yourself.

- **No proprietary observability format.** This is a *win* for us, but if your team is deeply invested in the LangSmith UI, you'll feel the migration.

If those givebacks feel painful, Keel isn't right for you yet. If they feel *clarifying* — "wait, we already do all that ourselves and the framework was just getting in the way" — you're probably ready.

---

## How we'd recommend trying it

If you want to look without committing:

1. **Spin up the [agentic-research demo](https://github.com/keelplatform/keel-examples/tree/main/agentic-research).** `docker compose up` brings up Jaeger + an agent that exercises the full failover stack against mock providers. No API keys. You'll have traces flowing in 5 minutes.

2. **Read the [migration playbook](https://github.com/keelplatform/keel-examples/tree/main/langchain-migration).** It walks the common LangChain patterns and shows what each becomes — including the honest "we don't ship this" entries.

3. **Try one provider call.** Replace one `ChatOpenAI.invoke` with `OpenAIAdapter` in a `ResilientClient`. Run it alongside your existing LangChain stack. Migrate incrementally; there's no flag-day.

The packages, by the way, are all on PyPI and `mypy --strict` clean: [`keel-llm-reliability`](https://pypi.org/project/keel-llm-reliability/), [`keel-llm-otel`](https://pypi.org/project/keel-llm-otel/), and adapters for [OpenAI-compatible](https://pypi.org/project/keel-llm-adapter-openai/), [Anthropic](https://pypi.org/project/keel-llm-adapter-anthropic/), [Gemini](https://pypi.org/project/keel-llm-adapter-google/), and [Bedrock](https://pypi.org/project/keel-llm-adapter-bedrock/). Open-source under MIT.

---

## When LangChain is still the right answer

To be clear: this isn't an anti-LangChain post. **If you're prototyping, if you don't need vendor neutrality, if RAG/memory/agent-runtime as a packaged framework is exactly what you want, LangChain is great.** It's still the fastest path from blank file to working agent. Many production systems are very happy on it.

This is for the *next conversation* — the one where you've outgrown the framework's shape and you can feel the cost compounding, and you want a clearer path forward than "rewrite from scratch."

That path is composable libraries with no lock-in. Keep your agent loop. Pick the legos you need. Replace one piece at a time.

---

*Discussion welcome on [Hacker News](#) / [Reddit](#) / [GitHub Discussions](https://github.com/keelplatform/keel-examples/discussions). The migration playbook is [here](https://github.com/keelplatform/keel-examples/tree/main/langchain-migration); the reference agentic example is [here](https://github.com/keelplatform/keel-examples/tree/main/agentic-research).*
