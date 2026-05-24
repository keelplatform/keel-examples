<h1 align="center">keel-examples</h1>

<p align="center">
  <strong>Reference example apps for <a href="https://github.com/keelplatform">Keel</a> — production-grade reliability + observability for multi-LLM products.</strong><br/>
  <code>docker compose up</code>, see traces in 5 minutes.
</p>

<p align="center">
  <a href="https://pypi.org/project/keel-llm-reliability/"><img src="https://img.shields.io/pypi/v/keel-llm-reliability.svg?label=keel-llm-reliability&color=2b8a3e" alt="PyPI"></a>
  <a href="https://pypi.org/project/keel-llm-otel/"><img src="https://img.shields.io/pypi/v/keel-llm-otel.svg?label=keel-llm-otel&color=2b8a3e" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT">
</p>

---

## Examples

### [`agentic-research/`](./agentic-research)

A small multi-step research agent (plan → tool-call → synthesize) demonstrating multi-model reliability + distributed OTel tracing in **~80 lines of agent code**. `docker compose up` brings up Jaeger and an agent firing 24 concurrent runs across three mock providers with realistic reliability profiles — within seconds you see failover under load, backpressure-correct breaker behaviour, and the full trace tree in Jaeger.

**Start here.** No API keys required.

---

### More examples coming

This repo grows as Keel adds canonical patterns. Planned:
- `langchain-migration/` — side-by-side LangChain → Keel translations.
- `bedrock-multi-region/` — multi-region Bedrock failover for enterprise.
- `cost-aware-routing/` — budget-circuit-breaker pattern.

Want one prioritized? [Open an issue](https://github.com/keelplatform/keel-examples/issues).

## What Keel is

Composable libraries — not a framework — for multi-LLM reliability + observability: vendor-neutral typed errors, fan-out / failover with transparent degradation, circuit breaker, and OpenTelemetry emission. All on PyPI. See the [org overview](https://github.com/keelplatform).

MIT licensed.
