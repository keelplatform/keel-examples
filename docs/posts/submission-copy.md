# Submission copy — staged for T9 (do not auto-submit)

This file is a staging area: the post (`moving-off-langchain-to-keel.md`) plus the copy below get submitted *together* to discoverability channels. Submission is a user-action; do not auto-submit.

---

## Hacker News — Show HN (best fit) or general submission

**Title (under 80 chars, no clickbait, factual):**

> Show HN: Keel – Composable libraries replacing LangChain for multi-LLM reliability

*(Alternative if "Show HN" doesn't fit because adoption is small: `"Replacing LangChain with composable libraries: a measured 3/10 → 10/10 reliability story"`.)*

**URL:** the blog post URL (once published on a personal blog / dev.to / Substack).

**First comment (within 5 minutes of submission — frames the post, links to source):**

> Author here — happy to answer questions. The full code is open-source under MIT at github.com/keelplatform (`keel-llm-reliability`, `keel-llm-otel`, adapters for OpenAI-compat / Anthropic / Gemini / Bedrock). The reference agentic demo (`docker compose up` → traces in Jaeger in 5 min, no API keys) is at github.com/keelplatform/keel-examples/tree/main/agentic-research. The migration playbook walked through in the post is at github.com/keelplatform/keel-examples/tree/main/langchain-migration.
>
> Two things I'd be most curious to hear:
> 1. **For folks who've done a LangChain migration**: what pattern surprised you that I haven't covered in the playbook?
> 2. **For folks who've tried and *not* moved**: what kept you on LangChain? (Honest "we evaluated and stayed" stories help the playbook get more accurate.)

---

## Reddit — r/LocalLLaMA (likely best engagement)

**Title:**

> Composable libraries for multi-LLM reliability — moved off LangChain, here's what changed

**Body:**

> We replaced LangChain in a multi-model production stack (OpenAI + Anthropic + Gemini + Bedrock) with a portfolio of small composable libraries. The result was less code, better observability, and measurably better reliability (a throttled model went from 3/10 to 10/10 availability after fixing the "treat 429 as backpressure, not failure" handling).
>
> Full post with side-by-side code: [LINK]
>
> Open-source under MIT — github.com/keelplatform. The key packages:
> - `keel-llm-reliability` — `ResilientClient` with category-correct breaker + failover (a 429 doesn't trip the model's circuit)
> - `keel-llm-otel` — pure OpenTelemetry overlay, no SaaS coupling
> - Adapters for OpenAI-compatible (Groq/OpenRouter/Mistral/vLLM/Ollama all work), Anthropic, Gemini, Bedrock
>
> 5-minute demo: `git clone keel-examples && cd agentic-research && docker compose up` → traces in Jaeger, no API keys needed.
>
> Not anti-LangChain — if you're prototyping, LangChain is still great. This is for the conversation about "what comes next when you've outgrown the framework shape."
>
> Migration playbook with the common LangChain → Keel patterns: [LINK]

---

## Reddit — r/MachineLearning

**Title:**

> [Project] Keel: composable libraries for multi-LLM reliability + observability (alternative to framework-style LLM stacks)

**Body:** *(slightly more technical-audience phrasing)*

> Sharing a portfolio of open-source libraries (MIT, on PyPI) we've been building as a vendor-neutral alternative to framework-style LLM stacks.
>
> Architecture:
> - `keel-llm-protocol` — typed errors + adapter interface across providers
> - `keel-llm-reliability` — category-dispatched failover (defer/retry/fail-fast), transparent `Attempt` trail
> - `keel-llm-otel` — OpenTelemetry signals; can also consume non-Keel orchestrator trails via a structural `AttemptLike` Protocol
> - Adapters for OpenAI-compatible / Anthropic / Gemini / Bedrock
>
> The headline measured result: treating a 429 as backpressure (rather than failure) keeps a throttled model from being spuriously circuit-broken. Took a throttled provider from 3/10 → 10/10 availability in our pipeline.
>
> Migration playbook off LangChain (side-by-side patterns): [LINK]
> Reference agentic demo (docker compose up → Jaeger traces, no API keys): [LINK]
>
> Genuinely interested in critique — what's missing, what's wrong, what's the gnarliest LangChain pattern we haven't addressed yet.

---

## awesome-llm GitHub lists

Submit PRs to add Keel under the appropriate sections of:

- `awesome-llm` (the main one): `Inference` or `Tooling` section.
- `awesome-llm-apps`: under `Frameworks` or `Reliability` section.
- `awesome-langchain` (counterintuitively useful): there's usually an `Alternatives` section.

PR template:

```markdown
- [keelplatform/keel](https://github.com/keelplatform) — Composable, vendor-neutral libraries for multi-LLM reliability + OpenTelemetry observability. Library-not-framework alternative to LangChain. MIT.
```

---

## Timing notes

- **HN: weekdays, 7-9am PT** (best front-page chance; avoid weekends).
- **Reddit r/LocalLLaMA: any day, but evenings PT** get higher engagement.
- **Submit HN + r/LocalLLaMA + r/MachineLearning on different days** (1-3 days apart) so each gets its own discussion thread without cannibalizing.
- **awesome-llm PRs: anytime**; PRs review on their own cadence.

## Engagement plan

- **First 2 hours after each submission**: respond to every top-level comment within ~15 minutes. The post-launch window decides how the thread goes.
- **Don't argue defensively.** Comments like "but LangChain does X!" — acknowledge, link to the migration playbook's relevant section, move on.
- **Pull genuine criticism back into the playbook / README.** Every "you didn't cover Y" comment that's right → file as an issue and update the docs.

---

*This file is a staging area for T9 — submission is the user's action. The submissions themselves go through (in order of priority): personal blog or dev.to → HN → r/LocalLLaMA → r/MachineLearning → awesome-* PRs.*
