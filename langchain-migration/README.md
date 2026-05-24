# Moving off LangChain to Keel — a playbook

> **You don't have to leave all at once.** Keel is a portfolio of composable libraries, not a framework — so the migration is incremental, replacement-by-replacement, with no all-or-nothing flag day. This playbook walks the common LangChain patterns and shows what each becomes in Keel.

If you've decided LangChain's framework shape isn't right for you anymore — the lock-in, the heavy import surface, the magic, the difficulty of changing one piece without rewriting around it — this is the off-ramp.

## Mental-model shift

Before any code, the mindset change that makes the rest easy:

| LangChain | Keel |
|---|---|
| You adopt a **framework** that owns your agent's control loop | You write your own `async def agent(...)` — Keel ships **libraries** the loop calls into |
| Memory, retrievers, agents, tools all sit inside the framework's hierarchy | Each concern is a **separately-installable lego** with its own clear contract |
| Provider differences hidden behind `BaseChatModel` | Provider differences hidden behind `keel-llm-protocol` (`ModelAdapter`) — but the protocol is small, typed, and replaceable |
| Callbacks for observability (proprietary) | Standard **OpenTelemetry** signals (open vendor-neutral observability) |
| `retry_if_exception_type` or framework-built-in retry | Typed error taxonomy + `ResilientClient` with category-correct reliability (429s defer, transients fail over) |
| Migration cost: rewrite around the framework | Migration cost: **replace one piece at a time** |

The key freedom: **everything in Keel is replaceable.** If a piece doesn't fit, you swap it for your own or for a third-party. There's no framework hierarchy to escape.

---

## What you gain — and what you give up

### Gain

- **Vendor neutrality.** One interface across OpenAI, Anthropic, Gemini, Bedrock, Groq, OpenRouter, Mistral, vLLM, Ollama. Swap providers without touching your agent code.
- **Right-by-default reliability.** A rate-limited model *defers* instead of failing — measured to move a throttled model from 3/10 → 10/10 availability. Category-dispatched: `backpressure` defers, `transient` records-then-retries, `terminal` fails fast. None of this is magic — every disposition is visible.
- **Standard observability.** OpenTelemetry signals (not framework callbacks). Same backend as the rest of your service infrastructure.
- **Small, typed import surface.** `pip install` only what you need; `mypy --strict` clean throughout.
- **Replaceable bricks.** If you outgrow any piece, swap it. No flag-day rewrite.

### Give up

Be honest: Keel deliberately doesn't ship some things LangChain does.

- **No agent framework.** You write `async def agent(...)` yourself. (Most adopters find this *clarifying*, not painful — your business logic stops being trapped in `AgentExecutor`.)
- **No memory abstractions.** Use a plain list, a database, or a vector store you already trust. There's no `ConversationBufferMemory` hierarchy.
- **No retrievers / RAG / embeddings out of the box.** Pick LlamaIndex, raw vector DBs, or your existing stack — Keel composes alongside.
- **No prompt templates / output parsers as a runtime concept.** They're just Python data — use f-strings + Pydantic.
- **No proprietary observability format.** OTel is the contract.

If those givebacks feel scary, Keel might not be the right call yet. If they feel *freeing*, read on.

---

## Pattern-by-pattern mapping

### 1. Single-model chat call with retry

**LangChain:**

```python
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7).with_retry(stop_after_attempt=3)
response = llm.invoke([HumanMessage(content="Hello")])
print(response.content)
```

**Keel:**

```python
import asyncio
from keel_llm_reliability import ResilientClient, Request
from keel_llm_adapter_openai import OpenAIAdapter
from keel_llm_protocol import user

client = ResilientClient([
    OpenAIAdapter(model="gpt-4o-mini", api_key="...", provider="openai"),
], transient_retries=2)  # bounded, transient-only, every retry visible

async def main():
    result = await client.failover(Request(messages=[user("Hello")], temperature=0.7))
    print(result.response.text)

asyncio.run(main())
```

What you get back as a bonus: **every retry is a visible `Attempt`** in `result.attempts`. No silent retry storms.

### 2. Multi-model with fallback

**LangChain:**

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

primary = ChatOpenAI(model="gpt-4o-mini")
fallback = ChatAnthropic(model="claude-3-5-sonnet-20241022")
chain = primary.with_fallbacks([fallback])
response = chain.invoke("Hello")
```

**Keel:**

```python
from keel_llm_reliability import ResilientClient
from keel_llm_adapter_openai import OpenAIAdapter
from keel_llm_adapter_anthropic import AnthropicAdapter

client = ResilientClient([
    OpenAIAdapter(model="gpt-4o-mini", api_key="..."),
    AnthropicAdapter(model="claude-3-5-sonnet-20241022", api_key="..."),
])
result = await client.failover(Request(messages=[user("Hello")]))
```

**The difference**: Keel's failover is **category-dispatched**. If OpenAI 429s, the failover happens *and OpenAI's circuit doesn't open* (a 429 means healthy-but-throttled, not failed). LangChain's `with_fallbacks` treats every error the same way — including over-tripping circuits.

Bonus: with `keel-llm-otel`, every fallback decision is a span event you can query in Jaeger.

### 3. Parallel fan-out (ensemble / council)

**LangChain:** typically requires `RunnableParallel` + custom plumbing for graceful degradation.

**Keel:**

```python
result = await client.fan_out(Request(messages=[user("Hello")]))
for response in result.successes:           # every model that answered
    print(response.model_key, response.text)
print(f"degraded: {result.degraded}")        # True if not all models contributed
```

Throttled models *defer* (no breaker hit); transient failures count against breaker; terminal errors don't pollute model-health stats. The "everything that answered, with a visible degradation status" pattern, built in.

### 4. Tool calling

**LangChain:**

```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: sunny"

llm = ChatOpenAI(model="gpt-4o").bind_tools([get_weather])
response = llm.invoke("Weather in SF?")
# tool calls in response.tool_calls; YOU dispatch them
```

**Keel:**

```python
from keel_llm_protocol import ToolSpec, user
from keel_llm_adapter_openai import OpenAIAdapter

adapter = OpenAIAdapter(model="gpt-4o", api_key="...")
weather = ToolSpec(
    name="get_weather",
    description="Get weather for a city.",
    parameters={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
)
response = await adapter.generate_with_tools([user("Weather in SF?")], [weather])
for call in response.tool_calls:           # YOU dispatch — same as LangChain pattern
    print(call.name, call.arguments)
```

The shape is the same — *you* dispatch tools either way. Keel just makes the `ToolSpec` **vendor-neutral**: pass the same spec to `OpenAIAdapter` / `AnthropicAdapter` / `BedrockAdapter` / `GoogleAdapter` and the adapter handles the per-provider translation (OpenAI's `tools` vs Anthropic's `tools` vs Bedrock's `toolConfig` vs Gemini's `functionDeclarations`).

### 5. Observability — callbacks vs OTel

**LangChain:**

```python
from langchain.callbacks import StdOutCallbackHandler
chain.invoke("Hello", config={"callbacks": [StdOutCallbackHandler()]})
# proprietary callback format; LangSmith integration is the natural extension
```

**Keel:**

```python
# One line at startup, anywhere:
from keel_llm_otel.starter import setup
setup()

# That's it. Every ResilientClient call now emits OTel metrics + span events.
# Goes to Jaeger / Honeycomb / Datadog / Grafana Tempo / SigNoz / any OTel collector.
```

With `keel-llm-otel[full]` installed, `opentelemetry-instrumentation-httpx` also activates, so each provider HTTP call appears as a **real child span** with `traceparent` propagated to the provider. Full distributed tracing.

**Why this matters**: your LLM observability is now the same shape as the rest of your service infrastructure. No proprietary format. No SaaS lock-in (Helicone/Portkey/Langfuse). Open vendor-neutral signals you already know how to query.

### 6. Memory / conversation history

**LangChain:**

```python
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(chat_memory=ChatMessageHistory())
# ... wrapped through the runnable hierarchy
```

**Keel:** *deliberately not shipped.* Use:

```python
# Plain list (works fine for short conversations):
history: list[Message] = [system("..."), user("Hi"), assistant("Hello!"), user("How are you?")]
response = await adapter.generate(history)
history.append(assistant(response.text))
```

For persistent / window-bounded / summarized memory, plug in your own database call or use a tool you already trust. There's no `Memory` hierarchy to fight.

*(Keel may eventually ship a small `keel-llm-memory` lego of composable primitives — windowed / summarized / vector-backed — when consumer pain is articulated. Today, plain Python is enough.)*

### 7. Agents — the biggest mental shift

**LangChain:**

```python
from langchain.agents import create_react_agent, AgentExecutor

agent = create_react_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=10)
result = executor.invoke({"input": "Research X"})
```

**Keel — explicit loop:**

```python
async def research_agent(question: str, client: ResilientClient) -> str:
    # Step 1: planning
    plan = await client.failover(Request(messages=[
        system("Decide what to search for."), user(question)
    ]))
    query = plan.response.text

    # Step 2: tool call
    results = await search(query)

    # Step 3: synthesis
    synth = await client.failover(Request(messages=[
        system("Synthesize an answer from the search results."),
        user(f"Q: {question}\nResults: {results}"),
    ]))
    return synth.response.text
```

**Why this looks better than it sounds:**

- Each step is a real Python function with its own span in the trace tree (when `keel-llm-otel` is active).
- Behaviour is *visible* in your code — no `AgentExecutor.invoke` black box.
- Bug? Set a breakpoint. Want a different sequence? Move the lines. Need a loop? Use `for`.
- Testing is normal — each step is callable independently with normal mocks.

See the [`agentic-research`](../agentic-research) example in this repo for a full working version (with multi-model failover and OTel tracing).

For multi-agent patterns (orchestrator-workers, plan-act-reflect, swarm), Keel will ship `keel-agent-orchestration` as opt-in framework-shaped legos when consumer pain is articulated. Today, the explicit pattern is small enough that most teams prefer it over yet another framework.

---

## Migration strategy — incremental, not flag-day

You don't have to leave all at once. Here's the order most teams actually move:

### Step 1 — Add Keel for one new provider call

Pick one provider call (probably the throttled one). Replace the LangChain `ChatXYZ` invocation with `OpenAIAdapter` (or Anthropic / Bedrock / Gemini). Wrap in `ResilientClient([the_one_adapter])` so you get failover + breaker for free.

You're now running LangChain + Keel side by side. Nothing else changes.

### Step 2 — Replace LangChain's fallback chain with Keel's failover

When you outgrow `with_fallbacks` (or you want category-correct breaker behaviour), move your multi-model fallback to `ResilientClient`. Still alongside LangChain; just the LLM-call layer has moved.

### Step 3 — Add `keel-llm-otel[starter]` + `setup()`

One line, full OTel pipeline. Your LangChain calls won't emit (LangChain has its own callback model), but your Keel calls will. You can now *see* what your reliability layer is doing — without buying a SaaS.

### Step 4 — Migrate one chain at a time to explicit `async def`

This is the biggest shift, but it's incremental. Pick the chain that hurts most (usually the agent loop) and rewrite as `async def agent(...)`. Keel's reliability + observability come along for free.

Stop here if you want. Some teams keep LangChain for prompt templates / output parsers / retrievers and use Keel for the model + reliability + observability layer. **Composability allows it.**

### Step 5 — Remove LangChain entirely (optional)

If after Steps 1-4 LangChain is just `from langchain_core.prompts import PromptTemplate` for f-string interpolation, you've earned the right to remove it. f-strings are fine. Pydantic is fine. Most things LangChain wraps are 5-line Python.

---

## Common gotchas

- **Provider keys**: Keel doesn't read from `OPENAI_API_KEY` automatically (deliberate — you pass it explicitly so multi-tenant setups are obvious). Pull from your env in the adapter constructor.
- **Streaming**: `keel-llm-adapter-bedrock` doesn't ship streaming in 0.1.0 — Bedrock uses binary event-stream framing (not SSE), planned for 0.2. Check `adapter.capabilities` if you need it.
- **Output parsing**: there's no `PydanticOutputParser`. Use Pydantic directly on `response.text` (and consider `response_format={"type": "json_schema", ...}` where the adapter supports it).
- **`structured_output_honored`**: when you pass `response_format`, check `response.structured_output_honored` — it tells you whether the provider actually honored the request (`True`), degraded to best-effort (`False`), or you didn't ask (`None`). No silent degradation.
- **The agent loop**: don't try to recreate `AgentExecutor`. Write the loop you actually want.

---

## You're ready when

- Your highest-traffic LLM call is on `ResilientClient`.
- You can see your LLM calls in your OTel backend.
- The next time a provider 429s, your dashboard shows graceful failover instead of cascading failures.

Most teams report **2–6 weeks** for incremental migration, depending on how deeply LangChain is woven through. The first 80% of the value lands in week 1 (Steps 1–3); the rest is opportunistic cleanup.

---

## Next steps

- Try the [agentic-research demo](../agentic-research) — a working multi-step agent in ~80 LOC, end-to-end OTel.
- Read each package's "Is this for you?" segmentation on PyPI before adopting — the honest "skip when…" guidance applies even when migrating.
- File an issue if a LangChain pattern you depend on isn't covered above.

## The Keel toolkit

[`keel-llm-reliability`](https://pypi.org/project/keel-llm-reliability/) · [`keel-llm-protocol`](https://pypi.org/project/keel-llm-protocol/) · [`keel-llm-adapter-openai`](https://pypi.org/project/keel-llm-adapter-openai/) · [`keel-llm-adapter-anthropic`](https://pypi.org/project/keel-llm-adapter-anthropic/) · [`keel-llm-adapter-google`](https://pypi.org/project/keel-llm-adapter-google/) · [`keel-llm-adapter-bedrock`](https://pypi.org/project/keel-llm-adapter-bedrock/) · [`keel-circuit-breaker`](https://pypi.org/project/keel-circuit-breaker/) · [`keel-llm-otel`](https://pypi.org/project/keel-llm-otel/)

MIT licensed.
